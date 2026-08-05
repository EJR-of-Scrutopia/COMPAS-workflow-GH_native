"""The main bench must never import compas_fea2.

It mirrors Rhino 8 and pins numpy 2.0.2, scipy 1.13.1 and compas 2.15.1.
compas_fea2 is pinned to a mid-2025 commit in its own environment. If these
ever meet, one of the two pins loses.

Mentioning the name is not the hazard: worker.py reports FEA capability by
reading distribution metadata (importlib.metadata.version) without ever
importing compas_fea2, which cannot disturb the pins because no code from
the package runs. Only an import statement can pull compas_fea2's own
dependency versions into this environment, so only imports are forbidden
here; the guard matches import statements, not the bare string.
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "ananke_equilibrium"

IMPORT_PATTERN = re.compile(
    r"^\s*(import\s+compas_fea2|from\s+compas_fea2)", re.MULTILINE
)


def test_ananke_equilibrium_never_imports_compas_fea2():
    offenders = []
    for module in SOURCE.rglob("*.py"):
        if IMPORT_PATTERN.search(module.read_text(encoding="utf-8")):
            offenders.append(str(module.relative_to(SOURCE)))
    assert offenders == [], (
        "these modules import compas_fea2 and must not: {}".format(offenders)
    )


def test_ananke_equilibrium_never_imports_ananke_fea():
    """The mirror guard: the main bench must not creep the other way either."""

    pattern = re.compile(r"^\s*(import\s+ananke_fea|from\s+ananke_fea)", re.MULTILINE)
    offenders = [
        str(module.relative_to(SOURCE))
        for module in SOURCE.rglob("*.py")
        if pattern.search(module.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_rhino_mirroring_pins_have_not_moved():
    """The hazard, guarded directly rather than by proxy.

    An earlier version asserted compas_fea2 was absent from this
    environment. That was the wrong invariant: the repository's own "fea"
    extra installs compas_fea2 0.2.1 here for the worker's capability
    reporting, and measurement showed it leaves every pin intact. What must
    never move are the pins themselves, whoever's install moved them.
    """

    from importlib.metadata import version

    pins = {"numpy": "2.0.2", "scipy": "1.13.1", "compas": "2.15.1"}
    moved = {
        name: version(name)
        for name, expected in pins.items()
        if version(name) != expected
    }
    assert moved == {}, (
        "the Rhino 8 mirroring pins have moved: {}".format(moved)
    )
