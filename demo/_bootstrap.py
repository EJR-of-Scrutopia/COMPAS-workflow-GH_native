"""Re-launch a demo under the project's own interpreter.

VS Code's play button runs the file with whatever interpreter happens to be
selected, which may be a system Python with none of the COMPAS packages
installed. Rather than making every run depend on the interpreter picker
being right, each demo calls ``ensure_venv`` before importing anything, and
the script hands itself over to the correct interpreter if it is not already
running under it.

This module must import nothing outside the standard library, because it
runs before the environment is known to be correct.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

GUARD = "ANANKE_DEMO_BOOTSTRAPPED"


def project_root(start: Path) -> Path:
    """Walk up from a script until a directory containing .venv is found."""

    here = Path(start).resolve().parent
    for candidate in [here] + list(here.parents):
        if (candidate / ".venv").is_dir():
            return candidate
    # Nothing found: fall back to the repository layout, demo/ under the root.
    return here.parent if here.name == "demo" else here


def venv_python(start: Path) -> Path:
    """Return the project's interpreter, wherever the script sits."""

    root = project_root(start)
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def ensure_venv(script: str) -> None:
    """Hand this script to the project interpreter, if it is not already it.

    Returns normally when the current interpreter is correct. Otherwise it
    replaces the process, so nothing after the call runs in the old one.
    """

    if os.environ.get(GUARD):
        # Already handed over once. A second attempt would loop.
        return

    target = venv_python(Path(script))
    current = Path(sys.executable)
    if _same(current, target):
        return

    if not target.is_file():
        print("")
        print("The project interpreter is missing:")
        print("    {}".format(target))
        print("")
        print("Create it, then install the project:")
        print("    py -3.12 -m venv .venv")
        print('    .venv\\Scripts\\python.exe -m pip install -e ".[equilibrium,masonry,fab,plot,viz,dev]"')
        raise SystemExit(1)

    print("Switching from {}".format(current))
    print("            to {}".format(target))
    print("")
    sys.stdout.flush()

    environment = dict(os.environ)
    environment[GUARD] = "1"
    arguments = [str(target), str(Path(script).resolve())] + sys.argv[1:]

    # Not os.execv: on Windows it does not replace the process, it spawns a
    # detached one and lets the parent exit 0 immediately, so the real output
    # goes nowhere and the run silently appears to succeed. A subprocess keeps
    # stdout and stderr attached to this terminal.
    import subprocess

    try:
        completed = subprocess.run(arguments, env=environment)
    except OSError as error:
        print("Could not switch interpreter: {}".format(error))
        raise SystemExit(1)
    raise SystemExit(completed.returncode)


__all__ = ["GUARD", "ensure_venv", "project_root", "venv_python"]
