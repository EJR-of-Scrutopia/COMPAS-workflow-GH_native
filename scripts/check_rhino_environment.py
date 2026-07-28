"""Report the Python and COMPAS environment used by Rhino 8.

Run from a terminal while Rhino is open:

    "C:\Program Files\Rhino 8\System\RhinoCode.exe" script \
        scripts/check_rhino_environment.py
"""

from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path


PACKAGES = (
    "compas",
    "compas_fd",
    "compas_tna",
    "compas_ags",
    "compas_model",
    "compas_ifc",
    "compas_fea2",
)


def package_version(name: str) -> str:
    try:
        module = importlib.import_module(name)
    except Exception as error:
        return "MISSING ({})".format(error)
    return str(getattr(module, "__version__", "installed; version unavailable"))


lines = [
    "Python: {}".format(sys.version.replace("\n", " ")),
    "Implementation: {}".format(platform.python_implementation()),
    "Executable: {}".format(sys.executable),
]
for package in PACKAGES:
    lines.append("{}: {}".format(package, package_version(package)))

report = "\n".join(lines)
print(report)
Path(__file__).with_name("rhino_environment.txt").write_text(
    report + "\n",
    encoding="utf-8",
)
