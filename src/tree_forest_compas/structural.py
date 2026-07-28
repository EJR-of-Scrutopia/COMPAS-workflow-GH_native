"""Neutral structural handoff for equilibrium networks.

The form-finding result remains the source of truth.  This module turns its
vertices, edges, signed axial forces, and support keys into an immutable
``StructuralBundle`` before any downstream representation is created.

``compas_model`` elements are optional, explicitly sized geometric previews.
The IFC adapter creates axis-only ``IfcMember`` objects by default and stores
the equilibrium values as informational property data.  Neither adapter is a
finite-element analysis.

There are deliberately no Rhino imports and all optional COMPAS dependencies
are imported lazily.  The neutral bundle and its validation therefore work in
plain Python as well as Rhino's CPython environment.
"""

import importlib
import importlib.util
import math
from typing import NamedTuple


class StructuralHandoffError(ValueError):
    """Raised when an equilibrium network cannot form a valid handoff."""


class MissingAnalysisBackendError(ImportError):
    """Raised when a requested analysis backend is unavailable."""


class StructuralNode(NamedTuple):
    """One immutable node in a structural handoff."""

    key: object
    xyz: tuple
    is_support: bool


class StructuralMember(NamedTuple):
    """One immutable axial member and its solved equilibrium result."""

    index: int
    u: object
    v: object
    start: tuple
    end: tuple
    length: float
    axial_force: float
    force_state: str


class StructuralBundle(NamedTuple):
    """Validated, library-neutral equilibrium data.

    Positive force means tension when ``tension_positive`` is true.  The
    opposite convention can be declared explicitly for upstream solvers that
    use positive compression.
    """

    nodes: tuple
    members: tuple
    support_keys: tuple
    length_unit: str
    force_unit: str
    tension_positive: bool
    source: str
    report: str

    @property
    def vertices(self):
        """Node coordinates in the same order as :attr:`nodes`."""
        return tuple(node.xyz for node in self.nodes)

    @property
    def vertex_keys(self):
        """Node keys in the same order as :attr:`nodes`."""
        return tuple(node.key for node in self.nodes)

    @property
    def edges(self):
        """Member endpoint keys in the same order as :attr:`members`."""
        return tuple((member.u, member.v) for member in self.members)

    @property
    def axial_forces(self):
        """Signed axial forces in the same order as :attr:`members`."""
        return tuple(member.axial_force for member in self.members)

    @property
    def sign_convention(self):
        """Human-readable sign convention."""
        if self.tension_positive:
            return "positive=tension; negative=compression"
        return "positive=compression; negative=tension"


class SourceVertexMapping(NamedTuple):
    """Provenance link from one source vertex to an active bundle node.

    ``bundle_node_key`` and ``solver_node_key`` are ``None`` when TNA boundary
    conditioning removed the source vertex from the solved pattern.
    """

    source_id: object
    source_point: tuple
    solver_node_key: object
    bundle_node_key: object
    status: str


class SourceMemberMapping(NamedTuple):
    """Provenance link from one source member to an active bundle member."""

    source_id: object
    source_edge: tuple
    solver_edge: object
    bundle_member_index: object
    status: str
    role: str


class NodalVector(NamedTuple):
    """A vector and its application point, both in world coordinates."""

    node_key: object
    point: tuple
    vector: tuple


class StructuralAnalysisCase(NamedTuple):
    """Immutable neutral analysis provenance around a structural bundle.

    The bundle contains only active solved topology.  This case additionally
    retains source correspondence, including removed TNA members, plus the
    exact selected source support IDs, loads and solver results needed to
    understand how that bundle was made. It is an exchange contract, not a
    finite-element model.
    """

    bundle: StructuralBundle
    analysis_kind: str
    solver: str
    load_case: str
    source_vertex_mappings: tuple
    source_member_mappings: tuple
    source_support_ids: tuple
    member_source_ids: tuple
    member_force_densities: tuple
    member_roles: tuple
    source_nodal_loads: tuple
    nodal_loads: tuple
    nodal_reactions: tuple
    nodal_residuals: tuple
    diagnostics: tuple
    provenance: tuple
    report: str

    @property
    def removed_source_member_ids(self):
        """IDs of source members omitted from the active solved bundle."""
        return tuple(
            mapping.source_id
            for mapping in self.source_member_mappings
            if mapping.status == "removed"
        )


class CompasModelHandoff(NamedTuple):
    """A ``compas_model`` preview and its stable source mapping."""

    model: object
    elements: tuple
    member_index_to_guid: tuple
    bundle: StructuralBundle
    width: float
    depth: float
    report: str


class IFCMemberSpec(NamedTuple):
    """Neutral instructions for one physical IFC member."""

    member_index: int
    ifc_class: str
    name: str
    u: object
    v: object
    start: tuple
    end: tuple
    length: float
    axial_force: float
    force_state: str
    start_is_support: bool
    end_is_support: bool


class IFCFormulation(NamedTuple):
    """IFC-facing data that can be reviewed before creating an IFC model."""

    schema: str
    project_name: str
    length_unit: str
    force_unit: str
    sign_convention: str
    source: str
    members: tuple
    support_keys: tuple
    report: str


class IFCModelHandoff(NamedTuple):
    """An in-memory ``compas_ifc`` model and its source mapping."""

    model: object
    elements: tuple
    member_index_to_global_id: tuple
    formulation: IFCFormulation
    body_included: bool
    report: str


class BackendStatus(NamedTuple):
    """Availability of an optional downstream backend."""

    available: bool
    module: str
    version: str
    message: str


class FEAReadiness(NamedTuple):
    """Readiness audit for a future finite-element analysis handoff."""

    ready: bool
    backend: BackendStatus
    missing_inputs: tuple
    report: str


def _point3(value, label):
    try:
        if hasattr(value, "x") and hasattr(value, "y"):
            coords = (
                float(value.x),
                float(value.y),
                float(getattr(value, "z", 0.0)),
            )
        else:
            values = list(value)
            if len(values) < 2:
                raise StructuralHandoffError(
                    "{} needs at least X and Y coordinates.".format(label)
                )
            coords = (
                float(values[0]),
                float(values[1]),
                float(values[2]) if len(values) > 2 else 0.0,
            )
    except StructuralHandoffError:
        raise
    except (TypeError, ValueError):
        raise StructuralHandoffError("{} is not a numeric point.".format(label))
    if not all(math.isfinite(value) for value in coords):
        raise StructuralHandoffError(
            "{} contains a non-finite coordinate.".format(label)
        )
    return coords


def _vertex_items(vertices):
    if vertices is None:
        raise StructuralHandoffError("Vertices are required.")
    if hasattr(vertices, "items"):
        items = list(vertices.items())
    else:
        items = list(enumerate(vertices))
    if not items:
        raise StructuralHandoffError("At least one vertex is required.")
    return items


def _force_state(value, tolerance, tension_positive):
    if abs(value) <= tolerance:
        return "zero"
    is_tension = value > 0.0 if tension_positive else value < 0.0
    return "tension" if is_tension else "compression"


def _freeze_neutral(value):
    """Recursively convert metadata to immutable, dependency-free values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "items"):
        return tuple(
            (str(key), _freeze_neutral(item))
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_neutral(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(
            sorted(
                (_freeze_neutral(item) for item in value),
                key=repr,
            )
        )
    return repr(value)


def _load_case_label(value):
    label = "equilibrium" if value is None else str(value).strip()
    if not label:
        raise StructuralHandoffError("A non-empty load-case label is required.")
    return label


def _normalise_member_roles(value, member_source_ids):
    """Return roles aligned one-to-one with active bundle members.

    A mapping is interpreted as ``source_member_id -> role``.  Coincident
    source members mapped to one active member must not declare conflicting
    roles.  A sequence is active-member aligned; a string is broadcast.
    """
    count = len(member_source_ids)
    if value is None:
        return tuple("unspecified" for _ in range(count))
    if isinstance(value, str):
        role = value.strip() or "unspecified"
        return tuple(role for _ in range(count))
    if hasattr(value, "items"):
        output = []
        for source_ids in member_source_ids:
            declared = {
                str(value[source_id]).strip() or "unspecified"
                for source_id in source_ids
                if source_id in value
            }
            if len(declared) > 1:
                raise StructuralHandoffError(
                    "Source members {} mapped to one active member have "
                    "conflicting roles: {}.".format(
                        source_ids, sorted(declared)
                    )
                )
            output.append(next(iter(declared)) if declared else "unspecified")
        return tuple(output)
    try:
        roles = tuple(str(role).strip() or "unspecified" for role in value)
    except TypeError:
        raise StructuralHandoffError(
            "member_roles must be a role string, source-ID mapping, or "
            "active-member-aligned sequence."
        )
    if len(roles) != count:
        raise StructuralHandoffError(
            "member_roles count {} does not match active member count {}."
            .format(len(roles), count)
        )
    return roles


def _source_role(source_id, bundle_member_index, role_input, aligned_roles):
    if hasattr(role_input, "items") and source_id in role_input:
        return str(role_input[source_id]).strip() or "unspecified"
    if bundle_member_index is None:
        return "unspecified"
    return aligned_roles[int(bundle_member_index)]


def _analysis_plane(session):
    metadata = getattr(session, "metadata", {}) or {}
    plane = metadata.get("analysis_plane", {}) if hasattr(metadata, "get") else {}
    if not plane:
        return None
    try:
        return {
            "origin": _point3(plane["origin"], "analysis_plane origin"),
            "xaxis": _point3(plane["xaxis"], "analysis_plane xaxis"),
            "yaxis": _point3(plane["yaxis"], "analysis_plane yaxis"),
            "zaxis": _point3(plane["zaxis"], "analysis_plane zaxis"),
        }
    except (KeyError, TypeError) as error:
        raise StructuralHandoffError(
            "analysis_plane metadata is incomplete: {}.".format(error)
        )


def _world_point(coordinates, plane):
    point = _point3(coordinates, "analysis point")
    if not plane:
        return point
    return tuple(
        plane["origin"][index]
        + point[0] * plane["xaxis"][index]
        + point[1] * plane["yaxis"][index]
        + point[2] * plane["zaxis"][index]
        for index in range(3)
    )


def _world_vector(vector, plane):
    xyz = _point3(vector, "analysis vector")
    if not plane:
        return xyz
    return tuple(
        xyz[0] * plane["xaxis"][index]
        + xyz[1] * plane["yaxis"][index]
        + xyz[2] * plane["zaxis"][index]
        for index in range(3)
    )


def _edge_token(edge):
    try:
        u, v = edge
        return frozenset((u, v))
    except (TypeError, ValueError):
        raise StructuralHandoffError(
            "Solver edge {!r} is not a two-key pair.".format(edge)
        )


def _nodal_vector(node_key, point, vector, plane=None):
    return NodalVector(
        node_key=node_key,
        point=_world_point(point, None),
        vector=_world_vector(vector, plane),
    )


def make_structural_bundle(
    vertices,
    edges,
    axial_forces,
    support_keys=(),
    length_unit="m",
    force_unit="kN",
    tension_positive=True,
    source="equilibrium",
    geometric_tolerance=1e-9,
    force_zero_tolerance=1e-9,
):
    """Validate explicit network data and create a neutral structural bundle.

    Parameters
    ----------
    vertices : sequence[point] | mapping[key, point]
        Vertex coordinates.  A sequence receives integer keys.
    edges : sequence[tuple[key, key]]
        Undirected axial members.
    axial_forces : sequence[float]
        Signed solved member forces, aligned one-to-one with ``edges``.
    support_keys : sequence[key], optional
        Keys of equilibrium supports.  This does not imply any FEA restraint
        degrees of freedom.
    length_unit, force_unit : str, optional
        Declared units; no conversion is performed.
    tension_positive : bool, optional
        Sign convention for ``axial_forces``.
    source : str, optional
        Upstream solver or workflow label.
    geometric_tolerance : float, optional
        Minimum permitted member length.
    force_zero_tolerance : float, optional
        Absolute force threshold used only to classify the force state.
    """
    try:
        geometric_tolerance = float(geometric_tolerance)
        force_zero_tolerance = float(force_zero_tolerance)
    except (TypeError, ValueError):
        raise StructuralHandoffError("Tolerances must be numeric.")
    if geometric_tolerance < 0.0 or force_zero_tolerance < 0.0:
        raise StructuralHandoffError("Tolerances cannot be negative.")
    if not isinstance(length_unit, str) or not length_unit.strip():
        raise StructuralHandoffError("A non-empty length unit is required.")
    if not isinstance(force_unit, str) or not force_unit.strip():
        raise StructuralHandoffError("A non-empty force unit is required.")
    if not isinstance(source, str) or not source.strip():
        raise StructuralHandoffError("A non-empty source label is required.")

    coordinates = {}
    ordered_keys = []
    for key, point in _vertex_items(vertices):
        try:
            hash(key)
        except TypeError:
            raise StructuralHandoffError(
                "Vertex key {!r} is not hashable.".format(key)
            )
        if key in coordinates:
            raise StructuralHandoffError(
                "Duplicate vertex key {!r}.".format(key)
            )
        coordinates[key] = _point3(point, "Vertex {!r}".format(key))
        ordered_keys.append(key)

    edge_list = [] if edges is None else list(edges)
    force_list = [] if axial_forces is None else list(axial_forces)
    if not edge_list:
        raise StructuralHandoffError("At least one edge is required.")
    if len(force_list) != len(edge_list):
        raise StructuralHandoffError(
            "Axial-force count {} does not match edge count {}.".format(
                len(force_list), len(edge_list)
            )
        )

    supports = () if support_keys is None else tuple(support_keys)
    for key in supports:
        try:
            hash(key)
        except TypeError:
            raise StructuralHandoffError(
                "Support key {!r} is not hashable.".format(key)
            )
    if len(set(supports)) != len(supports):
        raise StructuralHandoffError("Support keys contain duplicates.")
    unknown_supports = [key for key in supports if key not in coordinates]
    if unknown_supports:
        raise StructuralHandoffError(
            "Unknown support keys: {}.".format(unknown_supports)
        )

    members = []
    seen_edges = set()
    for index, edge in enumerate(edge_list):
        try:
            u, v = edge
        except (TypeError, ValueError):
            raise StructuralHandoffError(
                "Edge {} is not a two-key pair.".format(index)
            )
        if u not in coordinates or v not in coordinates:
            raise StructuralHandoffError(
                "Edge {} references an unknown vertex.".format(index)
            )
        if u == v:
            raise StructuralHandoffError(
                "Edge {} is a self-edge at {!r}.".format(index, u)
            )
        canonical = frozenset((u, v))
        if canonical in seen_edges:
            raise StructuralHandoffError(
                "Edge {} duplicates an existing undirected member.".format(index)
            )
        seen_edges.add(canonical)

        try:
            force = float(force_list[index])
        except (TypeError, ValueError):
            raise StructuralHandoffError(
                "Axial force {} is not numeric.".format(index)
            )
        if not math.isfinite(force):
            raise StructuralHandoffError(
                "Axial force {} is not finite.".format(index)
            )

        start = coordinates[u]
        end = coordinates[v]
        length = math.sqrt(
            (end[0] - start[0]) ** 2
            + (end[1] - start[1]) ** 2
            + (end[2] - start[2]) ** 2
        )
        if length <= geometric_tolerance:
            raise StructuralHandoffError(
                "Edge {} is zero-length within tolerance.".format(index)
            )
        members.append(
            StructuralMember(
                index=index,
                u=u,
                v=v,
                start=start,
                end=end,
                length=length,
                axial_force=force,
                force_state=_force_state(
                    force, force_zero_tolerance, bool(tension_positive)
                ),
            )
        )

    support_set = set(supports)
    nodes = tuple(
        StructuralNode(
            key=key,
            xyz=coordinates[key],
            is_support=key in support_set,
        )
        for key in ordered_keys
    )
    state_counts = {
        state: sum(member.force_state == state for member in members)
        for state in ("tension", "compression", "zero")
    }
    sign = (
        "positive=tension; negative=compression"
        if tension_positive
        else "positive=compression; negative=tension"
    )
    report = (
        "Neutral structural handoff ready\n"
        "Source: {}\n"
        "Nodes/members/supports: {}/{}/{}\n"
        "Force states T/C/0: {}/{}/{}\n"
        "Units: {} and {}\n"
        "Sign convention: {}"
    ).format(
        source,
        len(nodes),
        len(members),
        len(supports),
        state_counts["tension"],
        state_counts["compression"],
        state_counts["zero"],
        length_unit,
        force_unit,
        sign,
    )
    return StructuralBundle(
        nodes=nodes,
        members=tuple(members),
        support_keys=supports,
        length_unit=length_unit,
        force_unit=force_unit,
        tension_positive=bool(tension_positive),
        source=source,
        report=report,
    )


def structural_bundle_from_compas_graph(
    graph,
    edges=None,
    force_attribute="_f",
    support_attribute="is_support",
    **kwargs
):
    """Extract an explicit bundle from a COMPAS-style network or diagram.

    The adapter is intentionally duck-typed.  It uses ``edge_force(edge)``
    when available (as in equilibrium diagrams), otherwise it reads
    ``edge_attribute(edge, force_attribute)``.
    """
    if graph is None:
        raise StructuralHandoffError("A COMPAS graph or diagram is required.")
    try:
        vertex_keys = tuple(graph.vertices())
        selected_edges = tuple(edges) if edges is not None else tuple(graph.edges())
        vertices = {
            key: tuple(graph.vertex_coordinates(key)) for key in vertex_keys
        }
    except (AttributeError, TypeError, ValueError) as error:
        raise StructuralHandoffError(
            "Object does not provide the required COMPAS graph API: {}".format(
                error
            )
        )

    forces = []
    for edge in selected_edges:
        value = None
        edge_force = getattr(graph, "edge_force", None)
        if callable(edge_force):
            value = edge_force(edge)
        if value is None:
            try:
                value = graph.edge_attribute(edge, force_attribute)
            except (AttributeError, KeyError, TypeError):
                value = None
        if value is None:
            raise StructuralHandoffError(
                "No axial force found for edge {!r}; expected edge_force() "
                "or attribute {!r}.".format(edge, force_attribute)
            )
        forces.append(value)

    supports = []
    for key in vertex_keys:
        try:
            fixed = graph.vertex_attribute(key, support_attribute)
        except (AttributeError, KeyError, TypeError):
            fixed = False
        if fixed:
            supports.append(key)

    return make_structural_bundle(
        vertices=vertices,
        edges=selected_edges,
        axial_forces=forces,
        support_keys=supports,
        **kwargs
    )


def structural_bundle_from_tna_session(
    session,
    length_unit="m",
    force_unit="kN",
    source="COMPAS TNA",
    **kwargs
):
    """Create a neutral bundle from a solved ``TNASession``.

    Active form-diagram keys are retained as bundle keys.  The session remains
    available separately for its stable source-to-form mapping and reactions.
    """
    if session is None:
        raise StructuralHandoffError("A solved TNA session is required.")
    try:
        edges = tuple(session.edge_forces)
        plane = _analysis_plane(session)
        vertices = {
            key: _world_point(session.form.vertex_coordinates(key), plane)
            for key in session.form.vertices()
        }
        forces = tuple(session.edge_forces[edge] for edge in edges)
        supports = tuple(session.support_form_keys)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise StructuralHandoffError(
            "Object does not provide the solved TNASession contract: {}".format(
                error
            )
        )
    return make_structural_bundle(
        vertices=vertices,
        edges=edges,
        axial_forces=forces,
        support_keys=supports,
        length_unit=length_unit,
        force_unit=force_unit,
        tension_positive=True,
        source=source,
        **kwargs
    )


def structural_bundle_from_fd_session(
    session,
    length_unit="m",
    force_unit="kN",
    source="COMPAS FD",
    **kwargs
):
    """Create a neutral bundle from a solved ``FDSession``."""

    if session is None:
        raise StructuralHandoffError("A solved FD session is required.")
    try:
        vertices = tuple(tuple(point) for point in session.equilibrium_vertices)
        edges = tuple(tuple(edge) for edge in session.source_edges)
        forces = tuple(float(value) for value in session.member_forces)
        supports = tuple(session.fixed)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise StructuralHandoffError(
            "Object does not provide the solved FDSession contract: {}".format(
                error
            )
        )
    return make_structural_bundle(
        vertices=vertices,
        edges=edges,
        axial_forces=forces,
        support_keys=supports,
        length_unit=length_unit,
        force_unit=force_unit,
        tension_positive=True,
        source=source,
        **kwargs
    )


def _form_residual(form, key):
    try:
        values = form.vertex_attributes(key, ["_rx", "_ry", "_rz"])
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise StructuralHandoffError(
            "Could not read TNA residual at node {!r}: {}.".format(key, error)
        )
    if values is None:
        values = (0.0, 0.0, 0.0)
    return tuple(float(value or 0.0) for value in values)


def analysis_case_from_tna_session(
    session,
    load_case="equilibrium",
    member_roles=None,
    length_unit="m",
    force_unit="kN",
):
    """Preserve a solved TNA session as a neutral immutable analysis case.

    The active ``StructuralBundle`` uses form-diagram keys.  Source mappings
    retain every registered source member; members removed by
    ``update_boundaries`` have ``bundle_member_index=None`` and
    ``status="removed"``.
    """
    load_case = _load_case_label(load_case)
    bundle = structural_bundle_from_tna_session(
        session,
        length_unit=length_unit,
        force_unit=force_unit,
    )
    plane = _analysis_plane(session)

    try:
        source_vertex_order = tuple(session.source_vertex_order)
        source_vertices = session.source_vertices
        source_to_form = session.source_to_form
        form_to_sources = session.form_to_sources
        source_edges = session.source_edges
        source_edge_to_form = session.source_edge_to_form
        source_support_ids = tuple(session.support_keys)
        edge_q = session.edge_q
        effective_form_loads = session.effective_form_loads
        source_nodal_pz = session.source_nodal_pz
        support_reactions = session.support_reactions_by_form
        diagnostics_input = session.diagnostics
        metadata_input = session.metadata
    except AttributeError as error:
        raise StructuralHandoffError(
            "Object does not provide the solved TNA provenance contract: {}."
            .format(error)
        )

    member_by_edge = {
        _edge_token((member.u, member.v)): member.index
        for member in bundle.members
    }
    source_ids_by_member = [[] for _ in bundle.members]
    active_edge_by_source = {}
    for source_id in source_edges:
        solver_edge = source_edge_to_form.get(source_id)
        member_index = (
            member_by_edge.get(_edge_token(solver_edge))
            if solver_edge is not None
            else None
        )
        active_edge_by_source[source_id] = (
            tuple(solver_edge) if solver_edge is not None else None,
            member_index,
        )
        if member_index is not None:
            source_ids_by_member[member_index].append(source_id)
    member_source_ids = tuple(
        tuple(source_ids) for source_ids in source_ids_by_member
    )

    force_densities = []
    q_by_edge = {_edge_token(edge): value for edge, value in edge_q.items()}
    for member in bundle.members:
        token = _edge_token((member.u, member.v))
        if token not in q_by_edge:
            raise StructuralHandoffError(
                "TNA force density is missing for active member {}."
                .format(member.index)
            )
        value = float(q_by_edge[token])
        if not math.isfinite(value):
            raise StructuralHandoffError(
                "TNA force density is non-finite for active member {}."
                .format(member.index)
            )
        force_densities.append(value)
    force_densities = tuple(force_densities)
    roles = _normalise_member_roles(member_roles, member_source_ids)

    bundle_node_keys = set(bundle.vertex_keys)
    source_vertex_mappings = []
    for source_id in source_vertex_order:
        solver_key = source_to_form.get(source_id)
        bundle_key = solver_key if solver_key in bundle_node_keys else None
        merged_sources = (
            tuple(form_to_sources.get(solver_key, ()))
            if bundle_key is not None
            else ()
        )
        if bundle_key is None:
            status = "removed"
            solver_key = None
        elif len(merged_sources) > 1:
            status = "merged"
        else:
            status = "active"
        source_vertex_mappings.append(
            SourceVertexMapping(
                source_id=source_id,
                source_point=_world_point(source_vertices[source_id], plane),
                solver_node_key=solver_key,
                bundle_node_key=bundle_key,
                status=status,
            )
        )

    source_member_mappings = []
    for source_id, source_edge in source_edges.items():
        solver_edge, member_index = active_edge_by_source[source_id]
        if member_index is None:
            status = "removed"
        elif len(member_source_ids[member_index]) > 1:
            status = "merged"
        else:
            status = "active"
        source_member_mappings.append(
            SourceMemberMapping(
                source_id=source_id,
                source_edge=tuple(source_edge),
                solver_edge=solver_edge,
                bundle_member_index=member_index,
                status=status,
                role=_source_role(
                    source_id, member_index, member_roles, roles
                ),
            )
        )

    unknown_source_supports = [
        source_id
        for source_id in source_support_ids
        if source_id not in source_to_form
    ]
    if unknown_source_supports:
        raise StructuralHandoffError(
            "TNA source supports are absent from the source mapping: {}."
            .format(unknown_source_supports)
        )
    inactive_source_supports = [
        source_id
        for source_id in source_support_ids
        if source_to_form[source_id] not in set(bundle.support_keys)
    ]
    if inactive_source_supports:
        raise StructuralHandoffError(
            "TNA source supports do not map to active bundle supports: {}."
            .format(inactive_source_supports)
        )

    point_by_key = {node.key: node.xyz for node in bundle.nodes}
    source_nodal_loads = tuple(
        _nodal_vector(
            source_id,
            _world_point(source_vertices[source_id], plane),
            _world_vector(
                (0.0, 0.0, float(source_nodal_pz.get(source_id, 0.0))),
                plane,
            ),
        )
        for source_id in source_vertex_order
    )
    nodal_loads = tuple(
        _nodal_vector(
            node.key,
            node.xyz,
            _world_vector(
                effective_form_loads.get(node.key, (0.0, 0.0, 0.0)),
                plane,
            ),
        )
        for node in bundle.nodes
    )
    nodal_reactions = tuple(
        _nodal_vector(
            key,
            point_by_key[key],
            _world_vector(support_reactions[key], plane),
        )
        for key in session.support_form_keys
        if key in point_by_key
    )
    support_set = set(bundle.support_keys)
    nodal_residuals = tuple(
        _nodal_vector(
            node.key,
            node.xyz,
            _world_vector(_form_residual(session.form, node.key), plane),
        )
        for node in bundle.nodes
        if node.key not in support_set
    )

    diagnostics = (
        (
            "_coordinate_statement",
            "raw COMPAS TNA diagnostics; vector aggregates use registered "
            "analysis-plane XYZ",
        ),
    ) + tuple(
        (str(key), _freeze_neutral(value))
        for key, value in diagnostics_input.items()
    )
    provenance = (
        ("session_type", type(session).__name__),
        ("source_kind", str(getattr(session, "source_kind", "unknown"))),
        ("metadata", _freeze_neutral(metadata_input)),
        (
            "coordinate_statement",
            "nodal point/vector fields are world-coordinate values; raw "
            "diagnostic vector aggregates retain analysis-plane XYZ",
        ),
    )
    removed_count = sum(
        mapping.status == "removed" for mapping in source_member_mappings
    )
    report = (
        "Neutral TNA analysis case ready\n"
        "Load case: {}\n"
        "Active/source/removed members: {}/{}/{}\n"
        "Member force densities and roles: {}/{} aligned\n"
        "Loads/reactions/free residuals: {}/{}/{}\n"
        "This preserves form-finding provenance; it is not a full FEA."
    ).format(
        load_case,
        len(bundle.members),
        len(source_member_mappings),
        removed_count,
        len(force_densities),
        len(roles),
        len(nodal_loads),
        len(nodal_reactions),
        len(nodal_residuals),
    )
    return StructuralAnalysisCase(
        bundle=bundle,
        analysis_kind="thrust_network",
        solver="COMPAS TNA",
        load_case=load_case,
        source_vertex_mappings=tuple(source_vertex_mappings),
        source_member_mappings=tuple(source_member_mappings),
        source_support_ids=source_support_ids,
        member_source_ids=member_source_ids,
        member_force_densities=force_densities,
        member_roles=roles,
        source_nodal_loads=source_nodal_loads,
        nodal_loads=nodal_loads,
        nodal_reactions=nodal_reactions,
        nodal_residuals=nodal_residuals,
        diagnostics=diagnostics,
        provenance=provenance,
        report=report,
    )


def analysis_case_from_fd_session(
    session,
    load_case="equilibrium",
    member_roles=None,
    length_unit="m",
    force_unit="kN",
):
    """Preserve a solved FD session as a neutral immutable analysis case."""
    load_case = _load_case_label(load_case)
    bundle = structural_bundle_from_fd_session(
        session,
        length_unit=length_unit,
        force_unit=force_unit,
    )
    try:
        source_vertices = tuple(session.source_vertices)
        equilibrium_vertices = tuple(session.equilibrium_vertices)
        source_edges = tuple(session.source_edges)
        force_densities = tuple(
            float(value) for value in session.force_densities
        )
        loads = tuple(session.loads)
        reactions = tuple(session.support_reactions)
        residuals = tuple(session.residuals)
        fixed = tuple(session.fixed)
        components = tuple(session.components)
    except AttributeError as error:
        raise StructuralHandoffError(
            "Object does not provide the solved FD provenance contract: {}."
            .format(error)
        )
    count = len(bundle.members)
    aligned_counts = {
        "source edges": len(source_edges),
        "force densities": len(force_densities),
        "loads": len(loads),
        "reactions": len(reactions),
        "residuals": len(residuals),
    }
    if aligned_counts["source edges"] != count:
        raise StructuralHandoffError(
            "FD source-edge count does not match the active bundle."
        )
    if aligned_counts["force densities"] != count:
        raise StructuralHandoffError(
            "FD force-density count does not match the active bundle."
        )
    node_count = len(bundle.nodes)
    for label in ("loads", "reactions", "residuals"):
        if aligned_counts[label] != node_count:
            raise StructuralHandoffError(
                "FD {} count does not match the active bundle.".format(label)
            )
    if any(not math.isfinite(value) for value in force_densities):
        raise StructuralHandoffError(
            "FD force densities contain a non-finite value."
        )

    member_source_ids = tuple((index,) for index in range(count))
    roles = _normalise_member_roles(member_roles, member_source_ids)
    source_vertex_mappings = tuple(
        SourceVertexMapping(
            source_id=index,
            source_point=_point3(point, "FD source vertex {}".format(index)),
            solver_node_key=index,
            bundle_node_key=index,
            status="active",
        )
        for index, point in enumerate(source_vertices)
    )
    source_member_mappings = tuple(
        SourceMemberMapping(
            source_id=index,
            source_edge=tuple(edge),
            solver_edge=tuple(edge),
            bundle_member_index=index,
            status="active",
            role=_source_role(index, index, member_roles, roles),
        )
        for index, edge in enumerate(source_edges)
    )

    point_by_key = {node.key: node.xyz for node in bundle.nodes}
    source_nodal_loads = tuple(
        _nodal_vector(index, source_vertices[index], loads[index])
        for index in range(node_count)
    )
    nodal_loads = tuple(
        _nodal_vector(index, equilibrium_vertices[index], loads[index])
        for index in range(node_count)
    )
    fixed_set = set(fixed)
    nodal_reactions = tuple(
        _nodal_vector(index, point_by_key[index], reactions[index])
        for index in fixed
    )
    nodal_residuals = tuple(
        _nodal_vector(index, point_by_key[index], residuals[index])
        for index in range(node_count)
        if index not in fixed_set
    )

    def vector_sum(vectors):
        return tuple(
            sum(float(vector[index]) for vector in vectors)
            for index in range(3)
        )

    load_sum = vector_sum(loads)
    reaction_sum = vector_sum(tuple(reactions[index] for index in fixed))
    global_error = tuple(
        load_sum[index] + reaction_sum[index] for index in range(3)
    )
    max_free_residual = max(
        (
            math.sqrt(sum(float(value) ** 2 for value in residuals[index]))
            for index in range(node_count)
            if index not in fixed_set
        ),
        default=0.0,
    )
    diagnostics = (
        ("component_count", len(components)),
        ("support_count", len(fixed)),
        ("max_free_residual", max_free_residual),
        ("load_sum", load_sum),
        ("reaction_sum", reaction_sum),
        ("global_force_error", global_error),
        (
            "global_force_error_norm",
            math.sqrt(sum(value * value for value in global_error)),
        ),
    )
    provenance = (
        ("session_type", type(session).__name__),
        ("source_kind", "welded_lines"),
        ("solver_function", "compas_fd.solvers.fd_numpy"),
        ("components", _freeze_neutral(components)),
        (
            "coordinate_statement",
            "points and vectors in this case are world-coordinate values",
        ),
    )
    report = (
        "Neutral FD analysis case ready\n"
        "Load case: {}\n"
        "Active/source members: {}/{}\n"
        "Member force densities and roles: {}/{} aligned\n"
        "Loads/reactions/free residuals: {}/{}/{}\n"
        "This preserves force-density provenance; it is not a full FEA."
    ).format(
        load_case,
        count,
        len(source_member_mappings),
        len(force_densities),
        len(roles),
        len(nodal_loads),
        len(nodal_reactions),
        len(nodal_residuals),
    )
    return StructuralAnalysisCase(
        bundle=bundle,
        analysis_kind="force_density",
        solver="COMPAS FD",
        load_case=load_case,
        source_vertex_mappings=source_vertex_mappings,
        source_member_mappings=source_member_mappings,
        source_support_ids=fixed,
        member_source_ids=member_source_ids,
        member_force_densities=force_densities,
        member_roles=roles,
        source_nodal_loads=source_nodal_loads,
        nodal_loads=nodal_loads,
        nodal_reactions=nodal_reactions,
        nodal_residuals=nodal_residuals,
        diagnostics=diagnostics,
        provenance=provenance,
        report=report,
    )


def _member_axes(member):
    zx = member.end[0] - member.start[0]
    zy = member.end[1] - member.start[1]
    zz = member.end[2] - member.start[2]
    inverse = 1.0 / member.length
    zaxis = (zx * inverse, zy * inverse, zz * inverse)

    reference = (0.0, 0.0, 1.0)
    if abs(zaxis[2]) > 0.9:
        reference = (1.0, 0.0, 0.0)
    xaxis = (
        reference[1] * zaxis[2] - reference[2] * zaxis[1],
        reference[2] * zaxis[0] - reference[0] * zaxis[2],
        reference[0] * zaxis[1] - reference[1] * zaxis[0],
    )
    xlength = math.sqrt(sum(value * value for value in xaxis))
    xaxis = tuple(value / xlength for value in xaxis)
    yaxis = (
        zaxis[1] * xaxis[2] - zaxis[2] * xaxis[1],
        zaxis[2] * xaxis[0] - zaxis[0] * xaxis[2],
        zaxis[0] * xaxis[1] - zaxis[1] * xaxis[0],
    )
    return xaxis, yaxis, zaxis


def build_compas_model(
    bundle,
    width,
    depth=None,
    name="Tree Forest Equilibrium Preview",
):
    """Create explicitly sized ``BeamElement`` previews in ``compas_model``.

    ``width`` and ``depth`` are mandatory design assumptions.  No material,
    connection, section resistance, or analysis model is inferred.
    """
    if not isinstance(bundle, StructuralBundle):
        raise StructuralHandoffError(
            "build_compas_model expects a StructuralBundle."
        )
    try:
        width = float(width)
        depth = width if depth is None else float(depth)
    except (TypeError, ValueError):
        raise StructuralHandoffError("Member width and depth must be numeric.")
    if not math.isfinite(width) or not math.isfinite(depth):
        raise StructuralHandoffError("Member width and depth must be finite.")
    if width <= 0.0 or depth <= 0.0:
        raise StructuralHandoffError("Member width and depth must be positive.")

    try:
        from compas.geometry import Frame
        from compas.geometry import Transformation
        from compas_model.elements import BeamElement
        from compas_model.models import Model
    except ImportError as error:
        raise MissingAnalysisBackendError(
            "compas_model is unavailable in this Python environment: {}".format(
                error
            )
        )

    model = Model(name=name)
    elements = []
    mapping = []
    for member in bundle.members:
        xaxis, yaxis, _ = _member_axes(member)
        frame = Frame(member.start, xaxis, yaxis)
        element = BeamElement(
            width=width,
            depth=depth,
            length=member.length,
            transformation=Transformation.from_frame(frame),
            name="member_{:04d}_{}".format(
                member.index, member.force_state
            ),
        )
        model.add_element(element)
        elements.append(element)
        mapping.append((member.index, str(element.guid)))

    report = (
        "compas_model geometric preview ready\n"
        "Members: {}\n"
        "Rectangular preview section: {:.6g} x {:.6g} {}\n"
        "No material, connection, resistance, or FEA behaviour was assigned."
    ).format(len(elements), width, depth, bundle.length_unit)
    return CompasModelHandoff(
        model=model,
        elements=tuple(elements),
        member_index_to_guid=tuple(mapping),
        bundle=bundle,
        width=width,
        depth=depth,
        report=report,
    )


def make_ifc_formulation(
    bundle,
    schema="IFC4",
    project_name="Tree Forest Equilibrium",
    ifc_class="IfcMember",
):
    """Create a reviewable IFC formulation without writing an IFC file.

    ``IfcMember`` is used as a physical coordination object.  The solved axial
    forces are informational properties, not an IFC structural-analysis model.
    """
    if not isinstance(bundle, StructuralBundle):
        raise StructuralHandoffError(
            "make_ifc_formulation expects a StructuralBundle."
        )
    schema = str(schema).upper()
    if schema not in ("IFC2X3", "IFC4", "IFC4X3"):
        raise StructuralHandoffError(
            "IFC schema must be IFC2X3, IFC4, or IFC4X3."
        )
    if not isinstance(project_name, str) or not project_name.strip():
        raise StructuralHandoffError("A non-empty IFC project name is required.")
    if not isinstance(ifc_class, str) or not ifc_class.startswith("Ifc"):
        raise StructuralHandoffError(
            "IFC member class must be an Ifc-prefixed class name."
        )
    if ifc_class.startswith("IfcStructural"):
        raise StructuralHandoffError(
            "This boundary does not create IFC structural-analysis entities. "
            "Use a physical class such as IfcMember."
        )

    support_set = set(bundle.support_keys)
    members = tuple(
        IFCMemberSpec(
            member_index=member.index,
            ifc_class=ifc_class,
            name="member_{:04d}_{}".format(
                member.index, member.force_state
            ),
            u=member.u,
            v=member.v,
            start=member.start,
            end=member.end,
            length=member.length,
            axial_force=member.axial_force,
            force_state=member.force_state,
            start_is_support=member.u in support_set,
            end_is_support=member.v in support_set,
        )
        for member in bundle.members
    )
    report = (
        "IFC coordination formulation ready\n"
        "Schema/class: {}/{}\n"
        "Members/support keys: {}/{}\n"
        "Geometry: axis-only until an optional body section is supplied\n"
        "Equilibrium forces are informational properties, not engineering "
        "analysis entities."
    ).format(schema, ifc_class, len(members), len(bundle.support_keys))
    return IFCFormulation(
        schema=schema,
        project_name=project_name,
        length_unit=bundle.length_unit,
        force_unit=bundle.force_unit,
        sign_convention=bundle.sign_convention,
        source=bundle.source,
        members=members,
        support_keys=bundle.support_keys,
        report=report,
    )


def _ifc_properties(spec, formulation):
    return {
        "AE_EquilibriumResult": {
            "MemberIndex": int(spec.member_index),
            "StartNode": str(spec.u),
            "EndNode": str(spec.v),
            "SignedAxialForce": float(spec.axial_force),
            "ForceUnit": formulation.force_unit,
            "ForceState": spec.force_state,
            "SignConvention": formulation.sign_convention,
            "Source": formulation.source,
            "StartIsSupport": bool(spec.start_is_support),
            "EndIsSupport": bool(spec.end_is_support),
            "ResultOnly": True,
        }
    }


def build_ifc_model(formulation, body_section=None):
    """Create an in-memory ``compas_ifc`` BIM from a reviewed formulation.

    Parameters
    ----------
    formulation : :class:`IFCFormulation`
        Reviewable boundary generated by :func:`make_ifc_formulation`.
    body_section : tuple[float, float], optional
        Explicit width and depth.  If omitted, each member receives only an
        IFC axis representation.  Supplying a section adds a rectangular body.

    Notes
    -----
    This function does not save a file.  The caller must explicitly call
    ``handoff.model.save(path)`` after reviewing the formulation.
    """
    if not isinstance(formulation, IFCFormulation):
        raise StructuralHandoffError(
            "build_ifc_model expects an IFCFormulation."
        )
    if formulation.length_unit not in ("m", "cm", "mm"):
        raise StructuralHandoffError(
            "compas_ifc supports m, cm, or mm project length units; got {!r}."
            .format(formulation.length_unit)
        )

    section = None
    if body_section is not None:
        try:
            width, depth = body_section
            width = float(width)
            depth = float(depth)
        except (TypeError, ValueError):
            raise StructuralHandoffError(
                "body_section must contain numeric width and depth."
            )
        if (
            not math.isfinite(width)
            or not math.isfinite(depth)
            or width <= 0.0
            or depth <= 0.0
        ):
            raise StructuralHandoffError(
                "IFC body-section dimensions must be finite and positive."
            )
        section = (width, depth)

    try:
        from compas.geometry import Box
        from compas.geometry import Frame
        from compas.geometry import Line
        from compas_ifc.bim import BuildingInformationModel
    except ImportError as error:
        raise MissingAnalysisBackendError(
            "compas_ifc is unavailable in this Python environment: {}".format(
                error
            )
        )

    model = BuildingInformationModel.template(
        schema=formulation.schema,
        building_count=1,
        storey_count=1,
        unit=formulation.length_unit,
        name=formulation.project_name,
    )
    storey = model.storeys[0]
    elements = []
    mapping = []
    for spec in formulation.members:
        geometry = None
        if section is not None:
            member = StructuralMember(
                index=spec.member_index,
                u=spec.u,
                v=spec.v,
                start=spec.start,
                end=spec.end,
                length=spec.length,
                axial_force=spec.axial_force,
                force_state=spec.force_state,
            )
            xaxis, yaxis, _ = _member_axes(member)
            midpoint = tuple(
                0.5 * (a + b) for a, b in zip(spec.start, spec.end)
            )
            geometry = Box(
                xsize=section[0],
                ysize=section[1],
                zsize=spec.length,
                frame=Frame(midpoint, xaxis, yaxis),
            )

        element = model.create_element(
            ifc_type=spec.ifc_class,
            parent=storey,
            geometry=geometry,
            properties=_ifc_properties(spec, formulation),
            name=spec.name,
        )
        # Keep the solved member line independently of any optional body.
        element.ifc_entity.axis = Line(spec.start, spec.end)
        elements.append(element)
        mapping.append((spec.member_index, element.global_id))

    report = (
        "In-memory compas_ifc coordination model ready\n"
        "Members: {}\n"
        "Axis representations: {}\n"
        "Rectangular bodies: {}\n"
        "No file was written and no IFC structural-analysis model was claimed."
    ).format(
        len(elements),
        len(elements),
        len(elements) if section is not None else 0,
    )
    return IFCModelHandoff(
        model=model,
        elements=tuple(elements),
        member_index_to_global_id=tuple(mapping),
        formulation=formulation,
        body_included=section is not None,
        report=report,
    )


def compas_fea2_status():
    """Return the availability of ``compas_fea2`` without installing it."""
    module_name = "compas_fea2"
    try:
        specification = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError) as error:
        return BackendStatus(
            available=False,
            module=module_name,
            version="",
            message="Could not inspect compas_fea2: {}".format(error),
        )
    if specification is None:
        return BackendStatus(
            available=False,
            module=module_name,
            version="",
            message=(
                "compas_fea2 is not installed in this Python environment. "
                "The neutral bundle remains usable for a dedicated FEA "
                "environment."
            ),
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        return BackendStatus(
            available=False,
            module=module_name,
            version="",
            message="compas_fea2 was found but could not import: {}".format(error),
        )
    version = str(getattr(module, "__version__", "unknown"))
    return BackendStatus(
        available=True,
        module=module_name,
        version=version,
        message="compas_fea2 {} is importable.".format(version),
    )


def require_compas_fea2():
    """Import ``compas_fea2`` or raise a precise backend error."""
    status = compas_fea2_status()
    if not status.available:
        raise MissingAnalysisBackendError(status.message)
    return importlib.import_module(status.module)


def assess_fea_readiness(
    bundle,
    material=None,
    section=None,
    nodal_loads=None,
    support_dofs=None,
    load_combinations=None,
):
    """Audit the information needed before a real FEA adapter is written.

    Solved axial forces are results (or possible initial-state targets), not
    substitutes for loads, stiffness, restraints, or load combinations.
    """
    analysis_case = None
    if isinstance(bundle, StructuralAnalysisCase):
        analysis_case = bundle
        bundle = analysis_case.bundle
        if nodal_loads is None:
            nodal_loads = analysis_case.nodal_loads
    if not isinstance(bundle, StructuralBundle):
        raise StructuralHandoffError(
            "assess_fea_readiness expects a StructuralBundle or "
            "StructuralAnalysisCase."
        )
    backend = compas_fea2_status()
    missing = []
    if not backend.available:
        missing.append("compas_fea2 backend")
    if material is None:
        missing.append("member material/stiffness")
    if section is None:
        missing.append("member section properties")
    if nodal_loads is None:
        missing.append("analysis load cases")
    if support_dofs is None:
        missing.append("support restraint degrees of freedom")
    if load_combinations is None:
        missing.append("load combinations")
    report = (
        "FEA handoff {}\n"
        "Missing: {}\n"
        "Neutral load case: {}\n"
        "Equilibrium axial forces remain result data; they do not replace "
        "loads, stiffness, supports, or code checks."
    ).format(
        "ready for adapter implementation" if not missing else "not ready",
        ", ".join(missing) if missing else "none",
        analysis_case.load_case if analysis_case is not None else "not retained",
    )
    return FEAReadiness(
        ready=not missing,
        backend=backend,
        missing_inputs=tuple(missing),
        report=report,
    )
