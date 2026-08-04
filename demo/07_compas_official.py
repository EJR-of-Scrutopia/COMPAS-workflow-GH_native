"""Demo 7: run COMPAS's own example files, unmodified.

The demos numbered 1 to 6 are ours. These are the COMPAS project's, taken
from the upstream repositories in `upstream/`, and they are richer than
anything hand-rolled: real case-study geometry rather than parametric
templates, and `DEMViewer`, which is a proper application with a COMPAS DEM
menu (Show Blocks, Show Contacts, Show Interactions), a sidebar object tree
with visibility checkboxes, per-object and camera settings, four render
modes and five view presets.

Nothing here is edited. This script only picks an example, points the
interpreter and the working directory at it, and runs it, because the
examples load data by a path relative to their own repository.

Run with no argument for the menu:

    python demo/07_compas_official.py

Run one by name or number:

    python demo/07_compas_official.py dem_vault_cross
    python demo/07_compas_official.py 3
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hand this script to the project interpreter before importing anything
# that needs it, so the play button works whatever VS Code has selected.
from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)

import runpy  # noqa: E402

from _common import banner, step  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
UPSTREAM = REPO / "upstream"

# The example most worth showing first: 184 real voussoirs from an OBJ, not a
# parametric template, with 488 contacts and supports found by graph degree.
DEFAULT = "dem_vault_cross"


def discover():
    """Find the upstream example scripts, newest-looking first."""

    found = []
    for package in sorted(p for p in UPSTREAM.iterdir() if p.is_dir()):
        for folder in ("docs/examples", "scripts"):
            directory = package / folder
            if not directory.is_dir():
                continue
            for script in sorted(directory.glob("*.py")):
                if script.name.startswith("_"):
                    continue
                found.append((package.name, script))
    return found


def show_menu(examples):
    banner("COMPAS official examples")
    print("These are unmodified files from the COMPAS repositories.")
    print("")
    current = None
    for index, (package, script) in enumerate(examples, start=1):
        if package != current:
            print("")
            print("  {}".format(package))
            current = package
        print("    {:>2}  {}".format(index, script.stem))
    print("")
    print("Every one of these that runs has a clickable file of its own in:")
    print("    demo/compas_examples/")
    print("")
    print("Open one and press play. Or run one from here by number or name:")
    print("    python demo/07_compas_official.py {}".format(DEFAULT))
    print("")
    print("Known not to run in this environment:")
    print("    robot, model, test_ui, scene, nurbscurve   compas_viewer API or plugin")
    print("    dem_new_features, dem_new_features_RBE     pyomo 6.4.2 vs numpy 2")
    print("    extract_robot_package_from_ros             needs a live ROS connection")


def resolve(examples, wanted):
    """Match a selection by number or by name."""

    if wanted.isdigit():
        index = int(wanted)
        if 1 <= index <= len(examples):
            return examples[index - 1]
        return None
    for package, script in examples:
        if script.stem == wanted or script.name == wanted:
            return package, script
    return None


def main() -> int:
    if not UPSTREAM.is_dir():
        print("")
        print("The upstream examples are not present. Fetch them with:")
        print("    bash scripts/fetch_compas_examples.sh")
        return 1

    examples = discover()
    if not examples:
        print("No example scripts found under {}".format(UPSTREAM))
        return 1

    wanted = sys.argv[1] if len(sys.argv) > 1 else None
    if wanted is None:
        show_menu(examples)
        return 0

    match = resolve(examples, wanted)
    if match is None:
        print("No example called {!r}.".format(wanted))
        print("")
        show_menu(examples)
        return 1

    package, script = match
    # The examples resolve their data relative to their own repository, so
    # run from the package root and put it first on sys.path.
    root = UPSTREAM / package
    banner("{} / {}".format(package, script.stem))
    step("Running {}".format(script.relative_to(UPSTREAM)))
    print("   unmodified upstream file, run from {}".format(root.name))
    print("")

    import os

    previous = Path.cwd()
    os.chdir(root)
    sys.path.insert(0, str(root))
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    except FileNotFoundError as error:
        print("")
        print("The example could not find a data file: {}".format(error))
        print("Some upstream examples depend on data not kept in the repo.")
        return 1
    finally:
        os.chdir(previous)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
