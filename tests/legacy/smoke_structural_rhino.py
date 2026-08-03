"""Repeatable structural-handoff smoke test for Rhino 8's Python environment.

Run with Rhino's Python executable and the catenary COMPAS site environment on
``PYTHONPATH``.  No files survive the test; the IFC round trip uses a temporary
directory.
"""

import os
import tempfile

from compas_ifc.bim import BuildingInformationModel

from tree_forest_compas.fd import solve_fd_network
from tree_forest_compas.structural import analysis_case_from_fd_session
from tree_forest_compas.structural import analysis_case_from_tna_session
from tree_forest_compas.structural import assess_fea_readiness
from tree_forest_compas.structural import build_compas_model
from tree_forest_compas.structural import build_ifc_model
from tree_forest_compas.structural import compas_fea2_status
from tree_forest_compas.structural import make_ifc_formulation
from tree_forest_compas.structural import make_structural_bundle
from tree_forest_compas.structural import structural_bundle_from_tna_session
from tree_forest_compas.tna import solve_tna_pattern


def main():
    bundle = make_structural_bundle(
        vertices={
            "a": [0.0, 0.0, 0.0],
            "b": [2.0, 0.0, 0.0],
            "c": [2.0, 0.0, 3.0],
        },
        edges=[("a", "b"), ("b", "c")],
        axial_forces=[12.0, -8.0],
        support_keys=["a", "c"],
        source="Rhino environment smoke test",
    )

    model_handoff = build_compas_model(bundle, width=0.1, depth=0.2)
    for member, element in zip(bundle.members, model_handoff.elements):
        line = element.center_line.transformed(element.modeltransformation)
        assert all(
            abs(float(a) - float(b)) < 1e-9
            for a, b in zip(line.start, member.start)
        )
        assert all(
            abs(float(a) - float(b)) < 1e-9
            for a, b in zip(line.end, member.end)
        )

    formulation = make_ifc_formulation(bundle)
    ifc_handoff = build_ifc_model(formulation)
    assert len(ifc_handoff.elements) == len(bundle.members)
    assert all(element.axis is not None for element in ifc_handoff.elements)

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "equilibrium.ifc")
        ifc_handoff.model.save(path)
        loaded = BuildingInformationModel(
            filepath=path, load_geometries=False
        )
        members = loaded.get_elements_by_type("IfcMember")
        assert len(members) == len(bundle.members)
        properties_by_index = {
            member.properties["AE_EquilibriumResult"]["MemberIndex"]:
            member.properties["AE_EquilibriumResult"]
            for member in members
        }
        properties = properties_by_index[0]
        assert properties["SignedAxialForce"] == 12.0
        assert properties["ResultOnly"] is True
        assert all(member.axis is not None for member in members)

    assert not compas_fea2_status().available
    assert not assess_fea_readiness(bundle).ready

    tna_vertices = [
        [float(x), float(y), 0.0]
        for y in range(3)
        for x in range(3)
    ]
    tna_faces = [
        [0, 1, 4, 3],
        [1, 2, 5, 4],
        [3, 4, 7, 6],
        [4, 5, 8, 7],
    ]
    tna_session = solve_tna_pattern(
        vertices=tna_vertices,
        faces=tna_faces,
        pz={4: -1.0},
        vertical_mode="q",
        q_scale=-1.0,
    )
    tna_bundle = structural_bundle_from_tna_session(tna_session)
    assert len(tna_bundle.members) == len(tna_session.edge_forces)
    assert tna_bundle.support_keys == tna_session.support_form_keys
    assert all(
        member.force_state == "compression"
        for member in tna_bundle.members
    )
    tna_case = analysis_case_from_tna_session(
        tna_session,
        load_case="TNA smoke",
        member_roles="vault",
    )
    assert tna_case.bundle == tna_bundle
    assert len(tna_case.member_force_densities) == len(tna_bundle.members)
    assert len(tna_case.source_member_mappings) == len(
        tna_session.source_edges
    )
    assert tna_case.removed_source_member_ids == tuple(
        tna_session.diagnostics["removed_source_edge_ids"]
    )
    assert "analysis load cases" not in assess_fea_readiness(
        tna_case
    ).missing_inputs

    fd_session = solve_fd_network(
        lines=[
            [[0, 0, 0], [1, 0, 0]],
            [[1, 0, 0], [2, 0, 0]],
        ],
        fixed=[0, 2],
        forcedensities=1.0,
        loads=((0, 0, 0), (0, 0, -1), (0, 0, 0)),
    )
    fd_case = analysis_case_from_fd_session(
        fd_session,
        load_case="FD smoke",
        member_roles="cable",
    )
    assert fd_case.member_force_densities == (1.0, 1.0)
    assert fd_case.member_source_ids == ((0,), (1,))
    assert fd_case.member_roles == ("cable", "cable")
    assert fd_case.nodal_loads[1].vector == (0.0, 0.0, -1.0)
    print("STRUCTURAL_HANDOFF_SMOKE_OK")


if __name__ == "__main__":
    main()
