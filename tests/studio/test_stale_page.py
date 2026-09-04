"""The page tells you when it is stale, and only when it is.

Three times this studio has been reported as "nothing has changed on the
interface" when the change was on disk. The last time the diagnosis was
written on the screen and neither of us read it: the build stamp said
"__BUILD__", the literal placeholder, which is only possible if the page was
NOT served by the route that fills it in.

The check that says so has to live inline in the page, because the fault it
exists for is a studio.js the browser is serving from its own cache, and a
check inside that file would be the cached version of the check.

And it must not be written in a form the placeholder substitution can reach.
The first version compared against a literal "__BUILD__" and the server's
replace-every-occurrence rewrote that literal to the stamp, so the test
became "is the stamp different from the stamp": never true, and the warning
fired on every load instead of never. That is what these tests are for.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "bench" / "studio"
STATIC = STUDIO / "static"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import app as studio_app  # noqa: E402

PLACEHOLDER = "__" + "BUILD" + "__"


def inline_script(page: str) -> str:
    """The self-check script, found by its content rather than by position.

    Slicing from the first "<script>" to the first "</script>" finds the
    import map's closing tag, which comes earlier, and returns nothing.
    """

    at = page.index("stale-server")
    start = page.rindex("<script>", 0, at)
    return page[start:page.index("</script>", start)]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(studio_app.create_app())


def test_the_check_is_inline_in_the_page_not_in_a_module():
    """The fault it exists for is a cached studio.js. A check inside that
    file would be the cached version of the check."""

    page = (STATIC / "index.html").read_text(encoding="utf-8")
    # The notice's id is set in script, not written as an attribute: it does
    # not exist in the markup until something has gone wrong.
    assert '"stale-server"' in inline_script(page)
    assert "createElement" in page, "the notice is built by the inline script"
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "stale-server" not in js, (
        "a module cannot report that it is itself out of date"
    )


def test_the_comparison_cannot_be_rewritten_by_the_substitution():
    """The server fills the placeholder in with a replace-every-occurrence.
    A literal in the comparison is rewritten to the stamp, and the test
    becomes 'is the stamp different from the stamp', which is never true."""

    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = inline_script(page)
    assert PLACEHOLDER not in script, (
        "the placeholder must not appear whole inside the check, or the "
        "substitution rewrites the very thing being compared against"
    )
    assert 'var placeholder = "__" + "BUILD" + "__";' in script
    # And exactly one place in the whole page carries it, the span.
    assert page.count(PLACEHOLDER) == 1


def test_a_page_served_by_the_route_has_no_warning_and_a_real_stamp(client):
    page = client.get("/").text
    assert PLACEHOLDER not in page, "the placeholder must be filled in"
    stamp = re.search(r'id="build-stamp"[^>]*>([0-9a-f]{6,})<', page)
    assert stamp, "the stamp must be a version"
    # The check will compare the span against an assembled placeholder and
    # find them different, so it returns without shouting.
    assert stamp.group(1) != PLACEHOLDER


def test_the_raw_file_still_carries_the_placeholder():
    """Which is what an old server serves, and what the check is looking
    for. If this ever stops being true the check can never fire."""

    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '>{}</span>'.format(PLACEHOLDER) in page


def test_a_module_level_throw_is_reported_rather_than_swallowed():
    """A studio.js that throws halfway through wiring leaves half a panel
    built and the rest silently never built, which looks merely
    disappointing. The handler is registered before the module loads."""

    page = (STATIC / "index.html").read_text(encoding="utf-8")
    inline_at = page.index("stale-server")
    module_at = page.index('src="/static/studio.js"')
    assert inline_at < module_at, (
        "the error handler must be registered before the module it is there "
        "to catch"
    )
    script = inline_script(page)
    assert 'window.addEventListener("error"' in script
    assert "stopped setting itself up" in script
