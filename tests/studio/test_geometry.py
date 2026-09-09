from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]
TRIAL_2 = REPO / "bench" / "demo" / "upload from grasshopper" / "Trial 2-contract.json"


def studio():
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import geometry

    return geometry


def test_slugify_matches_the_demo_09_rule():
    g = studio()
    assert g.slugify("Trial 2") == "trial-2"
    assert g.slugify("Algebraic TNA method") == "algebraic-tna-method"


def test_mesh_arrays_reads_the_synthetic_contract():
    g = studio()
    arrays = g.mesh_arrays(tiny_contract())
    assert len(arrays["vertices"]) == 9
    assert arrays["vertices"][4] == [1.0, 1.0, 1.0]
    assert arrays["faces"] == [[0, 1, 4, 3], [1, 2, 5, 4], [3, 4, 7, 6], [4, 5, 8, 7]]
    assert len(arrays["edges"]) == 12


def test_a_permuted_vertex_space_is_refused_rather_than_drawn():
    """formGraph.faces carry FORM vertex ids, and form vertices and
    equilibrium vertices are two index spaces joined by
    mappings.sourceVertexToFormVertex. This module indexes faces into
    equilibrium.vertices DIRECTLY, which is right only while the two
    coincide.

    They do on every export in existence (measured 2026-09-09: 2 Sided
    Vault 441, Aramdillo style 801, Column diagnosis 661, Round trip
    check 441, every mapping the identity). The exporter guarantees
    nothing, and its own plugin readers sort by id rather than trusting
    array position.

    Indexing by position must NOT change, because the stage plan names
    placed faces by position and solve_stage looks them up the same way,
    so a reader that resolved ids differently would put the cut and the
    analysis on different meshes. The day the spaces diverge is refused
    instead: a permuted vertex space would draw a scrambled vault and
    solve one nobody designed, and every number would still look like a
    number."""

    g = studio()
    contract = tiny_contract()
    # The identity mapping every real export carries: read, allowed.
    contract["mappings"] = {"sourceVertexToFormVertex": [
        {"formVertexId": i, "equilibriumVertexId": i} for i in range(9)]}
    assert len(g.mesh_arrays(contract)["vertices"]) == 9

    # One vertex that is not where its id says: refused, and it says which.
    contract["mappings"]["sourceVertexToFormVertex"][3] = {
        "formVertexId": 3, "equilibriumVertexId": 7}
    with pytest.raises(ValueError, match="different index spaces"):
        g.mesh_arrays(contract)


def test_faces_out_of_id_order_are_refused():
    """The stage plan names placed faces by POSITION. Faces arriving in
    another order would stage the wrong cells and never fail."""

    g = studio()
    contract = tiny_contract()
    contract["formGraph"]["faces"][2]["id"] = 9
    with pytest.raises(ValueError, match="not in id order"):
        g.mesh_arrays(contract)


def test_a_face_naming_a_vertex_that_is_not_there_is_refused():
    """An out-of-range id is the same fault caught one step earlier than
    the IndexError it would otherwise become, with the export named."""

    g = studio()
    contract = tiny_contract()
    contract["formGraph"]["faces"][1]["vertices"] = [1, 2, 5, 99]
    with pytest.raises(ValueError, match="outside this export"):
        g.mesh_arrays(contract)


def test_loads_are_converted_to_newtons_exactly_once():
    g = studio()
    loads = g.node_loads_newtons(tiny_contract())
    assert loads == {4: [0.0, 0.0, -1000.0]}


def test_support_ids():
    g = studio()
    assert g.support_ids(tiny_contract()) == [0, 2, 6, 8]


def test_support_reactions_share_the_load_reader_and_conversion():
    g = studio()
    contract = tiny_contract()
    contract["equilibrium"]["reactions"] = [
        {"nodeId": 0, "vector": {"x": 0.0, "y": 0.0, "z": 0.25}},
        {"nodeId": 2, "vector": {"x": 0.0, "y": 0.0, "z": 0.25}},
    ]
    assert g.support_reactions_newtons(contract) == {
        0: [0.0, 0.0, 250.0],
        2: [0.0, 0.0, 250.0],
    }
    assert g.support_reactions_newtons(tiny_contract()) == {}


def test_member_forces_convert_once_and_check_the_count():
    g = studio()
    contract = tiny_contract()
    contract["equilibrium"]["memberForces"] = [-2.0] * 12
    assert g.member_forces_newtons(contract) == [-2000.0] * 12
    assert g.member_forces_newtons(tiny_contract()) == []
    contract["equilibrium"]["memberForces"] = [-2.0] * 5
    with pytest.raises(ValueError, match="5"):
        g.member_forces_newtons(contract)


def test_face_centroid_and_area_on_a_flat_unit_quad():
    g = studio()
    verts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
    assert g.face_centroids(verts, [[0, 1, 2, 3]]) == [[0.5, 0.5, 0.0]]
    assert g.face_area(verts, [0, 1, 2, 3]) == pytest.approx(1.0)


@pytest.mark.skipif(
    not TRIAL_2.is_file(), reason="the Trial 2 export is not present")
def test_the_real_export_parses_to_the_known_shape():
    """Guarded 2026-09-04, the same way every tests/fea test that reads this
    export already is. The uploads folder the studio SERVES is also where
    this fixture lives, so the new Delete button removes it: Trial 2 and
    ananke-export both left the working tree the first afternoon the button
    existed. A skip states that plainly; the alternative was a suite that
    goes red whenever the user tidies their own study list."""

    g = studio()
    contract = g.load_contract(TRIAL_2)
    arrays = g.mesh_arrays(contract)
    assert len(arrays["vertices"]) == 2521
    assert len(arrays["faces"]) == 2400
    assert len(arrays["edges"]) == 4800
    assert all(len(face) == 4 for face in arrays["faces"])
    assert len(g.support_ids(contract)) == 123
    # The 3D surface, not the flat form diagram: the crown is lifted.
    assert max(v[2] for v in arrays["vertices"]) > 6.0


def test_available_exports_lists_every_contract_in_the_folder(tmp_path):
    """Re-pinned 2026-09-04 on Param's ask that the study list read whatever
    is in the folder. The pair requirement is gone: a contract is enough,
    because the compas half is a passenger nothing in the studio parses
    (staging carries its path to the FEA runner and stops there), and
    requiring it hid whole studies over a file that says nothing. A JSON
    with no kind suffix is offered when it reads like a contract, so a file
    dropped in under its own name is a study; a file that carries a kind
    suffix never is, even when its content would pass."""

    g = studio()
    contract = json.dumps(tiny_contract())
    (tmp_path / "A-contract.json").write_text(contract, encoding="utf-8")
    (tmp_path / "A-compas.json").write_text("{}", encoding="utf-8")
    (tmp_path / "B-contract.json").write_text(contract, encoding="utf-8")
    (tmp_path / "Dropped in.json").write_text(contract, encoding="utf-8")
    (tmp_path / "notes.json").write_text('{"hello": "world"}', encoding="utf-8")
    (tmp_path / "A-tessellation.json").write_text(contract, encoding="utf-8")
    pairs = g.available_exports(tmp_path)
    assert sorted(pairs) == ["A", "B", "Dropped in"]
    assert pairs["A"]["contract"].name == "A-contract.json"
    assert pairs["A"]["geometry"].name == "A-compas.json"
    # B has no compas half at all and is listed anyway, without the key.
    assert "geometry" not in pairs["B"]
    assert pairs["Dropped in"]["contract"].name == "Dropped in.json"
