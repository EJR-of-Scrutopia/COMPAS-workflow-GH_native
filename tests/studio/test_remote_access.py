"""The studio over the tailnet: cache tiers and the waker.

The studio began as a loopback tool, where "cache nothing" was free and
every asset was a memory copy away. Over a phone link the same choices
cost megabytes per reload, so the flat no-store splits into three tiers:
the app's own files stay uncacheable (a stale studio.css has produced two
bug reports already), the frozen vendor modules may be kept but must be
re-asked-about, and the heavy assets -- prop models, sky derivations,
material maps -- are paid for once and refreshed in the background.

The waker is the one always-on piece of the remote door: a loopback-only
stdlib server whose only power is to run the same launcher the desktop
shortcut runs. Its logic lives in small pure functions exactly so it can
be tested without binding a port.
"""

from __future__ import annotations

import inspect
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "bench" / "studio"
LAUNCHER = REPO / "launcher"
for place in (STUDIO, LAUNCHER):
    if str(place) not in sys.path:
        sys.path.insert(0, str(place))

import app as studio_app  # noqa: E402
import waker  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(studio_app.create_app())


def test_heavy_assets_are_cached_and_their_indexes_are_not(
        client, tmp_path, monkeypatch):
    """The prefixes are shared: /api/props/ serves both a folder row (JSON,
    mutable state) and gigabyte-class models (frozen bytes). The content
    type is what tells them apart, so a JSON answer slipping into the
    week-long tier would freeze the library lists on every remote device."""

    props = tmp_path / "props"
    props.mkdir()
    (props / "boulder.glb").write_bytes(b"glTF fake, weight is the point")
    (props / "boulder.glb.thumb.png").write_bytes(b"png fake")
    monkeypatch.setattr(studio_app, "PROPS_DIR", props)

    model = client.get("/api/props/boulder.glb")
    assert model.status_code == 200
    assert model.headers["cache-control"] == studio_app.HEAVY_ASSET_CACHE
    assert model.headers["content-type"] == "model/gltf-binary"

    # The drawer's snapshots share the route and the cache tier, but they
    # are PICTURES: calling a PNG a glTF worked only by browser sniffing.
    thumb = client.get("/api/props/boulder.glb.thumb.png")
    assert thumb.headers["cache-control"] == studio_app.HEAVY_ASSET_CACHE
    assert thumb.headers["content-type"] == "image/png"

    row = client.get("/api/props/folder")
    assert row.status_code == 200
    assert row.headers.get("cache-control") != studio_app.HEAVY_ASSET_CACHE

    # The LIST at the prefixless path must stay fresh too: a cached
    # /api/hdri would hide every newly added sky from a remote device.
    listing = client.get("/api/hdri")
    assert listing.headers.get("cache-control") != studio_app.HEAVY_ASSET_CACHE


def test_the_cache_patience_is_hours_not_forever():
    """Props ARE replaced in place -- an ingest rewrites the same filename
    -- so immutable-style caching would serve a re-ingested tree stale for
    a year. An hour of patience plus background revalidation is the
    deliberate trade, and this pin is what makes changing it a decision."""

    assert studio_app.HEAVY_ASSET_CACHE == (
        "public, max-age=3600, stale-while-revalidate=604800")
    assert studio_app.HEAVY_ASSET_PREFIXES == (
        "/api/props/", "/api/hdri/", "/api/materials/",
        "/api/ground-materials/")


def test_vendor_keeps_but_reasks_while_the_app_stays_uncacheable(client):
    """no-cache is not no-store: the vendor megabytes may be KEPT and cost
    a 304 to confirm, while the daily-edited app files may not be kept at
    all -- the stale-stylesheet fault stays closed."""

    vendor = client.get("/static/vendor/three.module.js")
    assert vendor.status_code == 200
    assert vendor.headers["cache-control"] == "no-cache"

    app_file = client.get("/static/studio.js")
    assert app_file.headers["cache-control"] == "no-store, max-age=0"
    assert client.get("/").headers["cache-control"] == "no-store, max-age=0"


def test_the_waker_wakes_the_studio_and_nothing_else():
    """Both spellings of the mount ("/start" whole, "/" stripped) must
    wake, because Tailscale Serve decides which one arrives. Every other
    path is a 404: the waker fronts nothing and proxies nothing."""

    assert waker.plan("/start", up=False) == "wake"
    assert waker.plan("/", up=False) == "wake"
    assert waker.plan("/start?from=laptop", up=False) == "wake"
    assert waker.plan("/start", up=True) == "studio"
    assert waker.plan("/waker-health", up=False) == "health"
    assert waker.plan("/api/health", up=False) == "missing"
    assert waker.plan("/etc/passwd", up=False) == "missing"


def test_a_burst_of_knocks_is_one_launch():
    """Each spawn RESTARTS the studio (the launcher takes the port), so a
    laptop double-click plus an impatient reload must not become three
    restarts in a row."""

    assert waker.should_spawn(now=30.0, last=0.0, cooldown=30.0) is True
    assert waker.should_spawn(now=29.9, last=0.0, cooldown=30.0) is False


def test_the_start_page_waits_for_the_studio_not_the_proxy():
    """When the studio is down the tailnet proxy still answers /api/health
    with a 502, so the page must demand an OK reply that says "studio"
    before moving, or it would bounce to a bad-gateway screen."""

    assert "reply.ok" in waker.START_PAGE
    assert "health.studio" in waker.START_PAGE
    assert 'location.replace("/")' in waker.START_PAGE


def test_the_waker_spawn_is_quiet_and_browserless():
    """-NoBrowser because the asking device has its own browser open on
    this very page; CREATE_NO_WINDOW because the waker lives at logon and
    a flashing console per knock would be the old launcher fault again."""

    body = inspect.getsource(waker.spawn_studio)
    # The QUOTED tokens, not the bare words: the docstring names the same
    # switches while explaining them, and a pin the docstring can satisfy
    # is no pin at all (measured: removing the argument passed the test).
    assert '"-NoBrowser"' in body
    assert '"-Quiet"' in body
    assert "CREATE_NO_WINDOW" in body
    assert '"launch.ps1"' in body, "one launch path, the shortcut's own"


def _js_function(source, header):
    """One function's text, from its header to the next top-level one."""

    start = source.index(header)
    end = source.index("\nfunction ", start + 1)
    for stop in ("\nasync function ", "\nconst ", "\nlet "):
        try:
            end = min(end, source.index(stop, start + 1))
        except ValueError:
            pass
    return source[start:end]


STUDIO_JS = (REPO / "bench" / "studio" / "static" / "studio.js")


def test_the_prop_library_loads_no_models_at_boot():
    """Eager loading pulled 241 MB of models through every boot. A desktop
    shrugged; the iPad died of it -- an iOS tab gets a fraction of a
    desktop's memory, and the studio would not open there at all. The
    manifest and the tiles are the whole boot cost now."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(source, "async function loadPropLibrary()")
    assert "loadPropTemplate" not in body, (
        "boot must not touch model files; ensurePropTemplate owns loading")
    assert "buildPropTiles()" in body
    # Every manifest entry is offered in the select, not only loaded ones.
    assert "propTemplates.has" not in body


def test_a_model_loads_once_and_a_failure_stays_failed():
    """The promise map is the dedup AND the convergence rule: restoreProps
    re-runs when a model lands, so a failed load that cleared its promise
    would be re-asked-for on every landing, forever."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(source, "function ensurePropTemplate(key)")
    assert "propTemplatePromises.has(key)" in body
    assert "return null" in body
    assert "propTemplatePromises.delete" not in body
    assert "beginLoading" in body, "a load the user asked for shows the toast"


def test_tiles_draw_snapshots_not_geometry():
    """A tile's picture is a .thumb.png file (snapped once by
    tools/props/snap_thumbs.py); only a prop with no snapshot falls back to
    loading its model live. The click is what loads geometry, and it waits."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(source, "function buildPropTiles()")
    # The CODE forms, not the words: the comments explain snapshots too,
    # and a pin a comment can satisfy is no pin at all.
    assert 'picture.src = "/api/props/"' in body
    assert 'encodeURIComponent(entry.file + ".thumb.png")' in body
    assert "picture.onerror" in body
    assert "await ensurePropTemplate(entry.key)" in body


def test_restores_summon_their_own_models():
    """A saved layout and a saved scene both name models that are no longer
    resident at boot. Each path must ask for what it needs: the layout by
    re-running itself as models land, the scene by loading them all before
    placing any."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    restore = _js_function(source, "function restoreProps()")
    assert "ensurePropTemplate(entry.type)" in restore
    assert "restoreProps()" in restore.replace("function restoreProps()", "", 1)
    scene_block = source[source.index("adoptLayers(scene_.propLayers)"):]
    scene_block = scene_block[:scene_block.index("applyLayerVisibility()")]
    assert "await Promise.all" in scene_block
    assert "ensurePropTemplate(type)" in scene_block


def test_the_report_survives_a_dying_page():
    """The iPad's crash never reached diagnostics.log: a tab being
    reclaimed for memory drops in-flight fetch bodies. sendBeacon is the
    transport built for dying pages, and the context must never be the
    message's ransom -- an error during module evaluation reaches the
    reporter before `state` exists."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(source, "function reportProblem(message, detail)")
    assert "navigator.sendBeacon" in body
    assert body.index("sendBeacon") < body.index('fetch("/api/diagnostics"'), (
        "the beacon is the first choice, fetch the fallback")
    assert "context: null" in body, "the bare message travels without context"


def test_the_boot_banner_hears_rejections_and_stands_down():
    """An async boot step that dies arrives as a rejection, not an error
    event -- but a stray rejection during ordinary use must not shout
    half-built over a fully built page."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert '"unhandledrejection"' in html
    assert "__studioReady" in html
    source = STUDIO_JS.read_text(encoding="utf-8")
    assert "window.__studioReady = true" in source


def test_big_props_fit_the_preview_frustum():
    """The rig's far plane is 20, sized for the material ball; a cliff
    framed from sixty metres sat beyond it and sixteen of the library's
    previews came out empty squares. The planes follow the framing."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(source, "function renderObjectPreview(object, canvasEl)")
    assert "camera.far = distance * 4 + reach" in body
    assert "updateProjectionMatrix" in body
    assert "camera.far = 20" in body, "and the ball gets its frustum back"


def test_the_page_can_start_what_it_stopped():
    """Param: "if i stop the server we need a ztart server too". The
    studio is gone but the waker is not, and it answers in two places:
    this origin's /start mount (the tailnet page) and its own loopback
    port (the desktop page). Both are knocked -- the knock IS the message,
    neither answer is read -- and the page reloads when its own server
    answers again. The button appears exactly when "stopped" does."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    stop = js[js.index('getElementById("stop-studio").addEventListener'):]
    stop = stop[:stop.index("\n});")]
    assert 'document.getElementById("start-studio").hidden = false;' in stop

    start = js[js.index('getElementById("start-studio").addEventListener'):]
    start = start[:start.index("\n});")]
    assert 'fetch("/start", { cache: "no-store" })' in start
    assert 'fetch("http://127.0.0.1:8611/start", { mode: "no-cors"' in start
    assert "location.reload()" in start
    assert "health.studio" in start, (
        "through the proxy only a real studio answer means up; a 502 or "
        "the waker page must not trigger the reload")

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert 'id="start-studio" hidden' in html


def test_the_footer_sits_on_the_banner_floor():
    """Param: the footer belongs "on the bottom of the banner not on the
    bottom of the menus displayed". The panel is a flex column and the
    mode row's auto top margin swallows the free space when the open
    section is short; sticky still owns the overflowing case."""

    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    panel = css[css.index("#panel { position: fixed"):]
    panel = panel[:panel.index("}")]
    assert "flex-direction: column" in panel
    mode = css[css.index("#mode-row { position: sticky"):]
    mode = mode[:mode.index("}")]
    assert "margin-top: auto;" in mode


def test_fingers_and_narrow_screens_are_provided_for():
    """First device-fit pass for the tailnet's tablets: coarse pointers
    get taller footer buttons and tabs, and below 1000px the drawer
    centres itself in the space LEFT of the panel instead of under it."""

    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    assert "@media (pointer: coarse)" in css
    assert "@media (max-width: 1000px)" in css
    assert "calc((100vw - var(--panel-w)) / 2)" in css


def test_constrained_devices_ask_for_smaller_maps():
    """An iPad asked for five MASTER-tier maps per material change spends
    seconds decoding them, and under GPU memory pressure iOS drops texture
    uploads -- the silver-props face of the same ceiling. Touch is the
    tell (iPadOS masquerades as a Mac; Macs have no touch points), and the
    server's tier system does the rest."""

    pbr = (REPO / "bench" / "studio" / "static" / "pbr.js").read_text(
        encoding="utf-8")
    assert "navigator.maxTouchPoints > 1" in pbr
    assert "VIEWPORT_PX = CONSTRAINED_DEVICE ? 1024 : 0" in pbr


def test_touch_devices_render_at_a_capped_density_and_losses_are_reported():
    """DPR 2 on an iPad is a 3200x2400 canvas -- half of the slowness by
    itself. And when iOS reclaims the graphics context, the report must
    say so with the device's numbers, or every downstream symptom looks
    like a different bug."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "Math.min(window.devicePixelRatio, 1.5)" in js
    assert '"webglcontextlost"' in js
    lost = js[js.index('"webglcontextlost"'):]
    lost = lost[:lost.index("});")]
    assert 'reportProblem("WebGL context lost"' in lost
    report = _js_function(js, "function reportProblem(message, detail)")
    assert "maxTextureSize" in report
    assert "maxTouchPoints" in report


def test_the_waker_stays_on_loopback_and_stays_silent():
    """Loopback-only is the security model: Tailscale Serve is the only
    road in. And the handler must override the stdlib's request logging,
    which writes to a stderr that does not exist under pythonw -- one such
    write ends the process (serve.py's ensure_stdio lesson)."""

    body = inspect.getsource(waker.main)
    assert '("127.0.0.1", WAKER_PORT)' in body
    assert waker.WakerHandler.log_message is not (
        BaseHTTPRequestHandler.log_message)
