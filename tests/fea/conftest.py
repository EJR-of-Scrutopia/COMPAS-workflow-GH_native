"""Keep the FEA tests out of any environment that cannot run them.

The main .venv mirrors Rhino 8 and deliberately has no compas_fea2. Its
pytest run collects everything under tests/, so without this these modules
would fail at import rather than being skipped.
"""

collect_ignore_glob = []

try:
    import compas_fea2  # noqa: F401
except ImportError:
    collect_ignore_glob = ["*.py"]
