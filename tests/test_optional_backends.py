"""Integration tests run when the pinned COMPAS equilibrium extra is present."""

from __future__ import annotations

import pytest


pytest.importorskip("compas_fd")
pytest.importorskip("compas_tna")

from ananke_equilibrium import FDConfig
from ananke_equilibrium import HeightControl
from ananke_equilibrium import TNAConfig
from ananke_equilibrium.gh import build_load_case
from ananke_equilibrium.gh import build_network
from ananke_equilibrium.gh import build_preview_payload
from ananke_equilibrium.gh import build_support_set
from ananke_equilibrium.gh import solve_fd
from ananke_equilibrium.gh import solve_tna
from ananke_equilibrium.gh import validate_result
from ananke_equilibrium.worker import dispatch


def value(result):
    assert result.ok, result.status.message
    return result.unwrap()


def test_real_fd_backend_through_bundle_api():
    topology = value(
        build_network(
            (
                ((-5, 0, 0), (0, 0, -1)),
                ((0, 0, -1), (5, 0, 0)),
            )
        )
    )
    supports = value(
        build_support_set(node_ids=(0, 2), topology=topology)
    )
    loads = value(
        build_load_case(
            vectors=((0, 0, -1),),
            node_ids=(1,),
            topology=topology,
        )
    )

    case = value(solve_fd(topology, supports, loads, FDConfig(10.0)))
    diagnostics = value(validate_result(case))

    assert len(case.member_forces) == 2
    assert next(
        item.value for item in diagnostics if item.code == "equilibrium.residual"
    ) == pytest.approx(0.0, abs=1.0e-12)


def test_real_tna_backend_through_bundle_and_preview_api():
    vertices = tuple(
        (float(x), float(y), 0.0)
        for y in range(3)
        for x in range(3)
    )
    topology = value(
        build_network(
            vertices=vertices,
            faces=(
                (0, 1, 4, 3),
                (1, 2, 5, 4),
                (3, 4, 7, 6),
                (4, 5, 8, 7),
            ),
            kind="faced",
        )
    )
    supports = value(build_support_set(mode="boundary", topology=topology))
    loads = value(
        build_load_case(
            vectors=((0, 0, -1),),
            distribution="uniform_nodes",
            topology=topology,
        )
    )

    case = value(
        solve_tna(
            topology,
            supports,
            loads,
            HeightControl.crown_height(1.0),
            TNAConfig(),
        )
    )
    diagram = value(build_preview_payload(case))

    assert len(case.member_forces) == 4
    assert len(diagram.primitives) == 4


def test_real_tna_backend_through_worker_preserves_reciprocal_state():
    vertices = [
        [float(x), float(y), 0.0]
        for y in range(3)
        for x in range(3)
    ]
    faces = [
        [0, 1, 4, 3],
        [1, 2, 5, 4],
        [3, 4, 7, 6],
        [4, 5, 8, 7],
    ]
    edges = []
    seen = set()
    for face in faces:
        for index, u in enumerate(face):
            v = face[(index + 1) % len(face)]
            edge = (min(u, v), max(u, v))
            if edge not in seen:
                seen.add(edge)
                edges.append(list(edge))

    response = dispatch(
        {
            "v": 1,
            "type": "request",
            "id": "real-tna",
            "command": "tna.solve",
            "payload": {
                "topology": {
                    "kind": "faced",
                    "vertices": vertices,
                    "edges": edges,
                    "faces": faces,
                    "source_vertex_ids": [
                        "grid-{}".format(index)
                        for index in range(len(vertices))
                    ],
                    "length_unit": "m",
                    "metadata": {
                        "analysis_plane": [
                            [0, 0, 0],
                            [1, 0, 0],
                            [0, 1, 0],
                            [0, 0, 1],
                        ]
                    },
                },
                "supports": {"mode": "boundary"},
                "load_case": {
                    "name": "dead",
                    "distribution": "uniform_nodes",
                    "base_vector": [0, 0, -1],
                },
                "control": {
                    "height_control": {
                        "mode": "zmax",
                        "value": 1.0,
                    },
                    "settings": {
                        "horizontal_alpha": 100.0,
                        "horizontal_iterations": 100,
                        "vertical_iterations": 100,
                        "tolerance": 1.0e-3,
                    },
                },
            },
        }
    )

    assert response["type"] == "result", response
    result = response["result"]
    assert result["kind"] == "Result"
    assert result["solver"] == "tna"
    assert result["equilibrium"]["solver"] == "tna"
    assert len(result["form_graph"]["edges"]) == 4
    assert len(result["force_graph"]["edges"]) == 4
    assert len(result["edge_states"]) == 4
    assert result["horizontal_scale"] == pytest.approx(-0.375)
    assert all(
        state["force_state"] == "compression"
        for state in result["edge_states"]
    )
    assert all(
        state["reciprocity_error_degrees"] <= 1.0e-8
        for state in result["edge_states"]
    )
    assert all(
        state["source_edge_ids"]
        for state in result["edge_states"]
    )
    assert len(result["mappings"]["supports"]) == 4
    assert result["mappings"]["supports"][0]["source_vertex_id"] == "grid-1"
