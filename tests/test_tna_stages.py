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
