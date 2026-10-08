"""How far an unbalanced force moves a cable net, to first order.

A member of length L, unit vector u, axial stiffness EA and force density q
(tension over length) resists its end moving by

    k = (EA / L) u u^T + q (I - u u^T)

elastically along itself and geometrically across itself. The geometric part
is what a slack member lacks: with q = 0 a flat patch of net is a mechanism
out of its own plane, which is why callers pass the entered prestress as a
floor on q. The displacement under a residual force field r is the solution
of K_ff d = r_f over the free vertices, one sparse solve.

This is a first-order figure. The real net stiffens as it sags, so a large
answer is an upper bound on the movement and a small one is close.

Units are newtons and millimetres.
"""

from __future__ import annotations

import warnings

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import MatrixRankWarning
from scipy.sparse.linalg import spsolve


class StiffnessError(RuntimeError):
    """Raised when the tangent stiffness cannot be built or solved."""


def tangent_stiffness(vertices, edges, force_densities, ea):
    """The 3n by 3n tangent stiffness of the net at these force densities."""

    xyz = np.asarray(vertices, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise StiffnessError("vertices must be an n by 3 array of coordinates.")
    edges = [(int(u), int(v)) for u, v in edges]
    q = np.asarray(force_densities, dtype=float).reshape(-1)
    if q.size != len(edges):
        raise StiffnessError(
            "Needs one force density per member: got {}, expected {}.".format(
                q.size, len(edges)))
    if not np.all(np.isfinite(q)) or np.any(q < 0.0):
        raise StiffnessError("force densities must be finite and non-negative.")
    ea = float(ea)
    if not np.isfinite(ea) or ea <= 0.0:
        raise StiffnessError("EA must be finite and greater than zero.")
    count = len(xyz)
    rows, cols, values = [], [], []
    eye = np.eye(3)
    for index, (u, v) in enumerate(edges):
        if not (0 <= u < count and 0 <= v < count):
            raise StiffnessError(
                "Edge ({}, {}) refers to a vertex outside 0..{}.".format(u, v, count - 1))
        d = xyz[v] - xyz[u]
        length = float(np.linalg.norm(d))
        if length <= 0.0:
            raise StiffnessError("Member {} has no length.".format(index))
        unit = d / length
        along = np.outer(unit, unit)
        k = (ea / length) * along + q[index] * (eye - along)
        for a, b, sign in ((u, u, 1.0), (v, v, 1.0), (u, v, -1.0), (v, u, -1.0)):
            for i in range(3):
                for j in range(3):
                    rows.append(3 * a + i)
                    cols.append(3 * b + j)
                    values.append(sign * k[i, j])
    return coo_matrix((values, (rows, cols)), shape=(3 * count, 3 * count)).tocsr()


def first_order_sag(vertices, edges, fixed, force_densities, ea, residual, floor=0.0):
    """Millimetres each free vertex moves under `residual`, zero at held ones.

    floor is a force density applied as a minimum to every member, one number
    or one per member: the prestress the net is given, which is what makes a
    slack patch stiff across itself.
    """

    xyz = np.asarray(vertices, dtype=float)
    r = np.asarray(residual, dtype=float)
    if r.shape != xyz.shape:
        raise StiffnessError("residual must have one row of three per vertex.")
    q = np.asarray(force_densities, dtype=float).reshape(-1)
    floor_q = np.asarray(floor, dtype=float)
    if floor_q.ndim == 0:
        floor_q = np.full(q.shape, float(floor_q))
    if floor_q.shape != q.shape:
        raise StiffnessError("floor must be one number or one per member.")
    if np.any(floor_q < 0.0) or not np.all(np.isfinite(floor_q)):
        raise StiffnessError("floor must be finite and non-negative.")
    k = tangent_stiffness(xyz, edges, np.maximum(q, floor_q), ea)
    count = len(xyz)
    fixed_set = {int(f) for f in fixed}
    for index in fixed_set:
        if not 0 <= index < count:
            raise StiffnessError("Fixed index {} is outside the {} vertices.".format(index, count))
    free = [index for index in range(count) if index not in fixed_set]
    out = np.zeros_like(r)
    if not free:
        return out
    dof = np.asarray([[3 * i, 3 * i + 1, 3 * i + 2] for i in free]).reshape(-1)
    kff = k[dof][:, dof].tocsc()
    with warnings.catch_warnings():
        warnings.simplefilter("error", MatrixRankWarning)
        try:
            d = spsolve(kff, r.reshape(-1)[dof])
        except (MatrixRankWarning, RuntimeError) as error:
            raise StiffnessError(
                "The net has a mechanism nothing stiffens: a free vertex can move "
                "without stretching or tensioning any member. Give the members a "
                "prestress floor. ({})".format(error)) from error
    d = np.asarray(d, dtype=float).reshape(-1)
    if not np.all(np.isfinite(d)):
        raise StiffnessError(
            "The net has a mechanism nothing stiffens: the displacement is not "
            "finite. Give the members a prestress floor.")
    out[free] = d.reshape(-1, 3)
    return out
