"""Run an unmodified upstream COMPAS example.

The examples in ``upstream/`` load their data by paths relative to their own
repository, so they have to be run from that repository's root with it on
``sys.path``. Every wrapper in ``demo/compas_examples/`` is a two-line file
that calls into here, which keeps the upstream files untouched and still
gives one clickable, playable script per example.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from _bootstrap import project_root


def run_upstream(package: str, relative: str) -> int:
    """Run one upstream example from its own repository root."""

    root = project_root(Path(__file__))
    repository = root / "upstream" / package
    script = repository / relative

    if not script.is_file():
        print("")
        print("Missing upstream example: {}".format(script))
        print("")
        print("Fetch the COMPAS example repositories with:")
        print("    bash scripts/fetch_compas_examples.sh")
        return 1

    print("=" * 66)
    print("  COMPAS official example: {} / {}".format(package, script.stem))
    print("=" * 66)
    print("")
    print("Unmodified upstream file:")
    print("  upstream/{}/{}".format(package, relative))
    print("")
    print("Close the viewer window to finish.")
    print("")

    previous = Path.cwd()
    os.chdir(repository)
    sys.path.insert(0, str(repository))
    sys.argv = [str(script)]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    except FileNotFoundError as error:
        print("")
        print("This example needs a data file that is not in the repository:")
        print("  {}".format(error))
        return 1
    finally:
        os.chdir(previous)
    return 0


__all__ = ["run_upstream"]
