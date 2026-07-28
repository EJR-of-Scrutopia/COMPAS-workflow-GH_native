"""Exercise the migrated FD core inside Rhino 8's CPython environment."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from tree_forest_compas.fd import solve_fd_network


lines = (
    ((-1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
    ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0)),
)
loads = np.zeros((3, 3), dtype=float)
loads[1, 2] = -1.0

session = solve_fd_network(
    lines,
    fixed=(0, 2),
    forcedensities=1.0,
    loads=loads,
)

free_nodes = tuple(
    index
    for index in range(len(session.residuals))
    if index not in set(session.fixed)
)
maximum_residual = max(
    float(np.linalg.norm(session.residuals[index])) for index in free_nodes
)
report = "\n".join(
    (
        "Migrated FD smoke test complete.",
        "Nodes: {}".format(len(session.equilibrium_vertices)),
        "Members: {}".format(len(session.member_forces)),
        "Maximum residual: {:.6g}".format(maximum_residual),
        "Member forces: {}".format(tuple(session.member_forces)),
    )
)
print(report)
(REPOSITORY / "scripts" / "rhino_smoke_fd.txt").write_text(
    report + "\n",
    encoding="utf-8",
)
