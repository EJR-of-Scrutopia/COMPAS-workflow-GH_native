"""The one file a staged run writes, and the only schema anything reads.

Every adapter produces this, so a number never depends on which door it came in
through.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTER_COLUMNS = (
    "stage",
    "kind",
    "cable",
    "rest_length",
    "reel_command",
    "length",
    "tension",
    "force_density",
    "worst_deviation",
    "acceptance",
    "acceptance_source",
    "within_acceptance",
    "load_applied",
    "units",
)


def write_register(rows, path):
    """Write the register as JSON, every row carrying every column."""

    ordered = []
    for row in rows:
        missing = set(REGISTER_COLUMNS) - set(row)
        if missing:
            raise ValueError(
                "Register row is missing: " + ", ".join(sorted(missing))
            )
        ordered.append({column: row[column] for column in REGISTER_COLUMNS})
    Path(path).write_text(
        json.dumps(ordered, indent=1, ensure_ascii=False), encoding="utf-8"
    )
