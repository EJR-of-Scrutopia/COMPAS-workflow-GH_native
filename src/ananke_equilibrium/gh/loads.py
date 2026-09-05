"""Support-set and load-case component adapters."""

from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Optional

from ._base import AdapterError
from ._base import finite_float
from ._base import friendly
from ._base import get_any
from ._base import items
from ._base import make_contract
from ._base import point3
from ._base import vector3


@friendly("Support Set")
def build_support_set(
    points: Any = None,
    node_ids: Any = None,
    *,
    topology: Any = None,
    mode: str = "explicit",
    snap_tolerance: Optional[float] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Bundle support selection separately from either equilibrium solver."""

    clean_points = tuple(
        point3(value, "Support point {}".format(index))
        for index, value in enumerate(items(points))
    )
    clean_ids = tuple(int(value) for value in items(node_ids))
    if clean_points and clean_ids:
        raise AdapterError("Use support points or node IDs, not both.")
    if any(value < 0 for value in clean_ids):
        raise AdapterError("Support node IDs must be zero or greater.")

    normalised_mode = str(mode or "explicit").strip().lower().replace(" ", "_")
    aliases = {
        "all_boundary": "boundary",
        "boundary_corners": "corners",
        "ids": "explicit",
        "points": "explicit",
    }
    normalised_mode = aliases.get(normalised_mode, normalised_mode)
    if normalised_mode not in ("explicit", "boundary", "corners", "terminals"):
        raise AdapterError(
            "Support mode must be Explicit, Boundary, Corners, or Terminals."
        )
    if normalised_mode == "explicit" and not (clean_points or clean_ids):
        raise AdapterError(
            "Explicit support mode requires support points or node IDs."
        )

    snap = (
        finite_float(snap_tolerance, "Snap tolerance", positive=True)
        if snap_tolerance is not None
        else None
    )
    return make_contract(
        "SupportSet",
        topology_hash=(
            str(get_any(topology, ("topology_hash",), ""))
            if topology is not None
            else ""
        ),
        mode=normalised_mode,
        points=clean_points,
        node_ids=clean_ids,
        snap_tolerance=snap,
        metadata=dict(metadata or {}),
    )


@friendly("Load Case")
def build_load_case(
    vectors: Any = None,
    *,
    points: Any = None,
    node_ids: Any = None,
    topology: Any = None,
    distribution: str = "point",
    name: str = "equilibrium",
    factor: float = 1.0,
    thickness: float = 1.0,
    density: float = 1.0,
    coordinate_system: str = "world",
    metadata: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Bundle a named set of load records.

    One vector broadcasts to every target.  ``uniform_nodes``,
    ``tributary_area`` and ``self_weight`` may be target-free; the solver
    resolves those distributions against the supplied topology.

    ``thickness`` and ``density`` are RhinoVault's selfweight pair (rule
    2.4(a) of the 2026-09-04 design): a surface load weighs tributary area
    times thickness times density, and both default to 1.0 so that a call
    written before they existed keeps the weight its base vector gave it.
    """

    clean_points = tuple(
        point3(value, "Load point {}".format(index))
        for index, value in enumerate(items(points))
    )
    clean_ids = tuple(int(value) for value in items(node_ids))
    if clean_points and clean_ids:
        raise AdapterError("Use load points or node IDs, not both.")
    if any(value < 0 for value in clean_ids):
        raise AdapterError("Load node IDs must be zero or greater.")

    clean_vectors = tuple(
        vector3(value, "Load vector {}".format(index))
        for index, value in enumerate(items(vectors))
    )
    normalised_distribution = (
        str(distribution or "point").strip().lower().replace(" ", "_")
    )
    aliases = {
        "points": "point",
        "uniform": "uniform_nodes",
        "nodes": "uniform_nodes",
        "area": "tributary_area",
        "tributary": "tributary_area",
        "selfweight": "self_weight",
    }
    normalised_distribution = aliases.get(
        normalised_distribution,
        normalised_distribution,
    )
    permitted = {
        "point",
        "uniform_nodes",
        "tributary_area",
        "self_weight",
        "custom",
    }
    if normalised_distribution not in permitted:
        raise AdapterError(
            "Load distribution must be Point, Uniform Nodes, Tributary Area, "
            "Self Weight, or Custom."
        )

    target_count = len(clean_ids) or len(clean_points)
    if normalised_distribution in ("point", "custom") and target_count == 0:
        raise AdapterError(
            "{} loads require points or node IDs.".format(
                normalised_distribution.replace("_", " ").title()
            )
        )
    if not clean_vectors:
        raise AdapterError("Connect at least one load vector.")
    if target_count:
        if len(clean_vectors) == 1:
            clean_vectors = clean_vectors * target_count
        elif len(clean_vectors) != target_count:
            raise AdapterError(
                "Load vectors must contain one item or one vector per target."
            )
    elif len(clean_vectors) != 1:
        raise AdapterError(
            "A target-free load distribution accepts one base vector."
        )

    clean_factor = finite_float(factor, "Load factor")
    factored_vectors = tuple(
        tuple(clean_factor * component for component in vector)
        for vector in clean_vectors
    )
    records = tuple(
        {
            "node_id": clean_ids[index] if clean_ids else None,
            "point": clean_points[index] if clean_points else None,
            "vector": vector,
        }
        for index, vector in enumerate(factored_vectors)
    ) if target_count else ()
    return make_contract(
        "LoadCase",
        topology_hash=(
            str(get_any(topology, ("topology_hash",), ""))
            if topology is not None
            else ""
        ),
        name=str(name or "equilibrium"),
        distribution=normalised_distribution,
        points=clean_points,
        node_ids=clean_ids,
        vectors=factored_vectors,
        records=records,
        base_vector=factored_vectors[0] if not target_count else None,
        thickness=finite_float(thickness, "Load thickness"),
        density=finite_float(density, "Load density"),
        factor=clean_factor,
        coordinate_system=str(coordinate_system or "world"),
        metadata=dict(metadata or {}),
    )


support_set = build_support_set
load_case = build_load_case
