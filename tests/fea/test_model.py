from __future__ import annotations

import pytest

from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model


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
