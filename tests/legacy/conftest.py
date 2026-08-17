"""Keep the legacy solver tests out of environments without COMPAS.

This suite exercises the compatibility solver namespace, whose modules
import compas and compas_ags at module level. CI's dependency-light job
installs no COMPAS stack, and without this gate collection itself crashes
there. The equilibrium-integration job installs the full stack and runs
these for real, so the coverage is not lost, only placed where it can run.
Same pattern as tests/fea/conftest.py.
"""

collect_ignore_glob = []

try:
    import compas  # noqa: F401
except ImportError:
    collect_ignore_glob = ["*.py"]
