"""Headless form and force diagrams from a solved result.

Graphic statics is planar, so this is matplotlib rather than the 3D viewer.
The output is a committable artefact: it diffs, it drops into a document, and
it needs no display server.

Members are drawn with width proportional to axial force magnitude and
coloured by force state, which is the conventional reading: a thrust network
whose members all sit on one side of zero is a funicular, and you can see
that at a glance rather than reading a table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be selected first)

from .results import ResultError  # noqa: E402
from .results import diagram  # noqa: E402
from .results import thrust_vertices  # noqa: E402


COMPRESSION_COLOUR = "#1f4e79"
TENSION_COLOUR = "#a33a1f"
NEUTRAL_COLOUR = "#5a5a5a"
SUPPORT_COLOUR = "#000000"

MIN_WIDTH = 0.6
MAX_WIDTH = 4.0


def _edge_forces(result: Mapping[str, Any]) -> Dict[int, float]:
    """Map form-diagram edge id to axial force, where TNA reports it."""

    forces: Dict[int, float] = {}
    for state in result.get("edge_states") or []:
        if not isinstance(state, Mapping):
            continue
        edge_id = state.get("form_edge_id")
        force = state.get("axial_force")
        if edge_id is None or force is None:
            continue
        forces[int(edge_id)] = float(force)
    return forces


DEFAULT_WIDTH = (MIN_WIDTH + MAX_WIDTH) / 2.0


def _width_scale(values: Sequence[Optional[float]]) -> Any:
    """Return a function mapping one force to a line width.

    Values may be absent, because the force diagram carries no per-edge
    axial force of its own. When nothing is known, or every magnitude is the
    same, every member draws at one width.
    """

    magnitudes = [abs(value) for value in values if value is not None]
    if not magnitudes:
        return lambda value: DEFAULT_WIDTH
    low = min(magnitudes)
    high = max(magnitudes)
    if high - low < 1e-12:
        return lambda value: DEFAULT_WIDTH

    def scale(value: Optional[float]) -> float:
        if value is None:
            return DEFAULT_WIDTH
        fraction = (abs(value) - low) / (high - low)
        return MIN_WIDTH + (MAX_WIDTH - MIN_WIDTH) * fraction

    return scale


def _colour(force: Optional[float]) -> str:
    if force is None:
        return NEUTRAL_COLOUR
    if force < 0.0:
        return COMPRESSION_COLOUR
    if force > 0.0:
        return TENSION_COLOUR
    return NEUTRAL_COLOUR


def _draw_graph(
    axis: Any,
    graph: Mapping[str, Any],
    title: str,
    forces: Optional[Mapping[int, float]] = None,
    default_colour: str = NEUTRAL_COLOUR,
) -> None:
    points = {vertex["id"]: vertex["point"] for vertex in graph["vertices"]}
    edges = list(graph["edges"])
    values = [
        None if forces is None else forces.get(index)
        for index in range(len(edges))
    ]
    width_of = _width_scale(values)

    for index, edge in enumerate(edges):
        start = points.get(edge["u"])
        end = points.get(edge["v"])
        if start is None or end is None:
            continue
        value = values[index]
        axis.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            color=default_colour if value is None else _colour(value),
            linewidth=width_of(value),
            solid_capstyle="round",
            zorder=2,
        )

    xs = [point[0] for point in points.values()]
    ys = [point[1] for point in points.values()]
    axis.scatter(xs, ys, s=6, color="#222222", zorder=3, linewidths=0)
    axis.set_title(title, fontsize=11)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")


def _draw_elevation(
    axis: Any,
    vertices: Sequence[Sequence[float]],
    form: Optional[Mapping[str, Any]] = None,
    forces: Optional[Mapping[int, float]] = None,
) -> None:
    """Draw the thrust network in elevation, as a vault section.

    The form diagram's vertex ids index the solved 3D vertices, so the same
    edge list drawn against x and z gives the real arching profile rather
    than a cloud of points.
    """

    if not vertices:
        axis.axis("off")
        return

    def xz(index: int) -> Optional[Sequence[float]]:
        if index < 0 or index >= len(vertices):
            return None
        point = vertices[index]
        return (point[0], point[2] if len(point) > 2 else 0.0)

    drew_edges = False
    if form is not None:
        edges = list(form["edges"])
        values = [
            None if forces is None else forces.get(index)
            for index in range(len(edges))
        ]
        width_of = _width_scale(values)
        for index, edge in enumerate(edges):
            start = xz(edge["u"])
            end = xz(edge["v"])
            if start is None or end is None:
                continue
            value = values[index]
            axis.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color=NEUTRAL_COLOUR if value is None else _colour(value),
                linewidth=width_of(value) * 0.8,
                solid_capstyle="round",
                alpha=0.85,
                zorder=2,
            )
            drew_edges = True

    zs = [point[2] if len(point) > 2 else 0.0 for point in vertices]
    if not drew_edges:
        axis.scatter(
            [point[0] for point in vertices],
            zs,
            s=8,
            color=COMPRESSION_COLOUR,
            zorder=3,
            linewidths=0,
        )
    axis.axhline(min(zs), color="#cccccc", linewidth=0.8, zorder=1)
    axis.set_title("Thrust surface, elevation", fontsize=11)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")


def plot_result(
    result: Mapping[str, Any],
    out: Path,
    title: Optional[str] = None,
) -> Path:
    """Draw the reciprocal form and force pair, plus a thrust elevation."""

    form = diagram(result, "form_graph")
    force = diagram(result, "force_graph")
    if form is None and force is None:
        raise ResultError(
            "This result carries no reciprocal diagrams; it is not a TNA result."
        )

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    forces = _edge_forces(result)

    figure, axes = plt.subplots(1, 3, figsize=(15, 5))
    try:
        if form is not None:
            _draw_graph(axes[0], form, "Form diagram", forces)
        else:
            axes[0].axis("off")
        if force is not None:
            _draw_graph(axes[1], force, "Force diagram", None)
        else:
            axes[1].axis("off")
        _draw_elevation(axes[2], thrust_vertices(result), form, forces)

        if title:
            figure.suptitle(title, fontsize=13)
        compression = sum(1 for value in forces.values() if value < 0.0)
        tension = sum(1 for value in forces.values() if value > 0.0)
        if forces:
            figure.text(
                0.5,
                0.02,
                "{} members in compression, {} in tension. "
                "Widths scale with axial force magnitude.".format(
                    compression,
                    tension,
                ),
                ha="center",
                fontsize=9,
                color="#444444",
            )
        figure.tight_layout(rect=(0, 0.04, 1, 0.96 if title else 1.0))
        figure.savefig(out, dpi=200)
    finally:
        plt.close(figure)
    return out


__all__ = ["plot_result"]
