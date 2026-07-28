"""Display-style and host-independent preview payload adapters."""

from __future__ import annotations

from dataclasses import fields
from dataclasses import is_dataclass
from dataclasses import replace
from typing import Any
from typing import Mapping

from ._base import AdapterError
from ._base import contract_type
from ._base import friendly
from ._base import get_any
from ._base import make_contract


@friendly("Diagram Style")
def make_diagram_style(
    preset: str = "analysis",
    **overrides: Any
) -> Any:
    """Create one reusable style object from a named preset."""

    style_type = contract_type("DiagramStyle")
    factory = getattr(style_type, "from_preset", None)
    if callable(factory):
        style = factory(str(preset or "analysis"))
    else:
        style = make_contract("DiagramStyle", preset=str(preset or "analysis"))

    clean = {key: value for key, value in overrides.items() if value is not None}
    if not clean:
        return style
    if is_dataclass(style):
        allowed = {item.name for item in fields(style)}
        unknown = sorted(set(clean) - allowed)
        if unknown:
            raise AdapterError(
                "Unknown DiagramStyle override(s): {}.".format(", ".join(unknown))
            )
        return replace(style, **clean)
    for key, value in clean.items():
        if not hasattr(style, key):
            raise AdapterError("Unknown DiagramStyle override: {}.".format(key))
        setattr(style, key, value)
    return style


def _style_data(style: Any) -> Mapping[str, Any]:
    if style is None:
        return {}
    serialise = getattr(style, "to_data", None)
    if callable(serialise):
        return serialise()
    if is_dataclass(style):
        return {item.name: getattr(style, item.name) for item in fields(style)}
    return {"preset": str(getattr(style, "preset", "analysis"))}


@friendly("Preview Payload")
def build_preview_payload(
    solved_case: Any,
    style: Any = None,
    layout: Mapping[str, Any] = None,
    *,
    kind: str = "form",
    dimension: int = 3,
) -> Any:
    """Build renderer-neutral line primitives for Rhino preview components.

    RhinoCommon drawing is intentionally outside this module.  A future SDK
    component can consume the returned ``DiagramBundle`` in
    ``DrawViewportWires`` without forcing a solver recompute.
    """

    if solved_case is None:
        raise AdapterError("Connect a SolvedCase.")
    topology = get_any(solved_case, ("topology",))
    vertices = tuple(get_any(solved_case, ("equilibrium_vertices",), ()))
    mappings = dict(get_any(solved_case, ("mappings",), {}))
    edges = tuple(mappings.get("source_edges", ()))
    forces = tuple(get_any(solved_case, ("member_forces",), ()))
    if not vertices:
        raise AdapterError("The SolvedCase contains no equilibrium vertices.")
    if not edges:
        raise AdapterError(
            "The SolvedCase contains no source-edge mapping for preview."
        )

    primitives = []
    for index, edge in enumerate(edges):
        u, v = (int(edge[0]), int(edge[1]))
        if min(u, v) < 0 or max(u, v) >= len(vertices):
            raise AdapterError("Preview edge {} has an invalid node ID.".format(index))
        magnitude = float(forces[index]) if index < len(forces) else None
        primitives.append(
            make_contract(
                "DiagramPrimitive",
                role="form_member",
                geometry_type="line",
                points=(vertices[u], vertices[v]),
                source_ids=(index,),
                magnitude=magnitude,
                label="",
                metadata={
                    "force_state": (
                        "tension"
                        if magnitude is not None and magnitude > 0.0
                        else "compression"
                        if magnitude is not None and magnitude < 0.0
                        else "neutral"
                    )
                },
            )
        )

    return make_contract(
        "DiagramBundle",
        topology=topology,
        kind=str(kind or "form"),
        dimension=int(dimension),
        primitives=tuple(primitives),
        diagnostics=tuple(get_any(solved_case, ("diagnostics",), ())),
        mappings={"primitive_to_member": tuple(range(len(primitives)))},
        metadata={
            "style": dict(_style_data(style)),
            "layout": dict(layout or {}),
        },
    )


diagram_style = make_diagram_style
preview_payload = build_preview_payload
