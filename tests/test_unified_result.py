"""The worker returns one Result envelope from both solvers.

The C# side keys a single ResultDto off three fields: kind, solver, and
resultSchema. Everything else is the existing per-solver payload unchanged,
so old keys stay where the codecs already put them.
"""

from __future__ import annotations

import pytest

from ananke_equilibrium.codec import encode_result


def test_envelope_adds_exactly_three_keys():
    inner = {"a": 1, "nested": {"b": 2}}
    out = encode_result("tna", inner)

    assert out["kind"] == "Result"
    assert out["solver"] == "tna"
    assert out["resultSchema"] == "0.2"
    assert out["a"] == 1
    assert out["nested"] == {"b": 2}
    assert set(out) == {"kind", "solver", "resultSchema", "a", "nested"}


def test_envelope_rejects_unknown_solver():
    with pytest.raises(ValueError):
        encode_result("ags", {})


def test_envelope_does_not_mutate_the_inner_payload():
    inner = {"kind": "TnaResult"}
    encode_result("tna", inner)
    assert inner == {"kind": "TnaResult"}


def request(command, request_id="t-1", payload=None):
    # Matches the framed request shape ``worker._validate_request`` expects
    # (``v`` / ``type``), the same helper test_worker_protocol.py uses.
    return {
        "v": 1,
        "type": "request",
        "id": request_id,
        "command": command,
        "payload": payload or {},
    }


# Smallest passing tna.solve payload, copied verbatim from the
# ``tna_payload()`` fixture in tests/test_worker_protocol.py: a 3x3 grid,
# boundary supports, a uniform dead load, and a zmax height control.
PAYLOAD = {
    "topology": {
        "kind": "faced",
        "vertices": [
            [float(x), float(y), 0.0]
            for y in range(3)
            for x in range(3)
        ],
        "edges": [
            [0, 1],
            [1, 4],
            [3, 4],
            [0, 3],
            [1, 2],
            [2, 5],
            [4, 5],
            [4, 7],
            [6, 7],
            [3, 6],
            [5, 8],
            [7, 8],
        ],
        "faces": [
            [0, 1, 4, 3],
            [1, 2, 5, 4],
            [3, 4, 7, 6],
            [4, 5, 8, 7],
        ],
        "source_vertex_ids": [
            "grid-{}".format(index) for index in range(9)
        ],
        "length_unit": "m",
        "metadata": {
            "source": "test",
            "analysis_plane": [
                [0, 0, 0],
                [1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
            ],
        },
    },
    "supports": {
        "mode": "boundary",
    },
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
}


def test_tna_solve_dispatch_returns_result_kind():
    pytest.importorskip("compas_tna")
    from ananke_equilibrium.worker import dispatch

    response = dispatch(request("tna.solve", payload=PAYLOAD))
    assert response["result"]["kind"] == "Result"
    assert response["result"]["solver"] == "tna"


# Smallest passing fd.solve payload, copied verbatim from
# test_fd_solve_decodes_contracts_and_encodes_stable_snapshot in
# tests/test_worker_protocol.py: a three-node line with explicit supports
# and a fixed force density.
FD_PAYLOAD = {
    "topology": {
        "kind": "line",
        "vertices": [[0, 0, 0], [1, -1, 0], [2, 0, 0]],
        "edges": [[0, 1], [1, 2]],
        "length_unit": "m",
        "metadata": {"source": "test"},
    },
    "supports": {
        "mode": "explicit",
        "node_ids": [0, 2],
    },
    "load_case": {
        "name": "dead",
        "distribution": "point",
        "node_ids": [1],
        "vectors": [[0, -1, 0]],
    },
    "settings": {
        "force_densities": 10.0,
        "sign_convention": "positive_tension",
    },
}


def test_fd_solve_dispatch_returns_result_kind():
    pytest.importorskip("compas_fd")
    from ananke_equilibrium.worker import dispatch

    response = dispatch(request("fd.solve", payload=FD_PAYLOAD))
    assert response["result"]["kind"] == "Result"
    assert response["result"]["solver"] == "fd"
