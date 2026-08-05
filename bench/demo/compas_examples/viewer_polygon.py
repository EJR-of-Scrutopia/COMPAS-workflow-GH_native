"""COMPAS official example: compas_viewer / polygon.

An official COMPAS example.

This file is a wrapper. The example itself is unmodified upstream code at
upstream/compas_viewer/scripts/polygon.py, run from its own repository root because it loads
data by relative path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _runner import run_upstream  # noqa: E402

raise SystemExit(run_upstream("compas_viewer", "scripts/polygon.py"))
