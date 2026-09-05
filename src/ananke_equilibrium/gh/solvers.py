"""Thin FD and TNA solver component adapters."""

from __future__ import annotations

from math import sqrt
from typing import Any
from typing import Mapping

from ._base import AdapterError
from ._base import ComponentResult
from ._base import call_backend
from ._base import friendly
from ._base import get_any
from ._base import import_backend
from ._base import make_contract


_FD_BACKENDS = (
    "ananke_equilibrium.backends.fd",
    "tree_forest_compas.fd",
)
_TNA_BACKENDS = (
    "ananke_equilibrium.backends.tna",
    "tree_forest_compas.tna",
)


def _xyz_distance(a: Any, b: Any) -> float:
    return sqrt(sum((float(a[index]) - float(b[index])) ** 2 for index in range(3)))


def _nearest(vertices: tuple[Any, ...], point: Any) -> tuple[int, float]:
    if not vertices:
        raise AdapterError("The topology has no vertices.")
    values = [(_xyz_distance(vertex, point), index) for index, vertex in enumerate(vertices)]
    distance, index = min(values)
    return index, distance


def _topology_data(topology: Any) -> tuple[str, tuple, tuple, tuple]:
    kind = str(
        get_any(topology, ("kind", "topology_type"), "line")
    ).strip().lower()
    vertices = tuple(get_any(topology, ("vertices", "source_vertices"), ()))
    edges = tuple(get_any(topology, ("edges", "source_edges"), ()))
    faces = tuple(get_any(topology, ("faces",), ()))
    return kind, vertices, edges, faces


def _support_ids(
    topology: Any,
    support_set: Any,
) -> tuple[int, ...]:
    _, vertices, edges, faces = _topology_data(topology)
    if isinstance(support_set, (list, tuple)):
        mode = "explicit"
        node_ids = tuple(int(value) for value in support_set)
        points = ()
        snap = None
    else:
        mode = str(get_any(support_set, ("mode",), "explicit")).lower()
        node_ids = tuple(
            int(value)
            for value in get_any(support_set, ("node_ids", "keys"), ())
        )
        points = tuple(get_any(support_set, ("points",), ()))
        snap = get_any(support_set, ("snap_tolerance",), None)
    if points:
        selected = []
        for index, point in enumerate(points):
            node, distance = _nearest(vertices, point)
            if snap is not None and distance > float(snap):
                raise AdapterError(
                    "Support point {} is {:.6g} from its nearest node, beyond "
                    "SnapTol {:.6g}.".format(index, distance, float(snap))
                )
            selected.append(node)
        node_ids = tuple(selected)

    if mode in ("terminals", "boundary", "corners") and not node_ids:
        degree = [0] * len(vertices)
        for u, v in edges:
            degree[int(u)] += 1
            degree[int(v)] += 1
        if mode == "terminals":
            node_ids = tuple(index for index, value in enumerate(degree) if value == 1)
        elif faces:
            counts: dict[tuple[int, int], int] = {}
            for face in faces:
                for index, u in enumerate(face):
                    v = face[(index + 1) % len(face)]
                    key = (u, v) if u < v else (v, u)
                    counts[key] = counts.get(key, 0) + 1
            boundary = sorted(
                {vertex for edge, count in counts.items() if count == 1 for vertex in edge}
            )
            # Corner detection is intentionally deferred; using all boundary
            # vertices is stable and explicit in diagnostics for v0.1.
            node_ids = tuple(boundary)
        else:
            node_ids = tuple(index for index, value in enumerate(degree) if value == 1)

    node_ids = tuple(dict.fromkeys(node_ids))
    if not node_ids:
        raise AdapterError("The support set resolves to no topology nodes.")
    if min(node_ids) < 0 or max(node_ids) >= len(vertices):
        raise AdapterError("A support node ID lies outside the topology.")
    return node_ids


def _plan_tributary_areas(
    vertices: tuple,
    faces: tuple,
) -> tuple[float, ...]:
    """Plan (XY) tributary area per vertex: each face shares its shoelace
    area equally between its corners, the same discretisation RhinoVault
    uses to turn a surface load into nodal loads."""
    areas = [0.0] * len(vertices)
    for face in faces:
        corners = [vertices[int(index)] for index in face]
        doubled = 0.0
        for position in range(1, len(corners) - 1):
            ax = corners[position][0] - corners[0][0]
            ay = corners[position][1] - corners[0][1]
            bx = corners[position + 1][0] - corners[0][0]
            by = corners[position + 1][1] - corners[0][1]
            doubled += abs(ax * by - ay * bx)
        share = doubled / (2.0 * len(face))
        for index in face:
            areas[int(index)] += share
    return tuple(areas)


def _load_records(
    topology: Any,
    load_case: Any,
    *,
    vertices_override: Any = None,
    faces_override: Any = None,
    nodal_only: bool = False,
) -> tuple[tuple[int, tuple[float, float, float]], ...]:
    """Resolve one load case to (node, vector) records.

    Rule 2.4(b) of the 2026-09-04 selfweight design: a surface load's
    base vector is the SELF-WEIGHT, spread over every vertex by tributary
    area times thickness times density, and any explicit node IDs ride
    BESIDE it as ordinary point loads rather than replacing it. That is
    RhinoVault's own ``pz + pzext`` split.

    ``nodal_only`` asks for the point-load half alone, which is what the
    TNA path needs: there the self-weight is evaluated on the SOLVED
    surface inside the worker rather than on these plan areas.
    """
    _, vertices, _, faces = _topology_data(topology)
    if vertices_override is not None:
        vertices = tuple(vertices_override)
    if faces_override is not None:
        faces = tuple(faces_override)
    distribution = str(
        get_any(load_case, ("distribution",), "point")
    ).lower()
    node_ids = tuple(
        int(value) for value in get_any(load_case, ("node_ids",), ())
    )
    points = tuple(get_any(load_case, ("points",), ()))
    vectors = tuple(get_any(load_case, ("vectors",), ()))
    base_vector = get_any(load_case, ("base_vector",), None)

    if points:
        node_ids = tuple(_nearest(vertices, point)[0] for point in points)
    surface = distribution in ("tributary_area", "self_weight")
    # The self-weight half. A surface case with no base vector keeps the
    # older reading, where the explicit vectors themselves are the area
    # density at their own nodes, so nothing authored that way moves.
    surface_nodes: tuple[int, ...] = ()
    surface_vectors: tuple[Any, ...] = ()
    if surface and base_vector is not None and not nodal_only:
        if not faces:
            raise AdapterError(
                "Tributary-area loading needs registered faces to measure "
                "plan areas. Use uniform_nodes for a pure edge network."
            )
        weight = float(
            get_any(load_case, ("thickness",), 1.0)
        ) * float(get_any(load_case, ("density",), 1.0))
        areas = _plan_tributary_areas(vertices, faces)
        surface_nodes = tuple(range(len(vertices)))
        surface_vectors = tuple(
            tuple(
                float(component) * areas[node] * weight
                for component in base_vector
            )
            for node in surface_nodes
        )
    if not node_ids and (
        distribution == "uniform_nodes"
        # THE TARGET-FREE SURFACE CASE, restored. A surface load with no
        # base vector is the older reading, where the explicit vectors
        # are themselves the area density at their own nodes, and with no
        # targets it broadcasts over every vertex for the area-scaling arm
        # below to rescale. Narrowing this arm to uniform_nodes turned
        # that whole load case into NO LOAD AT ALL, silently: a unit quad
        # under a 'tributary_area' vector of (0, 0, -1) gave four records
        # of -0.25 and then gave none.
        or (surface and base_vector is None and not nodal_only)
    ):
        node_ids = tuple(range(len(vertices)))
        if base_vector is not None:
            vectors = (base_vector,)
    if not vectors and not surface_vectors:
        if nodal_only:
            return ()
        raise AdapterError("The load case contains no load vectors.")
    if not node_ids and surface and base_vector is not None:
        # The base vector has already been read as the self-weight above,
        # or deliberately withheld from it under nodal_only, and the copy
        # a target-free contract keeps in ``vectors`` is the same vector
        # again: it must not be counted a second time as a nodal load.
        # Clearing unconditionally SWALLOWED a misaligned case instead of
        # refusing it, so a point case with two vectors and no targets
        # solved with no load where it used to raise.
        vectors = ()
    elif len(vectors) == 1:
        vectors = vectors * len(node_ids)
    if len(vectors) != len(node_ids):
        raise AdapterError("Load vectors do not align with resolved load nodes.")

    if surface and base_vector is None and not nodal_only:
        if not faces:
            raise AdapterError(
                "Tributary-area loading needs registered faces to measure "
                "plan areas. Use uniform_nodes for a pure edge network."
            )
        areas = _plan_tributary_areas(vertices, faces)
        vectors = tuple(
            tuple(float(component) * areas[int(node)] for component in vector)
            for node, vector in zip(node_ids, vectors)
        )

    node_ids = tuple(surface_nodes) + tuple(node_ids)
    vectors = tuple(surface_vectors) + tuple(vectors)

    accumulated: dict[int, list[float]] = {}
    for node, vector in zip(node_ids, vectors):
        if node < 0 or node >= len(vertices):
            raise AdapterError("A load node ID lies outside the topology.")
        current = accumulated.setdefault(node, [0.0, 0.0, 0.0])
        for axis in range(3):
            current[axis] += float(vector[axis])
    return tuple(
        (node, tuple(vector))
        for node, vector in sorted(accumulated.items())
    )


def _diagnostics_from_session(session: Any, solver: str) -> dict[str, Any]:
    existing = get_any(session, ("diagnostics",), {})
    diagnostics = dict(existing) if isinstance(existing, Mapping) else {}
    if solver == "fd":
        residuals = tuple(get_any(session, ("residuals",), ()))
        fixed = set(get_any(session, ("fixed",), ()))
        free_norms = [
            sqrt(sum(float(value) ** 2 for value in residual))
            for index, residual in enumerate(residuals)
            if index not in fixed
        ]
        diagnostics.setdefault("max_free_residual", max(free_norms or [0.0]))
    diagnostics.setdefault("solver", solver)
    diagnostics.setdefault("status", "solved")
    return diagnostics


def _diagnostic_contracts(values: Mapping[str, Any]) -> tuple[Any, ...]:
    output = []
    for code, value in sorted(values.items()):
        if isinstance(value, (str, tuple, list, dict)) or value is None:
            continue
        numeric = float(value) if isinstance(value, (int, float)) else None
        output.append(
            make_contract(
                "Diagnostic",
                code=str(code),
                severity="info",
                message=str(code).replace("_", " ").capitalize(),
                value=numeric,
                context={} if numeric is not None else {"value": str(value)},
            )
        )
    return tuple(output)


def _ordered_values(values: Any) -> tuple:
    if isinstance(values, Mapping):
        return tuple(values[key] for key in sorted(values, key=str))
    return tuple(values)


def _solved_case(
    *,
    solver: str,
    topology: Any,
    supports: Any,
    load_case: Any,
    config: Any,
    backend_result: Any,
) -> Any:
    if type(backend_result).__name__ == "SolvedCase":
        return backend_result

    solver_edge_keys = ()
    if solver == "fd":
        vertices = tuple(
            get_any(backend_result, ("equilibrium_vertices", "vertices"), ())
        )
        edges = tuple(get_any(backend_result, ("source_edges", "edges"), ()))
        member_forces = tuple(
            float(value)
            for value in get_any(backend_result, ("member_forces", "forces"), ())
        )
        force_densities = tuple(
            float(value)
            for value in get_any(
                backend_result,
                ("force_densities", "edge_q"),
                (),
            )
        )
        reactions = tuple(
            get_any(
                backend_result,
                ("support_reactions", "reactions"),
                (),
            )
        )
        loads = tuple(get_any(backend_result, ("loads",), ()))
        residuals = tuple(get_any(backend_result, ("residuals",), ()))
        solver_edge_keys = edges
    else:
        form = get_any(backend_result, ("form",), None)
        vertices = ()
        edges = ()
        form_key_to_index = {}
        if form is not None and all(
            hasattr(form, name) for name in ("vertices", "vertex_coordinates", "edges")
        ):
            vertex_keys = tuple(form.vertices())
            form_key_to_index = {
                key: index for index, key in enumerate(vertex_keys)
            }
            vertices = tuple(
                tuple(float(value) for value in form.vertex_coordinates(key))
                for key in vertex_keys
            )
            solver_edge_keys = tuple(tuple(edge) for edge in form.edges())
            edges = tuple(
                (
                    form_key_to_index[edge[0]],
                    form_key_to_index[edge[1]],
                )
                for edge in solver_edge_keys
            )
        force_values = get_any(
            backend_result,
            ("edge_forces", "member_forces"),
            (),
        )
        density_values = get_any(
            backend_result,
            ("edge_q", "force_densities"),
            (),
        )
        if isinstance(force_values, Mapping):
            ordered_edges = tuple(sorted(force_values, key=str))
            solver_edge_keys = ordered_edges
            edges = tuple(
                (
                    form_key_to_index[edge[0]],
                    form_key_to_index[edge[1]],
                )
                if form_key_to_index
                else (int(edge[0]), int(edge[1]))
                for edge in ordered_edges
            )
            member_forces = tuple(
                float(force_values[edge]) for edge in ordered_edges
            )
            if isinstance(density_values, Mapping):
                force_densities = tuple(
                    float(density_values[edge]) for edge in ordered_edges
                )
            else:
                force_densities = _ordered_values(density_values)
        else:
            member_forces = _ordered_values(force_values)
            force_densities = _ordered_values(density_values)
        reactions = _ordered_values(get_any(
            backend_result,
            ("support_reactions_by_form", "support_reactions", "reactions"),
            (),
        ))
        loads = _ordered_values(get_any(
            backend_result,
            ("effective_form_loads", "loads"),
            (),
        ))
        residuals = ()

    diagnostics = _diagnostics_from_session(backend_result, solver)
    topology_ref = get_any(topology, ("topology",), topology)
    return make_contract(
        "SolvedCase",
        solver=solver,
        solver_kind=solver,
        topology=topology_ref,
        supports=supports,
        support_set=supports,
        load_case=load_case,
        config=config,
        session=backend_result,
        backend_result=backend_result,
        vertices=vertices,
        edges=edges,
        member_forces=member_forces,
        force_densities=force_densities,
        reactions=reactions,
        loads=loads,
        residuals=residuals,
        diagnostics=_diagnostic_contracts(diagnostics),
        report=str(get_any(backend_result, ("report",), "{} solve complete.".format(solver.upper()))),
        mappings={
            "source_edges": edges,
            "solver_edge_keys": solver_edge_keys,
            "resolved_support_ids": tuple(
                int(value)
                for value in get_any(
                    backend_result,
                    ("fixed", "support_keys"),
                    (),
                ) or ()
            ),
            "registered_source_edges": get_any(
                backend_result,
                ("source_edges",),
                (),
            ),
            "source_to_form": dict(
                get_any(backend_result, ("source_to_form",), {})
            ),
        },
        metadata={
            "backend_type": type(backend_result).__name__,
            "raw_diagnostics": diagnostics,
        },
    )


def _injected_solve(
    backend: Any,
    *,
    topology: Any,
    supports: Any,
    load_case: Any,
    config: Any,
    height_control: Any = None,
    prepared: Any = None,
) -> Any:
    try:
        values = dict(
            topology=topology,
            supports=supports,
            load_case=load_case,
            config=config,
            height_control=height_control,
        )
        if prepared is not None:
            values["prepared"] = prepared
        return backend(**values)
    except TypeError:
        # A deliberately small compatibility path for four-argument test or
        # application callbacks that predate HeightControl.
        if height_control is None:
            return backend(topology, supports, load_case, config)
        return backend(topology, supports, load_case, height_control, config)


@friendly("FD Solve")
def solve_fd(
    topology: Any,
    supports: Any,
    load_case: Any,
    config: Any = None,
    *,
    backend: Any = None,
) -> Any:
    """Solve one topology's edge network and return one ``SolvedCase``.

    A faced topology is accepted because force-density form finding uses its
    registered vertices and edges; registered faces remain available as
    provenance but do not enter the FD equations.
    """

    kind, vertices, edges, _ = _topology_data(topology)
    if kind not in (
        "line",
        "fd",
        "network",
        "faced",
        "mesh",
        "tna",
        "thrust",
    ):
        raise AdapterError("FD Solve requires a registered edge TopologyBundle.")
    fixed = _support_ids(topology, supports)
    load_records = _load_records(topology, load_case)

    if callable(backend):
        try:
            session = _injected_solve(
                backend,
                topology=topology,
                supports=supports,
                load_case=load_case,
                config=config,
            )
        except Exception as error:
            raise AdapterError("Injected FD backend failed: {}".format(error)) from error
    else:
        module = import_backend(
            backend,
            candidates=_FD_BACKENDS,
            purpose="FD Solve",
        )
        source_lines = get_any(topology, ("source_lines",), ())
        if not source_lines:
            source_lines = tuple(
                (vertices[int(u)], vertices[int(v)]) for u, v in edges
            )
        topology_metadata = get_any(topology, ("metadata",), {})
        tolerance = float(topology_metadata.get("weld_tolerance", 1e-6))
        try:
            problem = call_backend(
                module,
                "register_fd_network",
                source_lines,
                tolerance=tolerance,
            )
            loads = [[0.0, 0.0, 0.0] for _ in vertices]
            for node, vector in load_records:
                loads[node] = list(vector)
            force_density = get_any(
                config,
                ("force_densities", "force_density", "q"),
                1.0,
            ) if config is not None else 1.0
            session = call_backend(
                module,
                "solve_fd_problem",
                problem,
                fixed=fixed,
                forcedensities=force_density,
                loads=loads,
            )
        except Exception as error:
            raise AdapterError("COMPAS FD backend failed: {}".format(error)) from error

    return _solved_case(
        solver="fd",
        topology=topology,
        supports=supports,
        load_case=load_case,
        config=config,
        backend_result=session,
    )


def _tna_pz(
    topology: Any,
    load_case: Any,
    *,
    vertices_override: Any = None,
    faces_override: Any = None,
    nodal_only: bool = False,
) -> Any:
    records = _load_records(
        topology,
        load_case,
        vertices_override=vertices_override,
        faces_override=faces_override,
        nodal_only=nodal_only,
    )
    if any(abs(vector[0]) > 1e-12 or abs(vector[1]) > 1e-12 for _, vector in records):
        raise AdapterError(
            "TNA v0.1 accepts loads along analysis-plane Z only. Use FD for a "
            "general spatial load vector."
        )
    if not records:
        # No nodal load at all, said as the scalar zero the solver reads
        # rather than as an empty mapping it would have to interpret.
        return 0.0
    values = {node: float(vector[2]) for node, vector in records}
    vertex_count = (
        len(tuple(vertices_override))
        if vertices_override is not None
        else len(_topology_data(topology)[1])
    )
    if len(set(values.values())) == 1 and len(values) == vertex_count:
        return next(iter(values.values()))
    return values


def _faced_analysis_contracts(
    source_topology: Any,
    supports: Any,
    load_case: Any,
    pattern: Mapping[str, Any],
) -> tuple[Any, Any, Any]:
    """Promote a prepared line source to a faced TNA analysis topology."""
    metadata = dict(get_any(source_topology, ("metadata",), {}))
    metadata.update(
        {
            "source_topology_hash": str(
                get_any(source_topology, ("topology_hash",), "")
            ),
            "source_topology_kind": str(
                get_any(source_topology, ("kind",), "line")
            ),
            "prepared_analysis_topology": True,
        }
    )
    analysis = make_contract(
        "TopologyBundle",
        kind="faced",
        vertices=tuple(pattern["vertices"]),
        edges=tuple(pattern["edges"]),
        faces=tuple(pattern["faces"]),
        source_vertex_ids=tuple(
            get_any(source_topology, ("source_vertex_ids",), ())
        ),
        length_unit=str(get_any(source_topology, ("length_unit",), "m")),
        metadata=metadata,
    )
    analysis_supports = make_contract(
        "SupportSet",
        topology_hash=analysis.topology_hash,
        mode="explicit",
        node_ids=tuple(get_any(supports, ("node_ids", "keys"), ())),
        snap_tolerance=get_any(supports, ("snap_tolerance",), None),
        metadata=dict(get_any(supports, ("metadata",), {})),
    )
    analysis_load = make_contract(
        "LoadCase",
        topology_hash=analysis.topology_hash,
        name=str(get_any(load_case, ("name",), "equilibrium")),
        distribution=str(get_any(load_case, ("distribution",), "point")),
        points=tuple(get_any(load_case, ("points",), ())),
        node_ids=tuple(get_any(load_case, ("node_ids",), ())),
        vectors=tuple(get_any(load_case, ("vectors",), ())),
        records=tuple(get_any(load_case, ("records",), ())),
        base_vector=get_any(load_case, ("base_vector",), None),
        factor=float(get_any(load_case, ("factor",), 1.0)),
        coordinate_system=str(
            get_any(load_case, ("coordinate_system",), "world")
        ),
        metadata=dict(get_any(load_case, ("metadata",), {})),
    )
    return analysis, analysis_supports, analysis_load


@friendly("TNA Solve")
def solve_tna(
    topology: Any,
    supports: Any,
    load_case: Any,
    height_control: Any,
    config: Any = None,
    *,
    backend: Any = None,
) -> Any:
    """Solve a faced topology or a fully reconstructible prepared Pattern."""

    prepared = (
        topology if type(topology).__name__ == "PreparedTNA" else None
    )
    if prepared is not None:
        source_topology = get_any(prepared, ("topology",))
        supports = get_any(prepared, ("support_set", "supports"))
        pattern = dict(get_any(prepared, ("pattern",)))
        kind = "faced"
        vertices = tuple(pattern.get("vertices", ()))
        faces = tuple(pattern.get("faces", ()))
        prepared_edges = tuple(pattern.get("edges", ()))
        prepared_q = tuple(pattern.get("edge_force_densities", ()))
        fixed_ids = tuple(int(value) for value in pattern.get("fixed_node_ids", ()))
    else:
        source_topology = topology
        kind, vertices, _, faces = _topology_data(source_topology)
        prepared_edges = ()
        prepared_q = ()
        topology_metadata = get_any(source_topology, ("metadata",), {})
        fixed_ids = tuple(
            int(value)
            for value in topology_metadata.get("tna_fixed_node_ids", ())
        )
    if kind not in ("faced", "mesh", "tna", "thrust"):
        raise AdapterError("TNA Solve requires a faced TopologyBundle.")
    if not faces:
        raise AdapterError("TNA Solve requires registered faces, not isolated lines.")
    support_ids = _support_ids(source_topology, supports)
    distribution = str(
        get_any(load_case, ("distribution",), "point")
    ).lower()
    if distribution in ("tributary_area", "self_weight"):
        # RhinoVault's loading model, adopted whole by rule 2.4 of the
        # 2026-09-04 design: the self-weight is tributary area times
        # THICKNESS times DENSITY, evaluated on the surface the solve
        # produces rather than on the plan mesh. The base vector's signed
        # Z says which way that weight acts and, for a load case authored
        # before thickness and density existed, still carries its
        # magnitude: both default to 1.0, so base_vector.z x 1 x 1 is the
        # density that canvas always sent.
        base_vector = get_any(load_case, ("base_vector",), None)
        if base_vector is None:
            raise AdapterError("Surface loading requires one base vector.")
        if (
            abs(float(base_vector[0])) > 1e-12
            or abs(float(base_vector[1])) > 1e-12
        ):
            raise AdapterError(
                "TNA v0.1 accepts loads along analysis-plane Z only. Use FD "
                "for a general spatial load vector."
            )
        if abs(float(base_vector[2])) <= 1e-12:
            raise AdapterError(
                "Surface loading requires a base vector with a non-zero "
                "Z: it is the direction the self-weight acts in. Ask for "
                "no self-weight with a Thickness or a Density of zero, "
                "which both leave the weight out and keep the node loads."
            )
        surface_thickness = float(get_any(load_case, ("thickness",), 1.0))
        load_density = float(base_vector[2]) * float(
            get_any(load_case, ("density",), 1.0)
        )
        # RULE 2.4(b). The nodal point loads used to be ZEROED here
        # whenever a surface load was wired, so a canvas could carry the
        # self-weight or its point loads but never both. They now ride
        # BESIDE the self-weight, additive, exactly RhinoVault's pz +
        # pzext split. Nodal only: the surface half is not a plan-area
        # load here, it is evaluated on the solved geometry in the worker.
        pz = _tna_pz(
            source_topology,
            load_case,
            vertices_override=vertices if prepared is not None else None,
            faces_override=faces if prepared is not None else None,
            nodal_only=True,
        )
        # A THICKNESS OR A DENSITY OF ZERO IS NO SELF-WEIGHT, not a
        # refusal. Both contracts accept zero on either port
        # (SpineComponents.cs and ContractDtos.cs), the worker already
        # reads a "t" of nought as a caller asking for no weight, and the
        # FD path returns all-zero records for it, so refusing here was
        # the only reading of the three and it took the canvas's point
        # loads down with it. Density zero is how the worker is told
        # there is no weight: it turns selfweight_active off, so the
        # solve reports the node loads alone and ships no self-weight
        # diagnostics for a weight nobody asked for.
        if abs(load_density * surface_thickness) <= 1e-12:
            load_density = 0.0
            if not pz:
                raise AdapterError(
                    "A Thickness or a Density of zero asks for no "
                    "self-weight, and this load case carries no node "
                    "loads either, so there is nothing to solve. Give a "
                    "non-zero thickness and density, or wire the node "
                    "loads the solve should carry."
                )
    else:
        load_density = 0.0
        surface_thickness = 1.0
        pz = _tna_pz(
            source_topology,
            load_case,
            vertices_override=vertices if prepared is not None else None,
            faces_override=faces if prepared is not None else None,
        )
    result_topology = source_topology
    result_supports = supports
    result_load_case = load_case
    if prepared is not None and str(
        get_any(source_topology, ("kind",), "")
    ).lower() == "line":
        (
            result_topology,
            result_supports,
            result_load_case,
        ) = _faced_analysis_contracts(
            source_topology,
            supports,
            load_case,
            pattern,
        )

    if callable(backend):
        try:
            session = _injected_solve(
                backend,
                topology=result_topology,
                supports=result_supports,
                load_case=result_load_case,
                height_control=height_control,
                config=config,
                prepared=prepared,
            )
        except Exception as error:
            raise AdapterError("Injected TNA backend failed: {}".format(error)) from error
    else:
        module = import_backend(
            backend,
            candidates=_TNA_BACKENDS,
            purpose="TNA Solve",
        )
        topology_metadata = get_any(source_topology, ("metadata",), {})
        tolerance = float(topology_metadata.get("weld_tolerance", 1e-6))
        metadata = dict(get_any(source_topology, ("metadata",), {}))
        try:
            problem = call_backend(
                module,
                "register_tna_pattern",
                vertices=vertices,
                faces=faces,
                vertex_keys=tuple(range(len(vertices))),
                tolerance=tolerance,
                metadata=metadata,
            )
            if prepared is not None:
                if len(prepared_edges) != len(prepared_q):
                    raise AdapterError(
                        "Prepared Pattern q values do not align with its edges."
                    )
                actual_edges = {
                    tuple(sorted((int(u), int(v)))): (int(u), int(v))
                    for u, v in problem.form.edges()
                }
                for edge, q_value in zip(prepared_edges, prepared_q):
                    key = tuple(sorted((int(edge[0]), int(edge[1]))))
                    registered = actual_edges.get(key)
                    if registered is None:
                        raise AdapterError(
                            "Prepared Pattern edge {} was lost during "
                            "reconstruction.".format(tuple(edge))
                        )
                    problem.form.edge_attribute(
                        registered, "q", float(q_value)
                    )
            height_mode = str(
                get_any(height_control, ("mode",), "zmax")
            ).lower()
            height_value = get_any(
                height_control,
                ("value", "height", "zmax", "force_scale", "q_scale"),
                None,
            )
            if height_mode in ("q", "force_scale"):
                vertical_mode = "q"
            elif (
                height_mode in ("natural", "auto", "equilibrium")
                or height_value is None
            ):
                vertical_mode = "natural"
            else:
                vertical_mode = "zmax"
            horizontal_iterations = (
                get_any(
                    config,
                    ("horizontal_iterations", "horizontal_kmax"),
                    None,
                )
                if config is not None
                else None
            )
            solve_kwargs = {
                "support_mode": "keys",
                "support_keys": support_ids,
                "fixed_keys": fixed_ids,
                "pz": pz,
                "vertical_mode": vertical_mode,
                "zmax": (
                    float(height_value)
                    if vertical_mode == "zmax"
                    else None
                ),
                "q_scale": (
                    float(height_value)
                    if vertical_mode == "q" and height_value is not None
                    else -1.0
                ),
                "density": load_density,
                # Rule 2.4(a): RhinoVault's per-vertex "t". One scalar for
                # now, and the seam a per-vertex thickness arrives on.
                "thickness": surface_thickness,
                "horizontal_alpha": float(
                    get_any(config, ("horizontal_alpha", "alpha"), 100.0)
                ) if config is not None else 100.0,
                "horizontal_kmax": (
                    None
                    if horizontal_iterations is None
                    else int(horizontal_iterations)
                ),
                "horizontal_method": str(
                    get_any(config, ("horizontal_method",), "iterative")
                ) if config is not None else "iterative",
                "vertical_kmax": int(
                    get_any(config, ("vertical_iterations", "vertical_kmax"), 100)
                ) if config is not None else 100,
                "vertical_tolerance": float(
                    get_any(config, ("tolerance", "vertical_tolerance"), 1e-3)
                ) if config is not None else 1e-3,
            }
            session = call_backend(
                module,
                "solve_tna_problem",
                problem,
                **solve_kwargs,
            )
        except Exception as error:
            raise AdapterError("COMPAS TNA backend failed: {}".format(error)) from error

    return _solved_case(
        solver="tna",
        topology=result_topology,
        supports=result_supports,
        load_case=result_load_case,
        config=config,
        backend_result=session,
    )


fd_solve = solve_fd
tna_solve = solve_tna
