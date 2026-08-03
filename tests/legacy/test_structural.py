import importlib.util
import math
from pathlib import Path
import sys

import pytest

# Keep the neutral validation tests runnable in plain Python even when another
# optional package module is eagerly imported from tree_forest_compas.__init__.
try:
    from tree_forest_compas.structural import MissingAnalysisBackendError
    from tree_forest_compas.structural import StructuralHandoffError
    from tree_forest_compas.structural import StructuralAnalysisCase
    from tree_forest_compas.structural import analysis_case_from_fd_session
    from tree_forest_compas.structural import analysis_case_from_tna_session
    from tree_forest_compas.structural import assess_fea_readiness
    from tree_forest_compas.structural import build_compas_model
    from tree_forest_compas.structural import build_ifc_model
    from tree_forest_compas.structural import compas_fea2_status
    from tree_forest_compas.structural import make_ifc_formulation
    from tree_forest_compas.structural import make_structural_bundle
    from tree_forest_compas.structural import structural_bundle_from_compas_graph
    from tree_forest_compas.structural import structural_bundle_from_fd_session
    from tree_forest_compas.structural import structural_bundle_from_tna_session
except ModuleNotFoundError as error:
    if error.name != "compas":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from structural import MissingAnalysisBackendError
    from structural import StructuralHandoffError
    from structural import StructuralAnalysisCase
    from structural import analysis_case_from_fd_session
    from structural import analysis_case_from_tna_session
    from structural import assess_fea_readiness
    from structural import build_compas_model
    from structural import build_ifc_model
    from structural import compas_fea2_status
    from structural import make_ifc_formulation
    from structural import make_structural_bundle
    from structural import structural_bundle_from_compas_graph
    from structural import structural_bundle_from_fd_session
    from structural import structural_bundle_from_tna_session


def _bundle():
    return make_structural_bundle(
        vertices={
            "a": [0.0, 0.0, 0.0],
            "b": [2.0, 0.0, 0.0],
            "c": [2.0, 0.0, 3.0],
        },
        edges=[("a", "b"), ("b", "c")],
        axial_forces=[12.0, -8.0],
        support_keys=["a", "c"],
        source="test equilibrium",
    )


def test_neutral_bundle_preserves_mapping_sign_and_supports():
    bundle = _bundle()

    assert bundle.vertex_keys == ("a", "b", "c")
    assert bundle.edges == (("a", "b"), ("b", "c"))
    assert bundle.axial_forces == (12.0, -8.0)
    assert [member.force_state for member in bundle.members] == [
        "tension",
        "compression",
    ]
    assert bundle.members[0].length == pytest.approx(2.0)
    assert bundle.members[1].length == pytest.approx(3.0)
    assert [node.is_support for node in bundle.nodes] == [True, False, True]
    assert "positive=tension" in bundle.sign_convention


def test_sequence_vertices_receive_integer_keys_and_zero_state():
    bundle = make_structural_bundle(
        vertices=[[0, 0], [1, 0]],
        edges=[(0, 1)],
        axial_forces=[1e-12],
        force_zero_tolerance=1e-9,
    )

    assert bundle.vertex_keys == (0, 1)
    assert bundle.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    assert bundle.members[0].force_state == "zero"


def test_duck_typed_compas_graph_adapter_reads_forces_and_supports():
    class FakeGraph:
        def vertices(self):
            return iter(("left", "right"))

        def edges(self):
            return iter((("left", "right"),))

        def vertex_coordinates(self, key):
            return {"left": (0, 0, 0), "right": (2, 0, 0)}[key]

        def vertex_attribute(self, key, name):
            assert name == "is_support"
            return key == "left"

        def edge_force(self, edge):
            assert edge == ("left", "right")
            return -5.0

    bundle = structural_bundle_from_compas_graph(FakeGraph())

    assert bundle.edges == (("left", "right"),)
    assert bundle.axial_forces == (-5.0,)
    assert bundle.support_keys == ("left",)
    assert bundle.members[0].force_state == "compression"


def test_fd_session_adapter_preserves_solved_world_geometry():
    class FakeFDSession:
        equilibrium_vertices = ((0, 0, 0), (2, 0, 1))
        source_edges = ((0, 1),)
        member_forces = (-5.0,)
        fixed = (0,)

    bundle = structural_bundle_from_fd_session(FakeFDSession())

    assert bundle.vertices == ((0.0, 0.0, 0.0), (2.0, 0.0, 1.0))
    assert bundle.edges == ((0, 1),)
    assert bundle.axial_forces == (-5.0,)
    assert bundle.support_keys == (0,)


def test_tna_adapter_returns_geometry_in_recorded_analysis_plane():
    class FakeForm:
        def vertices(self):
            return iter((0, 1))

        def vertex_coordinates(self, key):
            return ((1, 2, 3), (2, 2, 3))[key]

    class FakeTNASession:
        form = FakeForm()
        edge_forces = {(0, 1): -4.0}
        support_form_keys = (0,)
        metadata = {
            "analysis_plane": {
                "origin": [10, 20, 30],
                "xaxis": [0, 1, 0],
                "yaxis": [-1, 0, 0],
                "zaxis": [0, 0, 1],
            }
        }

    bundle = structural_bundle_from_tna_session(FakeTNASession())

    assert bundle.vertices == ((8.0, 21.0, 33.0), (8.0, 22.0, 33.0))
    assert bundle.axial_forces == (-4.0,)


def test_fd_analysis_case_preserves_aligned_results_and_world_vectors():
    class FakeFDSession:
        source_vertices = ((0, 0, 0), (1, 0, 0), (2, 0, 0))
        source_edges = ((0, 1), (1, 2))
        equilibrium_vertices = ((0, 0, 0), (1, 0, -1), (2, 0, 0))
        member_forces = (3.0, 3.0)
        force_densities = (2.0, 2.0)
        fixed = (0, 2)
        loads = ((0, 0, 0), (0, 0, -1), (0, 0, 0))
        residuals = ((-1, 0, -0.5), (0, 0, 1e-12), (1, 0, -0.5))
        support_reactions = ((1, 0, 0.5), (0, 0, 0), (-1, 0, 0.5))
        components = ((0, 1, 2),)

    case = analysis_case_from_fd_session(
        FakeFDSession(),
        load_case="DL",
        member_roles=("cable", "cable"),
    )

    assert isinstance(case, StructuralAnalysisCase)
    assert case.bundle.vertices[1] == (1.0, 0.0, -1.0)
    assert case.load_case == "DL"
    assert case.member_source_ids == ((0,), (1,))
    assert case.source_support_ids == (0, 2)
    assert case.member_force_densities == (2.0, 2.0)
    assert case.member_roles == ("cable", "cable")
    assert case.nodal_loads[1].point == (1.0, 0.0, -1.0)
    assert case.nodal_loads[1].vector == (0.0, 0.0, -1.0)
    assert tuple(item.node_key for item in case.nodal_reactions) == (0, 2)
    assert tuple(item.node_key for item in case.nodal_residuals) == (1,)
    assert not case.removed_source_member_ids

    with pytest.raises(AttributeError):
        case.load_case = "changed"


def test_tna_analysis_case_keeps_removed_sources_and_world_vectors():
    class FakeForm:
        def vertices(self):
            return iter((10, 11))

        def vertex_coordinates(self, key):
            return {10: (1, 2, 3), 11: (2, 2, 3)}[key]

        def vertex_attributes(self, key, names):
            assert names == ["_rx", "_ry", "_rz"]
            return {10: (0, 0, 2), 11: (1, 0, 0)}[key]

    class FakeTNASession:
        form = FakeForm()
        source_kind = "vertices_faces"
        source_vertex_order = ("a", "support-alias", "b", "c")
        source_vertices = {
            "a": (1, 2, 0),
            "support-alias": (1, 2, 0),
            "b": (2, 2, 0),
            "c": (3, 2, 0),
        }
        source_to_form = {
            "a": 10,
            "support-alias": 10,
            "b": 11,
            "c": None,
        }
        form_to_sources = {
            10: ("a", "support-alias"),
            11: ("b",),
        }
        source_edges = {
            100: ("a", "b"),
            101: ("b", "c"),
        }
        source_edge_to_form = {
            100: (10, 11),
            101: None,
        }
        support_keys = ("support-alias",)
        support_form_keys = (10,)
        source_nodal_pz = {
            "a": -1.0,
            "support-alias": 0.0,
            "b": 0.0,
            "c": -1.0,
        }
        effective_form_loads = {
            10: (0, 0, -2),
            11: (0, 0, 0),
        }
        edge_q = {(10, 11): -2.0}
        edge_forces = {(10, 11): -4.0}
        support_reactions_by_form = {10: (0, 0, 2)}
        diagnostics = {
            "removed_source_edge_ids": (101,),
            "max_free_residual": 1.0,
        }
        metadata = {
            "analysis_plane": {
                "origin": [10, 20, 30],
                "xaxis": [0, 1, 0],
                "yaxis": [-1, 0, 0],
                "zaxis": [0, 0, 1],
            },
            "versions": {"compas_tna": "0.7.0"},
        }

    case = analysis_case_from_tna_session(
        FakeTNASession(),
        load_case="self-weight",
        member_roles={100: "vault", 101: "conditioned-boundary"},
    )

    assert case.bundle.vertices == (
        (8.0, 21.0, 33.0),
        (8.0, 22.0, 33.0),
    )
    assert case.member_source_ids == ((100,),)
    assert case.source_support_ids == ("support-alias",)
    assert case.member_force_densities == (-2.0,)
    assert case.member_roles == ("vault",)
    assert case.removed_source_member_ids == (101,)
    assert case.source_member_mappings[1].bundle_member_index is None
    assert case.source_member_mappings[1].status == "removed"
    assert case.source_member_mappings[1].role == "conditioned-boundary"
    assert case.source_vertex_mappings[3].status == "removed"
    assert case.nodal_loads[0].point == (8.0, 21.0, 33.0)
    assert case.nodal_loads[0].vector == (0.0, 0.0, -2.0)
    assert case.nodal_reactions[0].vector == (0.0, 0.0, 2.0)
    assert case.nodal_residuals[0].vector == (0.0, 1.0, 0.0)
    assert case.source_nodal_loads[3].point == (8.0, 23.0, 30.0)
    assert case.source_nodal_loads[3].vector == (0.0, 0.0, -1.0)
    assert isinstance(case.diagnostics, tuple)
    assert isinstance(case.provenance, tuple)


def test_analysis_case_rejects_misaligned_member_roles():
    class FakeFDSession:
        source_vertices = ((0, 0, 0), (1, 0, 0))
        source_edges = ((0, 1),)
        equilibrium_vertices = source_vertices
        member_forces = (1.0,)
        force_densities = (1.0,)
        fixed = (0,)
        loads = ((0, 0, 0), (0, 0, 0))
        residuals = ((0, 0, 0), (0, 0, 0))
        support_reactions = residuals
        components = ((0, 1),)

    with pytest.raises(StructuralHandoffError, match="member_roles count"):
        analysis_case_from_fd_session(
            FakeFDSession(), member_roles=("cable", "beam")
        )


def test_fea_readiness_recognises_case_loads_but_not_missing_design_data():
    class FakeFDSession:
        source_vertices = ((0, 0, 0), (1, 0, 0))
        source_edges = ((0, 1),)
        equilibrium_vertices = source_vertices
        member_forces = (1.0,)
        force_densities = (1.0,)
        fixed = (0,)
        loads = ((0, 0, 0), (0, 0, -1))
        residuals = ((0, 0, 1), (0, 0, 0))
        support_reactions = ((0, 0, 1), (0, 0, 0))
        components = ((0, 1),)

    case = analysis_case_from_fd_session(
        FakeFDSession(), load_case="DL"
    )
    readiness = assess_fea_readiness(case)

    assert "analysis load cases" not in readiness.missing_inputs
    assert "member material/stiffness" in readiness.missing_inputs
    assert "support restraint degrees of freedom" in readiness.missing_inputs
    assert "Neutral load case: DL" in readiness.report
    assert not readiness.ready


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"edges": [("a", "missing")]}, "unknown vertex"),
        (
            {"edges": [("a", "b"), ("b", "a")], "axial_forces": [1, 2]},
            "duplicates",
        ),
        ({"support_keys": ["missing"]}, "Unknown support"),
        ({"axial_forces": []}, "does not match"),
    ],
)
def test_bundle_rejects_invalid_networks(kwargs, message):
    data = dict(
        vertices={"a": [0, 0, 0], "b": [1, 0, 0]},
        edges=[("a", "b")],
        axial_forces=[1.0],
        support_keys=[],
    )
    data.update(kwargs)

    with pytest.raises(StructuralHandoffError, match=message):
        make_structural_bundle(**data)


def test_bundle_rejects_zero_length_and_nonfinite_force():
    with pytest.raises(StructuralHandoffError, match="zero-length"):
        make_structural_bundle(
            vertices=[[0, 0, 0], [0, 0, 0]],
            edges=[(0, 1)],
            axial_forces=[1.0],
        )

    with pytest.raises(StructuralHandoffError, match="not finite"):
        make_structural_bundle(
            vertices=[[0, 0, 0], [1, 0, 0]],
            edges=[(0, 1)],
            axial_forces=[math.inf],
        )


def test_ifc_formulation_is_reviewable_and_rejects_analysis_claim():
    formulation = make_ifc_formulation(_bundle())

    assert formulation.schema == "IFC4"
    assert len(formulation.members) == 2
    assert formulation.members[0].ifc_class == "IfcMember"
    assert formulation.members[0].start_is_support
    assert not formulation.members[0].end_is_support
    assert "informational properties" in formulation.report

    with pytest.raises(StructuralHandoffError, match="does not create IFC"):
        make_ifc_formulation(
            _bundle(), ifc_class="IfcStructuralCurveMember"
        )


def test_fea_readiness_does_not_treat_solved_force_as_analysis_input():
    readiness = assess_fea_readiness(_bundle())

    assert not readiness.ready
    assert "analysis load cases" in readiness.missing_inputs
    assert "support restraint degrees of freedom" in readiness.missing_inputs
    assert "do not replace" in readiness.report


def test_compas_fea2_detection_is_explicit():
    status = compas_fea2_status()

    assert status.module == "compas_fea2"
    if not status.available:
        assert "not installed" in status.message or "could not" in status.message


@pytest.mark.skipif(
    importlib.util.find_spec("compas_model") is None,
    reason="compas_model is tested in the Rhino COMPAS environment",
)
def test_compas_model_preview_aligns_member_centerlines():
    handoff = build_compas_model(_bundle(), width=0.1, depth=0.2)

    assert len(handoff.elements) == 2
    assert len(tuple(handoff.model.elements())) == 2
    for member, element in zip(handoff.bundle.members, handoff.elements):
        line = element.center_line.transformed(element.modeltransformation)
        assert tuple(line.start) == pytest.approx(member.start)
        assert tuple(line.end) == pytest.approx(member.end)
    assert "No material" in handoff.report


@pytest.mark.skipif(
    importlib.util.find_spec("compas_model") is not None,
    reason="missing-dependency path only",
)
def test_compas_model_missing_dependency_is_clear():
    with pytest.raises(MissingAnalysisBackendError, match="compas_model"):
        build_compas_model(_bundle(), width=0.1)


@pytest.mark.skipif(
    importlib.util.find_spec("compas_ifc") is None,
    reason="compas_ifc is tested in the Rhino COMPAS environment",
)
def test_ifc_axis_only_model_preserves_results_and_mapping():
    handoff = build_ifc_model(make_ifc_formulation(_bundle()))

    assert len(handoff.elements) == 2
    assert not handoff.body_included
    assert all(element.ifc_type == "IfcMember" for element in handoff.elements)
    assert all(element.axis is not None for element in handoff.elements)
    assert all(global_id for _, global_id in handoff.member_index_to_global_id)
    properties = handoff.elements[0].properties["AE_EquilibriumResult"]
    assert properties["SignedAxialForce"] == pytest.approx(12.0)
    assert properties["ForceState"] == "tension"
    assert properties["ResultOnly"] is True
    assert "No file was written" in handoff.report


@pytest.mark.skipif(
    importlib.util.find_spec("compas_ifc") is None,
    reason="compas_ifc is tested in the Rhino COMPAS environment",
)
def test_ifc_optional_body_requires_explicit_section():
    handoff = build_ifc_model(
        make_ifc_formulation(_bundle()), body_section=(0.1, 0.2)
    )

    assert handoff.body_included
    assert all(element.geometry is not None for element in handoff.elements)


def test_ifc_model_rejects_unsupported_project_unit_before_import():
    bundle = make_structural_bundle(
        vertices=[[0, 0, 0], [1, 0, 0]],
        edges=[(0, 1)],
        axial_forces=[1.0],
        length_unit="ft",
    )
    formulation = make_ifc_formulation(bundle)

    with pytest.raises(StructuralHandoffError, match="supports m, cm, or mm"):
        build_ifc_model(formulation)
