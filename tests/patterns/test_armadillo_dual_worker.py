"""Task 3 of the Armadillo Dual wave: the wire command "pattern.armadillo_dual".

Follows the dispatch-test pattern established for "export.compas" in
tests/test_export_compas.py (the same ``request()`` framed-request helper,
the same dispatch-then-assert-on-response-type shape, and the same
"is an advertised command" check against ``system.health``'s capabilities).

This file lives in tests/patterns/ (rather than beside test_export_compas.py
at the tests/ root) specifically so it inherits ``dome_result`` from the
sibling tests/patterns/conftest.py through pytest's ordinary directory-scoped
fixture resolution -- neither tests/ nor tests/patterns/ has an __init__.py,
so "tests.patterns.conftest" is not an importable dotted module path from a
tests/-root test file; co-locating the test here is what "reusing
tests/patterns/conftest.py's dome_result via a conftest import" resolves to
under this repo's (package-less) test layout, with no import statement
needed at all.
"""

from __future__ import annotations

import pytest

from ananke_equilibrium.patterns.armadillo_dual import PatternRefused
from ananke_equilibrium.patterns.armadillo_dual import field_source
from ananke_equilibrium.patterns.armadillo_dual import generate
from ananke_equilibrium.worker import ALLOWED_COMMANDS
from ananke_equilibrium.worker import dispatch


def request(command, payload=None, request_id="request-1"):
    # Matches the framed request shape ``worker._validate_request`` expects
    # (``v`` / ``type``), the same helper tests/test_export_compas.py and
    # tests/test_worker_protocol.py use.
    return {
        "v": 1,
        "type": "request",
        "id": request_id,
        "command": command,
        "payload": payload or {},
    }


def test_allowed_commands_includes_pattern_armadillo_dual():
    assert "pattern.armadillo_dual" in ALLOWED_COMMANDS


def test_pattern_armadillo_dual_is_an_advertised_command():
    response = dispatch(request("system.health"))
    assert "pattern.armadillo_dual" in response["result"]["capabilities"]["commands"]


def test_unknown_command_is_still_rejected():
    # Unrelated to this task's change, but pins that adding a command to
    # ALLOWED_COMMANDS does not loosen the allowlist check for everyone else.
    response = dispatch(request("pattern.nonexistent"))
    assert response["type"] == "error"
    assert response["error"]["code"] == "unknown_command"


def test_pattern_armadillo_dual_dispatch_returns_the_generate_response_shape(dome_result):
    result, _geometry = dome_result(n_rings=6, n_segments=12)

    response = dispatch(
        request("pattern.armadillo_dual", payload={"result": result, "size": 1.0})
    )

    assert response["type"] == "result"
    payload = response["result"]
    assert set(payload.keys()) == {"cells", "flowlines", "diagnostics"}
    assert payload["diagnostics"]["field_source"] == "forces"
    assert len(payload["cells"]) > 0
    assert len(payload["flowlines"]) > 0
    for cell in payload["cells"]:
        assert set(cell.keys()) == {"outline", "course"}

    # The dispatch response must be exactly generate()'s own output passed
    # through untouched (it is already JSON-plain), not a re-shaped copy.
    direct = generate(result, size=1.0)
    assert payload == direct


def test_pattern_armadillo_dual_dispatch_defaults_missing_size_to_0_4(
    monkeypatch, dome_result
):
    # The honest check: capture the actual size argument dispatch() passes
    # to generate(), rather than inferring the default from an observable
    # side effect of the real algorithm.
    import ananke_equilibrium.patterns.armadillo_dual as armadillo_dual_module

    captured = {}

    def fake_generate(result, size):
        captured["result"] = result
        captured["size"] = size
        return {"cells": [], "flowlines": [], "diagnostics": {}}

    monkeypatch.setattr(armadillo_dual_module, "generate", fake_generate)

    result, _geometry = dome_result(n_rings=6, n_segments=12)
    response = dispatch(
        request("pattern.armadillo_dual", payload={"result": result})
    )

    assert response["type"] == "result"
    assert captured["size"] == 0.4
    assert captured["result"] is result


def test_pattern_armadillo_dual_dispatch_rejects_a_missing_result():
    response = dispatch(request("pattern.armadillo_dual", payload={"size": 0.4}))
    assert response["type"] == "error"
    assert response["error"]["code"] == "invalid_payload"


def test_pattern_armadillo_dual_dispatch_rejects_a_none_result():
    response = dispatch(
        request("pattern.armadillo_dual", payload={"result": None, "size": 0.4})
    )
    assert response["type"] == "error"
    assert response["error"]["code"] == "invalid_payload"


def test_pattern_armadillo_dual_dispatch_rejects_a_non_result_payload():
    response = dispatch(
        request(
            "pattern.armadillo_dual",
            payload={"result": {"kind": "Nope"}, "size": 0.4},
        )
    )
    assert response["type"] == "error"
    assert response["error"]["code"] == "invalid_payload"


def test_pattern_armadillo_dual_dispatch_maps_pattern_refused_to_the_error_envelope_verbatim(
    dome_result,
):
    result, _geometry = dome_result(include_forces=False, include_diagrams=False)

    # Get the exact message ``generate`` will raise with, straight from the
    # algorithm itself, so this test does not hardcode a copy that could
    # silently drift from the real refusal text.
    with pytest.raises(PatternRefused) as excinfo:
        field_source(result)
    expected_message = str(excinfo.value)

    response = dispatch(
        request("pattern.armadillo_dual", payload={"result": result, "size": 1.0})
    )

    assert response["type"] == "error"
    assert response["error"]["message"] == expected_message
