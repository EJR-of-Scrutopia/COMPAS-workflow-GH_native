"""The cable net engine, run as its own process.

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
    fixed: tuple                      # anchors plus frame points, problem indices


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

    fixed = tuple(sorted(
        set(node_of[int(a)] for a in anchors) | set(wire_vertices)
    ))
    return BuiltProblem(
        problem=problem,
        node_of=node_of,
        vertex_of={v: k for k, v in node_of.items()},
        net_edge_count=len(edges),
        wire_vertices=tuple(wire_vertices),
        fixed=fixed,
    )


def to_engine(loads_by_node, node_of, vertex_count):
    """Per-contract-node loads reordered into the problem's own vertex order."""

    out = [[0.0, 0.0, 0.0] for _ in range(vertex_count)]
    for node, vector in enumerate(loads_by_node):
        vertex = node_of.get(node)
        if vertex is None:
            continue                  # a node no edge touched carries nothing
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
                acceptance_source, target=None, stage_names=None, stage_kinds=None):
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



def solve(request: dict) -> dict:
    """The demand document for one request, wires echoed back as given."""

    wires = [
        Wire(name=w["name"], net_vertex=int(w["net_vertex"]),
             frame_point=list(w["frame_point"]))
        for w in request["wires"]
    ]
    vertices = request["vertices"]
    edges = [tuple(edge) for edge in request["edges"]]
    built = build_problem(vertices, edges, request["anchors"], wires)
    names = {int(k): v for k, v in request["stage_names"].items()}
    document = walk_stages(
        built, request["loads_by_stage"], request["net_weight"],
        request["ea"], request["prestress"], request["acceptance"],
        request["acceptance_source"], target=None, stage_names=names,
    )
    document["wires"] = [
        {"name": w.name, "net_vertex": w.net_vertex, "frame_point": w.frame_point}
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
