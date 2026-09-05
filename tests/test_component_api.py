"""Contract tests for the Rhino-independent v0.1 component boundary."""

from types import SimpleNamespace

import pytest

from ananke_equilibrium.contracts import FDConfig
from ananke_equilibrium.contracts import HeightControl
from ananke_equilibrium.contracts import LoadCase
from ananke_equilibrium.contracts import TopologyBundle
from ananke_equilibrium.contracts import TNAConfig
from ananke_equilibrium.gh import build_load_case
from ananke_equilibrium.gh import build_network
from ananke_equilibrium.gh import build_preview_payload
from ananke_equilibrium.gh import build_support_set
from ananke_equilibrium.gh import make_diagram_style
from ananke_equilibrium.gh import solve_fd
from ananke_equilibrium.gh import solve_tna
from ananke_equilibrium.gh import validate_result


def _value(result):
    assert result.ok, result.status.message
    assert result.value is not None
    return result.value


def test_import_and_network_registration_are_host_independent():
    topology = _value(
        build_network(
            [
                ((0, 0, 0), (1, 0, 0)),
                ((1.0 + 1e-8, 0, 0), (2, 0, 0)),
            ],
            tolerance=1e-6,
        )
    )
    assert topology.kind == "line"
    assert len(topology.vertices) == 3
    assert topology.edges == ((0, 1), (1, 2))


def test_invalid_network_returns_friendly_status():
    result = build_network(None)
    assert not result.ok
    assert result.value is None
    assert "Network:" in result.status.message


def test_load_case_broadcasts_and_supports_remain_solver_neutral():
    topology = _value(
        build_network(
            [
                ((0, 0, 0), (1, 0, 0)),
                ((1, 0, 0), (2, 0, 0)),
            ]
        )
    )
    supports = _value(
        build_support_set(node_ids=[0, 2], topology=topology)
    )
    loads = _value(
        build_load_case(
            vectors=[(0, 0, -5)],
            node_ids=[1, 2],
            name="Dead",
            topology=topology,
        )
    )
    assert supports.node_ids == (0, 2)
    assert supports.topology_hash == topology.topology_hash
    assert loads.name == "Dead"
    assert loads.topology_hash == topology.topology_hash
    assert loads.vectors == ((0.0, 0.0, -5.0),) * 2


def test_fd_solve_uses_injected_backend_before_optional_compas_imports():
    topology = _value(
        build_network(
            [
                ((0, 0, 0), (1, -1, 0)),
                ((1, -1, 0), (2, 0, 0)),
            ]
        )
    )
    supports = _value(build_support_set(node_ids=[0, 2]))
    loads = _value(build_load_case(vectors=[(0, -1, 0)], node_ids=[1]))
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            equilibrium_vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
            source_edges=((0, 1), (1, 2)),
            member_forces=(1.0, 1.0),
            force_densities=(1.0, 1.0),
            support_reactions=((0, 1, 0), (0, 0, 0), (0, 1, 0)),
            residuals=((0, 0, 0), (0, 1e-10, 0), (0, 0, 0)),
            fixed=(0, 2),
            loads=((0, 0, 0), (0, -1, 0), (0, 0, 0)),
            report="Injected FD solve complete.",
        )

    solved = _value(
        solve_fd(
            topology,
            supports,
            loads,
            FDConfig(),
            backend=backend,
        )
    )
    assert calls
    assert solved.solver == "fd"
    assert solved.member_forces == (1.0, 1.0)
    assert solved.topology == topology.topology

    diagram = _value(build_preview_payload(solved))
    assert len(diagram.primitives) == 2
    assert all(item.geometry_type == "line" for item in diagram.primitives)

    diagnostics = _value(validate_result(solved))
    residual = next(
        item for item in diagnostics if item.code == "equilibrium.residual"
    )
    assert residual.value == pytest.approx(1.0e-10)


def test_fd_solve_accepts_a_faced_topologys_registered_edges():
    topology = TopologyBundle(
        kind="faced",
        vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
        edges=((0, 1), (1, 2), (2, 0)),
        faces=((0, 1, 2),),
    )
    supports = _value(build_support_set(node_ids=[0, 2], topology=topology))
    loads = _value(
        build_load_case(
            vectors=[(0, -1, 0)],
            node_ids=[1],
            topology=topology,
        )
    )
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            equilibrium_vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
            source_edges=((0, 1), (1, 2), (2, 0)),
            member_forces=(1.0, 1.0, 1.0),
            force_densities=(1.0, 1.0, 1.0),
            support_reactions=((0, 1, 0), (0, 0, 0), (0, 1, 0)),
            residuals=((0, 0, 0), (0, 1e-10, 0), (0, 0, 0)),
            fixed=(0, 2),
            loads=((0, 0, 0), (0, -1, 0), (0, 0, 0)),
            report="Injected faced FD solve complete.",
        )

    solved = _value(
        solve_fd(
            topology,
            supports,
            loads,
            FDConfig(),
            backend=backend,
        )
    )

    assert calls
    assert calls[0]["topology"].kind == "faced"
    assert solved.solver == "fd"
    assert solved.topology.faces == ((0, 1, 2),)


def test_tna_solve_accepts_faced_pattern_and_injected_backend():
    topology = _value(
        build_network(
            vertices=[
                (0, 0, 0),
                (1, 0, 0),
                (1, 1, 0),
                (0, 1, 0),
                (0.5, 0.5, 0),
            ],
            faces=[
                (0, 1, 4),
                (1, 2, 4),
                (2, 3, 4),
                (3, 0, 4),
            ],
            kind="faced",
        )
    )
    supports = _value(build_support_set(mode="boundary"))
    loads = _value(
        build_load_case(
            vectors=[(0, 0, -1)],
            distribution="uniform_nodes",
        )
    )

    def backend(**kwargs):
        return SimpleNamespace(
            form=None,
            edge_forces={(0, 4): -2.0},
            edge_q={(0, 4): -1.0},
            support_reactions_by_form={0: (0, 0, 1)},
            effective_form_loads={4: (0, 0, -1)},
            diagnostics={
                "global_force_error_norm": 1e-9,
                "max_reciprocal_angle_deviation": 177.9,
            },
        )

    solved = _value(
        solve_tna(
            topology,
            supports,
            loads,
            HeightControl(mode="crown_height", value=1.0),
            TNAConfig(),
            backend=backend,
        )
    )
    assert solved.solver == "tna"
    assert solved.edges == ((0, 4),)
    assert solved.member_forces == (-2.0,)
    assert solved.force_densities == (-1.0,)

    validation = validate_result(solved, angle_tolerance=3.0)
    assert validation.ok
    reciprocity = next(
        item for item in validation.value if item.code == "reciprocity.angle"
    )
    assert reciprocity.value == pytest.approx(2.1)


def test_diagram_style_preset_has_no_host_dependency():
    style = _value(make_diagram_style("analysis"))
    assert style.preset == "analysis"


# THE FD HALF OF THE 2026-09-04 LOADS MODEL, rule 2.4. Everything below
# drives `solve_fd` with a MODULE-SHAPED backend rather than a callable
# one, because a callable backend is handed the contracts and never the
# resolved records: the loads array is built inside `solve_fd` itself
# (gh/solvers.py, the `solve_fd_problem` call) and the module seam is the
# only place a test can read what the FD solver was actually given. The
# TNA path always asks for the nodal half alone, so nothing else in
# either test world executes the surface arm or its area rescaling.
UNIT_QUAD = TopologyBundle(
    kind="faced",
    vertices=((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
    edges=((0, 1), (1, 2), (2, 3), (3, 0)),
    faces=((0, 1, 2, 3),),
)


class _RecordingFdBackend:
    """An FD backend as a module, not a callable.

    `import_backend` returns anything non-None untouched and
    `call_backend` reaches a non-callable backend's methods by name, so
    an instance carrying the two method names is the module the adapter
    would otherwise import.
    """

    def __init__(self):
        self.loads = None

    def register_fd_network(self, source_lines, tolerance=1.0e-6):
        return SimpleNamespace(source_lines=tuple(source_lines))

    def solve_fd_problem(self, problem, fixed=(), forcedensities=1.0, loads=None):
        self.loads = [[float(value) for value in vector] for vector in loads]
        vertices = UNIT_QUAD.vertices
        return SimpleNamespace(
            equilibrium_vertices=vertices,
            source_edges=UNIT_QUAD.edges,
            member_forces=(1.0,) * len(UNIT_QUAD.edges),
            force_densities=(1.0,) * len(UNIT_QUAD.edges),
            support_reactions=((0, 0, 0),) * len(vertices),
            residuals=((0, 0, 0),) * len(vertices),
            fixed=tuple(fixed),
            loads=tuple(tuple(vector) for vector in loads),
            report="Recording FD solve complete.",
        )


def _fd_loads(load_case):
    """The vertical load the FD solver is handed, vertex by vertex."""

    backend = _RecordingFdBackend()
    supports = _value(build_support_set(node_ids=[0, 1], topology=UNIT_QUAD))
    _value(solve_fd(UNIT_QUAD, supports, load_case, FDConfig(), backend=backend))
    assert backend.loads is not None
    return [vector[2] for vector in backend.loads]


def _surface_case(**overrides):
    fields = {
        "name": "dead",
        "distribution": "self_weight",
        "base_vector": (0.0, 0.0, -1.0),
        "thickness": 1.0,
        "density": 1.0,
    }
    fields.update(overrides)
    return LoadCase(**fields)


def test_fd_spreads_a_surface_load_by_plan_area_times_thickness_and_density():
    """Rule 2.4(a) on the FD path.

    The unit quad's four vertices share one square metre, so a base
    vector of (0, 0, -1) at T = D = 1 is a quarter each: exactly the
    weight this canvas carried before thickness and density existed.
    """

    assert _fd_loads(_surface_case()) == pytest.approx([-0.25] * 4)


def test_fd_thickness_and_density_multiply_the_surface_load():
    """The pair is a product, so a 500 mm shell at four units weighs the
    same as a metre at two and twice what T = D = 1 weighs. Nothing on
    the FD path proved that T and D scaled its plan load at all."""

    assert _fd_loads(
        _surface_case(thickness=0.5, density=4.0)
    ) == pytest.approx([-0.5] * 4)
    assert _fd_loads(
        _surface_case(thickness=1.0, density=2.0)
    ) == pytest.approx([-0.5] * 4)


def test_fd_node_loads_ride_beside_the_surface_weight_without_double_counting():
    """Rule 2.4(b) on the FD path, the shape only the native component
    and a hand-authored payload can author: a base vector AND node IDs.
    The listed vertex carries its own tributary share PLUS the point
    load; every other vertex carries its share alone, once."""

    loads = _fd_loads(
        _surface_case(node_ids=(2,), vectors=((0.0, 0.0, -10.0),))
    )
    assert loads == pytest.approx([-0.25, -0.25, -10.25, -0.25])


def test_fd_a_surface_case_with_no_base_vector_still_weighs_every_vertex():
    """The target-free surface case, whose vectors ARE the area density
    at their own nodes. It broadcasts over every vertex and is rescaled
    by tributary area, which is the reading every canvas authored that
    way has always had; resolving it to NO LOAD AT ALL is the silent
    answer this pins against."""

    records = _fd_loads(
        LoadCase(
            name="dead",
            distribution="tributary_area",
            vectors=((0.0, 0.0, -1.0),),
        )
    )
    assert records == pytest.approx([-0.25] * 4)


def test_fd_refuses_load_vectors_that_align_with_no_target():
    """A load case whose vectors match no node is an authoring mistake
    and is refused. Answering it with an empty record set instead means
    the solve proceeds under no load at all and says nothing."""

    result = solve_fd(
        UNIT_QUAD,
        _value(build_support_set(node_ids=[0, 1], topology=UNIT_QUAD)),
        LoadCase(
            name="dead",
            distribution="point",
            vectors=((0.0, 0.0, -1.0), (0.0, 0.0, -2.0)),
        ),
        FDConfig(),
        backend=_RecordingFdBackend(),
    )
    assert not result.ok
    assert "do not align" in result.status.message
