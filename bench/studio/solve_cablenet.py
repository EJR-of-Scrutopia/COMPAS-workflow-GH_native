"""The cable net engine, run as its own process.

The document it writes is the hold analysis (hold_analysis): at every computed
instant, the best tension-only state the net can carry with the drum ends and
the column heads held, the force that state leaves unbalanced at each node,
the sag that force causes, and the actuators placed at the heaviest instant.
The forward walk (walk_stages) is optional: it runs only when a request asks
for it, and its document, or its refusal, lands under the document's
"forward" key.

Runs under a solver interpreter (the repo's main .venv, the only one holding
numpy, scipy and compas_fd together). Like solve_stage.py and solve_cra.py, this
file is a deliberate exception to the studio guard: it executes in a solver
environment, never in the server's. cablenet.py invokes it as a subprocess:

    .venv/Scripts/python.exe bench/studio/solve_cablenet.py request.json out.json

Failure discipline: a study the engine refuses is a CableNetError; it is
printed to stderr and the process exits 1, and cablenet.run_cablenet turns that
back into a CableNetError carrying the message. Only the engine lives here;
everything that needs no solver stays in cablenet.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cablenet import CableNetError, Wire  # noqa: E402


class BuiltProblem(NamedTuple):
    """The engine's problem, and everything needed to speak to it in contract ids."""

    problem: object
    node_of: dict                     # contract node id -> problem vertex index
    vertex_of: dict                   # problem vertex index -> contract node id
    net_edge_count: int               # problem edges 0..n-1 are the net's own
    wire_vertices: tuple              # the problem vertex of each wire's frame end
    fixed: tuple                      # the wires' machine ends only, problem indices


def build_problem(vertices_metres, edges, anchors, wires, tolerance=1e-6):
    """The net plus its wires as one registered problem, in millimetres.

    register_fd_network takes LINES and welds coincident endpoints in FIRST
    ENCOUNTER order, so its vertex indices are not the contract's node ids and
    must never be assumed to be. The map is recovered from endpoint_to_vertex,
    which reports the pair of vertices each input line became, and then checked
    both ways: a contract node that lands on two problem vertices, or two
    contract nodes that land on one, is refused. That second case is a silent
    merge of two real nodes, which would solve a vault nobody designed, and it
    is the same failure geometry.check_index_spaces exists to refuse.

    Problem edge k is input line k, so the net's edges keep the contract's own
    order and the wires follow, one per wire, in the order given. Rest lengths
    and reel commands are indexed the same way.

    `anchors` are the form's support nodes. They are NOT fixed. The wires hold
    them: each support is the net end of a wire, the wire's other end is a
    machine point, and `fixed` is those machine points and nothing else. A
    support with no wire would float, so it is refused.
    """

    millimetres = [[float(c) * 1000.0 for c in point] for point in vertices_metres]
    lines = [[millimetres[int(u)], millimetres[int(v)]] for u, v in edges]
    for wire in wires:
        lines.append([list(wire.frame_point), millimetres[wire.net_vertex]])

    from tree_forest_compas.fd import FDInputError, register_fd_network

    for wire in wires:
        node = millimetres[wire.net_vertex]
        if max(abs(a - b) for a, b in zip(wire.frame_point, node)) <= tolerance:
            raise CableNetError(
                "Wire {!r} has its frame point on top of net node {}. A wire "
                "needs somewhere to pull FROM.".format(wire.name, wire.net_vertex)
            )

    try:
        problem = register_fd_network(lines, tolerance=tolerance)
    except FDInputError as error:
        raise CableNetError(
            "The solver refused the net: {}".format(error)
        ) from error
    node_of: Dict[int, int] = {}

    def bind(node, vertex):
        seen = node_of.get(node)
        if seen is not None and seen != vertex:
            raise CableNetError(
                "Contract node {} welded to two different vertices ({} and {}); "
                "the net cannot be read.".format(node, seen, vertex)
            )
        node_of[node] = vertex

    for index, (u, v) in enumerate(edges):
        pu, pv = problem.endpoint_to_vertex[index]
        bind(int(u), int(pu))
        bind(int(v), int(pv))

    if len(set(node_of.values())) != len(node_of):
        merged = {}
        for node, vertex in node_of.items():
            merged.setdefault(vertex, []).append(node)
        clash = sorted(nodes for nodes in merged.values() if len(nodes) > 1)[0]
        raise CableNetError(
            "Contract nodes {} are closer together than the weld tolerance of "
            "{:g} mm and became one vertex. Two real nodes merged into one "
            "would solve a vault nobody designed.".format(clash, tolerance)
        )

    for wire in wires:
        if wire.net_vertex not in node_of:
            raise CableNetError(
                "Wire {!r} pulls node {}, which no edge touches.".format(
                    wire.name, wire.net_vertex
                )
            )
    for anchor in anchors:
        if int(anchor) not in node_of:
            raise CableNetError(
                "Contract anchor {} is not touched by any edge, so it is fixed "
                "to nothing. That is a defect in the export; it is not skipped "
                "silently.".format(int(anchor))
            )

    wire_vertices = []
    for position, wire in enumerate(wires):
        frame_vertex, net_vertex = problem.endpoint_to_vertex[len(edges) + position]
        if int(net_vertex) != node_of[wire.net_vertex]:
            raise CableNetError(
                "Wire {!r} did not attach to node {} as asked.".format(
                    wire.name, wire.net_vertex
                )
            )
        if int(frame_vertex) in set(node_of.values()):
            raise CableNetError(
                "Wire {!r} has its frame point on top of a net node. A wire "
                "needs somewhere to pull FROM.".format(wire.name)
            )
        wire_vertices.append(int(frame_vertex))

    wired = set(wire.net_vertex for wire in wires)
    for anchor in anchors:
        if int(anchor) not in wired:
            raise CableNetError(
                "Support node {} has no wire. The wires are the supports on "
                "this machine, so a support nothing holds would float free "
                "rather than stand on the ground.".format(int(anchor))
            )
    # Only the machine ends are fixed. The net nodes the wires hold are free.
    fixed = tuple(sorted(set(wire_vertices)))
    return BuiltProblem(
        problem=problem,
        node_of=node_of,
        vertex_of={v: k for k, v in node_of.items()},
        net_edge_count=len(edges),
        wire_vertices=tuple(wire_vertices),
        fixed=fixed,
    )


def to_engine(loads_by_node, node_of, vertex_count):
    """Per-contract-node loads reordered into the problem's own vertex order.

    A node that carries load and maps to no problem vertex is refused, never
    skipped: faces come from formGraph.faces and edges from equilibrium.edges,
    so a face corner no edge touches would otherwise lose its weight silently.
    A node with exactly zero load may be skipped, since nothing is lost.
    """

    out = [[0.0, 0.0, 0.0] for _ in range(vertex_count)]
    for node, vector in enumerate(loads_by_node):
        vertex = node_of.get(node)
        if vertex is None:
            if any(float(value) != 0.0 for value in vector):
                raise CableNetError(
                    "Contract node {} carries a load of {} N (x, y, z) but no "
                    "edge touches it, so the net has nothing to hang that "
                    "weight from. Dropping it would understate the demand; "
                    "the faces and the edges of this study disagree about "
                    "which nodes exist.".format(
                        node, [float(value) for value in vector])
                )
            continue
        out[vertex] = [float(value) for value in vector]
    return out


def cut_rest_lengths(problem, net_edge_count, ea, prestress):
    """The lengths the net's own members are MADE to.

    Every member carries the same prestress when stretched to its length at the
    target geometry:

        rest = length(target) / (1 + prestress / EA)

    There is no solve here and there deliberately is not one. The vault's
    geometry is a rising compression shell, and a tension-only net at a rising
    geometry under downward load cannot be held at all at its highest nodes: on
    the real export two free nodes at the crown have every neighbour at or below
    them, so no cable can hold them and only a wire can. A hold solve at the
    target is therefore infeasible rather than approximate, and a non-negative
    least squares over 2253 members would in any case not finish in minutes.

    So prestress is an INPUT, which is what it always was physically, and where
    the net then sits is the forward solve's answer.
    """

    import numpy as np

    if not float(ea) > 0.0:
        raise CableNetError("EA must be greater than zero.")
    if not float(prestress) > 0.0:
        raise CableNetError(
            "The prestress must be greater than zero: a net cut to its own "
            "target lengths carries nothing and goes slack."
        )
    xyz = np.asarray(problem.source_vertices, dtype=float)
    rest = []
    for u, v in problem.source_edges[:int(net_edge_count)]:
        length = float(np.linalg.norm(xyz[int(v)] - xyz[int(u)]))
        rest.append(length / (1.0 + float(prestress) / float(ea)))
    return rest


def walk_stages(built, loads_by_stage, net_weight, ea, prestress, acceptance,
                acceptance_source, target=None, stage_names=None, stage_kinds=None,
                placed_weights=None):
    """Solve every stage in order and return the demand document.

    The net's own rest lengths never change: they are manufactured. Only the
    wires are commanded, and only the wires are perturbed when the correction is
    linearised, which is the difference between one solve per member and one per
    wire.
    """

    import numpy as np

    from tree_forest_compas.hold import correction_for
    from tree_forest_compas.hold import nodes_needing_support
    from tree_forest_compas.prescribed import PrescribedError
    from tree_forest_compas.prescribed import solve_prescribed_lengths

    if acceptance is None:
        raise CableNetError("the forward walk needs an acceptance line")
    problem = built.problem
    vertex_count = len(problem.source_vertices)
    edge_count = len(problem.source_edges)
    wire_indices = list(range(built.net_edge_count, edge_count))
    if not wire_indices:
        raise CableNetError("A cable net with no wires cannot be commanded.")

    net_rest = cut_rest_lengths(problem, built.net_edge_count, ea, prestress)
    xyz = np.asarray(problem.source_vertices, dtype=float)
    wire_rest = [
        float(np.linalg.norm(xyz[int(v)] - xyz[int(u)])) / (1.0 + prestress / ea)
        for u, v in problem.source_edges[built.net_edge_count:]
    ]
    reference = xyz if target is None else np.asarray(target, dtype=float)

    # the diagnostic first, so an unholdable node is a node number and not a
    # least squares message
    heaviest = max(
        range(len(loads_by_stage)),
        key=lambda k: sum(-row[2] for row in loads_by_stage[k]),
    )
    combined = [
        [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
        for a, b in zip(loads_by_stage[heaviest], net_weight)
    ]
    engine_loads = to_engine(combined, built.node_of, vertex_count)
    stranded = nodes_needing_support(
        problem.source_vertices, problem.source_edges, built.fixed, engine_loads
    )
    if stranded:
        named = [built.vertex_of.get(v, v) for v in stranded]
        raise CableNetError(
            "These nodes need a wire and have none: {}. Every cable at such a "
            "node runs downward, so no tension can hold it and the load has "
            "nowhere to go. Add a wire to each in the mechanism document."
            .format(", ".join(str(n) for n in named[:20]))
        )

    stages = []
    previous = list(wire_rest)
    for index, skin in enumerate(loads_by_stage):
        combined = [
            [a[0] + b[0], a[1] + b[1], a[2] + b[2]] for a, b in zip(skin, net_weight)
        ]
        loads = np.asarray(
            to_engine(combined, built.node_of, vertex_count), dtype=float
        )
        rest = np.asarray(list(net_rest) + list(previous), dtype=float)
        try:
            state = solve_prescribed_lengths(
                problem, fixed=built.fixed, rest_lengths=rest, ea=ea, loads=loads
            )
        except PrescribedError as error:
            raise CableNetError(
                "Stage {} did not solve: {}".format(index + 1, error)
            ) from error
        measured = np.asarray(state.session.equilibrium_vertices, dtype=float)

        correction = correction_for(
            problem, fixed=built.fixed, rest_lengths=rest, ea=ea, loads=loads,
            measured=measured, target=reference, actuated=wire_indices,
            tolerance=float(acceptance),
        )
        commanded = [
            previous[position] + correction.reel_commands[edge]
            for position, edge in enumerate(wire_indices)
        ]
        tensions = np.asarray(state.tensions, dtype=float)
        skin_sum = float(sum(-row[2] for row in skin))
        net_sum = float(sum(-row[2] for row in net_weight))
        stages.append({
            "stage": index + 1,
            "name": (stage_names or {}).get(index, "S{}".format(index + 1)),
            "kind": (stage_kinds or {}).get(index, "raise" if index == 0 else "tile"),
            "placed_weight_newtons": (
                None if placed_weights is None else float(placed_weights[index])
            ),
            "skin_load_sum_newtons": skin_sum,
            "net_weight_newtons": net_sum,
            "node_load_sum_newtons": skin_sum + net_sum,
            "wire_rest_lengths": [float(v) for v in commanded],
            "wire_reel_commands": [
                float(commanded[p] - previous[p]) for p in range(len(commanded))
            ],
            "wire_tensions": [float(tensions[edge]) for edge in wire_indices],
            "worst_net_tension": float(np.max(tensions[: built.net_edge_count])),
            "deviation": float(correction.residual_before),
            "reachable": bool(correction.reachable),
            "residual_after": float(correction.residual_after),
        })
        previous = commanded

    worst = max(stages, key=lambda row: max(row["wire_tensions"]))
    return {
        "schema": "bench.cablenet/1",
        "units": "N, mm",
        "geometry_scale_applied": 1000.0,
        "prestress": float(prestress),
        "ea_newtons": float(ea),
        "net": {
            "vertices": [[float(c) for c in p] for p in problem.source_vertices],
            "edges": [[int(u), int(v)] for u, v in problem.source_edges],
            "fixed": [int(v) for v in built.fixed],
            "net_edge_count": int(built.net_edge_count),
            "manufactured_rest_lengths": [float(v) for v in net_rest],
            "node_of": {str(k): int(v) for k, v in built.node_of.items()},
        },
        "stages": stages,
        "sizing_stage": worst["name"],
        "acceptance": float(acceptance),
        "acceptance_source": str(acceptance_source),
    }


def instants_of(request):
    """The computed instants, in order: the sampled frames under the net's own
    weight, then every course of the skin at the finished shape."""

    net_weight = request["net_weight"]
    names = {int(k): v for k, v in (request.get("stage_names") or {}).items()}
    placed = request.get("placed_weights")
    out = []
    for frame in request.get("frames") or []:
        time = float(frame["time"])
        out.append({
            "name": "F{:g}".format(time), "kind": str(frame.get("phase") or "frame"),
            "time": time, "course": None, "vertices": frame["vertices"],
            "loads": [[float(c) for c in row] for row in net_weight],
            "placed_weight": None, "skin_sum": 0.0,
        })
    for index, skin in enumerate(request["loads_by_stage"]):
        combined = [[a[0] + b[0], a[1] + b[1], a[2] + b[2]]
                    for a, b in zip(skin, net_weight)]
        out.append({
            "name": names.get(index, "S{}".format(index + 1)), "kind": "tile",
            "time": None, "course": index, "vertices": request["vertices"],
            "loads": combined,
            "placed_weight": None if placed is None else float(placed[index]),
            "skin_sum": float(sum(-row[2] for row in skin)),
        })
    if not out:
        raise CableNetError("There is no instant to analyse: no frames and no courses.")
    return out


def hold_analysis(built, heads, instants, vertex_count, ea, prestress, acceptance,
                  acceptance_source, wire_nodes=(), batch=20, steps=40):
    """Fit the net at every instant, place the actuators at the heaviest, and
    return the bench.cablenet/2 demand document (study and wires added by solve).

    A HoldError or a StiffnessError from the fit, the sag or the walk is
    refused as a CableNetError carrying its message and naming the instant,
    so a mechanism in the net is a refusal that says so, not a traceback.

    The sizing block's worst_wire_tension_newtons is the figure every wire is
    judged at: the larger of the entered prestress and the greatest tension
    the fit found in any wire at any instant, with the two kept beside it as
    prestress_newtons and fitted_wire_tension_newtons. The shape half gives
    every member the prestress as a floor on its stiffness, and the sag is
    judged at that floor, so the tension half judges no wire at less: the
    fit's own wire tensions can be far below it (14.6 N on the real study at
    300 N), and a rig judged at those would be said to hold a net the analysis
    held at the prestress. It is worked out here and the readers read it
    (catalogue.wire_floor, and cablenet_model.prestressFloor on the panel);
    only a document written before the block carried the two figures has its
    floor taken by the same rule from what it does carry. The stages keep the
    fit's own wire tensions, which the lenses draw.
    """

    import numpy as np

    from tree_forest_compas.hold import HoldError
    from tree_forest_compas.hold import fit_tension_state
    from tree_forest_compas.hold import nodes_needing_support
    from tree_forest_compas.placement import greedy_actuators
    from tree_forest_compas.stiffness import StiffnessError
    from tree_forest_compas.stiffness import first_order_sag

    if not float(ea) > 0.0:
        raise CableNetError("EA must be greater than zero.")
    if not float(prestress) > 0.0:
        raise CableNetError(
            "The prestress must be greater than zero: it is the floor every "
            "member's stiffness is judged at, and a slack flat net is a mechanism.")
    problem = built.problem
    base = np.asarray(problem.source_vertices, dtype=float)
    count = len(base)
    edges = [(int(u), int(v)) for u, v in problem.source_edges]
    net_edges = int(built.net_edge_count)
    node_of, vertex_of = built.node_of, built.vertex_of
    heads = [int(h) for h in heads]
    for head in heads:
        if head not in node_of:
            raise CableNetError(
                "Column head {} is a node no edge touches, so no column can "
                "prop it.".format(head))
    heads_p = sorted(set(node_of[h] for h in heads))
    held_base = sorted(set(int(v) for v in built.fixed) | set(heads_p))
    wire_count = len(edges) - net_edges

    def positions(instant):
        here = base.copy()
        for node, vertex in node_of.items():
            x, y, z = instant["vertices"][node]
            here[vertex] = (float(x) * 1000.0, float(y) * 1000.0, float(z) * 1000.0)
        return here

    def lengths(here):
        return np.linalg.norm(here[[v for _, v in edges]] - here[[u for u, _ in edges]], axis=1)

    def engine_loads(instant):
        return np.asarray(to_engine(instant["loads"], node_of, count), dtype=float)

    # the floor every member is given, as a force density at the finished shape
    floor = float(prestress) / lengths(base)

    heaviest = max(range(len(instants)),
                   key=lambda k: sum(-row[2] for row in instants[k]["loads"]))
    here = positions(instants[heaviest])
    loads = engine_loads(instants[heaviest])
    stranded = nodes_needing_support(here, edges, held_base, loads)
    try:
        placement = greedy_actuators(here, edges, held_base, loads, float(ea), floor,
                                     acceptance, batch=batch, steps=steps)
    except (HoldError, StiffnessError) as error:
        raise CableNetError(
            "The actuators cannot be placed at {}: {}".format(
                instants[heaviest]["name"], error)) from error
    actuators_p = [int(v) for v in placement.actuators]
    held = sorted(set(held_base) | set(actuators_p))

    def contract_rows(vector_rows, free_only):
        out = [None] * int(vertex_count)
        for node, vertex in node_of.items():
            if vertex in free_only:
                continue
            out[node] = [float(c) for c in vector_rows[vertex]]
        return out

    held_set = set(held)
    stages = []
    previous = None
    for index, instant in enumerate(instants):
        here = positions(instant)
        loads = engine_loads(instant)
        length = lengths(here)
        try:
            bare = fit_tension_state(here, edges, held_base, loads)
            bare_sag = first_order_sag(here, edges, held_base, bare.force_densities,
                                       float(ea), bare.residual, floor)
            fit = fit_tension_state(here, edges, held, loads)
            sag = np.asarray(first_order_sag(here, edges, held, fit.force_densities,
                                             float(ea), fit.residual, floor), dtype=float)
        except (HoldError, StiffnessError) as error:
            raise CableNetError(
                "The net cannot be analysed at {}: {}".format(
                    instant["name"], error)) from error
        tensions = np.asarray(fit.tensions, dtype=float)
        residual = np.asarray(fit.residual, dtype=float)
        reactions = np.asarray(fit.reactions, dtype=float)
        sag_mm = np.linalg.norm(sag, axis=1)
        bare_mm = np.linalg.norm(np.asarray(bare_sag, dtype=float), axis=1)
        wire_t = [float(tensions[e]) for e in range(net_edges, len(edges))]
        wire_l = [float(length[e]) for e in range(net_edges, len(edges))]
        if previous is None:
            reel = [0.0] * wire_count
        else:
            reel = [
                (wire_l[i] - previous["l"][i])
                - (wire_t[i] - previous["t"][i]) * wire_l[i] / float(ea)
                for i in range(wire_count)
            ]
        travel = [[0.0, 0.0, 0.0] for _ in actuators_p] if previous is None else [
            [float(c) for c in (here[v] - previous["xyz"][v])] for v in actuators_p]
        worst_sag = float(sag_mm.max()) if sag_mm.size else 0.0
        free_mask = [v for v in range(count) if v not in held_set]
        worst_residual = float(np.linalg.norm(residual[free_mask], axis=1).max()) if free_mask else 0.0
        skin_sum = float(instant["skin_sum"])
        net_sum = float(sum(-row[2] for row in instant["loads"])) - skin_sum
        node_sag_mm = [None] * int(vertex_count)
        for node, vertex in node_of.items():
            if vertex not in held_set:
                node_sag_mm[node] = float(sag_mm[vertex])
        stages.append({
            "stage": index + 1,
            "name": instant["name"],
            "kind": instant["kind"],
            "time": instant["time"],
            "course": instant["course"],
            "placed_weight_newtons": instant["placed_weight"],
            "skin_load_sum_newtons": skin_sum,
            "net_weight_newtons": net_sum,
            "node_load_sum_newtons": skin_sum + net_sum,
            "member_tensions": [float(tensions[e]) for e in range(net_edges)],
            "wire_tensions": wire_t,
            "wire_lengths": wire_l,
            "wire_rest_lengths": [wire_l[i] * (1.0 - wire_t[i] / float(ea))
                                  for i in range(wire_count)],
            "wire_reel_commands": [float(r) for r in reel],
            "actuator_forces": [[float(c) for c in reactions[v]] for v in actuators_p],
            "actuator_travel": travel,
            "node_residual": contract_rows(residual, held_set),
            "node_sag": contract_rows(sag, held_set),
            "node_sag_mm": node_sag_mm,
            "column_forces": [
                {"node": int(vertex_of[v]),
                 "force": [float(c) for c in reactions[v]],
                 "newtons": float(np.linalg.norm(reactions[v])),
                 "vertical": float(reactions[v][2])}
                for v in heads_p
            ],
            "worst_net_tension": float(tensions[:net_edges].max()) if net_edges else 0.0,
            "worst_residual_newtons": worst_residual,
            "deviation": float(bare_mm.max()) if bare_mm.size else 0.0,
            "residual_after": worst_sag,
            "reachable": None if acceptance is None else bool(worst_sag <= float(acceptance)),
        })
        previous = {"l": wire_l, "t": wire_t, "xyz": here}

    def worst_force(stage):
        forces = [abs(t) for t in stage["wire_tensions"]]
        forces += [sum(c * c for c in f) ** 0.5 for f in stage["actuator_forces"]]
        return max(forces) if forces else 0.0

    # The raise is shown, not judged: the shape verdict reads the courses, so
    # the stage that sizes the system and the sag it is judged by come from
    # the courses, and from every instant only when there are none. The rope
    # and the drum see the raise too, so their worst forces are over every
    # instant.
    judged = [s for s in stages if s["course"] is not None] or stages
    sizing_stage = max(judged, key=worst_force)
    fitted_wire = max(
        max(abs(t) for t in s["wire_tensions"]) if s["wire_tensions"] else 0.0
        for s in stages)
    sizing = {
        "stage": sizing_stage["name"],
        # the figure the wires are judged at, the larger of the two beside it
        # (see the docstring): worked out once, here, and read everywhere
        "worst_wire_tension_newtons": max(float(prestress), fitted_wire),
        "fitted_wire_tension_newtons": fitted_wire,
        "prestress_newtons": float(prestress),
        "worst_actuator_newtons": max(
            max([sum(c * c for c in f) ** 0.5 for f in s["actuator_forces"]] or [0.0])
            for s in stages),
        "worst_sag_mm": max(s["residual_after"] for s in judged),
        "load_newtons": sizing_stage["node_load_sum_newtons"],
    }
    placement_block = {
        "stage": instants[heaviest]["name"],
        "batch": int(batch), "steps": int(steps),
        "reached": bool(placement.reached),
        "method": "greedy by unbalanced force, in batches: a heuristic, not an optimum",
        "stranded": [int(vertex_of[v]) for v in stranded],
        "curve": [
            {"count": int(p.count), "worst_residual_newtons": float(p.worst_residual),
             "worst_sag_mm": float(p.worst_sag),
             "residual_norm_newtons": float(p.residual_norm),
             "added": [int(vertex_of[v]) for v in p.added]}
            for p in placement.points
        ],
    }
    if not heads:
        # frames come only from a formwork document, so frames with no heads
        # are a document that names none (an older frames document carries no
        # columns block), not a missing document
        if any(instant["time"] is not None for instant in instants):
            placement_block["note"] = (
                "the formwork document names no column heads, so none were "
                "held: the net is held by its drum ends alone and every column "
                "is unknown")
        else:
            placement_block["note"] = (
                "no formwork document, so no column heads were held: the net is "
                "held by its drum ends alone and every column is unknown")
    return {
        "schema": "bench.cablenet/2",
        "units": "N, mm",
        "geometry_scale_applied": 1000.0,
        "prestress": float(prestress),
        "ea_newtons": float(ea),
        "net": {
            "vertices": [[float(c) for c in p] for p in problem.source_vertices],
            "edges": [[int(u), int(v)] for u, v in edges],
            "fixed": [int(v) for v in built.fixed],
            "net_edge_count": net_edges,
            "node_of": {str(k): int(v) for k, v in node_of.items()},
            "column_heads": heads,
        },
        "held": {
            "wire_nodes": [int(node) for node in wire_nodes],
            "column_heads": heads,
            "actuators": [int(vertex_of[v]) for v in actuators_p],
        },
        "placement": placement_block,
        "sizing": sizing,
        "sizing_stage": sizing["stage"],
        "stages": stages,
        "acceptance": None if acceptance is None else float(acceptance),
        "acceptance_source": None if acceptance_source is None else str(acceptance_source),
    }


def resolve_acceptance(request: dict, vertices_metres, anchors):
    """The acceptance line and its source, from a named falsework entry.

    The line is the deflection of the timber rib this machine replaces under
    the same skin. Units: millimetres and newtons; the skin's areal load is
    thickness (m) * density (kg/m3) * g (m/s2) = N/m2, divided by 1e6 for N/mm2.
    A rib shorter than half the greatest anchor-to-anchor distance describes a
    different building, and is refused.
    """

    import json as _json
    import math

    import staging
    from tree_forest_compas import falsework

    key = request["falsework"]
    parts = _json.loads(
        (Path(__file__).resolve().parent / "parts.json").read_text(encoding="utf-8"))
    entry = (parts.get("falsework") or {}).get(key)
    if entry is None:
        raise CableNetError("No falsework entry named {!r} in parts.json.".format(key))
    rib = falsework.Rib(
        span=float(entry["span"]), spacing=float(entry["spacing"]),
        depth=float(entry["depth"]), width=float(entry["width"]),
        e_modulus=float(entry["e_modulus"]))
    points = [[float(c) * 1000.0 for c in vertices_metres[int(a)]] for a in anchors]
    reach = max(
        (math.dist(p, q) for i, p in enumerate(points) for q in points[i + 1:]),
        default=0.0)
    if rib.span < reach / 2.0:
        raise CableNetError(
            "Falsework {!r} spans {:g} mm, less than half the study's greatest "
            "anchor-to-anchor distance of {:g} mm (half is {:g} mm). It describes "
            "a different building, so its deflection is not an acceptance line "
            "for this one.".format(key, rib.span, reach, reach / 2.0))
    areal = float(request["thickness"]) * float(request["density"]) * staging.GRAVITY / 1e6
    try:
        line = falsework.acceptance_line(rib, areal)
    except falsework.FalseworkError as error:
        raise CableNetError("Falsework {!r}: {}".format(key, error)) from error
    source = "falsework {}: {}".format(key, _json.dumps(entry, sort_keys=True))
    return line, source


def solve(request: dict) -> dict:
    """The demand document for one request, wires echoed back as given."""

    wires = [
        Wire(name=w["name"], net_vertex=int(w["net_vertex"]),
             frame_point=list(w["frame_point"]),
             machine_wire=w.get("machine_wire"),
             reeve_factor=w.get("reeve_factor"),
             permanence=w.get("permanence"))
        for w in request["wires"]
    ]
    vertices = request["vertices"]
    edges = [tuple(edge) for edge in request["edges"]]
    built = build_problem(vertices, edges, request["anchors"], wires)
    acceptance = request.get("acceptance")
    acceptance_source = request.get("acceptance_source")
    if request.get("falsework"):
        acceptance, acceptance_source = resolve_acceptance(
            request, vertices, request["anchors"])
    document = hold_analysis(
        built, request.get("column_heads") or [], instants_of(request),
        len(vertices), request["ea"], request["prestress"], acceptance,
        acceptance_source, wire_nodes=[w.net_vertex for w in wires],
        batch=int(request.get("batch", 20)), steps=int(request.get("steps", 40)),
    )
    if request.get("forward"):
        names = {int(k): v for k, v in request["stage_names"].items()}
        try:
            document["forward"] = walk_stages(
                built, request["loads_by_stage"], request["net_weight"],
                request["ea"], request["prestress"], acceptance,
                acceptance_source, target=None, stage_names=names,
                placed_weights=request.get("placed_weights"))
        except CableNetError as error:
            document["forward"] = {"refused": str(error)}
    document["study"] = request.get("study")
    document["note"] = request.get("note")
    document["density"] = request.get("density")
    document["thickness"] = request.get("thickness")
    document["net"]["ea_provenance"] = request.get("ea_provenance")
    document["wires"] = [
        {"name": w.name, "net_vertex": w.net_vertex, "frame_point": w.frame_point,
         "machine_wire": w.machine_wire, "reeve_factor": w.reeve_factor,
         "permanence": w.permanence}
        for w in wires
    ]
    return document


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: solve_cablenet.py <request.json> <out.json>", file=sys.stderr)
        return 2
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        document = solve(request)
    except CableNetError as error:
        print(str(error), file=sys.stderr)
        return 1
    Path(sys.argv[2]).write_text(
        json.dumps(document, allow_nan=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
