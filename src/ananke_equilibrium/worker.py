"""Persistent finite-JSON worker for native Grasshopper components.

Run with the exact Python environment used for COMPAS::

    python -m ananke_equilibrium.worker

Standard output is reserved exclusively for framed protocol messages.  Human
readable diagnostics and tracebacks are written to standard error.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from importlib import metadata as importlib_metadata
import platform
import sys
import traceback
from typing import Any
from typing import Callable
from typing import Dict
from typing import Mapping
from typing import Optional
from typing import Tuple

from . import __version__
from .codec import CodecError
from .codec import FrameTooLargeError
from .codec import MAX_FRAME_BYTES
from .codec import TruncatedFrameError
from .codec import decode_fd_payload
from .codec import decode_tna_prepare_payload
from .codec import decode_tna_payload
from .codec import encode_result
from .codec import encode_solved_case
from .codec import encode_tna_prepared
from .codec import encode_tna_result
from .codec import read_frame
from .codec import to_json_value
from .codec import write_frame
from .contracts import ContractError
from .contracts import SCHEMA_VERSION
from .gh import ComponentResult
from .gh import solve_fd
from .gh import prepare_tna
from .gh import solve_tna


PROTOCOL_VERSION = 1
WORKER_NAME = "ananke-equilibrium-worker"
ALLOWED_COMMANDS = frozenset(
    (
        "system.hello",
        "system.health",
        "system.shutdown",
        "fd.solve",
        "tna.prepare",
        "tna.solve",
        "export.compas",
        "pattern.armadillo_dual",
    )
)

_PACKAGE_DISTRIBUTIONS = (
    "ananke-equilibrium",
    "compas",
    "compas_fd",
    "compas_tna",
    "compas_ags",
    "compas_model",
    "compas_fea2",
    "compas_ifc",
    # Masonry family, backing the "04 Masonry" tab.
    "compas_dem",
    "compas_assembly",
    "compas_cra",
    # Digital fabrication family, backing the "07 Fabrication" tab.
    "compas_fab",
    "compas_robots",
    # Patterns family, backing the TNA Pattern generator modes.
    "compas_skeleton",
)

# Backend plugins for compas_fea2. None of them are published to PyPI, so a
# present compas_fea2 says nothing about whether an analysis can actually run.
_FEA2_BACKENDS = (
    "compas_fea2_opensees",
    "compas_fea2_abaqus",
    "compas_fea2_ansys",
    "compas_fea2_sofistik",
    "compas_fea2_castem",
)


class ProtocolError(ValueError):
    """Expected request error that can be returned without a traceback."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.details = dict(details or {})


def result_response(request_id: Any, payload: Any) -> Dict[str, Any]:
    """Create a successful protocol response."""

    return {
        "v": PROTOCOL_VERSION,
        "type": "result",
        "id": request_id,
        "result": to_json_value(payload),
    }


def error_response(
    request_id: Any,
    code: str,
    message: str,
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a structured protocol error."""

    return {
        "v": PROTOCOL_VERSION,
        "type": "error",
        "id": request_id,
        "error": {
            "code": str(code),
            "message": str(message),
            "details": to_json_value(dict(details or {})),
        },
    }


def event_response(request_id: Any, event: str, payload: Any) -> Dict[str, Any]:
    """Create a protocol event for future progress reporting."""

    return {
        "v": PROTOCOL_VERSION,
        "type": "event",
        "id": request_id,
        "event": str(event),
        "payload": to_json_value(payload),
    }


def _distribution_version(name: str) -> Optional[str]:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None
    except Exception:
        # A broken optional package must not make health checks unavailable.
        return None


def _installed_fea2_backends() -> Tuple[str, ...]:
    """Return the compas_fea2 solver backends present in this environment.

    Checked by distribution metadata rather than import, so a backend that
    needs its solver executable on PATH is still reported as installed and the
    check stays cheap and side-effect free.
    """
    return tuple(
        name
        for name in _FEA2_BACKENDS
        if _distribution_version(name) is not None
    )


def health_payload() -> Dict[str, Any]:
    """Return environment information without importing optional backends."""

    packages = {
        name: _distribution_version(name)
        for name in _PACKAGE_DISTRIBUTIONS
    }
    packages["ananke-equilibrium"] = (
        packages["ananke-equilibrium"] or __version__
    )
    fea2_backends = _installed_fea2_backends()
    return {
        "status": "ok",
        "worker": {
            "name": WORKER_NAME,
            "version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "packages": packages,
        "capabilities": {
            "commands": sorted(ALLOWED_COMMANDS),
            "fd.solve": packages["compas_fd"] is not None,
            "tna.prepare": (
                packages["compas_fd"] is not None
                and packages["compas_tna"] is not None
            ),
            "tna.solve": packages["compas_tna"] is not None,
            "ags.solve": packages["compas_ags"] is not None,
            "model": packages["compas_model"] is not None,
            # compas_fea2 without a solver backend can express a model but
            # cannot analyse one, so the flag tracks the backend, not the
            # package. "fea.model" reports the weaker, honest claim.
            "fea": (
                packages["compas_fea2"] is not None
                and bool(fea2_backends)
            ),
            "fea.model": packages["compas_fea2"] is not None,
            "fea.backends": list(fea2_backends),
            "ifc": packages["compas_ifc"] is not None,
            # Masonry needs the whole chain: block geometry, contact assembly,
            # and the equilibrium solver. Any one missing leaves the tab unable
            # to complete a build-stage analysis.
            "masonry": (
                packages["compas_dem"] is not None
                and packages["compas_assembly"] is not None
                and packages["compas_cra"] is not None
            ),
            "fab": (
                packages["compas_fab"] is not None
                and packages["compas_robots"] is not None
            ),
            "patterns": packages["compas_skeleton"] is not None,
        },
    }


def hello_payload() -> Dict[str, Any]:
    """Return the protocol negotiation payload."""

    health = health_payload()
    return {
        "name": WORKER_NAME,
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "max_frame_bytes": MAX_FRAME_BYTES,
        "commands": sorted(ALLOWED_COMMANDS),
        "health": health,
    }


def _validate_request(request: Any) -> Dict[str, Any]:
    if not isinstance(request, Mapping):
        raise ProtocolError(
            "invalid_request",
            "A request must be a JSON object.",
        )
    data = dict(request)
    request_id = data.get("id")
    if data.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(
            "unsupported_version",
            "Protocol version {} is required.".format(PROTOCOL_VERSION),
            {"received": data.get("v"), "request_id": request_id},
        )
    if data.get("type") != "request":
        raise ProtocolError(
            "invalid_request",
            "Request type must be 'request'.",
            {"received": data.get("type"), "request_id": request_id},
        )
    if "id" not in data:
        raise ProtocolError(
            "invalid_request",
            "A request id is required.",
        )
    command = data.get("command")
    if not isinstance(command, str) or not command:
        raise ProtocolError(
            "invalid_request",
            "A non-empty command string is required.",
            {"request_id": request_id},
        )
    if command not in ALLOWED_COMMANDS:
        raise ProtocolError(
            "unknown_command",
            "Command {!r} is not allowed.".format(command),
            {
                "command": command,
                "allowed_commands": sorted(ALLOWED_COMMANDS),
                "request_id": request_id,
            },
        )
    payload = data.get("payload", {})
    if not isinstance(payload, Mapping):
        raise ProtocolError(
            "invalid_payload",
            "Request payload must be a JSON object.",
            {"command": command, "request_id": request_id},
        )
    data["payload"] = dict(payload)
    return data


def _fd_payload(
    payload: Mapping[str, Any],
    *,
    fd_backend: Any = None,
    fd_solver: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    topology, supports, load_case, settings = decode_fd_payload(payload)
    solver = fd_solver or solve_fd
    component_result = solver(
        topology,
        supports,
        load_case,
        settings,
        backend=fd_backend,
    )
    if not isinstance(component_result, ComponentResult):
        raise ProtocolError(
            "solver_contract_error",
            "FD solver returned {}, not ComponentResult.".format(
                type(component_result).__name__
            ),
        )
    if not component_result.ok or component_result.value is None:
        status = component_result.status
        raise ProtocolError(
            "fd_solve_failed",
            status.message,
            {
                "severity": status.severity,
                "details": dict(status.details),
            },
        )
    status = component_result.status
    return encode_solved_case(
        component_result.unwrap(),
        provenance={
            "worker": WORKER_NAME,
            "worker_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "adapter_status": {
                "severity": status.severity,
                "message": status.message,
                "details": dict(status.details),
            },
        },
    )


def _tna_prepare_payload(
    payload: Mapping[str, Any],
    *,
    tna_prepare_backend: Any = None,
    tna_prepare_solver: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    topology, supports, settings = decode_tna_prepare_payload(payload)
    solver = tna_prepare_solver or prepare_tna
    component_result = solver(
        topology,
        supports,
        settings,
        backend=tna_prepare_backend,
    )
    if not isinstance(component_result, ComponentResult):
        raise ProtocolError(
            "solver_contract_error",
            "TNA Prepare returned {}, not ComponentResult.".format(
                type(component_result).__name__
            ),
        )
    if not component_result.ok or component_result.value is None:
        status = component_result.status
        raise ProtocolError(
            "tna_prepare_failed",
            status.message,
            {
                "severity": status.severity,
                "details": dict(status.details),
            },
        )
    status = component_result.status
    return encode_tna_prepared(
        component_result.unwrap(),
        provenance={
            "worker": WORKER_NAME,
            "worker_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SCHEMA_VERSION,
            "adapter_status": {
                "severity": status.severity,
                "message": status.message,
                "details": dict(status.details),
            },
        },
    )


def _tna_payload(
    payload: Mapping[str, Any],
    *,
    tna_backend: Any = None,
    tna_solver: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    (
        topology,
        supports,
        load_case,
        height_control,
        settings,
    ) = decode_tna_payload(payload)
    solver = tna_solver or solve_tna
    component_result = solver(
        topology,
        supports,
        load_case,
        height_control,
        settings,
        backend=tna_backend,
    )
    if not isinstance(component_result, ComponentResult):
        raise ProtocolError(
            "solver_contract_error",
            "TNA solver returned {}, not ComponentResult.".format(
                type(component_result).__name__
            ),
        )
    if not component_result.ok or component_result.value is None:
        status = component_result.status
        raise ProtocolError(
            "tna_solve_failed",
            status.message,
            {
                "severity": status.severity,
                "details": dict(status.details),
            },
        )
    status = component_result.status
    provenance = {
        "worker": WORKER_NAME,
        "worker_version": __version__,
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "adapter_status": {
            "severity": status.severity,
            "message": status.message,
            "details": dict(status.details),
        },
    }
    return encode_tna_result(
        component_result.unwrap(),
        height_control,
        settings,
        provenance=provenance,
    )


def dispatch(
    request: Any,
    *,
    fd_backend: Any = None,
    fd_solver: Optional[Callable[..., Any]] = None,
    tna_prepare_backend: Any = None,
    tna_prepare_solver: Optional[Callable[..., Any]] = None,
    tna_backend: Any = None,
    tna_solver: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Dispatch one decoded request against the fixed command allowlist."""

    request_id = request.get("id") if isinstance(request, Mapping) else None
    try:
        data = _validate_request(request)
        request_id = data["id"]
        command = data["command"]
        payload = data["payload"]
        if command == "system.hello":
            return result_response(request_id, hello_payload())
        if command == "system.health":
            return result_response(request_id, health_payload())
        if command == "system.shutdown":
            return result_response(request_id, {"shutdown": True})
        if command == "fd.solve":
            return result_response(
                request_id,
                encode_result(
                    "fd",
                    _fd_payload(
                        payload,
                        fd_backend=fd_backend,
                        fd_solver=fd_solver,
                    ),
                ),
            )
        if command == "tna.prepare":
            return result_response(
                request_id,
                _tna_prepare_payload(
                    payload,
                    tna_prepare_backend=tna_prepare_backend,
                    tna_prepare_solver=tna_prepare_solver,
                ),
            )
        if command == "tna.solve":
            return result_response(
                request_id,
                encode_result(
                    "tna",
                    _tna_payload(
                        payload,
                        tna_backend=tna_backend,
                        tna_solver=tna_solver,
                    ),
                ),
            )
        if command == "export.compas":
            from .gh.export import compas_export_payload

            result = payload.get("result")
            if not isinstance(result, Mapping) or result.get("kind") != "Result":
                raise ProtocolError(
                    "invalid_payload",
                    "export.compas requires a Result payload.",
                    {"request_id": request_id},
                )
            return result_response(request_id, compas_export_payload(result))
        if command == "pattern.armadillo_dual":
            from .patterns.armadillo_dual import DEFAULT_SIZE
            from .patterns.armadillo_dual import PatternRefused
            from .patterns.armadillo_dual import generate as armadillo_dual_generate

            result = payload.get("result")
            if not isinstance(result, Mapping) or result.get("kind") != "Result":
                raise ProtocolError(
                    "invalid_payload",
                    "pattern.armadillo_dual requires a Result payload.",
                    {"request_id": request_id},
                )
            size = payload.get("size")
            # The generator owns the default (armadillo_dual.DEFAULT_SIZE),
            # so the worker's fallback and the component's S default cannot
            # drift apart.
            size = DEFAULT_SIZE if size is None else float(size)
            try:
                pattern_payload = armadillo_dual_generate(result, size)
            except PatternRefused as error:
                raise ProtocolError(
                    "pattern_refused",
                    str(error),
                    {"request_id": request_id},
                ) from error
            return result_response(request_id, pattern_payload)
        # Defensive only: _validate_request already enforces the allowlist.
        raise ProtocolError(
            "unknown_command",
            "Command {!r} is not implemented.".format(command),
        )
    except ProtocolError as error:
        request_id = error.details.pop("request_id", request_id)
        return error_response(
            request_id,
            error.code,
            error.message,
            error.details,
        )
    except (CodecError, ContractError, TypeError, ValueError) as error:
        return error_response(
            request_id,
            "invalid_payload",
            str(error),
            {"exception": type(error).__name__},
        )
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        return error_response(
            request_id,
            "internal_error",
            "The worker encountered an unexpected error.",
            {"exception": type(error).__name__},
        )


def _is_successful_shutdown(request: Any, response: Mapping[str, Any]) -> bool:
    return (
        isinstance(request, Mapping)
        and request.get("v") == PROTOCOL_VERSION
        and request.get("type") == "request"
        and request.get("command") == "system.shutdown"
        and response.get("type") == "result"
    )


def serve(
    input_stream: Any = None,
    output_stream: Any = None,
    *,
    fd_backend: Any = None,
    fd_solver: Optional[Callable[..., Any]] = None,
    tna_prepare_backend: Any = None,
    tna_prepare_solver: Optional[Callable[..., Any]] = None,
    tna_backend: Any = None,
    tna_solver: Optional[Callable[..., Any]] = None,
    max_frame_bytes: int = MAX_FRAME_BYTES,
) -> int:
    """Serve framed requests until EOF or a successful shutdown command."""

    source = input_stream if input_stream is not None else sys.stdin.buffer
    target = output_stream if output_stream is not None else sys.stdout.buffer
    while True:
        try:
            request = read_frame(source, max_frame_bytes=max_frame_bytes)
        except FrameTooLargeError as error:
            print("{}: {}".format(WORKER_NAME, error), file=sys.stderr)
            write_frame(
                target,
                error_response(None, "frame_too_large", str(error)),
                max_frame_bytes=max_frame_bytes,
            )
            return 2
        except TruncatedFrameError as error:
            print("{}: {}".format(WORKER_NAME, error), file=sys.stderr)
            return 2
        except CodecError as error:
            print("{}: {}".format(WORKER_NAME, error), file=sys.stderr)
            write_frame(
                target,
                error_response(None, "invalid_frame", str(error)),
                max_frame_bytes=max_frame_bytes,
            )
            continue
        if request is None:
            return 0
        # Third-party numerical backends occasionally print progress. Keep
        # those bytes away from the framed stdout protocol and surface them
        # through the worker's captured stderr diagnostics instead.
        with redirect_stdout(sys.stderr):
            response = dispatch(
                request,
                fd_backend=fd_backend,
                fd_solver=fd_solver,
                tna_prepare_backend=tna_prepare_backend,
                tna_prepare_solver=tna_prepare_solver,
                tna_backend=tna_backend,
                tna_solver=tna_solver,
            )
        try:
            write_frame(
                target,
                response,
                max_frame_bytes=max_frame_bytes,
            )
        except CodecError:
            traceback.print_exc(file=sys.stderr)
            fallback = error_response(
                response.get("id"),
                "response_encoding_failed",
                "The worker could not encode the command response.",
            )
            write_frame(
                target,
                fallback,
                max_frame_bytes=max_frame_bytes,
            )
        if _is_successful_shutdown(request, response):
            return 0


def main() -> int:
    """Process entry point used by ``python -m ananke_equilibrium.worker``."""

    protocol_output = sys.stdout.buffer
    return serve(output_stream=protocol_output)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ALLOWED_COMMANDS",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "WORKER_NAME",
    "dispatch",
    "error_response",
    "event_response",
    "health_payload",
    "hello_payload",
    "main",
    "result_response",
    "serve",
]
