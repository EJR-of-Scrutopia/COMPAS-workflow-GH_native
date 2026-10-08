"""Shared helpers for the demo scripts.

Each demo script prints its analysis to the terminal and then opens a
compas_viewer window. Closing the window ends the script.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from typing import Optional

# parents[1] is the bench directory; studies and demo data live beside us.
REPO = Path(__file__).resolve().parents[1]
STUDIES = REPO / "studies"
DEMO = REPO / "demo"
PAVILION = STUDIES / "pavilion"

# Colours reused across the demos so the same thing reads the same way twice.
COMPRESSION = (0.12, 0.31, 0.47)
TENSION = (0.64, 0.23, 0.12)
SURFACE = (0.55, 0.64, 0.71)
BLOCK = (0.80, 0.74, 0.62)
SUPPORT = (0.05, 0.05, 0.05)
CASE_COLOURS = [
    (0.12, 0.31, 0.47),
    (0.20, 0.50, 0.42),
    (0.64, 0.51, 0.12),
    (0.64, 0.23, 0.12),
    (0.40, 0.28, 0.55),
    (0.15, 0.45, 0.60),
    (0.50, 0.35, 0.25),
]


def banner(title: str) -> None:
    """Print a section heading that is readable on a projector."""

    line = "=" * max(60, len(title) + 4)
    print("")
    print(line)
    print("  " + title)
    print(line)


def step(text: str) -> None:
    print("")
    print("-> " + text)


def add(scene: Any, item: Any, name: str, **kwargs: Any) -> Any:
    """Add an object to a viewer scene, tolerating optional style kwargs.

    compas_viewer accepts different style keywords for different object
    types, and a rejected keyword should not end a live demonstration.
    """

    try:
        return scene.add(item, name=name, **kwargs)
    except Exception:
        try:
            return scene.add(item, name=name)
        except Exception as error:
            print("   (could not add {}: {})".format(name, error))
            return None


def open_viewer(title: str = "Ananke Equilibrium") -> Any:
    """Create a viewer, or explain clearly why it cannot open."""

    try:
        from compas_viewer import Viewer
    except ImportError:
        print("")
        print("compas_viewer is not installed. Install it with:")
        print('    python -m pip install -e ".[viz]"')
        sys.exit(1)
    try:
        return Viewer(title=title)
    except TypeError:
        return Viewer()


def show(viewer: Any) -> None:
    """Show the viewer window and report if the display fails.

    Set ANANKE_DEMO_NO_SHOW=1 to run a demo end to end without opening a
    window, which is how these scripts are tested.
    """

    import os

    if os.environ.get("ANANKE_DEMO_NO_SHOW"):
        print("")
        print("(ANANKE_DEMO_NO_SHOW set: skipping the viewer window)")
        return
    print("")
    print("Opening the viewer. Close the window to continue.")
    try:
        viewer.show()
    except Exception as error:
        print("The viewer could not open a window: {}".format(error))
        print("The terminal output above is the same analysis.")


def require(path: Path, hint: str) -> Path:
    """Fail with an actionable message rather than a traceback."""

    if not path.exists():
        print("")
        print("Missing: {}".format(path))
        print(hint)
        sys.exit(1)
    return path


def latest_result() -> Optional[Path]:
    """Return the pavilion result, if it has been solved."""

    path = PAVILION / "results" / "result.json"
    return path if path.exists() else None
