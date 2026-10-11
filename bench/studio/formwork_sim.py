"""The seam between a study and the formwork engine (spec 2026-10-09).

This module needs no solver: the engine runs in solve_formwork.py, a
subprocess under the main .venv, and this file only builds its request and
writes the capture document where the studio reads it. The study's documents
are in metres and the engine works in millimetres and newtons; the conversion
happens here and nowhere else.

What the request is built from:
- the net, its weight and the skin from the study's one cut
  (staging.cut_and_plan): the skin a row at a time, each row in four
  quarters, each quarter a run of the row's pieces in the order the
  animation drops them (spec section 4.2);
- the rim wires from the mechanism document: where each wire enters its
  anchor and the way it runs in, from the first points of its route taken
  into world space by its machine instance's frame, and the stiffness of the
  reeved rope inside, MA^2 EA / L_route (section 3.2);
- the trees and their motion from the formwork document, from machine time
  30 on: the reel phase before it is the net being laid out by people
  (section 4.1).
"""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, NamedTuple

import bundle
import cablenet
import frames
import geometry
import staging

FORMWORK_PYTHON = staging.REPO / ".venv" / "Scripts" / "python.exe"
SOLVE_FORMWORK = Path(__file__).resolve().parent / "solve_formwork.py"
RAISE_FROM = 30.0       # the machine time the engine starts at (spec section 4.1)
FREE_SPAN_MM = 1.0      # a rim node further than this from where its wire enters
                        # the anchor would hang on a free span of wire
QUARTERS = 4            # the steps each row of skin goes on in


class FormworkError(RuntimeError):
    """A study that cannot be run through the formwork engine, with the reason."""


class Inputs(NamedTuple):
    """What the engine takes from the study's documents, read and checked
    before the cut, so a study that cannot run is told before the slow part."""

    rim: list               # a dict a wire: node, name, anchor and into (mm), stiffness (N/mm),
                            # route_mm, reeve
    machines: list          # per machine instance, its rim nodes in spool order
    heads: list             # [net node, tree node] pairs
    tree_members: list      # [u, v] pairs of tree nodes
    tree_feet: list         # tree nodes standing on the ground
    frames: list            # {time, phase, net, trees}, mm, from machine time 30 on
    assumptions: list       # sentences the capture document carries


def _distance(a, b):
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def _world_mm(frame, local):
    return [c * 1000.0 for c in cablenet.frame_to_world(frame, local)]


def rim_wires(mechanism_document, design_mm, supports, ea, pulleys=True):
    """Each rim wire as the engine holds it (spec section 3.2): where it enters
    its anchor, the unit vector it runs in along, and the stiffness of the
    reeved rope inside, MA^2 EA / L_route, with the route's length.

    A route in the current shape is in its machine instance's own space and
    runs from the net end to the drum; the instance's frame takes it into
    world space. The older nested shape names only the machine point, so its
    wire is taken to run straight from its node to that point. A rim node away
    from where its wire enters the anchor would hang on a free span of wire,
    which this engine does not model yet, so it is refused.

    Without pulleys (pulleys False, the owner's "no" of 9 October 2026) every
    wire runs straight off its drum on one fall, whatever its reeving.
    """

    try:
        wires = cablenet.wires_from_mechanism(mechanism_document, len(design_mm), supports)
    except cablenet.CableNetError as error:
        raise FormworkError(str(error)) from error
    document = mechanism_document or {}
    routes = document.get("wires") or []
    instance_frames = {(instance.get("side"), instance.get("mechanism")): instance.get("frame")
                       for instance in document.get("instances") or []}
    out = []
    for position, wire in enumerate(wires):
        node = design_mm[wire.net_vertex]
        if routes:
            entry = routes[position]
            step = entry["path"][0]
            frame = instance_frames[(step["side"], step["mechanism"])]
            points = [_world_mm(frame, point["origin"]) for point in entry["route"]]
            anchor = points[0]
            ahead = next((p for p in points[1:] if _distance(p, anchor) > 1.0e-6), None)
            route_mm = sum(_distance(a, b) for a, b in zip(points, points[1:]))
        else:
            anchor = list(node)
            ahead = list(wire.frame_point)
            route_mm = _distance(anchor, ahead)
        if ahead is None or route_mm <= 1.0e-6:
            raise FormworkError("Wire {!r} has a route of no length, so nothing says which way "
                                "it runs into its anchor.".format(wire.name))
        gap = _distance(anchor, node)
        if gap > FREE_SPAN_MM:
            raise FormworkError(
                "Wire {!r} enters its anchor {:.0f} mm from rim node {}, so a free span of "
                "wire would hang between them, and this engine does not model one yet "
                "(spec section 3.2).".format(wire.name, gap, wire.net_vertex))
        length = _distance(ahead, anchor)
        reeve = (int(wire.reeve_factor) if wire.reeve_factor else 1) if pulleys else 1
        out.append({
            "node": int(wire.net_vertex), "name": wire.name, "anchor": list(anchor),
            "into": [(a - b) / length for a, b in zip(ahead, anchor)],
            "stiffness": reeve ** 2 * float(ea) / route_mm, "route_mm": route_mm,
            "reeve": reeve, "reeve_given": bool(wire.reeve_factor) or not pulleys,
        })
    return out


def machines_of(mechanism_document, rim):
    """Each machine instance's rim nodes in spool order, from its wire ids. The
    older nested shape names no machines, and gives none."""

    node_of = {str(entry.get("id")): int(entry["net_vertex"])
               for entry in (mechanism_document or {}).get("wires") or []}
    held = {wire["node"] for wire in rim}
    machines = []
    for instance in (mechanism_document or {}).get("instances") or []:
        if instance.get("kind", "mechanism") != "mechanism":
            continue
        nodes = [node_of[str(i)] for i in instance.get("wireIds") or [] if str(i) in node_of]
        nodes = [node for node in nodes if node in held]
        if nodes:
            machines.append(nodes)
    return machines


def tree_inputs(document):
    """The trees from a validated formwork document: which tree node props which
    net node, the members and the feet."""

    columns = document.get("columns") or {}
    count = int(document.get("columnNodeCount") or 0)
    head_nodes = columns.get("headNode") or []
    heads = columns.get("heads") or []
    members = columns.get("members") or []
    if not head_nodes or len(head_nodes) != len(heads) or not members:
        raise FormworkError(
            "The formwork document names no trees to raise the net with: it needs columns "
            "with heads, the net nodes they prop (headNode) and members.")
    pairs = [[int(net), int(tree)] for net, tree in zip(head_nodes, heads)]
    edges = [[int(member["u"]), int(member["v"])] for member in members]
    feet = [int(foot) for foot in columns.get("feet") or []]
    used = [tree for _, tree in pairs] + [i for edge in edges for i in edge] + feet
    if any(not 0 <= i < count for i in used):
        raise FormworkError("The formwork document's columns name tree nodes outside its "
                            "0 to {}.".format(count - 1))
    return pairs, edges, feet


def frames_from(document):
    """The frames the engine follows, from machine time 30 on, in millimetres."""

    out = [{"time": frame["time"], "phase": frame["phase"],
            "net": [[c * 1000.0 for c in point] for point in frame["vertices"]],
            "trees": [[c * 1000.0 for c in point] for point in frame["columnNodes"]]}
           for frame in document["frames"] if frame["time"] >= RAISE_FROM]
    if not out:
        raise FormworkError("The formwork document has no frame from machine time {:g} on, "
                            "where the raise begins.".format(RAISE_FROM))
    return out


def check_documents(contract, mechanism_document, formwork_document, ea, wires_per_motor=1,
                    pulleys=True):
    """Everything the engine needs from the study's documents, read and checked
    before the cut: a study that cannot run is told now, not after it."""

    if mechanism_document is None:
        raise FormworkError("the formwork engine needs this study's mechanism document, and it "
                            "carries none")
    if formwork_document is None:
        raise FormworkError("the formwork engine needs this study's formwork document: the "
                            "raise follows its trees, and the study carries none")
    try:
        document = frames.validate_frames_document(formwork_document)
        unread = frames.pairing_error(document, contract)
    except ValueError as error:
        unread = str(error)
    if unread is not None:
        raise FormworkError("the formwork document was not read: {}".format(unread))
    vertices = geometry.mesh_arrays(contract)["vertices"]
    design_mm = [[c * 1000.0 for c in point] for point in vertices]
    rim = rim_wires(mechanism_document, design_mm, geometry.support_ids(contract), ea, pulleys)
    heads, members, feet = tree_inputs(document)
    machines = machines_of(mechanism_document, rim)
    if int(wires_per_motor) > 1 and not machines:
        raise FormworkError(
            "This mechanism names no machine instances, so its spools cannot share motors; "
            "run it at one wire a motor.")
    assumptions = []
    unnamed = sum(1 for wire in rim if not wire["reeve_given"])
    if unnamed:
        assumptions.append("{} of {} wires name no reeve factor, so each is taken as a single "
                           "line (MA 1)".format(unnamed, len(rim)))
    return Inputs(rim, machines, heads, members, feet, frames_from(document), assumptions)


def rows_from(arrays, binding, plan, thickness, density):
    """The skin a row at a time (spec section 4.2). A row is a stage of the plan;
    its new pieces are split into four runs in the order the animation drops
    them, and each quarter carries every piece placed by its end, the rows
    before included, as vertical loads, a quarter's nodes and their newtons. A
    row with no new piece gives no steps, and nor does a run that adds no
    face."""

    vertices, faces = arrays["vertices"], arrays["faces"]
    pair_of = {key: tuple(pair) for key, pair in zip(binding["keys"], binding["order"])}
    faces_of = {}
    for face, pair in enumerate(binding["assignment"]):
        if pair is not None:
            faces_of.setdefault(tuple(pair), []).append(face)
    rows, placed, before = [], [], 0
    for entry in plan:
        new = entry["segments"][before:]
        before = len(entry["segments"])
        cells = [faces_of.get(pair_of[key], []) for key in new]
        quarters = []
        for q in range(QUARTERS):
            run = cells[len(cells) * q // QUARTERS:len(cells) * (q + 1) // QUARTERS]
            added = [face for cell in run for face in cell]
            if not added:
                continue
            placed = placed + added
            loads = cablenet.stage_node_loads(vertices, faces, [{"faces": placed}],
                                              thickness, density)[0]
            nodes = [i for i, load in enumerate(loads) if load[2] != 0.0]
            # the faces it placed, for the Formwork tab's skin (spec 2026-10-10)
            quarters.append({"nodes": nodes, "z": [loads[i][2] for i in nodes],
                             "faces": added})
        if quarters:
            rows.append({"name": "S{}".format(entry["stage"]), "quarters": quarters})
    return rows


def request_from(inputs, arrays, binding, plan, thickness, density, ea, mass_per_metre,
                 prestress, wires_per_motor, wall, study=None, options=None, note=None):
    """The engine's request, every length in millimetres and every force in
    newtons."""

    vertices = arrays["vertices"]
    edges = [[int(u), int(v)] for u, v in arrays["edges"]]
    return {
        "study": None if study is None else str(study),
        "units": "mm, N",
        "design": [[c * 1000.0 for c in point] for point in vertices],
        "edges": edges,
        # the cut mesh's faces, which the skin goes on (spec 2026-10-10)
        "faces": [[int(i) for i in face] for face in arrays["faces"]],
        "ea": float(ea), "prestress": float(prestress),
        "weight": cablenet.net_weight_loads(vertices, edges, mass_per_metre),
        "rim": inputs.rim, "machines": inputs.machines, "wires_per_motor": int(wires_per_motor),
        "heads": inputs.heads, "tree_members": inputs.tree_members, "tree_feet": inputs.tree_feet,
        "frames": inputs.frames,
        "rows": rows_from(arrays, binding, plan, thickness, density),
        "wall": float(wall),
        "options": options, "note": note, "assumptions": list(inputs.assumptions),
    }


def _subprocess_runner(python_exe: Path) -> Callable:
    def run(request, progress=None):
        with tempfile.TemporaryDirectory(prefix="ananke_formwork_") as tmp:
            request_path = Path(tmp) / "request.json"
            out_path = Path(tmp) / "out.json"
            errors_path = Path(tmp) / "errors.txt"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            # stderr to a file, not a pipe: read line by line, stdout cannot
            # stall behind a full stderr pipe
            with open(errors_path, "w", encoding="utf-8") as errors:
                process = subprocess.Popen(
                    [str(python_exe), str(SOLVE_FORMWORK), str(request_path), str(out_path)],
                    stdout=subprocess.PIPE, stderr=errors, text=True)
                for line in process.stdout:
                    parts = line.split(None, 3)
                    if progress is not None and len(parts) >= 3 and parts[0] == "progress":
                        progress(int(parts[1]), int(parts[2]),
                                 parts[3].strip() if len(parts) > 3 else "")
                code = process.wait()
            if code != 0 or not out_path.is_file():
                raise FormworkError("solve_formwork exited {}: {}".format(
                    code, errors_path.read_text(encoding="utf-8").strip()[-2000:]))
            return json.loads(out_path.read_text(encoding="utf-8"))

    return run


def sides_of(faces, edges, rim_nodes, node_count):
    """Each node's side (spec 2026-10-11 one Cable net tab, section 6): the
    rim's wire nodes chained along the net's boundary (its edges on one face)
    split into runs, a side each, numbered in the rim's own order; every node
    belongs to the side it is fewest net steps from, ties to the lower side.
    None for a net with no faces to find its boundary by."""

    if not faces:
        return None
    key = lambda a, b: (a, b) if a < b else (b, a)
    on_faces = {}
    for face in faces:
        for i in range(len(face)):
            edge = key(int(face[i]), int(face[(i + 1) % len(face)]))
            on_faces[edge] = on_faces.get(edge, 0) + 1
    rim = [int(node) for node in rim_nodes]
    joined = {node: [] for node in rim}
    for (a, b), count in on_faces.items():
        if count == 1 and a in joined and b in joined:
            joined[a].append(b)
            joined[b].append(a)
    side_of = {}
    for start in rim:
        if start in side_of:
            continue
        side = len(set(side_of.values()))
        side_of[start] = side
        stack = [start]
        while stack:
            for other in joined[stack.pop()]:
                if other not in side_of:
                    side_of[other] = side
                    stack.append(other)
    neighbours = [[] for _ in range(int(node_count))]
    for u, v in edges:
        neighbours[int(u)].append(int(v))
        neighbours[int(v)].append(int(u))
    sides = [None] * int(node_count)
    for node, side in side_of.items():
        sides[node] = side
    frontier = sorted(side_of)
    while frontier:
        reached = {}
        for node in frontier:
            for other in neighbours[node]:
                if sides[other] is None and (other not in reached
                                             or sides[node] < reached[other]):
                    reached[other] = sides[node]
        for node, side in reached.items():
            sides[node] = side
        frontier = sorted(reached)
    return sides


NO_TENDONS = "No tendons"


def across_lines(faces, heads, sides=None):
    """The across lines (spec 2026-10-11 across tendons, section 2): the quads
    sorted into two families from the principal lines out (an edge joining two
    head nodes runs along; across a quad the opposite edge keeps its family and
    a side edge takes the other), and from each head node each across edge
    followed outward, a step further from the principal line each time, to its
    end. heads: the column heads' net nodes in the run's order; sides: each
    node's side, or None. Returns (families, lines, reason): {(a, b) ascending:
    "along" | "across"}, [{"head": index in heads, "side": the last node's side,
    "path": [nodes]}], and None; or (None, [], NO_TENDONS) for a net that does
    not sort."""

    if not faces or any(len(face) != 4 for face in faces):
        return None, [], NO_TENDONS
    head_nodes = [int(node) for node in heads]
    heads_set = set(head_nodes)
    key = lambda a, b: (a, b) if a < b else (b, a)
    face_edges = [[key(int(f[i]), int(f[(i + 1) % 4])) for i in range(4)] for f in faces]
    edge_faces = {}
    for index, edges in enumerate(face_edges):
        for k, edge in enumerate(edges):
            edge_faces.setdefault(edge, []).append((index, k))
    along = [edge for edge in edge_faces if edge[0] in heads_set and edge[1] in heads_set]
    if not along:
        return None, [], NO_TENDONS
    families = {edge: "along" for edge in along}
    queue = list(along)
    while queue:
        edge = queue.pop()
        for index, k in edge_faces[edge]:
            edges = face_edges[index]
            other = "across" if families[edge] == "along" else "along"
            for neighbour, wanted in ((edges[(k + 2) % 4], families[edge]),
                                      (edges[(k + 1) % 4], other), (edges[(k + 3) % 4], other)):
                if neighbour not in families:
                    families[neighbour] = wanted
                    queue.append(neighbour)
                elif families[neighbour] != wanted:
                    return None, [], NO_TENDONS
    if len(families) != len(edge_faces):
        return None, [], NO_TENDONS
    across = {}
    for (a, b), kind in families.items():
        if kind == "across":
            across.setdefault(a, []).append(b)
            across.setdefault(b, []).append(a)
    band = {node: 0 for node in heads_set}
    frontier = sorted(heads_set)
    while frontier:
        reached = []
        for a in frontier:
            for b in across.get(a, []):
                if b not in band:
                    band[b] = band[a] + 1
                    reached.append(b)
        frontier = reached
    lines = []
    for index, head in enumerate(head_nodes):
        for first in sorted(b for b in across.get(head, []) if band.get(b) == 1):
            path = [head, first]
            while True:
                onward = [b for b in across.get(path[-1], []) if band.get(b) == band[path[-1]] + 1]
                if len(onward) != 1:
                    break
                path.append(onward[0])
            lines.append({"head": index, "path": path,
                          "side": None if sides is None else sides[path[-1]]})
    return families, lines, None


def _floats(entry):
    """One packed array of a capture document (solve_formwork.pack), read with
    the standard library: the studio's server imports no numpy."""

    import base64
    import struct

    raw = base64.b64decode(entry["f32"])
    return list(struct.unpack("<%df" % (len(raw) // 4), raw))


def travel_checks(parts, configuration, document, reeve_by_node, rim_nodes):
    """The drum and the carriage of the run's mechanism (spec 2026-10-11
    section 8.1), from the run's own take-up at each drum: each capture's reels,
    in the engine's rim order (the rim's nodes ascending), each wire reeved as
    the export draws it. The worst wire of each, its figure, its limit and
    whether it fits; None for a run with no reels."""

    import machine

    order = sorted(int(node) for node in rim_nodes)
    series = [[] for _ in order]
    for capture in document.get("captures") or []:
        if not isinstance(capture.get("reel"), dict):
            continue
        for w, value in enumerate(_floats(capture["reel"])[:len(order)]):
            series[w].append(value)
    if not any(series):
        return None
    reeves = [int(reeve_by_node.get(node, 1)) for node in order]
    travel = machine.travel(parts, configuration, series, reeves)
    drum, carriage = travel["worst_drum"], travel["worst_carriage"]
    return {"drum": {"value_mm": drum["drum_rope_mm"], "limit_mm": drum["drum_capacity_mm"],
                     "fits": drum["drum_fits"], "wire": drum["wire"]},
            "carriage": {"value_mm": carriage["carriage_mm"], "limit_mm": carriage["stroke_mm"],
                         "fits": carriage["rail_fits"], "wire": carriage["wire"]}}


def run_formwork(inputs, arrays, binding, plan, thickness, density, out_path, ea,
                 mass_per_metre, prestress, wires_per_motor, wall, study=None, options=None,
                 note=None, runner=None, python_exe=None, progress=None, holds_per_side=0,
                 state_path=None, resume=False, annotate=None, pull_in=0.0):
    """From a checked study and its cut to a written capture document. runner,
    when given, replaces the subprocess: it takes the request and progress and
    returns the document. progress, when given, is called with (captures done,
    captures in all, what). The engine is told each node's side (sides_of) and
    places holds_per_side rods on each; it keeps its state at the hold at
    state_path, and with resume a state there is where it starts (spec
    2026-10-11 one Cable net tab, sections 6 and 7). With a pull_in, N, the
    engine is handed a tendon along each across line (across_lines) pulled in
    with it (spec 2026-10-11 across tendons). The document gains the sides,
    each edge's family (null for a net that does not sort), the reason a
    pulled run has no tendons, and what annotate, when given, returns from the
    finished document."""

    request = request_from(inputs, arrays, binding, plan, thickness, density, ea,
                           mass_per_metre, prestress, wires_per_motor, wall, study, options, note)
    vertices, edges = arrays.get("vertices"), arrays.get("edges")
    sides = (None if vertices is None or edges is None else
             sides_of(arrays.get("faces"), edges, [wire["node"] for wire in inputs.rim],
                      len(vertices)))
    if holds_per_side and sides is None:
        raise FormworkError("rods a side need the net's sides, and this net's rim does not "
                            "split into wired runs")
    families, lines, reason = across_lines(arrays.get("faces"),
                                           [net for net, _ in inputs.heads], sides)
    pulled = float(pull_in) > 0.0
    request.update(sides=sides, holds_per_side=int(holds_per_side),
                   tendons=lines if pulled else [], tendon_pull=float(pull_in) if pulled else 0.0)
    if state_path is not None:
        request["state_out"] = str(state_path)
        if resume and Path(state_path).is_file():
            request["state_in"] = str(state_path)
    if runner is None:
        runner = _subprocess_runner(python_exe or FORMWORK_PYTHON)
    document = runner(request, progress)
    document.setdefault("net", {})["sides"] = sides
    document["net"]["families"] = None if families is None or edges is None else [
        families.get((min(int(a), int(b)), max(int(a), int(b)))) for a, b in edges]
    document["tendons_reason"] = reason if pulled else None
    if annotate is not None:
        document.update(annotate(document))
    bundle.write_json_atomically(Path(out_path), document)
    return {"path": str(out_path), "captures": len(document.get("captures") or [])}
