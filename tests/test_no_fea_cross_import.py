"""The main bench must never import compas_fea2.

It mirrors Rhino 8 and pins numpy 2.0.2, scipy 1.13.1 and compas 2.15.1.
compas_fea2 is pinned to a mid-2025 commit in its own environment. If these
ever meet, one of the two pins loses.
"""

from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "ananke_equilibrium"


def test_ananke_equilibrium_never_imports_compas_fea2():
    offenders = []
    for module in SOURCE.rglob("*.py"):
        text = module.read_text(encoding="utf-8")
        if "compas_fea2" in text:
            offenders.append(str(module.relative_to(SOURCE)))
    assert offenders == [], (
        "these modules reference compas_fea2 and must not: {}".format(offenders)
    )


def test_ananke_fea_is_not_importable_from_the_main_environment():
    """A guard against someone adding it to the main install by accident."""

    import importlib.util

    spec = importlib.util.find_spec("compas_fea2")
    assert spec is None, (
        "compas_fea2 is installed in the main environment, which will move "
        "the numpy and compas pins that mirror Rhino 8"
    )
