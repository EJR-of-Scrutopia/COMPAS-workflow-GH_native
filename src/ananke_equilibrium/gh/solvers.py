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


def _load_records(topology: Any, load_case: Any) -> tuple[tuple[int, tuple[float, float, float]], ...]:
    _, vertices, _, _ = _topology_data(topology)
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
    if not node_ids and distribution in (
        "uniform_nodes",
        "tributary_area",
        "self_weight",
    ):
        node_ids = tuple(range(len(vertices)))
        if base_vector is not None:
            vectors = (base_vector,)
    if not vectors:
        raise AdapterError("The load case contains no load vectors.")
    if len(vectors) == 1:
        vectors = vectors * len(node_ids)
    if len(vectors) != len(node_ids):
        raise AdapterError("Load vectors do not align with resolved load nodes.")

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
) -> Any:
    try:
        return backend(
            topology=topology,
            supports=supports,
            load_case=load_case,
            config=config,
            height_control=height_control,
        )
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


def _tna_pz(topology: Any, load_case: Any) -> Any:
    records = _load_records(topology, load_case)
    if any(abs(vector[0]) > 1e-12 or abs(vector[1]) > 1e-12 for _, vector in records):
        raise AdapterError(
            "TNA v0.1 accepts loads along analysis-plane Z only. Use FD for a "
            "general spatial load vector."
        )
    values = {node: float(vector[2]) for node, vector in records}
    if len(set(values.values())) == 1 and len(values) == len(_topology_data(topology)[1]):
        return next(iter(values.values()))
    return values


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
    """Register and solve one faced ``TopologyBundle`` as a TNA pattern."""

    kind, vertices, _, faces = _topology_data(topology)
    if kind not in ("faced", "mesh", "tna", "thrust"):
        raise AdapterError("TNA Solve requires a faced TopologyBundle.")
    if not faces:
        raise AdapterError("TNA Solve requires registered faces, not isolated lines.")
    support_ids = _support_ids(topology, supports)
    pz = _tna_pz(topology, load_case)

    if callable(backend):
        try:
            session = _injected_solve(
                backend,
                topology=topology,
                supports=supports,
                load_case=load_case,
                height_control=height_control,
                config=config,
            )
        except Exception as error:
            raise AdapterError("Injected TNA backend failed: {}".format(error)) from error
    else:
        module = import_backend(
            backend,
            candidates=_TNA_BACKENDS,
            purpose="TNA Solve",
        )
        topology_metadata = get_any(topology, ("metadata",), {})
        tolerance = float(topology_metadata.get("weld_tolerance", 1e-6))
        metadata = dict(get_any(topology, ("metadata",), {}))
        try:
            problem = call_backend(
                module,
                "register_tna_pattern",
                vertices=vertices,
                faces=faces,
                tolerance=tolerance,
                metadata=metadata,
            )
            height_mode = str(
                get_any(height_control, ("mode",), "zmax")
            ).lower()
            height_value = get_any(
                height_control,
                ("value", "height", "zmax", "force_scale", "q_scale"),
                None,
            )
            solve_kwargs = {
                "support_mode": "keys",
                "support_keys": support_ids,
                "pz": pz,
                "vertical_mode": "q" if height_mode in ("q", "force_scale") else "zmax",
                "zmax": (
                    float(height_value)
                    if height_mode not in ("q", "force_scale") and height_value is not None
                    else None
                ),
                "q_scale": (
                    float(height_value)
                    if height_mode in ("q", "force_scale") and height_value is not None
                    else -1.0
                ),
                "density": 0.0,
                "horizontal_alpha": float(
                    get_any(config, ("horizontal_alpha", "alpha"), 100.0)
                ) if config is not None else 100.0,
                "horizontal_kmax": int(
                    get_any(config, ("horizontal_iterations", "horizontal_kmax"), 100)
                ) if config is not None else 100,
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
        topology=topology,
        supports=supports,
        load_case=load_case,
        config=config,
        backend_result=session,
    )


fd_solve = solve_fd
tna_solve = solve_tna
