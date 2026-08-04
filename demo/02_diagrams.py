"""Demo 2: the reciprocal diagrams, on screen and as a committable image.

Graphic statics reads a structure through two linked drawings. The form
diagram is the plan of the network; the force diagram is its reciprocal,
where every edge length is a force magnitude. They are dual: change one and
the other must change with it.

This script writes a PNG you can put in a document, then shows the same
three drawings in the viewer, laid out side by side.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hand this script to the project interpreter before importing anything
# that needs it, so the play button works whatever VS Code has selected.
from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _common import COMPRESSION, DEMO, PAVILION, SURFACE, TENSION  # noqa: E402
from _common import add, banner, open_viewer, require, show, step  # noqa: E402

from compas.datastructures import Mesh  # noqa: E402
from compas.geometry import Translation  # noqa: E402

from ananke_equilibrium.cli.plot import plot_result  # noqa: E402
from ananke_equilibrium.cli.results import diagram  # noqa: E402
from ananke_equilibrium.cli.results import load_result  # noqa: E402
from ananke_equilibrium.cli.results import thrust_faces  # noqa: E402
from ananke_equilibrium.cli.results import thrust_vertices  # noqa: E402
from ananke_equilibrium.cli.view import _graph_from_diagram  # noqa: E402
from ananke_equilibrium.cli.view import thrust_network  # noqa: E402


def span_of(points):
    xs = [point[0] for point in points]
    return (max(xs) - min(xs)) if xs else 1.0


def main() -> int:
    result_path = require(
        PAVILION / "results" / "result.json",
        "Run demo/01_solve_pavilion.py first: it produces the result file.",
    )
    result = load_result(result_path)

    banner("1. Write the diagrams as an image")
    image = DEMO / "pavilion-diagrams.png"
    step("Drawing form, force, and elevation")
    plot_result(result, image, title="Funicular pavilion: form and force")
    print("   wrote {}".format(image))
    print("   this file is committable, diffable, and drops into a document")

    banner("2. The same drawings in 3D")
    form = diagram(result, "form_graph")
    force = diagram(result, "force_graph")
    vertices = thrust_vertices(result)
    faces = thrust_faces(result)

    viewer = open_viewer("Form and force diagrams")

    mesh = Mesh.from_vertices_and_faces(vertices, faces)
    add(
        viewer.scene,
        mesh,
        "Thrust surface",
        show_faces=True,
        show_lines=False,
        opacity=0.4,
        facecolor=SURFACE,
    )
    network = thrust_network(result, vertices)
    if network is not None:
        add(
            viewer.scene,
            network,
            "Thrust network",
            linewidth=3,
            linecolor=COMPRESSION,
        )

    width = span_of(vertices) * 1.35
    if form is not None:
        graph = _graph_from_diagram(form)
        graph.transform(Translation.from_vector([width, 0.0, 0.0]))
        add(
            viewer.scene,
            graph,
            "Form diagram",
            linewidth=2,
            linecolor=COMPRESSION,
            show_points=True,
        )
        print("   form diagram   {} nodes, {} edges".format(
            graph.number_of_nodes(), graph.number_of_edges()))
    if force is not None:
        graph = _graph_from_diagram(force)
        graph.transform(Translation.from_vector([width * 2.0, 0.0, 0.0]))
        add(
            viewer.scene,
            graph,
            "Force diagram",
            linewidth=2,
            linecolor=TENSION,
            show_points=True,
        )
        print("   force diagram  {} nodes, {} edges".format(
            graph.number_of_nodes(), graph.number_of_edges()))

    print("")
    print("   Left: the vault. Middle: its form diagram. Right: the reciprocal")
    print("   force diagram, where every edge length is a force magnitude.")
    show(viewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
