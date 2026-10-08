"""Run the cable net analysis on the real 5 sided form export through the
studio's own routes, in process, and print what it found. What this prints
is the deliverable of spec 2026-10-08: how many nodes must be grabbed, where,
what the columns carry, and whether a designed system holds the skin.

Usage, from the repo root under the solver interpreter:

    .venv/Scripts/python.exe bench/scripts/cablenet_real.py
        [--material tile] [--pattern bonded-courses] [--size 1.0]
        [--thickness 0.02] [--prestress 300] [--study "5 sided form"]

The export folder is the one the studio remembers in bench/studio/settings.json.
The script reads it and writes only under bench/studies/.

Exits 2 when the export is not on this machine, 1 when the run fails.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))
sys.path.insert(0, str(REPO / "src"))


def summarise(demand):
    held = demand.get("held") or {}
    placement = demand.get("placement") or {}
    acceptance = demand.get("acceptance")
    print("schema {}  prestress {} N  EA {} N  acceptance {} ({})".format(
        demand.get("schema"), demand.get("prestress"), demand.get("ea_newtons"),
        "none" if acceptance is None else "{:.2f} mm".format(acceptance),
        demand.get("acceptance_source")))
    if demand.get("note"):
        print("note:", demand["note"])
    print("held: {} wire nodes, {} column heads, {} actuators".format(
        len(held.get("wire_nodes") or []), len(held.get("column_heads") or []),
        len(held.get("actuators") or [])))
    # the size of the net, so that the grabbed count can be read against it
    net = demand.get("net") or {}
    nodes = len(net.get("node_of") or {})
    beyond_columns = nodes - len(held.get("column_heads") or [])
    grabbed = len(held.get("actuators") or [])
    print("net: {} nodes, {} members; {} are not column heads, of which {} were grabbed and {} were not".format(
        nodes, net.get("net_edge_count"), beyond_columns, grabbed, beyond_columns - grabbed))
    print("placement at {}: batch {} steps {} reached {}".format(
        placement.get("stage"), placement.get("batch"), placement.get("steps"),
        placement.get("reached")))
    if placement.get("stranded"):
        print("  stranded (no tension-only hold possible):", placement["stranded"][:20])
    for point in placement.get("curve") or []:
        print("  {:5d} grabbed  worst sag {:10.1f} mm  worst unbalanced {:8.1f} N  norm {:10.1f} N".format(
            point["count"], point["worst_sag_mm"], point["worst_residual_newtons"],
            point["residual_norm_newtons"]))
    print("first actuators chosen:", (held.get("actuators") or [])[:20])
    print()
    print("{:>6} {:>7} {:>10} {:>10} {:>10} {:>10} {:>9} {:>10}".format(
        "stage", "kind", "wire N", "actuator N", "dev mm", "after mm", "reach", "column N"))
    for stage in demand.get("stages") or []:
        wire = max(stage.get("wire_tensions") or [0.0])
        actuator = max([sum(c * c for c in f) ** 0.5 for f in stage.get("actuator_forces") or []] or [0.0])
        column = max([c["newtons"] for c in stage.get("column_forces") or []] or [0.0])
        print("{:>6} {:>7} {:10.1f} {:10.1f} {:10.1f} {:10.1f} {:>9} {:10.1f}".format(
            stage["name"], stage["kind"], wire, actuator, stage["deviation"],
            stage["residual_after"], str(stage["reachable"]), column))
    worst = None
    for stage in demand.get("stages") or []:
        for column in stage.get("column_forces") or []:
            if worst is None or column["newtons"] > worst[0]:
                worst = (column["newtons"], stage["name"], column.get("node"), column.get("vertical"))
    if worst is not None:
        print("worst column: {:.1f} N at {}, node {} (vertical part {:.1f} N)".format(*worst))
    print()
    print("sizing:", demand.get("sizing"))


def factor_words(factor):
    """A load factor block as one phrase: the factor and the part that binds."""

    factor = factor or {}
    limit = factor.get("limit_factor")
    return "{} binds on {}".format(
        "none" if limit is None else "{:.1f}".format(limit),
        factor.get("binding_part") or "nothing")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="5 sided form")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--pattern", default="bonded-courses")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=0.02)
    parser.add_argument("--prestress", type=float, default=300.0)
    args = parser.parse_args()
    # redirected to a file, as the usage above does, a block-buffered run shows
    # nothing until it ends
    sys.stdout.reconfigure(line_buffering=True)

    import geometry
    import bundle
    import staging
    from fastapi.testclient import TestClient
    import app as studio_app

    # create_app does not read settings.json, serve.py does, before it builds
    # the app: without this the export is looked for in the repo's demo folder
    studio_app.apply_saved_folder()
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if args.study not in pairs:
        print("the export {!r} is not in {}".format(args.study, bundle.UPLOAD_DIR))
        return 2
    print("export folder:", bundle.UPLOAD_DIR)
    client = TestClient(studio_app.create_app())
    options = {"material": args.material, "pattern": args.pattern, "size": args.size,
               "thickness": args.thickness}
    started = client.post("/api/studies/{}/cablenet/run".format(args.study),
                          json={**options, "prestress": args.prestress})
    print("run:", started.status_code, started.json())
    if started.status_code not in (202, 409):
        return 1
    run_id = started.json()["run"]
    began = time.time()
    while True:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            break
        print("  {:5.0f} s  {}  {}".format(time.time() - began, state["phase"], state["message"]))
        time.sleep(5)
    print("run {} after {:.0f} s {}".format(state["state"], time.time() - began, state["message"]))
    if state["state"] != "done":
        return 1
    slot = staging.cut_slot(pairs[args.study], args.pattern)
    print("cut source: {}  demand document: {}".format(
        slot.cut_source,
        bundle.cablenet_path(geometry.slugify(args.study), args.material, slot.key_pattern,
                             args.size, args.thickness, None)))
    response = client.get("/api/studies/{}/cablenet".format(args.study), params=options)
    if response.status_code != 200:
        print("the demand could not be read:", response.status_code, response.text)
        return 1
    summarise(response.json())
    print()
    response = client.post("/api/studies/{}/cablenet/recommend".format(args.study),
                           json={"angle_degrees": 10.0, "options": options})
    if response.status_code != 200:
        print("the recommendation could not be made:", response.status_code, response.text)
        return 1
    recommended = response.json()
    for row in recommended["rows"]:
        if row.get("refused"):
            print("  {:28} refused: {}".format(row["key"], row["refused"]))
            continue
        line = "  {:28} load factor {}".format(row["key"], factor_words(row.get("load_factor")))
        if row.get("parts_factor"):
            # the shape is past the line, so no part can change it; the parts' own
            # factor is what ranks the rigs
            line += "  |  parts alone {}".format(factor_words(row["parts_factor"]))
        print(line)
    print("recommend:", recommended["key"], "|", recommended["rule"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
