"""Versioned, Rhino-independent data contracts for the plugin.

The numerical backends remain free to use their native COMPAS objects at
runtime. These small contracts define the stable boundary between Grasshopper
components and retain enough provenance to reject accidental cross-wiring.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from hashlib import sha256
import json
from math import isfinite
from typing import Any
from typing import ClassVar
from typing import Dict
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple


SCHEMA_VERSION = "0.1"
Point3 = Tuple[float, float, float]
Edge = Tuple[int, int]


class ContractError(ValueError):
    """Raised when data cannot cross a component boundary safely."""


def _finite_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ContractError("{} must be numeric.".format(label)) from error
    if not isfinite(result):
        raise ContractError("{} must be finite.".format(label))
    return result


def _point3(value: Sequence[Any], label: str) -> Point3:
    try:
        coordinates = tuple(value)
    except TypeError as error:
        raise ContractError("{} must be a coordinate sequence.".format(label)) from error
    if len(coordinates) == 2:
        coordinates = coordinates + (0.0,)
    if len(coordinates) != 3:
        raise ContractError("{} must contain two or three values.".format(label))
    return tuple(
        _finite_float(component, "{} coordinate".format(label))
        for component in coordinates
    )


def _mapping(value: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return dict(value or {})


def _topology_fingerprint(
    kind: str,
    vertices: Tuple[Point3, ...],
    edges: Tuple[Edge, ...],
    faces: Tuple[Tuple[int, ...], ...],
) -> str:
    payload = {
        "kind": kind,
        "vertices": vertices,
        "edges": edges,
        "faces": faces,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class Contract:
    """Small JSON-oriented mixin shared by all persisted contracts."""

    schema_version: ClassVar[str] = SCHEMA_VERSION

    def to_data(self) -> Dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        return data


@dataclass(frozen=True)
class TopologyBundle(Contract):
    """One registered whole-object topology shared by all downstream stages."""

    kind: str
    vertices: Tuple[Point3, ...]
    edges: Tuple[Edge, ...]
    faces: Tuple[Tuple[int, ...], ...] = ()
    source_vertex_ids: Tuple[Any, ...] = ()
    length_unit: str = "m"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    topology_hash: str = ""

    def __post_init__(self) -> None:
        kind = str(self.kind).strip().lower()
        aliases = {
            "fd": "line",
            "network": "line",
            "lines": "line",
            "mesh": "faced",
            "tna": "faced",
            "thrust": "faced",
        }
        kind = aliases.get(kind, kind)
        if kind not in ("line", "faced"):
            raise ContractError("Topology kind must be 'line' or 'faced'.")

        vertices = tuple(
            _point3(point, "Vertex {}".format(index))
            for index, point in enumerate(self.vertices)
        )
        if not vertices:
            raise ContractError("A topology requires at least one vertex.")

        edges = []
        for index, edge in enumerate(self.edges):
            if len(edge) != 2:
                raise ContractError("Edge {} does not contain two node IDs.".format(index))
            u, v = (int(edge[0]), int(edge[1]))
            if u == v:
                raise ContractError("Edge {} is collapsed.".format(index))
            if min(u, v) < 0 or max(u, v) >= len(vertices):
                raise ContractError("Edge {} contains an invalid node ID.".format(index))
            edges.append((u, v))
        if not edges:
            raise ContractError("A topology requires at least one edge.")

        faces = []
        for index, face in enumerate(self.faces):
            cycle = tuple(int(value) for value in face)
            if len(set(cycle)) < 3:
                raise ContractError(
                    "Face {} requires at least three distinct nodes.".format(index)
                )
            if min(cycle) < 0 or max(cycle) >= len(vertices):
                raise ContractError("Face {} contains an invalid node ID.".format(index))
            faces.append(cycle)
        if kind == "faced" and not faces:
            raise ContractError("A faced topology requires registered faces.")

        source_ids = tuple(self.source_vertex_ids)
        if source_ids and len(source_ids) != len(vertices):
            raise ContractError(
                "source_vertex_ids must be empty or align with every vertex."
            )
        if not source_ids:
            source_ids = tuple(range(len(vertices)))

        length_unit = str(self.length_unit or "").strip()
        if not length_unit:
            raise ContractError("length_unit cannot be empty.")

        fingerprint = _topology_fingerprint(
            kind,
            vertices,
            tuple(edges),
            tuple(faces),
        )
        if self.topology_hash and self.topology_hash != fingerprint:
            raise ContractError(
                "The supplied topology_hash does not match the topology content."
            )

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "edges", tuple(edges))
        object.__setattr__(self, "faces", tuple(faces))
        object.__setattr__(self, "source_vertex_ids", source_ids)
        object.__setattr__(self, "length_unit", length_unit)
        object.__setattr__(self, "metadata", _mapping(self.metadata))
        object.__setattr__(self, "topology_hash", fingerprint)

    @property
    def source_lines(self) -> Tuple[Tuple[Point3, Point3], ...]:
        return tuple((self.vertices[u], self.vertices[v]) for u, v in self.edges)

    @property
    def topology(self) -> "TopologyBundle":
        """Protocol alias used by adapters that also accept wrapped topology."""

        return self


@dataclass(frozen=True)
class TopologyBoundContract(Contract):
    """Mixin for data that may be bound to a particular topology."""

    topology_hash: str = ""

    def assert_compatible(self, topology: TopologyBundle) -> None:
        if self.topology_hash and self.topology_hash != topology.topology_hash:
            raise ContractError(
                "{} belongs to topology {}, not {}.".format(
                    type(self).__name__,
                    self.topology_hash[:12],
                    topology.topology_hash[:12],
                )
            )


@dataclass(frozen=True)
class SupportSet(TopologyBoundContract):
    """Form-finding support selection.

    This deliberately does not represent finite-element restraint degrees of
    freedom; those belong to the later ``StructuralDefinition`` contract.
    """

    mode: str = "explicit"
    points: Tuple[Point3, ...] = ()
    node_ids: Tuple[int, ...] = ()
    snap_tolerance: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode = str(self.mode or "explicit").strip().lower()
        allowed = {"explicit", "terminals", "boundary", "corners"}
        if mode not in allowed:
            raise ContractError(
                "Support mode must be Explicit, Terminals, Boundary, or Corners."
            )
        points = tuple(
            _point3(point, "Support point {}".format(index))
            for index, point in enumerate(self.points)
        )
        node_ids = tuple(dict.fromkeys(int(value) for value in self.node_ids))
        if node_ids and min(node_ids) < 0:
            raise ContractError("Support node IDs cannot be negative.")
        snap = (
            _finite_float(self.snap_tolerance, "snap_tolerance")
            if self.snap_tolerance is not None
            else None
        )
        if snap is not None and snap <= 0.0:
            raise ContractError("snap_tolerance must be greater than zero.")
        if mode == "explicit" and not points and not node_ids:
            raise ContractError(
                "Explicit supports require points or registered node IDs."
            )
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "snap_tolerance", snap)
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True)
class LoadCase(TopologyBoundContract):
    """Named form-finding load data with stable topology targets."""

    name: str = "equilibrium"
    distribution: str = "point"
    points: Tuple[Point3, ...] = ()
    node_ids: Tuple[int, ...] = ()
    vectors: Tuple[Point3, ...] = ()
    records: Tuple[Mapping[str, Any], ...] = ()
    base_vector: Optional[Point3] = None
    factor: float = 1.0
    coordinate_system: str = "world"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        if not name:
            raise ContractError("A load case requires a name.")
        distribution = str(self.distribution or "point").strip().lower()
        distribution = distribution.replace(" ", "_")
        allowed = {
            "point",
            "uniform_nodes",
            "tributary_area",
            "self_weight",
            "custom",
        }
        if distribution not in allowed:
            raise ContractError("Unsupported load distribution: {}.".format(distribution))
        points = tuple(
            _point3(point, "Load point {}".format(index))
            for index, point in enumerate(self.points)
        )
        node_ids = tuple(int(value) for value in self.node_ids)
        if node_ids and min(node_ids) < 0:
            raise ContractError("Load node IDs cannot be negative.")
        vectors = tuple(
            _point3(vector, "Load vector {}".format(index))
            for index, vector in enumerate(self.vectors)
        )
        target_count = len(node_ids) or len(points)
        if node_ids and points and len(node_ids) != len(points):
            raise ContractError("Load points and node IDs must align when both are set.")
        if target_count and len(vectors) not in (1, target_count):
            raise ContractError(
                "Load vectors must contain one value or one value per target."
            )
        base_vector = (
            _point3(self.base_vector, "Base load vector")
            if self.base_vector is not None
            else None
        )
        if not vectors and base_vector is None:
            raise ContractError("A load case requires at least one vector.")
        factor = _finite_float(self.factor, "Load factor")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "distribution", distribution)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "node_ids", node_ids)
        object.__setattr__(self, "vectors", vectors)
        object.__setattr__(self, "records", tuple(dict(item) for item in self.records))
        object.__setattr__(self, "base_vector", base_vector)
        object.__setattr__(self, "factor", factor)
        object.__setattr__(
            self,
            "coordinate_system",
            str(self.coordinate_system or "world"),
        )
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True)
class FDConfig(Contract):
    """Force-density solver controls."""

    force_densities: Any = 1.0
    sign_convention: str = "positive_tension"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def force_density(self) -> Any:
        return self.force_densities

    @property
    def q(self) -> Any:
        return self.force_densities


@dataclass(frozen=True)
class HeightControl(Contract):
    """TNA vertical form-control choice."""

    mode: str = "zmax"
    value: Optional[float] = None
    target: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode = str(self.mode or "zmax").strip().lower().replace(" ", "_")
        aliases = {
            "crown_height": "zmax",
            "height": "zmax",
            "force_scale": "q",
            "q_scale": "q",
            "target_surface": "target",
        }
        mode = aliases.get(mode, mode)
        if mode not in ("zmax", "q", "target"):
            raise ContractError("Height mode must be Crown Height, Force Scale, or Target.")
        value = (
            _finite_float(self.value, "Height control value")
            if self.value is not None
            else None
        )
        if mode in ("zmax", "q") and value is None:
            raise ContractError("{} height control requires a value.".format(mode))
        if mode == "target" and self.target is None:
            raise ContractError("Target height control requires target geometry.")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def crown_height(cls, value: float) -> "HeightControl":
        return cls(mode="zmax", value=value)

    @classmethod
    def force_scale(cls, value: float) -> "HeightControl":
        return cls(mode="q", value=value)


@dataclass(frozen=True)
class TNAConfig(Contract):
    """Horizontal and vertical TNA iteration controls."""

    horizontal_alpha: float = 100.0
    horizontal_iterations: int = 100
    vertical_iterations: int = 100
    tolerance: float = 1.0e-3
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        alpha = _finite_float(self.horizontal_alpha, "horizontal_alpha")
        if not 0.0 <= alpha <= 100.0:
            raise ContractError("horizontal_alpha must be between 0 and 100.")
        horizontal = int(self.horizontal_iterations)
        vertical = int(self.vertical_iterations)
        if horizontal < 1 or vertical < 1:
            raise ContractError("TNA iteration counts must be positive.")
        tolerance = _finite_float(self.tolerance, "TNA tolerance")
        if tolerance <= 0.0:
            raise ContractError("TNA tolerance must be greater than zero.")
        object.__setattr__(self, "horizontal_alpha", alpha)
        object.__setattr__(self, "horizontal_iterations", horizontal)
        object.__setattr__(self, "vertical_iterations", vertical)
        object.__setattr__(self, "tolerance", tolerance)
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True)
class TNAPrepareConfig(Contract):
    """Plan-pattern relaxation and unsupported-boundary controls.

    ``force_density`` is the uniform positive force-density weight used for
    the initial plan FDM relaxation.  Its absolute value has no effect when all
    edges share the same value; the opening-sag matcher changes the *relative*
    force densities of unsupported boundary segments.

    ``boundary_sag`` is rise/span as a ratio (``0.10`` means ten percent).
    Structural supports and the optional ``fixed_node_ids`` are both held in
    plan during relaxation.  Only structural supports become reaction nodes in
    the later TNA vertical solve.
    """

    force_density: float = 1.0
    relax: bool = True
    boundary_sag: Optional[float] = 0.10
    sag_iterations: int = 10
    sag_tolerance: float = 0.01
    fixed_node_ids: Tuple[int, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        force_density = _finite_float(self.force_density, "force_density")
        if force_density <= 0.0:
            raise ContractError("force_density must be greater than zero.")
        boundary_sag = (
            _finite_float(self.boundary_sag, "boundary_sag")
            if self.boundary_sag is not None
            else None
        )
        if boundary_sag is not None and not 0.0 < boundary_sag <= 1.0:
            raise ContractError(
                "boundary_sag must be a rise/span ratio greater than zero "
                "and no greater than one."
            )
        iterations = int(self.sag_iterations)
        if iterations < 0:
            raise ContractError("sag_iterations cannot be negative.")
        tolerance = _finite_float(self.sag_tolerance, "sag_tolerance")
        if tolerance <= 0.0:
            raise ContractError("sag_tolerance must be greater than zero.")
        fixed = tuple(dict.fromkeys(int(value) for value in self.fixed_node_ids))
        if fixed and min(fixed) < 0:
            raise ContractError("fixed_node_ids cannot contain negative IDs.")
        object.__setattr__(self, "force_density", force_density)
        object.__setattr__(self, "relax", bool(self.relax))
        object.__setattr__(self, "boundary_sag", boundary_sag)
        object.__setattr__(self, "sag_iterations", iterations)
        object.__setattr__(self, "sag_tolerance", tolerance)
        object.__setattr__(self, "fixed_node_ids", fixed)
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True)
class PreparedTNA(Contract):
    """Stable prepared-pattern result plus an optional live COMPAS stage.

    The live ``session`` is retained only inside the Python worker so that the
    form and force diagrams can be encoded.  It is deliberately excluded from
    :meth:`to_data`.
    """

    topology: TopologyBundle
    support_set: SupportSet
    config: TNAPrepareConfig
    pattern: Mapping[str, Any] = field(default_factory=dict)
    session: Any = None
    boundary_segments: Tuple[Mapping[str, Any], ...] = ()
    diagnostics: Tuple[Diagnostic, ...] = ()
    mappings: Mapping[str, Any] = field(default_factory=dict)
    report: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.support_set.assert_compatible(self.topology)
        pattern = _mapping(self.pattern)
        required = {"kind", "vertices", "edges", "faces", "edge_force_densities"}
        missing = sorted(required - set(pattern))
        if missing:
            raise ContractError(
                "Prepared TNA pattern is missing: {}.".format(", ".join(missing))
            )
        if str(pattern["kind"]).strip().lower() != "faced":
            raise ContractError("Prepared TNA pattern kind must be 'faced'.")
        vertices = tuple(
            _point3(point, "Prepared Pattern vertex {}".format(index))
            for index, point in enumerate(pattern["vertices"])
        )
        if len(vertices) != len(self.topology.vertices):
            raise ContractError(
                "Prepared Pattern vertices must align with the stable source topology."
            )
        edges = tuple(
            (int(edge[0]), int(edge[1])) for edge in pattern["edges"]
        )
        faces = tuple(
            tuple(int(value) for value in face) for face in pattern["faces"]
        )
        q = tuple(
            _finite_float(value, "Prepared Pattern force density")
            for value in pattern["edge_force_densities"]
        )
        if len(q) != len(edges):
            raise ContractError(
                "Prepared Pattern force densities must align with its edges."
            )
        fixed = tuple(
            dict.fromkeys(
                int(value) for value in pattern.get("fixed_node_ids", ())
            )
        )
        if fixed and (min(fixed) < 0 or max(fixed) >= len(vertices)):
            raise ContractError(
                "A prepared fixed plan node ID lies outside the topology."
            )
        pattern = {
            "kind": "faced",
            "vertices": vertices,
            "edges": edges,
            "faces": faces,
            "edge_force_densities": q,
            "fixed_node_ids": fixed,
        }
        object.__setattr__(self, "pattern", pattern)
        object.__setattr__(
            self,
            "boundary_segments",
            tuple(dict(item) for item in self.boundary_segments),
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "mappings", _mapping(self.mappings))
        object.__setattr__(self, "report", str(self.report))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @property
    def supports(self) -> SupportSet:
        return self.support_set

    def to_data(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": "tna_prepared",
            "topology": self.topology.to_data(),
            "support_set": self.support_set.to_data(),
            "config": self.config.to_data(),
            "pattern": dict(self.pattern),
            "boundary_segments": self.boundary_segments,
            "diagnostics": tuple(item.to_data() for item in self.diagnostics),
            "mappings": dict(self.mappings),
            "report": self.report,
            "metadata": dict(self.metadata),
        }


_STYLE_PRESETS = {
    "analysis": {
        "colours": {
            "form": (35, 35, 35),
            "tension": (210, 45, 45),
            "compression": (35, 95, 210),
            "load": (238, 135, 35),
            "reaction": (35, 155, 75),
            "construction": (155, 155, 155),
            "error": (220, 30, 170),
        },
        "line_weights": {"form": 1.5, "force": 2.0, "construction": 0.5},
    },
    "classical_gs": {
        "colours": {
            "form": (20, 20, 20),
            "force": (20, 145, 45),
            "load": (245, 125, 20),
            "construction": (170, 170, 170),
        },
        "line_weights": {"form": 1.5, "force": 2.0, "construction": 0.5},
    },
    "monochrome": {
        "colours": {
            "form": (20, 20, 20),
            "force": (60, 60, 60),
            "construction": (175, 175, 175),
        },
        "line_weights": {"form": 1.5, "force": 1.5, "construction": 0.5},
    },
    "print": {
        "colours": {
            "form": (0, 0, 0),
            "force": (0, 0, 0),
            "construction": (145, 145, 145),
        },
        "line_weights": {"form": 2.0, "force": 2.0, "construction": 0.35},
    },
}


@dataclass(frozen=True)
class DiagramStyle(Contract):
    """Shared presentation controls, kept separate from solved mechanics."""

    preset: str = "analysis"
    colours: Mapping[str, Tuple[int, int, int]] = field(default_factory=dict)
    line_weights: Mapping[str, float] = field(default_factory=dict)
    force_scale: float = 1.0
    vector_scale: float = 1.0
    label_density: int = 1
    show_labels: bool = True
    show_construction: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        preset = str(self.preset or "analysis").strip().lower().replace(" ", "_")
        if preset not in _STYLE_PRESETS:
            raise ContractError(
                "Unknown diagram preset {!r}. Available: {}.".format(
                    preset,
                    ", ".join(sorted(_STYLE_PRESETS)),
                )
            )
        colours = {}
        for role, colour in dict(self.colours).items():
            values = tuple(int(value) for value in colour)
            if len(values) != 3 or min(values) < 0 or max(values) > 255:
                raise ContractError(
                    "Colour {!r} must contain three values from 0 to 255.".format(role)
                )
            colours[str(role)] = values
        weights = {
            str(role): _finite_float(value, "Line weight")
            for role, value in dict(self.line_weights).items()
        }
        if any(value <= 0.0 for value in weights.values()):
            raise ContractError("Line weights must be greater than zero.")
        force_scale = _finite_float(self.force_scale, "force_scale")
        vector_scale = _finite_float(self.vector_scale, "vector_scale")
        if force_scale <= 0.0 or vector_scale <= 0.0:
            raise ContractError("Display scales must be greater than zero.")
        density = int(self.label_density)
        if density < 0:
            raise ContractError("label_density cannot be negative.")
        object.__setattr__(self, "preset", preset)
        object.__setattr__(self, "colours", colours)
        object.__setattr__(self, "line_weights", weights)
        object.__setattr__(self, "force_scale", force_scale)
        object.__setattr__(self, "vector_scale", vector_scale)
        object.__setattr__(self, "label_density", density)
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @classmethod
    def from_preset(cls, name: str) -> "DiagramStyle":
        key = str(name or "analysis").strip().lower().replace(" ", "_")
        if key not in _STYLE_PRESETS:
            raise ContractError("Unknown diagram preset {!r}.".format(name))
        data = _STYLE_PRESETS[key]
        return cls(
            preset=key,
            colours=data["colours"],
            line_weights=data["line_weights"],
        )


@dataclass(frozen=True)
class Diagnostic(Contract):
    """One machine-readable validation result."""

    code: str
    severity: str
    message: str
    value: Optional[float] = None
    tolerance: Optional[float] = None
    unit: str = ""
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        severity = str(self.severity or "info").lower()
        if severity not in ("ok", "info", "warning", "error"):
            raise ContractError("Unknown diagnostic severity {!r}.".format(severity))
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(
            self,
            "value",
            _finite_float(self.value, "Diagnostic value")
            if self.value is not None
            else None,
        )
        object.__setattr__(
            self,
            "tolerance",
            _finite_float(self.tolerance, "Diagnostic tolerance")
            if self.tolerance is not None
            else None,
        )
        object.__setattr__(self, "context", _mapping(self.context))


@dataclass(frozen=True)
class SolvedCase(Contract):
    """Canonical compact result passed between analysis and display components."""

    solver: str
    topology: TopologyBundle
    support_set: SupportSet
    load_case: LoadCase
    config: Any = None
    session: Any = None
    vertices: Tuple[Point3, ...] = ()
    edges: Tuple[Edge, ...] = ()
    member_forces: Tuple[float, ...] = ()
    force_densities: Tuple[float, ...] = ()
    reactions: Tuple[Any, ...] = ()
    loads: Tuple[Any, ...] = ()
    residuals: Tuple[Any, ...] = ()
    diagnostics: Tuple[Diagnostic, ...] = ()
    report: str = ""
    mappings: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.support_set.assert_compatible(self.topology)
        self.load_case.assert_compatible(self.topology)
        vertices = tuple(
            _point3(point, "Equilibrium vertex {}".format(index))
            for index, point in enumerate(self.vertices)
        )
        edges = tuple((int(edge[0]), int(edge[1])) for edge in self.edges)
        if edges and vertices and max(max(edge) for edge in edges) >= len(vertices):
            raise ContractError("A solved edge has an invalid equilibrium node ID.")
        forces = tuple(
            _finite_float(value, "Member force") for value in self.member_forces
        )
        if edges and forces and len(edges) != len(forces):
            raise ContractError("Member forces must align with solved edges.")
        object.__setattr__(self, "solver", str(self.solver).lower())
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "member_forces", forces)
        object.__setattr__(
            self,
            "force_densities",
            tuple(_finite_float(value, "Force density") for value in self.force_densities),
        )
        object.__setattr__(self, "reactions", tuple(self.reactions))
        object.__setattr__(self, "loads", tuple(self.loads))
        object.__setattr__(self, "residuals", tuple(self.residuals))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "report", str(self.report))
        object.__setattr__(self, "mappings", _mapping(self.mappings))
        object.__setattr__(self, "metadata", _mapping(self.metadata))

    @property
    def solver_kind(self) -> str:
        return self.solver

    @property
    def equilibrium_vertices(self) -> Tuple[Point3, ...]:
        return self.vertices

    @property
    def supports(self) -> SupportSet:
        return self.support_set

    def to_data(self) -> Dict[str, Any]:
        """Serialise stable results while deliberately excluding live sessions."""

        return {
            "schema_version": self.schema_version,
            "solver": self.solver,
            "topology": self.topology.to_data(),
            "support_set": self.support_set.to_data(),
            "load_case": self.load_case.to_data(),
            "vertices": self.vertices,
            "edges": self.edges,
            "member_forces": self.member_forces,
            "force_densities": self.force_densities,
            "reactions": self.reactions,
            "loads": self.loads,
            "residuals": self.residuals,
            "diagnostics": tuple(item.to_data() for item in self.diagnostics),
            "report": self.report,
            "mappings": dict(self.mappings),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DiagramPrimitive(Contract):
    """Renderer-neutral graphic-statistics primitive."""

    role: str
    geometry_type: str
    points: Tuple[Point3, ...]
    source_ids: Tuple[Any, ...] = ()
    magnitude: Optional[float] = None
    label: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "points",
            tuple(
                _point3(point, "Diagram point {}".format(index))
                for index, point in enumerate(self.points)
            ),
        )
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(
            self,
            "magnitude",
            _finite_float(self.magnitude, "Diagram magnitude")
            if self.magnitude is not None
            else None,
        )
        object.__setattr__(self, "metadata", _mapping(self.metadata))


@dataclass(frozen=True)
class DiagramBundle(Contract):
    """A complete renderer-neutral form/force diagram payload."""

    topology: TopologyBundle
    kind: str
    dimension: int
    primitives: Tuple[DiagramPrimitive, ...] = ()
    diagnostics: Tuple[Diagnostic, ...] = ()
    mappings: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        dimension = int(self.dimension)
        if dimension not in (2, 3):
            raise ContractError("Diagram dimension must be 2 or 3.")
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "primitives", tuple(self.primitives))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "mappings", _mapping(self.mappings))
        object.__setattr__(self, "metadata", _mapping(self.metadata))


__all__ = [
    "Contract",
    "ContractError",
    "Diagnostic",
    "DiagramBundle",
    "DiagramPrimitive",
    "DiagramStyle",
    "FDConfig",
    "HeightControl",
    "LoadCase",
    "PreparedTNA",
    "SCHEMA_VERSION",
    "SolvedCase",
    "SupportSet",
    "TNAConfig",
    "TNAPrepareConfig",
    "TopologyBoundContract",
    "TopologyBundle",
]
