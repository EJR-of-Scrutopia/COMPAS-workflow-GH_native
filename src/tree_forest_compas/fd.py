"""Whole-network force-density equilibrium with stable source mappings.

This module wraps COMPAS FD without Rhino dependencies. Straight input segments
are welded into one graph, solved once, and returned as a session that can be
passed to visualisation, model and export stages.
"""

from collections import deque
from typing import NamedTuple

import numpy as np


class FDInputError(ValueError):
    """Raised when source geometry or boundary data is invalid."""


class FDSolveError(RuntimeError):
    """Raised when COMPAS FD cannot solve the registered network."""


class FDProblem(NamedTuple):
    """A complete registered network before loads and boundary conditions."""

    source_lines: tuple
    source_vertices: tuple
    source_edges: tuple
    endpoint_to_vertex: tuple
    components: tuple
    tolerance: float


class FDSession(NamedTuple):
    """A solved force-density network and its source correspondence."""

    source_lines: tuple
    source_vertices: tuple
    source_edges: tuple
    endpoint_to_vertex: tuple
    fixed: tuple
    loads: tuple
    force_densities: tuple
    equilibrium_vertices: tuple
    member_forces: tuple
    member_lengths: tuple
    residuals: tuple
    support_reactions: tuple
    components: tuple
    report: str


class JointForcePolygon(NamedTuple):
    """One local nodal force polygon.

    ``member_vectors`` follows source-member order. ``points`` contains the
    cumulative polygon vertices after members, external load, and (for supports)
    reaction have been appended.
    """

    node: int
    member_indices: tuple
    member_vectors: tuple
    load_vector: tuple
    reaction_vector: tuple
    points: tuple
    closure_vector: tuple
    closure_error: float


def _point(value, label):
    try:
        coordinates = tuple(float(component) for component in value)
    except (TypeError, ValueError):
        raise FDInputError("{} is not a coordinate sequence.".format(label))
    if len(coordinates) == 2:
        coordinates = coordinates + (0.0,)
    if len(coordinates) != 3 or not all(np.isfinite(coordinates)):
        raise FDInputError("{} must contain two or three finite values.".format(label))
    return coordinates


def _register_lines(lines, tolerance):
    if tolerance <= 0.0:
        raise FDInputError("tolerance must be positive.")

    clean = []
    vertices = []
    edges = []
    endpoints = []
    tolerance2 = float(tolerance) ** 2

    def vertex_index(point):
        xyz = np.asarray(point, dtype=float)
        for index, existing in enumerate(vertices):
            delta = existing - xyz
            if float(np.dot(delta, delta)) <= tolerance2:
                return index
        vertices.append(xyz)
        return len(vertices) - 1

    for index, line in enumerate(lines or []):
        if line is None or len(line) != 2:
            raise FDInputError(
                "Source line {} is not an endpoint pair.".format(index)
            )
        a = _point(line[0], "Source line {} start".format(index))
        b = _point(line[1], "Source line {} end".format(index))
        u = vertex_index(a)
        v = vertex_index(b)
        if u == v:
            raise FDInputError(
                "Source line {} collapses inside the weld tolerance.".format(index)
            )
        clean.append((a, b))
        edges.append((u, v))
        endpoints.append((u, v))

    if not clean:
        raise FDInputError("At least one straight source line is required.")
    return (
        tuple(clean),
        tuple(tuple(float(value) for value in xyz) for xyz in vertices),
        tuple(edges),
        tuple(endpoints),
    )


def _components(vertex_count, edges):
    adjacency = [[] for _ in range(vertex_count)]
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)

    unseen = set(range(vertex_count))
    output = []
    while unseen:
        start = min(unseen)
        queue = deque([start])
        unseen.remove(start)
        component = []
        while queue:
            node = queue.popleft()
            component.append(node)
            for neighbour in adjacency[node]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    queue.append(neighbour)
        output.append(tuple(sorted(component)))
    return tuple(output)


def _coerce_fixed(fixed, vertex_count):
    values = tuple(sorted(set(int(value) for value in (fixed or []))))
    if not values:
        raise FDInputError("At least one fixed/support vertex is required.")
    if values[0] < 0 or values[-1] >= vertex_count:
        raise FDInputError(
            "A fixed vertex index is outside 0..{}.".format(vertex_count - 1)
        )
    return values


def _coerce_q(forcedensities, edge_count):
    if np.ndim(forcedensities) == 0:
        values = np.full(edge_count, float(forcedensities), dtype=float)
    else:
        values = np.asarray(forcedensities, dtype=float).reshape(-1)
    if len(values) != edge_count:
        raise FDInputError(
            "force densities must be scalar or have one value per source segment."
        )
    if not np.all(np.isfinite(values)) or np.any(np.abs(values) <= 1e-12):
        raise FDInputError("force densities must be finite and non-zero.")
    return values


def _coerce_loads(loads, vertex_count):
    if loads is None:
        return np.zeros((vertex_count, 3), dtype=float)
    values = np.asarray(loads, dtype=float)
    if values.shape != (vertex_count, 3):
        raise FDInputError(
            "loads must have shape ({}, 3), aligned with registered vertices.".format(
                vertex_count
            )
        )
    if not np.all(np.isfinite(values)):
        raise FDInputError("loads must contain only finite values.")
    return values


def solve_fd_network(
    lines,
    fixed,
    forcedensities=1.0,
    loads=None,
    tolerance=1e-6,
):
    """Register and solve all source segments as one COMPAS FD network.

    Positive force density follows COMPAS FD's tension convention; negative force
    density represents compression. Values are force per length.
    """

    problem = register_fd_network(lines, tolerance=tolerance)
    return solve_fd_problem(
        problem,
        fixed=fixed,
        forcedensities=forcedensities,
        loads=loads,
    )


def register_fd_network(lines, tolerance=1e-6):
    """Weld all source segments into one stable whole-network problem."""

    source_lines, vertices, edges, endpoints = _register_lines(lines, tolerance)
    return FDProblem(
        source_lines=source_lines,
        source_vertices=vertices,
        source_edges=edges,
        endpoint_to_vertex=endpoints,
        components=_components(len(vertices), edges),
        tolerance=float(tolerance),
    )


def solve_fd_problem(problem, fixed, forcedensities=1.0, loads=None):
    """Solve a previously registered :class:`FDProblem`."""

    source_lines = problem.source_lines
    vertices = problem.source_vertices
    edges = problem.source_edges
    endpoints = problem.endpoint_to_vertex
    components = problem.components
    vertex_count = len(vertices)
    fixed = _coerce_fixed(fixed, vertex_count)
    q = _coerce_q(forcedensities, len(edges))
    p = _coerce_loads(loads, vertex_count)

    fixed_set = set(fixed)
    unsupported = [
        index
        for index, component in enumerate(components)
        if not fixed_set.intersection(component)
    ]
    if unsupported:
        raise FDInputError(
            "Every connected component needs a support; unsupported component(s): "
            + ", ".join(str(index) for index in unsupported)
        )

    try:
        from compas_fd.solvers import fd_numpy

        result = fd_numpy(
            vertices=vertices,
            fixed=list(fixed),
            edges=list(edges),
            forcedensities=q.tolist(),
            loads=p,
        )
    except Exception as error:
        raise FDSolveError(
            "COMPAS FD failed. Check supports, topology and force-density signs: "
            + str(error)
        )

    xyz = np.asarray(result.vertices, dtype=float)
    forces = np.asarray(result.forces, dtype=float).reshape(-1)
    lengths = np.asarray(result.lengths, dtype=float).reshape(-1)
    residuals = np.asarray(result.residuals, dtype=float)
    if (
        xyz.shape != (vertex_count, 3)
        or residuals.shape != (vertex_count, 3)
        or len(forces) != len(edges)
        or not np.all(np.isfinite(xyz))
        or not np.all(np.isfinite(forces))
        or not np.all(np.isfinite(residuals))
    ):
        raise FDSolveError("COMPAS FD returned non-finite or misaligned results.")

    reactions = np.zeros_like(residuals)
    reactions[list(fixed)] = -residuals[list(fixed)]
    free = sorted(set(range(vertex_count)) - fixed_set)
    max_free_residual = (
        float(np.linalg.norm(residuals[free], axis=1).max()) if free else 0.0
    )
    report = (
        "COMPAS FD whole-network solve complete\n"
        "Source segments: {}  Registered vertices: {}\n"
        "Connected components: {}  Supports: {}\n"
        "Force convention: positive=tension, negative=compression\n"
        "Maximum |member force|: {:.6g}\n"
        "Maximum free-node residual: {:.3e}"
    ).format(
        len(edges),
        vertex_count,
        len(components),
        len(fixed),
        float(np.abs(forces).max()) if len(forces) else 0.0,
        max_free_residual,
    )

    def rows(values):
        return tuple(tuple(float(component) for component in row) for row in values)

    return FDSession(
        source_lines=source_lines,
        source_vertices=vertices,
        source_edges=edges,
        endpoint_to_vertex=endpoints,
        fixed=fixed,
        loads=rows(p),
        force_densities=tuple(float(value) for value in q),
        equilibrium_vertices=rows(xyz),
        member_forces=tuple(float(value) for value in forces),
        member_lengths=tuple(float(value) for value in lengths),
        residuals=rows(residuals),
        support_reactions=rows(reactions),
        components=components,
        report=report,
    )


def joint_force_polygons(session, nodes=None, scale=1.0):
    """Construct local force polygons for selected equilibrium nodes.

    These are separate nodal polygons. They are not a single global reciprocal
    force diagram. A degree-two loaded catenary node naturally produces a
    triangle: two member-force sides plus one load side.
    """

    scale = float(scale)
    if not np.isfinite(scale) or scale <= 0.0:
        raise FDInputError("scale must be finite and positive.")

    xyz = np.asarray(session.equilibrium_vertices, dtype=float)
    q = np.asarray(session.force_densities, dtype=float)
    loads = np.asarray(session.loads, dtype=float)
    reactions = np.asarray(session.support_reactions, dtype=float)
    edges = tuple(session.source_edges)
    if nodes is None:
        selected = tuple(range(len(xyz)))
    else:
        selected = tuple(int(node) for node in nodes)
        if selected and (min(selected) < 0 or max(selected) >= len(xyz)):
            raise FDInputError("A force-polygon node index is out of range.")

    incident = [[] for _ in range(len(xyz))]
    for edge_index, (u, v) in enumerate(edges):
        incident[u].append((edge_index, v))
        incident[v].append((edge_index, u))

    output = []
    for node in selected:
        member_indices = []
        member_vectors = []
        cursor = np.zeros(3, dtype=float)
        points = [tuple(cursor)]

        for edge_index, neighbour in incident[node]:
            vector = q[edge_index] * (xyz[neighbour] - xyz[node])
            member_indices.append(edge_index)
            member_vectors.append(tuple(float(value) for value in vector))
            cursor = cursor + scale * vector
            points.append(tuple(float(value) for value in cursor))

        load = loads[node]
        cursor = cursor + scale * load
        points.append(tuple(float(value) for value in cursor))

        reaction = reactions[node]
        cursor = cursor + scale * reaction
        points.append(tuple(float(value) for value in cursor))

        closure = (
            np.asarray(member_vectors, dtype=float).sum(axis=0)
            if member_vectors
            else np.zeros(3, dtype=float)
        )
        closure = closure + load + reaction
        output.append(
            JointForcePolygon(
                node=node,
                member_indices=tuple(member_indices),
                member_vectors=tuple(member_vectors),
                load_vector=tuple(float(value) for value in load),
                reaction_vector=tuple(float(value) for value in reaction),
                points=tuple(points),
                closure_vector=tuple(float(value) for value in closure),
                closure_error=float(np.linalg.norm(closure)),
            )
        )
    return tuple(output)
