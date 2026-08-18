"""The Armadillo Dual line field: mesh assembly and its force-driven source.

``line_field`` is a LINE field, not a vector field: a direction and its
negation describe the same thrust line, so both the raw per-face direction
and its neighbour smoothing happen in doubled-angle (2-theta) space. These
tests exercise that on a synthetic hemispherical dome (``dome_result`` in
conftest.py): meridian member forces radiating from the apex to an equator
support ring, mirroring what a real solved TNA Result looks like off
codec.py / gh/export.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ananke_equilibrium.patterns.armadillo_dual import PatternRefused
from ananke_equilibrium.patterns.armadillo_dual import assemble_mesh
from ananke_equilibrium.patterns.armadillo_dual import face_basis
from ananke_equilibrium.patterns.armadillo_dual import field_source
from ananke_equilibrium.patterns.armadillo_dual import line_field


def _angle_to_meridian_degrees(mesh, field, face_index, geometry):
    """Line-metric angle (0-90) between a face's field and its meridian."""

    e1, e2, _normal = face_basis(mesh.vertices, mesh.triangles[face_index])
    direction3d = field[face_index, 0] * e1 + field[face_index, 1] * e2
    assert np.isfinite(direction3d).all()
    assert abs(float(np.linalg.norm(direction3d)) - 1.0) < 1e-6

    centroid = geometry.face_centroid_lonlat(mesh.triangles[face_index])
    tangent = np.array(geometry.meridian_tangent(*centroid))
    cos_angle = min(1.0, abs(float(np.dot(direction3d, tangent))))
    return math.degrees(math.acos(cos_angle))


def test_assemble_mesh_matches_the_dome_topology_and_supports(dome_result):
    result, geometry = dome_result()

    mesh = assemble_mesh(result)

    expected_triangles = len(geometry.apex_faces) + 2 * len(geometry.quad_faces)
    assert mesh.vertices.shape == (len(geometry.positions), 3)
    assert mesh.triangles.shape == (expected_triangles, 3)
    assert mesh.edges.shape == (len(geometry.meridian_edges), 2)
    assert mesh.edge_forces.shape == (len(geometry.meridian_edges),)
    assert sorted(mesh.support_vertex_ids) == sorted(geometry.support_vertex_ids)
    assert field_source(result) == "forces"


def test_line_field_aligns_with_meridians_away_from_the_pole(dome_result):
    result, geometry = dome_result()
    mesh = assemble_mesh(result)

    field = line_field(mesh)
    assert field.shape == (mesh.triangles.shape[0], 2)
    assert field.dtype == np.float64
    norms = np.linalg.norm(field, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-9)

    apex = geometry.apex_index
    checked = 0
    for face_index, triangle in enumerate(mesh.triangles):
        if apex in tuple(triangle):
            continue  # near-pole faces: meridians converge, skip per the brief
        angle = _angle_to_meridian_degrees(mesh, field, face_index, geometry)
        assert angle < 15.0, "face {} is {:.1f} degrees off its meridian".format(
            face_index, angle
        )
        checked += 1
    assert checked > 0


def test_smoothing_pulls_a_noisy_face_patch_back_toward_its_neighbours(
    dome_result,
):
    ring, segment = 1, 2
    result, geometry = dome_result()
    v0 = geometry.ring_vertex(ring, segment)
    v2 = geometry.ring_vertex(ring + 1, segment + 1)
    noisy_diagonal = (v0, v2)

    # A single quad's diagonal, given a force many times larger than any
    # meridian edge, drags that quad's own two triangles 50-60 degrees
    # off-meridian in the raw (pre-smoothing) field (confirmed directly
    # against the internal _face_raw_direction helper while calibrating
    # this test) -- everything around that patch stays clean
    # meridian-driven, within the ~7 degree spread the clean field test
    # above measures.
    result, geometry = dome_result(extra_edges=[(noisy_diagonal, 40.0)])
    mesh = assemble_mesh(result)
    field = line_field(mesh)

    noisy_indices = [
        i
        for i, triangle in enumerate(mesh.triangles)
        if v0 in tuple(triangle) and v2 in tuple(triangle)
    ]
    assert len(noisy_indices) == 2

    for face_index in noisy_indices:
        angle = _angle_to_meridian_degrees(mesh, field, face_index, geometry)
        # Not a flip to garbage (checked inside the helper: finite, unit
        # length) and not stuck as an outlier either -- three doubled-angle
        # neighbour-averaging passes, pulled by this patch's untouched
        # neighbours, land it decisively closer to meridian (measured
        # ~12-13 degrees) than the raw ~50-60 degree disagreement the
        # noisy diagonal alone produces.
        assert angle < 20.0, "noisy face {} did not converge: {:.1f} degrees".format(
            face_index, angle
        )


def test_field_source_falls_back_to_diagrams_when_forces_are_absent(dome_result):
    result, _geometry = dome_result(include_forces=False, include_diagrams=True)

    assert field_source(result) == "diagrams"

    mesh = assemble_mesh(result)
    assert mesh.edge_forces.shape == (mesh.edges.shape[0],)
    assert np.any(mesh.edge_forces != 0.0)

    # A real (non-zero) force-density weighting produces a non-degenerate
    # field: every face gets a finite, unit-length direction, not a
    # collapsed or NaN one.
    field = line_field(mesh)
    assert np.isfinite(field).all()
    assert np.allclose(np.linalg.norm(field, axis=1), 1.0, atol=1e-9)


def test_field_source_refuses_a_weightless_diagram_pair(dome_result):
    # The diagram pair (form_graph/force_graph) is present, but its force
    # densities are all zero: a diagram graph alone names no direction to
    # weight by, so this must refuse rather than silently building a
    # zero-weight (degenerate) field.
    result, _geometry = dome_result(include_forces=False, include_diagrams=True)
    result["equilibrium"]["force_densities"] = [
        0.0 for _ in result["equilibrium"]["force_densities"]
    ]

    with pytest.raises(PatternRefused) as excinfo:
        field_source(result)

    message = str(excinfo.value).lower()
    assert "diagram pair" in message
    assert "force densities" in message


def test_assemble_mesh_refuses_a_weightless_diagram_pair(dome_result):
    result, _geometry = dome_result(include_forces=False, include_diagrams=True)
    result["equilibrium"]["force_densities"] = [
        0.0 for _ in result["equilibrium"]["force_densities"]
    ]

    with pytest.raises(PatternRefused):
        assemble_mesh(result)


def test_field_source_refuses_when_neither_forces_nor_diagrams_exist(dome_result):
    result, _geometry = dome_result(include_forces=False, include_diagrams=False)

    with pytest.raises(PatternRefused) as excinfo:
        field_source(result)

    message = str(excinfo.value).lower()
    assert "force" in message
    assert "diagram" in message


def test_assemble_mesh_refuses_when_neither_forces_nor_diagrams_exist(dome_result):
    result, _geometry = dome_result(include_forces=False, include_diagrams=False)

    with pytest.raises(PatternRefused):
        assemble_mesh(result)
