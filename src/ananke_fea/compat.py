"""Make the pinned compas_fea2 usable, and record exactly what was wrong.

The OpenSees backend was last pushed 2025-06-17 and imports BeamSection,
which the core removed on 2025-07-30, so the core is pinned to 664ec20. That
commit is internally inconsistent in one place: model/nodes.py sets
self._loads but leaves the public `loads` property commented out, while
problem/steps/step.py:117 calls node.loads when a combination is assigned.
The result is that applying any load a combination recognises raises
AttributeError. One property closes it.

This module is the only place that reaches into upstream internals, and
every patch is announced by name so a future version bump can drop it.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

BACKEND_NAME = "compas_fea2_opensees"

_applied: List[str] = []


def require_backend() -> str:
    """Register the OpenSees backend and return its name.

    Importing the backend is not enough. Without set_backend the BACKENDS
    mapping stays empty and every model builds as an abstract base class.
    """

    import compas_fea2

    if compas_fea2.BACKEND is None:
        compas_fea2.set_backend(BACKEND_NAME)
    return BACKEND_NAME


def apply_patches() -> List[str]:
    """Shim the upstream inconsistencies. Returns the names newly applied."""

    require_backend()
    from compas_fea2.model import Node

    newly: List[str] = []
    if not hasattr(Node, "loads"):
        Node.loads = property(lambda self: self._loads)
        newly.append("Node.loads")

    _applied.extend(newly)
    return newly


def analyse(problem, path) -> None:
    """Solve and extract, avoiding the double-extraction bug.

    problem.analyse_and_extract() runs extraction twice and inserts every
    result row twice, so sums come out doubled while max() looks correct.
    Splitting the call gives one row per node.

    The directory must not already exist: compas_fea2 calls input() on an
    existing path, which hangs a non-interactive run.
    """

    directory = Path(path)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(
            "analysis directory is not empty, which makes compas_fea2 prompt "
            "on stdin and hang: {}".format(directory)
        )
    directory.mkdir(parents=True, exist_ok=True)

    problem.analyse(path=str(directory), verbose=False)
    problem.extract_results()
