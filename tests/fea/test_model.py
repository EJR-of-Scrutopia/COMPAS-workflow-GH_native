from __future__ import annotations

import pytest

from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import GRAVITY, build_shell_model, self_weight_loads


@pytest.fixture(scope="module")
def barrel():
    """A coarse barrel vault: enough to exercise the builder, quick to solve."""

    from compas.datastructures import Mesh

    return Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)


def test_every_mesh_vertex_becomes_a_node(barrel):
    require_backend()
    apply_patches()
    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, [])
    assert len(built.nodes) == barrel.number_of_vertices()


def test_every_mesh_face_becomes_an_element(barrel):
    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, [])
    assert len(list(built.part.elements)) == barrel.number_of_faces()


def test_supports_are_pinned_where_asked(barrel):
    corners = list(barrel.vertices_on_boundary())[:4]
    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, corners)
    assert len(built.supports) == 4


def test_nodes_are_keyed_by_vertex_not_by_insertion_order(barrel):
    """Part stores nodes in a set, so index-based mapping silently scrambles."""

    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, [])
    for key, node in built.nodes.items():
        assert tuple(node.xyz) == pytest.approx(tuple(barrel.vertex_coordinates(key)))


def test_an_unknown_support_key_is_rejected_loudly(barrel):
    with pytest.raises(ValueError, match="not a vertex"):
        build_shell_model(barrel, PRESETS["concrete"], 0.15, [10**6])


def test_self_weight_loads_sum_to_the_sections_own_weight(barrel):
    """The 4x4 plate is exactly 16 m2 by construction, so its self-weight is
    exact, not approximate: any drift here means vertex_area stopped
    partitioning the surface exactly."""

    weight = self_weight_loads(barrel, 0.15, 2400)
    total_z = sum(vector[2] for vector in weight.values())
    assert total_z == pytest.approx(-16 * 0.15 * 2400 * GRAVITY, rel=1e-6)
    for vector in weight.values():
        assert vector[0] == 0.0
        assert vector[1] == 0.0


def test_a_face_with_five_vertices_is_rejected_not_triangulated():
    """The brief's one named behaviour: never silently change the topology."""

    from compas.datastructures import Mesh

    pentagon = Mesh()
    keys = [
        pentagon.add_vertex(x=x, y=y, z=0.0)
        for x, y in [(0, 0), (2, 0), (3, 1.5), (1, 3), (-1, 1.5)]
    ]
    pentagon.add_face(keys)

    with pytest.raises(ValueError, match="5 vertices"):
        build_shell_model(pentagon, PRESETS["concrete"], 0.15, [])
