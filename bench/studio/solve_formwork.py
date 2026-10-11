"""The formwork engine, run as its own process (spec 2026-10-09 section 7).

It reads the request formwork_sim.py builds, in millimetres and newtons, runs
the sequence in tree_forest_compas.formwork_sequence, and writes the capture
document, schema bench.formwork-sim/1: a JSON index with every position and
force as base64 little-endian float32 arrays, which the browser decodes
directly and the studio's server never parses with numpy (section 4.5).

Like solve_stage.py and solve_cra.py, this file is a
deliberate exception to the studio guard: it runs under the repo's main .venv,
never in the server's process. formwork_sim.py starts it as a subprocess:

    .venv/Scripts/python.exe bench/studio/solve_formwork.py request.json out.json

A line goes to stdout for every capture, "progress <done> <total> <what>". A
run the engine refuses prints the reason to stderr and exits 1.

A request may name state_out, where the sequence's state at the hold is
written, and state_in, a state written for the same request but its rods,
which a run starts from (spec 2026-10-11 one Cable net tab, section 7). The
state is gzipped JSON whose numbers are the engine's own doubles, so the run
from it is the full run to the bit; one written for another request, or none
readable, is a full run.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
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
        wires_per_motor=int(request["wires_per_motor"]), wall=float(request["wall"]),
        holds=tuple(int(node) for node in request.get("holds") or ()),
        sides=tuple(-1 if side is None else int(side) for side in request.get("sides") or ()),
        holds_per_side=int(request.get("holds_per_side") or 0),
        tendons=tuple(tuple(int(node) for node in line["path"])
                      for line in request.get("tendons") or ()))


# What a state does not depend on: the rods, where the state goes, and words.
NOT_IN_STATE = ("holds", "holds_per_side", "state_in", "state_out", "options", "note",
                "study", "assumptions")


def fingerprint(request):
    """What a state at the hold was worked out from: the request but its rods."""

    kept = {key: value for key, value in request.items() if key not in NOT_IN_STATE}
    return hashlib.sha256(json.dumps(kept, sort_keys=True).encode("utf-8")).hexdigest()


def _array(values):
    array = np.asarray(values, dtype=float)
    return {"shape": list(array.shape), "values": array.ravel().tolist()}


def _from_array(entry):
    return np.asarray(entry["values"], dtype=float).reshape(entry["shape"])


ARRAYS = ("x", "tension", "deviation", "head_push", "hold_push", "anchor_force",
          "wire_tension", "reel", "let_out", "tree_x", "tree_axial", "tree_utilisation",
          "tendon_tension")


def _capture_state(capture):
    entry = {field: _array(getattr(capture, field)) for field in ARRAYS}
    entry.update(phase=capture.phase, time=capture.time, row=capture.row,
                 quarter=capture.quarter, ground=[int(node) for node in capture.ground],
                 tree_bending=[[int(node), [float(v) for v in load]]
                               for node, load in capture.tree_bending.items()],
                 solver=capture.solver, iterations=int(capture.iterations),
                 leftover=float(capture.leftover))
    return entry


def _capture_from_state(entry):
    return fs.Capture(
        **{field: _from_array(entry[field]) for field in ARRAYS},
        phase=entry["phase"], time=entry["time"], row=entry["row"], quarter=entry["quarter"],
        ground=tuple(entry["ground"]),
        tree_bending={int(node): np.asarray(load, dtype=float)
                      for node, load in entry["tree_bending"]},
        solver=entry["solver"], iterations=entry["iterations"], leftover=entry["leftover"])


def write_state(path, state, print_):
    """The state at the hold, gzipped JSON, written whole or not at all."""

    contacts = state.contacts
    document = {
        "fingerprint": print_,
        "x": _array(state.x),
        "contacts": {
            "heads": [[int(node), [float(v) for v in at]] for node, at in contacts.heads.items()],
            "engaged": sorted(int(node) for node in contacts.engaged),
            "resting": [[int(node), [float(v) for v in at]]
                        for node, at in contacts.resting.items()],
            "seated": sorted(int(node) for node in contacts.seated),
            "left": sorted(int(node) for node in contacts.left),
            "tied": sorted(int(node) for node in contacts.tied)},
        "reel": [[int(node), float(value)] for node, value in state.reel.items()],
        "captures": [_capture_state(capture) for capture in state.captures],
        "rest_lengths": _array(state.rest_lengths), "cut_force": _array(state.cut_force),
        "groups": None if state.groups is None else [
            [[int(node) for node in group] for group in machine] for machine in state.groups],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    with gzip.open(partial, "wt", encoding="utf-8") as out:
        json.dump(document, out)
    os.replace(partial, path)


def read_state(path, print_):
    """The state written for this request, or None: none there, unreadable,
    or written for another."""

    try:
        with gzip.open(Path(path), "rt", encoding="utf-8") as source:
            document = json.load(source)
        if document.get("fingerprint") != print_:
            return None
        held = document["contacts"]
        contacts = ne.Contacts(
            heads={int(node): np.asarray(at, dtype=float) for node, at in held["heads"]},
            engaged=frozenset(held["engaged"]),
            resting={int(node): np.asarray(at, dtype=float) for node, at in held["resting"]},
            seated=frozenset(held["seated"]), left=frozenset(held["left"]),
            tied=frozenset(held["tied"]))
        return fs.HoldState(
            x=_from_array(document["x"]), contacts=contacts,
            reel={int(node): float(value) for node, value in document["reel"]},
            captures=[_capture_from_state(entry) for entry in document["captures"]],
            rest_lengths=_from_array(document["rest_lengths"]),
            cut_force=_from_array(document["cut_force"]), groups=document["groups"])
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        return None


def _capture_entry(capture, added_faces=None):
    return {
        "phase": capture.phase, "time": capture.time, "row": capture.row,
        "quarter": capture.quarter, "solver": capture.solver,
        "iterations": int(capture.iterations), "leftover": float(capture.leftover),
        "x": pack(capture.x), "tension": pack(capture.tension),
        "deviation": pack(capture.deviation), "head_push": pack(capture.head_push),
        "hold_push": pack(capture.hold_push), "tendon_tension": pack(capture.tendon_tension),
        "anchor_force": pack(capture.anchor_force), "wire_tension": pack(capture.wire_tension),
        "reel": pack(capture.reel), "let_out": pack(capture.let_out),
        "tree_x": pack(capture.tree_x), "tree_axial": pack(capture.tree_axial),
        "tree_utilisation": pack(capture.tree_utilisation),
        "tree_bending": {str(node): [float(v) for v in load]
                         for node, load in capture.tree_bending.items()},
        # what the Formwork tab draws the ground contacts and the skin from
        # (spec 2026-10-10 formwork tab, section 4): the nodes the ground
        # holds, and for a tiling quarter the faces it placed
        "ground": [int(node) for node in capture.ground],
        "added_faces": None if added_faces is None else [int(face) for face in added_faces],
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
        # spec 2026-10-10 formwork holds, section 4: what the search judges, the
        # worst deviation from the jacking on, every node counted
        "holds_deviation_max_mm": None if not any(c.phase == "holds" for c in every) else max(
            float(c.deviation.max()) for c in every if c.phase in ("holds", "tiling")),
        # spec 2026-10-11 across tendons, section 4: the most any tendon carries
        "tendon_tension_max_n": None if not any(len(c.tendon_tension) for c in every) else max(
            float(c.tendon_tension.max()) for c in every if len(c.tendon_tension)),
    }


def solve(request, progress=None):
    """The capture document for one request."""

    model = model_from(request)
    print_ = fingerprint(request)
    state = None if not request.get("state_in") else read_state(request["state_in"], print_)
    began = time.perf_counter()
    result = fs.simulate(model, progress, state=state)
    seconds = time.perf_counter() - began
    if request.get("state_out") and state is None:
        write_state(request["state_out"], result.state, print_)
    sides = list(model.sides)
    rim = sorted(model.rim)
    names = {int(wire["node"]): wire.get("name") for wire in request["rim"]}
    # each tiling quarter's faces, in the order the sequence captures them; an
    # older request names none
    added = [quarter.get("faces") for row in request["rows"] for quarter in row["quarters"]]
    tiled = iter(added)
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
        # whether the run started from a saved state at the hold
        "resumed": state is not None,
        # each tendon's line and its length at the design (spec 2026-10-11
        # across tendons, section 4); null for a run without
        "tendons": None if not model.tendons else {"lines": [
            {"head": line.get("head"), "side": line.get("side"),
             "path": [int(node) for node in line["path"]],
             "design_length_mm": float(length)}
            for line, length in zip(request["tendons"], fs._line_lengths(model, model.design))]},
        "net": {
            "nodes": len(model.design), "edges": model.edges.tolist(),
            "ea": model.ea, "prestress": model.prestress, "design": pack(model.design),
            "rest_lengths": pack(result.rest_lengths), "cut_force": pack(result.cut_force),
            "faces": None if request.get("faces") is None else [
                [int(i) for i in face] for face in request["faces"]],
            "holds": [int(node) for node in result.holds],
            "holds_per_side": int(model.holds_per_side),
            "hold_sides": [sides[node] if node < len(sides) else None
                           for node in result.holds] if sides else None,
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
        "captures": [_capture_entry(capture, next(tiled) if capture.phase == "tiling" else None)
                     for capture in result.captures],
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
