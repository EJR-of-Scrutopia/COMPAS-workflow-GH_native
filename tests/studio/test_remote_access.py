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
    monkeypatch.setattr(studio_app, "PROPS_DIR", props)

    model = client.get("/api/props/boulder.glb")
    assert model.status_code == 200
    assert model.headers["cache-control"] == studio_app.HEAVY_ASSET_CACHE

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


def test_the_waker_stays_on_loopback_and_stays_silent():
    """Loopback-only is the security model: Tailscale Serve is the only
    road in. And the handler must override the stdlib's request logging,
    which writes to a stderr that does not exist under pythonw -- one such
    write ends the process (serve.py's ensure_stdio lesson)."""

    body = inspect.getsource(waker.main)
    assert '("127.0.0.1", WAKER_PORT)' in body
    assert waker.WakerHandler.log_message is not (
        BaseHTTPRequestHandler.log_message)
