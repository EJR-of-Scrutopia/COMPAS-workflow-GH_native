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
from scipy.optimize import lsq_linear, nnls

from tree_forest_compas.prescribed import PrescribedError, solve_prescribed_lengths


class HoldError(RuntimeError):
    """Raised when the target geometry cannot be held in tension alone."""


class HoldResult(NamedTuple):
    """One equilibrium solution at the target geometry.

    Only equilibrium is guaranteed. When the net is redundant (more edges than
    three times the number of free nodes) the force densities are not unique and
    this is one non-negative member of a family; do not read it as a property of
    the net. Choosing a preferred member is a separate, explicit decision.
    """

    force_densities: tuple
    tensions: tuple
    residual: float
    units: str


def hold_force_densities(vertices, edges, fixed, loads, residual_tolerance=1e-6):
    """One set of force densities that holds every free node in place.

    The result satisfies equilibrium under the given load with every density
    non-negative. It is one solution among many when the net is redundant:
    non-negative least squares returns a single sparse vertex of the family, so
    only equilibrium is guaranteed, not uniqueness.
    """

    xyz = np.asarray(vertices, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise HoldError("vertices must be an n by 3 array of coordinates.")
    edges = [(int(u), int(v)) for u, v in edges]
    p = np.asarray(loads, dtype=float)
    if p.shape != xyz.shape:
        raise HoldError("loads must have one row per vertex.")
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(xyz)):
        raise HoldError("vertices and loads must be finite numbers.")

    count = len(xyz)
    fixed_set = {int(f) for f in fixed}
    for index in fixed_set:
        if not 0 <= index < count:
            raise HoldError("Fixed index {} is outside the {} vertices.".format(index, count))
    for u, v in edges:
        if not (0 <= u < count and 0 <= v < count):
            raise HoldError("Edge ({}, {}) refers to a vertex outside 0..{}.".format(u, v, count - 1))

    free = [index for index in range(count) if index not in fixed_set]
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

    try:
        q, residual = nnls(a, b)
    except Exception as error:  # scipy raises its own types; report ours
        raise HoldError("The non-negative least squares solve failed: {}".format(error)) from error
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


class CorrectionResult(NamedTuple):
    """The correction, and how well it was checked.

    reel_commands are CHANGES to each cable's rest length in millimetres:
    negative shortens (reels in), positive lets out. residual_before and
    residual_after are the largest node distance from target in millimetres;
    residual_after comes from re-solving the net at the commanded rest lengths and
    adding its movement to the measured positions, so reachable rests on the net's
    own answer, not the linear model. residual_predicted is
    the linear model's forecast of the same number. A large gap between the two,
    or a max_command beyond the range where the linear model holds (see
    correction_for), means the correction should be repeated from fresh
    measurements.
    """

    reel_commands: tuple
    residual_before: float
    residual_after: float
    reachable: bool
    units: str
    residual_predicted: float = 0.0
    max_command: float = 0.0


def correction_for(
    problem,
    fixed,
    rest_lengths,
    ea,
    loads,
    measured,
    target,
    step=1.0,
    tolerance=5.0,
):
    """What to reel to remove the deviation the markers actually measured.

    The net has one rest length per cable and three coordinates per node, so it
    is under-actuated: the best any command can do is least squares. The residual
    this cannot remove is reported, because if it exceeds the acceptance line the
    answer is more cables, not better tuning.

    rest_lengths are the CURRENT commanded rest lengths. The sensitivity of every
    node to each rest length is found by finite difference about the net at those
    lengths: one solve at rest_lengths and one per cable with that cable shortened
    by ``step`` mm. The linear model is trustworthy for commands of a few times
    ``step``; max_command reports the largest command so a caller can see when it
    has left that range. Too small a step gives noisy columns, too large a
    linearisation error. The commands are then applied and the net re-solved, and
    residual_after is the measured position plus the re-solved net's movement
    (nonlinear), so it and reachable do not rest on the linear model.

    A net that is slack at any of the solved lengths (including the commanded
    ones) raises HoldError naming the cable or saying so, because a correction
    around a slack net would be fiction.
    """

    measured = np.asarray(measured, dtype=float)
    target = np.asarray(target, dtype=float)
    if measured.shape != target.shape:
        raise HoldError("measured and target must be the same shape.")
    node_count = len(problem.source_vertices)
    if target.shape != (node_count, 3):
        raise HoldError(
            "measured and target need one row per node: got {}, expected "
            "({}, 3).".format(target.shape, node_count)
        )

    rest = np.asarray(rest_lengths, dtype=float).reshape(-1)
    cable_count = len(problem.source_edges)
    if rest.size != cable_count:
        raise HoldError(
            "Needs one rest length per cable: got {}, expected {}.".format(
                rest.size, cable_count
            )
        )
    step = float(step)
    if not np.isfinite(step) or step <= 0.0:
        raise HoldError("step must be finite and positive.")

    deviation = (measured - target).reshape(-1)
    before = float(np.linalg.norm((measured - target), axis=1).max())

    def solve_at(lengths, what):
        try:
            state = solve_prescribed_lengths(
                problem, fixed=fixed, rest_lengths=lengths, ea=ea, loads=loads
            )
        except PrescribedError as error:
            raise HoldError("{}: {}".format(what, error)) from error
        return np.asarray(state.session.equilibrium_vertices, dtype=float)

    baseline = solve_at(rest, "cannot linearise the net at the current rest lengths")

    # one column per cable: how every node moves per mm of shortening
    columns = []
    for index in range(rest.size):
        nudged = rest.copy()
        nudged[index] = nudged[index] - step
        xyz = solve_at(
            nudged, "cannot linearise the net around cable {}".format(index)
        )
        columns.append(((xyz - baseline) / step).reshape(-1))
    jacobian = np.column_stack(columns)

    solution = lsq_linear(jacobian, -deviation)
    if not solution.success or not np.all(np.isfinite(solution.x)):
        raise HoldError(
            "least squares did not converge (status {}): {}".format(
                solution.status, solution.message
            )
        )
    shortening = solution.x
    commands = tuple(float(-value) for value in shortening)
    predicted_vector = (jacobian.dot(shortening) + deviation).reshape(target.shape)
    predicted = float(np.linalg.norm(predicted_vector, axis=1).max())

    applied = solve_at(
        rest + np.asarray(commands), "the commanded rest lengths leave the net slack"
    )
    # the markers may disagree with the model, so carry the measured position
    # forward by the model's own predicted movement, not the model's absolute one
    after = float(np.linalg.norm(measured + (applied - baseline) - target, axis=1).max())

    return CorrectionResult(
        reel_commands=commands,
        residual_before=before,
        residual_after=after,
        reachable=bool(after <= float(tolerance)),
        units="N, mm",
        residual_predicted=predicted,
        max_command=float(max(abs(value) for value in commands)),
    )
