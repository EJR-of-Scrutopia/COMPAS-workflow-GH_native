"""Solve a cable net from the lengths the machine reels, not from its forces.

Force density is linear in the geometry only when the force densities are known.
Here the rest lengths are known instead, and each member's force density depends
on how far it has stretched, so the linear solve is wrapped in an iteration:
guess q, solve, measure the new lengths, update q, repeat.

Units are newtons and millimetres.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from tree_forest_compas.fd import FDInputError
from tree_forest_compas.fd import FDSolveError
from tree_forest_compas.fd import solve_fd_problem


_FLOOR = 1e-6          # force density given to a member that is slack mid-iteration
_RESIDUAL_TOLERANCE = 1e-8   # largest relative gap between q and the elastic q
_MEMORY = 6            # steps the Anderson mixing looks back over


class PrescribedError(RuntimeError):
    """Raised when a prescribed-length solve cannot produce a tension state."""


class PrescribedResult(NamedTuple):
    session: object
    force_densities: tuple
    rest_lengths: tuple
    lengths: tuple
    tensions: tuple
    iterations: int
    movement: float
    units: str


def _edge_lengths(vertices, edges):
    xyz = np.asarray(vertices, dtype=float)
    starts = xyz[[u for u, _ in edges]]
    ends = xyz[[v for _, v in edges]]
    return np.linalg.norm(ends - starts, axis=1)


def solve_prescribed_lengths(
    problem,
    fixed,
    rest_lengths,
    ea,
    loads=None,
    max_iterations=100,
    movement_tolerance=1e-6,
    damping=0.5,
):
    """Find the geometry and tension a net takes for the given rest lengths."""

    edges = tuple(problem.source_edges)
    rest = np.asarray(rest_lengths, dtype=float).reshape(-1)
    if rest.size != len(edges):
        raise PrescribedError(
            "Needs one rest length per registered segment: got {}, expected "
            "{}.".format(rest.size, len(edges))
        )
    if not np.all(np.isfinite(rest)) or np.any(rest <= 0.0):
        raise PrescribedError("Every rest length must be finite and positive.")

    stiffness = np.asarray(ea, dtype=float).reshape(-1)
    if stiffness.size == 1:
        stiffness = np.full(len(edges), float(stiffness[0]))
    if stiffness.size != len(edges):
        raise PrescribedError("ea must be one value or one value per segment.")
    if not np.all(np.isfinite(stiffness)) or np.any(stiffness <= 0.0):
        raise PrescribedError("Every ea must be finite and greater than zero.")

    lengths = _edge_lengths(problem.source_vertices, edges)
    slack = lengths <= rest
    if np.all(slack):
        raise PrescribedError(
            "Every member is slack at the registered geometry: the net cannot "
            "carry anything until it is reeled in."
        )
    # Vectorised rest_length.force_density, the definition of record.
    q = np.where(slack, 1e-6, stiffness * (lengths - rest) / (rest * lengths))

    previous = np.asarray(problem.source_vertices, dtype=float)
    movement = float("inf")
    session = None
    history_q = []
    history_f = []
    for iteration in range(1, int(max_iterations) + 1):
        try:
            session = solve_fd_problem(
                problem, fixed=fixed, forcedensities=q, loads=loads
            )
        except (FDInputError, FDSolveError) as error:
            raise PrescribedError(
                "The linear solve failed at iteration {}: {}".format(iteration, error)
            )

        xyz = np.asarray(session.equilibrium_vertices, dtype=float)
        lengths = np.asarray(session.member_lengths, dtype=float)
        movement = float(np.abs(xyz - previous).max())
        previous = xyz

        stretch = lengths - rest
        slack = stretch <= 0.0
        # Vectorised rest_length.force_density, the definition of record.
        # A member that is slack part-way through is held at a small positive
        # force density so the iteration can recover; it is refused only if it
        # is still slack when the iteration settles.
        target = np.where(
            slack, _FLOOR, stiffness * np.where(slack, 1.0, stretch) / (rest * lengths)
        )
        residual = float(np.abs(target - q).max() / np.abs(q).max())
        if residual < _RESIDUAL_TOLERANCE and movement < float(movement_tolerance):
            if np.any(slack):
                bad = np.flatnonzero(slack)
                raise PrescribedError(
                    "Members {} are slack at equilibrium: a cable cannot push. "
                    "Shorten the rest length or change the anchors.".format(
                        ", ".join(str(int(index)) for index in bad)
                    )
                )
            return PrescribedResult(
                session=session,
                force_densities=tuple(float(value) for value in q),
                rest_lengths=tuple(float(value) for value in rest),
                lengths=tuple(float(value) for value in lengths),
                tensions=tuple(float(value) for value in (q * lengths)),
                iterations=iteration,
                movement=movement,
                units="N, mm",
            )

        # A cable net of real cable is very stiff: a 1 percent change in a
        # force density moves the length by far more than the elastic update
        # puts back, so the plain update q <- target overshoots without bound.
        # Scaling each member's step by 1 / (1 + EA / (L0 q)), the stiffness
        # against which the length responds, tames that; Anderson mixing over
        # the last few steps then supplies the coupling between members.
        step = float(damping) * (target - q) / (1.0 + stiffness / (rest * q))
        history_q.append(q.copy())
        history_f.append(step.copy())
        del history_q[:-(_MEMORY + 1)]
        del history_f[:-(_MEMORY + 1)]
        proposal = q + step
        if len(history_f) > 1:
            d_f = np.diff(np.array(history_f), axis=0).T
            d_q = np.diff(np.array(history_q), axis=0).T
            gamma = np.linalg.lstsq(d_f, step, rcond=None)[0]
            mixed = q + step - (d_q + d_f) @ gamma
            if np.all(np.isfinite(mixed)) and np.all(mixed > 0.0):
                proposal = mixed
        q = np.maximum(proposal, _FLOOR)

    raise PrescribedError(
        "Did not settle in {} iterations; the net was still moving {:.6g} mm per "
        "step.".format(max_iterations, movement)
    )
