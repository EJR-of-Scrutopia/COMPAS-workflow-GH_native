"""Keep the API tests out of environments without fastapi.

Only the app tests need fastapi; geometry, tessellation, subdivision and
bundle tests are stdlib-only and always collect. Same per-suite
prerequisite pattern as tests/fea/conftest.py and tests/legacy/conftest.py.
"""

collect_ignore_glob = []

try:
    import fastapi  # noqa: F401
except ImportError:
    collect_ignore_glob = ["test_app*.py"]
