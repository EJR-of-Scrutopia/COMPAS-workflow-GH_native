"""Keep the API tests out of environments without fastapi.

Only the app tests need fastapi; geometry, tessellation, subdivision and
bundle tests are stdlib-only and always collect. Same per-suite
prerequisite pattern as tests/fea/conftest.py and tests/legacy/conftest.py.
"""

import sys
from pathlib import Path

import pytest

collect_ignore_glob = []

try:
    import fastapi  # noqa: F401
except ImportError:
    collect_ignore_glob = ["test_app*.py"]

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clear_cut_memo():
    """Every studio test starts and ends with an empty in-process cut memo.

    bundle._cut_memo is a process global keyed only on (export_name,
    pattern, size), so a cut memoised by one test leaks into the next one
    that happens to reuse the same key against its own tmp_path upload
    dir. Same sys.path dance test_bundle.py's own studio() helper does,
    tolerating ImportError so a suite run without the studio package on
    the path (or without its dependencies) still collects.
    """

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import bundle
    except ImportError:
        yield
        return
    bundle.clear_cut_memo()
    yield
    bundle.clear_cut_memo()
