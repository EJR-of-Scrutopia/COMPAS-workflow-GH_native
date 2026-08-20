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
from ananke_equilibrium.patterns.armadillo_dual import _smooth_pass
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


# ---------------------------------------------------------------------------
# M7 (2026-08-20 dual-quality wave, task 3): coherence-weighted smoothing.
#
# The diagnosis's own finding (findings.md, "M7 NEW latent"): about 8% of
# faces on Param's real vault are near-equilateral, where the three edges'
# doubled-angle directions sit close to 120 degrees apart and their
# force-weighted sum nearly cancels -- ``_undouble``'s output there is
# numerically arbitrary (a hair of floating noise decides it), not a real
# measurement. ``_smooth_pass`` used to fold every neighbour's contribution
# in at the SAME unit strength regardless of how arbitrary that neighbour's
# own raw direction was, so one noisy face could swing its well-behaved
# neighbours' own smoothed output. The fix weights each neighbour's
# contribution by that neighbour's own RAW coherence (this file's
# ``_face_raw_direction``, extended to also report
# ``|weighted doubled sum| / sum(|weight|)``), computed ONCE from the
# unsmoothed field and held fixed across every pass -- CLAMPED to full
# (1.0) strength at and above ``_ARBITRARY_COHERENCE_THRESHOLD`` (0.2, the
# diagnosis's own boundary for "numerically arbitrary"). Task 3's own
# fix round measured directly why the clamp is load-bearing, not
# cosmetic: raw coherence is a continuous, mostly-MODERATE quantity on a
# real mesh (Param's vault: median 0.558, only 8.0% under 0.2) -- an
# artefact of doubled-angle space amplifying even a normal spread of edge
# directions -- so weighting every neighbour by its raw value discounts
# the 92% of ordinary faces too, not just the 8% named, and regresses
# Task 2's own established vault bars (streamline_count 103 -> 99,
# cross-flow starvation 1.03% -> 6.16%, isolated and confirmed directly).
# See ``_smooth_pass``'s own docstring for the full account.
# ---------------------------------------------------------------------------


def test_smooth_pass_downweights_a_low_coherence_neighbours_vote():
    """Direct, hand-computed pin on ``_smooth_pass`` itself: a reporter face
    with one HIGH-coherence neighbour agreeing with its own prior direction
    (0 degrees) and three genuinely near-cancelling (coherence 0.01, well
    under ``_ARBITRARY_COHERENCE_THRESHOLD``) neighbours voting for a
    spurious ~60-70 degree cluster.

    Worked by hand (doubled-angle arithmetic, see the task 3 report for the
    full derivation): UNWEIGHTED, the three noisy votes (unit strength each)
    outvote the reporter's own prior state plus its one strong neighbour,
    landing the smoothed result about 44 degrees off -- a real flip, not a
    rounding wobble. Weighted (each neighbour's own coherence, clamped to
    full strength at 1.0 for the strong one -- 0.98 clamps to 1.0 -- and to
    0.05 for each noisy one -- 0.01/0.2), the same inputs land under 5
    degrees off: the noisy block's total weight (0.15) never threatens the
    strong block's (1.0 self + 1.0 neighbour). 0.01, not the design spec's
    own 0.05 illustrative middle value, deliberately: task 3's own fix
    round measured that RAW coherence in [0.05, 0.2) is common on a real
    mesh even for perfectly healthy faces (median 0.558 on Param's vault)
    and must NOT be crushed the way this test crushes a genuinely
    near-zero, arbitrary one -- see ``_smooth_pass``'s own docstring.
    """

    e1 = np.array([1.0, 0.0, 0.0])
    e2 = np.array([0.0, 1.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    bases = [(e1, e2, normal) for _ in range(5)]

    def unit_state(angle_degrees: float):
        radians = math.radians(angle_degrees)
        return (math.cos(radians), math.sin(radians))

    # face 0 is the reporter; 1 is its strong (high-coherence) neighbour at
    # its own prior angle; 2/3/4 are noisy (near-zero coherence) neighbours
    # clustered off to one side.
    states = [
        unit_state(0.0),
        unit_state(0.0),
        unit_state(60.0),
        unit_state(65.0),
        unit_state(70.0),
    ]
    adjacency = [[1, 2, 3, 4], [], [], [], []]
    coherence = np.array([1.0, 0.98, 0.01, 0.01, 0.01])

    new_states = _smooth_pass(bases, states, adjacency, coherence)
    dx, dy = new_states[0]
    angle_off = math.degrees(abs(math.atan2(dy, dx)))
    # _undouble halves the doubled angle back into (-90, 90]; a genuine
    # flip toward the noisy cluster reads near 44 degrees off, not near 0.
    assert angle_off < 5.0, (
        "reporter face drifted {:.2f} degrees off its own strong "
        "consensus -- the noisy neighbours' vote was not downweighted"
        .format(angle_off)
    )


def _near_equilateral_patch_result(third_vertex):
    """Two triangles sharing edge A-B: T0 (A, B, C) near-equilateral with
    EQUAL force on all three of its own edges (the doubled-angle
    cancellation M7 targets), and N (A, B, D) sharing only that one edge
    with T0, its OTHER two edges carrying a force 100x A-B's so N's own
    raw direction is strongly, unambiguously dominated by them regardless
    of T0's own instability. ``third_vertex`` is T0's own C, perturbed by
    the caller to swing T0's raw (arbitrary, near-cancelling) direction
    between two otherwise-identical meshes.
    """

    a, b = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)
    d = (0.5, -0.8660254037844386, 0.0)
    vertices = [a, b, third_vertex, d]
    edges = [(0, 1), (1, 2), (2, 0), (1, 3)]
    member_forces = [10.0, 10.0, 10.0, 1000.0]
    faces = [[0, 1, 2], [0, 1, 3]]

    result = {
        "kind": "Result",
        "solver": "tna",
        "equilibrium": {
            "vertices": [list(v) for v in vertices],
            "edges": [list(e) for e in edges],
            "member_forces": list(member_forces),
            "mappings": {"resolved_support_ids": []},
        },
        "form_graph": {
            "vertices": [
                {"id": i, "key": i, "point": list(v)} for i, v in enumerate(vertices)
            ],
            "edges": [
                {"id": i, "u": u, "v": v} for i, (u, v) in enumerate(edges)
            ],
            "faces": [
                {"id": i, "key": i, "vertices": face} for i, face in enumerate(faces)
            ],
        },
    }
    return result


def test_line_field_stays_stable_across_a_near_equilateral_patch_perturbation():
    """The hand-built near-equilateral noisy patch the task 3 brief names:
    T0 is close enough to equilateral, with equal force on all three
    edges, that its raw doubled-angle sum nearly cancels -- perturbing its
    third vertex by a few percent swings its OWN raw direction wildly (the
    classic near-zero-magnitude ``atan2`` instability), while its own
    coherence stays low both times. N, T0's one neighbour, has a strong,
    unambiguous direction of its own (dominated by a edge weighted 100x
    T0's). Pinned behaviour: N's SMOOTHED direction barely moves between
    the two perturbations, because T0's vote is weighted by its own (low)
    coherence rather than at full strength.
    """

    exact_equilateral = (0.5, 0.8660254037844386, 0.0)
    perturbed = (0.52, 0.8510254037844386, 0.0)  # a few percent, arbitrary direction

    angles = []
    for third_vertex in (exact_equilateral, perturbed):
        result = _near_equilateral_patch_result(third_vertex)
        mesh = assemble_mesh(result)
        field = line_field(mesh)
        # face index 1 is N == (0, 1, 3), the one sharing only edge A-B
        # with the near-equilateral T0 == (0, 1, 2) at face index 0.
        assert list(mesh.triangles[1]) == [0, 1, 3]
        e1, e2, _normal = face_basis(mesh.vertices, mesh.triangles[1])
        direction3d = field[1, 0] * e1 + field[1, 1] * e2
        angles.append(direction3d)

    cos_angle = min(1.0, abs(float(np.dot(angles[0], angles[1]))))
    angle_between = math.degrees(math.acos(cos_angle))
    assert angle_between < 5.0, (
        "N's own smoothed direction moved {:.2f} degrees between the two "
        "T0 perturbations -- T0's numerically arbitrary vote was not "
        "downweighted by its own low coherence".format(angle_between)
    )
