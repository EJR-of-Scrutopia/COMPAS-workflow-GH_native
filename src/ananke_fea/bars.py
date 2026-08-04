"""A beam frame of the thrust network, for checking the FEA setup itself.

The point of this model is not to predict anything. It is to be solved
under the same loads as the shell and compared against the member forces
TNA already reported. Agreement means the loads, supports, units and
extraction are all wired up correctly, and the shell result can be believed.
Disagreement means the fault is in the setup, not in the vault.

Getting this to solve at all took two fixes, in the order they were found:

1. A truss element carries no rotational stiffness, and the backend writes
   every OpenSees domain with 6 DOF per node regardless of element type, so
   a model built entirely from TrussElement is singular in rotation.
   Restraining rotations at every free node cured that.
2. It was not enough. The exported thrust network is a pure quad grid with
   no diagonals, and a pin-jointed quad panel has an in-plane shear
   mechanism: a translational collapse mode, not a rotational one, so no
   rotational restraint touches it. Free DOFs comfortably outnumber
   members, so the mechanism is not an edge case, it is present in every
   panel. TNA never notices, because it solves force balance on the
   network as given, not elastic stiffness; a linear FEA solve must have a
   stiffness matrix that is not singular. The fix is BeamElement instead of
   TrussElement: a small bending stiffness suppresses the shear mechanism
   in every panel, and the rotational restraints from fix 1 are no longer
   needed or wanted, because a beam already stiffens its own end rotations,
   and adding a restraint on top of that would spuriously stiffen the
   parasitic bending path.

The caller keeps this an axial check by choosing a slender section: at the
area this project uses, the ratio of bending stiffness to axial stiffness
(EI/L^3 over EA/L) works out to about 5e-4, so the bending path carries a
negligible share of the load and the comparison still falsifies exactly
what it exists to falsify, loads, supports, units and extraction, not
bending behaviour.

The comparison can never be tighter than the file it is checking. The
exported Trial 2 solve closes to a global force error of 2.406 kN on 190 kN
of applied load, so the tolerance is read from the file's own diagnostic
rather than hard-coded.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ananke_fea import mesh as reader
from ananke_fea.materials import MaterialPreset, elastic_isotropic
from ananke_fea.model import ShellModel

# The residual is a lower bound on what we can resolve. Allow a margin above
# it so that ordinary solver noise does not read as disagreement.
TOLERANCE_MARGIN = 2.0

# A quad thrust net is statically indeterminate and admits self-stress
# states, so TNA's member forces and the elastic solve's member forces are
# different, equally valid members of the same equilibrium family: they
# need not match bar by bar even when everything about the setup is
# correct. This is reported back to callers verbatim, not just explained
# here, because "the numbers differ" reads as a failure without it.
MEMBER_NOTE = (
    "Per-member equality with TNA is only expected on statically "
    "determinate networks. This network admits self-stress, so the "
    "elastic and TNA distributions may legitimately differ member by "
    "member while both equilibrate the same loads. The reaction check "
    "is the wiring falsifier here; the member statistics are reported "
    "for scale."
)

# A beam's frame vector must not be parallel to its own axis, or the cross
# product the backend takes to build the local z-axis degenerates to zero.
# Global Z is not parallel to almost every bar in a thrust network, so it is
# the default; the exception is a bar close enough to vertical that global Z
# nearly IS its axis, where global X is used instead. "Close enough" is
# taken as within 5 degrees of vertical.
_VERTICAL_COS_THRESHOLD = 0.996


def _beam_frame(start: Sequence[float], end: Sequence[float]) -> List[float]:
    """Pick a frame vector for a beam from start to end, never parallel to it."""

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = (dx * dx + dy * dy + dz * dz) ** 0.5
    if length and abs(dz / length) > _VERTICAL_COS_THRESHOLD:
        return [1.0, 0.0, 0.0]
    return [0.0, 0.0, 1.0]


def build_bar_model(
    contract: Mapping[str, Any],
    preset: MaterialPreset,
    area: float,
    name: str = "thrust",
) -> ShellModel:
    """Build a slender beam frame from the exported thrust network."""

    from ananke_fea.compat import apply_patches

    apply_patches()

    from compas_fea2.model import BeamElement, CircularSection, FixedBC, Model, Node, Part

    model = Model(name=name)
    part = Part(name="{}_bars".format(name))

    points = reader.vertices(contract)
    nodes: Dict[int, object] = {}
    for index, point in enumerate(points):
        node = Node(xyz=list(point))
        part.add_node(node)
        nodes[index] = node

    material = elastic_isotropic(preset)
    radius = (area / 3.141592653589793) ** 0.5
    section = CircularSection(r=radius, material=material)

    for start, end in reader.edges(contract):
        part.add_element(
            BeamElement(
                nodes=[nodes[start], nodes[end]],
                section=section,
                frame=_beam_frame(points[start], points[end]),
            )
        )

    model.add_part(part)

    # Supports still take every DOF. Free nodes take none here: a beam
    # stiffens rotation as well as translation at both of its own ends, so
    # nothing needs restraining on top of that, and restraining it would
    # only stiffen the parasitic bending path this model is not meant to
    # exercise.
    support_ids = reader.support_node_ids(contract)
    supports = [nodes[index] for index in support_ids]
    if supports:
        model.add_bcs(FixedBC(), nodes=supports)

    return ShellModel(model=model, part=part, nodes=nodes, supports=supports)


def member_axial_forces(
    built: ShellModel,
    contract: Mapping[str, Any],
    outcome,
    area: float,
    modulus: float,
) -> List[float]:
    """Axial force per member from the solved displacement field, in newtons.

    The backend cannot record truss section forces: requesting
    SectionForcesFieldResults never gets a recorder written into the Tcl,
    and the stress XML comes back with empty Data for Truss elements. What
    does extract reliably is nodal displacement, and for a linear truss
    N = (E A / L) x axial elongation is exact, not an approximation, so
    that is the channel used here. Negative is compression, matching the
    export's positive_tension convention.
    """

    displacements: Dict[object, Tuple[float, float, float]] = {}
    for result in outcome.step.displacement_field.results:
        displacements[result.node] = tuple(float(v) for v in result.vector)

    points = reader.vertices(contract)
    forces: List[float] = []
    for start, end in reader.edges(contract):
        ax, ay, az = points[start]
        bx, by, bz = points[end]
        dx, dy, dz = bx - ax, by - ay, bz - az
        length = (dx * dx + dy * dy + dz * dz) ** 0.5
        ux, uy, uz = dx / length, dy / length, dz / length
        da = displacements[built.nodes[start]]
        db = displacements[built.nodes[end]]
        elongation = (db[0] - da[0]) * ux + (db[1] - da[1]) * uy + (db[2] - da[2]) * uz
        forces.append(modulus * area / length * elongation)
    return forces


def cross_check(
    contract: Mapping[str, Any],
    outcome,
    tolerance: Optional[float] = None,
    reactions: Optional[Tuple[float, float, float]] = None,
    axial_forces: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Compare the solved reactions, and optionally the solved member forces,
    against what the file itself reports.

    Two verdicts are reported because they falsify different things.
    `reactions_agree` is the global equilibrium check: reacted load against
    factored applied load, within tolerance. It is the wiring falsifier,
    the thing this whole model exists to prove, and it is what `agrees`
    reports. `strict_agrees` additionally requires `members_agree`
    (`reactions_agree and members_agree`), for callers that want the
    older, stricter meaning. Per-member equality is only guaranteed on a
    statically determinate network, and this package has no determinacy
    detector, so a member mismatch alone does not fail `agrees` once the
    reactions already balance; see `member_note` in the result, present
    whenever axial_forces was supplied.

    Parameters
    ----------
    reactions
        The summed reaction vector in newtons. Passed explicitly so this can
        be checked without a solve; when omitted it is read from the step.
    tolerance
        Newtons. Defaults to the file's own global force error, widened by
        TOLERANCE_MARGIN.
    axial_forces
        Per-member axial force in newtons, in the same order as
        mesh.edges(contract), typically from member_axial_forces. Optional:
        without it, only the global reaction check runs. Must have the same
        length as mesh.member_forces(contract); a mismatch raises ValueError
        rather than silently comparing a truncated pair via zip.
    """

    residual = reader.residual_norm(contract)
    if tolerance is None:
        tolerance = (residual or 0.0) * TOLERANCE_MARGIN
        # A file with no diagnostic still needs a usable floor.
        tolerance = max(tolerance, reader.applied_total(contract) * 0.01)

    if reactions is None:
        from ananke_fea.results import reaction_summary

        reactions = tuple(reaction_summary(outcome.step)["total"])

    applied = reader.applied_total(contract)
    magnitude = sum(component**2 for component in reactions) ** 0.5
    factor = getattr(outcome, "combination_factor", 1.0)

    reactions_agree = abs(magnitude - applied * factor) <= tolerance

    result: Dict[str, Any] = {
        "tolerance": tolerance,
        "residual_from_file": residual,
        "applied_magnitude": applied * factor,
        "reaction_magnitude": magnitude,
        "difference": abs(magnitude - applied * factor),
        "reactions_agree": reactions_agree,
        # This is the wiring falsifier: see the docstring for why a member
        # mismatch alone does not override it.
        "agrees": reactions_agree,
    }

    if axial_forces is not None:
        tna_forces = reader.member_forces(contract)
        if len(axial_forces) != len(tna_forces):
            raise ValueError(
                "axial_forces has {} members but the contract reports {}".format(
                    len(axial_forces), len(tna_forces)
                )
            )

        # The TNA forces in the file are unfactored: they close equilibrium
        # at the real applied load. run_static's combination factor scales
        # the solved response the same way it scales the reactions above
        # (applied_magnitude is the unfactored contract total times factor,
        # for the same reason), so the TNA side is scaled up here rather
        # than the solved side scaled down.
        expected = [force * factor for force in tna_forces]
        differences = [
            abs(got - want) for got, want in zip(axial_forces, expected)
        ]
        member_count = len(differences)
        max_difference = max(differences) if differences else 0.0
        mean_difference = sum(differences) / member_count if member_count else 0.0
        # Reusing the same tolerance as the global reaction check is
        # deliberately generous for a single member: the file's residual is
        # a whole-network force-balance error, spread over every member in
        # the mesh, so it is a loose bound on any one member's difference.
        members_agree = max_difference <= tolerance

        result["member_count"] = member_count
        result["max_member_difference"] = max_difference
        result["mean_member_difference"] = mean_difference
        result["members_agree"] = members_agree
        result["member_note"] = MEMBER_NOTE
        # The stricter, older meaning, kept for callers that want it. Not
        # what "agrees" reports: see the docstring and MEMBER_NOTE for why
        # a member mismatch does not by itself override an agreeing
        # reaction check.
        result["strict_agrees"] = reactions_agree and members_agree

    return result
