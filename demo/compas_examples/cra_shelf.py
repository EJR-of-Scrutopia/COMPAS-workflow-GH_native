"""compas_cra example: 07_shelf.

A corbelled shelf assembly.

This is coupled rigid-block analysis: it solves for stability under friction,
which a thrust network cannot express. It runs in the separate .venv-cra
environment on Python 3.10, because compas_cra pins pyomo 6.4.2, and it needs
IPOPT on PATH. The wrapper arranges both.

The example itself is unmodified upstream code at
upstream/compas_cra/docs/examples/07_shelf.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _bootstrap import ensure_cra_venv  # noqa: E402

ensure_cra_venv(__file__)

from _cra_runner import run_cra  # noqa: E402

raise SystemExit(run_cra("docs/examples/07_shelf.py"))
