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
    assert metrics["selfweight_mode_code"] == 1.0
    assert "selfweight_refined" not in metrics
    # The frozen natural height is unit-relative but stays in the same
    # order of magnitude as the plan; the feedback loop blew far past it.
    assert 0.0 < metrics["zmax_solved"] < 60.0
    # The loads the result reports are the plan-evaluated selfweight the
    # equilibrium actually satisfies: total pz is about minus the plan
    # area, not the area of the risen surface.
    assert metrics["effective_total_pz"] < -100.0
    assert metrics["effective_total_pz"] > -500.0


# The six keys that describe the refinement LOOP. They belong to a solve
# that ran one, and to no other.
SELFWEIGHT_LOOP_KEYS = (
    "selfweight_refined",
    "selfweight_rounds_run",
    "selfweight_total_load_by_round",
    "selfweight_final_drift",
    "selfweight_converged",
    "selfweight_fenced",
)


def rendered_canvas_diagnostics(metrics):
    """What the canvas actually reads.

    ananke_equilibrium.gh.solvers._diagnostic_contracts is the renderer a
    Result's diagnostics list is built by, and it is the renderer that
    minted "Natural selfweight frozen 0". Driving it, rather than reading
    the metric dictionary alone, is the only way a check can speak about
    what a canvas SEES: the renderer drops every string on the floor.
    """

    from ananke_equilibrium.gh.solvers import _diagnostic_contracts

    return {
        contract.code: (contract.message, contract.value)
        for contract in _diagnostic_contracts(metrics)
    }


def test_a_solve_that_never_refined_puts_no_refinement_line_on_the_canvas():
    """Round-1 review finding against rule 2.5.

    A natural height freezes its weight at the plan and refines nothing.
    Shipping the loop's numbers anyway put five lines on the canvas:
    "Selfweight converged 1.0", "Selfweight fenced 0.0", "Selfweight final
    drift 0.0", "Selfweight refined 0.0" and "Selfweight rounds run 1.0",
    every one of them a guard reporting a state it never entered, in words
    that read as an operation that happened. Meanwhile the one key that
    says what the weight WAS, selfweight_mode, is a string, and the
    renderer skips strings, so the canvas was told everything except the
    answer. Absence for the loop, a number for the mode.
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
        "prepare-canvas-lines",
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
        "solve-canvas-lines",
    ))
    assert solved_response["type"] == "result", solved_response
    metrics = solved_response["result"]["diagnostic_metrics"]

    # The canvas first, because the canvas is where the defect was read.
    rendered = rendered_canvas_diagnostics(metrics)
    lines = [
        "{} {}".format(message, value)
        for code, (message, value) in rendered.items()
        if code.startswith("selfweight")
    ]
    for key in SELFWEIGHT_LOOP_KEYS:
        assert key not in rendered, (
            "the canvas is being told about a refinement that never ran: "
            "{}".format(lines)
        )
    # And it IS told the mode, which as a string it never was.
    assert "Selfweight mode code 1.0" in lines, lines

    # Then the wire, which is the stronger statement: the renderer drops
    # tuples silently, so selfweight_total_load_by_round could ride the
    # wire forever without ever showing up on a canvas.
    present = [key for key in SELFWEIGHT_LOOP_KEYS if key in metrics]
    assert present == [], (
        "a solve that ran no refinement is still shipping the loop's "
        "diagnostics: {}".format(
            {key: metrics[key] for key in present}
        )
    )
    assert metrics["selfweight_mode"] == "frozen at the plan geometry"
    assert metrics["selfweight_mode_code"] == 1.0


def test_the_selfweight_mode_code_is_the_twin_of_the_mode_it_names():
    """The other half of the same finding.

    selfweight_mode is a string, and both channels that carry a solve's
    diagnostics to a reader take numbers only: the canvas renderer drops
    strings outright, and the native component's metric dictionary is a
    dictionary of doubles. So the mode travels as a code as well, cut from
    the same chain, and this check walks every mode a solve can be in and
    holds the two together. It also fixes the meaning of each number, so
    that a reader of "Selfweight mode code 2.0" is reading refinement and
    not something a later edit renumbered underneath them.
    """

    vertices, faces, corners = selfweight_meshgrid(5)

    def solve(**overrides):
        problem = register_tna_pattern(
            vertices=vertices,
            faces=faces,
            vertex_keys=range(len(vertices)),
        )
        settings = dict(
            support_mode="keys",
            support_keys=corners,
            pz=-1.0,
            vertical_mode="zmax",
            zmax=2.0,
            density=0.0,
            horizontal_kmax=100,
            vertical_kmax=1000,
            vertical_tolerance=1.0e-3,
        )
        settings.update(overrides)
        return solve_tna_problem(problem, **settings).diagnostics

    no_selfweight = solve()
    frozen = solve(vertical_mode="natural", density=-1.0)
    refined = solve(density=-1.0)
    # The live mode is the one route by which a density still reaches the
    # library, and it is only reachable through an explicit q scale. It
    # needs the whole rim held: on four corner supports the live weight
    # and the geometry chase each other into the NaN this design was
    # written to retire, which is the point, and is measured elsewhere.
    live = solve(
        vertical_mode="q",
        q_scale=-1.0,
        density=-1.0,
        support_mode="boundary",
        support_keys=None,
        pz=0.0,
    )

    assert no_selfweight["selfweight_mode"] == "none"
    assert no_selfweight["selfweight_mode_code"] == 0.0
    assert frozen["selfweight_mode"] == "frozen at the plan geometry"
    assert frozen["selfweight_mode_code"] == 1.0
    assert refined["selfweight_mode"] == "refined on the solved geometry"
    assert refined["selfweight_mode_code"] == 2.0
    assert live["selfweight_mode"] == "live inside the library"
    assert live["selfweight_mode_code"] == 3.0

    # The loop's numbers are present exactly where the loop turned, and
    # the code says so on its own: a reader with numbers alone can tell a
    # refined solve from the three that were not.
    for diagnostics in (no_selfweight, frozen, live):
        assert diagnostics["selfweight_mode_code"] != 2.0
        for key in SELFWEIGHT_LOOP_KEYS:
            assert key not in diagnostics, (
                "{} arrived on a solve whose mode is {!r}".format(
                    key, diagnostics["selfweight_mode"]
                )
            )
    for key in SELFWEIGHT_LOOP_KEYS:
        assert key in refined, key
    assert refined["selfweight_refined"] is True

    # Every code is rendered onto the canvas, which is the whole point of
    # having one: the string never gets there.
    for diagnostics in (no_selfweight, frozen, refined, live):
        rendered = rendered_canvas_diagnostics(diagnostics)
        assert "selfweight_mode_code" in rendered
        assert rendered["selfweight_mode_code"][1] == (
            diagnostics["selfweight_mode_code"]
        )
        assert "selfweight_mode" not in rendered


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


# The canvas rule 2.4(b) is about: a square grid on four corner supports,
# a self-weight over the whole surface, and one heavy point load at the
# centre vertex. Everything below drives the WORKER SEAM rather than
# solve_tna_problem directly, because the zeroing this retires lived in
# the adapter (ananke_equilibrium.gh.solvers) and a check that never
# crosses it could not see the defect at all.
LOADED_VERTEX = 12
NODAL_LOAD = -25.0


def loads_case_grid_payload(load_case, zmax=3.0, size=5):
    vertices, faces, edges, corners, _ = grid(size)
    return {
        "topology": {
            "kind": "faced",
            "vertices": vertices,
            "edges": edges,
            "faces": faces,
            "source_vertex_ids": [
                "grid-{}".format(index) for index in range(len(vertices))
            ],
            "length_unit": "m",
        },
        "supports": {"mode": "explicit", "node_ids": list(corners)},
        "load_case": load_case,
        "control": {
            "height_control": {"mode": "zmax", "value": zmax},
            "settings": {
                "horizontal_alpha": 100.0,
                "horizontal_iterations": 100,
                "vertical_iterations": 1000,
                "tolerance": 1.0e-3,
            },
        },
    }


def solve_loads_case(load_case, request_id, zmax=3.0):
    response = dispatch(request(
        "tna.solve",
        loads_case_grid_payload(load_case, zmax=zmax),
        request_id,
    ))
    assert response["type"] == "result", response
    return response["result"]


def effective_pz_by_vertex(result):
    return {
        int(record["topology_vertex_ids"][0]): float(record["vector"][2])
        for record in result["mappings"]["loads"]
        if record["topology_vertex_ids"]
    }


def test_selfweight_and_nodal_loads_ride_together_additively():
    """Check 5 of the 2026-09-04 design, rule 2.4(b).

    A canvas with BOTH a self-weight and nodal point loads wired gets
    both. Until this rule the adapter set ``pz = 0.0`` the moment a
    surface load appeared, so the point loads were silently thrown away
    and a canvas could carry one kind of load or the other, never both.
    """

    solved = solve_loads_case(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, -1.0),
            "thickness": 1.0,
            "density": 1.0,
            "node_ids": [LOADED_VERTEX],
            "vectors": [(0.0, 0.0, NODAL_LOAD)],
        },
        "solve-both-wired",
    )
    metrics = solved["diagnostic_metrics"]

    # THE TWO TOTALS, REPORTED SEPARATELY. The nodal half is exactly what
    # was wired: not a fraction of it, not zero.
    assert metrics["nodal_total_pz"] == pytest.approx(NODAL_LOAD, rel=1e-12)
    # The self-weight half is a real weight, not a rounding error. The
    # plan is 4 x 4 metres at a density of one, so a surface risen out of
    # that plan can never weigh less than 16.
    assert metrics["selfweight_total_pz"] <= -16.0
    # And they are the whole of the load: the two totals add up to the
    # one the equilibrium actually satisfies.
    assert metrics["effective_total_pz"] == pytest.approx(
        metrics["nodal_total_pz"] + metrics["selfweight_total_pz"],
        rel=1e-12,
    )
    assert metrics["selfweight_mode"] == "refined on the solved geometry"

    # ADDITIVE AT THE VERTEX, not merely in the total. The loaded vertex
    # carries its own tributary share AND the point load; every other
    # vertex carries its share alone, and on this fixture no share comes
    # anywhere near the point load.
    pz_by_vertex = effective_pz_by_vertex(solved)
    assert pz_by_vertex[LOADED_VERTEX] < NODAL_LOAD
    others = [
        value
        for vertex, value in pz_by_vertex.items()
        if vertex != LOADED_VERTEX
    ]
    assert others
    assert max(others) < 0.0
    assert min(others) > 0.5 * NODAL_LOAD, (
        "no unloaded vertex should carry anything like the point load: "
        "{}".format(sorted(others))
    )

    # The self-weight alone, everything else equal, is the same solve
    # without the point load: lighter in total, and with the loaded
    # vertex carrying only its own share.
    alone = solve_loads_case(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, -1.0),
            "thickness": 1.0,
            "density": 1.0,
        },
        "solve-selfweight-alone",
    )
    alone_metrics = alone["diagnostic_metrics"]
    assert alone_metrics["nodal_total_pz"] == pytest.approx(0.0, abs=1e-12)
    assert alone_metrics["effective_total_pz"] == pytest.approx(
        alone_metrics["selfweight_total_pz"], rel=1e-12
    )
    assert (
        metrics["effective_total_pz"] < alone_metrics["effective_total_pz"]
    )
    alone_pz = effective_pz_by_vertex(alone)
    assert alone_pz[LOADED_VERTEX] > 0.5 * NODAL_LOAD


def test_a_solve_with_no_selfweight_ships_neither_total():
    """The other half of rule 2.4(b)'s diagnostics: a canvas with point
    loads and no self-weight has ONE load, and effective_total_pz already
    is it. Two more lines saying so, one of them a nought, is the defect
    rule 2.5 spent a round retiring."""

    solved = solve_loads_case(
        {
            "name": "dead",
            "distribution": "point",
            "node_ids": [LOADED_VERTEX],
            "vectors": [(0.0, 0.0, NODAL_LOAD)],
        },
        "solve-nodal-only",
    )
    metrics = solved["diagnostic_metrics"]
    assert metrics["selfweight_mode"] == "none"
    for key in (
        "nodal_total_pz",
        "selfweight_total_pz",
        "selfweight_thickness",
        "selfweight_area_density",
    ):
        assert key not in metrics, (
            "a solve carrying no self-weight is being told about one: "
            "{}".format(sorted(metrics))
        )
    assert metrics["effective_total_pz"] == pytest.approx(
        NODAL_LOAD, rel=1e-12
    )


def test_a_surface_load_authored_before_thickness_and_density_keeps_its_weight():
    """The backwards mapping, pinned.

    Under the OLD model the surface load's whole density was the base
    vector's signed Z: a wire of (0, 0, -4) meant four units of weight
    per square metre, downward. Under rule 2.4(a) the density is the
    THICKNESS times the DENSITY, and the base vector says which way. The
    two meet because both new inputs default to 1.0, so the old wire is
    the new wire with T = 1 and D = 1, and the same weight can be
    authored afresh as a unit downward vector with T = 1 and D = 4.
    """

    old_wire = solve_loads_case(
        {
            "name": "dead",
            "distribution": "tributary_area",
            "base_vector": (0.0, 0.0, -4.0),
        },
        "solve-old-wire",
    )
    # The same canvas reopened, with the two appended ports at the
    # defaults an archived definition gives them.
    defaulted = solve_loads_case(
        {
            "name": "dead",
            "distribution": "tributary_area",
            "base_vector": (0.0, 0.0, -4.0),
            "thickness": 1.0,
            "density": 1.0,
        },
        "solve-old-wire-defaulted",
    )
    # And the weight re-authored under the new model: a unit downward
    # vector, one unit thick, at a density of four.
    new_wire = solve_loads_case(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, -1.0),
            "thickness": 1.0,
            "density": 4.0,
        },
        "solve-new-wire",
    )

    old_metrics = old_wire["diagnostic_metrics"]
    for other in (defaulted, new_wire):
        metrics = other["diagnostic_metrics"]
        assert metrics["effective_total_pz"] == pytest.approx(
            old_metrics["effective_total_pz"], rel=1e-12
        )
        assert metrics["vertical_scale"] == pytest.approx(
            old_metrics["vertical_scale"], rel=1e-12
        )
        assert metrics["selfweight_area_density"] == pytest.approx(
            -4.0, rel=1e-12
        )
        for old_vertex, vertex in zip(
            old_wire["equilibrium"]["vertices"],
            other["equilibrium"]["vertices"],
        ):
            assert vertex[2] == pytest.approx(old_vertex[2], abs=1e-12)

    # The thickness is the other half of the pair, and it multiplies:
    # half the thickness at the same density is half the weight, which is
    # what a canvas asking for a 200 mm shell at 24 units expects.
    halved = solve_loads_case(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, -1.0),
            "thickness": 0.5,
            "density": 4.0,
        },
        "solve-half-thickness",
    )
    assert halved["diagnostic_metrics"]["selfweight_thickness"] == 0.5
    assert halved["diagnostic_metrics"][
        "selfweight_total_load_by_round"
    ][0] == pytest.approx(
        0.5 * old_metrics["selfweight_total_load_by_round"][0], rel=1e-12
    )


def test_a_thickness_or_density_of_zero_is_no_selfweight_not_a_refusal():
    """The value both contracts accept and the solve used to refuse.

    ``LoadsComponent`` permits Thickness and Density of zero or greater
    and ``LoadCaseDto`` permits both zero, so T = 0 validates green on
    the canvas; the adapter then refused the WHOLE solve with "Surface
    loading requires a non-zero vertical vector, thickness and density",
    naming none of the three numbers and taking the author's point loads
    down with it. The worker has read a thickness of nought as a caller
    asking for no weight since the previous round, and the FD path
    returns all-zero records for it, so the refusal was the odd reading
    of three. Zero on either port now means NO SELF-WEIGHT: the node
    loads stand alone and no self-weight diagnostics are shipped for a
    weight nobody asked for.
    """

    for label, thickness, density in (
        ("thickness", 0.0, 1.0),
        ("density", 1.0, 0.0),
    ):
        solved = solve_loads_case(
            {
                "name": "dead",
                "distribution": "self_weight",
                "base_vector": (0.0, 0.0, -1.0),
                "thickness": thickness,
                "density": density,
                "node_ids": [LOADED_VERTEX],
                "vectors": [(0.0, 0.0, NODAL_LOAD)],
            },
            "solve-zero-{}".format(label),
        )
        metrics = solved["diagnostic_metrics"]
        assert metrics["selfweight_mode"] == "none", label
        assert metrics["effective_total_pz"] == pytest.approx(
            NODAL_LOAD, rel=1e-12
        ), label
        for key in ("nodal_total_pz", "selfweight_total_pz"):
            assert key not in metrics, (
                "a zero {} asks for no self-weight, so the solve must not "
                "report one: {}".format(label, sorted(metrics))
            )
        # The point load is where the author put it, and nowhere else.
        pz_by_vertex = effective_pz_by_vertex(solved)
        assert pz_by_vertex[LOADED_VERTEX] == pytest.approx(
            NODAL_LOAD, rel=1e-12
        ), label
        assert all(
            value == pytest.approx(0.0, abs=1e-12)
            for vertex, value in pz_by_vertex.items()
            if vertex != LOADED_VERTEX
        ), label


def test_a_selfweight_wire_that_can_carry_no_load_at_all_is_still_refused():
    """The two wires that stay refused, and the reason each is refused.

    A base vector with no Z says nothing about which way a weight acts,
    and it is the one number the old model could not do without. And a
    zero thickness with no node loads beside it is a solve with no load
    on it at all: allowed through, it reaches the library and comes back
    as `RuntimeError: Factor is exactly singular` behind a wall of
    `dgstrf info 1`, which is precisely the bare-library failure rule 2.3
    of the 2026-09-04 design exists to keep off the canvas.
    """

    def refusal(load_case, request_id):
        response = dispatch(request(
            "tna.solve",
            loads_case_grid_payload(load_case),
            request_id,
        ))
        assert response["type"] == "error", response
        return response["error"]["message"]

    zero_vector = refusal(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, 0.0),
            "thickness": 1.0,
            "density": 1.0,
            "node_ids": [LOADED_VERTEX],
            "vectors": [(0.0, 0.0, NODAL_LOAD)],
        },
        "solve-zero-base-vector",
    )
    assert "base vector with a non-zero Z" in zero_vector

    nothing_at_all = refusal(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, -1.0),
            "thickness": 0.0,
            "density": 1.0,
        },
        "solve-zero-thickness-alone",
    )
    assert "carries no node loads either" in nothing_at_all

    # AND THE WIRE THE GUARD USED TO MISS. A load case that LISTS a node
    # and gives it a zero vector resolves to the mapping {12: 0.0}, which
    # is a truthy container carrying nothing, so a guard written as
    # ``if not pz`` never fired and the canvas got
    # "COMPAS TNA zmax vertical solve failed: RuntimeError: Factor is
    # exactly singular" behind 35 lines of "dgstrf info 1" on stderr:
    # the bare library failure the guard exists to keep off the canvas.
    zero_vectors = refusal(
        {
            "name": "dead",
            "distribution": "self_weight",
            "base_vector": (0.0, 0.0, -1.0),
            "thickness": 0.0,
            "density": 1.0,
            "node_ids": [LOADED_VERTEX],
            "vectors": [(0.0, 0.0, 0.0)],
        },
        "solve-zero-thickness-zero-vector",
    )
    assert "carries no node loads either" in zero_vectors
    assert "Factor is exactly singular" not in zero_vectors


def test_a_point_case_of_all_zero_vectors_is_refused_rather_than_left_to_scipy():
    """The same leak on the branch that never had a guard at all.

    The surface branch's guard is the only one the previous round wrote,
    so a PURE point case listing a node and giving it a zero vector fell
    straight through to the library with the same singular factorisation.
    Rule 2.3 of the 2026-09-04 design is that a canvas is never handed
    scipy's own sentence, and the branch a load arrives on does not
    change that.
    """

    response = dispatch(request(
        "tna.solve",
        loads_case_grid_payload({
            "name": "dead",
            "distribution": "point",
            "node_ids": [LOADED_VERTEX],
            "vectors": [(0.0, 0.0, 0.0)],
        }),
        "solve-point-zero-vector",
    ))
    assert response["type"] == "error", response
    message = response["error"]["message"]
    assert "resolves to no load at all" in message
    assert "Factor is exactly singular" not in message


def test_a_self_balancing_load_still_solves_because_the_guard_asks_each_vertex():
    """The guard asks the VERTEX, not the total, and this is why.

    A total-based guard would refuse this canvas: two point loads of +10
    and -10 sum to nought while carrying real load at both vertices. It
    solves today, so refusing it would be a new refusal of a working
    definition rather than a fence around a library failure. The guard
    therefore fires only when nothing is carried anywhere.
    """

    solved = solve_loads_case(
        {
            "name": "dead",
            "distribution": "point",
            "node_ids": [LOADED_VERTEX - 1, LOADED_VERTEX + 1],
            "vectors": [(0.0, 0.0, 10.0), (0.0, 0.0, -10.0)],
        },
        "solve-self-balancing-pair",
    )
    pz_by_vertex = effective_pz_by_vertex(solved)
    assert pz_by_vertex[LOADED_VERTEX - 1] == pytest.approx(10.0, rel=1e-12)
    assert pz_by_vertex[LOADED_VERTEX + 1] == pytest.approx(-10.0, rel=1e-12)
    assert solved["diagnostic_metrics"]["effective_total_pz"] == pytest.approx(
        0.0, abs=1e-12
    )
