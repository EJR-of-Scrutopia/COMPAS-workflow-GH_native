"""The seam between a Grasshopper study and the staged cable net engine.

Everything the engine sees is newtons and millimetres. Everything the contract
carries is metres. The conversion happens in build_problem and nowhere else.

The loads here are built from the MESH, never from the contract's own
equilibrium.loads. In the exports that exist those are tributary AREAS with a
factor of one, while geometry.node_loads_newtons multiplies them by a thousand
as kilonewtons, so reading them would give a load a thousand times the area and
it would look like a number. Building them from the mesh is also the only way
they can agree with the formwork curve already on screen, which is what the
invariant in the tests checks.
"""

from __future__ import annotations

import math
from typing import Dict, List, NamedTuple, Optional, Sequence

import geometry
import staging


class CableNetError(RuntimeError):
    """Raised when a study cannot be turned into a cable net problem."""


def stage_node_loads(vertices, faces, plan, thickness, density,
                     gravity=staging.GRAVITY):
    """Per stage, the downward load at every node from the faces placed by then.

    vertices and faces are the contract's own arrays in METRES, as
    geometry.mesh_arrays returns them: face_area is an area in square metres and
    the weight below is already newtons, so only coordinates ever need scaling.

    A face's weight is shared equally between its corners. A corner-area
    weighting would also preserve the total, which is the quantity that matters,
    and would add a choice with no evidence behind it.
    """

    out = []
    for entry in plan:
        loads = [[0.0, 0.0, 0.0] for _ in vertices]
        for index in entry["faces"]:
            face = faces[index]
            weight = (
                geometry.face_area(vertices, face) * thickness * density * gravity
            )
            share = weight / float(len(face))
            for node in face:
                loads[node][2] -= share
        out.append(loads)
    return out


def net_weight_loads(vertices, edges, mass_per_metre, gravity=staging.GRAVITY):
    """The rope's own weight, half of each member at each of its ends.

    The whole net hangs from the moment it is raised, so this does not vary by
    stage. It matters because hold and capacity both refuse a stage with no load
    at all rather than answering zero.
    """

    loads = [[0.0, 0.0, 0.0] for _ in vertices]
    for u, v in edges:
        a, b = vertices[int(u)], vertices[int(v)]
        length = math.sqrt(
            (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
        )
        half = length * float(mass_per_metre) * gravity / 2.0
        loads[int(u)][2] -= half
        loads[int(v)][2] -= half
    return loads


class Wire(NamedTuple):
    """One spooled cable: a net node, and the frame point it is pulled to."""

    name: str
    net_vertex: int
    frame_point: list                 # millimetres


def wires_from_mechanism(document, vertex_count, anchors):
    """The wires a study's mechanism document declares, in millimetres.

    mechanism.py validates the schema and the scale and hands the document
    through verbatim by design, so the wire keys are read and checked here. The
    document's components, its motors and reels, are deliberately ignored:
    choosing those is what the chooser does.
    """

    body = (document or {}).get("mechanism") or {}
    raw = body.get("wires")
    if not raw:
        raise CableNetError(
            "This study's mechanism document declares no wires. Add one wire "
            "per spool, each naming the net_vertex it pulls and the frame "
            "point it is anchored to, and export it again."
        )
    held = set(int(index) for index in anchors)
    wires = []
    for position, entry in enumerate(raw):
        name = str(entry.get("name") or "wire {}".format(position + 1))
        if "net_vertex" not in entry:
            raise CableNetError(
                "Wire {!r} carries no net_vertex, so nothing says which node it "
                "pulls.".format(name)
            )
        node = int(entry["net_vertex"])
        if not 0 <= node < int(vertex_count):
            raise CableNetError(
                "Wire {!r} pulls net_vertex {}, which is outside this study's "
                "0 to {}.".format(name, node, int(vertex_count) - 1)
            )
        if node in held:
            raise CableNetError(
                "Wire {!r} pulls net_vertex {}, which is an anchor. Commanding "
                "a fixed node moves nothing and would silently achieve "
                "nothing.".format(name, node)
            )
        point = entry.get("frame_point") or {}
        try:
            frame = [
                float(point["x"]) * 1000.0,
                float(point["y"]) * 1000.0,
                float(point["z"]) * 1000.0,
            ]
        except (KeyError, TypeError, ValueError):
            raise CableNetError(
                "Wire {!r} has no usable frame_point; it needs x, y and z in "
                "metres.".format(name)
            )
        wires.append(Wire(name=name, net_vertex=node, frame_point=frame))
    return wires


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
