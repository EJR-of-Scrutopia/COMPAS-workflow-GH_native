"""export.compas turns a Result payload into native COMPAS JSON.

The output must rebuild into real COMPAS objects with json_loads, because
that is the entire point: another tool receives working datastructures,
not our schema.
"""

from __future__ import annotations

import pytest

compas = pytest.importorskip("compas")
from compas.data import json_loads

from ananke_equilibrium.gh.export import compas_export_payload


def _tna_result():
    """Shape mirrors ``encode_tna_result`` in codec.py.

    The solved 3D thrust vertices nest under "equilibrium" (the SolvedCase
    snapshot) alongside the reciprocal form/force graphs. Only the form
    graph carries face topology, via ``_diagram_faces``; graph vertices
    carry a plain ``[x, y, z]`` "point" array, not an object.
    """
    return {
        "kind": "Result",
        "solver": "tna",
        "resultSchema": "0.2",
        "equilibrium": {
            "vertices": [
                [0.0, 0.0, 0.5],
                [1.0, 0.0, 0.4],
                [1.0, 1.0, 0.6],
                [0.0, 1.0, 0.5],
            ],
            "edges": [[0, 1], [1, 2], [2, 3], [3, 0]],
        },
        "form_graph": {
            "vertices": [
                {"id": 0, "key": 0, "point": [0.0, 0.0, 0.0]},
                {"id": 1, "key": 1, "point": [1.0, 0.0, 0.0]},
                {"id": 2, "key": 2, "point": [1.0, 1.0, 0.0]},
                {"id": 3, "key": 3, "point": [0.0, 1.0, 0.0]},
            ],
            "edges": [
                {"id": 0, "u": 0, "v": 1},
                {"id": 1, "u": 1, "v": 2},
                {"id": 2, "u": 2, "v": 3},
                {"id": 3, "u": 3, "v": 0},
            ],
            "faces": [{"id": 0, "key": 0, "vertices": [0, 1, 2, 3]}],
        },
        "force_graph": {
            "vertices": [
                {"id": 0, "key": 0, "point": [0.0, 0.0, 0.0]},
                {"id": 1, "key": 1, "point": [1.0, 0.0, 0.0]},
            ],
            "edges": [{"id": 0, "u": 0, "v": 1}],
            "faces": [],
        },
    }


def _fd_result():
    """Shape mirrors ``encode_solved_case`` in codec.py.

    fd.solve returns the solved network flat at the top level (no
    "equilibrium" nesting) and never registers faces or reciprocal
    diagrams; those are TNA-only.
    """
    return {
        "kind": "Result",
        "solver": "fd",
        "resultSchema": "0.2",
        "vertices": [
            [0.0, 0.0, 0.0],
            [1.0, -1.0, 0.0],
            [2.0, 0.0, 0.0],
        ],
        "edges": [[0, 1], [1, 2]],
    }


def test_thrust_mesh_round_trips_into_a_compas_mesh():
    payload = compas_export_payload(_tna_result())

    assert payload["compasVersion"] == compas.__version__
    mesh = json_loads(payload["thrustMesh"])
    assert mesh.number_of_vertices() == 4
    assert mesh.number_of_faces() == 1


def test_form_and_force_diagrams_round_trip_into_compas_graphs():
    payload = compas_export_payload(_tna_result())

    form = json_loads(payload["formDiagram"])
    force = json_loads(payload["forceDiagram"])
    assert form.number_of_nodes() == 4
    assert form.number_of_edges() == 4
    assert force.number_of_nodes() == 2
    assert force.number_of_edges() == 1


def test_fd_result_has_no_diagrams():
    payload = compas_export_payload(_fd_result())
    assert payload["formDiagram"] is None
    assert payload["forceDiagram"] is None


def test_result_without_faces_has_no_mesh():
    result = _tna_result()
    result["form_graph"]["faces"] = []
    payload = compas_export_payload(result)
    assert payload["thrustMesh"] is None


def test_fd_result_has_no_mesh_either():
    # fd.solve never registers faces, so a thrust mesh cannot be built from
    # its flat, faceless snapshot.
    payload = compas_export_payload(_fd_result())
    assert payload["thrustMesh"] is None


def request(command, payload=None, request_id="request-1"):
    # Matches the framed request shape ``worker._validate_request`` expects
    # (``v`` / ``type``), the same helper tests/test_worker_protocol.py uses.
    return {
        "v": 1,
        "type": "request",
        "id": request_id,
        "command": command,
        "payload": payload or {},
    }


def test_export_compas_dispatch_returns_native_compas_json():
    from ananke_equilibrium.worker import dispatch

    response = dispatch(
        request("export.compas", payload={"result": _tna_result()})
    )

    assert response["type"] == "result"
    mesh = json_loads(response["result"]["thrustMesh"])
    assert mesh.number_of_faces() == 1


def test_export_compas_dispatch_rejects_a_non_result_payload():
    from ananke_equilibrium.worker import dispatch

    response = dispatch(
        request("export.compas", payload={"result": {"kind": "Nope"}})
    )

    assert response["type"] == "error"
    assert response["error"]["code"] == "invalid_payload"


def test_export_compas_is_an_advertised_command():
    from ananke_equilibrium.worker import dispatch

    response = dispatch(request("system.health"))
    assert "export.compas" in response["result"]["capabilities"]["commands"]
