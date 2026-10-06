"""The one file a staged run writes, and the only schema anything reads.

Every adapter produces this, so a number never depends on which door it came in
through.

Column notes. `reel_command` is the change in rest length from the stage before,
in millimetres: negative means reeling in, which shortens the cable and raises
the net (the sign of `prescribed.reel_commands`). `load_magnitude_sum` is the sum
of the force magnitudes at the nodes, in newtons: the total weight arriving for
a gravity case. It is not a resultant (opposing loads add, they do not cancel).
`worst_deviation` and `within_acceptance` are null when the stage was solved
without a target, because no check was made. They are also always null for the
stage kind "raise" (`staged_solve.NO_TARGET_KINDS`): a raise stage is still
stepping towards the target by design, so it carries no conformance verdict, and
a reader must not take null there as a pass or a fail. Only the other kinds, for
example "tile", carry a verdict when a target was given.
"""

from __future__ import annotations

import json
from pathlib import Path

class RegisterError(RuntimeError):
    """Raised when a register cannot be written as a valid file."""


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
    "load_magnitude_sum",
    "units",
)


def write_register(rows, path):
    """Write the register as JSON, every row carrying every column."""

    rows = list(rows)
    if not rows:
        raise RegisterError("A register with no rows is not a register.")
    ordered = []
    for row in rows:
        missing = set(REGISTER_COLUMNS) - set(row)
        if missing:
            raise RegisterError(
                "Register row is missing: " + ", ".join(sorted(missing))
            )
        ordered.append({column: row[column] for column in REGISTER_COLUMNS})
    try:
        text = json.dumps(ordered, indent=1, ensure_ascii=False, allow_nan=False)
    except ValueError as error:
        raise RegisterError(
            "A register value is NaN or infinite, which is not valid JSON: "
            "{}".format(error)
        )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
