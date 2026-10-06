"""Run a trade study from a JSON brief and write the result beside it.

    .venv/Scripts/python.exe scripts/trade_study.py brief.json out.json

The brief holds lines, fixed, rest_lengths, ea, load_pattern, grid, acceptance
and mechanism (the fixed Mechanism fields). Units are newtons and millimetres.
The limit_factor in each row is a multiple of load_pattern, not newtons.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from tree_forest_compas.fd import register_fd_network
from tree_forest_compas.trade_study import fronts
from tree_forest_compas.trade_study import sweep


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    brief = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    problem = register_fd_network(brief["lines"])
    results = sweep(
        problem,
        fixed=brief["fixed"],
        rest_lengths=brief["rest_lengths"],
        ea=brief["ea"],
        load_pattern=np.asarray(brief["load_pattern"], dtype=float),
        grid=brief["grid"],
        acceptance=brief["acceptance"],
        steps=brief.get("steps", 40),
        max_factor=brief.get("max_factor", 20.0),
        **brief["mechanism"],
    )
    Path(argv[2]).write_text(
        json.dumps({"results": results, "fronts": fronts(results)}, indent=1),
        encoding="utf-8",
    )
    skipped = sum(1 for row in results if row["skipped"])
    print(
        "{} combinations ({} skipped as invalid), written to {}".format(
            len(results), skipped, argv[2]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
