"""Re-launch a demo under the interpreter it needs.

VS Code's play button runs a file with whatever interpreter happens to be
selected, which may be a system Python with none of the COMPAS packages
installed. Rather than making every run depend on the interpreter picker
being right, each demo calls ``ensure_venv`` before importing anything, and
hands itself over to the correct interpreter if it is not already running
under it.

Coupled rigid-block analysis needs a second interpreter entirely, so the CRA
demos call ``ensure_cra_venv`` instead.

This module must import nothing outside the standard library, because it
runs before the environment is known to be correct.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

GUARD = "ANANKE_DEMO_BOOTSTRAPPED"

# Coupled rigid-block analysis cannot share the main interpreter: compas_cra
# pins pyomo 6.4.2, which needs Python 3.10 or lower and numpy below 2, while
# this project pins numpy 2.0.2 to mirror Rhino 8. It gets its own
# environment, built by scripts/setup_cra_env.sh.
CRA_VENV = ".venv-cra"

# Every compas_cra solver calls SolverFactory("ipopt"), so the binaries must
# be on PATH before a solve starts. Microsoft Store Python virtualises
# %LOCALAPPDATA%, so idaes installs them under Packages rather than where
# pyomo reports them. Forward slashes throughout: Windows accepts them, and
# they survive any amount of shell quoting.
IPOPT_CANDIDATES = (
    "%LOCALAPPDATA%/Packages"
    "/PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0"
    "/LocalCache/Local/idaes/bin",
    "%LOCALAPPDATA%/idaes/bin",
    "%USERPROFILE%/.idaes/bin",
)


def project_root(start: Path) -> Path:
    """Walk up from a script until a directory containing .venv is found."""

    here = Path(start).resolve().parent
    for candidate in [here] + list(here.parents):
        if (candidate / ".venv").is_dir():
            return candidate
    # Nothing found: fall back to the repository layout, demo/ under the root.
    return here.parent if here.name == "demo" else here


def venv_python(start: Path, name: str = ".venv") -> Path:
    """Return an interpreter from one of the project's environments."""

    root = project_root(start)
    if os.name == "nt":
        return root / name / "Scripts" / "python.exe"
    return root / name / "bin" / "python"


def ipopt_directory() -> Optional[Path]:
    """Return the directory holding the IPOPT binaries, or None."""

    for candidate in IPOPT_CANDIDATES:
        directory = Path(os.path.expandvars(candidate))
        if (directory / "ipopt.exe").is_file() or (directory / "ipopt").is_file():
            return directory
    return None


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def ensure_venv(
    script: str,
    name: str = ".venv",
    extra_path: Optional[Path] = None,
) -> None:
    """Hand this script to the named interpreter, if it is not already it.

    Returns normally when the current interpreter is correct. Otherwise it
    runs the script under the right one and exits, so nothing after the call
    runs in the wrong environment.
    """

    if os.environ.get(GUARD):
        # Already handed over once. A second attempt would loop.
        if extra_path is not None:
            os.environ["PATH"] = "{}{}{}".format(
                extra_path, os.pathsep, os.environ.get("PATH", "")
            )
        return

    target = venv_python(Path(script), name)
    current = Path(sys.executable)
    if _same(current, target):
        if extra_path is not None:
            os.environ["PATH"] = "{}{}{}".format(
                extra_path, os.pathsep, os.environ.get("PATH", "")
            )
        return

    if not target.is_file():
        print("")
        print("The {} interpreter is missing:".format(name))
        print("    {}".format(target))
        print("")
        if name == CRA_VENV:
            print("Build it with:")
            print("    bash scripts/setup_cra_env.sh")
        else:
            print("Create it, then install the project:")
            print("    py -3.12 -m venv .venv")
            print('    .venv/Scripts/python.exe -m pip install -e ".[equilibrium,masonry,fab,plot,viz,dev]"')
        raise SystemExit(1)

    print("Switching from {}".format(current))
    print("            to {}".format(target))
    print("")
    sys.stdout.flush()

    environment = dict(os.environ)
    environment[GUARD] = "1"
    if extra_path is not None:
        environment["PATH"] = "{}{}{}".format(
            extra_path, os.pathsep, environment.get("PATH", "")
        )

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


def ensure_cra_venv(script: str) -> None:
    """Hand this script to the CRA interpreter, with IPOPT on PATH."""

    directory = ipopt_directory()
    if directory is None:
        print("")
        print("IPOPT was not found, and compas_cra cannot solve without it.")
        print("")
        print("Install it with:")
        print("    .venv/Scripts/python.exe -m pip install idaes-pse")
        print("    .venv/Scripts/idaes.exe get-extensions")
        raise SystemExit(1)
    ensure_venv(script, name=CRA_VENV, extra_path=directory)


__all__ = [
    "CRA_VENV",
    "GUARD",
    "IPOPT_CANDIDATES",
    "ensure_cra_venv",
    "ensure_venv",
    "ipopt_directory",
    "project_root",
    "venv_python",
]
