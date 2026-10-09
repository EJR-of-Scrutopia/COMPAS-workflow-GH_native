"""The formwork engine, run as its own process (spec 2026-10-09 section 7).

It reads the request formwork_sim.py builds, in millimetres and newtons, runs
the sequence in tree_forest_compas.formwork_sequence, and writes the capture
document, schema bench.formwork-sim/1: a JSON index with every position and
force as base64 little-endian float32 arrays, which the browser decodes
directly and the studio's server never parses with numpy (section 4.5).

Like solve_stage.py, solve_cra.py and solve_cablenet.py, this file is a
deliberate exception to the studio guard: it runs under the repo's main .venv,
never in the server's process. formwork_sim.py starts it as a subprocess:

    .venv/Scripts/python.exe bench/studio/solve_formwork.py request.json out.json

A line goes to stdout for every capture, "progress <done> <total> <what>". A
run the engine refuses prints the reason to stderr and exits 1.
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import numpy as np

from tree_forest_compas import formwork_sequence as fs
from tree_forest_compas import net_engine as ne
from tree_forest_compas import trees as tr

SCHEMA = "bench.formwork-sim/1"


def pack(values):
    """An array as the document carries it: its shape, and its values as base64
    of little-endian float32."""

    array = np.ascontiguousarray(np.asarray(values, dtype="<f4"))
    return {"shape": list(array.shape), "f32": base64.b64encode(array.tobytes()).decode("ascii")}


def unpack(entry):
    """The array that pack wrote, as float32 in its shape."""

    flat = np.frombuffer(base64.b64decode(entry["f32"]), dtype="<f4")
    return flat.reshape(entry["shape"])


def model_from(request):
    """The engine's model from the request: lengths in mm, forces in N, the
    skin as each quarter's vertical loads at the nodes it reaches."""

    design = np.asarray(request["design"], dtype=float).reshape(-1, 3)
    count = len(design)
    rim = {int(wire["node"]): fs.RimWire(np.asarray(wire["anchor"], dtype=float),
                                         np.asarray(wire["into"], dtype=float),
                                         float(wire["stiffness"]))
           for wire in request["rim"]}
    frames = [fs.Frame(float(frame["time"]), str(frame["phase"]),
                       np.asarray(frame["net"], dtype=float).reshape(-1, 3),
                       np.asarray(frame["trees"], dtype=float).reshape(-1, 3))
              for frame in request["frames"]]
    rows = []
    for row in request["rows"]:
        quarters = []
        for quarter in row["quarters"]:
            skin = np.zeros((count, 3))
            skin[np.asarray(quarter["nodes"], dtype=int), 2] = np.asarray(quarter["z"], dtype=float)
            quarters.append(skin)
        rows.append(fs.Row(str(row["name"]), quarters))
    return fs.Model(
        design=design, edges=np.asarray(request["edges"], dtype=int).reshape(-1, 2),
        ea=float(request["ea"]), weight=np.asarray(request["weight"], dtype=float).reshape(-1, 3),
        prestress=float(request["prestress"]), rim=rim,
        heads=[(int(net), int(tree)) for net, tree in request["heads"]],
        tree_members=np.asarray(request["tree_members"], dtype=int).reshape(-1, 2),
        tree_feet=[int(foot) for foot in request["tree_feet"]], frames=frames, rows=rows,
        machines=[[int(node) for node in machine] for machine in request["machines"]],
        wires_per_motor=int(request["wires_per_motor"]), wall=float(request["wall"]))


def _capture_entry(capture):
    return {
        "phase": capture.phase, "time": capture.time, "row": capture.row,
        "quarter": capture.quarter, "solver": capture.solver,
        "iterations": int(capture.iterations), "leftover": float(capture.leftover),
        "x": pack(capture.x), "tension": pack(capture.tension),
        "deviation": pack(capture.deviation), "head_push": pack(capture.head_push),
        "anchor_force": pack(capture.anchor_force), "wire_tension": pack(capture.wire_tension),
        "reel": pack(capture.reel), "let_out": pack(capture.let_out),
        "tree_x": pack(capture.tree_x), "tree_axial": pack(capture.tree_axial),
        "tree_utilisation": pack(capture.tree_utilisation),
        "tree_bending": {str(node): [float(v) for v in load]
                         for node, load in capture.tree_bending.items()},
    }


def _summary(result):
    """The few figures a reader wants first, every one read from the captures."""

    raised = [c for c in result.captures if c.phase != "tiling"]
    tiled = [c for c in result.captures if c.phase == "tiling"]
    every = result.captures

    def largest(captures, field):
        return max((float(np.max(getattr(c, field), initial=0.0)) for c in captures), default=None)

    return {
        "captures": len(every),
        # spec section 8, test 10: how close the end of the raise sits to the
        # designed shape, reported and not judged
        "raise_deviation_max_mm": None if not raised else float(raised[-1].deviation.max()),
        "tiling_deviation_max_mm": None if not tiled else float(tiled[-1].deviation.max()),
        "wire_tension_max_n": largest(every, "wire_tension"),
        "let_out_max_mm": largest(every, "let_out"),
        "tree_utilisation_max": largest(every, "tree_utilisation"),
        "relaxation_captures": sum(1 for c in every if c.solver == "relaxation"),
    }


def solve(request, progress=None):
    """The capture document for one request."""

    model = model_from(request)
    began = time.perf_counter()
    result = fs.simulate(model, progress)
    seconds = time.perf_counter() - began
    rim = sorted(model.rim)
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    reeves = {int(wire["node"]): int(wire.get("reeve") or 1) for wire in request["rim"]}
    routes = {int(wire["node"]): wire.get("route_mm") for wire in request["rim"]}
    return {
        "schema": SCHEMA,
        "study": request.get("study"),
        "units": "mm, N",
        "options": request.get("options"),
        "note": request.get("note"),
        "assumptions": list(request.get("assumptions") or []),
        "seconds": round(seconds, 1),
        "net": {
            "nodes": len(model.design), "edges": model.edges.tolist(),
            "ea": model.ea, "prestress": model.prestress, "design": pack(model.design),
            "rest_lengths": pack(result.rest_lengths), "cut_force": pack(result.cut_force),
        },
        "rim": {
            "nodes": rim, "names": [names.get(node) for node in rim],
            "anchors": pack([model.rim[node].anchor for node in rim]),
            "into": pack([model.rim[node].into for node in rim]),
            "stiffness": pack([model.rim[node].stiffness for node in rim]),
            # each wire's reeving and route, so a tension becomes its drum's
            # (spec 2026-10-09 mechanism choices, section 4.7)
            "reeve": [reeves.get(node, 1) for node in rim],
            "route_mm": [None if routes.get(node) is None else float(routes[node])
                         for node in rim],
            "machines": model.machines, "wires_per_motor": model.wires_per_motor,
            # per machine, the spools each motor carries; null at one a motor
            "motors": None if result.groups is None else [
                [[int(node) for node in group] for group in machine] for machine in result.groups],
        },
        "trees": {
            "members": model.tree_members.tolist(), "feet": model.tree_feet,
            "heads": [[net, tree] for net, tree in model.heads],
            "diameter": tr.DIAMETER, "wall": result.wall,
            "thinnest_wall": result.thinnest_wall,
        },
        "captures": [_capture_entry(capture) for capture in result.captures],
        "summary": _summary(result),
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: solve_formwork.py <request.json> <out.json>", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    def progress(done, total, what):
        print("progress {} {} {}".format(done, total, what), flush=True)

    try:
        document = solve(request, progress)
    except ne.EngineError as error:
        print(str(error), file=sys.stderr)
        return 1
    Path(sys.argv[2]).write_text(json.dumps(document, allow_nan=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
