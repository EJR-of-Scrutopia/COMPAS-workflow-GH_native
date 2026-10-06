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
_SLACK_PATIENCE = 50   # consecutive iterations a member may stay slack before refusal
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


def _names(mask):
    return ", ".join(str(int(index)) for index in np.flatnonzero(mask))


def _slack_message(registered, mask, iteration):
    parts = []
    if np.any(registered):
        parts.append(
            "members {} are already slack at the registered geometry (rest "
            "length not shorter than the registered length: the likely cause)".format(
                _names(registered)
            )
        )
    if np.any(mask):
        parts.append(
            "members {} were slack at iteration {}, after the net moved "
            "(a symptom, not necessarily a cause)".format(_names(mask), iteration)
        )
    return (
        "A cable cannot push, and the net went slack: {}. Shorten the rest "
        "lengths of the first set or change the anchors.".format("; ".join(parts))
    )


def solve_prescribed_lengths(
    problem,
    fixed,
    rest_lengths,
    ea,
    loads=None,
    max_iterations=1000,
    movement_tolerance=1e-6,
    damping=0.5,
    residual_tolerance=1e-8,
):
    """Find the geometry and tension a net takes for the given rest lengths.

    The iteration settles when the largest node movement is below
    movement_tolerance (mm) AND every member's force density is within
    residual_tolerance (relative) of the value its own elastic law gives.
    A member that is slack (length not above rest length) is refused by name.
    """

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
    registered_slack = slack.copy()
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
    slack_count = np.zeros(len(edges), dtype=int)
    residual = float("inf")
    slack = np.zeros(len(edges), dtype=bool)
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
        # A member that is slack part-way through is given a small positive
        # force density (fd.py rejects zero). That value is nearly absorbing
        # under the stiffness-scaled step, so a member that stays slack is
        # refused by name rather than waited on.
        target = np.where(
            slack, _FLOOR, stiffness * np.where(slack, 1.0, stretch) / (rest * lengths)
        )
        # Per member, so one stiff member cannot hide behind a large one.
        residual = float(np.max(np.abs(target - q) / q))
        slack_count = np.where(slack, slack_count + 1, 0)
        if np.any(slack_count >= _SLACK_PATIENCE):
            raise PrescribedError(
                _slack_message(
                    registered_slack, slack_count >= _SLACK_PATIENCE, iteration
                )
            )
        if residual < float(residual_tolerance) and movement < float(movement_tolerance):
            if np.any(slack):
                raise PrescribedError(_slack_message(registered_slack, slack, iteration))
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

    if np.any(slack):
        raise PrescribedError(_slack_message(registered_slack, slack, int(max_iterations)))
    unmet = []
    if movement >= float(movement_tolerance):
        unmet.append(
            "movement {:.6g} mm per step is not below {:.6g}".format(
                movement, float(movement_tolerance)
            )
        )
    if residual >= float(residual_tolerance):
        unmet.append(
            "worst member force-density error {:.6g} is not below {:.6g}".format(
                residual, float(residual_tolerance)
            )
        )
    raise PrescribedError(
        "Did not settle in {} iterations: {}.".format(max_iterations, "; ".join(unmet))
    )


def rest_lengths_from_session(session, ea):
    """The rest length each member must have had to be in the state it is in."""

    lengths = np.asarray(session.member_lengths, dtype=float)
    tensions = np.asarray(session.force_densities, dtype=float) * lengths
    stiffness = np.asarray(ea, dtype=float).reshape(-1)
    if stiffness.size == 1:
        stiffness = np.full(len(lengths), float(stiffness[0]))
    if stiffness.size != len(lengths):
        raise PrescribedError("ea must be one value or one value per segment.")
    if np.any(~(tensions > 0.0)):
        bad = np.flatnonzero(~(tensions > 0.0))
        raise PrescribedError(
            "Members {} are not in tension, so they have no rest length to "
            "reel to.".format(", ".join(str(int(index)) for index in bad))
        )
    # Vectorised rest_length.rest_length_for, the definition of record.
    return tuple(float(value) for value in lengths / (1.0 + tensions / stiffness))


def reel_commands(before, after):
    """How much each cable must be reeled to go from one state to the next.

    Negative is reeling in, which shortens the cable and raises the net.
    """

    first = np.asarray(before, dtype=float).reshape(-1)
    second = np.asarray(after, dtype=float).reshape(-1)
    if first.size != second.size:
        raise PrescribedError("Both states must have the same number of cables.")
    return tuple(float(value) for value in (second - first))
