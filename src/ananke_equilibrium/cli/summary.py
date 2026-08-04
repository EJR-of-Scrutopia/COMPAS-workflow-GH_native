"""Describe a solved result in terms a structural engineer can check.

The centrepiece is the global equilibrium residual: the vector sum of every
applied load and every support reaction. For a converged funicular it is
zero to solver tolerance, and printing it means the bench states a checkable
claim rather than asserting that the solve "worked".

Every force quantity reported here is an equilibrium demand. None of it is a
member capacity, and none of it constitutes a verified structure.
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple

from .results import diagram
from .results import force_states
from .results import loads
from .results import member_forces
from .results import reactions
from .results import solver_name
from .results import thrust_faces
from .results import thrust_vertices


def _extent(points: Sequence[Sequence[float]], axis: int) -> Tuple[float, float]:
    values = [float(point[axis]) for point in points if len(point) > axis]
    if not values:
        return (0.0, 0.0)
    return (min(values), max(values))


def _vector_sum(vectors: Sequence[Sequence[float]]) -> List[float]:
    total = [0.0, 0.0, 0.0]
    for vector in vectors:
        for axis in range(min(3, len(vector))):
            total[axis] += float(vector[axis])
    return total


def _magnitude(vector: Sequence[float]) -> float:
    return sum(float(value) ** 2 for value in vector) ** 0.5


def summarise(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the structural summary of one solved result."""

    vertices = thrust_vertices(result)
    faces = thrust_faces(result)
    forces = member_forces(result)
    applied = loads(result)
    supports = reactions(result)
    states = force_states(result)

    load_total = _vector_sum(applied)
    reaction_total = _vector_sum([record["vector"] for record in supports])
    residual = [load_total[i] + reaction_total[i] for i in range(3)]

    x_min, x_max = _extent(vertices, 0)
    y_min, y_max = _extent(vertices, 1)
    z_min, z_max = _extent(vertices, 2)

    compression = sum(1 for state in states if state.lower().startswith("comp"))
    tension = sum(1 for state in states if state.lower().startswith("tens"))
    if not states and forces:
        compression = sum(1 for value in forces if value < 0.0)
        tension = sum(1 for value in forces if value > 0.0)

    form = diagram(result, "form_graph")
    force = diagram(result, "force_graph")

    return {
        "solver": solver_name(result),
        "schema": result.get("resultSchema") or result.get("schema_version"),
        "report": result.get("report"),
        "geometry": {
            "vertices": len(vertices),
            "faces": len(faces),
            "span_x": x_max - x_min,
            "span_y": y_max - y_min,
            "rise": z_max - z_min,
            "z_min": z_min,
            "z_max": z_max,
        },
        "forces": {
            "members": len(forces),
            "compression": compression,
            "tension": tension,
            "min": min(forces) if forces else None,
            "max": max(forces) if forces else None,
        },
        "actions": {
            "loaded_nodes": len(applied),
            "supports": len(supports),
            "load_total": load_total,
            "reaction_total": reaction_total,
            "residual": residual,
            "residual_magnitude": _magnitude(residual),
        },
        "diagrams": {
            "form_vertices": len(form["vertices"]) if form else 0,
            "form_edges": len(form["edges"]) if form else 0,
            "force_vertices": len(force["vertices"]) if force else 0,
            "force_edges": len(force["edges"]) if force else 0,
        },
    }


def _fmt(value: Optional[float], places: int = 4) -> str:
    if value is None:
        return "not reported"
    return "{:.{}f}".format(float(value), places)


def format_summary(summary: Mapping[str, Any], tolerance: float = 1e-6) -> str:
    """Render the summary as a terminal report."""

    geometry = summary["geometry"]
    forces = summary["forces"]
    actions = summary["actions"]
    diagrams = summary["diagrams"]

    lines = []
    lines.append(
        "solver {}   schema {}".format(summary["solver"], summary["schema"])
    )
    if summary.get("report"):
        lines.append(str(summary["report"]))
    lines.append("")

    lines.append("geometry")
    lines.append("  vertices          {}".format(geometry["vertices"]))
    lines.append("  faces             {}".format(geometry["faces"]))
    lines.append(
        "  span              {} x {}".format(
            _fmt(geometry["span_x"], 3),
            _fmt(geometry["span_y"], 3),
        )
    )
    lines.append("  rise              {}".format(_fmt(geometry["rise"], 3)))
    lines.append(
        "  rise / span       {}".format(
            _fmt(
                geometry["rise"] / geometry["span_x"]
                if geometry["span_x"]
                else None,
                4,
            )
        )
    )
    lines.append("")

    lines.append("member forces (equilibrium demands, not capacities)")
    lines.append("  members           {}".format(forces["members"]))
    lines.append("  compression       {}".format(forces["compression"]))
    lines.append("  tension           {}".format(forces["tension"]))
    lines.append(
        "  range             {} to {}".format(
            _fmt(forces["min"]),
            _fmt(forces["max"]),
        )
    )
    lines.append("")

    lines.append("actions")
    lines.append("  loaded nodes      {}".format(actions["loaded_nodes"]))
    lines.append("  supports          {}".format(actions["supports"]))
    lines.append(
        "  applied load      [{}]".format(
            ", ".join(_fmt(value) for value in actions["load_total"])
        )
    )
    lines.append(
        "  total reaction    [{}]".format(
            ", ".join(_fmt(value) for value in actions["reaction_total"])
        )
    )
    lines.append("")

    magnitude = actions["residual_magnitude"]
    balanced = magnitude <= tolerance
    lines.append("global equilibrium check")
    lines.append(
        "  residual          [{}]".format(
            ", ".join(_fmt(value) for value in actions["residual"])
        )
    )
    lines.append("  magnitude         {}".format(_fmt(magnitude, 3 + 9)))
    lines.append(
        "  verdict           {} (tolerance {})".format(
            "BALANCED" if balanced else "NOT BALANCED",
            tolerance,
        )
    )
    lines.append("")

    lines.append("reciprocal diagrams")
    lines.append(
        "  form              {} vertices, {} edges".format(
            diagrams["form_vertices"],
            diagrams["form_edges"],
        )
    )
    lines.append(
        "  force             {} vertices, {} edges".format(
            diagrams["force_vertices"],
            diagrams["force_edges"],
        )
    )
    return "\n".join(lines)


def is_balanced(summary: Mapping[str, Any], tolerance: float = 1e-6) -> bool:
    """Return whether the global load and reaction sums cancel."""

    return float(summary["actions"]["residual_magnitude"]) <= tolerance


__all__ = ["format_summary", "is_balanced", "summarise"]
