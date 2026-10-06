"""Run a trade study from a JSON brief and write the result.

    .venv/Scripts/python.exe scripts/trade_study.py brief.json out.json

The brief holds lines, fixed, rest_lengths, ea, load_pattern, grid, acceptance
and mechanism (the fixed Mechanism fields), with optional steps, max_factor,
steps_per_revolution and microsteps. Units are newtons and millimetres; the
limit_factor in each row is a multiple of load_pattern, not newtons. The output
carries a header naming the checks made and the checks not made.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.trade_study import study

REQUIRED = (
    "lines", "fixed", "rest_lengths", "ea", "load_pattern", "grid",
    "acceptance", "mechanism",
)


class BriefError(RuntimeError):
    pass


def _read_brief(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise BriefError("Cannot read the brief: {}".format(error))
    try:
        brief = json.loads(text)
    except ValueError as error:
        raise BriefError("The brief is not valid JSON: {}".format(error))
    if not isinstance(brief, dict):
        raise BriefError("The brief must be a JSON object.")
    missing = [key for key in REQUIRED if key not in brief]
    if missing:
        raise BriefError("The brief is missing: {}.".format(", ".join(missing)))
    if not isinstance(brief["mechanism"], dict) or not isinstance(brief["grid"], dict):
        raise BriefError("mechanism and grid must be JSON objects.")
    for name, values in brief["grid"].items():
        if not isinstance(values, list) or not values:
            raise BriefError("grid[{!r}] must be a non-empty list.".format(name))
    lines = brief["lines"]
    rest = brief["rest_lengths"]
    if not isinstance(lines, list) or not lines:
        raise BriefError("lines must be a non-empty list.")
    if not isinstance(rest, list) or len(rest) != len(lines):
        raise BriefError(
            "rest_lengths needs one length per line ({}).".format(len(lines))
        )
    for value in rest:
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not (math.isfinite(value) and value > 0.0)
        ):
            raise BriefError("rest_lengths must be finite and greater than zero.")
    try:
        pattern = np.asarray(brief["load_pattern"], dtype=float)
    except (TypeError, ValueError):
        raise BriefError("load_pattern must be a rectangular array of numbers.")
    if pattern.ndim != 2 or pattern.shape[1] != 3 or not np.isfinite(pattern).all():
        raise BriefError("load_pattern must be finite, one [x, y, z] row per vertex.")
    return brief, pattern


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    out = Path(argv[2])
    try:
        brief, pattern = _read_brief(argv[1])
        existed = out.exists()
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.open("ab").close()
        except OSError as error:
            raise BriefError("Cannot write the output: {}".format(error))
        try:
            problem = register_fd_network(brief["lines"])
            extra = {
                key: brief[key]
                for key in ("steps", "max_factor", "steps_per_revolution", "microsteps")
                if key in brief
            }
            written = study(
                problem,
                fixed=brief["fixed"],
                rest_lengths=brief["rest_lengths"],
                ea=brief["ea"],
                load_pattern=pattern,
                grid=brief["grid"],
                acceptance=brief["acceptance"],
                **extra,
                **brief["mechanism"],
            )
            out.write_text(
                json.dumps(written, indent=1, allow_nan=False), encoding="utf-8"
            )
        except BaseException:
            if not existed and out.exists() and out.stat().st_size == 0:
                out.unlink()
            raise
    except (RuntimeError, ValueError, TypeError, KeyError, IndexError) as error:
        print("trade_study: {}".format(error), file=sys.stderr)
        return 1
    results = written["results"]
    skipped = sum(1 for row in results if row["skipped"])
    print(
        "{} combinations ({} skipped as invalid), written to {}".format(
            len(results), skipped, out
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
