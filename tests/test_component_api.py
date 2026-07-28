"""Contract tests for the Rhino-independent v0.1 component boundary."""

from types import SimpleNamespace

import pytest

from ananke_equilibrium.contracts import FDConfig
from ananke_equilibrium.contracts import HeightControl
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
