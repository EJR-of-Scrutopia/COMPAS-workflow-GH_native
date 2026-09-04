"""Two problems that were reported as one: "nothing has changed".

The first is caching. A Cache-Control header is a REQUEST not to cache, and
it has now failed three times on this studio: the page's HTML and JavaScript
were current while its stylesheet and one of its modules were from before
the change. A version in the URL is not a request. If the bytes change the
address changes, and no cache can return an old entry for a new address
whatever it believes about freshness.

The second is that there was no way to tell. A build stamp printed in the
panel turns "I do not see a difference" into a fact: a stamp that does not
move after an edit says the page is cached, which is a different problem
from a change that did not land.
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


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(studio_app.create_app())


def test_every_asset_the_page_loads_carries_a_version(client):
    page = client.get("/").text
    stamp = re.search(r'studio\.css\?v=([0-9a-f]{6,})', page)
    assert stamp, "the stylesheet must be versioned"
    version = stamp.group(1)
    assert 'studio.js?v={}'.format(version) in page
    # And the modules studio.js imports, which are each their own cache
    # entry. A stale panel.js is the exact fault that was reported: native
    # sliders where scrub rows should be.
    for module in ("panel.js", "pbr.js", "fields.js"):
        assert '"/static/{0}": "/static/{0}?v={1}"'.format(module, version) in page, (
            module + " must be remapped to its versioned address"
        )


def test_the_version_moves_when_a_file_does_and_not_otherwise(tmp_path, monkeypatch):
    """A real tree, really edited. The whole point of the stamp is that it
    tracks the files, so a fixture that fakes the files proves nothing."""

    tree = tmp_path / "static"
    tree.mkdir()
    (tree / "studio.css").write_text("a{}", encoding="utf-8")
    (tree / "studio.js").write_text("//", encoding="utf-8")
    (tree / "logo.png").write_bytes(b"not a script")
    monkeypatch.setattr(studio_app, "STATIC_DIR", tree)

    first = studio_app.static_version()
    assert first == studio_app.static_version(), (
        "an unchanged tree must give an unchanged stamp, or the stamp says "
        "nothing about whether anything changed"
    )

    # An edit moves it, even one that leaves the file the same length: the
    # mark carries the modification time as well as the size.
    (tree / "studio.css").write_text("a{color:red}", encoding="utf-8")
    edited = studio_app.static_version()
    assert edited != first

    # A file the page does not load does not move it. The stamp answers
    # "is my page stale", and an image is not part of that question.
    (tree / "logo.png").write_bytes(b"a different picture entirely")
    assert studio_app.static_version() == edited


def test_the_page_prints_which_build_it_is(client):
    page = client.get("/").text
    assert 'id="build-stamp"' in page
    assert "__BUILD__" not in page, "the placeholder must be filled in"
    stamp = re.search(r'id="build-stamp"[^>]*>([0-9a-f]{6,})<', page)
    assert stamp, "the stamp must be a version, not a word"
    assert 'studio.css?v=' + stamp.group(1) in page, (
        "the stamp the panel shows must be the one the assets carry, or it "
        "reassures without informing"
    )


def test_the_theme_is_nine_variables_and_a_toggle():
    """Param asked for black or white with a toggle. This is what the token
    block was for: every colour in the panel comes from one of nine
    variables, so a second theme is nine values and not a second stylesheet.
    """

    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert ':root[data-theme="light"] {' in css
    light = css[css.index(':root[data-theme="light"] {'):]
    light = light[:light.index("}")]
    for token in ("--ground", "--panel", "--raised", "--well", "--line",
                  "--ink", "--ink-2", "--ink-3", "--accent", "--panel-veil"):
        assert token in light, token
    # Light is a ramp of its own, not the dark one inverted: a light surface
    # gets DARKER as it rises where a dark one gets lighter.
    assert "--ground:   #f8f8f8;" in light and "--panel:    #ffffff;" in light

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function applyTheme(theme)" in js
    assert 'localStorage.setItem("bench-studio-theme"' in js
    # The button names what it will DO, which is the one choice that stops a
    # toggle being ambiguous in a screenshot.
    assert 'button.textContent = light ? "Dark" : "Light";' in js


def test_the_panel_is_translucent_and_its_controls_are_not():
    """A blurred panel over a moving viewport makes every grey in it depend
    on what is behind it, so only the panel's own ground is see-through."""

    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "--panel-veil: rgba(27, 27, 27, 0.72);" in css
    panel = css[css.index("#panel { position: fixed"):]
    panel = panel[:panel.index("}")]
    assert "background: var(--panel-veil);" in panel
    assert "backdrop-filter: blur(" in panel
    # The raised surface, which every control sits on, stays opaque.
    assert "--raised:   #222222;" in css
    assert "rgba" not in css[css.index("--raised:"):css.index("--raised:") + 40]


def test_the_overlays_are_not_themed():
    """The HUD and the event log sit on the VIEWPORT, whose ground comes
    from the environment the vault is lit by and stays dark when the panel
    goes light. Darkening them with the panel made them unreadable, which
    the first screenshot of the light theme showed."""

    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    themed = re.findall(r':root\[data-theme="light"\][^{]*\{', css)
    joined = " ".join(themed)
    assert "#hud" not in joined
    assert "#event-log" not in joined
    # The two that DO have grounds of their own still take the theme, via
    # the one overlay token: each paints var(--scrim), and the light block
    # overrides --scrim once instead of restating each overlay by hand.
    for selector in ("#legend {", "#cut-overlay {"):
        block = css.split(selector, 1)[1]
        assert "var(--scrim)" in block[:block.index("}")]
    light_block = css.split(':root[data-theme="light"] {', 1)[1]
    assert "--scrim:" in light_block[:light_block.index("}")]
