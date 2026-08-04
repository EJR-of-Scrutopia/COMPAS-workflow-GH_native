"""Pull numbers out of a solved step, in a shape the main bench can read.

Everything here reads from the step's field results, which only exist
because the step requested field outputs before solving and because the
solve went through ananke_fea.compat.analyse rather than
analyse_and_extract. Without the first there is no results table at all;
without the second every row appears twice and every sum is doubled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def displacement_summary(step) -> Dict[str, Any]:
    """Peak displacement and where it is."""

    results = list(step.displacement_field.results)
    if not results:
        raise ValueError(
            "no displacement results. Was DisplacementFieldResults requested "
            "with step.add_output before solving?"
        )
    peak = max(results, key=lambda result: result.magnitude)
    return {
        "count": len(results),
        "peak_magnitude": float(peak.magnitude),
        "peak_vector": [float(component) for component in peak.vector],
        "peak_node_xyz": [float(value) for value in peak.node.xyz],
    }


def reaction_summary(step) -> Dict[str, Any]:
    """Summed reactions, which should cancel the factored applied load."""

    results = list(step.reaction_field.results)
    if not results:
        raise ValueError(
            "no reaction results. Was ReactionFieldResults requested with "
            "step.add_output before solving?"
        )
    total = [0.0, 0.0, 0.0]
    for result in results:
        for axis in range(3):
            total[axis] += float(result.vector[axis])
    return {
        "count": len(results),
        "total": total,
        "magnitude": sum(component**2 for component in total) ** 0.5,
    }


def write(path, payload: Mapping[str, Any]) -> Path:
    """Write a result JSON, creating the directory if needed."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target
