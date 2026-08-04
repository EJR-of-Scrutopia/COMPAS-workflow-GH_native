"""Argument parsing and subcommand dispatch for the ``ananke`` CLI."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
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
from ..worker import dispatch
from ..worker import health_payload
from .results import ResultError
from .results import load_result
from .study import StudyError
from .study import build_request
from .study import load_study
from .summary import format_summary
from .summary import is_balanced
from .summary import summarise


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
    solve = subparsers.add_parser(
        "solve",
        help="Solve a study file and write its result.",
    )
    solve.add_argument("problem", type=Path, help="Path to problem.json")
    solve.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Result path. Defaults to results/result.json beside the study.",
    )
    solve.add_argument(
        "--archive",
        action="store_true",
        help="Also write a timestamped copy beside the result.",
    )
    describe = subparsers.add_parser(
        "describe",
        help="Summarise a solved result and check global equilibrium.",
    )
    describe.add_argument("result", type=Path, help="Path to a result JSON file")
    describe.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Residual magnitude accepted as balanced. Default 1e-6.",
    )
    describe.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when the global equilibrium residual exceeds tolerance.",
    )
    plot = subparsers.add_parser(
        "plot",
        help="Draw form and force diagrams from a result file.",
    )
    plot.add_argument("result", type=Path, help="Path to a result JSON file")
    plot.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Image path. Defaults to the result path with a .png suffix.",
    )
    plot.add_argument(
        "--title",
        default=None,
        help="Optional figure title.",
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


def solve_study(
    path: Path,
    out: Optional[Path] = None,
    archive: bool = False,
) -> int:
    """Solve one study file through the same dispatch Grasshopper uses."""

    try:
        study = load_study(path)
    except StudyError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    response = dispatch(build_request(study))
    if response.get("type") == "error":
        error = response.get("error", {})
        print(
            "{}: {} ({})".format(
                path,
                error.get("message", "solve failed"),
                error.get("code", "unknown"),
            ),
            file=sys.stderr,
        )
        details = error.get("details")
        if details:
            print(json.dumps(details, indent=2), file=sys.stderr)
        return 1
    destination = out or (path.parent / "results" / "result.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(response["result"], indent=2, sort_keys=True)
    destination.write_text(payload + "\n", encoding="utf-8")
    print("{} -> {}".format(path, destination))
    if archive:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        archived = destination.with_name(
            "{}-{}{}".format(destination.stem, stamp, destination.suffix)
        )
        archived.write_text(payload + "\n", encoding="utf-8")
        print("archived -> {}".format(archived))
    return 0


def _describe(path: Path, tolerance: float, strict: bool) -> int:
    """Print the structural summary of one result file."""

    try:
        summary = summarise(load_result(path))
    except ResultError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    print(format_summary(summary, tolerance=tolerance))
    if strict and not is_balanced(summary, tolerance=tolerance):
        print(
            "{}: global equilibrium residual exceeds {}.".format(path, tolerance),
            file=sys.stderr,
        )
        return 1
    return 0


def _plot(path: Path, out: Optional[Path], title: Optional[str]) -> int:
    """Draw the diagrams for one result file.

    matplotlib is imported here rather than at module scope so that solving,
    checking, describing, and health reporting all work in an environment
    that has no plotting stack.
    """

    try:
        from .plot import plot_result
    except ImportError as error:
        print(
            "{}: plotting needs matplotlib. Install the plot extra: "
            'python -m pip install -e ".[plot]"  ({})'.format(path, error),
            file=sys.stderr,
        )
        return 1
    try:
        result = load_result(path)
        written = plot_result(result, out or path.with_suffix(".png"), title=title)
    except ResultError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    print("{} -> {}".format(path, written))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one CLI invocation and return its process exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    if args.command == "solve":
        return solve_study(args.problem, out=args.out, archive=args.archive)
    if args.command == "check":
        return _check(args.problem)
    if args.command == "describe":
        return _describe(args.result, args.tolerance, args.strict)
    if args.command == "plot":
        return _plot(args.result, args.out, args.title)
    if args.command == "health":
        print(_format_health(health_payload()))
        return 0
    print("Unhandled command: {}".format(args.command), file=sys.stderr)
    return 2


__all__ = ["build_parser", "main", "solve_study"]
