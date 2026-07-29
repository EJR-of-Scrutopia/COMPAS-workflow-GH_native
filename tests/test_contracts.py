from __future__ import annotations

import pytest

from ananke_equilibrium.contracts import ContractError
from ananke_equilibrium.contracts import Diagnostic
from ananke_equilibrium.contracts import DiagramStyle
from ananke_equilibrium.contracts import HeightControl
from ananke_equilibrium.contracts import LoadCase
from ananke_equilibrium.contracts import SolvedCase
from ananke_equilibrium.contracts import SupportSet
from ananke_equilibrium.contracts import TopologyBundle
from ananke_equilibrium.contracts import TNAPrepareConfig


def line_topology():
    return TopologyBundle(
        kind="line",
        vertices=((0, 0, 0), (1, 0, 0), (2, 0, 0)),
        edges=((0, 1), (1, 2)),
    )


def test_topology_hash_is_deterministic_and_content_sensitive():
    first = line_topology()
    second = line_topology()
    changed = TopologyBundle(
        kind="line",
        vertices=((0, 0, 0), (1, 0, 0), (3, 0, 0)),
        edges=((0, 1), (1, 2)),
    )

    assert first.topology_hash == second.topology_hash
    assert first.topology_hash != changed.topology_hash
    assert len(first.topology_hash) == 64


def test_faced_topology_requires_faces():
    with pytest.raises(ContractError, match="requires registered faces"):
        TopologyBundle(
            kind="faced",
            vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            edges=((0, 1), (1, 2), (2, 0)),
        )


def test_topology_bound_data_rejects_cross_wiring():
    topology = line_topology()
    changed = TopologyBundle(
        kind="line",
        vertices=((0, 0, 0), (1, 0, 0), (3, 0, 0)),
        edges=((0, 1), (1, 2)),
    )
    supports = SupportSet(
        topology_hash=topology.topology_hash,
        node_ids=(0, 2),
    )

    with pytest.raises(ContractError, match="belongs to topology"):
        supports.assert_compatible(changed)


def test_solved_case_keeps_one_compact_result_contract():
    topology = line_topology()
    supports = SupportSet(
        topology_hash=topology.topology_hash,
        node_ids=(0, 2),
    )
    loads = LoadCase(
        topology_hash=topology.topology_hash,
        node_ids=(1,),
        vectors=((0, 0, -1),),
    )
    case = SolvedCase(
        solver="fd",
        topology=topology,
        support_set=supports,
        load_case=loads,
        vertices=((0, 0, 0), (1, 0, -0.5), (2, 0, 0)),
        edges=topology.edges,
        member_forces=(2.0, 2.0),
        diagnostics=(
            Diagnostic(
                code="equilibrium.residual",
                severity="ok",
                message="closed",
                value=1.0e-12,
            ),
        ),
    )

    assert case.solver_kind == "fd"
    assert case.equilibrium_vertices[1] == (1.0, 0.0, -0.5)
    assert "session" not in case.to_data()


def test_diagram_style_presets_are_validated():
    style = DiagramStyle.from_preset("Classical GS")

    assert style.preset == "classical_gs"
    assert style.colours["force"] == (20, 145, 45)
    with pytest.raises(ContractError, match="Unknown diagram preset"):
        DiagramStyle.from_preset("rainbow mystery")


def test_height_control_requires_mode_specific_data():
    assert HeightControl.crown_height(5.0).mode == "zmax"
    assert HeightControl.force_scale(-2.0).mode == "q"
    with pytest.raises(ContractError, match="requires a value"):
        HeightControl(mode="zmax")


def test_tna_prepare_config_uses_rise_over_span_and_distinct_plan_pins():
    config = TNAPrepareConfig(
        boundary_sag=0.10,
        fixed_node_ids=(2, 2, 5),
    )

    assert config.boundary_sag == pytest.approx(0.10)
    assert config.fixed_node_ids == (2, 5)
    with pytest.raises(ContractError, match="rise/span"):
        TNAPrepareConfig(boundary_sag=10.0)
