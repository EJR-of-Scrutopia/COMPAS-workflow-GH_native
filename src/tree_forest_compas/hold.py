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
from scipy.optimize import lsq_linear, minimize, nnls

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


class FitResult(NamedTuple):
    """The best tension-only state, and what it leaves unbalanced.

    residual[i] is the force an actuator at free vertex i would have to add for
    equilibrium, zero at a held vertex. reactions[i] is the force held vertex i
    supplies, zero at a free vertex. residual_norm is the Euclidean norm of the
    whole residual field, the quantity the non-negative least squares minimised,
    so it never rises when a vertex is moved from free to held. On a redundant
    net force_densities, tensions and reactions are one member of a family of
    equally good states; residual and residual_norm are the same for every member.
    """

    force_densities: tuple
    tensions: tuple
    residual: tuple
    reactions: tuple
    residual_norm: float
    units: str


def _checked_inputs(vertices, edges, fixed, loads):
    """The coordinates, edges, loads and fixed set, or a HoldError saying what is wrong."""

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
    return xyz, edges, p, fixed_set


def _equilibrium_operator(xyz, edges):
    """Rows 3i..3i+2 of a times q is the pull of every member on vertex i."""

    a = np.zeros((3 * len(xyz), len(edges)), dtype=float)
    for column, (u, v) in enumerate(edges):
        a[3 * u:3 * u + 3, column] = xyz[v] - xyz[u]
        a[3 * v:3 * v + 3, column] = xyz[u] - xyz[v]
    return a


def _rows_of(nodes):
    """The rows of the equilibrium operator that belong to these vertices."""

    return np.asarray([[3 * i, 3 * i + 1, 3 * i + 2] for i in nodes], dtype=int).reshape(-1)


def _member_lengths(xyz, edges):
    """Each member length, in the order of the edges."""

    return np.array(
        [float(np.linalg.norm(xyz[v] - xyz[u])) for u, v in edges], dtype=float
    )


def _floats(values):
    """Plain Python floats in a tuple, so a result carries no numpy scalars."""

    return tuple(float(value) for value in values)


# A net with more members than this is given to the fast path first; a net with
# this many or fewer keeps the exact solves alone. See _non_negative_solve.
_LARGE_NET_MEMBERS = 400

# How far the fast path's answer may sit from the optimality conditions,
# relative to the largest entry of a^T b (or to 1, if that is smaller), before
# the exact solves answer instead.
_OPTIMALITY_TOLERANCE = 1.0e-6


def _fast_solve(a, b):
    """q >= 0 from a bound-constrained L-BFGS-B solve, with the norm of a q - b,
    or None.

    None means the exact solves should answer: the solve raised, or what it
    returned does not meet the optimality conditions of the non-negative least
    squares. With g = a^T (a q - b) those are g_i = 0 where q_i is positive and
    g_i >= 0 where q_i is zero, held here to _OPTIMALITY_TOLERANCE. SciPy's own
    success flag is not asked: L-BFGS-B often reports an abnormal ending once it
    has reached the limit of double precision, and the conditions are the test.
    """

    columns = a.shape[1]

    def objective(q):
        misfit = a.dot(q) - b
        return 0.5 * float(misfit.dot(misfit)), a.T.dot(misfit)

    try:
        answer = minimize(
            objective, x0=np.zeros(columns), jac=True, method="L-BFGS-B",
            bounds=[(0.0, None)] * columns,
            options=dict(maxiter=20000, maxfun=40000, ftol=1e-16, gtol=1e-10),
        )
    except Exception:  # scipy raises its own types; the exact solves answer then
        return None
    # a cable never pushes: a density a rounding error below zero is zero
    q = np.maximum(np.asarray(answer.x, dtype=float), 0.0)
    misfit = a.dot(q) - b
    gradient = a.T.dot(misfit)
    tolerance = _OPTIMALITY_TOLERANCE * max(1.0, float(np.max(np.abs(a.T.dot(b)))))
    positive = q > 0.0
    # written so that an answer or a gradient that is not a number is refused
    if not (np.all(np.abs(gradient[positive]) <= tolerance)
            and np.all(gradient[~positive] >= -tolerance)):
        return None
    return q, float(np.linalg.norm(misfit))


def _non_negative_solve(a, b):
    """The q >= 0 that minimises the norm of a q - b, and that norm.

    A net of more than 400 members is given to a bound-constrained L-BFGS-B
    solve first, the fast path, because on the real net (2105 members), with the
    held set at its base and with 200, 500 and 800 greedy-chosen nodes added,
    nnls took 1.4, 44.7, 15.0 and 1.0 s and bvls 32, 110, 0.4 and 5.2 s while
    L-BFGS-B took 0.7, 1.0, 0.5 and 0.1 s and gave the same residual norm to
    four significant figures every time (2491, 991.3, 471.6 and 125.4 N). Its
    answer is kept only if it meets the optimality conditions; otherwise, and
    for a net of 400 members or fewer, the exact solves below run alone and
    unchanged.

    The SciPy non-negative least squares goes first of those. On a redundant net
    it can cycle and give up however many iterations it is given, or meet a
    singular matrix, even when the net holds its load exactly (seen with SciPy
    1.13). A bounded-variable least squares then takes over: it reaches the same
    optimum and is not troubled by members that are not independent. A HoldError
    is raised only when both fail.
    """

    if a.shape[1] > _LARGE_NET_MEMBERS:
        answer = _fast_solve(a, b)
        if answer is not None:
            return answer

    try:
        q, norm = nnls(a, b)
    except Exception as error:  # scipy raises its own types; report ours
        reason = str(error)
    else:
        return q, float(norm)

    try:
        solution = lsq_linear(a, b, bounds=(0.0, np.inf), method="bvls")
    except Exception as error:
        raise HoldError(
            "The non-negative least squares solve failed: {}; the bounded "
            "fallback failed too: {}".format(reason, error)
        ) from error
    if not solution.success or not np.all(np.isfinite(solution.x)):
        raise HoldError(
            "The non-negative least squares solve failed: {}; the bounded "
            "fallback did not converge either (status {}): {}".format(
                reason, solution.status, solution.message
            )
        )
    # bvls steps onto a bound by arithmetic and can land a rounding error below
    # it, and a cable never pushes
    q = np.maximum(solution.x, 0.0)
    return q, float(np.linalg.norm(a.dot(q) - b))


def fit_tension_state(vertices, edges, fixed, loads):
    """The best tension-only state the net can carry, with the shortfall named.

    The same non-negative least squares as hold_force_densities, but a net that
    cannot be held is answered rather than refused: the force left unbalanced
    at each free vertex is reported, because on an actuated net that force is
    what the actuator must supply and where it must go. An unloaded net is
    answered with zeros.
    """

    xyz, edges, p, fixed_set = _checked_inputs(vertices, edges, fixed, loads)
    free = [index for index in range(len(xyz)) if index not in fixed_set]
    a = _equilibrium_operator(xyz, edges)
    b = -p.reshape(-1)
    q = np.zeros(len(edges), dtype=float)
    if free and edges:
        rows = _rows_of(free)
        q, _ = _non_negative_solve(a[rows], b[rows])
    # member pulls plus load at every vertex: zero where the state balances
    balance = (a.dot(q) + p.reshape(-1)).reshape(-1, 3)
    residual = np.zeros_like(p)
    reactions = np.zeros_like(p)
    if free:
        residual[free] = -balance[free]
    held = sorted(fixed_set)
    if held:
        reactions[held] = -balance[held]
    return FitResult(
        force_densities=_floats(q),
        tensions=_floats(q * _member_lengths(xyz, edges)),
        residual=tuple(_floats(row) for row in residual),
        reactions=tuple(_floats(row) for row in reactions),
        residual_norm=float(np.linalg.norm(residual)),
        units="N, mm",
    )


def hold_force_densities(vertices, edges, fixed, loads, residual_tolerance=1e-6):
    """One set of force densities that holds every free node in place.

    The result satisfies equilibrium under the given load with every density
    non-negative. It is one solution among many when the net is redundant: the
    solve returns a single member of the family, so only equilibrium is
    guaranteed, not uniqueness.
    """

    xyz, edges, p, fixed_set = _checked_inputs(vertices, edges, fixed, loads)
    free = [index for index in range(len(xyz)) if index not in fixed_set]
    if not free:
        raise HoldError("Every vertex is fixed, so there is nothing to hold.")

    load_size = float(np.abs(p[free]).max())
    if load_size <= 0.0:
        raise HoldError(
            "There is no load on any free node, so the hold solve has nothing to "
            "balance. At an unloaded stage the prestress comes from form-finding, "
            "not from this solve."
        )

    a = _equilibrium_operator(xyz, edges)[_rows_of(free)]
    b = -p[free].reshape(-1)
    q, residual = _non_negative_solve(a, b)
    relative = float(residual) / load_size
    if relative > float(residual_tolerance):
        worst = int(np.argmax(np.abs(a.dot(q) - b)))
        raise HoldError(
            "The target geometry cannot be held in tension alone under this load: "
            "out of balance by {:.6g} N at free node {}, which is {:.3g} of the "
            "load. The net needs another anchor, another cable, or a different "
            "shape.".format(float(residual), free[worst // 3], relative)
        )

    return HoldResult(
        force_densities=_floats(q),
        tensions=_floats(q * _member_lengths(xyz, edges)),
        residual=float(residual),
        units="N, mm",
    )


def nodes_needing_support(vertices, edges, fixed, loads):
    """Free nodes no tension-only net can hold, named rather than discovered.

    A cable pulls a node TOWARD its neighbour and never pushes. So a node whose
    load has a downward component, and every one of whose neighbours is at or
    below it, cannot be in equilibrium: every available force and the load all
    point down. On the real vault export two such nodes sit at the crown, and
    the answer is to put a wire on them.

    This is a NECESSARY condition, not a sufficient one: a node with a neighbour
    above it may still be unholdable once the horizontal balance is worked out.
    The solver stays the authority. This exists so the common case gives a node
    number instead of a least squares message.
    """

    xyz = np.asarray(vertices, dtype=float)
    pull = np.asarray(loads, dtype=float).reshape(-1, 3)
    held = set(int(index) for index in fixed)
    above = [False] * len(xyz)
    touched = [False] * len(xyz)
    for u, v in edges:
        u, v = int(u), int(v)
        touched[u] = touched[v] = True
        if xyz[v][2] > xyz[u][2]:
            above[u] = True
        if xyz[u][2] > xyz[v][2]:
            above[v] = True
    return tuple(
        index
        for index in range(len(xyz))
        if index not in held
        and touched[index]
        and not above[index]
        and pull[index][2] < 0.0
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
    actuated=None,
):
    """What to reel to remove the deviation the markers actually measured.

    The net has one rest length per cable and three coordinates per node, so it
    is under-actuated: the best any command can do is least squares. The residual
    this cannot remove is reported, because if it exceeds the acceptance line the
    answer is more cables, not better tuning.

    rest_lengths are the CURRENT commanded rest lengths. The sensitivity of every
    node to each rest length is found by finite difference about the net at those
    lengths: one solve at rest_lengths and one per ACTUATED cable with that cable
    shortened by ``step`` mm. The linear model is trustworthy for commands of a few times
    ``step``; max_command reports the largest command so a caller can see when it
    has left that range. Too small a step gives noisy columns, too large a
    linearisation error. The commands are then applied and the net re-solved, and
    residual_after is the measured position plus the re-solved net's movement
    (nonlinear), so it and reachable do not rest on the linear model.

    actuated is a sequence of cable indices, the ones a motor can really reel.
    Only those are perturbed and commanded; every other cable receives exactly
    0.0, and reel_commands is always one entry per cable so callers can index it
    by cable number. None means every cable is actuated. A manufactured member
    can never be commanded, so on a real net (2253 members, about seven wires)
    this is the difference between one solve per member and one per wire.

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

    if actuated is None:
        driven = tuple(range(rest.size))
    else:
        driven = tuple(int(index) for index in actuated)
        if not driven:
            raise HoldError("actuated must name at least one cable to command.")
        for index in driven:
            if not 0 <= index < rest.size:
                raise HoldError(
                    "actuated cable {} is outside 0..{}.".format(index, rest.size - 1)
                )
        if len(set(driven)) != len(driven):
            raise HoldError("actuated names the same cable twice.")

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

    # one column per actuated cable: how every node moves per mm of shortening
    columns = []
    for index in driven:
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
    full = np.zeros(rest.size)
    full[list(driven)] = shortening
    commands = tuple(float(-value) for value in full)
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
