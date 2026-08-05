"""COMPAS official example: compas_dem / dem_dome.

A masonry dome built from measured block geometry.

This file is a wrapper. The example itself is unmodified upstream code at
upstream/compas_dem/docs/examples/dem_dome.py, run from its own repository root because it loads
data by relative path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

from _runner import run_upstream  # noqa: E402

raise SystemExit(run_upstream("compas_dem", "docs/examples/dem_dome.py"))
