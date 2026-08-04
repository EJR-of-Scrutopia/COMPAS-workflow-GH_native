"""A truss model of the thrust network, for checking the FEA setup itself.

The point of this model is not to predict anything. It is to be solved
under the same loads as the shell and compared against the member forces
TNA already reported. Agreement means the loads, supports, units and
extraction are all wired up correctly, and the shell result can be believed.
Disagreement means the fault is in the setup, not in the vault.

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


def build_bar_model(
    contract: Mapping[str, Any],
    preset: MaterialPreset,
    area: float,
    name: str = "thrust",
) -> ShellModel:
    """Build a pin-jointed truss from the exported thrust network."""

    from ananke_fea.compat import apply_patches

    apply_patches()

    from compas_fea2.model import CircularSection, Model, Node, Part
    from compas_fea2.model import FixedBC, GeneralBC, TrussElement

    model = Model(name=name)
    part = Part(name="{}_bars".format(name))

    nodes: Dict[int, object] = {}
    for index, point in enumerate(reader.vertices(contract)):
        node = Node(xyz=list(point))
        part.add_node(node)
        nodes[index] = node

    material = elastic_isotropic(preset)
    radius = (area / 3.141592653589793) ** 0.5
    section = CircularSection(r=radius, material=material)

    for start, end in reader.edges(contract):
        part.add_element(
            TrussElement(nodes=[nodes[start], nodes[end]], section=section)
        )

    model.add_part(part)

    support_ids = reader.support_node_ids(contract)
    supports = [nodes[index] for index in support_ids]
    if supports:
        model.add_bcs(FixedBC(), nodes=supports)

    # A truss element carries no rotational stiffness, so a model built
    # entirely from TrussElement is singular in every rotational DOF: the
    # backend writes the OpenSees domain as `model -ndm 3 -ndf 6` regardless
    # of element type, and nothing couples to xx/yy/zz anywhere in the mesh.
    # Restraining rotations at every node that is not already a support
    # removes exactly those singular DOFs. It changes no translation, no
    # force and no displacement, because no element stiffness term ever
    # referenced a rotational DOF in the first place.
    support_id_set = set(support_ids)
    free = [node for index, node in nodes.items() if index not in support_id_set]
    if free:
        model.add_bcs(
            GeneralBC(x=False, y=False, z=False, xx=True, yy=True, zz=True),
            nodes=free,
        )

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

    reaction_agrees = abs(magnitude - applied * factor) <= tolerance

    result: Dict[str, Any] = {
        "tolerance": tolerance,
        "residual_from_file": residual,
        "applied_magnitude": applied * factor,
        "reaction_magnitude": magnitude,
        "difference": abs(magnitude - applied * factor),
        "agrees": reaction_agrees,
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
        # Task 10's consumer of this dict should read members_agree with
        # that in mind rather than treating it as a tight per-member check.
        members_agree = max_difference <= tolerance

        result["member_count"] = member_count
        result["max_member_difference"] = max_difference
        result["mean_member_difference"] = mean_difference
        result["members_agree"] = members_agree
        result["agrees"] = reaction_agrees and members_agree

    return result
