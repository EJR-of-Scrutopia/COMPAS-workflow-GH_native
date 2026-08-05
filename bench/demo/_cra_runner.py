"""Run an unmodified compas_cra example.

Two things need fixing before one of these will run, and neither is a change
to the example itself.

**Sample data.** The installed wheel computes ``compas_cra.SAMPLE`` as a path
relative to a source checkout, so on a wheel install it points at a directory
that does not exist. The repository in ``upstream/`` does carry the samples,
so ``SAMPLE`` is redirected there.

**The viewer.** ``compas_cra.viewers`` is written against ``compas_view2``,
which imports ``compas.robots``. COMPAS 2 removed that module, moving it out
to the standalone ``compas_robots`` package, so ``compas_view2`` cannot run
against the ``compas 2.15.1`` this project pins. The upstream code swallows
the failed import in a ``try`` block and then raises ``NameError: name 'app'
is not defined`` at the point of use.

Rather than crash after a successful solve, ``cra_view`` is replaced with a
summary that reports what the solve actually found. The analysis is
untouched; only the drawing is different.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from _bootstrap import project_root


def _redirect_sample_data(repository: Path) -> bool:
    """Point compas_cra.SAMPLE at the repository's own sample data."""

    samples = repository / "src" / "compas_cra" / "data" / "samples"
    if not samples.is_dir():
        return False
    try:
        import compas_cra
    except ImportError:
        return False
    if Path(getattr(compas_cra, "SAMPLE", "")).is_dir():
        return True
    compas_cra.SAMPLE = str(samples)
    return True


def _summarise(assembly) -> None:
    """Report what a CRA solve found, in place of the dead viewer."""

    print("")
    print("-" * 66)
    print("  Solved assembly")
    print("-" * 66)
    try:
        blocks = assembly.number_of_nodes()
    except Exception:
        blocks = "unknown"
    try:
        interfaces = assembly.number_of_edges()
    except Exception:
        interfaces = "unknown"
    print("  blocks              {}".format(blocks))
    print("  contact interfaces  {}".format(interfaces))

    supports = 0
    try:
        for node in assembly.nodes():
            if assembly.node_attribute(node, "is_support"):
                supports += 1
        print("  supports            {}".format(supports))
    except Exception:
        pass

    # Interface forces live on the edges as per-contact force records.
    magnitudes = []
    try:
        for edge in assembly.edges():
            interface = assembly.edge_attribute(edge, "interface")
            for candidate in (interface, ) if interface else ():
                forces = getattr(candidate, "forces", None) or []
                for record in forces:
                    value = record.get("c_np", None) if isinstance(record, dict) else None
                    if value is not None:
                        magnitudes.append(float(value))
    except Exception:
        pass
    if magnitudes:
        print("  contact normal forces")
        print("    count             {}".format(len(magnitudes)))
        print("    range             {:.4f} to {:.4f}".format(
            min(magnitudes), max(magnitudes)))

    print("")
    print("  The solver printed its own status above: 'result: optimal' means")
    print("  a valid equilibrium state was found for this assembly under the")
    print("  friction coefficient given. That is a stability statement, and it")
    print("  is what a thrust network cannot make.")
    print("")
    print("  The upstream drawing step is skipped: compas_cra ships a viewer")
    print("  built on compas_view2, which imports compas.robots, a module")
    print("  COMPAS 2 removed. The analysis above is unaffected.")


def _install_viewer_shim() -> None:
    """Replace compas_cra's dead viewer with the summary above."""

    try:
        import compas_cra.viewers as viewers
    except ImportError:
        return

    def shim(assembly, *args, **kwargs):
        _summarise(assembly)

    for name in ("cra_view", "cra_view_ex"):
        if hasattr(viewers, name):
            setattr(viewers, name, shim)
    # Examples import the name directly, so patch the defining module too.
    try:
        import compas_cra.viewers.cra_view as module

        for name in ("cra_view", "cra_view_ex"):
            if hasattr(module, name):
                setattr(module, name, shim)
    except ImportError:
        pass


def run_cra(relative: str) -> int:
    """Run one upstream compas_cra example from its repository root."""

    root = project_root(Path(__file__))
    repository = root / "upstream" / "compas_cra"
    script = repository / relative

    if not script.is_file():
        print("")
        print("Missing upstream example: {}".format(script))
        print("Fetch it with: bash scripts/fetch_compas_examples.sh")
        return 1

    print("=" * 66)
    print("  compas_cra example: {}".format(script.stem))
    print("=" * 66)
    print("")
    print("Unmodified upstream file:")
    print("  upstream/compas_cra/{}".format(relative))
    print("")
    print("Coupled rigid-block analysis: blocks, contacts, and friction.")
    print("This one solves for stability, which the thrust network does not.")
    print("")

    _install_viewer_shim()

    if not _redirect_sample_data(repository):
        print("Note: sample data could not be located; a data-driven example")
        print("may fail. Parametric examples are unaffected.")
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
        print("This example needs a data file that is not present:")
        print("  {}".format(error))
        return 1
    finally:
        os.chdir(previous)
    return 0


__all__ = ["run_cra"]
