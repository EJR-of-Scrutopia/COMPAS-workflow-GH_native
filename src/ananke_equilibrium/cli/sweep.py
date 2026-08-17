"""Solve one study under several load cases and compare the results.

A funicular is funicular for one load case. Change the loading and the
thrust surface that was in pure compression may no longer be. Asking that
question means re-solving, which on a canvas means rewiring, and here means
one command over a list.

Each case is a patch deep-merged into the study payload, so a case states
only what it changes.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence

from ..worker import dispatch
from .study import build_request
from .summary import summarise


class SweepError(ValueError):
    """Raised when a case list cannot be read or applied."""


def deep_merge(base: Mapping[str, Any], patch: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge patch into base, recursing into nested objects.

    Lists replace wholesale rather than merging element by element: a load
    vector list is one value, not a sequence to be spliced.
    """

    merged = dict(base)
    for key, value in patch.items():
        if (
            key in merged
            and isinstance(merged[key], Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_cases(path: Path) -> List[Dict[str, Any]]:
    """Read a case list: a JSON array of {name, patch} objects."""

    path = Path(path)
    if not path.is_file():
        raise SweepError("Case file does not exist: {}".format(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SweepError("{} is not valid JSON: {}".format(path, error))
    if not isinstance(document, list) or not document:
        raise SweepError("A case file must contain a non-empty JSON array.")
    cases = []
    for index, entry in enumerate(document):
        if not isinstance(entry, Mapping):
            raise SweepError("Case {} is not a JSON object.".format(index))
        name = entry.get("name")
        patch = entry.get("patch", {})
        if not isinstance(name, str) or not name:
            raise SweepError("Case {} requires a name.".format(index))
        if not isinstance(patch, Mapping):
            raise SweepError("Case {!r} requires a patch object.".format(name))
        cases.append({"name": name, "patch": dict(patch)})
    return cases


def run_cases(
    study: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Solve the study once per case and summarise each outcome."""

    outcomes = []
    for case in cases:
        patched = dict(study)
        patched["payload"] = deep_merge(study["payload"], case["patch"])
        response = dispatch(build_request(patched))
        if response.get("type") == "error":
            error = response.get("error", {})
            outcomes.append(
                {
                    "name": case["name"],
                    "ok": False,
                    "message": error.get("message", "solve failed"),
                    "code": error.get("code", "unknown"),
                    "summary": None,
                    "result": None,
                }
            )
            continue
        result = response["result"]
        outcomes.append(
            {
                "name": case["name"],
                "ok": True,
                "message": None,
                "code": None,
                "summary": summarise(result),
                "result": result,
            }
        )
    return outcomes


def _cell(value: Optional[float], places: int = 3) -> str:
    if value is None:
        return "-"
    return "{:.{}f}".format(float(value), places)


def format_sweep(outcomes: Sequence[Mapping[str, Any]], tolerance: float = 1e-6) -> str:
    """Render the comparison as one table."""

    header = (
        "{:<22} {:>7} {:>10} {:>11} {:>11} {:>6} {:>7} {:>10}".format(
            "case",
            "rise",
            "rise/span",
            "min force",
            "max force",
            "comp",
            "tens",
            "residual",
        )
    )
    lines = [header, "-" * len(header)]
    for outcome in outcomes:
        if not outcome["ok"]:
            lines.append(
                "{:<22} {}".format(
                    outcome["name"][:22],
                    "FAILED: {}".format(outcome["message"]),
                )
            )
            continue
        summary = outcome["summary"]
        geometry = summary["geometry"]
        forces = summary["forces"]
        actions = summary["actions"]
        span = geometry["span_x"] or None
        lines.append(
            "{:<22} {:>7} {:>10} {:>11} {:>11} {:>6} {:>7} {:>10}".format(
                outcome["name"][:22],
                _cell(geometry["rise"]),
                _cell(geometry["rise"] / span if span else None, 4),
                _cell(forces["min"]),
                _cell(forces["max"]),
                forces["compression"],
                forces["tension"],
                "{:.2e}".format(actions["residual_magnitude"]),
            )
        )

    lines.append("")
    tensioned = [
        outcome["name"]
        for outcome in outcomes
        if outcome["ok"] and outcome["summary"]["forces"]["tension"] > 0
    ]
    if tensioned:
        lines.append(
            "Tension appears under: {}. A compression-only vault cannot "
            "deliver that without a tie, a change of shape, or a change of "
            "support.".format(", ".join(tensioned))
        )
    else:
        lines.append(
            "Every case stays wholly in compression. The surface remains "
            "funicular across this range of loading."
        )
    unbalanced = [
        outcome["name"]
        for outcome in outcomes
        if outcome["ok"]
        and outcome["summary"]["actions"]["residual_magnitude"] > tolerance
    ]
    if unbalanced:
        lines.append(
            "Global equilibrium residual exceeds {} for: {}.".format(
                tolerance,
                ", ".join(unbalanced),
            )
        )
    return "\n".join(lines)


__all__ = [
    "SweepError",
    "deep_merge",
    "format_sweep",
    "load_cases",
    "run_cases",
]
