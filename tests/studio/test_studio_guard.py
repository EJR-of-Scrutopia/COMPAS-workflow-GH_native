"""The studio must stay a thin client of the solver environments.

bench/studio runs in the main venv, which mirrors Rhino 8. Importing
compas_fea2 there would fight the fea pin; importing ananke_fea would pull
compat shims into an environment they were never written for; importing
numpy, scipy or compas would couple the server to the pinned stack for no
reason: everything the studio does is JSON and subprocess. The solver work
is shelled to .venv-fea, so only import statements are forbidden, matching
tests/test_no_fea_cross_import.py.
"""

from __future__ import annotations

import re
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"

FORBIDDEN = re.compile(
    r"^\s*(import\s+(compas_fea2|ananke_fea|compas|numpy|scipy)\b"
    r"|from\s+(compas_fea2|ananke_fea|compas|numpy|scipy)\b)",
    re.MULTILINE,
)


def test_studio_never_imports_the_solver_stacks():
    offenders = []
    for module in STUDIO.rglob("*.py"):
        if FORBIDDEN.search(module.read_text(encoding="utf-8")):
            offenders.append(str(module.relative_to(STUDIO)))
    assert offenders == [], (
        "these studio modules import a solver stack and must not: {}".format(offenders)
    )


def test_the_studio_package_exists():
    assert (STUDIO / "__init__.py").is_file()
