"""Global planar force diagrams derived from solved COMPAS FD sessions.

``FDVisualize`` deliberately draws independent nodal force polygons.  This
module performs the additional topological operation required by classical
graphic statics: it orders every nodal polygon cyclically and glues opposite
copies of shared member-force sides into one connected reciprocal.

The translation-only construction is exact for connected acyclic graphs.  A
serial cable or arch automatically becomes the familiar common-pole fan with a
cumulative load line.  A branching tree becomes a connected collection of
force cells.  Cyclic form graphs are routed to COMPAS AGS, whose mesh-dual data
structure is the appropriate general representation.
"""

from collections import deque
import math
from typing import NamedTuple

import numpy as np


class GraphicStaticsError(ValueError):
    """Raised when an FD session cannot form one planar global reciprocal."""


class ForceSide(NamedTuple):
    """One placed side of a joint force cell."""

    node: int
    kind: str
    source: int
    other: int
    vector: tuple
    start: tuple
    end: tuple


class ForceCell(NamedTuple):
    """One nodal equilibrium polygon after global stitching."""

    node: int
    sides: tuple
    points: tuple
    closure_error: float


class BoundaryLoop(NamedTuple):
    """One ordered external-force boundary.

    ``points`` retains every load and reaction subdivision.
    ``simplified_points`` removes only duplicate and forward-collinear points.
    """

    sides: tuple
    points: tuple
    simplified_points: tuple
    closure_error: float


class StitchedForceDiagram(NamedTuple):
    """A connected global reciprocal derived from an FD session."""

    cells: tuple
    member_lines: tuple
    load_lines: tuple
    reaction_lines: tuple
    boundary_loops: tuple
    chain_path: tuple
    chain_edges: tuple
    pole: object
    load_line_points: tuple
    plane_xaxis: tuple
    plane_yaxis: tuple
    plane_normal: tuple
    form_planarity_error: float
    force_planarity_error: float
    force_dimension: int
    fits_outer_envelope: bool
    max_joint_closure_error: float
    max_glue_error: float
    report: str


def _vadd(a, b):
    return tuple(a[index] + b[index] for index in range(3))


def _vsub(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def _vscale(a, factor):
    return tuple(factor * a[index] for index in range(3))


def _dot(a, b):
    return sum(a[index] * b[index] for index in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a, label):
    length = _length(a)
    if not math.isfinite(length) or length <= 1e-15:
        raise GraphicStaticsError(
            "{} must be a finite non-zero vector.".format(label)
        )
    return _vscale(a, 1.0 / length)


def _point(value, label):
    try:
        point = tuple(float(component) for component in value)
    except (TypeError, ValueError):
        raise GraphicStaticsError("{} is not a coordinate sequence.".format(label))
    if len(point) == 2:
        point = point + (0.0,)
    if len(point) != 3 or not all(math.isfinite(value) for value in point):
        raise GraphicStaticsError(
            "{} must contain two or three finite values.".format(label)
        )
    return point


def _plane_axes(xaxis, yaxis):
    xaxis = _unit(_point(xaxis, "plane x-axis"), "plane x-axis")
    yaxis = _point(yaxis, "plane y-axis")
    yaxis = _vsub(yaxis, _vscale(xaxis, _dot(yaxis, xaxis)))
    yaxis = _unit(yaxis, "plane y-axis")
    normal = _unit(_cross(xaxis, yaxis), "plane normal")
    return xaxis, yaxis, normal


def _infer_plane(xyz, edges, loads, reactions):
    """Infer a stable right-handed force plane from form and external vectors."""

    candidates = []
    for u, v in edges:
        vector = np.asarray(xyz[v], dtype=float) - np.asarray(xyz[u], dtype=float)
        length = float(np.linalg.norm(vector))
        if length > 1e-15:
            candidates.append(vector / length)
    for vector in tuple(loads) + tuple(reactions):
        vector = np.asarray(vector, dtype=float)
        length = float(np.linalg.norm(vector))
        if length > 1e-15:
            candidates.append(vector / length)
    if not candidates:
        raise GraphicStaticsError("Could not infer a plane from zero-length vectors.")

    matrix = np.asarray(candidates, dtype=float)
    _, singular, vh = np.linalg.svd(matrix, full_matrices=True)
    rank = int(np.sum(singular > max(singular[0], 1.0) * 1e-10))
    xaxis = np.asarray(vh[0], dtype=float)

    if rank >= 2:
        normal = np.asarray(vh[-1], dtype=float)
    else:
        helpers = np.eye(3)
        helper = min(helpers, key=lambda axis: abs(float(np.dot(axis, xaxis))))
        normal = np.cross(xaxis, helper)
        normal /= np.linalg.norm(normal)

    first = np.asarray(xyz[edges[0][1]], dtype=float) - np.asarray(
        xyz[edges[0][0]], dtype=float
    )
    if float(np.dot(first, xaxis)) < 0.0:
        xaxis *= -1.0

    yaxis = np.cross(normal, xaxis)
    yaxis /= np.linalg.norm(yaxis)

    total_load = np.sum(np.asarray(loads, dtype=float), axis=0)
    if float(np.linalg.norm(total_load)) > 1e-15 and float(
        np.dot(total_load, yaxis)
    ) > 0.0:
        yaxis *= -1.0
        normal *= -1.0

    return (
        tuple(float(value) for value in xaxis),
        tuple(float(value) for value in yaxis),
        tuple(float(value) for value in normal),
    )


def _angle(vector, xaxis, yaxis):
    return math.atan2(_dot(vector, yaxis), _dot(vector, xaxis))


def _distance(a, b):
    return _length(_vsub(a, b))


def _translate(point, translation):
    return _vadd(point, translation)


def _simplify_closed_polygon(points, tolerance):
    """Remove duplicate and forward-collinear vertices, preserving reversals."""

    if len(points) <= 1:
        return tuple(points)
    vertices = list(
        points[:-1] if _distance(points[0], points[-1]) <= tolerance else points
    )
    changed = True
    while changed and len(vertices) >= 3:
        changed = False
        output = []
        count = len(vertices)
        for index, current in enumerate(vertices):
            previous = vertices[(index - 1) % count]
            following = vertices[(index + 1) % count]
            incoming = _vsub(current, previous)
            outgoing = _vsub(following, current)
            lin = _length(incoming)
            lout = _length(outgoing)
            if lin <= tolerance or lout <= tolerance:
                changed = True
                continue
            cross_length = _length(_cross(incoming, outgoing))
            is_collinear = cross_length <= tolerance * max(1.0, lin * lout)
            if is_collinear and _dot(incoming, outgoing) > 0.0:
                changed = True
                continue
            output.append(current)
        vertices = output
    if not vertices:
        return tuple()
    return tuple(vertices + [vertices[0]])


def _chain_path(vertex_count, edges, xyz, xaxis, start_node):
    adjacency = [[] for _ in range(vertex_count)]
    for edge_index, (u, v) in enumerate(edges):
        adjacency[u].append((v, edge_index))
        adjacency[v].append((u, edge_index))
    if len(edges) != vertex_count - 1 or any(len(items) > 2 for items in adjacency):
        return tuple(), tuple()
    endpoints = [node for node, items in enumerate(adjacency) if len(items) == 1]
    if len(endpoints) != 2:
        return tuple(), tuple()
    if start_node is None:
        start = min(endpoints, key=lambda node: (_dot(xyz[node], xaxis), node))
    else:
        start = int(start_node)
        if start not in endpoints:
            raise GraphicStaticsError(
                "StartNode must be one of the chain terminals: {}.".format(
                    ", ".join(str(value) for value in endpoints)
                )
            )

    nodes = [start]
    edge_path = []
    previous = None
    current = start
    while True:
        choices = [item for item in adjacency[current] if item[0] != previous]
        if not choices:
            break
        neighbour, edge_index = choices[0]
        nodes.append(neighbour)
        edge_path.append(edge_index)
        previous, current = current, neighbour
    if len(nodes) != vertex_count:
        return tuple(), tuple()
    return tuple(nodes), tuple(edge_path)


def _common_endpoint(lines, tolerance):
    if len(lines) < 2:
        return None
    for candidate in lines[0]:
        if all(
            _distance(candidate, line[0]) <= tolerance
            or _distance(candidate, line[1]) <= tolerance
            for line in lines
        ):
            return candidate
    return None


def _force_dimension(points, xaxis, yaxis, tolerance):
    if not points:
        return 0
    values = np.asarray(
        [[_dot(point, xaxis), _dot(point, yaxis)] for point in points],
        dtype=float,
    )
    values -= np.mean(values, axis=0)
    if not np.any(values):
        return 0
    singular = np.linalg.svd(values, compute_uv=False)
    reference = max(float(singular[0]), 1.0)
    return int(np.sum(singular > tolerance * reference))


def _point_in_triangle(point, triangle, xaxis, yaxis, tolerance):
    values = np.asarray(
        [
            [_dot(value, xaxis), _dot(value, yaxis)]
            for value in (triangle[0], triangle[1], triangle[2], point)
        ],
        dtype=float,
    )
    a, b, c, p = values
    matrix = np.column_stack((b - a, c - a))
    determinant = float(np.linalg.det(matrix))
    if abs(determinant) <= tolerance:
        return False
    uv = np.linalg.solve(matrix, p - a)
    return (
        float(uv[0]) >= -tolerance
        and float(uv[1]) >= -tolerance
        and float(uv.sum()) <= 1.0 + tolerance
    )


def stitch_fd_force_diagram(
    session,
    plane_xaxis=None,
    plane_yaxis=None,
    start_node=None,
    tolerance=1e-8,
    clockwise=True,
):
    """Stitch one connected acyclic FD network into a global force diagram.

    Parameters
    ----------
    session : :class:`FDSession`
        Solved whole-network COMPAS FD session.
    plane_xaxis, plane_yaxis : sequence of float, optional
        Axes of the planar form/force system. If both are omitted, a best-fit
        orientation is inferred from member and external-force vectors.
    start_node : int, optional
        Preferred first terminal for a serial chain. It only controls ordered
        chain mappings; it does not change equilibrium.
    tolerance : float, optional
        Relative planarity, closure, and stitching tolerance.
    clockwise : bool, optional
        Cyclic side orientation. Clockwise places the pole on the conventional
        side of a vertical load line for right/up diagram axes.

    Returns
    -------
    :class:`StitchedForceDiagram`
        Connected reciprocal cells, shared member lines, external boundary, and
        chain-fan specialisation when applicable.
    """

    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise GraphicStaticsError("tolerance must be finite and positive.")

    xyz = tuple(
        _point(value, "equilibrium vertex {}".format(index))
        for index, value in enumerate(session.equilibrium_vertices)
    )
    edges = tuple((int(u), int(v)) for u, v in session.source_edges)
    q = tuple(float(value) for value in session.force_densities)
    loads = tuple(
        _point(value, "load {}".format(index))
        for index, value in enumerate(session.loads)
    )
    reactions = tuple(
        _point(value, "reaction {}".format(index))
        for index, value in enumerate(session.support_reactions)
    )
    vertex_count = len(xyz)
    if (
        len(q) != len(edges)
        or len(loads) != vertex_count
        or len(reactions) != vertex_count
    ):
        raise GraphicStaticsError("Session arrays are not aligned.")
    if not edges:
        raise GraphicStaticsError("At least one structural edge is required.")

    if (plane_xaxis is None) != (plane_yaxis is None):
        raise GraphicStaticsError(
            "Provide both plane axes, or leave both empty for automatic inference."
        )
    if plane_xaxis is None:
        xaxis, yaxis, normal = _infer_plane(xyz, edges, loads, reactions)
    else:
        xaxis, yaxis, normal = _plane_axes(plane_xaxis, plane_yaxis)

    incident = [[] for _ in range(vertex_count)]
    raw = [[] for _ in range(vertex_count)]
    form_planarity_error = 0.0
    force_planarity_error = 0.0

    def update_planarity(vector, kind):
        nonlocal form_planarity_error, force_planarity_error
        length = _length(vector)
        if length <= 1e-15:
            return
        ratio = abs(_dot(vector, normal)) / length
        if kind == "form":
            form_planarity_error = max(form_planarity_error, ratio)
        else:
            force_planarity_error = max(force_planarity_error, ratio)

    def add_raw(node, kind, source, other, ray, vector):
        raw[node].append(
            {
                "node": node,
                "kind": kind,
                "source": source,
                "other": other,
                "ray": ray,
                "vector": vector,
            }
        )

    for edge_index, (u, v) in enumerate(edges):
        if not (0 <= u < vertex_count and 0 <= v < vertex_count) or u == v:
            raise GraphicStaticsError(
                "Structural edge {} is invalid.".format(edge_index)
            )
        direction = _vsub(xyz[v], xyz[u])
        if _length(direction) <= 1e-15:
            raise GraphicStaticsError(
                "Structural edge {} has collapsed.".format(edge_index)
            )
        vector = _vscale(direction, q[edge_index])
        if _length(vector) <= 1e-15:
            raise GraphicStaticsError(
                "Structural edge {} has zero force.".format(edge_index)
            )
        update_planarity(direction, "form")
        update_planarity(vector, "force")
        add_raw(u, "member", edge_index, v, direction, vector)
        add_raw(
            v,
            "member",
            edge_index,
            u,
            _vscale(direction, -1.0),
            _vscale(vector, -1.0),
        )
        incident[u].append(v)
        incident[v].append(u)

    force_reference = max(
        [1.0]
        + [
            _length(_vscale(_vsub(xyz[v], xyz[u]), q[index]))
            for index, (u, v) in enumerate(edges)
        ]
        + [_length(vector) for vector in loads + reactions]
    )
    zero_force = tolerance * force_reference
    for node in range(vertex_count):
        for kind, values in (("load", loads), ("reaction", reactions)):
            vector = values[node]
            if _length(vector) <= zero_force:
                continue
            update_planarity(vector, "force")
            add_raw(node, kind, node, -1, vector, vector)

    if (
        form_planarity_error > tolerance
        or force_planarity_error > tolerance
    ):
        raise GraphicStaticsError(
            "The FD session is not planar in the selected diagram plane "
            "(form {:.3e}, forces {:.3e}, tolerance {:.3e}).".format(
                form_planarity_error,
                force_planarity_error,
                tolerance,
            )
        )

    seen = {0}
    queue = deque([0])
    while queue:
        node = queue.popleft()
        for neighbour in incident[node]:
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    if len(seen) != vertex_count:
        raise GraphicStaticsError(
            "One global reciprocal requires one connected FD network. "
            "Solve or visualise disconnected trees as separate components."
        )
    if len(edges) != vertex_count - 1:
        raise GraphicStaticsError(
            "FD cell stitching currently accepts acyclic networks only. "
            "Use AGSGraphicStatics for a canopy, truss, or other cyclic planar "
            "form graph."
        )

    priority = {"member": 0, "load": 1, "reaction": 2}
    local_sides = [[] for _ in range(vertex_count)]
    next_halfedge = {}
    twin = {}
    member_halfedges = {}
    joint_errors = []
    halfedge = 0
    for node in range(vertex_count):
        ordered = sorted(
            raw[node],
            key=lambda item: (
                -_angle(item["ray"], xaxis, yaxis)
                if clockwise
                else _angle(item["ray"], xaxis, yaxis),
                priority[item["kind"]],
                item["source"],
                item["other"],
            ),
        )
        cursor = (0.0, 0.0, 0.0)
        node_halfedges = []
        for item in ordered:
            item["halfedge"] = halfedge
            item["start"] = cursor
            cursor = _vadd(cursor, item["vector"])
            item["end"] = cursor
            local_sides[node].append(item)
            node_halfedges.append(halfedge)
            if item["kind"] == "member":
                member_halfedges.setdefault(item["source"], []).append(halfedge)
            halfedge += 1
        if not node_halfedges:
            raise GraphicStaticsError(
                "Node {} has no non-zero force sides.".format(node)
            )
        for index, key in enumerate(node_halfedges):
            next_halfedge[key] = node_halfedges[(index + 1) % len(node_halfedges)]
        joint_errors.append(_length(cursor))

    by_halfedge = {
        item["halfedge"]: item for sides in local_sides for item in sides
    }
    for edge_index in range(len(edges)):
        halves = member_halfedges.get(edge_index, [])
        if len(halves) != 2:
            raise GraphicStaticsError(
                "Member {} does not have two force halfedges.".format(edge_index)
            )
        twin[halves[0]] = halves[1]
        twin[halves[1]] = halves[0]

    max_joint_error = max(joint_errors)
    if max_joint_error > tolerance * force_reference:
        raise GraphicStaticsError(
            "A joint force polygon does not close (maximum error {:.6g}). "
            "Check support reactions and FD residuals.".format(max_joint_error)
        )

    translations = {0: (0.0, 0.0, 0.0)}
    queue = deque([0])
    glue_errors = []
    while queue:
        node = queue.popleft()
        for item in local_sides[node]:
            if item["kind"] != "member":
                continue
            adjacent = item["other"]
            opposite = by_halfedge[twin[item["halfedge"]]]
            parent_end = _translate(item["end"], translations[node])
            candidate = _vsub(parent_end, opposite["start"])
            mapped_end = _translate(opposite["end"], candidate)
            parent_start = _translate(item["start"], translations[node])
            glue_errors.append(_distance(mapped_end, parent_start))
            if adjacent in translations:
                glue_errors.append(_distance(candidate, translations[adjacent]))
            else:
                translations[adjacent] = candidate
                queue.append(adjacent)
    max_glue_error = max(glue_errors or [0.0])
    if max_glue_error > tolerance * force_reference:
        raise GraphicStaticsError(
            "Reciprocal cells are globally incompatible "
            "(maximum glue error {:.6g}). Use COMPAS AGS for cyclic/global "
            "reciprocal solving.".format(max_glue_error)
        )

    def placed(item, endpoint):
        return _translate(item[endpoint], translations[item["node"]])

    external_halfedges = {
        key for key, item in by_halfedge.items() if item["kind"] != "member"
    }
    if not external_halfedges:
        raise GraphicStaticsError(
            "No external load or reaction sides were found in the FD session."
        )

    def next_boundary(key):
        candidate = next_halfedge[key]
        guard = 0
        while candidate not in external_halfedges:
            candidate = next_halfedge[twin[candidate]]
            guard += 1
            if guard > len(by_halfedge):
                raise GraphicStaticsError(
                    "Boundary traversal did not reach an external side."
                )
        return candidate

    boundary_keys = []
    unvisited = set(external_halfedges)
    while unvisited:
        start = min(unvisited)
        loop = []
        current = start
        while current not in loop:
            if current not in external_halfedges:
                raise GraphicStaticsError(
                    "Boundary traversal reached an internal side."
                )
            loop.append(current)
            unvisited.discard(current)
            current = next_boundary(current)
        if current != start:
            raise GraphicStaticsError(
                "The external force boundary branches or self-merges."
            )
        boundary_keys.append(tuple(loop))

    path, path_edges = _chain_path(
        vertex_count,
        edges,
        xyz,
        xaxis,
        start_node,
    )
    raw_member_lines = []
    for edge_index, (u, _) in enumerate(edges):
        item = next(
            item
            for item in local_sides[u]
            if item["kind"] == "member" and item["source"] == edge_index
        )
        raw_member_lines.append((placed(item, "start"), placed(item, "end")))
    pole = (
        _common_endpoint(raw_member_lines, tolerance * force_reference)
        if path
        else None
    )

    shift = _vscale(pole, -1.0) if pole is not None else (0.0, 0.0, 0.0)

    def shifted(point):
        return _translate(point, shift)

    cells = []
    load_lines = []
    reaction_lines = []
    all_points = []
    for node, sides in enumerate(local_sides):
        public = []
        points = []
        for item in sides:
            start = shifted(placed(item, "start"))
            end = shifted(placed(item, "end"))
            side = ForceSide(
                node=node,
                kind=item["kind"],
                source=item["source"],
                other=item["other"],
                vector=item["vector"],
                start=start,
                end=end,
            )
            public.append(side)
            points.append(start)
            all_points.extend((start, end))
            if item["kind"] == "load":
                load_lines.append(side)
            elif item["kind"] == "reaction":
                reaction_lines.append(side)
        points.append(public[-1].end)
        cells.append(
            ForceCell(
                node=node,
                sides=tuple(public),
                points=tuple(points),
                closure_error=joint_errors[node],
            )
        )

    member_lines = tuple(
        (shifted(line[0]), shifted(line[1])) for line in raw_member_lines
    )
    shifted_pole = shifted(pole) if pole is not None else None

    boundary_loops = []
    for keys in boundary_keys:
        sides = []
        points = []
        for key in keys:
            item = by_halfedge[key]
            start = shifted(placed(item, "start"))
            end = shifted(placed(item, "end"))
            sides.append(
                ForceSide(
                    node=item["node"],
                    kind=item["kind"],
                    source=item["source"],
                    other=item["other"],
                    vector=item["vector"],
                    start=start,
                    end=end,
                )
            )
            points.append(start)
        points.append(sides[-1].end)
        closure_error = _distance(points[0], points[-1])
        boundary_loops.append(
            BoundaryLoop(
                sides=tuple(sides),
                points=tuple(points),
                simplified_points=_simplify_closed_polygon(
                    points,
                    tolerance * force_reference,
                ),
                closure_error=closure_error,
            )
        )

    load_line_points = []
    if path and shifted_pole is not None:
        for edge_index in path_edges:
            line = member_lines[edge_index]
            if _distance(line[0], shifted_pole) <= tolerance * force_reference:
                load_line_points.append(line[1])
            elif _distance(line[1], shifted_pole) <= tolerance * force_reference:
                load_line_points.append(line[0])
            else:
                load_line_points = []
                break

    triangular = (
        len(boundary_loops) == 1
        and len(boundary_loops[0].simplified_points) == 4
    )
    fits = False
    if triangular and shifted_pole is not None and load_line_points:
        triangle = boundary_loops[0].simplified_points[:3]
        fits = all(
            _point_in_triangle(
                point,
                triangle,
                xaxis,
                yaxis,
                tolerance * force_reference,
            )
            for point in load_line_points
        )

    force_dimension = _force_dimension(
        all_points,
        xaxis,
        yaxis,
        tolerance,
    )
    warnings = []
    if force_dimension < 2:
        warnings.append(
            "The reciprocal is degenerate (force-space dimension {}). "
            "A bare one-root tree under parallel tip loads needs a canopy, "
            "another reaction path, or a frame/bending analysis.".format(
                force_dimension
            )
        )
    if path and shifted_pole is None:
        warnings.append("The chain did not produce one common force pole.")

    report = (
        "Global COMPAS FD graphic statics complete\n"
        "Joint cells: {}  Shared member sides: {}  External sides: {}\n"
        "Boundary loops: {}  Simplified envelope: {}\n"
        "Serial funicular fan: {}  Common pole: {}  Fits envelope: {}\n"
        "Force-space dimension: {}\n"
        "Planarity error (form/force): {:.3e} / {:.3e}\n"
        "Maximum joint closure error: {:.3e}\n"
        "Maximum member stitch error: {:.3e}"
    ).format(
        len(cells),
        len(member_lines),
        len(load_lines) + len(reaction_lines),
        len(boundary_loops),
        (
            len(boundary_loops[0].simplified_points) - 1
            if len(boundary_loops) == 1
            else "multiple"
        ),
        bool(path),
        shifted_pole is not None,
        fits,
        force_dimension,
        form_planarity_error,
        force_planarity_error,
        max_joint_error,
        max_glue_error,
    )
    if warnings:
        report += "\nWarning: " + " ".join(warnings)

    return StitchedForceDiagram(
        cells=tuple(cells),
        member_lines=member_lines,
        load_lines=tuple(load_lines),
        reaction_lines=tuple(reaction_lines),
        boundary_loops=tuple(boundary_loops),
        chain_path=path,
        chain_edges=path_edges,
        pole=shifted_pole,
        load_line_points=tuple(load_line_points),
        plane_xaxis=xaxis,
        plane_yaxis=yaxis,
        plane_normal=normal,
        form_planarity_error=form_planarity_error,
        force_planarity_error=force_planarity_error,
        force_dimension=force_dimension,
        fits_outer_envelope=fits,
        max_joint_closure_error=max_joint_error,
        max_glue_error=max_glue_error,
        report=report,
    )


def funicular_force_diagram(session, **kwargs):
    """Return the stitched diagram after requiring the serial-chain special case."""

    result = stitch_fd_force_diagram(session, **kwargs)
    if not result.chain_path or result.pole is None:
        raise GraphicStaticsError(
            "A funicular pole diagram requires one connected serial chain with "
            "two terminals. Use the stitched tree output or COMPAS AGS instead."
        )
    return result
