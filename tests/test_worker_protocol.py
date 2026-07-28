from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from ananke_equilibrium.codec import CodecError
from ananke_equilibrium.codec import decode_frame
from ananke_equilibrium.codec import encode_frame
from ananke_equilibrium.codec import read_frame
from ananke_equilibrium.codec import write_frame
from ananke_equilibrium.worker import dispatch
from ananke_equilibrium.worker import serve


def request(command, payload=None, request_id="request-1"):
    return {
        "v": 1,
        "type": "request",
        "id": request_id,
        "command": command,
        "payload": payload or {},
    }


def test_frame_roundtrip_uses_big_endian_length_prefix():
    message = request("system.health", request_id="health-1")

    frame = encode_frame(message)
    assert int.from_bytes(frame[:4], byteorder="big", signed=False) == len(frame) - 4
    assert decode_frame(frame) == message

    stream = BytesIO()
    write_frame(stream, message)
    stream.seek(0)
    assert read_frame(stream) == message
    assert read_frame(stream) is None


def test_frame_codec_rejects_non_finite_json():
    with pytest.raises(CodecError, match="Non-finite"):
        encode_frame({"value": float("nan")})


def test_health_dispatch_reports_runtime_and_optional_capabilities():
    response = dispatch(request("system.health"))

    assert response["type"] == "result"
    assert response["id"] == "request-1"
    health = response["result"]
    assert health["status"] == "ok"
    assert health["worker"]["protocol_version"] == 1
    assert health["python"]["version"]
    assert "compas_fd" in health["packages"]
    assert "fd.solve" in health["capabilities"]
    assert "system.health" in health["capabilities"]["commands"]


def test_unknown_command_returns_structured_error_and_echoes_id():
    response = dispatch(request("python.eval", {"source": "2 + 2"}, "unsafe-1"))

    assert response["type"] == "error"
    assert response["id"] == "unsafe-1"
    assert response["error"]["code"] == "unknown_command"
    assert "not allowed" in response["error"]["message"]
    assert "python.eval" not in response["error"]["details"]["allowed_commands"]


def test_fd_solve_decodes_contracts_and_encodes_stable_snapshot():
    payload = {
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
    calls = []

    def backend(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            equilibrium_vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
            source_edges=((0, 1), (1, 2)),
            member_forces=(10.0, 10.0),
            force_densities=(10.0, 10.0),
            support_reactions=((0, 0.5, 0), (0, 0, 0), (0, 0.5, 0)),
            residuals=((0, 0, 0), (0, 1e-12, 0), (0, 0, 0)),
            fixed=(0, 2),
            loads=((0, 0, 0), (0, -1, 0), (0, 0, 0)),
            report="Injected worker FD solve complete.",
        )

    response = dispatch(
        request("fd.solve", payload, "fd-1"),
        fd_backend=backend,
    )

    assert response["type"] == "result", response
    assert response["id"] == "fd-1"
    assert calls
    assert calls[0]["topology"].topology_hash
    assert calls[0]["supports"].topology_hash == calls[0]["topology"].topology_hash
    assert calls[0]["load_case"].topology_hash == calls[0]["topology"].topology_hash

    solved = response["result"]
    assert solved["solver"] == "fd"
    assert solved["member_forces"] == [10.0, 10.0]
    assert solved["config"]["force_densities"] == 10.0
    assert solved["topology"]["metadata"]["source"] == "test"
    assert solved["provenance"]["protocol_version"] == 1
    assert solved["mappings"]["resolved_support_ids"] == [0, 2]
    assert "session" not in solved

    # The resulting response itself remains valid framed JSON.
    assert decode_frame(encode_frame(response)) == response


def test_solver_stdout_cannot_corrupt_framed_worker_response(capsys):
    payload = {
        "topology": {
            "kind": "line",
            "vertices": [[0, 0, 0], [1, -1, 0], [2, 0, 0]],
            "edges": [[0, 1], [1, 2]],
        },
        "supports": {"mode": "explicit", "node_ids": [0, 2]},
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

    def noisy_backend(**_kwargs):
        print("backend progress that must not enter the protocol")
        return SimpleNamespace(
            equilibrium_vertices=((0, 0, 0), (1, -1, 0), (2, 0, 0)),
            source_edges=((0, 1), (1, 2)),
            member_forces=(10.0, 10.0),
            force_densities=(10.0, 10.0),
            support_reactions=((0, 0.5, 0), (0, 0, 0), (0, 0.5, 0)),
            residuals=((0, 0, 0), (0, 0, 0), (0, 0, 0)),
            fixed=(0, 2),
            loads=((0, 0, 0), (0, -1, 0), (0, 0, 0)),
            report="Noisy backend solve complete.",
        )

    source = BytesIO()
    write_frame(source, request("fd.solve", payload, "noisy-fd"))
    write_frame(source, request("system.shutdown", request_id="stop"))
    source.seek(0)
    target = BytesIO()

    assert serve(source, target, fd_backend=noisy_backend) == 0
    target.seek(0)
    solve_response = read_frame(target)
    shutdown_response = read_frame(target)
    assert solve_response["id"] == "noisy-fd"
    assert solve_response["type"] == "result"
    assert shutdown_response["id"] == "stop"
    assert read_frame(target) is None
    assert "backend progress" in capsys.readouterr().err
