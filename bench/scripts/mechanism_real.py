"""Judge the five choices on the real 5 sided form export, in process: the
cable net demand through the studio's own routes, as the Cable net panel
judges it, and the formwork engine's captures through the same machine
functions; print what was found (spec 2026-10-09 mechanism choices,
section 9).

Usage, from the repo root under the solver interpreter:

    .venv/Scripts/python.exe bench/scripts/mechanism_real.py
        [--study "5 sided form"] [--material tile] [--pattern bonded-courses]
        [--size 1.0] [--thickness 0.02] [--angle 10]

The export folder is the one the studio remembers in bench/studio/settings.json.
The script reads it and the study's documents under bench/studies/, and writes
nothing.

Exits 2 when the export is not on this machine, 1 when a route refuses or a
document is missing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))
sys.path.insert(0, str(REPO / "src"))


def formwork_peaks(document):
    """Each rim wire's greatest tension over the formwork engine's captures, in
    N, and the capture in which the greatest of them is reached."""

    from solve_formwork import unpack

    peaks, where, top = [], None, None
    for capture in document["captures"]:
        tension = [float(t) for t in unpack(capture["wire_tension"])]
        peaks = tension if not peaks else [max(a, b) for a, b in zip(peaks, tension)]
        if tension and (top is None or max(tension) > top):
            top, where = max(tension), capture
    return peaks, where


def where_of(capture):
    """A capture's phase and its moment: a machine time, or a row's quarter."""

    if capture["time"] is not None:
        return "{} t {:g}".format(capture["phase"], capture["time"])
    return "{} {} q{}".format(capture["phase"], capture["row"], capture["quarter"])


def captures_over(document, newtons):
    """The captures in which some wire pulls harder than the given tension."""

    from solve_formwork import unpack

    return [where_of(capture) for capture in document["captures"]
            if max((float(t) for t in unpack(capture["wire_tension"])), default=0.0) > newtons]


def recommend_lines(result):
    """Recommend's answer as two lines: the machine and its numbers."""

    if result["holds"]:
        floor = (" (floor: {})".format(", ".join(result["unpriced"]))
                 if result.get("unpriced") else "")
        return ["recommend: {}".format(result["described"]),
                "  GBP {:.2f}{}; worst {}, {}, {:.2f}x{}".format(
                    result["priced_gbp"], floor, result["limit"], result["part"],
                    result["margin"], "; run to confirm" if result.get("confirm_run") else "")]
    closest = result.get("closest")
    if closest is None:
        return ["recommend: none holds, and none could be judged"]
    return ["recommend: none holds",
            "  closest {}; {}, {}, {:.3f}x".format(
                closest["described"], closest["limit"], closest["part"], closest["margin"])]


def row_lines(row):
    """One judged set of choices as lines: the verdict, the travel, the wire
    to buy and the price."""

    if row.get("refused"):
        return ["refused: {}".format(row["refused"])]
    verdict, travel, price = row["verdict"], row["travel"], row["price"]
    worst = verdict["worst"]
    drum, carriage = travel["worst_drum"], travel["worst_carriage"]
    cuts = [cut["length_mm"] / 1000.0 for cut in row["cut_lengths"]]
    best = price["rope"]["best"]
    lines = [
        "machine: {}".format(row["described"]),
        "  verdict {}: worst {}, {}, wire {}, {:.0f} N, {:.2f}x; pairing {}; {} machines".format(
            "holds" if verdict["holds"] else "does not hold", worst["limit"], worst["part"],
            worst["wire"], verdict["wires"][worst["wire"]]["tension"], worst["margin"],
            verdict["pairing"], len(verdict["machines"])),
        "  drum {:.0f} of {:.0f} mm, carriage {:.1f} of {:.0f} mm, travel {}".format(
            drum["drum_rope_mm"], drum["drum_capacity_mm"], carriage["carriage_mm"],
            carriage["stroke_mm"], "fits" if travel["fits"] else "does not fit"),
        "  wire: {:.1f} m in {} cut lengths of {:.2f} to {:.2f} m, bought {}{}".format(
            price["rope"]["total_m"], len(cuts), min(cuts), max(cuts),
            "nowhere" if best is None else best["buy"],
            "" if best is None else ", GBP {:.2f}".format(best["cost_gbp"])),
        "  price GBP {:.2f}{}; {} cabinets, GBP {:.2f} of it".format(
            price["priced_gbp"], " (a floor)" if price["unpriced"] else "",
            len(price["cabinets"]["cabinets"]), price["cabinets"]["priced_gbp"]),
    ]
    return lines


def study_facts(study, ea):
    """What the export says about the machine, read as the studio reads it:
    the vault's mechanism document with the machine it cites folded in."""

    import bundle
    import geometry
    import machine
    import mechanism

    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    contract = geometry.load_contract(pairs[study]["contract"])
    design_mm = [[c * 1000.0 for c in point]
                 for point in geometry.mesh_arrays(contract)["vertices"]]
    sidecar = bundle.mechanism_sidecar(study)
    document = bundle._read_optional(sidecar)
    ident = mechanism.cited_machine_id(document)
    if ident:
        cited = json.loads((sidecar.parent / (ident + mechanism.MACHINE_SUFFIX))
                           .read_text(encoding="utf-8"))
        document = mechanism.merge_cited_machine(document, cited)
    return machine.facts_from(document, design_mm, geometry.support_ids(contract), ea)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="5 sided form")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--pattern", default="bonded-courses")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=0.02)
    parser.add_argument("--angle", type=float, default=10.0)
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    import bundle
    import catalogue
    import geometry
    import recommend
    from fastapi.testclient import TestClient
    import app as studio_app

    # create_app does not read settings.json, serve.py does, before it builds
    # the app: without this the export is looked for in the repo's demo folder
    studio_app.apply_saved_folder()
    if args.study not in geometry.available_exports(bundle.UPLOAD_DIR):
        print("the export {!r} is not in {}".format(args.study, bundle.UPLOAD_DIR))
        return 2
    print("export folder:", bundle.UPLOAD_DIR)
    client = TestClient(studio_app.create_app())
    options = {"material": args.material, "pattern": args.pattern, "size": args.size,
               "thickness": args.thickness}

    offered = client.get("/api/catalogue").json()["choices"]
    print("catalogue: {} motors, {} wires, {} wires-a-motor counts, {} combinations".format(
        len(offered["motors"]), len(offered["ropes"]), len(offered["wires_per_motor"]),
        len(list(recommend.combinations(catalogue.load_parts())))))

    # the cable net demand, as the panel judges it
    print("== the cable net demand ==")
    began = time.time()
    reply = client.post("/api/studies/{}/cablenet/recommend".format(args.study),
                        json={"options": options, "angle_degrees": args.angle})
    if reply.status_code != 200:
        print("recommend refused:", reply.status_code, reply.text[:300])
        return 1
    result = reply.json()
    print("searched in {:.1f} s".format(time.time() - began))
    for line in recommend_lines(result):
        print(line)
    if result["holds"]:
        for line in row_lines(result["row"]):
            print(line)

    # the formwork engine's captures, through the same functions
    print("== the formwork captures ==")
    response = client.get("/api/studies/{}/formwork/sim".format(args.study), params=options)
    if response.status_code != 200:
        print("the captures could not be read:", response.status_code, response.text[:300])
        return 1
    document = json.loads(response.content)
    peaks, where = formwork_peaks(document)
    parts = catalogue.load_parts()
    facts = study_facts(args.study, float(parts["rope"]["rope-4mm"]["ea_newtons"]))
    # the captures list the rim's nodes sorted; the export's facts list them as
    # the export draws them, so the peaks are matched by node
    by_node = dict(zip(document["rim"]["nodes"], peaks))
    if set(by_node) != set(facts["nodes"]):
        print("the captures' wires are not the export's; nothing judged")
        return 1
    peaks = [by_node[node] for node in facts["nodes"]]
    print("{} wires on {} machines; the greatest tension {:.0f} N, at {}".format(
        len(peaks), len(facts["machines"]), max(peaks), where_of(where)))
    key, rope = max(parts["rope"].items(), key=lambda item: float(item[1]["rope_mbl"]))
    working = float(rope["rope_mbl"]) / 5.0
    over = captures_over(document, working)
    print("{} of {} wires peak above {:.0f} N, a fifth of {}'s breaking load, in {} of {} "
          "captures: {}".format(sum(1 for p in peaks if p > working), len(peaks), working, key,
                                len(over), len(document["captures"]),
                                ", ".join(over) if over else "none"))
    began = time.time()
    # the reels' travel through the raise is part 3's: judged here on tension alone
    held = recommend.recommend(parts, facts, peaks, facts["machines"], facts["routes_mm"],
                               [[0.0] for _ in peaks], args.angle)
    print("searched in {:.1f} s".format(time.time() - began))
    for line in recommend_lines(held):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
