"""Argument parsing and subcommand dispatch for the ``ananke`` CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from typing import Mapping
from typing import Optional
from typing import Sequence

from ..codec import CodecError
from ..codec import decode_fd_payload
from ..codec import decode_tna_payload
from ..codec import decode_tna_prepare_payload
from ..contracts import ContractError
from ..worker import health_payload
from .study import StudyError
from .study import build_request
from .study import load_study


_DECODERS = {
    "fd.solve": decode_fd_payload,
    "tna.prepare": decode_tna_prepare_payload,
    "tna.solve": decode_tna_payload,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per command."""

    parser = argparse.ArgumentParser(
        prog="ananke",
        description="Run COMPAS equilibrium studies from the terminal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "health",
        help="Report worker, interpreter, package, and capability state.",
    )
    check = subparsers.add_parser(
        "check",
        help="Validate a study file without solving it.",
    )
    check.add_argument("problem", type=Path, help="Path to problem.json")
    return parser


def _format_health(payload: Mapping[str, Any]) -> str:
    lines = []
    worker = payload.get("worker", {})
    lines.append(
        "{} {}  protocol {}  schema {}".format(
            worker.get("name"),
            worker.get("version"),
            worker.get("protocol_version"),
            worker.get("schema_version"),
        )
    )
    python = payload.get("python", {})
    lines.append(
        "python {} ({})".format(
            python.get("version"),
            python.get("executable"),
        )
    )
    lines.append("")
    lines.append("packages")
    for name in sorted(payload.get("packages", {})):
        version = payload["packages"][name]
        lines.append(
            "  {:<24} {}".format(name, version if version else "not installed")
        )
    lines.append("")
    lines.append("capabilities")
    capabilities = payload.get("capabilities", {})
    for name in sorted(capabilities):
        if name == "commands":
            continue
        lines.append("  {:<24} {}".format(name, capabilities[name]))
    return "\n".join(lines)


def _check(path: Path) -> int:
    """Decode a study payload and report the first contract failure."""

    try:
        study = load_study(path)
    except StudyError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    request = build_request(study)
    decoder = _DECODERS.get(request["command"])
    if decoder is None:
        print(
            "{}: no validator for command {!r}; solve it to validate.".format(
                path,
                request["command"],
            ),
            file=sys.stderr,
        )
        return 1
    try:
        decoder(request["payload"])
    except (CodecError, ContractError) as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    print("{}: valid {} study".format(path, request["command"]))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one CLI invocation and return its process exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    if args.command == "check":
        return _check(args.problem)
    if args.command == "health":
        print(_format_health(health_payload()))
        return 0
    print("Unhandled command: {}".format(args.command), file=sys.stderr)
    return 2


__all__ = ["build_parser", "main"]
