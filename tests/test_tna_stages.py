from __future__ import annotations

import pytest

pytest.importorskip("compas_tna")
pytest.importorskip("compas_fd")

from ananke_equilibrium.worker import dispatch
from tree_forest_compas import tna as tna_module
from tree_forest_compas.tna import prepare_tna_pattern
from tree_forest_compas.tna import register_tna_pattern
from tree_forest_compas.tna import solve_tna_problem


def grid(size=5):
    vertices = [
        (float(x), float(y), 0.0)
        for y in range(size)
        for x in range(size)
    ]
    faces = [
        (
            y * size + x,
            y * size + x + 1,
            (y + 1) * size + x + 1,
            (y + 1) * size + x,
        )
        for y in range(size - 1)
        for x in range(size - 1)
    ]
    edges = []
    seen = set()
    for face in faces:
        for index, u in enumerate(face):
            v = face[(index + 1) % len(face)]
            canonical = tuple(sorted((u, v)))
            if canonical not in seen:
                seen.add(canonical)
                edges.append((u, v))
    corners = (0, size - 1, size * (size - 1), size * size - 1)
    boundary = tuple(
        list(range(size))
        + [row * size + size - 1 for row in range(1, size)]
        + list(range(size * size - 2, size * (size - 1) - 1, -1))
        + [row * size for row in range(size - 2, 0, -1)]
    )
    return vertices, faces, edges, corners, boundary


def request(command, payload, request_id="stage"):
    return {
        "v": 1,
        "type": "request",
        "id": request_id,
        "command": command,
        "payload": payload,
    }


def test_prepare_matches_rhinovault_boundary_sag_and_then_solves_height():
    vertices, faces, _, corners, _ = grid()
    preparation = prepare_tna_pattern(
        vertices=vertices,
        faces=faces,
        vertex_keys=range(len(vertices)),
        support_mode="keys",
        support_keys=corners,
        boundary_sag=0.10,
    )

    assert len(preparation.boundary_segments) == 4
    assert all(
        segment.actual_sag == pytest.approx(0.10, abs=0.01)
        for segment in preparation.boundary_segments
    )
    assert preparation.diagnostics["boundary_support_count"] == 4
    assert preparation.diagnostics["held_boundary_edge_count"] == 0
    for corner in corners:
        assert preparation.pattern.vertex_coordinates(corner) == pytest.approx(
            vertices[corner]
        )
    intermediate = 2
    relaxed_intermediate = preparation.pattern.vertex_coordinates(intermediate)
    assert relaxed_intermediate[1] > vertices[intermediate][1]

    session = solve_tna_problem(
        preparation.problem,
        support_mode="keys",
        support_keys=corners,
        pz=-1.0,
        zmax=2.0,
        density=0.0,
    )
    assert session.diagnostics["zmax_solved"] == pytest.approx(2.0, abs=1e-2)
    assert session.diagnostics["support_count"] == 4


def test_prepare_warns_when_every_boundary_vertex_is_held():
    vertices, faces, _, _, boundary = grid(size=4)
    preparation = prepare_tna_pattern(
        vertices=vertices,
        faces=faces,
        vertex_keys=range(len(vertices)),
        support_mode="keys",
        support_keys=boundary,
        boundary_sag=0.10,
    )

    assert preparation.boundary_segments == ()
    assert preparation.diagnostics["boundary_vertex_count"] == len(boundary)
    assert preparation.diagnostics["boundary_support_count"] == len(boundary)
    assert preparation.diagnostics["held_boundary_edge_count"] == len(boundary)
    assert "complete rim is held" in preparation.diagnostics[
        "boundary_condition_warning"
    ]


def test_worker_prepared_json_is_stateless_and_line_source_finishes_faced():
    vertices, faces, edges, corners, _ = grid(size=4)
    topology = {
        "kind": "line",
        "vertices": vertices,
        "edges": edges,
        "source_vertex_ids": [
            "grid-{}".format(index) for index in range(len(vertices))
        ],
        "length_unit": "m",
    }
    prepared_response = dispatch(
        request(
            "tna.prepare",
            {
                "topology": topology,
                "supports": {
                    "mode": "explicit",
                    "node_ids": corners,
                },
                "settings": {
                    "force_density": 1.0,
                    "relax": True,
                    "boundary_sag": 0.10,
                    "sag_iterations": 10,
                    "sag_tolerance": 0.01,
                },
            },
            "prepare-line",
        )
    )
    assert prepared_response["type"] == "result", prepared_response
    prepared = prepared_response["result"]
    assert prepared["kind"] == "tna_prepared"
    assert prepared["topology"]["kind"] == "line"
    assert prepared["pattern"]["kind"] == "faced"
    assert prepared["pattern"]["edges"] == [
        list(edge) for edge in edges
    ]
    assert len(prepared["pattern"]["faces"]) == len(faces)
    assert len(prepared["pattern"]["edge_force_densities"]) == len(edges)
    assert len(prepared["form_graph"]["edges"]) == len(edges)
    assert len(prepared["force_graph"]["edges"]) == len(edges)
    # update_boundaries closes the four corner-supported openings with
    # unloaded scaffolding faces; the exported form graph must carry only
    # the load-bearing faces or the thrust mesh covers the arches.
    assert len(prepared["form_graph"]["faces"]) == len(faces)

    # The second dispatch reconstructs the prepared stage exclusively from its
    # finite JSON response; no live TNAPreparation object is available.
    solved_response = dispatch(
        request(
            "tna.solve",
            {
                "prepared": prepared,
                "load_case": {
                    "name": "dead",
                    "distribution": "uniform_nodes",
                    "base_vector": (0.0, 0.0, -1.0),
                },
                "control": {
                    "height_control": {
                        "mode": "zmax",
                        "value": 1.5,
                    },
                    "settings": {
                        "horizontal_alpha": 100.0,
                        "horizontal_iterations": 100,
                        "vertical_iterations": 100,
                        "tolerance": 1.0e-3,
                    },
                },
            },
            "solve-prepared",
        )
    )
    assert solved_response["type"] == "result", solved_response
    solved = solved_response["result"]
    assert solved["kind"] == "Result"
    assert solved["solver"] == "tna"
    assert solved["equilibrium"]["topology"]["kind"] == "faced"
    assert solved["equilibrium"]["topology"]["metadata"][
        "source_topology_hash"
    ] == prepared["topology"]["topology_hash"]
    assert solved["equilibrium"]["topology"]["metadata"][
        "source_topology_kind"
    ] == "line"
    assert len(solved["edge_states"]) == len(edges)
    assert len(solved["form_graph"]["faces"]) == len(faces)


def polar_disk(rings=6, spokes=16, radius=10.0):
    from math import cos, pi, sin

    vertices = [(0.0, 0.0, 0.0)]
    ring_start = {}
    for ring in range(1, rings + 1):
        ring_start[ring] = len(vertices)
        r = radius * ring / rings
        for j in range(spokes):
            a = 2.0 * pi * j / spokes
            vertices.append((r * cos(a), r * sin(a), 0.0))
    faces = []
    for j in range(spokes):
        faces.append(
            [0, ring_start[1] + j, ring_start[1] + (j + 1) % spokes]
        )
    for ring in range(1, rings):
        a0, b0 = ring_start[ring], ring_start[ring + 1]
        for j in range(spokes):
            jn = (j + 1) % spokes
            faces.append([a0 + j, b0 + j, b0 + jn, a0 + jn])
    edges = []
    seen = set()
    for face in faces:
        for index, u in enumerate(face):
            v = face[(index + 1) % len(face)]
            key = tuple(sorted((u, v)))
            if key not in seen:
                seen.add(key)
                edges.append(list(key))
    rim = list(range(ring_start[rings], ring_start[rings] + spokes))
    return vertices, faces, edges, rim, ring_start


def test_staged_polar_crown_stays_funicular_and_sag_hits_target():
    """The relaxation must hold the interior plan: a whole-plan FDM pass
    halves a polar hub's ring radius, loads its short edges with high
    force density, and flattens or dips the crown that RhinoVault
    resolves properly. Openings still need their local apron free or the
    sag saturates and the downstream weld collapses faces."""

    vertices, faces, edges, rim, ring_start = polar_disk()
    free = {rim[j] for j in range(16) if j % 4 in (1, 2)}
    supports = [key for key in rim if key not in free]
    prepared_response = dispatch(request(
        "tna.prepare",
        {
            "topology": {
                "kind": "line",
                "vertices": vertices,
                "edges": edges,
                "source_vertex_ids": [
                    "disk-{}".format(index)
                    for index in range(len(vertices))
                ],
                "length_unit": "m",
            },
            "supports": {"mode": "explicit", "node_ids": supports},
            "settings": {
                "force_density": 1.0,
                "relax": True,
                "boundary_sag": 0.20,
                "sag_iterations": 50,
                "sag_tolerance": 0.01,
            },
        },
        "prepare-polar",
    ))
    assert prepared_response["type"] == "result", prepared_response
    prepared = prepared_response["result"]

    segments = prepared["boundary_segments"]
    assert len(segments) == 4
    for segment in segments:
        assert segment["actual_sag"] == pytest.approx(0.20, abs=0.01)

    # The hub must not shrink: ring-1 keeps its source plan radius.
    relaxed = prepared["pattern"]["vertices"]
    ring_one = relaxed[ring_start[1]]
    assert (ring_one[0] ** 2 + ring_one[1] ** 2) ** 0.5 == pytest.approx(
        10.0 / 6.0, rel=1e-6
    )

    solved_response = dispatch(request(
        "tna.solve",
        {
            "prepared": prepared,
            "load_case": {
                "name": "dead",
                "distribution": "tributary_area",
                "base_vector": (0.0, 0.0, -1.0),
            },
            "control": {
                "height_control": {"mode": "zmax", "value": 5.0},
                "settings": {
                    "horizontal_alpha": 100.0,
                    "horizontal_iterations": None,
                    "vertical_iterations": 1000,
                    "tolerance": 1.0e-3,
                },
            },
        },
        "solve-polar",
    ))
    assert solved_response["type"] == "result", solved_response
    solved = solved_response["result"]
    heights = {
        index: point[2]
        for index, point in enumerate(solved["equilibrium"]["vertices"])
    }
    profile = [heights[0]] + [
        heights[ring_start[ring]] for ring in range(1, 5)
    ]
    drops = [
        profile[index] - profile[index + 1]
        for index in range(len(profile) - 1)
    ]
    # Proper funicular curvature: the crown falls away monotonically and
    # each ring drops more than the one before it. A flat or dipped cap
    # fails the first drop.
    assert all(drop > 0.0 for drop in drops)
    assert drops[0] > 0.1
    assert drops[0] < drops[1] < drops[2] < drops[3]


def test_algebraic_horizontal_method_reaches_exact_reciprocity():
    """The algebraic sibling solves the force densities directly from the
    equilibrium matrix: the reciprocity angle must reach numerical zero on
    a pattern the iterative parallelisation only approximates, and the
    solved height must agree with the iterative solver's."""

    vertices, faces, edges, rim, ring_start = polar_disk()
    free = {rim[j] for j in range(16) if j % 4 in (1, 2)}
    supports = [key for key in rim if key not in free]
    prepared = dispatch(request(
        "tna.prepare",
        {
            "topology": {
                "kind": "line",
                "vertices": vertices,
                "edges": edges,
                "source_vertex_ids": [
                    "disk-{}".format(index)
                    for index in range(len(vertices))
                ],
                "length_unit": "m",
            },
            "supports": {"mode": "explicit", "node_ids": supports},
            "settings": {
                "force_density": 1.0,
                "relax": True,
                "boundary_sag": 0.15,
                "sag_iterations": 50,
                "sag_tolerance": 0.01,
            },
        },
        "prepare-algebraic",
    ))["result"]

    def solve(method):
        response = dispatch(request(
            "tna.solve",
            {
                "prepared": prepared,
                "load_case": {
                    "name": "dead",
                    "distribution": "tributary_area",
                    "base_vector": (0.0, 0.0, -1.0),
                },
                "control": {
                    "height_control": {"mode": "zmax", "value": 5.0},
                    "settings": {
                        "horizontal_alpha": 100.0,
                        "horizontal_iterations": None,
                        "horizontal_method": method,
                        "vertical_iterations": 1000,
                        "tolerance": 1.0e-3,
                    },
                },
            },
            "solve-algebraic-" + method,
        ))
        assert response["type"] == "result", response
        return response["result"]["diagnostic_metrics"]

    algebraic = solve("algebraic")
    iterative = solve("iterative")

    assert algebraic["horizontal_mode"] == "algebraic"
    assert algebraic["horizontal_converged"] is True
    assert algebraic["max_reciprocal_angle_deviation"] < 1.0e-4
    assert algebraic["max_reciprocal_angle_ungated"] < 1.0e-4
    assert algebraic["algebraic_residual_max_relative"] < 1.0e-9
    # Exact equilibrium is honest about sign: this wide-opening fixture
    # demands tension on some edges, and the count is surfaced instead of
    # being clamped away.
    assert algebraic["algebraic_negative_q_count"] >= 0
    assert algebraic["zmax_solved"] == pytest.approx(5.0, abs=1e-2)
    assert iterative["zmax_solved"] == pytest.approx(
        algebraic["zmax_solved"], abs=5e-2
    )


def test_natural_height_with_surface_load_freezes_selfweight():
    """A blank Height with a surface load must freeze the selfweight at
    the plan geometry. The regression: the scale-free natural solve fed
    geometry-dependent tributary loads back into themselves, and the vault
    crawled toward an absurd equilibrium (hundreds of metres over a
    twenty-metre plan) while re-evaluating loads for every one of its
    thousand iterations."""

    vertices, faces, edges, rim, ring_start = polar_disk()
    free = {rim[j] for j in range(16) if j % 4 in (1, 2)}
    supports = [key for key in rim if key not in free]
    prepared = dispatch(request(
        "tna.prepare",
        {
            "topology": {
                "kind": "line",
                "vertices": vertices,
                "edges": edges,
                "source_vertex_ids": [
                    "disk-{}".format(index)
                    for index in range(len(vertices))
                ],
                "length_unit": "m",
            },
            "supports": {"mode": "explicit", "node_ids": supports},
            "settings": {
                "force_density": 1.0,
                "relax": True,
                "boundary_sag": 0.15,
                "sag_iterations": 50,
                "sag_tolerance": 0.01,
            },
        },
        "prepare-natural",
    ))["result"]

    solved_response = dispatch(request(
        "tna.solve",
        {
            "prepared": prepared,
            "load_case": {
                "name": "dead",
                "distribution": "tributary_area",
                "base_vector": (0.0, 0.0, -1.0),
            },
            "control": {
                "height_control": {"mode": "natural"},
                "settings": {
                    "horizontal_alpha": 100.0,
                    "horizontal_iterations": None,
                    "vertical_iterations": 1000,
                    "tolerance": 1.0e-3,
                },
            },
        },
        "solve-natural",
    ))
    assert solved_response["type"] == "result", solved_response
    metrics = solved_response["result"]["diagnostic_metrics"]
    # Rule 2.5 of the 2026-09-04 design reworded the old
    # "natural_selfweight_frozen" boolean, which read out on the canvas as
    # "Natural selfweight frozen 0" whenever the guard was OFF. The
    # diagnostic now says what mode the weight was evaluated in.
    assert metrics["selfweight_mode"] == "frozen at the plan geometry"
    assert metrics["selfweight_refined"] is False
    assert metrics["selfweight_rounds_run"] == 1
    # The frozen natural height is unit-relative but stays in the same
    # order of magnitude as the plan; the feedback loop blew far past it.
    assert 0.0 < metrics["zmax_solved"] < 60.0
    # The loads the result reports are the plan-evaluated selfweight the
    # equilibrium actually satisfies: total pz is about minus the plan
    # area, not the area of the risen surface.
    assert metrics["effective_total_pz"] < -100.0
    assert metrics["effective_total_pz"] > -500.0


def grid_with_hole(size=6):
    """A ``size`` x ``size`` quad grid with its centre face removed.

    The removed face leaves a four-vertex interior boundary loop carrying no
    supports: the smallest honest stand-in for an oculus rim.
    """
    vertices, faces, _, _, _ = grid(size)
    hole_x = hole_y = size // 2 - 1
    hole_face = (
        hole_y * size + hole_x,
        hole_y * size + hole_x + 1,
        (hole_y + 1) * size + hole_x + 1,
        (hole_y + 1) * size + hole_x,
    )
    faces = [face for face in faces if tuple(face) != hole_face]
    corners = (0, size - 1, size * (size - 1), size * size - 1)
    return vertices, faces, corners, list(hole_face)


def test_an_unanchored_hole_rim_drifts_when_it_is_not_plan_fixed():
    """The failure this guards against: the sag apron recruits the rim."""
    vertices, faces, corners, rim = grid_with_hole()

    preparation = prepare_tna_pattern(
        vertices=vertices,
        faces=faces,
        vertex_keys=range(len(vertices)),
        support_mode="keys",
        support_keys=corners,
        boundary_sag=0.25,
    )

    moved = [
        key
        for key in rim
        if preparation.pattern.vertex_coordinates(key)[:2]
        != pytest.approx(vertices[key][:2], abs=1e-9)
    ]
    assert moved, (
        "the rim stayed put without being plan-fixed, so this fixture no "
        "longer exercises the apron and the test below proves nothing"
    )


def test_plan_fixed_rim_holds_its_shape_without_becoming_a_support():
    """An oculus rim needs the plan pin and specifically not the reaction.

    ``held_always`` is the union of the supports and the fixed-plan keys, so
    naming the rim here keeps the apron off it at any sag. Leaving it out of
    the support set is what lets FormDiagram.update_boundaries take its
    zero-support branch for the hole and the vertical solve lift the rim,
    rather than pinning it to the springing plane.
    """
    vertices, faces, corners, rim = grid_with_hole()

    preparation = prepare_tna_pattern(
        vertices=vertices,
        faces=faces,
        vertex_keys=range(len(vertices)),
        support_mode="keys",
        support_keys=corners,
        fixed_keys=rim,
        boundary_sag=0.25,
    )

    for key in rim:
        assert preparation.pattern.vertex_coordinates(key)[:2] == pytest.approx(
            vertices[key][:2], abs=1e-9
        ), "a plan-fixed rim vertex moved during the boundary relaxation"
        assert not preparation.pattern.vertex_attribute(key, "is_support"), (
            "a plan-fixed rim vertex became a structural support, which would "
            "pin the oculus to the springing plane"
        )
        assert preparation.pattern.vertex_attribute(key, "is_fixed")

    assert set(preparation.pattern.vertices_where(is_support=True)) == set(
        corners
    )


# The reproduction's own configuration, from section 1 of the 2026-09-04
# selfweight design: a square meshgrid on four corner supports at a
# uniform force density of 1, carrying no nodal load at all so that
# nothing constant remains, and asked for a crown far deeper than its
# span. Measured against this repository's code as it stood before this
# wave (HEAD~1 of the selfweight commit, driven side by side with the new
# module on this same fixture): at a vertical iteration cap of 1000 the
# live density raises "array must not contain infs or NaNs", the exact
# failure Param's six-lobe forms died of, and at a cap of 100 it returns
# a crown of 1.7e38 for a request of 160. The refined solve lands on 160
# exactly, in seven rounds.
SELFWEIGHT_MESHGRID_SIZE = 11
SELFWEIGHT_MESHGRID_ZMAX = 160.0


def selfweight_meshgrid(size=SELFWEIGHT_MESHGRID_SIZE):
    """A square meshgrid of unit quads with its four corners supported."""
    vertices = [
        (float(x), float(y), 0.0)
        for y in range(size)
        for x in range(size)
    ]
    faces = [
        (
            y * size + x,
            y * size + x + 1,
            (y + 1) * size + x + 1,
            (y + 1) * size + x,
        )
        for y in range(size - 1)
        for x in range(size - 1)
    ]
    corners = (0, size - 1, size * (size - 1), size * size - 1)
    return vertices, faces, corners


def solve_selfweight_meshgrid(
    zmax=SELFWEIGHT_MESHGRID_ZMAX,
    size=SELFWEIGHT_MESHGRID_SIZE,
    density=-1.0,
):
    vertices, faces, corners = selfweight_meshgrid(size)
    problem = register_tna_pattern(
        vertices=vertices,
        faces=faces,
        vertex_keys=range(len(vertices)),
    )
    return solve_tna_problem(
        problem,
        support_mode="keys",
        support_keys=corners,
        pz=0.0,
        vertical_mode="zmax",
        zmax=zmax,
        density=density,
        horizontal_kmax=100,
        vertical_kmax=1000,
        vertical_tolerance=1.0e-3,
    )


def round_to_round_drifts(totals):
    return [
        abs(totals[index] - totals[index - 1]) / abs(totals[index - 1])
        for index in range(1, len(totals))
    ]


def test_the_deep_meshgrid_that_diverged_live_settles_under_refinement():
    """Check 2 of the 2026-09-04 design.

    On the fixture where the live configuration overflows into a NaN, the
    refinement settles: the crown lands on the target, the total load
    stops moving, and every round after the second moves it less than the
    round before it. The first round is the plan-frozen solve, and on a
    vault this deep it under-weighs the surface by a factor of thirty
    three, which is what the refinement is for.
    """

    session = solve_selfweight_meshgrid()
    diagnostics = session.diagnostics

    assert diagnostics["selfweight_mode"] == "refined on the solved geometry"
    assert diagnostics["selfweight_refined"] is True
    assert diagnostics["selfweight_converged"] is True
    assert diagnostics["selfweight_fenced"] is False
    assert diagnostics["zmax_solved"] == pytest.approx(
        SELFWEIGHT_MESHGRID_ZMAX, rel=1e-6
    )

    rounds = diagnostics["selfweight_rounds_run"]
    assert 1 < rounds < tna_module.SELFWEIGHT_REFINEMENT_MAX_ROUNDS
    totals = list(diagnostics["selfweight_total_load_by_round"])
    assert len(totals) == rounds
    assert diagnostics["selfweight_final_drift"] < (
        tna_module.SELFWEIGHT_REFINEMENT_TOLERANCE
    )

    # The plan area is 10 x 10 at a density of -1, so round one holds
    # exactly the plan weight, and the surface it finds is nowhere near
    # flat: freezing at the plan alone would have under-weighed this
    # vault thirty-three fold.
    assert totals[0] == pytest.approx(-100.0, rel=1e-9)
    assert abs(totals[-1]) > 30.0 * abs(totals[0])

    drifts = round_to_round_drifts(totals)
    # Round two carries the whole plan-to-surface correction, so it is
    # not part of the monotone tail; it is asserted separately, because a
    # fixture whose first correction was small would prove nothing about
    # a refinement that has to survive a large one.
    assert drifts[0] > 1.0
    for index in range(1, len(drifts)):
        assert drifts[index] < drifts[index - 1], (
            "the round-to-round load change stopped falling at round "
            "{}: {}".format(index + 2, drifts)
        )


def test_the_refinement_tolerance_is_what_stops_the_loop(monkeypatch):
    """Check 6, the tolerance half. The loop stops at the first round
    whose relative load change falls under the tolerance, so loosening
    the tolerance to five per cent must stop it at round three, where
    that fixture's measured drift is 4.1 per cent."""

    monkeypatch.setattr(
        tna_module, "SELFWEIGHT_REFINEMENT_TOLERANCE", 5.0e-2
    )
    session = solve_selfweight_meshgrid()
    diagnostics = session.diagnostics

    assert diagnostics["selfweight_converged"] is True
    assert diagnostics["selfweight_fenced"] is False
    assert diagnostics["selfweight_rounds_run"] == 3
    assert diagnostics["selfweight_final_drift"] == pytest.approx(
        4.13e-2, rel=5e-2
    )


def test_the_refinement_cap_fences_back_to_round_one_and_names_the_drift(
    monkeypatch,
):
    """Check 3 of the 2026-09-04 design.

    A cap the fixture cannot settle inside must not ship the round that
    was still moving. It falls back to round one, the plan-frozen solve,
    which always exists, and says so with the drift it stopped at.

    The fallback is proved by running the same fixture at a cap of three
    and at a cap of one: if the fence holds, the three-round solve throws
    rounds two and three away and lands on exactly the state the
    one-round solve reached.
    """

    monkeypatch.setattr(tna_module, "SELFWEIGHT_REFINEMENT_MAX_ROUNDS", 1)
    with pytest.warns(tna_module.TNASelfweightRefinementWarning):
        round_one = solve_selfweight_meshgrid()

    monkeypatch.setattr(tna_module, "SELFWEIGHT_REFINEMENT_MAX_ROUNDS", 3)
    with pytest.warns(
        tna_module.TNASelfweightRefinementWarning,
        match=(
            r"did not settle in 3 rounds; the total load was still moving "
            r"[0-9]+\.[0-9] per cent; the result carries the round-1 weight"
        ),
    ):
        fenced = solve_selfweight_meshgrid()

    assert fenced.diagnostics["selfweight_converged"] is False
    assert fenced.diagnostics["selfweight_fenced"] is True
    assert fenced.diagnostics["selfweight_rounds_run"] == 3

    # The fenced result IS round one, vertex for vertex, edge for edge.
    assert fenced.diagnostics["vertical_scale"] == pytest.approx(
        round_one.diagnostics["vertical_scale"], rel=1e-12
    )
    assert fenced.diagnostics["effective_total_pz"] == pytest.approx(
        round_one.diagnostics["effective_total_pz"], rel=1e-12
    )
    for key in fenced.form.vertices():
        assert fenced.form.vertex_attribute(key, "z") == pytest.approx(
            round_one.form.vertex_attribute(key, "z"), rel=1e-12, abs=1e-12
        )
        assert fenced.form.vertex_attribute(key, "pz") == pytest.approx(
            round_one.form.vertex_attribute(key, "pz"), rel=1e-12, abs=1e-12
        )
    for edge, force_density in fenced.edge_q.items():
        assert force_density == pytest.approx(
            round_one.edge_q[edge], rel=1e-12
        )

    # And it is not the settled answer: round one holds the plan weight,
    # which on this vault is a thirty-third of the weight the refinement
    # converges on at its own cap.
    monkeypatch.undo()
    settled = solve_selfweight_meshgrid()
    assert settled.diagnostics["selfweight_converged"] is True
    assert fenced.diagnostics["effective_total_pz"] == pytest.approx(
        -100.0, rel=1e-9
    )
    assert abs(settled.diagnostics["effective_total_pz"]) > 30.0 * abs(
        fenced.diagnostics["effective_total_pz"]
    )


def test_a_non_finite_round_is_named_with_its_vertex_and_its_round(
    monkeypatch,
):
    """Check 4 of the 2026-09-04 design.

    A NaN injected through the library seam must arrive as a named error
    carrying the vertex it appeared at and the round that produced it,
    not as scipy's bare complaint about infs and NaNs two calls
    downstream. The first round is allowed through untouched, so the
    round number in the message is measured rather than assumed.
    """

    victim = 60
    real_vertical_from_zmax = tna_module.vertical_from_zmax
    rounds_seen = []

    def poisoned_vertical_from_zmax(form, **kwargs):
        rounds_seen.append(len(rounds_seen) + 1)
        result = real_vertical_from_zmax(form, **kwargs)
        if len(rounds_seen) >= 2:
            form.vertex_attribute(victim, "z", float("nan"))
        return result

    monkeypatch.setattr(
        tna_module, "vertical_from_zmax", poisoned_vertical_from_zmax
    )
    with pytest.raises(tna_module.TNANonFiniteError) as raised:
        solve_selfweight_meshgrid()

    message = str(raised.value)
    assert "selfweight round 2" in message, message
    assert "vertex key {!r}".format(victim) in message, message
    assert len(rounds_seen) == 2


def test_the_zmax_branch_never_hands_the_library_a_density():
    """Check 1 of the 2026-09-04 design, the grep half.

    Every call this module makes to the library's target-height routine
    passes a literal zero density. The rule is worth reading off the
    source as well as off behaviour: a density reaching that routine is
    both the instability of section 1 and, at a negative value, a
    negative scale.
    """

    import inspect

    source = inspect.getsource(tna_module)
    calls = []
    marker = "vertical_from_zmax("
    start = source.find(marker)
    while start != -1:
        cursor = start + len(marker)
        depth = 1
        while depth > 0:
            if source[cursor] == "(":
                depth += 1
            elif source[cursor] == ")":
                depth -= 1
            cursor += 1
        calls.append(source[start:cursor])
        start = source.find(marker, cursor)

    assert len(calls) == 2, (
        "the zmax call sites moved; this check must be pointed at all of "
        "them, and it found {}".format(len(calls))
    )
    for call in calls:
        assert "density=0.0," in call, call
        assert "density=density" not in call, call
        assert "density=vertical_density" not in call, call


def test_the_worker_zmax_seam_passes_a_zero_density_to_the_library(
    monkeypatch,
):
    """Check 1 of the 2026-09-04 design, the behaviour half.

    Driven through the worker protocol seam with a surface load and a
    target height, so the density the library is handed is the one a
    canvas would produce, not one a unit test chose.
    """

    vertices, faces, edges, rim, _ = polar_disk()
    free = {rim[j] for j in range(16) if j % 4 in (1, 2)}
    supports = [key for key in rim if key not in free]
    prepared = dispatch(request(
        "tna.prepare",
        {
            "topology": {
                "kind": "line",
                "vertices": vertices,
                "edges": edges,
                "source_vertex_ids": [
                    "disk-{}".format(index)
                    for index in range(len(vertices))
                ],
                "length_unit": "m",
            },
            "supports": {"mode": "explicit", "node_ids": supports},
            "settings": {
                "force_density": 1.0,
                "relax": True,
                "boundary_sag": 0.15,
                "sag_iterations": 50,
                "sag_tolerance": 0.01,
            },
        },
        "prepare-density-seam",
    ))["result"]

    real_vertical_from_zmax = tna_module.vertical_from_zmax
    densities = []

    def recording_vertical_from_zmax(form, **kwargs):
        densities.append(kwargs["density"])
        return real_vertical_from_zmax(form, **kwargs)

    monkeypatch.setattr(
        tna_module, "vertical_from_zmax", recording_vertical_from_zmax
    )
    solved_response = dispatch(request(
        "tna.solve",
        {
            "prepared": prepared,
            "load_case": {
                "name": "dead",
                "distribution": "tributary_area",
                "base_vector": (0.0, 0.0, -1.0),
            },
            "control": {
                "height_control": {"mode": "zmax", "value": 5.0},
                "settings": {
                    "horizontal_alpha": 100.0,
                    "horizontal_iterations": None,
                    "vertical_iterations": 1000,
                    "tolerance": 1.0e-3,
                },
            },
        },
        "solve-density-seam",
    ))

    assert solved_response["type"] == "result", solved_response
    metrics = solved_response["result"]["diagnostic_metrics"]
    # The canvas really did wire a surface load: the solve refined it.
    assert metrics["selfweight_refined"] is True
    assert metrics["selfweight_rounds_run"] > 1
    assert len(densities) == metrics["selfweight_rounds_run"]
    assert densities == [0.0] * len(densities)
