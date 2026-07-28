"""Whole-system planar graphic statics with COMPAS AGS.

This module deliberately contains no Rhino or Grasshopper imports.  The line
network must already be expressed in one XY plane and must include the external
load and reaction edges required by the graphic-statics construction.
"""

from typing import NamedTuple

from compas.tolerance import TOL
import math

from compas_ags.ags import graphstatics
from compas_ags.ags.graphstatics import form_count_dof
from compas_ags.diagrams import ForceDiagram
from compas_ags.diagrams import FormDiagram
from compas_ags.diagrams import FormGraph


class AGSRegistrationError(ValueError):
    """Raised when linework cannot become one valid AGS form diagram."""


class AGSResult(NamedTuple):
    """A solved pair of reciprocal planar diagrams.

    ``source_edge_to_form_edge`` preserves the relationship between input
    line order and the corresponding COMPAS form edge.
    """

    form: FormDiagram
    force: ForceDiagram
    source_edge_to_form_edge: tuple
    source_edge_to_force_edge: tuple
    reference_source_edge: int
    reference_force: float
    independent_source_edges: tuple
    independent_forces: tuple
    nullity: int
    mechanisms: int
    form_edges: tuple
    force_edges: tuple
    form_edge_roles: tuple
    source_roles: tuple
    external_force_edges: tuple
    member_forces: tuple
    source_forces: tuple
    angle_deviations: tuple
    report: str


def _coerce_lines(lines):
    """Return line endpoint coordinates as plain 3D float lists."""
    clean = []
    for index, line in enumerate(lines or []):
        if line is None or len(line) != 2:
            raise AGSRegistrationError(
                "Source line {} is not an endpoint pair.".format(index)
            )
        points = []
        for point in line:
            if point is None or len(point) < 2:
                raise AGSRegistrationError(
                    "Source line {} contains an invalid point.".format(index)
                )
            z = float(point[2]) if len(point) > 2 else 0.0
            points.append([float(point[0]), float(point[1]), z])
        if points[0] == points[1]:
            raise AGSRegistrationError(
                "Source line {} has coincident endpoints.".format(index)
            )
        clean.append(points)
    if not clean:
        raise AGSRegistrationError("At least one line is required.")
    return clean


def _validate_xy_plane(lines, tolerance):
    zvalues = [point[2] for line in lines for point in line]
    if max(zvalues) - min(zvalues) > float(tolerance):
        raise AGSRegistrationError(
            "AGS is two-dimensional. Transform the linework to one XY plane "
            "before registration."
        )


def _source_edge_map(graph, form, lines, precision):
    gkey_node = graph.gkey_node(precision=precision)
    mapping = []
    for index, (a, b) in enumerate(lines):
        ga = TOL.geometric_key(a, precision=precision)
        gb = TOL.geometric_key(b, precision=precision)
        if ga not in gkey_node or gb not in gkey_node:
            raise AGSRegistrationError(
                "Could not preserve source edge {} after node merging.".format(index)
            )
        u = gkey_node[ga]
        v = gkey_node[gb]
        if form.has_edge((u, v)):
            mapping.append((u, v))
        elif form.has_edge((v, u)):
            mapping.append((v, u))
        else:
            raise AGSRegistrationError(
                "Source edge {} is absent from the form diagram.".format(index)
            )
    return tuple(mapping)


def solve_planar_graphic_statics(
    lines,
    reference_source_edge=0,
    reference_force=-1.0,
    independent_source_edges=None,
    independent_forces=None,
    load_source_edges=None,
    reaction_source_edges=None,
    precision=None,
    planar_tolerance=1e-6,
):
    """Build and solve one reciprocal form/force-diagram pair.

    Parameters
    ----------
    lines : sequence
        Endpoint pairs describing the complete planar system, including
        structural, load, and reaction edges.
    reference_source_edge : int, optional
        Index of the input line whose signed force magnitude is prescribed.
    reference_force : float, optional
        Signed magnitude assigned to the reference edge.
    independent_source_edges : sequence of int, optional
        Source edges whose signed forces independently scale the equilibrium
        state. When supplied, this replaces ``reference_source_edge``.
    independent_forces : sequence of float, optional
        Signed force for every independent source edge.
    load_source_edges, reaction_source_edges : sequence of int, optional
        Optional visual/semantic classification of external source edges.
    precision : int, optional
        COMPAS geometric-key precision used when merging coincident endpoints.
    planar_tolerance : float, optional
        Maximum permitted spread in input Z coordinates.

    Returns
    -------
    :class:`AGSResult`
        The paired diagrams, mappings, forces, and reciprocity diagnostics.
    """
    clean = _coerce_lines(lines)
    _validate_xy_plane(clean, planar_tolerance)

    graph = FormGraph.from_lines(clean, precision=precision)
    if not graph.is_planar_embedding():
        raise AGSRegistrationError(
            "The merged linework is not a planar embedding. Split all crossings "
            "at their intersection points before registration."
        )

    try:
        form = FormDiagram.from_graph(graph)
        force = ForceDiagram.from_formdiagram(form)
    except Exception as error:
        raise AGSRegistrationError(
            "Could not construct reciprocal diagrams: {}".format(error)
        )

    mapping = _source_edge_map(graph, form, clean, precision)
    nullity, mechanisms = form_count_dof(form)
    if mechanisms:
        raise AGSRegistrationError(
            "The planar form has {} mechanism(s). Stabilise its topology before "
            "solving graphic statics.".format(mechanisms)
        )

    if independent_source_edges is None:
        independent_indices = (int(reference_source_edge),)
        independent_values = (float(reference_force),)
    else:
        independent_indices = tuple(int(value) for value in independent_source_edges)
        if independent_forces is None:
            raise AGSRegistrationError(
                "independent_forces are required with independent_source_edges."
            )
        independent_values = tuple(float(value) for value in independent_forces)
        if len(independent_values) != len(independent_indices):
            raise AGSRegistrationError(
                "Provide one independent force per independent source edge."
            )
    if not independent_indices:
        raise AGSRegistrationError("At least one independent force is required.")
    if len(set(independent_indices)) != len(independent_indices):
        raise AGSRegistrationError("Independent source-edge indices must be unique.")
    if min(independent_indices) < 0 or max(independent_indices) >= len(mapping):
        raise AGSRegistrationError(
            "An independent edge index is outside 0..{}.".format(len(mapping) - 1)
        )
    if any(abs(value) <= 1e-12 for value in independent_values):
        raise AGSRegistrationError("Independent forces must be non-zero.")
    if len(independent_indices) != nullity:
        raise AGSRegistrationError(
            "This form has {} independent force state(s); {} value(s) were "
            "provided.".format(nullity, len(independent_indices))
        )

    reference_source_edge = independent_indices[0]
    reference_force = independent_values[0]

    def source_indices(values, label):
        output = tuple(sorted(set(int(value) for value in (values or []))))
        if output and (output[0] < 0 or output[-1] >= len(mapping)):
            raise AGSRegistrationError(
                "A {} source-edge index is outside 0..{}.".format(
                    label, len(mapping) - 1
                )
            )
        return output

    load_indices = source_indices(load_source_edges, "load")
    reaction_indices = source_indices(reaction_source_edges, "reaction")
    overlap = set(load_indices).intersection(reaction_indices)
    if overlap:
        raise AGSRegistrationError(
            "Source edges cannot be both load and reaction: {}.".format(
                ", ".join(str(value) for value in sorted(overlap))
            )
        )
    for index in load_indices:
        edge = mapping[index]
        if not form.edge_attribute(edge, "is_external"):
            raise AGSRegistrationError(
                "Load source edge {} is not an external leaf edge.".format(index)
            )
        form.edge_attribute(edge, "is_load", True)
    for index in reaction_indices:
        edge = mapping[index]
        if not form.edge_attribute(edge, "is_external"):
            raise AGSRegistrationError(
                "Reaction source edge {} is not an external leaf edge.".format(
                    index
                )
            )
        form.edge_attribute(edge, "is_reaction", True)

    try:
        for index, force_value in zip(independent_indices, independent_values):
            form.edge_force(mapping[index], force_value)
        graphstatics.form_update_q_from_qind(form)
        graphstatics.force_update_from_form(force, form)
    except Exception as error:
        raise AGSRegistrationError(
            "AGS equilibrium failed. Check external edges and static "
            "determinacy: {}".format(error)
        )

    form_edges = tuple(form.edges())
    force_edges = tuple(force.ordered_edges(form))
    form_edge_index = {}
    for index, (u, v) in enumerate(form_edges):
        form_edge_index[u, v] = index
        form_edge_index[v, u] = index
    source_to_force = tuple(
        force_edges[form_edge_index[edge]] for edge in mapping
    )

    def role(edge):
        if form.edge_attribute(edge, "is_reaction"):
            return "reaction"
        if form.edge_attribute(edge, "is_load"):
            return "load"
        if form.edge_attribute(edge, "is_external"):
            return "external"
        return "member"

    form_edge_roles = tuple(role(edge) for edge in form_edges)
    source_roles = tuple(role(edge) for edge in mapping)
    external_force_edges = tuple(
        force_edge
        for force_edge, edge_role in zip(force_edges, form_edge_roles)
        if edge_role != "member"
    )
    member_forces = tuple(float(form.edge_force(edge)) for edge in form_edges)
    source_forces = tuple(float(form.edge_force(edge)) for edge in mapping)

    def parallel_deviation(form_edge, force_edge):
        a0, a1 = form.edge_coordinates(form_edge)
        b0, b1 = force.edge_coordinates(force_edge)
        ax = float(a1[0] - a0[0])
        ay = float(a1[1] - a0[1])
        bx = float(b1[0] - b0[0])
        by = float(b1[1] - b0[1])
        denominator = math.hypot(ax, ay) * math.hypot(bx, by)
        if denominator <= 1e-15:
            return float("inf")
        sine = max(0.0, min(1.0, abs((ax * by - ay * bx) / denominator)))
        return math.degrees(math.asin(sine))

    angle_deviations = tuple(
        parallel_deviation(form_edge, force_edge)
        for form_edge, force_edge in zip(form_edges, force_edges)
    )
    max_angle = max((abs(value) for value in angle_deviations), default=0.0)
    report = (
        "COMPAS AGS solve complete\n"
        "Source lines: {}\n"
        "Form vertices/edges/faces: {}/{}/{}\n"
        "Force vertices/edges/faces: {}/{}/{}\n"
        "Independent force states / mechanisms: {} / {}\n"
        "Independent source edges: {}\n"
        "External force edges: {}\n"
        "Maximum reciprocity angle deviation: {:.3e} deg"
    ).format(
        len(clean),
        form.number_of_vertices(),
        form.number_of_edges(),
        form.number_of_faces(),
        force.number_of_vertices(),
        force.number_of_edges(),
        force.number_of_faces(),
        nullity,
        mechanisms,
        ", ".join(
            "{}={:.6g}".format(index, value)
            for index, value in zip(independent_indices, independent_values)
        ),
        len(external_force_edges),
        max_angle,
    )

    return AGSResult(
        form=form,
        force=force,
        source_edge_to_form_edge=mapping,
        source_edge_to_force_edge=source_to_force,
        reference_source_edge=reference_source_edge,
        reference_force=reference_force,
        independent_source_edges=independent_indices,
        independent_forces=independent_values,
        nullity=int(nullity),
        mechanisms=int(mechanisms),
        form_edges=form_edges,
        force_edges=force_edges,
        form_edge_roles=form_edge_roles,
        source_roles=source_roles,
        external_force_edges=external_force_edges,
        member_forces=member_forces,
        source_forces=source_forces,
        angle_deviations=angle_deviations,
        report=report,
    )
