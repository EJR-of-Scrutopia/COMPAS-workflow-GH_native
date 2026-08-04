from __future__ import annotations

import pytest

pytest.importorskip("compas_tna")
pytest.importorskip("compas_fd")

from ananke_equilibrium.worker import dispatch
from tree_forest_compas.tna import prepare_tna_pattern
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
    assert metrics["natural_selfweight_frozen"] is True
    # The frozen natural height is unit-relative but stays in the same
    # order of magnitude as the plan; the feedback loop blew far past it.
    assert 0.0 < metrics["zmax_solved"] < 60.0
    # The loads the result reports are the plan-evaluated selfweight the
    # equilibrium actually satisfies: total pz is about minus the plan
    # area, not the area of the risen surface.
    assert metrics["effective_total_pz"] < -100.0
    assert metrics["effective_total_pz"] > -500.0
