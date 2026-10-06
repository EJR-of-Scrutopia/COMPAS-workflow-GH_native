"""Keep the funicular form while the skin load arrives.

With the geometry held at the target, equilibrium is linear in the force
densities, so the tension that keeps every free node exactly where it belongs is
a non-negative least squares solve. Cables pull and never push, which is what the
non-negativity enforces, and a geometry that would need a strut is refused rather
than quietly returned.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from scipy.optimize import nnls


class HoldError(RuntimeError):
    """Raised when the target geometry cannot be held in tension alone."""


class HoldResult(NamedTuple):
    force_densities: tuple
    tensions: tuple
    residual: float
    units: str


def hold_force_densities(vertices, edges, fixed, loads, residual_tolerance=1e-6):
    """Force densities that hold every free node in place under the given load."""

    xyz = np.asarray(vertices, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise HoldError("vertices must be an n by 3 array of coordinates.")
    edges = [(int(u), int(v)) for u, v in edges]
    p = np.asarray(loads, dtype=float)
    if p.shape != xyz.shape:
        raise HoldError("loads must have one row per vertex.")

    free = [index for index in range(len(xyz)) if index not in set(int(f) for f in fixed)]
    if not free:
        raise HoldError("Every vertex is fixed, so there is nothing to hold.")

    load_size = float(np.abs(p[free]).max())
    if load_size <= 0.0:
        raise HoldError(
            "There is no load on any free node, so the hold solve has nothing to "
            "balance. At an unloaded stage the prestress comes from form-finding, "
            "not from this solve."
        )

    row_of = {node: row for row, node in enumerate(free)}
    a = np.zeros((3 * len(free), len(edges)), dtype=float)
    for column, (u, v) in enumerate(edges):
        if u in row_of:
            a[3 * row_of[u]:3 * row_of[u] + 3, column] = xyz[v] - xyz[u]
        if v in row_of:
            a[3 * row_of[v]:3 * row_of[v] + 3, column] = xyz[u] - xyz[v]
    b = -p[free].reshape(-1)

    q, residual = nnls(a, b)
    relative = float(residual) / load_size
    if relative > float(residual_tolerance):
        worst = int(np.argmax(np.abs(a.dot(q) - b)))
        raise HoldError(
            "The target geometry cannot be held in tension alone under this load: "
            "out of balance by {:.6g} N at free node {}, which is {:.3g} of the "
            "load. The net needs another anchor, another cable, or a different "
            "shape.".format(float(residual), free[worst // 3], relative)
        )

    lengths = np.array(
        [float(np.linalg.norm(xyz[v] - xyz[u])) for u, v in edges], dtype=float
    )
    return HoldResult(
        force_densities=tuple(float(value) for value in q),
        tensions=tuple(float(value) for value in (q * lengths)),
        residual=float(residual),
        units="N, mm",
    )
