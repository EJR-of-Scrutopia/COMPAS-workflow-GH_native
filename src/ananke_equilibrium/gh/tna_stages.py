"""Rhino-independent adapters for the staged RhinoVault-style TNA workflow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._base import AdapterError
from ._base import call_backend
from ._base import friendly
from ._base import get_any
from ._base import import_backend
from ._base import make_contract
from .solvers import _diagnostic_contracts
from .solvers import _support_ids
from .solvers import _topology_data


_TNA_BACKENDS = (
    "tree_forest_compas.tna",
    "tree_forest_compas",
)


def _register_problem(module: Any, topology: Any, tolerance: float) -> Any:
    kind, vertices, edges, faces = _topology_data(topology)
    metadata = dict(get_any(topology, ("metadata",), {}))
    if kind in ("faced", "mesh", "tna", "thrust"):
        return call_backend(
            module,
            "register_tna_pattern",
            vertices=vertices,
            faces=faces,
            vertex_keys=tuple(range(len(vertices))),
            tolerance=tolerance,
            metadata=metadata,
        )
    if kind in ("line", "network", "fd"):
        lines = tuple(
            (vertices[int(u)], vertices[int(v)]) for u, v in edges
        )
        return call_backend(
            module,
            "register_tna_pattern",
            lines=lines,
            tolerance=tolerance,
            metadata=metadata,
        )
    raise AdapterError(
        "TNA Prepare requires a faced topology or a planar line pattern "
        "containing closed faces."
    )


def _source_topology_maps(problem: Any, topology: Any) -> tuple[dict[Any, int], dict[int, Any]]:
    """Map backend source keys to stable TopologyBundle node IDs."""
    kind, vertices, edges, _ = _topology_data(topology)
    if kind in ("faced", "mesh", "tna", "thrust"):
        source_to_topology = {
            source_key: int(source_key)
            for source_key in get_any(problem, ("source_vertex_order",), ())
        }
    else:
        source_to_topology = {}
        endpoint_to_source = dict(
            get_any(problem, ("endpoint_to_source",), {})
        )
        for edge_id, (u, v) in enumerate(edges):
            for endpoint, topology_id in ((0, int(u)), (1, int(v))):
                source_key = endpoint_to_source.get((edge_id, endpoint))
                if source_key is None:
                    raise AdapterError(
                        "The line registrar omitted endpoint {} of edge {}.".format(
                            endpoint, edge_id
                        )
                    )
                previous = source_to_topology.setdefault(source_key, topology_id)
                if previous != topology_id:
                    raise AdapterError(
                        "Line welding merged two distinct registered topology nodes."
                    )
    if len(source_to_topology) != len(vertices):
        raise AdapterError(
            "Prepared Pattern nodes do not align one-to-one with the registered "
            "topology. Increase registration precision or weld the input once "
            "in the Pattern component."
        )
    topology_to_source = {
        topology_id: source_key
        for source_key, topology_id in source_to_topology.items()
    }
    return source_to_topology, topology_to_source


def _form_topology_id(
    problem: Any,
    form_key: Any,
    source_to_topology: Mapping[Any, int],
) -> int:
    sources = tuple(
        get_any(problem, ("form_to_sources",), {}).get(form_key, ())
    )
    for source in sources:
        if source in source_to_topology:
            return int(source_to_topology[source])
    raise AdapterError(
        "Prepared form vertex {!r} has no stable source topology node.".format(
            form_key
        )
    )


def _prepared_pattern_data(
    preparation: Any,
    topology: Any,
    source_to_topology: Mapping[Any, int],
    fixed_node_ids: tuple[int, ...],
) -> dict[str, Any]:
    problem = get_any(preparation, ("problem",))
    pattern = get_any(preparation, ("pattern",))
    vertices = [tuple(point) for point in _topology_data(topology)[1]]
    source_to_form = dict(get_any(problem, ("source_to_form",), {}))
    for source_key, topology_id in source_to_topology.items():
        form_key = source_to_form[source_key]
        vertices[topology_id] = tuple(
            float(value) for value in pattern.vertex_coordinates(form_key)
        )

    topology_to_source = {
        topology_id: source_key
        for source_key, topology_id in source_to_topology.items()
    }
    # Keep the source TopologyBundle edge order. Native topology validation and
    # all downstream source-edge mappings depend on this deterministic order.
    # The line registrar rejects dangling lines, so every source edge is part
    # of the faced Pattern.
    edges = [
        (int(u), int(v)) for u, v in _topology_data(topology)[2]
    ]
    actual_pattern_edges = {
        tuple(sorted((int(u), int(v)))): (int(u), int(v))
        for u, v in pattern.edges()
    }
    force_densities = []
    for u, v in edges:
        form_u = source_to_form[topology_to_source[u]]
        form_v = source_to_form[topology_to_source[v]]
        registered = actual_pattern_edges.get(
            tuple(sorted((int(form_u), int(form_v))))
        )
        if registered is None:
            raise AdapterError(
                "Source topology edge ({}, {}) is not part of the prepared "
                "faced Pattern.".format(u, v)
            )
        force_densities.append(
            float(pattern.edge_attribute(registered, "q"))
        )
    faces = []
    for face in pattern.faces():
        faces.append(
            tuple(
                _form_topology_id(problem, key, source_to_topology)
                for key in pattern.face_vertices(face)
            )
        )
    return {
        "kind": "faced",
        "vertices": tuple(vertices),
        "edges": tuple(edges),
        "faces": tuple(faces),
        "edge_force_densities": tuple(force_densities),
        "fixed_node_ids": tuple(fixed_node_ids),
    }


def _boundary_records(
    preparation: Any,
    topology: Any,
    problem: Any,
    source_to_topology: Mapping[Any, int],
) -> tuple[dict[str, Any], ...]:
    source_ids = tuple(
        get_any(topology, ("source_vertex_ids",), ())
    )
    output = []
    for segment in get_any(preparation, ("boundary_segments",), ()):
        node_ids = tuple(
            _form_topology_id(problem, key, source_to_topology)
            for key in segment.form_vertex_keys
        )
        output.append(
            {
                "boundary_index": int(segment.boundary_index),
                "segment_index": int(segment.segment_index),
                "node_ids": node_ids,
                "source_vertex_ids": tuple(
                    source_ids[node] if node < len(source_ids) else node
                    for node in node_ids
                ),
                "target_sag": segment.target_sag,
                "initial_sag": float(segment.initial_sag),
                "actual_sag": float(segment.actual_sag),
                "sag_error": (
                    abs(float(segment.actual_sag) - float(segment.target_sag))
                    if segment.target_sag is not None
                    else 0.0
                ),
            }
        )
    return tuple(output)


@friendly("TNA Prepare")
def prepare_tna(
    topology: Any,
    supports: Any,
    settings: Any,
    *,
    backend: Any = None,
) -> Any:
    """Relax a Pattern, match unsupported-boundary sag, and create its dual."""
    if type(settings).__name__ != "TNAPrepareConfig":
        settings = make_contract(
            "TNAPrepareConfig",
            force_density=get_any(settings, ("force_density",), 1.0),
            relax=get_any(settings, ("relax",), True),
            boundary_sag=get_any(settings, ("boundary_sag",), 0.10),
            sag_iterations=get_any(settings, ("sag_iterations",), 10),
            sag_tolerance=get_any(settings, ("sag_tolerance",), 0.01),
            fixed_node_ids=tuple(
                get_any(settings, ("fixed_node_ids",), ())
            ),
            metadata=dict(get_any(settings, ("metadata",), {})),
        )
    source_topology = get_any(topology, ("topology",), topology)
    support_ids = _support_ids(source_topology, supports)
    kind, vertices, _, _ = _topology_data(source_topology)
    fixed_ids = tuple(
        int(value)
        for value in get_any(settings, ("fixed_node_ids",), ())
    )
    if fixed_ids and (min(fixed_ids) < 0 or max(fixed_ids) >= len(vertices)):
        raise AdapterError("A fixed plan node ID lies outside the topology.")

    module = import_backend(
        backend,
        candidates=_TNA_BACKENDS,
        purpose="TNA Prepare",
    )
    topology_metadata = get_any(source_topology, ("metadata",), {})
    tolerance = float(topology_metadata.get("weld_tolerance", 1e-6))
    problem = _register_problem(module, source_topology, tolerance)
    source_to_topology, topology_to_source = _source_topology_maps(
        problem, source_topology
    )
    support_source_keys = tuple(
        topology_to_source[node] for node in support_ids
    )
    fixed_source_keys = tuple(
        topology_to_source[node] for node in fixed_ids
    )
    preparation = call_backend(
        module,
        "prepare_tna_problem",
        problem,
        support_mode="keys",
        support_keys=support_source_keys,
        fixed_keys=fixed_source_keys,
        force_density=float(get_any(settings, ("force_density",), 1.0)),
        relax=bool(get_any(settings, ("relax",), True)),
        boundary_sag=get_any(settings, ("boundary_sag",), 0.10),
        sag_iterations=int(get_any(settings, ("sag_iterations",), 10)),
        sag_tolerance=float(get_any(settings, ("sag_tolerance",), 0.01)),
    )

    rebound_supports = make_contract(
        "SupportSet",
        topology_hash=str(get_any(source_topology, ("topology_hash",), "")),
        mode="explicit",
        node_ids=tuple(support_ids),
        metadata={
            "source_mode": str(get_any(supports, ("mode",), "explicit")),
            "prepared": True,
        },
    )
    pattern = _prepared_pattern_data(
        preparation,
        source_topology,
        source_to_topology,
        fixed_ids,
    )
    boundaries = _boundary_records(
        preparation,
        source_topology,
        problem,
        source_to_topology,
    )
    diagnostics = dict(get_any(preparation, ("diagnostics",), {}))
    diagnostic_contracts = list(_diagnostic_contracts(diagnostics))
    boundary_warning = str(
        diagnostics.get("boundary_condition_warning", "") or ""
    )
    if boundary_warning:
        diagnostic_contracts.append(
            make_contract(
                "Diagnostic",
                code="tna.boundary_supports",
                severity="warning",
                message=boundary_warning,
                value=float(
                    diagnostics.get("boundary_support_count", 0)
                ),
                context={
                    "boundary_vertex_count": int(
                        diagnostics.get("boundary_vertex_count", 0)
                    ),
                    "held_boundary_edge_count": int(
                        diagnostics.get("held_boundary_edge_count", 0)
                    ),
                },
            )
        )
    report = (
        "TNA Pattern prepared\n"
        "Source: {} topology; nodes/edges/faces: {}/{}/{}\n"
        "Supports/plan pins: {}/{}\n"
        "Unsupported boundary segments: {}; maximum sag error: {:.6g}\n"
        "Initial Form and topological-dual Force diagrams created; "
        "horizontal equilibrium has not run."
    ).format(
        kind,
        len(pattern["vertices"]),
        len(pattern["edges"]),
        len(pattern["faces"]),
        len(support_ids),
        len(fixed_ids),
        len(boundaries),
        float(diagnostics.get("max_boundary_sag_error", 0.0)),
    )
    if boundary_warning:
        report += "\nBoundary warning: {}".format(boundary_warning)
    return make_contract(
        "PreparedTNA",
        topology=source_topology,
        support_set=rebound_supports,
        config=settings,
        pattern=pattern,
        session=preparation,
        boundary_segments=boundaries,
        diagnostics=tuple(diagnostic_contracts),
        mappings={
            "pattern_vertex_to_topology_vertex": tuple(
                range(len(pattern["vertices"]))
            ),
            "source_edge_to_pattern_edge": tuple(
                {
                    "source_edge_id": edge_id,
                    "pattern_edge_id": edge_id,
                    "u": int(edge[0]),
                    "v": int(edge[1]),
                }
                for edge_id, edge in enumerate(pattern["edges"])
            ),
            "backend_source_to_topology_vertex": tuple(
                {
                    "source_key": source_key,
                    "topology_vertex_id": topology_id,
                }
                for source_key, topology_id in sorted(
                    source_to_topology.items(),
                    key=lambda item: item[1],
                )
            ),
            "support_node_ids": tuple(support_ids),
            "fixed_plan_node_ids": tuple(fixed_ids),
        },
        report=report,
        metadata={
            "source_topology_hash": str(
                get_any(source_topology, ("topology_hash",), "")
            ),
            "pattern_source_kind": kind,
            "raw_diagnostics": diagnostics,
        },
    )


tna_prepare = prepare_tna
