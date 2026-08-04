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

from typing import Any, Dict, Mapping, Optional, Tuple

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
    from compas_fea2.model import PinnedBC, TrussElement

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

    supports = [nodes[index] for index in reader.support_node_ids(contract)]
    if supports:
        model.add_bcs(PinnedBC(), nodes=supports)

    return ShellModel(model=model, part=part, nodes=nodes, supports=supports)


def cross_check(
    contract: Mapping[str, Any],
    outcome,
    tolerance: Optional[float] = None,
    reactions: Optional[Tuple[float, float, float]] = None,
) -> Dict[str, Any]:
    """Compare the solved reactions against the applied load.

    Parameters
    ----------
    reactions
        The summed reaction vector in newtons. Passed explicitly so this can
        be checked without a solve; when omitted it is read from the step.
    tolerance
        Newtons. Defaults to the file's own global force error, widened by
        TOLERANCE_MARGIN.
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

    return {
        "tolerance": tolerance,
        "residual_from_file": residual,
        "applied_magnitude": applied * factor,
        "reaction_magnitude": magnitude,
        "difference": abs(magnitude - applied * factor),
        "agrees": abs(magnitude - applied * factor) <= tolerance,
    }
