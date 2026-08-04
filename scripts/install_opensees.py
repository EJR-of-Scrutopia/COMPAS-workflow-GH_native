"""Wire a downloaded OpenSees into the FEA environment.

The OpenSees Windows binary cannot be fetched from a script: the download
page at

    https://opensees.berkeley.edu/OpenSees/user/download.php

drives it through a JavaScript handler, and every direct URL under
opensees.berkeley.edu/OpenSees/files/ returns 404. GitHub's releases for
OpenSees/OpenSees carry source only, with no binary assets. So the download
is a manual step, and this script is everything after it.

Download ``OpenSees3.8.0-x64.exe`` from that page. It is a self-extracting
archive that produces a folder containing ``bin/OpenSees.exe``. Then run:

    .venv/Scripts/python.exe scripts/install_opensees.py <path>

where <path> is either OpenSees.exe itself or any folder above it. The
script finds the executable, writes the .env file that compas_fea2_opensees
reads at import, and checks that the backend registers.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEA_VENV = ROOT / ".venv-fea"
ENV_FILE = ROOT / ".env"


def find_executable(start: Path):
    """Return the OpenSees executable at or below the given path."""

    start = Path(start).expanduser().resolve()
    if start.is_file():
        if start.name.lower() == "opensees.exe":
            return start
        # A self-extracting archive was passed rather than the executable.
        return None
    if not start.is_dir():
        return None
    direct = start / "bin" / "OpenSees.exe"
    if direct.is_file():
        return direct
    for candidate in start.rglob("OpenSees.exe"):
        return candidate
    return None


def write_env(executable: Path) -> None:
    """Write the .env file compas_fea2_opensees reads via load_dotenv."""

    # Forward slashes: the backend interpolates this into a shell command,
    # and backslashes in a .env value are an escaping hazard.
    line = "EXE={}\n".format(str(executable).replace("\\", "/"))
    ENV_FILE.write_text(line, encoding="utf-8")
    print("wrote {}".format(ENV_FILE))
    print("  {}".format(line.strip()))


def check_backend() -> int:
    """Import the backend in the FEA environment and report what happens."""

    python = FEA_VENV / "Scripts" / "python.exe"
    if not python.is_file():
        print("")
        print("The FEA environment is missing. Build it with:")
        print("    bash scripts/setup_fea_env.sh")
        return 1
    probe = (
        "import compas_fea2_opensees as b;"
        "from compas_fea2 import BACKENDS;"
        "print('EXE =', b.EXE);"
        "print('registered backends:', list(dict(BACKENDS).keys()))"
    )
    completed = subprocess.run(
        [str(python), "-c", probe],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    print("")
    print("--- backend check ---")
    print(output.strip()[-1200:])
    return completed.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    executable = find_executable(Path(sys.argv[1]))
    if executable is None:
        print("")
        print("No OpenSees.exe found at or below: {}".format(sys.argv[1]))
        print("")
        print("If you passed the downloaded self-extracting archive, run it")
        print("first: it expands to a folder containing bin/OpenSees.exe.")
        print("Then pass that folder to this script.")
        return 1

    print("found {}".format(executable))
    write_env(executable)
    return check_backend()


if __name__ == "__main__":
    raise SystemExit(main())
