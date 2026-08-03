"""Argument parsing and subcommand dispatch for the ``ananke`` CLI."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from typing import Mapping
from typing import Optional
from typing import Sequence

from ..worker import health_payload


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


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one CLI invocation and return its process exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    if args.command == "health":
        print(_format_health(health_payload()))
        return 0
    print("Unhandled command: {}".format(args.command), file=sys.stderr)
    return 2


__all__ = ["build_parser", "main"]
