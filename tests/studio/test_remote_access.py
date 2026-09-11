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
    # Of the VARIANT it is about to carry, since a tile is a family now
    # and eight tufts of one grass are one tile: the click still loads
    # exactly one model, and only the one being picked up.
    assert "const variant = pickVariant(entry.key);" in body
    assert "await ensurePropTemplate(variant)" in body


def test_restores_summon_their_own_models():
    """A saved layout and a saved scene both name models that are no longer
    resident at boot. Each path must ask for what it needs: the layout by
    re-running itself as models land, the scene by loading them all before
    placing any."""

    source = STUDIO_JS.read_text(encoding="utf-8")
    restore = _js_function(source, "function restoreProps(given)")
    assert "ensurePropTemplate(entry.type)" in restore
    assert "restoreProps()" in restore.replace("function restoreProps(given)", "", 1)
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


def test_the_banner_folds_on_its_own_handle():
    """Param: "a little tile arrow attached to the mid left side of the
    banner that can be pressed to collapse the banner to the side and then
    pressed again to open". One body class moves the panel, the tab rail,
    the handle and the log together; the choice is remembered per
    browser. The handle is a SIBLING of the panel -- the panel's overflow
    scroll would clip a child hung outside its box."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert 'id="panel-collapse"' in html
    assert html.index("</aside>") < html.index('id="panel-collapse"')

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'classList.toggle("panel-collapsed", collapsed)' in js
    assert 'localStorage.getItem("panel-collapsed")' in js

    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    assert "body.panel-collapsed #panel { transform: translateX(100%); }" in css
    assert "body.panel-collapsed #panel-collapse { right: 0; }" in css
    assert "body.panel-collapsed #tab-rail" in css, (
        "the rail must fold with the panel or its buttons float orphaned")


def test_play_lives_on_the_shelf_and_starts_where_you_stand():
    """Param: "add a play button next to the scene tile... it should start
    exactly where play is started from". The shelf button delegates to the
    one real play control so the logic lives once, both labels are painted
    by one helper, and the orbit base turns about the CAMERA'S OWN target
    -- lookAt(state.centre) on the first played frame re-aimed a panned
    view, which read as a jump and a lens change."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    tabs = html[html.index('id="shelf-tabs"'):]
    tabs = tabs[:tabs.index("</div>")]
    assert 'id="shelf-play"' in tabs, "Play sits beside the drawer tabs"

    js = STUDIO_JS.read_text(encoding="utf-8")
    # Play is in the strip but is NOT a drawer tab: unscoped wiring would
    # bind it to openShelf(undefined).
    assert 'querySelectorAll("#shelf-tabs button")' not in js
    assert js.count('querySelectorAll("#shelf-tabs button[data-shelf]")') == 3
    assert 'document.getElementById("play-button").click()' in js
    # Every label paint goes through the one helper, or the two buttons
    # drift into telling different stories.
    assert 'document.getElementById("play-button").textContent' not in js
    assert js.count("paintPlayButtons(") >= 8

    capture = _js_function(js, "function captureOrbitBase(atT)")
    assert "lookFrom: controls.target.clone()" in capture, (
        "the aim starts where the user was looking")
    apply_block = _js_function(js, "function applyTimeline(t)")
    assert "base.centre || state.centre" in apply_block

    # The trio: play, restart, record, icons in a row (his walk), each
    # delegating to the one real control so no logic is duplicated.
    tabs = html[html.index('id="shelf-tabs"'):]
    tabs = tabs[:tabs.index("</div>")]
    assert 'id="shelf-restart"' in tabs and 'id="shelf-record"' in tabs
    assert 'document.getElementById("restart-button").click()' in js
    assert 'document.getElementById("record-button").click()' in js
    assert r'"❚❚"' in js and r'"▶"' in js, (
        "the shelf play tile is an icon: triangle at rest, bars playing")


def test_the_take_neither_reaims_nor_inherits_the_drags_glide():
    """Param, after the re-aim fix: "it still did it though". The second
    cause: the controls keep gliding after a drag (damping), and the
    render loop's unconditional controls.update() re-applied that inertia
    on top of the pinned orbit every frame. Every capture now settles the
    controls first (one damped-off update applies and clears leftovers),
    and while the turntable owns the camera the controls stand aside."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    settle = _js_function(js, "function settleControls()")
    assert "controls.enableDamping = false;" in settle
    assert "controls.update();" in settle
    assert "controls.enableDamping = damped;" in settle

    for owner in ("function startPlaying(fromTheTop)",
                  "async function recordAnimation()"):
        body = _js_function(js, owner)
        assert "settleControls();" in body
        assert body.index("settleControls();") < body.index(
            "captureOrbitBase("), owner + " must settle before capturing"

    # The bearing is captured FOR the clock the take starts on. Captured
    # at a finished take's end and played from zero, the camera leapt
    # backwards by the previous take's whole rotation (Param: "its
    # decided where the start of the animation is").
    capture = _js_function(js, "function captureOrbitBase(atT)")
    assert 'typeof atT === "number" ? atT : state.timeline.t' in capture
    assert "Math.max(0, reference - openingSeconds())" in capture
    # The final shape of the ruling: the VAULT owns the circle, the AIM
    # starts where the user was looking and glides home -- no jump at
    # Play, no drifting off the vault mid-turn.
    assert ("state.centre ? state.centre.clone() "
            ": controls.target.clone()") in capture
    assert "lookFrom: controls.target.clone()" in capture
    play = _js_function(js, "function startPlaying(fromTheTop)")
    assert "captureOrbitBase(fromT);" in play
    assert "? 0 : state.timeline.t;" in play
    record = _js_function(js, "async function recordAnimation()")
    assert "captureOrbitBase(0);" in record, (
        "a recording runs from frame zero; its bearing must too")

    drag_end = js[js.index('controls.addEventListener("end"'):]
    drag_end = drag_end[:drag_end.index("\n});")]
    assert "settleControls();" in drag_end

    loop = js[js.index("const turntableOwns"):]
    loop = loop[:loop.index("renderView()")]
    assert "state.timeline.playing" in loop
    assert "state.timeline.orbitBase" in loop
    assert "!state.userDragging" in loop
    assert "if (!turntableOwns) controls.update();" in loop


def test_the_ground_wears_one_scale():
    """Param: "instead of scale x and y for the ground lets just make that
    scale and keep it uniform". One dial writes both axes; a texture
    stretched on one axis stops being a picture of its material."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert 'id="ground-scale"' in html
    assert "ground-scale-x" not in html
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "state.ground.scaleX = +e.target.value;" in js
    assert "state.ground.scaleY = +e.target.value;" in js


def test_randomise_deals_every_piece_its_own_hand():
    """Param: "its random for every instance and repetition". The old
    seed-parity term rotated the WHOLE deal 90 degrees at once under
    Match grain, which read as one rotation applied to everything."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "(seed & 1)" not in js
    assert "? (uvQuarterTurn(seedKey) & 1) * 2" in js, (
        "grain matched still flips 0/180 per piece; grain has no arrow "
        "but does have a direction")


def test_a_small_recorded_history_undoes_the_last_thing():
    """Param: "we are now building a small recorded history" -- sky,
    environment, skin, floor, placements, moves, adjustments, deletions,
    stamp plants. One tile, leftmost; each entry puts one thing back; a
    replayed undo must not record itself; another study empties it."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    tabs = html[html.index('id="shelf-tabs"'):]
    tabs = tabs[:tabs.index("</div>")]
    assert 'id="shelf-undo"' in tabs
    assert tabs.index('id="shelf-undo"') < tabs.index('data-shelf="props"'), (
        "the undo tile stands to the LEFT of the other tiles")

    js = STUDIO_JS.read_text(encoding="utf-8")
    push = _js_function(js, "function pushUndo(label, undo, redo)")
    assert "if (undoReplaying) return;" in push
    for wired in ('undoableSelect("hdri-select"',
                  'undoableSelect("environment-mode"',
                  'undoableSelect("render-skin"',
                  'undoableSelect("ground-preset"'):
        assert wired in js, wired
    assert 'pushUndo("placing the " + record.type' in js
    assert 'pushUndo("the move"' in js
    assert 'pushUndo("the adjustment"' in js
    assert 'pushUndo("deleting the " + gone.type' in js
    assert 'pushUndo("placing " + planted.length' in js
    study = js[js.index("async function loadStudy(exportName)"):]
    study = study[:400]
    assert "clearUndoHistory();" in study, (
        "yesterday's undos must not write into a different picture")


def test_touch_devices_get_a_sky_they_can_carry():
    """A 16k backdrop uploads as half a gigabyte of texture. An iPad asked
    to carry it sheds every other texture to fit -- the prefiltered
    lighting first, which is Param's "sun drop out while changing hdris on
    other devices". Touch devices ask the background route for a 4k
    ceiling; each ceiling is its own derived file beside the full one."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert '+ (CONSTRAINED_DEVICE ? "?px=4096" : "")' in js
    source = (REPO / "bench" / "studio" / "app.py").read_text(encoding="utf-8")
    route = source[source.index('@app.get("/api/hdri/{name}/background")'):]
    route = route[:route.index("\n    @app.")]
    assert "def hdri_background(name: str, px: int = 0):" in route
    assert '".bg-{}.png".format(cap)' in route
    assert "min(int(px), hdri_preview.BACKGROUND_WIDTH)" in route, (
        "the ceiling is clamped to the full tier, never above it")
    assert '".bg-full.png"' in route, "no px still means the master"


def test_the_analysis_lenses_are_buttons_one_at_a_time():
    """Param's analysis walk: the checkboxes become buttons; the three
    lenses that PAINT (two heatmaps, force wires) are exclusive; each
    lens's dial sits under its button only while it is on; the stress lens
    gains a threshold; the arrows gain scales and read through the shell;
    the force lens brings the net with it and paints a kN key; overlays is
    an annotation tucked at the bottom; the Data sheet is a contained
    translucent box; the key stands mid-height beside the panel."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    # Three since the pulse left (2026-09-06, his word).
    assert ('const EXCLUSIVE_LAYERS = '
            '["stress", "deflection", "forces"];') in js
    set_layer = _js_function(js, "function setLayer(name, on)")
    assert "state.layers[other] = false;" in set_layer
    # Round two of his walk: wire forces ARE the net's lens, so raising it
    # switches the view to the bare formwork and lowering it -- by its own
    # button or by another lens taking over -- restores what it interrupted.
    assert 'setShowMode("framework");' in set_layer
    assert 'setShowMode(state.showModeBeforeForces || "both");' in set_layer

    build = _js_function(js, "function buildLayerToggles()")
    assert 'className = "layer-btn"' in build
    assert "holder.appendChild(exaggerationRow)" in build, (
        "the exaggeration slider seats under the Deflection button")
    for key in ("loadsScale", "reactionsScale", "forcesScale", "thrustScale"):
        assert key in js
    # The girth dial is a real slider row under the Wire forces button,
    # not just a state key.
    assert 'forces: { key: "forcesScale", label: "Size"' in js
    assert "stressThreshold" not in js

    # Round two removed the stress threshold on his word.
    recolour = _js_function(js, "function recolourSegments()")
    assert "threshold" not in recolour
    assert '"member force, kN (extremes clamped)"' in js, (
        "the key speaks for the wires too, and admits its clamp")

    # Colours you can SEE (his report: "surely i should be seeing the
    # force colours?"): p95 normalisation spreads the body of the
    # distribution across the ramp, and the lens wears an UNLIT material
    # -- data, not scenography, the heatmaps' own exemption.
    magnitude = _js_function(js, "function forceMagnitude()")
    assert "0.95 *" in magnitude
    wire_lens = _js_function(js, "function applyWireForces()")
    assert "forceMaterial" in wire_lens
    assert "toneMapped: false" in wire_lens
    assert "baseMaterial" in wire_lens, "the steel comes back when the lens drops"
    # The black-lattice bug (his screenshot): vertexColors on a geometry
    # with no colour attribute samples BLACK and multiplies every
    # instance colour away. setColorAt alone is the whole mechanism.
    assert "vertexColors" not in wire_lens, (
        "the force material must not ask for a vertex colour attribute "
        "the wire cylinders do not have")
    assert "setColorAt" in wire_lens
    # And the fattening is HIS dial now: girth 0 keeps the net uniform.
    assert "state.analysisSliders.forcesScale" in wire_lens
    assert "girth * Math.abs(force)" in wire_lens

    # The pulse left on his word (2026-09-06: "no more green and flashing
    # etc"); Support thrust holds its slot: the reaction REVERSED,
    # bucketed at 20 and 35 degrees from vertical -- the same line the
    # narrative's abutment recommendation warns at -- all three colour
    # buckets normalised against ONE magnitude so lengths stay comparable.
    assert "applyPulseColours" not in js
    assert "PULSE_MATERIALS" not in js
    vectors = _js_function(js, "function updateVectorLayers()")
    assert "state.layers.thrust" in vectors
    assert "[-vector[0], -vector[1], -vector[2]]" in vectors
    assert "degrees >= 35 ? buckets.kicks" in vectors
    for shade in ("0x3f9e57", "0xc99a2e", "0xc24936"):
        assert shade in vectors, "the thrust buckets wear the verdict colours"
    assert "state.analysisSliders.thrustScale, magnitudeMax" in vectors
    # And the lens explains itself ON the panel (the pulse taught this
    # panel that much; a tooltip was not the answer).
    build2 = _js_function(js, "function buildLayerToggles()")
    assert '"layer-note"' in build2
    assert 'name === "thrust"' in build2

    arrows = _js_function(js, "function arrowField(entries, colour, anchor, lengthScale = 1,")
    assert "depthTest: false" in arrows
    assert "depthTest = false" in arrows
    assert "renderOrder = 25" in arrows


    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert 'id="overlays-tuck"' in html
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    data = css[css.index("#data-panel {"):]
    data = data[:data.index("}")]
    assert "var(--scrim)" in data and "max-height" in data
    # The key's home moved on his walk ("i dont like it sitting to the
    # middle... to the left of the menus and then slides to the right
    # when it gets retracted"): lower third beside the panel, riding the
    # fold like the handle and the log do.
    legend = css[css.index("#legend {"):]
    legend = legend[:legend.index("}")]
    assert "top: 50%" not in legend, "mid-height belongs to the collapse handle"
    assert "bottom:" in legend
    assert "calc(var(--panel-w)" in legend
    assert "transition: right" in legend
    assert "body.panel-collapsed #legend { right: var(--s4); }" in css
    # The overlay text lives IN the panel now, reading under the Data
    # button (his ask: "text that just reads below the data button"), and
    # the Data button wears the sheet's open state.
    hud = css[css.index("#hud {"):]
    hud = hud[:hud.index("}")]
    assert "position: fixed" not in hud, "the HUD is panel text, not a card"
    assert "pre-wrap" in hud
    assert "#data-button.active" in css
    html2 = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    button_at = html2.index('id="data-button"')
    assert html2.index('id="hud"') > button_at
    assert html2.index('id="hud"') < html2.index('id="overlays-tuck"')
    js2 = STUDIO_JS.read_text(encoding="utf-8")
    assert 'classList.toggle(\n    "active", !panel.classList.contains("hidden"))' in js2
    assert 'getElementById("data-button").classList.remove("active")' in js2

    # The formwork grounds itself (his report: "the formwork doesnt
    # project a shadow?"): the flag follows visibility and opacity at
    # every writer, so a solid net casts and a fading one goes quiet --
    # the old ghost-grid shadow stays fixed.
    sync = _js_function(js2, "function syncNetShadow(object)")
    assert "object.visible && object.material.opacity > 0.6" in sync
    scene_time = _js_function(js2, "function applySceneAtTime(t)")
    assert "syncNetShadow(object)" in scene_time
    show_mode = _js_function(js2, "function applyShowMode()")
    assert "syncNetShadow(state.objects.wires)" in show_mode
    assert "syncNetShadow(state.objects.nodes)" in show_mode
    act = _js_function(js2, "function applyFormworkAct(t, strikeU)")
    assert "syncNetShadow(formworkObjects.net)" in act
    assert "syncNetShadow(bars)" in act


def test_the_layers_drawer_edits_props_and_never_shows_a_ghost():
    """Param's three asks on the Layers drawer: "I should be able to
    select delete and move any of the props if i have them selected from
    the layer tab. instead of having to find the edit button and press
    it. we should also put the edit button on the layers tile too. i
    noticed when i deleted a prop via edit, it didnt remove that prop
    from the layers tile."

    So: one edit mode with two faces that cannot disagree, a tile click
    that grants the edit powers rather than requiring a hunt for the
    button, and a drawer that hears about every prop leaving or
    arriving."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")

    # The second face, in the drawer, lighting like the first.
    assert 'id="shelf-prop-edit"' in html
    assert "#shelf-actions #shelf-prop-edit.active" in css

    # One toggle drives both, so they can never disagree about the mode.
    # Anchored on the painting loop's own two lines rather than on the id
    # list alone: _js_function slices to the next top-level declaration,
    # which here runs past the end of setPropEdit into the listener loop
    # below, so a bare id-list assertion passes on the wrong loop.
    assert 'for (const id of ["prop-edit", "shelf-prop-edit", "shelf-edit-tile"]) {\n'\
        "    const button = document.getElementById(id);" in js
    assert 'for (const id of ["prop-edit", "shelf-prop-edit", "shelf-edit-tile"]) {\n'\
        '  document.getElementById(id).addEventListener("click",\n'\
        "    () => setPropEdit(!state.propEdit));" in js
    # And a freshly opened drawer shows the mode the scene is in.
    shelf = _js_function(js, "function renderShelf()")
    assert 'shelfEdit.classList.toggle("active", state.propEdit)' in shelf

    # Picking from a tile grants the powers, quietly -- and as a LOAN
    # worth one placement, not a mode he then has to notice and undo
    # (Param: "dont auto turn on edit if i move a prop around via the
    # select prop in layer and move it, should be a one time placement").
    tiles = _js_function(js, "function renderShelfLayers(grid)")
    assert "const granted = !state.propEdit;" in tiles
    assert "setPropEdit(true, true);" in tiles
    assert "if (granted) propEditOneShot = true;" in tiles
    assert "selectProp(record);" in tiles
    # Spent by the placement that ends the move, and by a delete, since
    # the prop it was loaned for is then gone.
    assert "    if (propEditOneShot) setPropEdit(false);" in js
    # A deliberate press of either button makes the mode his to keep.
    toggle_head = js[js.index("function setPropEdit(on, quietly = false)"):]
    toggle_head = toggle_head[:toggle_head.index("state.propEdit = on;")]
    assert "if (!quietly) propEditOneShot = false;" in toggle_head

    # The ghost tile: every writer of state.props tells the drawer, and
    # the call is pinned CONTIGUOUS with the save above it, so an early
    # return slipped in between cannot leave the text standing while the
    # behaviour goes.
    assert "  saveProps();\n"\
        "  // The drawer is a picture of state.props" in js
    assert "  if (propEditOneShot) setPropEdit(false);\n"\
        "  // A prop arriving on the open layer earns its tile" in js
    # removePropRecord hands one record to removePropRecords, which takes
    # any number in one pass (an undone stroke was 2,000 separate saves).
    remove = _js_function(js, "function removePropRecords(records)")
    assert "refreshLayersShelf();" in remove
    assert "removePropRecords([record]);" in _js_function(js, "function removePropRecord(record)")
    # The undo path too: putting a deleted prop back must give its tile
    # back. Pinned contiguously because OneDrive reverted exactly this
    # line once while the rest of the wave survived, and the suite stayed
    # green because nothing watched it.
    assert "      saveProps();\n"\
        "      // Undoing a delete must give the tile back too" in js
    refresh = _js_function(js, "function refreshLayersShelf()")
    assert 'if (shelfKind === "layers") renderShelf();' in refresh, (
        "the drawer redraws only when it is the thing on screen")
    # Clear empties the scene, so it must empty the drawer too.
    clear = js[js.index('getElementById("props-clear")'):]
    clear = clear[:clear.index("});")]
    assert "refreshLayersShelf();" in clear


def test_edit_is_a_tile_of_its_own_beside_the_drawers():
    """Param: "can you make the edit button a tile also to the right of
    the Scenes tile. Just a button you press it highlights and no pop up.
    just runs the edit mode. i feel it more intuitive."

    So: a third face on the same mode, standing in the tab strip to the
    right of Scenes, opening nothing. It carries no data-shelf, which is
    what keeps openShelf and closeShelf from claiming it -- a tab-shaped
    button that DID carry one would open a drawer named after itself and
    have its light scrubbed off every time another tab was pressed."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")

    tabs = html[html.index('id="shelf-tabs"'):]
    tabs = tabs[:tabs.index("</div>")]
    assert 'id="shelf-edit-tile"' in tabs, "the tile stands in the tab strip"
    assert tabs.index('data-shelf="scenes"') < tabs.index('id="shelf-edit-tile"'), (
        "and to the RIGHT of Scenes, where he asked for it")
    assert tabs.index('id="shelf-edit-tile"') < tabs.index('id="shelf-play"'), (
        "before the take controls, so it reads with the drawers not the take")

    # No drawer. The whole no-pop-up promise rests on this one absence:
    # the tab wiring is scoped to [data-shelf], so a tile without one is
    # invisible to openShelf, to closeShelf, and to the click loop.
    tile = tabs[tabs.index('id="shelf-edit-tile"'):]
    tile = tile[:tile.index(">")]
    assert "data-shelf" not in tile, (
        "a data-shelf here would make the mode toggle open a drawer")

    # It lights by the same rule the other tiles light by, and by the one
    # toggle that paints the other two Edit faces.
    assert "#shelf-tabs button.active" in css
    assert 'for (const id of ["prop-edit", "shelf-prop-edit", "shelf-edit-tile"]) {\n'\
        "    const button = document.getElementById(id);" in js
    assert 'for (const id of ["prop-edit", "shelf-prop-edit", "shelf-edit-tile"]) {\n'\
        '  document.getElementById(id).addEventListener("click",\n'\
        "    () => setPropEdit(!state.propEdit));" in js


def test_the_skin_is_weighed_in_the_analysis():
    """Param's major fix: "the material applied to skin needs to be the
    material density that is calculated during the stress test. that is
    paired with the skin thickness. so if i am picking a copper say, we
    need to use that material density in the calculations and it needs to
    say that."

    The skin stops being render-only for weight. Its density travels to
    the solver, earns its own cache slot, is recorded in provenance, and
    the narrative says which density it used and why."""

    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import staging

    # One resolver, bounded, falling back rather than poisoning a solve.
    assert staging.resolve_density("concrete") == 2400.0
    assert staging.resolve_density("concrete", 8940) == 8940.0
    assert staging.resolve_density("concrete", 0.5) == 2400.0, "below the floor"
    assert staging.resolve_density("concrete", 1e9) == 2400.0, "above the roof"
    assert staging.resolve_density("concrete", "copper") == 2400.0, "not a number"

    # A density override earns its OWN cache slot, or switching skins is
    # served the previous weight's answers -- and the default keeps the
    # old filename, so nothing already on disk rebuilds for nothing.
    import bundle as bundle_module
    plain = bundle_module.bundle_path("s", "concrete", "p", 0.4, 0.1).name
    heavy = bundle_module.bundle_path("s", "concrete", "p", 0.4, 0.1, 8940).name
    assert plain == "bundle-concrete-p-s400-t100.json"
    assert heavy == "bundle-concrete-p-s400-t100-d8940.json"
    assert bundle_module.staging_path("s", "c", "p", 0.4, 0.1, 8940).name.endswith(
        "-d8940.json")

    # The whole chain carries it, so no leg can quietly weigh it otherwise.
    app_source = (REPO / "bench" / "studio" / "app.py").read_text(encoding="utf-8")
    assert "source: str = Query(None), density: float = Query(None)," in app_source
    assert "thickness, source, density)" in app_source
    assert "source=cut_source, density=density," in app_source
    staging_source = (REPO / "bench" / "studio" / "staging.py").read_text(
        encoding="utf-8")
    assert "density = resolve_density(material, density)" in staging_source
    assert "weight_per_area = thickness * density * GRAVITY" in staging_source
    assert "DENSITIES[material]" not in staging_source.split(
        "def resolve_density")[1].split("def formwork_curve")[1], (
        "past the resolver nothing reads the raw table again")

    # Recorded, so the reader can be told rather than left to assume.
    bundle_source = (REPO / "bench" / "studio" / "bundle.py").read_text(
        encoding="utf-8")
    assert '"density": staging.resolve_density(material, density),' in bundle_source
    assert '"density_from_skin": density is not None,' in bundle_source

    # The client sends it only when the skin actually differs, so a plain
    # concrete study keeps its cache entry.
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const weighAs = skinDensity();" in js
    assert "Math.abs(weighAs - structuralDensity()) > 1" in js
    # The append itself, not just the decision to make one: without this a
    # deleted line left the condition standing and sent nothing.
    assert 'url += "&density=" + weighAs;' in js
    assert "density: params.density," in js, "the staged run is weighed too"

    # And the narrative says which density it used, and whose it was.
    narrative = (REPO / "bench" / "studio" / "static"
                 / "data_analysis.js").read_text(encoding="utf-8")
    assert "input.densityFromSkin = !!bundle.provenance.density_from_skin;" in narrative
    assert "the SKIN's own density rather than the structural" in narrative
    # And the self-weight ESTIMATE weighs with the same density it just
    # reported, or a copper shell is announced at 8940 and then weighed as
    # concrete two sentences later.
    assert "? area * thickness * input.density * 9.81 / 1e3" in narrative
    assert "area * thickness * DENSITIES[bundle.material]" not in narrative


def test_the_weight_note_names_the_material_and_shows_on_load():
    """Param: "is there a density info you can add to the skin banner
    menu. just showing how much density and weight is added and what
    material. Nothing too detailed."

    The note existed but said only the number, and only after an
    appearance control was touched -- so a freshly loaded study showed an
    empty row at exactly the moment the question is asked."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "function weighedAsLabel()" in js
    label = _js_function(js, "function weighedAsLabel()")
    assert "entry.label" in label, "a library skin answers with its own name"
    note = _js_function(js, "function updateWeightNote()")
    assert "weighedAsLabel() + \": \"" in note, "the name leads"
    assert "kg/m3 x " in note and "kN/m2" in note
    # Written on every study load, not only when a control moves. Pinned
    # CONTIGUOUS with the call above it, so an early return slipped in
    # between cannot leave the text standing while the row goes blank.
    assert ("  updateHud();\n"
            "  // The weight line was written only when an appearance") in js
    scene = _js_function(js, "function buildScene(bundle, preserve)")
    assert "updateWeightNote();" in scene


def test_ctrl_z_undoes_and_ctrl_shift_z_redoes():
    """Param: "Can we also get ctrl + z to also run an undo instead of
    just the button", and later "can we also add in more commands to
    this, like redo. full screen". Cmd+Z too, and never while text has
    focus, where the gesture belongs to the text rather than the scene.

    The window is measured from the KEYDOWN handler rather than from the
    tile's listener: redo and full screen were wired in between the two
    on 2026-09-09, and a fixed span from the tile stopped reaching the
    keyboard at all."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    start = js.index('if (event.key !== "z" && event.key !== "Z") return;')
    block = js[start:start + 1400]
    assert "event.ctrlKey || event.metaKey" in block.replace(
        "!event.ctrlKey && !event.metaKey", "event.ctrlKey || event.metaKey")
    assert 'if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;' in block
    assert "undoLast();" in block
    assert "event.preventDefault();" in block
    # Shift no longer falls out of the handler saying nothing: it redoes.
    assert "if (event.shiftKey) {" in block
    assert "redoLast();" in block, "Ctrl+Shift+Z is the redo gesture"


def test_a_slider_reading_can_be_typed_into():
    """Param: "where the text is on the slider say the 10mm in this
    screenshot. i would like to be able to click on it and type in my own
    value." The reading becomes a click target that edits in place."""

    panel = (REPO / "bench" / "studio" / "static" / "panel.js").read_text(
        encoding="utf-8")
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    assert "makeValueTypable(input, value);" in panel
    # The unit factor is DERIVED from what is on screen, so no table of
    # thirty sliders has to be kept in step with their labels.
    assert "(Number.isFinite(shown) && raw !== 0 ? shown / raw : 1);" in panel
    assert "typed / (scale || 1)" in panel
    # Children are hidden and restored, never replaced: handlers write
    # into spans in there by id.
    assert "node.style.display = \"none\";" in panel
    assert "node.restoreText = node.nodeValue;" in panel
    # Both events, because expensive handlers listen on change only.
    assert 'input.dispatchEvent(new Event("input", { bubbles: true }));' in panel
    assert 'input.dispatchEvent(new Event("change", { bubbles: true }));' in panel
    # Enter commits, Escape abandons, and the studio's own keys stay out.
    assert 'if (event.key === "Enter")' in panel
    assert 'else if (event.key === "Escape")' in panel
    assert "event.stopPropagation();" in panel
    # The reading has to take back the pointer the row gives away AND sit
    # above the range input, which is stretched over the whole row at
    # z-index 2. pointer-events alone shipped a control that looked
    # finished and did nothing: the input was simply on top of it.
    assert ".scrub .scrub-value.typable { pointer-events: auto;" in css
    typable = css[css.index(".scrub .scrub-value.typable {"):]
    typable = typable[:typable.index("}")]
    assert "position: relative" in typable and "z-index: 3" in typable


def test_the_voussoirs_can_be_inked_with_an_outline():
    """Param: "a outline slider. put it in the scene menu banner. it will
    just add a dark line around the vault voussoirs as an outline. the
    slider goes from a 0 line to thicker line."

    Drawn as geometry, not as lines: WebGL ignores linewidth on every
    desktop driver, so a LineSegments outline is one pixel wide for ever
    and a slider that cannot thicken is not the feature. Each casting
    carries a ribbon round its own top boundary, and the width is a
    UNIFORM, so dragging the slider moves one number rather than
    rebuilding 1500 pieces of geometry."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")

    # In the SKIN section. It sat in Scene until 2026-09-09, when he moved
    # it: "can you also move the outline slider to actually go into the
    # skin menu". Right, too: it draws on the voussoirs, so it belongs
    # beside the other controls that change how they look rather than
    # beside the sky and the floor.
    skin = html[html.index('<details id="study-section"'):]
    skin = skin[:skin.index("</details>")]
    assert 'id="outline-width"' in skin, "the slider lives in the Skin menu"
    scene = html[html.index('<details id="scene-section">'):]
    scene = scene[:scene.index("</details>")]
    assert 'id="outline-width"' not in scene, (
        "and it is not left behind in Scene as a second copy")
    row = skin[skin.index('id="outline-width"'):]
    row = row[:row.index(">")]
    assert 'min="0"' in row, "zero is a real setting: no line at all"

    # THE BOUNDARY. pieces.py emits "mid" as the cell's used corners --
    # a list, not a loop -- and the first cut of this joined corner to
    # corner in arrival order, which drew long chords wandering across
    # the vault: a fishing net, not voussoirs. The boundary is derived
    # instead, and it was checked against the server's own side walls on
    # a live 1501-piece cut: 24 edges per piece, both ways, no mismatch.
    edges = _js_function(js, "function boundaryEdges(faces, count, underside)")
    assert "if (index < low || index >= high) { ours = false; break; }" in edges, (
        "a face on the other surface, or a side wall, is not this boundary")
    assert "if (edge.uses === 1) edges.push(edge);" in edges, (
        "an edge two faces share is an interior seam, not an outline")

    # BOTH surfaces. Param: "make sure it shows on the underside of the
    # skin too, not just the outside" -- a vault is looked at from
    # underneath more than from above. The two calls differ only in which
    # range of points they read and which way the normal points, and the
    # underside's normal is reversed so its ribbon lifts clear of the face
    # instead of burying itself in the casting.
    assert "boundaryEdges(piece.faces, count, false), ribbon);" in js
    assert "boundaryEdges(piece.faces, count, true), ribbon);" in js
    assert "under.push([-n[0], -n[1], -n[2]]);" in js
    assert "below.push(place(points[i + count]));" in js

    # The width is a uniform on a side vector, so zero has no area and
    # the slider costs nothing to drag.
    ribbon = _js_function(
        js, "function outlineRibbon(loop, normals, centre, edges, into)")
    assert "sides.push(out * sx, out * sy, out * sz);" in ribbon
    assert "transformed += outlineSide * outlineWidth;" in js
    assert "const outlineWidth = { value: 0 };" in js
    # Inward from the edge: never across a joint on to the neighbour.
    assert "sx = -sx; sy = -sy; sz = -sz;" in ribbon

    # A child of its own casting, which is what makes it follow the build:
    # applySceneAtTime moves, scales and hides castings and nothing else.
    assert "line.userData.outline = true;" in js
    assert "mesh.add(line);" in js
    # At zero they are not drawn at all. On a 1500-piece vault, drawing
    # 1500 ribbons with no width in them doubles the draw calls for an
    # invisible result.
    visible = _js_function(js, "function setOutlineVisible(on)")
    assert "if (child.userData.outline) child.visible = on;" in visible
    assert "setOutlineVisible(state.outline > 0);" in js
    # Freed with the shell: the geometry is per piece, the material shared.
    dispose = _js_function(js, "function disposeShell()")
    assert "for (const child of segment.children) {" in dispose
    assert "if (child.geometry) child.geometry.dispose();" in dispose
    # And a scene remembers it.
    assert "outline: state.outline," in js
    assert 'if (typeof scene_.outline === "number") {' in js


def test_a_lamp_is_a_prop_that_carries_a_real_light():
    """Param: "some light props, using our great lumen engine. when we
    turn the sky dark and place an orb light say inside the pavilion, it
    will glow. We should then allow more settings to customise the warm
    and cool colour of the light too."

    A lamp is a prop like any other -- carried, placed, moved by the
    gumball, layered, saved -- that happens to hold a PointLight. Its two
    numbers are the two printed on a real lamp's box: lumens and kelvin.
    Verified live: placed at 1600 lm / 3000 K the light comes out
    ffb16e at 127 cd, and cooling it to 6500 K takes both the light and
    its halo to fffefa."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")

    # The prop itself, and the set that says which types are lamps -- a
    # set rather than a name test, so a second lamp is one builder and
    # one entry.
    assert '"orb-light": propOrbLight,' in js
    assert 'const LAMP_TYPES = new Set(["orb-light", "light-sphere", "light-strip",' in js, (
        "the set gained the three fixtures on 2026-09-09, and KEPT the old "
        "name: a scene saved before then still says orb-light, and a type "
        "nothing recognises is drawn as nothing")
    assert "new THREE.PointLight(0xffffff, 1, 0, 2)" in js, (
        "decay 2 is the inverse square, which is what makes a lamp read "
        "as a lamp rather than as a flood")

    # Kelvin, not two swatches. The coefficients are gamma-encoded bytes,
    # so they must go in through SRGBColorSpace or they come out pale.
    kelvin = _js_function(js, "function kelvinColour(kelvin)")
    assert "99.4708025861 * Math.log(t) - 161.1195681661" in kelvin
    assert "THREE.SRGBColorSpace);" in kelvin

    lit = _js_function(js, "function applyPropLight(record)")
    # Colour and output reach the light through the one writer of it,
    # which every size change also goes through (2026-09-11).
    assert "syncFixtureEmission(record);" in lit
    laid = _js_function(js, "function layFixtureEmitters(object, lumens, colour)")
    assert "light.color.copy(colour);" in laid
    assert "light.power = lumens;" in laid, "three.js takes lumens directly"
    # The globe is the source: unlit, and pushed above 1 so it reads as
    # brighter than white rather than as a pale ball.
    assert "1.2 + 1.8 * Math.min(1, lumens / 3000)" in lit

    # A source casting a hard sun shadow of ITSELF reads as plastic.
    made = _js_function(js, "function makeProp(type)")
    assert "if (child.isMesh && !child.userData.lampGlobe) {" in made

    assert "depthTest: false" not in _js_function(js, "function propOrbLight()")

    # Glow is gone, all of it. Param, 2026-09-11: "glow doesnt work well
    # id rather remove it". The dial, its state, the halo sprite and its
    # texture, and every write to them. control("glow-strength") in the
    # scene restore is named on purpose: the guard that every id the
    # script asks for exists reads only getElementById, so a lookup of a
    # removed id through control() would pass it and then throw on
    # restoring any old scene.
    assert "glow-strength" not in html
    assert "glow-strength" not in js
    assert 'control("glow-strength")' not in js
    assert "lampHalo" not in js and "haloTexture" not in js
    assert "state.glow" not in js and "applyGlow" not in js
    assert "child.isSprite" not in js, "the dispose branch served only the halo"
    # A scene saved with a glow still opens: the key is left unread, and
    # nothing writes it any more.
    restore = _js_function(js, "async function applyScene(record)")
    assert '// Older scenes carry "glow", the removed halo dial: ignored on purpose.' in restore
    assert "scene_.glow" not in js
    assert "glow: state" not in js

    # Both numbers survive a reload and a scene.
    # The layout and the scene share one encoder, which carries a lamp's
    # numbers beside its row, and one decoder, which puts them back.
    assert "extras[i] = { size: p.size, lumens: p.lumens, kelvin: p.kelvin };" in js, (
        "the study layout")
    assert "props: withProps ? encodeProps(state.props) : undefined," in js, "the scene"
    assert "if (extra) Object.assign(entry, extra);" in js
    assert js.count("adoptLampSettings(record, entry);") == 2, (
        "restoreProps and applyScene both give a lamp its numbers back")
    adopt = _js_function(js, "function adoptLampSettings(record, entry)")
    assert "state.lampLumens;" in adopt and "state.lampKelvin;" in adopt, (
        "a prop saved before lamps existed restores lit, not dark")

    # The controls, in the shelf's LIGHTS drawer since 2026-09-09, beside
    # the fixtures they tune. Param: "the light settings should find
    # itself somewhere else, maybe we need to make a light tile and put
    # all the lights there and not in props".
    drawer = html[html.index('<div id="lights-panel"'):]
    drawer = drawer[:drawer.index('<div id="shelf-grid"')]
    for control in ("lamp-lumens", "lamp-kelvin",
                    "light-size", "light-length"):
        assert 'id="%s"' % control in drawer, control
    scene = html[html.index('<details id="scene-section">'):]
    scene = scene[:scene.index("</details>")]
    assert 'id="lamp-lumens"' not in scene, (
        "and they are not left behind in Scene as a second set")
    aim = _js_function(js, "function lampTargets()")
    assert "if (isLamp(state.selectedProp)) return [state.selectedProp];" in aim
    assert "return state.props.filter(isLamp);" in aim
    # The heading says which of the two is about to happen, and it has to
    # be told when the count changes -- it read "Lights" over two lamps
    # until a placement started saying so.
    sync = _js_function(js, "function syncLightControls()")
    assert '"tuning all " + lamps.length + " fixtures"' in sync, (
        "the heading moved into the Lights drawer's readout line, and it "
        "stopped calling them lamps: Param asked for both")
    assert "  if (isLamp(record)) syncLightControls();\n  if (save) saveProps();" in js

    # The fixtures are offered even with no prop library at all: they are
    # code, not files, so no folder needs choosing and no fetch can fail
    # them. They live in LIGHT_KINDS since 2026-09-09, feeding their own
    # drawer rather than the prop shelf.
    assert 'key: "light-sphere", label: "Sphere"' in js
    assert 'key: "light-strip", label: "Strip"' in js
    assert 'key: "light-cube", label: "Cube"' in js
    assert "state.propLibrary = BUILT_IN_PROPS.slice();" in js
    ensure = _js_function(js, "function ensurePropTemplate(key)")
    assert "if (entry.builtIn) return Promise.resolve(null);" in ensure, (
        "a built-in has no file to fetch, and fetching one would log a "
        "load failure for a prop that works")


def test_a_slider_that_rests_at_zero_declares_its_unit():
    """The typable reading works out its unit by dividing what is shown by
    what the slider holds -- which is exactly the one thing a slider
    sitting at ZERO cannot tell it: 0 mm and 0 m read the same. Typing 20
    into such a slider wrote a raw 20, clamped to the maximum. Every
    slider that can rest at zero and shows a scaled reading declares its
    factor instead."""

    panel = (REPO / "bench" / "studio" / "static" / "panel.js").read_text(
        encoding="utf-8")
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")

    assert "const declared = parseFloat(input.dataset.unit);" in panel
    assert "const scale = Number.isFinite(declared) ? declared\n"\
        "      : (Number.isFinite(shown) && raw !== 0 ? shown / raw : 1);" in panel

    # The five that can sit at zero: four relief/percentage dials and the
    # new outline. A declared unit on each, or typing into it lies.
    for slider, unit in (("material-relief", "10"), ("material-occlusion", "100"),
                         ("material-variation", "100"), ("ground-relief", "10"),
                         ("outline-width", "1000")):
        mark = html[html.index('id="%s"' % slider):]
        mark = mark[:mark.index(">")]
        assert 'min="0"' in mark, slider
        assert 'data-unit="%s"' % unit in mark, slider


def test_the_client_size_floor_still_mirrors_the_server():
    """The floor moved to 100 mm on the server and this mirror was left at
    300, so a bundle cut at 100 or 200 mm failed the range test in
    applyCut: the slider and its reading kept the PREVIOUS number while
    the vault on screen was cut finer. A mirror that drifts is worse than
    no mirror, so the two files are held to the same pair here."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    app = (REPO / "bench" / "studio" / "app.py").read_text(encoding="utf-8")
    import re
    client = re.search(r"const SIZE_MIN = ([\d.]+), SIZE_MAX = ([\d.]+);", js)
    assert client, "the client mirror is gone"
    server_min = re.search(r"^SIZE_MIN = ([\d.]+)", app, re.M)
    server_max = re.search(r"^SIZE_MAX = ([\d.]+)", app, re.M)
    assert float(client.group(1)) == float(server_min.group(1)), (
        "the client would refuse a size the server happily cuts")
    assert float(client.group(2)) == float(server_max.group(1))


def test_a_take_records_at_the_size_it_claims_and_in_a_format_that_keeps_up():
    """Param: "i want high quality but its taking 10seconds plus a frame
    which is too long ... how do we get this whole recording to finish in
    5 mins max, but retain best quality we can."

    Three costs stacked. PNG is lossless deflate and his ground is fine
    gravel -- high-frequency noise is its worst case, so the encoder did
    maximum work for a maximum-size file, and it grew worse as the vault
    filled. The buffer was also four times the size the button claimed,
    because setSize multiplies by the display's device pixel ratio. And
    nothing overlapped: render, wait for encode, wait for upload, repeat.
    """

    js = STUDIO_JS.read_text(encoding="utf-8")
    # JPEG at 0.95, his ruling. ffmpeg re-encodes every take to H.264
    # 4:2:0, which throws away far more than 0.95 does.
    assert 'const RECORD_MIME = "image/jpeg";' in js
    assert "const RECORD_QUALITY = 0.95;" in js
    assert '(resolve) => canvas.toBlob(resolve, RECORD_MIME, RECORD_QUALITY));' in js
    # The TAKE never writes PNG frames: 3,617 of them at 1920 wide is
    # what throttled a recording to a crawl. The still is a different
    # job with the opposite trade, one plate printed and looked at
    # closely, so it does write PNG, and the check is scoped to the
    # recorder's own loop rather than the whole file.
    take = _js_function(js, "async function recordAnimation()")
    assert 'canvas.toBlob(resolve, "image/png")' not in take
    # A stitch failure reaches the LOG, not only a status line the next
    # click clears. Two eleven-minute takes failed on 2026-09-09 and the
    # diagnostics log never heard about either, which is why it read as
    # never having worked rather than as having failed once.
    assert 'logStudio("recording: stitch failed after " + total + " frames: "' in take
    assert "the frames are kept under the study folder" in take

    # A TRUE 1080p BUFFER. The composer keeps its own copy of the ratio,
    # taken when it was built, so setting it on the renderer alone would
    # leave every pass still running at the old size.
    assert "  renderer.setPixelRatio(1);\n  composer.setPixelRatio(1);" in js
    assert "    renderer.setPixelRatio(wasPixelRatio);\n" \
        "    composer.setPixelRatio(wasPixelRatio);" in js, (
            "and the viewport gets its own density back afterwards")

    # THE UPLOAD OVERLAPS THE NEXT FRAME. The previous frame's request is
    # awaited only after this one has rendered and encoded.
    assert "  let inFlight = null;" in js
    assert "      await settle();\n      inFlight = fetch(" in js
    assert "    await settle();                      // the last frame is still in the air" in js

    # MEASURED, so the next slow take is answerable from the log.
    assert "  const spent = { render: 0, encode: 0, upload: 0 };" in js
    assert '      + ", " + each.toFixed(3) + " s each -- render "' in js
    # And he can see the estimate while it runs, not only afterwards.
    assert '          + Math.round(each * (total - frameIndex) / 60) + " min left";' in js


def test_turning_the_machine_off_never_depends_on_the_server():
    """Param: "can you allow no machine to be placed in the web app, this
    can be done by having an option in the machine drop down which says no
    mechanism."

    It already existed. He could not SEE it, because refreshMechanisms
    fetched the library first and returned on failure before adding a
    single entry -- and his studio's server predates /api/mechanisms, so
    the fetch threw and the control was left entirely empty.

    Auto and No mechanism need no folder, no library and no server.
    Turning the machine off is the one choice that must never depend on
    anything being reachable."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    build = js[js.index("async function refreshMechanisms() {"):
               js.index("function fetchMechanismFor(")]
    # The two fixed entries are added BEFORE the fetch is even attempted.
    added = build.index('add("auto"')
    fetched = build.index('fetchJson("/api/mechanisms")')
    assert added < fetched, (
        "Auto and No mechanism must be written before the library is asked "
        "for, or a server that cannot answer empties the control")
    assert build.index('add("none"') < fetched
    # And a failed listing costs the borrowed machines and nothing else.
    assert "    return;                        // no folder chosen; the control stays empty" not in build, (
        "a failed listing must no longer abandon the whole control")
    assert 'logStudio("mechanism library: the machines could not be listed ("' in build
    assert "    state.mechanismLibrary = [];" in build
    # Choosing it draws no machine at all, and the old one is taken down:
    # buildMachine disposes before it reads the document.
    assert '  if (state.mechanismChoice === "none") return null;' in js
    machine = js[js.index("async function buildMachine() {"):]
    assert machine.index("disposeMachine();") < machine.index("if (!state.mechanism) return;"), (
        "the standing machine is taken down before the new document is read, "
        "or No mechanism would leave the old one on screen")


def test_the_recorder_owns_the_camera_and_the_canvas_during_a_take():
    """Param: "the animation recording, as long as it took, didnt do the
    same animation as i get when i play the animation directly? why? it
    should be the same please."

    Because the turntable's ownership was gated on state.timeline.playing,
    which recordAnimation deliberately sets FALSE -- two clocks racing the
    same state is worse. So during every take controls.update() ran on
    each animation frame and its leftover damping dragged the camera off
    the bearing applyTimeline had just pinned. Same function, same t,
    different camera.

    And renderView() then drew that camera over the frame the recorder had
    just composed, in the window between its render and its pixel read."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "  const turntableOwns = state.timeline\n" \
        "    && (state.timeline.playing || state.recording)" in js, (
            "a take owns the camera exactly as a play does")
    assert "  if (!state.recording) renderView();" in js, (
        "and the loop keeps its hands off the canvas until the take ends")
    # The clock itself was never the difference: live advances by
    # delta * speed, the recorder by frameIndex * speed / fps, which is
    # the same range at the same rate.
    assert "applyTimeline(Math.min(state.timeline.t + delta * state.timeline.speed," in js
    assert "      applyTimeline(frameIndex * speed / fps);" in js


def test_the_recordings_output_folder_has_a_button():
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(encoding="utf-8")
    assert '<button id="recordings-folder-choose"' in html
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'showLibraryFolder("recordings", "recordings-folder-path", "recordings");' in js
    assert 'chooseLibraryFolder("recordings", "recordings-folder-path", "recordings",' in js


def test_the_shelf_record_tile_becomes_a_stop_button():
    """Param: "the stop record needs to happen on the record tile too not
    just in the banner menu. show a stop icon when the recording is
    going." The tile already delegated its click to the panel button, so
    it always stopped the take; what it lacked was saying so."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert '    tile.textContent = state.recording ? "\\u25a0" : "\\u25cf";' in js, (
        "a filled square while recording, a filled circle at rest")
    assert '    tile.classList.toggle("recording", state.recording);' in js
    assert '    tile.title = state.recording ? "Stop the recording" : "Record the animation";' in js
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(encoding="utf-8")
    assert "#shelf-actions button.recording," in css, (
        "filled red at rest while a take runs, like the panel's own button")


def test_the_machines_are_derived_when_the_document_places_none():
    """Param: "if i dont add in a mechanism to the json, i need you to be
    able to add in the mechanisms and anchors where applicable ... the
    anchors dont play fair in my script with many chnaging forms."

    Runs ONLY on a document with no instances, which is the ownership
    rule agreed with the exporter: the document is authoritative when it
    carries them, and the studio derives only when it does not."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    build = js[js.index("async function buildMachine() {"):
               js.index("// Where a wire first meets the machine")]
    assert "  const derived = model.instances.length ? null : deriveMachines(model);" in build, (
        "a document that places its own machines is never second-guessed")
    # The derived placement becomes THE MODEL's. Held only in a local it
    # is invisible to everything that reads the model: the checks put a
    # wire's head into world space through model.instances, so with none
    # there every derived wire was reported 18 m from the vertex it names,
    # and the "missing placements" banner fired on a machine that had in
    # fact been placed.
    assert "    model.instances = derived.instances;\n" \
        "    model.wires = derived.wires;" in build
    assert "  const instances = model.instances.length ? model.instances\n" \
        "    : [{ side: 0, mechanism: 0, matrix: null, mirrored: false, wireIds: [] }];" in build
    assert "derived ? derived.instances" not in build, (
        "the derived instances reach the build through the model, not "
        "past it")
    # A derived placement is a studio OPINION and must never be mistaken
    # for his authoring, so it says so where he will see it.
    assert '    showBanner("This mechanism carries no placements, so the machines are "' in build

    # A SPOOL, not a pulley: they arrive under the same `reels` key and
    # only the winding radius separates them. The writer's own figure
    # first, the studio's own measurement behind it.
    assert "    const radius = Number.isFinite(+part.windingRadius)\n" \
        "      ? +part.windingRadius : measureSpoolRadius(part);" in js
    assert "    if (radius < SPOOL_RADIUS_LIMIT) spools.push(part.axis.origin);" in js

    # Back into the net's OWN numbering. derivePlacements works in
    # indices into the support list it was handed, and every consumer
    # downstream speaks net vertex indices; confusing the two would draw
    # every cable to the wrong vertex and still look like a machine.
    assert "    instance.netVertices = instance.netVertices.map((i) => ids[i]);" in js
    assert "    netVertex: ids[wire.support]," in js
    assert "    anchor.netVertices = anchor.netVertices.map((i) => ids[i]);" in js, (
        "the anchors are renumbered too, or each would name the wrong "
        "cables it holds")

    # ANCHORS ARE READ BEFORE THEY ARE DERIVED, the same ownership rule
    # as the instances: the writer emits them whenever a result is wired,
    # and a document carrying its own is never second-guessed.
    assert "    if (!model.anchors.length) model.anchors = derived.anchors;" in build

    # ONE frame per derived wire, at the spool it leaves from. A derived
    # wire knows where the cable ends and nothing about how it wraps, so
    # the free span is drawn and the routed portion is not -- the honest
    # picture rather than an invented wrap.
    assert "      owner: \"reel\", ownerReel: wire.spool," in js
    # A support the net does not carry means the two documents disagree,
    # and deriving from them anyway would place machines off a net that
    # is not there.
    assert "    if (!v) return null;               // a support the net does not carry" in js


def test_a_mechanism_is_chosen_rather_than_inherited():
    """Param: "the mechanism itself wants to become an asset, so add to
    import the mechanism as a drop down selection, so if i export any
    other types of mechanisms, we can pick and chose or you can auto chose
    the best one."

    A mechanism stopped being a property of one study. The document is
    still fetched through /api/studies/{export}/mechanism, which was
    already keyed by export name and so already served any of them; what
    was missing was a listing to choose from and somewhere to choose."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(encoding="utf-8")
    assert '<select id="mechanism-select"' in html
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'fetchJson("/api/mechanisms")' in js
    # A FOLDER OF THEIR OWN, on the same two helpers every other library
    # uses. Param: "Ok make a directory and export it there, I can then
    # wire in other mechanisms there too."
    assert '<button id="mechanism-folder-choose"' in html
    assert 'showLibraryFolder("mechanisms", "mechanism-folder-path", "machines");' in js
    assert 'chooseLibraryFolder("mechanisms", "mechanism-folder-path", "machines",' in js
    # A new folder can mean a different machine under the same name, so
    # the vault on screen is re-dressed rather than left wearing one out
    # of the old folder.
    assert "      await refreshMechanisms();\n" \
        "      // A new folder can mean a different machine under the same name," in js
    # The document is fetched by the MACHINE's name, not by a study's: a
    # machine in the library belongs to no study.
    assert '  return fetch("/api/mechanisms/" + encodeURIComponent(name))' in js
    assert '"/api/studies/" + encodeURIComponent(exportName) + "/mechanism")\n' \
        "    .then((r) => (r.ok ? r.json() : null))" not in js
    assert '  add("auto", "Auto",' in js
    assert '  add("none", "No mechanism", "Draw no machine at all");' in js
    # The facts a choice is made on go in the LABEL: a dropdown of bare
    # study names says nothing about which machine suits which vault.
    assert '      : entry.spools + " spools" + (entry.instances ? ", places itself" : "");' in js

    # AUTO NEVER OVERRIDES A DOCUMENT THAT PLACES ITSELF. Agreed with the
    # exporter session: the document is authoritative when it carries
    # instances, and the studio only chooses when it carries none.
    assert "  if (own && Array.isArray(own.instances) && own.instances.length) return own;" in js
    assert '  if (state.mechanismChoice === "none") return null;' in js
    # Only a choice landing on a DIFFERENT export costs a second request;
    # his own is already in flight beside the bundle.
    assert "    if (state.mechanismChoice === exportName) return own;" in js
    assert "  if (!pick || pick.export === exportName) return own;" in js
    # And a borrow is SAID, with the arithmetic that justified it.
    assert '    + pick.export + " is borrowed -- " + pick.spools + " spools against "' in js

    # The choice outlives the session, since a chosen machine is a setting
    # rather than a property of whichever vault happens to be open.
    assert 'const MECHANISM_CHOICE_KEY = "vaulted.mechanism.choice";' in js
    assert "    localStorage.setItem(MECHANISM_CHOICE_KEY, state.mechanismChoice);" in js
    # A remembered choice naming an export that has since left the folder
    # falls back to Auto and SAYS so: a machine quietly changing is worse
    # than one that changed loudly.
    assert "  if (!select.value) {" in js
    assert '      + "the folder, so Auto is used");' in js
    # Refresh re-reads the machines beside the vaults, or a newly
    # exported machine would not appear until a reload.
    assert "  await refreshMechanisms();" in js


def test_refresh_reloads_the_vault_on_screen_not_just_the_listing():
    """Param: "when i press refresh in the import menu, i expect it to
    refresh the loaded vault too, because i upload a new file and it doesnt
    update even after pushing refresh."

    It only re-read the folder LISTING. A re-export of the vault already
    open changed the file on disk and nothing else: the listing came back
    identical, so nothing on screen was touched and the studio went on
    drawing the bundle it had loaded minutes before."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    handler = js[js.index('document.getElementById("study-refresh")'):]
    handler = handler[:handler.index("\n});")]
    assert "const standing = select.value;" in handler
    assert "await refreshStudies(standing);" in handler, (
        "the vault on screen keeps its place in the refilled list")
    assert "    await loadStudy(standing);" in handler, (
        "and is actually RELOADED, which is what the button promises")
    # Only if it is still there: a vault deleted from the folder between
    # exports must not be reloaded out of the listing it just left.
    assert "if (standing && names.includes(standing)) {" in handler


def test_a_scene_tile_can_update_itself_from_the_view_on_screen():
    """Param: "add a refrsh button to the scenes too ... a little refresh
    icon appears in the bottom right corner of the thumbnail which allows
    me to update that scene with what i have."

    PUT, not POST: POST mints a new id, which would leave a copy behind."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'update.className = "scene-update";' in js
    assert '"/api/scenes/" + encodeURIComponent(row.id),\n' \
        '        { method: "PUT", headers: { "content-type": "application/json" },' in js, (
            "an update replaces the scene he pointed at rather than "
            "saving a second one beside it")
    assert "state: collectScene(), thumbnail: captureThumbnail() }) });" in js, (
        "the view on screen now, still and all")
    # The tile underneath restores the scene, so the pip must not do both.
    assert "      event.stopPropagation();\n" \
        "      if (!state.bundle) {\n" \
        '        showBanner("Load a study before updating a scene", "error");' in js
    assert "      await refreshScenes();\n    });\n    const holder" in js, (
        "the list is re-read so the new still appears at once")
    # Hovering ANYWHERE on the tile reveals the pip. A sibling selector
    # cannot do it: the delete cross sits between the tile and the pip in
    # the DOM, so "+" never matches.
    assert '    holder.className = "scene-holder";' in js
    # A 405 means the running server predates the route, not that the
    # scene is bad. "Method Not Allowed" is the least useful thing that
    # could be said about that, and it is what he was shown.
    assert "        showBanner(response.status === 405" in js
    assert '            + "update route existed. Restart it and this will work."' in js

    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(encoding="utf-8")
    # POSITIONING UNSCOPED, because the scene list is drawn in two places:
    # the panel and the shelf's Scenes drawer. Scoped to #panel, the
    # shelf's pips had no positioning at all and flowed out below their
    # tiles at the left, which is exactly how he first saw them.
    # Anchored to the START OF A LINE. Written as a bare substring this
    # passed with the rule scoped back to "#panel .scene-update", since
    # that string still CONTAINS ".scene-update {" -- so the test agreed
    # with the very fault he reported.
    assert "\n.scene-update { position: absolute; right: var(--s2); bottom: var(--s2);" in css, (
        "the positioning rule must be unscoped, or the shelf's pips have none")
    assert ".scene-holder { position: relative; }" in css
    assert ".scene-holder:hover .scene-update," in css
    assert "#panel .scene-tile:hover + .scene-update" not in css, (
        "the delete cross sits between them, so + never matched")
    # The BOX is restated per container, because each has a blanket button
    # rule that outranks an unscoped class and would flatten it.
    for scope in ("#panel", "#shelf-body"):
        assert scope + " .scene-update {\n  width: 18px; height: 18px;" in css, scope
    assert "#panel .scene-delete {" in css and "top: var(--s2); right: var(--s2)" in css


def test_the_machine_draws_the_way_he_asked():
    """Param, on first seeing his machine in the app, 2026-09-09: the
    anchor once; the machine always there with the formwork and it was
    not; no animation; wires the same as the cables; the cables cropping
    through the drums; only one motor of seven; the bottom of the machine
    and the anchor on the floor; frame 1 in the principal bars' metal;
    real textures on every part.

    Each fix here rests on a measurement of his real export, recorded in
    the register and the contract page. The pins are contiguous where an
    early return could otherwise leave the text standing."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    build = js[js.index("async function buildMachine() {"):
               js.index("// Where a wire first meets the machine")]
    act = js[js.index("function applyMachineAct(t, strikeU) {"):
             js.index("function reportMachineChecks(model) {")]

    # THE MACHINE NEVER LEFT THE SCENE; IT WAS HIDDEN. Measured: 180
    # meshes present at every step, hidden by the strike once the clock
    # had been played or scrubbed to the end, where it sticks. The gate is
    # now the formwork's own lens in the timeline, and standing in the
    # rest modes, exactly as the finished net is.
    assert "formworkVisibility({ t, seconds, strikeU," in act
    # SHELL SHOWS THE ANCHORS (Param, 2026-09-09: "when i show shell i
    # expect to see the anchors too"). The permanent works are cast into
    # the finished building; only the plant is temporary. So the gate no
    # longer hides the whole group in shell -- it hides `temporary` and
    # leaves `permanent` standing.
    assert 'const wanted = state.showMachine !== false;' in act
    assert 'state.showMode !== "shell"' not in act, (
        "shell must no longer hide the anchor and tie with the machine")
    assert '  if (state.showMode === "shell") {\n' \
        '    temporary.visible = false;' in act
    assert "  permanent.visible = true;" in act
    assert "    temporary.visible = true;             // standing, as the finished net is" in act
    # The build lands after the load's own scene pass (it awaits its
    # materials), so it applies the clock itself or stands in a pose the
    # clock did not dictate.
    assert "  reportMachineChecks(model);\n" \
        "  // Born into the state the clock dictates." in build
    assert "applySceneAtTime(state.timeline.t);" in build
    # And it no longer waits on a bundle the first load has not got yet.
    assert "  if (!state.mechanism) return;" in build
    assert "!state.bundle" not in build

    # THE ANCHOR ONCE. The tie is authored at row scale in the body frame;
    # stamped per instance it appeared three times a side.
    # The anchor is stamped at every frame the document gives -- ONE PER
    # MACHINE, on his ruling -- now that the writer sends the body once
    # under mechanism.anchor and the placements separately (plugin
    # 95a31af). A document with no stamps still draws it once,
    # untransformed, which is how it travelled while it was fused into
    # the tension tie, and is what kept it from appearing three times a
    # side when he first saw it.
    assert '      const stamps = part.kind === "anchor" && model.anchors.length\n' \
        "        ? model.anchors : [null];" in build
    assert "        if (stamp) {\n" \
        "          mesh.matrixAutoUpdate = false;\n" \
        "          mesh.matrix.fromArray(stamp.matrix);" in build
    assert "        note(part.kind, lowestZ(geometry, stamp ? mesh.matrix : null));" in build, (
        "a stamped anchor is measured for the floor THROUGH its own frame")
    # A document can carry anchor frames with no body to stand on them.
    assert '  if (model.anchors.length && !model.parts.some((part) => part.kind === "anchor")) {' in build
    # And the summary says how many arrived, beside the parts, instances
    # and wires. Every one of those counts has answered a "why am I only
    # getting one" at some point tonight.
    assert '    + model.anchors.length + " anchors");' in build

    # THE SKINS ARE FETCHED, NOT MERELY HOPED FOR. This is the fault
    # behind "the material we have now is so ugly": machineMaterial only
    # ever READ libraryCache, nothing ever asked for the machine's
    # materials, so all seven names missed and every part wore the same
    # 0x8d9298 fallback grey. A build must ask for them and wear them.
    # skinMachine stands above buildMachine in the file, so these are
    # pinned against the whole of studio.js rather than the build's slice.
    assert "function skinMachine(group, mine) {" in js
    assert "  skinMachine(group, mine);" in build, (
        "a finished build asks for its materials")
    assert "    jobs.push(ensureLibraryMaterial(key).then((set) => {" in js
    # Counted and SAID, so a part left in the fallback grey is answerable
    # from the log rather than from a screenshot.
    assert '      + " library materials"' in js
    assert "      if (!set || mine !== machineBuild) return null;" in js, (
        "a set landing after a newer build must not repaint the old one")
    assert "  mesh.userData.machineSkin = part.material;" in js, (
        "each mesh remembers the set it asked for, so it can be re-skinned")
    # And the sets it wears cannot be evicted from under it: the machine
    # holds five at once against a cache that used to hold six.
    assert "  for (const key of wanted.keys()) libraryPins.add(key);" in js
    assert "      if (libraryPins.has(oldest)) continue;" in js
    # Cleared at the TOP of the build, not after it: the wire material
    # adds its own pin part way through, and clearing afterwards wiped it,
    # leaving the cables' metal open to eviction on every build.
    assert "  disposeMachine();\n" in build
    assert build.index("libraryPins.clear();") < build.index("libraryPins.add(PRINCIPAL_SKIN);"), (
        "the pins are cleared before anything adds one, not after")
    # And a name looked up against a list still in flight must WAIT.
    # Losing that race is why which parts got skinned varied by reload.
    assert "  if (!state.materialLibrary.length && materialLibraryReady) {\n" \
        "    await materialLibraryReady;" in js
    assert "materialLibraryReady = refreshMaterialLibrary().catch(" in js
    assert '    logStudio("material " + key + " is not in the library folder");' in js, (
        "and a genuine miss is said out loud rather than returning a "
        "silent null")

    # THE MOTOR BANK IS STAMPED ONCE WHEN THE BODY IS ALREADY THE BANK.
    # His single motors body spans 0.965 m along the bank line while the
    # seven spools span 0.820 m, so stamping it per spool made 49 motors a
    # machine (Param: "I also have found way too many motors?").
    assert "const MOTOR_BANK_SHARE = 0.5;" in js
    assert "  if (hi - lo > span * MOTOR_BANK_SHARE) return [[0, 0, 0]];" in js
    shifts = _js_function(js, "function motorShifts(model)")
    assert "      if (d > span) { span = d; axis = [dx / d, dy / d, dz / d]; }" in shifts, (
        "the bank's line is the two spools furthest apart, since the home "
        "reel need not be an end one")
    assert "    const along = v[i] * axis[0] + v[i + 1] * axis[1] + v[i + 2] * axis[2];" in shifts, (
        "and the body's reach is measured along that line")
    # The anodising tint has to survive the re-skin. Without this the
    # frames arrive in raw mill aluminium the moment the set lands --
    # which would look like the load having failed all over again.
    assert "        if (mesh.userData.machineTint) worn.color.set(mesh.userData.machineTint);" in js

    # THE ROUTING PLANES ARRIVE AS THE CENTRELINE, because HE offsets
    # them in Grasshopper: "yes i offset and you use it as centerline".
    # So the reader adds nothing. The other two readings stay reachable
    # from the document, which is what let three rulings in one evening
    # cost no code change on either side after the first.
    assert '"centreline" ? 0' in build
    assert '  const routingOffset = model.routingFrameMeaning === "centreline" ? 0\n' \
        '    : model.routingFrameMeaning === "contact" ? state.wireRadius\n' \
        "    : -state.wireRadius;" in build
    assert "      wireCentreline(wire.route, reelAxes, routingOffset), state.wireRadius);" in build
    assert "wireCentreline(wire.route, reelAxes, state.wireRadius)" not in build, (
        "the old one-wire-radius offset is gone")
    # And the reel radius the writer now measures per reel wins.
    assert "    part.contactRadius = part.windingRadius\n" in build

    # THERE IS A WAY OUT OF A RECORDING. Param: "if recording and i want
    # to stop theres no way out, so the recording button needs to become a
    # stop button." One button, both jobs, and the flag is read at the TOP
    # of each frame so a press lands within one frame rather than after
    # another render and upload.
    assert "  recordStop: false," in js
    assert "      if (state.recordStop) { stopped = frameIndex; break; }" in js
    assert 'button.textContent = state.recording ? "Stop recording" : "Record 1080p";' in js
    assert '  button.classList.toggle("recording", state.recording);' in js
    assert "    state.recordStop = true;" in js, "a second press stops the take"
    # A stopped take is not stitched: he pressed stop because it was
    # wrong, and handing him a video of it anyway would be a surprise.
    assert '      status.textContent = "stopped at frame " + stopped + " of " + total' in js
    # And the button goes back to Record however the take ended.
    assert "    state.recording = false;\n" \
        "    state.recordStop = false;\n" \
        "    paintRecordButton();" in js

    # AN EMPTY EXPORT SAYS SO RATHER THAN LOOKING LIKE A LOST MACHINE.
    # Param, on an export carrying no instances at all: "I am only getting
    # one mechanism why?" The fallback that draws the body once is right --
    # it is the only honest reading of a document with no placements -- but
    # in silence it is indistinguishable from the studio dropping five.
    assert "  const instances = model.instances.length ? model.instances\n" in build
    assert "  if (!model.instances.length) {\n" \
        '    logStudio("machine: this document carries NO instances, so the machine "' in build
    assert '      + "the exporter, so this is a gap in the export rather than in the "' in build, (
        "and it names where placements come from, so the next question "
        "starts in the right place")
    assert "  if (!model.wires.length) {\n" \
        '    logStudio("machine: this document carries NO wires, so no cables are "' in build
    assert "  if (!model.instances.length || !model.wires.length) {\n" in build
    assert '      + ", so the machine is drawn once and does not run", "error");' in build, (
        "loud enough to answer the question before he has to ask it")
    assert '[model.instances.length ? null : "machine placements",\n' \
        '         model.wires.length ? null : "wires"].filter(Boolean).join(" and ")' in build, (
            "and it names which of the two is missing, not both blindly")

    # THE STRIKE REVERSES THE PLANT OUT, it does not drop it through the
    # floor. Param: "have the mechanism go backwards from its position on
    # each side (backwards mirrored) when the collapse and fade of the
    # mechanism happens instead of having it fall under the ground."
    #
    # One group per instance is what makes that possible at all: a single
    # translation of `temporary` can only move both rows the same way,
    # which is exactly why the old strike dropped the lot downwards.
    assert "  const sides = instances.map(() => new THREE.Group());" in build
    assert "  for (const side of sides) temporary.add(side);" in build
    assert "        sides[instances.indexOf(instance)].add(mesh);" in build, (
        "the parts ride with their own side, not with the whole machine")
    assert "temporary.position.z = -1.5 * struck;" not in act, (
        "the machine no longer falls under the ground")
    assert "      away[0] * MACHINE_RETREAT * struck, away[1] * MACHINE_RETREAT * struck, 0);" in act, (
        "horizontal only: it drives off across the floor, not into it")
    # MIRRORED WITHOUT BEING TOLD WHICH SIDE IT IS ON: the direction is
    # taken outward from the mean of the instance origins, so two rows
    # mirror by construction and one row or three still behave.
    assert "    const dx = (instance.matrix ? instance.matrix[12] : 0) - middle[0];" in build
    assert "    return d > 1e-6 ? [dx / d, dy / d] : [0, 0];" in build, (
        "a machine with no outward direction fades where it stands")
    # The wires travel with the machine that pulls them, head and span
    # both, or they would be left stretched across the site.
    assert "  if (entry.side) into.add(entry.side.position);" in js
    assert "      if (entry.side) entry.free.position.sub(entry.side.position);" in act
    # And the permanent works do not move: they are cast in.
    assert "permanent.position" not in act

    # THE CABLES ARE BLACK, and black by WEARING THE FORMWORK'S OWN
    # METAL rather than a colour picked to imitate it: the principal
    # lines' polished dark steel is what reads black on his formwork.
    # Param: "the cables should be black to match the cables used on
    # formwork".
    assert "const CABLE_BLACK = 0x24262a;" in js
    assert "  wireMaterial.color.set(CABLE_BLACK);" in build
    assert "  ensureLibraryMaterial(PRINCIPAL_SKIN).then((set) => {" in build, (
        "the same key the principal bars wear, so a re-skin of one is a "
        "re-skin of both")
    assert "  libraryPins.add(PRINCIPAL_SKIN);" in build, (
        "and it cannot be evicted from under the wires")
    # ONE material for every wire, with the library's maps copied ONTO it:
    # applyMachineAct fades the whole net through this single opacity, so
    # a per-mesh re-skin would break the strike.
    assert "    wireMaterial.map = set.material.map;" in build
    assert "    wireMaterial.needsUpdate = true;" in build

    # THE WIRES ARE THE CABLES: the same steel the net clones, transparent
    # from birth, and never vertexColors.
    assert "  const wireMaterial = materials.steel.clone();\n" \
        "  wireMaterial.color.set(CABLE_BLACK);\n" \
        "  wireMaterial.transparent = true;" in build
    assert "vertexColors = true" not in build, (
        "the net needs that for setColorAt; a plain Mesh with no colour "
        "attribute would multiply by nothing and go black")

    # THE CENTRELINE IS PREPARED BEFORE IT IS LOFTED -- subdivided across
    # every drum span, and no longer pushed out, since Param ruled the
    # frames ARE the centreline. The loft sweeps a rotation-minimising
    # frame rather than trusting the exported x/y.
    loft = _js_function(js, "function loftWire(points, radius)")
    assert "x = [x[0] - tn[0] * along, x[1] - tn[1] * along, x[2] - tn[2] * along];" in loft, (
        "parallel transport: the previous x with its along-tangent part removed")

    # THE RADIUS A REEL WINDS AT comes from the frames it owns, not from
    # the document's spoolRadius (0.030, which matches nothing in the
    # file) and not from the flange.
    assert "      || reelContactRadius(model.wires, part.index, part.axis)" in build
    measure = _js_function(js, "function measureSpoolRadius(part)")
    assert "if (r > 1e-3 && r < nearest) nearest = r;" in measure, "the barrel, not the flange"

    # ONE MOTOR BODY, and WHICH READING WAS TAKEN said out loud: stamped
    # per spool when it is one motor, once when it is already the bank.
    assert "const shifts = motorShifts(model);" in build
    assert 'const placements = part.kind === "motor" ? shifts : [[0, 0, 0]];' in build
    assert 'logStudio("machine: the document carries ONE motor body, and it is "' in build
    assert 'logStudio("machine: the motor body already reaches across the spool "' in build

    # THE FLOOR: lifted so the lowest point sits on the studio's floor,
    # and the log names which part that was and where it was authored.
    assert "  const floor = groundLevel();\n" \
        "  const lift = Number.isFinite(lowest) ? floor - lowest : 0;\n" \
        "  group.position.z = lift;" in build
    # The wire head and the free spans live in that lifted, dropping frame.
    head = _js_function(js, "function wireHead(entry, into)")
    assert "into.z += machineObjects.group.position.z + machineObjects.temporary.position.z;" in head
    assert "      entry.free.position.z -= parentZ;" in act

    # THE SPIN is measured along the RIB through the net, not the free
    # span: on the real file the route's first frame IS the anchor, so
    # the free span is zero at every frame and the reels stood still.
    assert "entry.rib = ribChain(edges, finalPose, wire.netVertex);" in act
    assert "entry.ribAtFrame0 = chainLength(firstPose, entry.rib) / 2;" in act, (
        "halved: two machines pull on one rib")
    assert "served.ribNow * (1 - prestress), served.wire.reeveFactor, radius);" in act
    # THE SPIN turns about the drum's own axis through its own origin.
    assert ".multiply(pivotTo).multiply(machineMatrix).multiply(pivotBack);" in act
    assert "pivotTo.makeTranslation(axis.origin[0], axis.origin[1], axis.origin[2]);" in act

    # TEXTURES: smooth normals first, then a triangle soup with box UVs at
    # the picture's own tile size. Without UVs every library material read
    # as one flat texel.
    geom = _js_function(js, "function geometryFromPart(part)")
    assert "geometry.computeVertexNormals();" in geom
    assert "geometry = geometry.toNonIndexed();" in geom
    assert "boxUVs(positions, centre, [0, 0], 1 / tile[0], 1 / tile[1])" in geom
    assert 'geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));' in geom, (
        "computing the UVs is not the same as giving them to the mesh")
    # Twice in the file: the voussoirs' and the machine's. A mutation that
    # stripped the PIECES' UVs was caught by nothing until this line.
    assert js.count('geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));') == 2
    assert geom.index("computeVertexNormals") < geom.index("toNonIndexed"), (
        "normals are smoothed while the corners are still shared")


def test_the_entry_box_is_torn_down_exactly_once():
    """The red banner Param photographed: "Uncaught NotFoundError: Failed
    to execute 'remove' on 'Element': The node to be removed is no longer
    a child of this node. Perhaps it was moved in a 'blur' event
    handler?"

    Enter and blur BOTH commit, and they are not alternatives. Removing a
    focused element makes the browser fire blur synchronously from inside
    the removal, so Enter re-entered commit: every change event fired
    twice (two full re-cuts for one typed piece size) and the outer
    remove() then looked for a node its own reentrant twin had already
    taken out. Measured live before the fix: changes = 2, one throw.

    The teardown is therefore once-only, and it drops the blur listener
    BEFORE it removes the box, which is the ordering that matters: the
    other way round, blur still lands mid-removal."""

    panel = (REPO / "bench" / "studio" / "static" / "panel.js").read_text(
        encoding="utf-8")

    # Pinned contiguously, in order: the guard, then the unlisten, then
    # the removal. Any one of the three alone is not the fix.
    assert "    let torn = false;\n"\
        "    const restore = () => {\n"\
        "      if (torn) return;\n"\
        "      torn = true;\n"\
        '      box.removeEventListener("blur", commit);\n'\
        "      if (box.parentNode) box.remove();" in panel

    # And the banner it wore. A throw after the studio is up means a
    # handler failed on a page that is fully built; saying "half-built"
    # there sent him hunting a cached script for a fault in a slider.
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    boot = html[html.index("function bootFault(message)"):]
    boot = boot[:boot.index('window.addEventListener("error"')]
    assert "if (window.__studioReady) {" in boot
    assert "<b>Something in the studio threw.</b>" in boot
    assert boot.index("if (window.__studioReady) {") \
        < boot.index("<b>The studio stopped setting itself up.</b>"), (
        "the ready check has to come FIRST or the boot message wins anyway")


def test_props_carry_a_height_and_the_gumball_can_move_it():
    """Param: "add in a x,y,z arrow control on the objects when in edit
    mode. allowing them to clip below ground, as some assets need to do
    so", and then "if i drag an object down in z, when i click and move
    it around it should always stay at that z height until i raise or
    lower it again via z".

    So z is a real field on the record, persisted everywhere x and y are,
    carried through a move rather than reset by it, and driven by a
    double-headed arrow that reads its own upright plane."""

    js = STUDIO_JS.read_text(encoding="utf-8")

    # A height on the record, defaulted, and written where x and y are.
    assert ("function placeProp(type, x, y, rotation, save, scale = 1, z = 0,\n"
            "                   rotX = 0, rotY = 0) {") in js
    assert "object.position.set(x, y, z);" in js
    assert "const record = { type, x, y, z, rotation, rotX, rotY, scale," in js
    # Persisted by BOTH memories: the per-study layout and a saved scene.
    # Re-pinned 2026-09-11: both memories write rows through one encoder,
    # z the fourth number of each, and one decoder reads it back.
    assert ("rows.push(t, roundMm(p.x), roundMm(p.y), roundMm(p.z || 0), "
            "roundTurn(p.rotation),") in js
    assert "props: withProps ? encodeProps(state.props) : undefined," in js
    assert "z: rows[i + 3], rotation: rows[i + 4], rotX: rows[i + 5], rotY: rows[i + 6]," in js
    # And restored by every reader, or a sunk prop pops back to the floor.
    assert js.count("+entry.scale || 1, +entry.z || 0,") == 2, (
        "restoreProps and applyScene both give a prop its height back")
    assert ("false, gone.scale, gone.z || 0, gone.rotX || 0, gone.rotY || 0)"
            in js), "undoing a delete restores the height and the tilt too"

    # HIS SECOND RULING: a move keeps the height it was given.
    assert "carried.object.position.set(hit.x, hit.y, carried.z || 0);" in js
    assert "record.object.position.set(record.x, record.y, record.z || 0);" in js, (
        "the stamp rig moves at its own height too")

    # RHINO'S GUMBALL (Param: "lets copy rhinos version of it", with a
    # sketch of three arrows and three arcs): an arrow to move along each
    # axis, an arc to turn about each, a square to scale by, a dot at the
    # origin, in Rhino's own axis colours.
    assert ('{ key: "x", colour: 0xd63b3b, dir: [1, 0, 0] }' in js
            and '{ key: "y", colour: 0x3faa4f, dir: [0, 1, 0] }' in js
            and '{ key: "z", colour: 0x2f6fe4, dir: [0, 0, 1] }' in js), (
        "X red, Y green, Z blue, which is not negotiable to a Rhino user")
    gumball = _js_function(js, "function setPropGumball(record)")
    for gesture in ("move", "rot", "scale"):
        assert '"%s-" + axis.key' % gesture in gumball
    assert "for (const axis of GUMBALL_AXES)" in gumball
    # World aligned, like Rhino's default: a gumball that span with its
    # prop would make "drag the red arrow" mean a new direction each time.
    assert "propGumball.rotation" not in gumball
    follow = _js_function(js, "function refreshPropGumball()")
    assert "propGumball.rotation" not in follow

    # Param: "can we make it about 3 times smaller? Have it a default size
    # for all objects." One size ON SCREEN, whatever it drives and however
    # far off the camera stands, which is Rhino's own behaviour: built at
    # unit size, scaled per frame off the camera distance.
    assert "const GUMBALL_SCREEN = 0.1;" in js
    assert "setFromObject(record.object)" not in gumball, (
        "the prop's own bounding box must not size the gumball again: "
        "that is what gave a fifteen-metre beech a car-sized widget")
    size = _js_function(js, "function sizePropGumball()")
    # The gumball keeps a constant SCREEN size, so it needs the world
    # height the camera sees where it stands. The two projections answer
    # that differently and there is no shared formula: distance is the
    # whole story in perspective and means nothing in orthographic, where
    # the frame is as wide at the near plane as at the far one. Left on
    # the perspective formula, an orthographic gumball grew with every
    # step the eye took backwards.
    assert "visibleHeightAt(propGumball.position)" in size, (
        "the gumball asks the active projection how big a metre is")
    span = _js_function(js, "function visibleHeightAt(point)")
    assert "orthoFrameHeight / (camera.zoom || 1)" in span, (
        "an orthographic frame is its own height over its zoom, and no "
        "function of distance at all")
    assert "camera.position.distanceTo(point)" in span
    assert "Math.tan(THREE.MathUtils.degToRad(perspectiveCamera.fov) / 2)" in span, (
        "the visible world height at that distance, from the real lens")
    assert "propGumball.scale.setScalar" in size
    # Sized on the one path every render takes, the recorder's included.
    view = _js_function(js, "function renderView()")
    assert "sizePropGumball();" in view
    # And before a raycast, because a click can land between the build
    # and the next render, when the group is still at unit size.
    assert "  sizePropGumball();\n  propGumball.updateMatrixWorld(true);" in js
    # The group is declared above renderView, not down in the gumball
    # section: a `let` down there is in its temporal dead zone for any
    # render that happens during boot.
    assert js.index("let propGumball = null;") < js.index("function renderView()")

    # One reader per gesture, chosen for the gesture rather than the
    # ground: the ground plane cannot measure a vertical drag, nor a
    # rotation about anything but Z.
    along = _js_function(js, "function axisDistanceAt(event, record, index)")
    assert "camera.getWorldDirection(view);" in along
    assert "-view.dot(direction));" in along, (
        "the plane contains the axis and faces the camera as squarely as "
        "a plane containing that axis can")
    about = _js_function(js, "function rotationAngleAt(event, record, index)")
    assert "AXIS_VECTORS[(index + 1) % 3]" in about
    assert "Math.atan2(local.dot(v), local.dot(u))" in about

    # Tilt is real state, not just a control: all three arcs turn something.
    assert "function applyPropRotation(record)" in js
    assert "record.object.rotation.set(record.rotX || 0, record.rotY || 0," in js
    # Both memories write through one encoder (re-pinned 2026-09-11), so
    # the tilt is the sixth and seventh numbers of every row, in each.
    assert "roundTurn(p.rotX || 0), roundTurn(p.rotY || 0), roundMm(p.scale || 1)," in js, (
        "the layout keeps tilt")
    assert "props: withProps ? encodeProps(state.props) : undefined," in js, "a saved scene keeps tilt"
    assert js.count("+entry.rotX || 0, +entry.rotY || 0)") == 2, (
        "restoreProps and applyScene both give a prop its tilt back")

    # Z travel is bounded by the prop's own height, so it can always be
    # buried and can never be flung out of sight.
    assert "const reach = propHeightOf(record) + 1;" in js
    assert "record.z = Math.min(reach, Math.max(-reach, startZ + travel));" in js
    # And the whole adjustment undoes as one, position, tilt and size.
    assert '["x", "y", "z", "rotation", "rotX", "rotY", "scale"]' in js
    assert "Object.assign(record, before);" in js


def test_the_principal_lines_dress_the_column_rows_and_the_net_stays_silver():
    """His correction of the first attempt: "those arent the principle
    lines. they are one per leg. they run up the middle and its the row
    that the columns connect to. the rest of the wires can return to how
    they were. I dont want it to be competely black either just darker
    silver but give it a nice metal texture, we have some textures in
    our library now."

    So: the net is silver tubes again; the principal lines are a
    SEPARATE instanced mesh of rectangular bars over the rows the column
    tips thread, walked on down to each leg's springing, wearing the
    library's polished dark steel (a darker-silver registry fallback
    until it arrives), following the net's strike, clearance and shadow
    rules, and stepping aside for the forces lens."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    # The net itself is back to how it was.
    net = _js_function(js, "function netInstances(edgeCount, vertexCount)")
    assert "CylinderGeometry" in net
    assert net.count("materials.steel.clone()") == 2
    assert "BoxGeometry" not in net
    wire_lens = _js_function(js, "function applyWireForces()")
    assert "materials.steel.color" in wire_lens

    # The walk: tips per column TREE, nearest net vertex each, threaded
    # by shortest path, then down to the leg's own springing.
    walk = _js_function(js, "function principalEdges()")
    assert "state.columnMembers" in walk
    assert "member.from[2] >= member.to[2]" in walk, (
        "tips are the HIGH degree-one ends; the feet stay on the ground")
    assert "bundle.supports" in walk
    assert "dijkstra" in walk

    # The dressing: rectangular bars over the wires' own segments, the
    # library skin once it arrives, darker silver until then.
    assert 'const PRINCIPAL_SKIN = "metal/steel-polished-dark";' in js
    bars = _js_function(js, "function buildPrincipalBars()")
    assert "new THREE.BoxGeometry(section, 1, section)" in bars
    assert "Math.max(0.064, 2.2 * state.wireRadius)" in bars, (
        "64 mm on his word, and still clear of the wires at any slider size")
    assert "materials.bar.clone()" in bars
    assert "ensureLibraryMaterial(PRINCIPAL_SKIN)" in bars
    assert "state.objects.principal !== mesh) return;" in bars, (
        "a texture landing late must not dress a mesh already replaced")
    assert ("bar: new THREE.MeshPhysicalMaterial({\n"
            "    color: 0x787d86, roughness: 0.35, metalness: 1.0") in js, (
        "darker silver, not black -- his correction")

    # The behaviour hooks: strike fade, rest clearance, forces-lens
    # yield, and disposal with the rest of the net.
    scene_time = _js_function(js, "function applySceneAtTime(t)")
    assert '["principal", clearance.wires]' in scene_time
    show_mode = _js_function(js, "function applyShowMode()")
    assert "netOn && !state.layers.forces" in show_mode
    dispose = _js_function(js, "function disposeWiresAndNodes()")
    assert '"principal"' in dispose
    reload = _js_function(js, "async function reloadColumns(names)")
    assert "state.columnMembers = [];" in reload
    assert "buildPrincipalBars();" in reload


def test_a_scene_outranks_the_device_appearance_memory():
    """Param's report: restored on another device, a scene came back with
    the right sky but the wrong skin and floor. loadStudy restores the
    DEVICE's per-material appearance on its way in, so applyScene must
    re-impose the scene's own appearance AFTER loadStudy returns, load
    the library skin and floor the scene names, and let the device
    memory follow the screen."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    apply_start = js.index("async function applyScene(record)")
    apply_body = js[apply_start:js.index("repaintSettingControls();", apply_start)]
    load = apply_body.index("await loadStudy(study);")
    after_load = apply_body[load:]
    # The guard is part of the pin: an if (false) around the assignment
    # would leave the text standing and the behaviour gone.
    reimpose = after_load.index(
        "if (scene_.appearance) {\n"
        "    state.appearance = Object.assign({}, scene_.appearance);")
    assert "await ensureLibraryMaterial(state.appearance.skin);" in after_load
    assert "persistAppearance();" in after_load
    assert "await loadGroundMaterial(scene_.ground.preset);" in after_load
    # And the order holds: the re-imposition sits before the tail's
    # rebuildAppearance, which is what repaints the pieces with it.
    assert reimpose < after_load.index("rebuildAppearance();")


def test_a_scene_missing_its_sky_says_so_and_restores_the_rest():
    """Param's live case: a scene saved under a sky whose file later left
    the sky folder. loadHdri swallows its own failure, so applyScene must
    read the unstamped name as the verdict and tell the story in scene
    terms -- everything else restored, the missing sky named."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    apply_start = js.index("async function applyScene(record)")
    apply_body = js[apply_start:js.index("\n}", apply_start)]
    verdict = apply_body.index("await loadHdri(hdri.name);")
    after_load = apply_body[verdict:]
    assert "if (state.hdriName !== hdri.name)" in after_load
    assert "is not in the sky " in after_load
    assert "the rest of the scene is restored" in after_load


def test_the_folder_status_line_carries_the_reason():
    """The client repeats the server's zero-vault hint beside the count
    instead of leaving a bare "0 vaults in this folder" (the line Param
    met when the picker took the cut cache)."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'folder.hint ? " -- " + folder.hint : ""' in js


def test_the_data_sheet_leads_with_the_analysis():
    """Param: "another tab heading which comes up first... actually helps
    us make sense of the data". Analysis opens first, Overview keeps the
    raw sheet, Graphs loads the vendored plotting library only when
    asked, and a narrative fault shows itself in place instead of taking
    the Data button down."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    tabs = html[html.index('id="data-tabs"'):]
    tabs = tabs[:tabs.index("</div>")]
    assert tabs.index("Analysis") < tabs.index("Overview") < tabs.index("Graphs")

    js = STUDIO_JS.read_text(encoding="utf-8")
    button = js[js.index('getElementById("data-button").addEventListener'):]
    button = button[:button.index("\n});")]
    assert 'showDataTab("data-analysis");' in button
    assert "renderAnalysisTab();" in button
    assert '"/static/vendor/plotly-basic.min.js"' in js, (
        "the plotting library is vendored and lazy, never a CDN")
    render = _js_function(js, "function renderAnalysisTab()")
    assert 'reportProblem("the analysis narrative failed' in render, (
        "a narrative fault files a report and leaves the sheet standing")

    app_py = (REPO / "bench" / "studio" / "app.py").read_text(encoding="utf-8")
    assert '"data_analysis.js"' in app_py, (
        "the module must join the versioned import remap or a stale copy "
        "outlives every edit")


def test_the_waker_stays_on_loopback_and_stays_silent():
    """Loopback-only is the security model: Tailscale Serve is the only
    road in. And the handler must override the stdlib's request logging,
    which writes to a stderr that does not exist under pythonw -- one such
    write ends the process (serve.py's ensure_stdio lesson)."""

    body = inspect.getsource(waker.main)
    assert '("127.0.0.1", WAKER_PORT)' in body
    assert waker.WakerHandler.log_message is not (
        BaseHTTPRequestHandler.log_message)


def test_the_scatter_is_its_own_tab_with_the_controls_he_named():
    """Param: "we should have a scatter tile next to props that allows us
    to select the props we want, how often each one appears, the size
    ratio we pick, and some other relevant settings".

    A tab of its own rather than a button inside Layers, because choosing
    species is browsing and browsing is what the shelf is for."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")

    tabs = html[html.index('<div id="shelf-tabs">'):]
    tabs = tabs[:tabs.index("</div>")]
    assert 'data-shelf="scatter"' in tabs, "the tab is beside Props"
    assert tabs.index('data-shelf="scatter"') > tabs.index('data-shelf="props"')
    assert tabs.index('data-shelf="scatter"') < tabs.index('data-shelf="materials"')

    # The four things he asked for by name, plus the region and the dice.
    for control in ('id="scatter-species"',      # which props
                    'id="scatter-chosen"',       # how often each appears
                    'id="scatter-size-min"', 'id="scatter-size-max"',
                    'id="scatter-spacing"', 'id="scatter-clump"',
                    'id="scatter-seed"', 'id="scatter-dice"',
                    'id="scatter-area"', 'id="scatter-brush"',
                    'id="scatter-radius"',   # the brush's own size
                    'id="scatter-deselect-or-chips"'[:0] or 'id="scatter-chosen"'):
        assert control in html, control

    assert 'if (shelfKind === "scatter") { cats.innerHTML = ""; ' \
        'renderShelfScatter(); return; }' in js, "the tab has to render"


def test_the_scatter_seed_uses_a_generator_that_is_exact_in_32_bits():
    """Determinism is the whole value of a seed, and the idiom already in
    this file is not one: `seed * 1103515245` reaches about 2**61, far
    past Number.MAX_SAFE_INTEGER, so it silently loses its low bits.
    Math.imul is exact."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(js, "function scatterRandom(seed)")
    assert "Math.imul" in body
    assert "1103515245" not in body
    assert "Math.random" not in body, (
        "a seeded field that consulted Math.random could not be re-dealt")


def test_the_scatter_stops_at_a_measured_budget_and_says_why():
    """The ceiling is TRIANGLES, not instances: props-hd runs from a 94
    triangle bollard to a 219,430 triangle beech, so a count means
    nothing across it. 35 M manifest triangles is six of the sixteen
    point seven millisecond frame, measured on the 4090 by
    bench/scripts/scatter_budget.mjs, not guessed."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const SCATTER_BUDGET_TRIANGLES = 35e6;" in js
    solve = _js_function(js, "function scatterSolve(region, salt, strokeKeepOut)")
    assert "if (triangles >= SCATTER_BUDGET_TRIANGLES) break;" in solve
    assert "if (placed.length >= SCATTER_MAX_ITEMS) break;" in solve
    paint = _js_function(js, "function paintScatter(solved)")
    assert "stopped at" in paint, (
        "a guard rail with no explanation reads as a broken tool")


def test_the_scatter_region_outline_cannot_steal_a_click():
    """propRecordAt raycasts propsGroup RECURSIVELY and, when a hit maps
    to no record, continues to the next hit rather than returning -- so a
    stray pickable child in that group causes a WRONG selection, not a
    clean miss. That is why the prop outline's raycast is a no-op, and
    the region outline gets the same treatment plus a home in the scene."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    show = _js_function(js, "function showScatterOutline(region)")
    assert "scene.add(scatterOutline);" in show
    assert "propsGroup.add" not in show
    assert "scatterOutline.raycast = () => {};" in show


def test_leaving_the_scatter_tab_puts_the_region_drag_down():
    """The drag listens in CAPTURE phase, because OrbitControls and the
    studio's own prop handling both bound pointerdown at boot and a later
    listener sees a press they have already acted on. A capture listener
    left behind would eat his next click on a prop."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    # The tools own the LEFT button while armed: a press paints, a drag
    # keeps painting, a release ends the stroke (Param: "i want to drag
    # the brush around"). The camera keeps middle to orbit and right to
    # pan, so the orbit is never disabled and ground a stroke needs can
    # be brought on screen without putting the tool down.
    assert 'canvas.addEventListener("pointerdown", onBrushDown);' in js
    assert 'canvas.addEventListener("pointerdown", onAreaDown);' in js
    assert "const TOOL_BUTTONS = { LEFT: null, MIDDLE: THREE.MOUSE.ROTATE," in js
    assert "controls.enabled = false;" not in _js_function(js, "function armScatterArea()"), (
        "the orbit stays live while the tool is armed")
    assert "controls.enabled = false;" not in _js_function(js, "function armScatterBrush()")
    assert "giveButtonsToTool(true);" in _js_function(js, "function armScatterBrush()")
    assert "closeShelf();" in _js_function(js, "function armScatterBrush()"), (
        "the drawer gets out of the way: the floor was under the tiles")
    assert 'if (wasArmed) openShelf("scatter");' in _js_function(js, "function disarmScatterArea()")
    disarm = _js_function(js, "function disarmScatterArea()")
    for gone in ('canvas.removeEventListener("pointerdown", onBrushDown);',
                 'canvas.removeEventListener("pointerdown", onAreaDown);',
                 'canvas.removeEventListener("pointerup", onBrushUp);',
                 'canvas.removeEventListener("pointermove", onAreaMove);',
                 "giveButtonsToTool(false);"):
        assert gone in disarm, gone
    # Opening ANOTHER drawer puts the tool down; a CLOSED shelf does not,
    # because arming the brush folds the drawer away to clear the floor
    # and the first click then re-rendered the shelf and disarmed the
    # brush it had just been asked to paint with.
    assert 'if (shelfKind && shelfKind !== "scatter" && state.scatterArmed) ' \
        'disarmScatterArea();' in js


def test_a_scattered_prop_is_an_ordinary_prop():
    """The reason the gumball, the drag, Delete, the layer eye, undo and
    the scene round trip all work on a scattered tree with no new code:
    it goes through placeProp into state.props like anything else, and
    there is no second universe of pickable things to keep in step."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    run = _js_function(js, "async function runScatter(region, options)")
    assert "placeProp(" in run
    assert "InstancedMesh" not in run
    assert "pushUndo(" in run, "one undo entry for the whole field"
    assert "saveProps();" in run
    # Templates in hand BEFORE placing, or placeProp falls back to
    # makeProp and plants a primitive instead of the model.
    assert run.index("await ensurePropTemplate") < run.index("scatterSolve(")


def test_the_fixtures_are_emitters_with_no_furniture_on_them():
    """Param: "i didnt want the orb light with a lamp end. i wanted a
    sphere light only, lamp strip where we can resize it, cube lamp ...
    resize all of these actually."

    So each one is emitter plus light and nothing else: no stem, no foot,
    no shade. The old orb-light name survives because a scene saved
    before this names it, and a type nothing recognises draws as
    nothing -- but it builds the bare sphere now."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    body = _js_function(js, "function lightEmitter(geometry, lift, faces)")
    assert "MeshBasicMaterial" in body, "the source must not be shaded"
    # The sphere keeps its PointLight, which for a sphere is exact; the
    # strip and the cube emit from their faces (2026-09-11).
    assert "new THREE.PointLight(0xffffff, 1, 0, 2)" in body
    assert "new THREE.RectAreaLight(0xffffff, 1, 1, 1)" in body
    assert body.count("light.castShadow = false;") == 2, (
        "no fixture casts a shadow, the point light or the faces")
    assert "0.25, null);" in _js_function(js, "function lightSphere()")
    assert "0.03, STRIP_FACES);" in _js_function(js, "function lightStrip()")
    assert "0.2, BOX_FACES);" in _js_function(js, "function lightCube()")
    assert 'const STRIP_FACES = ["+y", "-y", "+z", "-z"];' in js, (
        "the strip's four long faces; its end caps carry almost nothing")
    assert 'const BOX_FACES = ["+x", "-x", "+y", "-y", "+z", "-z"];' in js
    assert "propOrbLightOld" not in js, "the dead stem-and-foot builder is gone"
    assert "CylinderGeometry" not in body, "no stem and no foot"
    for maker in ("function lightSphere()", "function lightStrip()",
                  "function lightCube()"):
        assert maker in js, maker
    legacy = _js_function(js, "function propOrbLight()")
    assert "return lightSphere();" in legacy
    # Built at 3000 K, not white. applyPropLight writes the real colour
    # once one is placed, but a tile's preview never gets that call, so a
    # white emitter came out white on the pale tile and Param said he
    # could barely see it.
    assert "color: kelvinColour(LAMP_KELVIN)" in body


def test_a_fixture_emits_from_its_shape_and_every_resize_relays_it():
    """Param, 2026-09-11: "the light itself when we scale it and chnage
    the shape etc it doesnt make that objects light project from the shape
    just from a point."

    A strip and a cube carry a RectAreaLight on each face that gives
    light, laid out by fixtureFaces (fields.js, tested under node) at the
    fixture's WORLD size. Two things make that true in the page: the LTC
    tables are in place before anything renders, and every path that
    changes a fixture's shape re-lays its light."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert ('import { RectAreaLightUniformsLib } from '
            '"three/addons/lights/RectAreaLightUniformsLib.js";') in js
    init = js.index("RectAreaLightUniformsLib.init();")
    assert init < js.index("previewRig = buildPreviewRig();"), (
        "the preview renderer shares the tables, so they come first")
    assert init < js.index("function renderView()"), "before the first frame"
    guard = js[init:init + 900]
    assert "if (!THREE.UniformsLib.LTC_FLOAT_1 || !THREE.UniformsLib.LTC_HALF_1) {" in guard
    assert guard.count("reportProblem(") == 2, (
        "a failed init and a missing table are both loud")
    assert "  fixtureFaces,\n} from \"/static/fields.js\";" in js

    laid = _js_function(js, "function layFixtureEmitters(object, lumens, colour)")
    assert "fixtureFaces(half, globe.position.toArray(), object.scale.toArray()," in laid, (
        "the faces are sized from the fixture's scale as it stands now")
    assert "light.quaternion.setFromRotationMatrix(faceBasis);" in laid
    power = laid.index("light.power = lumens * face.share;")
    assert laid.index("light.width = face.width;") < power, (
        "three divides power by the area, so the size goes on first")
    assert laid.index("light.height = face.height;") < power
    sync = _js_function(js, "function syncFixtureEmission(record)")
    assert "layFixtureEmitters(record.object, lumens, kelvinColour(kelvin));" in sync

    # Every writer of a fixture's shape goes through applyPropSize, and
    # applyPropSize re-lays the light. The gumball, the keys and the undo
    # used to set a uniform scale, which also threw away a stretched
    # strip's length until the next reload.
    size = _js_function(js, "function applyPropSize(record)")
    assert "syncFixtureEmission(record);" in size
    assert "applyPropSize(record);" in _js_function(js, "function writeLightSize()")
    gumball = js[js.index("startScale * distance / startReading));"):]
    assert "applyPropSize(record);" in gumball[:300]
    undo = js[js.index('pushUndo("the adjustment", () => {'):]
    assert "applyPropSize(record);" in undo[:300]
    assert "applyPropSize(state.selectedProp);" in js, "the + and - keys"
    assert "record.object.scale.setScalar(record.scale);" not in js
    assert "record.object.scale.setScalar(before.scale);" not in js
    assert "state.selectedProp.object.scale.setScalar(" not in js


EMITTER_HARNESS = r"""
import * as THREE from %(three)s;
import { fixtureFaces } from %(fields)s;

%(consts)s

%(functions)s

function expect(condition, message) {
  if (!condition) { console.error("FAIL: " + message); process.exit(1); }
}
function near(a, b, tol) { return Math.abs(a - b) < (tol || 1e-6); }

// What three's WebGLLights and the LTC shader make of one rect light:
// the rotation of its world matrix carries width along its X and height
// along its Y, the corners are taken in the shader's own order, and
// LTC_Evaluate lights only the side cross(r1 - r0, r3 - r0) points to.
function shaded(light) {
  light.updateWorldMatrix(true, false);
  const rotation = new THREE.Matrix4().extractRotation(light.matrixWorld);
  const centre = new THREE.Vector3().setFromMatrixPosition(light.matrixWorld);
  const hw = new THREE.Vector3(light.width * 0.5, 0, 0).applyMatrix4(rotation);
  const hh = new THREE.Vector3(0, light.height * 0.5, 0).applyMatrix4(rotation);
  const r0 = centre.clone().add(hw).sub(hh);
  const r1 = centre.clone().sub(hw).sub(hh);
  const r3 = centre.clone().add(hw).add(hh);
  const normal = new THREE.Vector3().crossVectors(
    r1.clone().sub(r0), r3.clone().sub(r0)).normalize();
  return { centre, normal, hw, hh };
}

// Every rect light on a fixture, checked against the box it is laid on,
// worked out here independently of fixtureFaces.
function checkFaces(record, faces, label) {
  const object = record.object;
  object.updateWorldMatrix(true, true);
  const globe = object.children.find((child) => child.userData.lampGlobe);
  const box = globe.geometry.boundingBox;
  const half = [(box.max.x - box.min.x) / 2, (box.max.y - box.min.y) / 2,
    (box.max.z - box.min.z) / 2];
  const scale = object.scale.toArray();
  const axis = (i) => new THREE.Vector3(...[0, 1, 2].map((k) => (k === i ? 1 : 0)))
    .applyQuaternion(object.quaternion);
  const lights = object.children.filter((child) => child.isRectAreaLight);
  expect(lights.length === faces.length, label + ": one light per face");
  let power = 0;
  const radiance = [];
  lights.forEach((light, n) => {
    const sign = faces[n][0] === "-" ? -1 : 1;
    const a = "xyz".indexOf(faces[n][1]);
    const local = globe.position.clone();
    local.setComponent(a, local.getComponent(a) + sign * half[a]);
    const centre = object.localToWorld(local);
    const outward = axis(a).multiplyScalar(sign);
    const seen = shaded(light);
    expect(seen.centre.distanceTo(centre) < 1e-6,
      label + " " + faces[n] + ": the light sits on its face");
    expect(seen.normal.dot(outward) > 1 - 1e-6,
      label + " " + faces[n] + ": the light shines out of its face");
    // Width and height lie along the face's own two axes, at their size
    // in the world.
    const others = [0, 1, 2].filter((k) => k !== a);
    const extent = (k) => 2 * half[k] * Math.abs(scale[k]);
    for (const half_ of [seen.hw, seen.hh]) {
      const along = others.find((k) => Math.abs(half_.clone().normalize().dot(axis(k))) > 1 - 1e-6);
      expect(along !== undefined, label + " " + faces[n] + ": a side lies along the face");
      expect(near(2 * half_.length(), extent(along)),
        label + " " + faces[n] + ": each side at its world size");
    }
    expect(light.color.equals(kelvinColour(record.kelvin)), label + ": its colour");
    power += light.power;
    radiance.push(light.intensity);
  });
  expect(near(power, record.lumens, 1e-6 * record.lumens),
    label + ": the faces share the whole output");
  for (const r of radiance) {
    expect(near(r, radiance[0], 1e-9 * Math.max(1, radiance[0])),
      label + ": every face equally bright, so shares go by area");
  }
}

// A twelve metre strip at scale 1.5, turned and lifted, warm-white off.
const strip = { type: "light-strip", object: lightStrip(), scale: 1.5,
  size: [6, 1, 1], lumens: 4000, kelvin: 5000 };
strip.object.position.set(3, -2, 1.5);
strip.object.rotation.set(0, 0, Math.PI / 6);
applyPropSize(strip);
checkFaces(strip, STRIP_FACES, "strip");
expect(near(strip.object.children.find((c) => c.isRectAreaLight).width
  * strip.object.children.find((c) => c.isRectAreaLight).height, 18 * 0.09),
  "the +y face of a 18 m strip is 18 m by 90 mm");

// The Output dial reaches the faces through applyPropLight.
strip.lumens = 2500;
applyPropLight(strip);
checkFaces(strip, STRIP_FACES, "strip at 2500 lm");

// A cube at Size 2, tipped on all three axes.
const cube = { type: "light-cube", object: lightCube(), scale: 2,
  lumens: 900, kelvin: 2200 };
cube.object.position.set(-4, 5, 0.5);
cube.object.rotation.set(0.3, 0.2, 1.0);
applyPropSize(cube);
checkFaces(cube, BOX_FACES, "cube");

// The sphere keeps one point light, at its centre, carrying all of it.
const sphere = { type: "light-sphere", object: lightSphere(), scale: 1,
  lumens: 700, kelvin: 3000 };
applyPropLight(sphere);
const points = sphere.object.children.filter((c) => c.isLight);
expect(points.length === 1 && points[0].isPointLight, "the sphere: one point light");
expect(near(points[0].power, 700, 1e-6), "the sphere: all of its output");
console.log("ok");
"""


def _js_statement(source, head):
    """One top-level statement: its lines, up to the one whose code (its
    trailing comment set aside) ends the statement."""

    start = source.index("\n" + head) + 1
    lines = []
    for line in source[start:].split("\n"):
        lines.append(line)
        if line.split(" //")[0].rstrip().endswith(";"):
            return "\n".join(lines) + "\n"
    raise ValueError(head)


def test_a_fixtures_emitters_are_laid_on_its_faces_and_shine_out_of_them(tmp_path):
    """The real layFixtureEmitters, syncFixtureEmission, applyPropSize and
    applyPropLight, run under node on vendored three: every face light of a
    turned, stretched strip and a tipped cube sits on its face, shines out
    of it by the LTC shader's own test, is its face's world size, wears the
    fixture's colour, and the faces share the fixture's own output by area.
    Source pins alone let the basis, the positions and the output go wrong
    with every fixture test green."""

    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    js = STUDIO_JS.read_text(encoding="utf-8")
    static = REPO / "bench" / "studio" / "static"
    consts = "\n".join(_js_statement(js, head) for head in (
        "const LAMP_LUMENS", "const LAMP_KELVIN", "const KELVIN_MIN",
        "const STRIP_FACES", "const BOX_FACES", "const LAMP_TYPES",
        "const faceAxes", "const faceBasis"))
    headers = ("function kelvinColour(kelvin)", "function isLamp(record)",
               "function lightEmitter(geometry, lift, faces)",
               "function layFixtureEmitters(object, lumens, colour)",
               "function syncFixtureEmission(record)",
               "function lightSphere()", "function lightStrip()",
               "function lightCube()", "function applyPropSize(record)",
               "function applyPropLight(record)")
    functions = "\n\n".join(_js_whole_function(js, header) for header in headers)
    script = tmp_path / "emitters.mjs"
    script.write_text(EMITTER_HARNESS % {
        "three": json.dumps((static / "vendor" / "three.module.js").as_uri()),
        "fields": json.dumps((static / "fields.js").as_uri()),
        "consts": consts, "functions": functions}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.strip() == "ok"


ROLL_HARNESS = r"""
import * as THREE from %(three)s;
const problems = [];
function reportProblem(message) { problems.push(message); }

%(regex)s

%(roll)s

const before = THREE.ShaderChunk.lights_fragment_begin;
const chunks = { lights_fragment_begin: before };
const rolled = rollRectAreaLoop(chunks);
const problemsAfterFirst = problems.length;
const again = rollRectAreaLoop({ lights_fragment_begin: chunks.lights_fragment_begin });
console.log(JSON.stringify({ rolled, problemsAfterFirst, again,
  problems: problems.length, before, after: chunks.lights_fragment_begin }));
"""


def test_the_rect_light_loop_is_rolled_so_a_strip_does_not_freeze_the_page(tmp_path):
    """Three unrolls its rect-light loop, so each strip put four more copies
    of the area-light shading into every lit program, and the fifth strip
    froze the page for ten seconds while they all recompiled. The loop is
    rolled on the vendored chunk at boot: only that loop loses its pragmas,
    nothing else in the chunk moves, and a chunk that no longer matches is
    reported rather than left to stall. Run on the real vendored chunk."""

    import json
    import shutil
    import subprocess

    js = STUDIO_JS.read_text(encoding="utf-8")
    call = js.index("\nrollRectAreaLoop(THREE.ShaderChunk);\n")
    assert call < js.index("previewRig = buildPreviewRig();"), (
        "rolled before either renderer builds a program")
    assert call < js.index("RectAreaLightUniformsLib.init();") + 2000

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    static = REPO / "bench" / "studio" / "static"
    script = tmp_path / "roll.mjs"
    script.write_text(ROLL_HARNESS % {
        "three": json.dumps((static / "vendor" / "three.module.js").as_uri()),
        "regex": _js_statement(js, "const RECT_AREA_UNROLLED"),
        "roll": _js_whole_function(js, "function rollRectAreaLoop(chunks)")},
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["rolled"] is True and out["problemsAfterFirst"] == 0
    before, after = out["before"], out["after"]
    loop = "for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {"
    segment = after[after.index("RectAreaLight rectAreaLight;"):after.index(loop) + 400]
    assert "#pragma" not in segment.split("#endif")[0], "the rect loop is plain"
    assert after.count("#pragma unroll_loop_start") == before.count("#pragma unroll_loop_start") - 1
    assert after.count("#pragma unroll_loop_end") == before.count("#pragma unroll_loop_end") - 1
    tail = "#endif\n#if defined( RE_IndirectDiffuse )"
    expected = before.replace("#pragma unroll_loop_start\n\t" + loop, loop, 1).replace(
        "\t}\n\t#pragma unroll_loop_end\n" + tail, "\t}\n" + tail, 1)
    assert expected != before, "the vendored chunk still has the unrolled rect loop"
    assert after == expected, "only the two pragmas round the rect loop go"
    assert out["again"] is False and out["problems"] == 1, (
        "a chunk the patch no longer fits is reported, not passed over")


def test_undoing_a_delete_brings_a_fixture_back_as_it_was():
    """Delete a twelve metre strip at 6000 lm, undo, and it came back a
    two metre strip at whatever the Lights sliders said: the undo carried
    neither the size nor the fixture's own two numbers."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    block = js[js.index('} else if (event.key === "Delete" || event.key === "Backspace") {'):]
    gone = block[:block.index("pushUndo(")]
    assert "size: Array.isArray(record.size) ? record.size.slice() : null," in gone
    assert "lumens: record.lumens, kelvin: record.kelvin };" in gone
    undo = block[block.index("pushUndo("):block.index("removePropRecord(record);")]
    placed = undo.index("const again = placeProp(")
    assert placed < undo.index("again.size = gone.size.slice();")
    assert undo.index("again.size = gone.size.slice();") < undo.index("applyPropSize(again);")
    assert placed < undo.index("adoptLampSettings(again, gone);"), (
        "placeProp lights it from the sliders; the fixture's own numbers go on after")


def test_a_fixture_can_be_stretched_along_one_axis_and_it_survives():
    """A strip whose thickness followed its length would just be a bigger
    strip, which is not resizing it. And a size that did not persist
    would be a control that quietly forgot."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    size = _js_function(js, "function applyPropSize(record)")
    assert "record.object.scale.set(" in size
    write = _js_function(js, "function writeLightSize()")
    assert "record.size = [along, 1, 1];" in write, (
        "only the long axis moves")
    assert "applyPropSize(record);" in write
    # Saved both ways, and read back both ways.
    # One encoder for both memories carries it beside the row, and one
    # decoder hands it back to both readers.
    assert "if (p.size || p.lumens !== undefined || p.kelvin !== undefined) {" in js
    assert "const extra = extras[entries.length];" in js
    assert js.count("record.size = entry.size.map(Number);") == 2, (
        "the layout restore and the scene restore both read it")


def test_the_scatter_brush_thickens_rather_than_repeating_itself():
    """Param: "clicking multiple times over an already scattered space
    increases its density still trying to avoid collision".

    Avoiding collision is free: scatterKeepOut already reads every placed
    prop as a keep-out disc. What was NOT free is dealing different
    points on the second click. Without a fresh deal the same arrangement
    comes back, every point lands on a prop that is now a keep-out, every
    one is refused, and the field simply stops thickening."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    solve = _js_function(js, "function scatterSolve(region, salt, strokeKeepOut)")
    assert "Math.imul(salt || 0, 0x9E3779B1)" in solve
    # The fill happens on pointerUP, and only when the press did not
    # travel: that is what tells a click from an orbit drag.
    # Every STAMP of a stroke deals a fresh salt, so a stroke dragged back
    # over itself thickens rather than repeating.
    stamp = _js_function(js, "function stampBrush(hit)")
    assert "state.scatterStroke += 1;" in stamp
    assert "const stamp = { region: brushRegion(), salt: state.scatterStroke };" in stamp
    # One layer for a painting session, not one per stamp.
    assert "intoLayer: state.scatterBrushLayer, stroke });" in stamp
    keep = _js_function(js, "function scatterKeepOut(clearance, spacing)")
    assert "for (const record of state.props) {" in keep


def test_the_keep_out_hugs_the_works_and_reads_the_spacing_dial():
    """Two reasons a stroke placed almost nothing. The vault kept out by
    ONE disc of half its diagonal, a 12 m circle round a 23 m by 4 m
    vault, so nothing could stand along either long side. And a placed
    prop kept out by a fixed 0.6 of its footprint, blind to the spacing
    dial and to its own scale, so a second stroke could never touch a
    first however low the dial went. The works are a capsule now, discs
    the width of the short side stepped along the long one, and a prop
    keeps out by its own size at the current spacing."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    keep = _js_function(js, "function scatterKeepOut(clearance, spacing)")
    assert "const r = short / 2 + clearance;" in keep
    assert "const steps = Math.max(1, Math.ceil((long - short) / Math.max(0.5, short / 2)));" in keep
    assert "propFootprint(record.type) * (record.scale || 1) * gap" in keep
    assert "* 0.6" not in keep
    solve = _js_function(js, "function scatterSolve(region, salt, strokeKeepOut)")
    assert "scatterKeepOut(rules.clearance, rules.spacing)" in solve


def test_the_keep_out_is_a_grid_and_not_a_list():
    """Every dart walked EVERY disc, and a dart-throwing fill throws far
    more darts than it lands: with 25,000 props down, a 4,000-dart stamp
    was a hundred million distance tests and the brush felt glued to the
    floor. A disc is filed in every grid cell it overlaps and a dart asks
    only the cells its own disc overlaps, so the answer is exact whatever
    the sizes, and a disc filed in several cells is tested once."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const KEEP_OUT_CELL = 1;   // metres" in js
    assert "function clearOf(" not in js
    add = _js_function(js, "function keepOutAdd(index, x, y, r)")
    assert "if (bucket) bucket.push(id); else index.cells.set(key, [id]);" in add
    clear = _js_function(js, "function keepOutClear(index, x, y, radius)")
    assert "if (index.seen[id] === pass) continue;" in clear
    assert "if (dx * dx + dy * dy < reach * reach) return false;" in clear
    solve = _js_function(js, "function scatterSolve(region, salt, strokeKeepOut)")
    assert "if (!keepOutClear(keepOut, x, y, radius)) { refused += 1; continue; }" in solve
    assert "keepOutAdd(keepOut, x, y, radius);" in solve


def test_the_brush_is_a_stroke_and_the_stroke_is_one_undo():
    """Param, the morning after click-to-place: "the double click is
    wrong because i want to drag the brush around etc. so lets stick with
    left click and have right click still to pan and scroll to zoom".

    A press stamps, a drag stamps again every half radius, a release ends
    the stroke, and the WHOLE stroke is one undo entry: forty entries for
    one sweep would make the Undo button a lottery. Stamps queue behind
    each other, because a stamp awaits its templates and two at once
    would both mint a layer."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const BRUSH_STEP = 0.5;" in js
    move = _js_function(js, "function onBrushMove(event)")
    assert "if (Math.hypot(hit.x - brushStroke.last.x, hit.y - brushStroke.last.y) >= step) {" in move
    stamp = _js_function(js, "function stampBrush(hit)")
    assert "stroke.busy = scatterQueue = scatterQueue.then(async () => {" in stamp
    up = _js_function(js, "async function onBrushUp(event)")
    assert "await stroke.busy;" in up
    assert "endBrushStroke(stroke);" in up
    end = _js_function(js, "function endBrushStroke(stroke)")
    assert 'pushUndo("painting " + records.length + " props", () => {' in end
    run = _js_function(js, "async function runScatter(region, options)")
    assert "if (settings.stroke) {" in run
    assert "stroke.run = { layer: home.id, records: stroke.records };" in run
    # The area's release is the pointer that pressed, the same way (the
    # rest of the area is test_the_area_stays_in_hand_and_a_click_fills_it_again).
    area = _js_function(js, "function onAreaUp(event)")
    assert "if (!press || event.pointerId !== press.pointerId) return;" in area


def test_the_area_stays_in_hand_and_a_click_fills_it_again():
    """Param, once the brush worked: "i drag the area it spawns one lot
    the block rectangle still stays and if i keep clicking it continues
    adding objects, then if i click and drag on a new area i can continue
    placing up until i press esc. make sure the click and drag has enough
    of a false start so it doesnt make the rectangles too easily, say a
    click and a drag has to drag for more than 10px before it activates".

    Twelve pixels for a mouse or a pen, twice that for a fingertip; a
    press that stays inside it is a click, and a click fills the
    rectangle on the floor again with a fresh deal."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const AREA_DRAG_PX = 12;" in js
    assert "const AREA_DRAG_PX_TOUCH = 24;" in js
    down = _js_function(js, "function onAreaDown(event)")
    assert 'slop: event.pointerType === "touch" ? AREA_DRAG_PX_TOUCH : AREA_DRAG_PX };' in down
    move = _js_function(js, "function onAreaMove(event)")
    assert "if (travelled <= press.slop) return;" in move
    assert move.index("if (travelled <= press.slop) return;") < move.index(
        "scatterDrag = {"), "no rectangle until the false start is past"
    up = _js_function(js, "function onAreaUp(event)")
    assert "disarmScatterArea" not in up, "the tool stays in hand until Escape"
    assert "} else if (!scatterDrag) {" in up, "a click with no rectangle yet says so"
    assert "  fillScatterArea();" in up
    fill = _js_function(js, "function fillScatterArea()")
    assert "const salt = state.scatterStroke;" in fill, "every fill deals afresh"
    assert "await runScatter(region, { salt, intoLayer: state.scatterBrushLayer });" in fill, (
        "one layer for the session, not one per fill")
    assert "scatterQueue = scatterQueue.then(async () => {" in fill


def test_every_placement_lands_on_the_open_layer():
    """Param: "in layers the scatters i do should land in the layer thats
    active not create a new one, same with lights etc. As well when I undo
    it doesnt always remove the scatter layer even though the objects are
    gone."

    A scatter minted "Scatter N" and then made it the open layer, so every
    fixture and prop placed after it landed there too, and no undo entry
    knew the layer had been made. Now every placement goes through
    placementLayer(): the open layer, shown if hidden, and a layer is made
    only when there is none, owned by the entry of the action that made it.
    A redo names its layer outright, so a replay can neither mint a second
    layer nor land on whatever is open by then."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    run = _js_function(js, "async function runScatter(region, options)")
    assert "placementLayer()" in run
    assert 'newLayer("Scatter "' not in run, "a scatter never mints its own layer"
    assert "state.activeLayer = home.id;" not in run, (
        "a placement never changes which layer is open")
    assert "record.layer = home.id;" in run, "a redo aimed at another layer re-stamps"
    fill = run[run.index('pushUndo("scattering "'):]
    assert "at = dropLayerIfEmpty(owns);" in fill
    assert "if (owns && at >= 0) reinstateLayer(owns, at);" in fill
    assert "Object.assign({}, settings, { intoLayer: home.id, owns })" in fill, (
        "the fill's redo names its layer, never the first fill's null")
    end = _js_function(js, "function endBrushStroke(stroke)")
    assert "at = dropLayerIfEmpty(owns);" in end
    assert "if (owns && at >= 0) reinstateLayer(owns, at);" in end
    assert "let layer = null;" not in end, "a stroke's redo starts from its own layer"
    assert "intoLayer: homeId," in end
    for header in ("function armScatterBrush()", "function armScatterArea()"):
        assert "state.scatterBrushLayer = placementLayer().layer.id;" in _js_function(js, header)
    assert "placementLayer();" in _js_function(js, "function carryNewProp(type)"), (
        "a fixture or prop from a tile lands on the open layer, shown if hidden")
    remove_last = js[js.index('getElementById("scatter-undo-last").addEventListener'):][:700]
    assert "dropLayerIfEmpty(run.minted);" in remove_last
    assert "again.layer = layerById(gone.layer) ? gone.layer : state.activeLayer;" in js, (
        "an undone delete never lands on a layer with no tab")
    group = _js_function(js, "function groupToNewLayer(again)")
    assert 'pushUndo("grouping " + chosen.length + " props", () => {' in group
    assert "at = dropLayerIfEmpty(home);" in group
    assert "() => groupToNewLayer({ chosen, home, at, openBefore })" in group
    # Say where things go.
    paint = _js_function(js, "function paintScatter(solved)")
    assert '"  --  brush it on, or drag an area, onto " + placingOntoName()' in paint
    assert '" placed onto "' in paint
    assert '"press and drag to paint onto " + placingOntoName()' in _js_function(
        js, "function armScatterBrush()")
    assert '"drag a rectangle to fill it onto " + placingOntoName()' in _js_function(
        js, "function armScatterArea()")
    assert '"; new fixtures go onto " + placingOntoName()' in _js_function(
        js, "function syncLightControls()")


def _js_whole_function(source, header):
    """One column-0 function, from its header to its own closing brace."""

    start = source.index(header)
    return source[start:source.index("\n}", start) + 2]


LAYER_STUBS = r"""
const logs = [];
const undo = [];
const state = {
  propLayers: [{ id: 1, name: "Layer 1", visible: true },
    { id: 2, name: "Layer 2", visible: true }],
  activeLayer: 2, nextLayerId: 3, props: [], scatterRuns: [],
  scatter: { species: [{ type: "tuft", weight: 1 }] },
};
const gatheredProps = new Set();
const document = { getElementById: () => ({ textContent: "", disabled: false }) };
function applyLayerVisibility() {}
function saveProps() {}
function renderShelf() {}
function refreshLayersShelf() {}
function paintScatter() {}
function logStudio(message) { logs.push(message); }
function pushUndo(label, undo_, redo) { undo.push({ label, undo: undo_, redo }); }
function familyMembers() { return []; }
async function ensurePropTemplate() {}
function scatterSolve(region, salt) {
  return { items: [{ type: "tuft", x: salt, y: 0, rotation: 0, scale: 1 },
    { type: "tuft", x: salt, y: 1, rotation: 0, scale: 1 }], keepOut: null, triangles: 0 };
}
// placeProp's own rule, the one that matters here: the open layer.
function placeProp(type, x, y, rotation, save, scale) {
  const record = { type, x, y, layer: state.activeLayer,
    object: { visible: layerVisible(state.activeLayer) } };
  state.props.push(record);
  return record;
}
function removePropRecords(records) {
  const gone = new Set(records);
  state.props = state.props.filter((p) => !gone.has(p));
}
%(functions)s
const ids = () => state.propLayers.map((l) => l.id);
const on = () => [...new Set(state.props.map((p) => p.layer))];
"""


LAYER_HARNESS = LAYER_STUBS + r"""
const out = {};
const region = { kind: "rect", x0: 0, y0: 0, x1: 4, y1: 4 };
(async () => {
  // Two fills with Layer 2 open, as an armed area tool makes them.
  await runScatter(region, { salt: 1, intoLayer: placementLayer().layer.id });
  await runScatter(region, { salt: 2, intoLayer: 2 });
  out.filled = { layers: ids(), open: state.activeLayer, on: on(), props: state.props.length };
  // He opens Layer 1, then undoes both fills and redoes both.
  state.activeLayer = 1;
  const second = undo.pop(), first = undo.pop();
  await second.undo(); await first.undo();
  out.undone = { layers: ids(), props: state.props.length };
  await first.redo(); await second.redo();
  out.redone = { layers: ids(), open: state.activeLayer, on: on(), props: state.props.length };
  // A hidden open layer is shown by the placement, and the log says so.
  state.props = []; undo.length = 0;
  state.propLayers[0].visible = false;
  await runScatter(region, { salt: 3 });
  out.hidden = { shown: state.propLayers[0].visible, on: on(),
    visible: state.props.every((p) => p.object.visible), said: logs.join("|") };
  // With no layer at all one is made; its undo takes it away once there is
  // another, and its redo brings the SAME one back, twice over.
  state.props = []; undo.length = 0;
  state.propLayers = []; state.activeLayer = 7; state.nextLayerId = 5;
  await runScatter(region, { salt: 4 });
  const made = state.propLayers[0];
  newLayer(null);
  let entry = undo.pop();
  await entry.undo();
  out.minted = { made: made.id, afterUndo: ids(), open: state.activeLayer };
  await entry.redo();
  out.minted.afterRedo = ids();
  out.minted.on = on();
  entry = undo.pop();
  await entry.undo();
  out.minted.afterSecondUndo = ids();
  // Group is one entry: undo puts them back and takes the layer away,
  // redo brings the same layer back in the same place.
  state.propLayers = [{ id: 1, name: "Layer 1", visible: true },
    { id: 2, name: "Layer 2", visible: true }];
  state.activeLayer = 1; state.nextLayerId = 3; undo.length = 0;
  const a = { layer: 1, object: {} }, b = { layer: 2, object: {} };
  state.props = [a, b];
  gatheredProps.add(a); gatheredProps.add(b);
  groupToNewLayer();
  out.grouped = { a: a.layer, b: b.layer, layers: ids(), open: state.activeLayer,
    entries: undo.length };
  entry = undo.pop();
  entry.undo();
  out.ungrouped = { a: a.layer, b: b.layer, layers: ids(), open: state.activeLayer };
  entry.redo();
  out.regrouped = { a: a.layer, b: b.layer, layers: ids(), open: state.activeLayer,
    entries: undo.length };
  console.log(JSON.stringify(out));
})().catch((error) => { console.error(error.stack); process.exit(1); });
"""


def test_scatter_undo_redo_and_group_keep_the_layer_list_honest(tmp_path):
    """The layer functions and runScatter themselves, run under node with
    the scene stubbed out: two fills onto the open Layer 2 add no layer;
    undoing both after opening Layer 1 leaves the list as it was, and
    redoing both puts them back on Layer 2, not on the open one. A hidden
    open layer is shown by the placement. A layer made because there was
    none is taken away by the undo and brought back, same id, by the redo,
    however many times. Group undoes and redoes as one entry."""

    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    js = STUDIO_JS.read_text(encoding="utf-8")
    headers = ("function layerById(id)", "function layerVisible(id)",
               "function newLayer(name)", "function placementLayer()",
               "function showLayerForPlacing(layer)", "function placingOntoName()",
               "function dropLayerIfEmpty(layer)", "function reinstateLayer(layer, index)",
               "function groupToNewLayer(again)",
               "async function runScatter(region, options)")
    functions = "\n\n".join(_js_whole_function(js, header) for header in headers)
    script = tmp_path / "layers.mjs"
    script.write_text(LAYER_HARNESS % {"functions": functions}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["filled"] == {"layers": [1, 2], "open": 2, "on": [2], "props": 4}
    assert out["undone"] == {"layers": [1, 2], "props": 0}
    assert out["redone"] == {"layers": [1, 2], "open": 1, "on": [2], "props": 4}
    assert out["hidden"]["shown"] is True and out["hidden"]["on"] == [1]
    assert out["hidden"]["visible"] is True
    assert "Layer 1 was hidden, so it is shown again" in out["hidden"]["said"]
    assert out["minted"] == {"made": 5, "afterUndo": [6], "open": 6,
                             "afterRedo": [5, 6], "on": [5], "afterSecondUndo": [6]}
    assert out["grouped"] == {"a": 3, "b": 3, "layers": [1, 2, 3], "open": 3, "entries": 1}
    assert out["ungrouped"] == {"a": 1, "b": 2, "layers": [1, 2], "open": 1}
    assert out["regrouped"] == {"a": 3, "b": 3, "layers": [1, 2, 3], "open": 3, "entries": 1}


LAYER_GUARD_HARNESS = LAYER_STUBS + r"""
let stampRig = null;
const controls = { enabled: true };
function selectProp() {}
function closeShelf() {}
function spawnStampInstance() {}
const L = (id, visible = true) => ({ id, name: "Layer " + id, visible });
function reset(layers, open) {
  state.propLayers = layers; state.activeLayer = open;
  state.nextLayerId = 1 + Math.max(0, ...layers.map((l) => l.id));
  state.props = []; state.scatterRuns = []; undo.length = 0; logs.length = 0;
  gatheredProps.clear();
}
const said = (text) => logs.some((line) => line.includes(text));
const out = {};
const region = { kind: "rect", x0: 0, y0: 0, x1: 4, y1: 4 };
(async () => {
  // Undoing a Group never takes away a layer something has moved onto since.
  reset([L(1), L(2)], 1);
  const a = { layer: 1, object: {} }, b = { layer: 2, object: {} }, c = { layer: 1, object: {} };
  state.props = [a, b, c];
  gatheredProps.add(a); gatheredProps.add(b);
  groupToNewLayer();
  c.layer = 3;
  undo.pop().undo();
  out.occupied = { layers: ids(), a: a.layer, b: b.layer, c: c.layer };
  // Nor the last layer there is.
  reset([], 7); state.nextLayerId = 5;
  await runScatter(region, { salt: 1 });
  undo.pop().undo();
  out.last = { layers: ids(), open: state.activeLayer };
  // A dropped layer that was open hands the open tab to one that lives.
  reset([], 7); state.nextLayerId = 5;
  await runScatter(region, { salt: 2 });
  newLayer(null);
  state.activeLayer = 5;
  undo.pop().undo();
  out.fallback = { layers: ids(), open: state.activeLayer };
  // A fixture from a tile onto a hidden open layer: shown, and said.
  reset([L(1), L(2, false)], 2);
  state.bundle = {}; state.centre = { x: 0, y: 0 };
  carryNewProp("light-sphere");
  out.carry = { layers: ids(), layer: state.carrying.record.layer,
    shown: state.propLayers[1].visible, seen: state.carrying.record.object.visible,
    said: said("Layer 2 was hidden, so it is shown again") };
  // A stamp onto a hidden open layer, the same.
  reset([L(1), L(2, false)], 2);
  const s = { layer: 1, x: 0, y: 0, rotation: 0, scale: 1, object: {} };
  state.props = [s]; gatheredProps.add(s);
  beginStamp();
  out.stamp = { shown: state.propLayers[1].visible,
    said: said("Layer 2 was hidden, so it is shown again") };
  // The readouts name the OPEN layer, not the first.
  reset([L(1), L(2)], 2);
  out.naming = [placingOntoName()];
  state.activeLayer = 9; out.naming.push(placingOntoName());
  reset([], 9); out.naming.push(placingOntoName());
  // A layer hidden while the area tool is armed is shown by the fill.
  reset([L(1), L(2)], 2);
  state.propLayers[1].visible = false;
  await runScatter(region, { salt: 3, intoLayer: 2 });
  out.armedHidden = { shown: state.propLayers[1].visible, on: on(),
    visible: state.props.every((p) => p.object.visible),
    said: said("Layer 2 was hidden, so it is shown again") };
  // A redo onto the shown Layer 2 while the open Layer 1 is hidden: the
  // props come back seen, and Layer 1 is left as he set it.
  reset([L(1), L(2)], 2);
  await runScatter(region, { salt: 4, intoLayer: 2 });
  let entry = undo.pop();
  entry.undo();
  state.activeLayer = 1; state.propLayers[0].visible = false;
  await entry.redo();
  out.redoSeen = { on: on(), props: state.props.length,
    visible: state.props.every((p) => p.object.visible),
    layer1: state.propLayers[0].visible, open: state.activeLayer };
  // Group from the open Layer 2: its undo reopens Layer 2, not the first.
  reset([L(1), L(2)], 2);
  const d = { layer: 2, object: {} }, e = { layer: 2, object: {} };
  state.props = [d, e]; gatheredProps.add(d); gatheredProps.add(e);
  groupToNewLayer();
  undo.pop().undo();
  out.groupOpen = { layers: ids(), open: state.activeLayer, d: d.layer, e: e.layer };
  // reinstateLayer never doubles an id, and the counter only climbs.
  reset([L(1), L(2)], 1);
  reinstateLayer({ id: 2, name: "Other", visible: true }, 0);
  out.duplicate = { layers: ids(), names: state.propLayers.map((l) => l.name) };
  reinstateLayer(L(7), 1);
  out.counter = { layers: ids(), next: state.nextLayerId };
  // A stroke that made its layer owns it through every redo, so the undo
  // after a redo takes it away again.
  reset([], 7); state.nextLayerId = 5;
  const stroke = { records: [], stamps: [], run: null, keepOut: null,
    busy: Promise.resolve() };
  for (const salt of [5, 6]) {
    const stamp = { region, salt };
    stroke.stamps.push(stamp);
    await runScatter(region, { salt, stroke });
  }
  endBrushStroke(stroke);
  newLayer(null);
  entry = undo.pop();
  entry.undo();
  out.stroke = { afterUndo: ids() };
  await entry.redo();
  out.stroke.afterRedo = ids();
  out.stroke.on = on();
  undo.pop().undo();
  out.stroke.afterSecondUndo = ids();
  console.log(JSON.stringify(out));
})().catch((error) => { console.error(error.stack); process.exit(1); });
"""


def test_the_layer_guards_hold_through_undo_redo_and_every_placement(tmp_path):
    """The guards the layer list stands on, each run for real under node:
    an undo never takes away a layer that still holds a prop, nor the last
    layer; a dropped open layer hands the open tab on; a fixture from a
    tile, a stamp and an armed fill each show a hidden layer they place
    onto and say so; the readouts name the open layer; a redo re-stamps
    visibility from its own layer, not the open one; Group's undo reopens
    the layer that was open; reinstateLayer never doubles an id and its
    counter only climbs; a stroke owns the layer it made through a redo."""

    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    js = STUDIO_JS.read_text(encoding="utf-8")
    headers = ("function layerById(id)", "function layerVisible(id)",
               "function newLayer(name)", "function placementLayer()",
               "function showLayerForPlacing(layer)", "function placingOntoName()",
               "function dropLayerIfEmpty(layer)", "function reinstateLayer(layer, index)",
               "function groupToNewLayer(again)",
               "async function runScatter(region, options)",
               "function carryNewProp(type)", "function beginStamp()",
               "function endBrushStroke(stroke)")
    functions = "\n\n".join(_js_whole_function(js, header) for header in headers)
    script = tmp_path / "guards.mjs"
    script.write_text(LAYER_GUARD_HARNESS % {"functions": functions}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["occupied"] == {"layers": [1, 2, 3], "a": 1, "b": 2, "c": 3}, (
        "a layer that still holds a prop stays")
    assert out["last"] == {"layers": [5], "open": 5}, "the last layer stays"
    assert out["fallback"] == {"layers": [6], "open": 6}
    assert out["carry"] == {"layers": [1, 2], "layer": 2, "shown": True, "seen": True,
                            "said": True}
    assert out["stamp"] == {"shown": True, "said": True}
    assert out["naming"] == ["Layer 2", "Layer 1", "a new layer"]
    assert out["armedHidden"] == {"shown": True, "on": [2], "visible": True, "said": True}
    assert out["redoSeen"] == {"on": [2], "props": 2, "visible": True, "layer1": False,
                               "open": 1}
    assert out["groupOpen"] == {"layers": [1, 2], "open": 2, "d": 2, "e": 2}
    assert out["duplicate"] == {"layers": [1, 2], "names": ["Layer 1", "Layer 2"]}
    assert out["counter"] == {"layers": [1, 7, 2], "next": 8}
    assert out["stroke"] == {"afterUndo": [6], "afterRedo": [5, 6], "on": [5],
                             "afterSecondUndo": [6]}


def test_one_escape_leaves_the_tool_and_brings_the_drawer_back():
    """The window's general Escape handler closes whatever drawer is
    open. The tool's own Escape reopens the drawer it folded away, so if
    both saw the same press the drawer would open and close again in one
    keystroke. The tool's handler is in the capture phase and stops the
    event immediately; the general one never sees it."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    key = _js_function(js, "function onScatterKey(event)")
    assert "event.stopImmediatePropagation();" in key
    assert "disarmScatterArea();" in key
    assert 'window.addEventListener("keydown", onScatterKey, true);' in js
    assert 'if (event.key === "Escape" && shelfKind) {' in js, (
        "the general handler this must beat")
    # And a placed prop tells the shadow fit it has arrived. The call sat
    # after the return for a while, so no prop ever did.
    place = _js_function(js, "function placeProp(type, x, y, rotation, save, scale = 1, z = 0,")
    assert "noteCastersChanged();" in place
    assert place.index("noteCastersChanged();") < place.index("return record;")


def test_a_library_prop_is_one_instance_of_its_variants_batch():
    """25,375 scattered props were 25,375 cloned groups: 48,078 draw calls
    a frame, one core flat out, the 4090 at 6% and the viewport at 2 fps
    (Param's readout). A library prop is one instance of its variant's
    batch now. The record is untouched and record.object is still an
    Object3D every existing writer moves, so the gumball, the carry, the
    stamp, the layer eye and every undo work on it unchanged: it is a
    PROXY outside the scene graph, and once a frame the batches follow
    whatever the proxies say."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    place = _js_function(js, "function placeProp(type, x, y, rotation, save, scale = 1, z = 0,")
    assert "const object = template ? propInstance(type, template) : makeProp(type);" in place
    assert "if (!object.instancedIn) propsGroup.add(object);" in place
    assert "if (object.instancedIn) object.record = record;" in place
    proxy = _js_function(js, "function propInstance(type, template)")
    # Its world matrix carries the floor's drop, and Box3 can measure it,
    # without the renderer ever walking it.
    assert "proxy.parent = propsGroup;" in proxy
    assert "proxy.geometry = batch.bounds;" in proxy
    assert "propsGroup.add" not in proxy
    dispose = _js_function(js, "function disposeProp(object)")
    assert "if (object.instancedIn) { leaveBatch(object); return; }" in dispose
    leave = _js_function(js, "function leaveBatch(proxy)")
    assert "batch.proxies[proxy.batchIndex] = last;" in leave, (
        "swapped with the last, so taking a stroke away is not quadratic")
    view = _js_function(js, "function renderView()")
    assert view.index("settlePropInstances();") < view.index(
        "if (shadowFitPending) fitSunShadow();"), (
        "the shadow fit measures the batches, so they are settled first")
    pick = _js_function(js, "function propRecordAt(event)")
    assert "const mine = hit.object.propSlots[hit.instanceId];" in pick
    moved = _js_function(js, "function proxyMoved(proxy)")
    assert "seen[10] === shown) return false;" in moved, (
        "a hidden layer is a change the batch must hear about")
    fill = _js_function(js, "function fillBatch(batch, reach, height)")
    assert "if (!batch.casts) {" in fill, (
        "a tree behind the camera still throws its shadow across the frame")
    assert "tier.slots[tier.count] = proxy.record;" in fill
    size = _js_function(js, "function sizeTier(tier, needed)")
    assert "mesh.instanceMatrix = places;" in size
    assert "mesh.frustumCulled = false;" in size
    settle = _js_function(js, "function settlePropInstances()")
    assert "const reach = state.recording ? 0" in settle, (
        "a still and a take render every prop at full detail")
    swap = js[js.index("Every template belongs to the old folder."):]
    assert "retirePropBatches();" in swap[:swap.index("await loadPropLibrary();")]


def test_the_far_tiers_borrow_the_near_materials_and_the_viewport_picks_the_detail():
    """A sidecar is bare geometry (tools/props/lod.mjs), so a far tier is
    drawn with the near tier's own materials, mesh for mesh, and one
    whose meshes do not line up is not drawn at all rather than drawn
    wrong. The fetch QUANTISES positions, which a clone kept and a bake
    would have written floats back into, so the bake widens them first."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    bake = _js_function(js, "function bakeTier(root, borrow)")
    assert "const from = borrow ? borrow[parts.length] : child;" in bake
    assert bake.index("floatAttributes(geometry);") < bake.index(
        "geometry.applyMatrix4(child.matrixWorld);")
    lods = _js_function(js, "function loadPropLods(batch, entry, template)")
    assert "if (meshes !== near.length) return;" in lods
    assert "side.rotation.copy(model.rotation);" in lods
    assert "const PROP_TIER_PIXELS = [48, 14];" in js
    assert "const DETAIL_REACH = { draft: 2.5, balanced: 1, full: 0 };" in js
    fill = _js_function(js, "function fillBatch(batch, reach, height)")
    assert "if (pixels < PROP_TIER_PIXELS[1] * reach) t = 2;" in fill
    assert "while (t > 0 && !tiers[t]) t -= 1;" in fill, (
        "a tier still loading falls back to the nearer one, never to nothing")
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="prop-detail"' in html and 'id="prop-detail-segments"' in html
    assert 'buildSegmented("prop-detail-segments", "prop-detail");' in js


def test_the_layout_is_rows_and_a_full_store_cannot_break_an_undo():
    """Param's log: "could not undo scattering 1846 props: Failed to
    execute 'setItem' on 'Storage': ... exceeded the quota". A layout was
    two hundred bytes a prop and written whole on every gesture, and an
    undone stroke wrote it once for EVERY prop it took away, so the throw
    came out of the undo. Now: nine numbers a prop, one write after the
    gestures stop, a marker instead of a throw when it will not fit, a
    copy on the server that always fits, and one removal for a stroke."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    encode = _js_function(js, "function encodeProps(props)")
    assert ("rows.push(t, roundMm(p.x), roundMm(p.y), roundMm(p.z || 0), "
            "roundTurn(p.rotation),") in encode
    decode = _js_function(js, "function decodeProps(block)")
    assert "if (Array.isArray(block)) return block;" in decode, (
        "every layout and scene written before still opens")
    save = _js_function(js, "function saveProps()")
    assert "key: propsKey()," in save, "where it goes is taken when asked"
    assert "timer: setTimeout(flushProps, LAYOUT_SETTLE_MS)," in save
    flush = _js_function(js, "function flushProps()")
    assert "localStorage.setItem(pending.key, text);" in flush
    assert ("localStorage.setItem(pending.key, JSON.stringify({ saved: layout.saved, "
            "onServer: true }));") in flush
    assert "putLayout(pending.export, text);" in flush
    restore = _js_function(js, "function restoreProps(given)")
    assert restore.index("flushProps();") < restore.index("localStorage.getItem"), (
        "a waiting write would otherwise be overtaken by the read")
    remove = _js_function(js, "function removePropRecords(records)")
    assert "state.props = state.props.filter((p) => !gone.has(p));" in remove
    assert remove.count("saveProps();") == 1
    run = _js_function(js, "async function runScatter(region, options)")
    assert "removePropRecords(records);" in run
    session = _js_function(js, "function sessionScene()")
    assert "return collectScene({ props: false });" in session, (
        "the session reopens the view; the layout brings the props")


def test_the_review_of_the_batched_field_held():
    """An adversarial review of the batched field confirmed ten faults,
    each with a scenario; each fix is held here.

    The section plane lives on materials, and a batch's meshes arrive a
    frame after placement, so a scene restored with its section on drew
    new batches uncut. A restore from nothing (a second device) or from
    the too-big marker, followed by an edit before the server's copy
    arrived, would have PUT an empty field over the whole one. The pull
    could replace a scene opened meanwhile. Two PUTs in flight could land
    in either order. Every stroke's undo entry held a keep-out of the
    whole scene. Two queued strokes solved against stale keep-outs. A
    cold open re-ran the restore once per late model. The session encoded
    the whole field to throw it away."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    size = _js_function(js, "function sizeTier(tier, needed)")
    assert 'if (state.section.mode === "plane") applySection();' in size
    end = _js_function(js, "function endBrushStroke(stroke)")
    assert end.index("stroke.keepOut = null;") < end.index("pushUndo(")
    stamp = _js_function(js, "function stampBrush(hit)")
    assert "stroke.busy = scatterQueue = scatterQueue.then(async () => {" in stamp
    restore = _js_function(js, "function restoreProps(given)")
    assert "waiting.push(ensurePropTemplate(entry.type));" in restore
    assert ("Promise.all(waiting).then(() => { if (propsAwaitingLibrary) "
            "restoreProps(); });") in restore
    assert "if (!stored || (layout && layout.onServer)) layoutAwaiting.add(propsKey());" in restore
    flush = _js_function(js, "function flushProps()")
    assert flush.index("if (layoutAwaiting.has(pending.key)) return;") < flush.index(
        "layoutWrite = null;"), "a held write stays in hand, not thrown away"
    pull = _js_function(js, "async function pullServerLayout()")
    assert "const awaiting = layoutAwaiting.delete(key);" in pull
    assert "if (!remote || propsGeneration !== generation) {" in pull
    assert "if (layoutWrite || brushStroke || state.carrying) return;" in pull
    scene_block = js[js.index("const sceneProps = decodeProps(scene_.props);"):]
    scene_block = scene_block[:scene_block.index("adoptLayers(scene_.propLayers);")]
    assert "propsGeneration += 1;" in scene_block
    assert "propsAwaitingLibrary = false;" in scene_block
    put = _js_function(js, "function sendLayout()")
    assert "}).finally(sendLayout);" in put, "one PUT at a time"
    assert "if (!layoutServerSaid) {" in put, "a stale server is said once, not per gesture"
    assert "layoutPutQueue.set(exportName, text);" in _js_function(
        js, "function putLayout(exportName, text)")
    assert "if ((layoutPutting || layoutPutQueue.size) && layoutOverQuota.size) {" in js
    collect = _js_function(js, "function collectScene(options)")
    assert "props: withProps ? encodeProps(state.props) : undefined," in collect
    hook = js[js.index("window.__studio = {"):]
    assert "disposeProp," in hook[:hook.index("};")]
    probe = (REPO / "bench" / "scripts" / "scatter_budget.mjs").read_text(encoding="utf-8")
    assert "S.disposeProp(record.object);" in probe


def test_every_dial_is_four_cells_so_the_rows_line_up():
    """A dial block is an eight-column grid and every label dissolves into
    it, so a label must put exactly four things there: name, control,
    reading, unit. The scatter drawer's Size carried its two grips as two
    cells, and every dial after it slid one cell along: Param's screenshot
    had the % and m units starting the next row. Two grips share one
    .range-pair; a select spans the three cells its row lacks, a number
    field two. Counted over every dial block on the page."""

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(encoding="utf-8")
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(encoding="utf-8")
    assert ".dial-block label > select { grid-column: span 3; }" in css
    assert '.dial-block label > input[type="number"] { grid-column: span 2; }' in css
    assert ".dial-block label > .range-pair { display: flex;" in css

    blocks = 0
    for opening in re.finditer(r'<div class="dial-block"[^>]*>', html):
        depth, i = 1, opening.end()
        while depth:
            o, c = html.find("<div", i), html.find("</div>", i)
            if o != -1 and o < c:
                depth, i = depth + 1, o + 4
            else:
                depth, i = depth - 1, c + 6
        blocks += 1
        for label in re.findall(r"<label.*?</label>", html[opening.end():i], re.S):
            inner = re.sub(r'<span class="range-pair">.*?</span>', "<pair>", label, flags=re.S)
            inner = re.sub(r"<select.*?</select>", "<select>", inner, flags=re.S)
            # A reading or a unit is ONE cell whatever it holds: Piece
            # size's unit carries the piece and course counts as spans.
            inner = re.sub(r"<b\b[^>]*>.*?</b>", "<b>", inner, flags=re.S)
            inner = re.sub(r"<em\b[^>]*>.*?</em>", "<em>", inner, flags=re.S)
            cells = 0
            for tag, rest in re.findall(r"<(span|input|select|button|b|em|pair)\b([^>]*)>", inner):
                if tag == "select":
                    cells += 3
                elif tag == "input" and 'type="number"' in rest:
                    cells += 2
                else:
                    cells += 1
            name = re.sub(r"<[^>]+>", " ", label).split()
            assert cells == 4, "{} cells in the dial {!r}".format(cells, " ".join(name[:3]))
    assert blocks >= 12, "every dial block on the page was counted"


def test_the_brush_replaced_the_whole_floor_button():
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert 'id="scatter-brush"' in html
    assert 'id="scatter-radius"' in html
    assert 'id="scatter-all"' not in html, (
        "Param asked for the brush and the area only")


def test_redo_is_built_and_says_when_it_cannot_run():
    """It was not, and the keyboard handler said so in a comment. An
    entry without a forward step ends the branch when it is undone,
    rather than pretending it can be replayed."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    push = _js_function(js, "function pushUndo(label, undo, redo)")
    assert "redoHistory.length = 0;" in push, (
        "a fresh action invalidates the branch it would have redone into")
    undo = _js_function(js, "async function undoLast()")
    assert "if (entry.redo) redoHistory.push(entry);" in undo
    assert "else redoHistory.length = 0;" in undo
    assert "function redoLast()" in js
    paint = _js_function(js, "function paintUndoButton()")
    assert 'document.getElementById("shelf-redo")' in paint
    assert '"Nothing to redo"' in paint


def test_the_readout_counts_a_whole_frame_not_the_last_pass():
    """renderer.info.autoReset clears the counters on EVERY render call,
    and the composer ends a frame with a fullscreen copy pass, so
    anything read afterwards reports that pass alone: one draw call and
    one triangle, identical however much is on screen. It is the exact
    fault the first budget measurement hit."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    note = _js_function(js, "function noteFrame()")
    assert "if (info.autoReset) info.autoReset = false;" in note
    assert "info.reset();" in note
    assert "noteFrame();" in js


def test_vram_and_cpu_come_from_the_server_because_a_browser_cannot_see_them():
    """WebGL exposes neither, and performance.memory is the JavaScript
    heap, which is not VRAM and would be a plausible wrong number in a
    box labelled VRAM."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'fetchJson("/api/stats")' in js
    assert "performance.memory" not in js
    app_py = (REPO / "bench" / "studio" / "app.py").read_text(encoding="utf-8")
    assert '@app.get("/api/stats")' in app_py
    assert "GetSystemTimes" in app_py, "no new dependency for the CPU share"
    assert "nvidia-smi" in app_py
    # The trap in that API: kernel already INCLUDES idle.
    assert "kernel already INCLUDES idle" in app_py


def test_the_sky_brightness_multiplies_the_mode_rather_than_replacing_it():
    """Param: "if i want to darken the hdri so that its dark enough for
    the lights to work well, we dont have that option". There was none:
    each environment mode wrote environmentIntensity outright and nothing
    could move it afterwards."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    apply = _js_function(js, "function applySkyBrightness()")
    assert "scene.environmentIntensity = environmentBase * dial;" in apply
    assert "scene.backgroundIntensity = dial;" in apply, (
        "a dark scene inside a blazing photograph is not darker")
    assert "setEnvironmentIntensity(0.6);" in js
    assert "scene.environmentIntensity = 0.6;" not in js, (
        "no mode may write it outright any more, or the dial is overruled")
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    assert 'id="sky-brightness"' in html
    # And since 2026-09-11 the dial reaches EVERYTHING the day gives, not
    # the environment map alone: Param's screenshot had it at 0 with the
    # sun at 3.0, the hemisphere at 0.5 and the backdrop at its noon tone.
    assert "sun.intensity = lightBase.sun * dial;" in apply
    assert "hemi.intensity = lightBase.hemi * dial * Math.max(NIGHT_FLOOR, night);" in apply
    assert "scene.environmentIntensity *= Math.max(NIGHT_FLOOR, night);" in apply, (
        "the studio's room environment is stand-in daylight and takes the night")
    assert "skyDaylight.value = dial * (0.03 + 0.97 * night);" in apply
    assert "if (hdriDome) hdriDome.children[0].material.color.setScalar(dial);" in apply
    assert "scene.background.copy(lightBase.backdrop).multiplyScalar(dial * (0.08 + 0.92 * night));" in apply
    assert "sun.intensity = 3.0;" not in js, "no mode writes the sun past the dial"
    assert "hemi.intensity = 0.5;" not in js, "nor the sky light"


def test_night_is_an_hour_and_the_moon_takes_the_shadow():
    """The Night preset stood the sun at twenty degrees, and the instrument
    floored every hour at 0.35 "so a night scene is lit by something": no
    hour was ever dark. Night is an hour past dusk now. Below the horizon
    the sun goes out and a moon stands opposite it at five per cent, cool;
    the sky mesh, which no background intensity reaches, is dimmed by its
    own uniform with the night and the dial; the sky light and the fog
    fade with the night; stars come out in sky mode; and a day preset
    chosen at night brings the day back rather than reading as broken."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "0.35 + 2.9 * light.strength" not in js, "the floor is gone"
    assert "const MOON_STRENGTH = 0.08;" in js
    assert "const FULL_SUN = 3.25;" in js
    assert "const NIGHT_FLOOR = 0.1;" in js
    placer = _js_function(js, "function applySunFromTime()")
    assert "const moon = light.strength <= 0;" in placer
    assert "lightBase.sun = moon ? FULL_SUN * MOON_STRENGTH : FULL_SUN * light.strength;" in placer
    assert "const az = THREE.MathUtils.degToRad(sceneAngle + 180);" in placer, (
        "the moon stands opposite the sun")
    assert "Math.max(12, Math.min(60, -placed.elevation))" in placer
    assert "applySkyBrightness();" in placer
    factor = _js_function(js, "function nightFactor(elevation)")
    assert "(elevation + 12) / 14" in factor
    # The sky's shader, patched on the vendored source and checked.
    assert '.replace("gl_FragColor = vec4( texColor, 1.0 );",' in js
    assert '"gl_FragColor = vec4( texColor * daylight, 1.0 );");' in js
    assert "shader.uniforms.daylight = skyDaylight;" in js
    regen = _js_function(js, "function regenerateEnvironment()")
    assert "skyDaylight.value = 0.03 + 0.97 * daylightNow();" in regen, (
        "the environment is captured without the dial, or it is dimmed twice")
    assert "skyDaylight.value = shown;" in regen
    # Stars: outside the fog, in sky mode only.
    stars = _js_function(js, "function starField()")
    assert "toneMapped: false, fog: false," in stars
    assert 'stars.visible = state.environmentMode === "sky" && stars.material.opacity > 0.01;' in js
    # The preset is an hour.
    assert "elevation: null, night: true," in js
    assert "if (preset.night) {\n    setSunMinutes(Math.min(1439, dayCycleEnd() + 90));" in js
    assert "} else if (sunInstrumentReady && currentSun().elevation < -0.833) {" in js
    # A saved scene keeps the sun BEFORE the dial, and the day cycle's
    # capture is the same figure.
    assert "intensity: lightBase.sun," in js
    assert js.count("state.sunIntensityOverride = lightBase.sun;") == 2
    assert "state.sunIntensityOverride = sun.intensity;" not in js


def test_shift_takes_the_whole_run_between_two_clicks():
    """Param: "if i select a thumb nail in props or scatter or layer and
    scroll down then shift and click i expect it to also select all the
    object from clicked point 1 to clicked point 2."

    In the two grids where selecting several means something: the scatter
    species and the layer members. A range ADDS rather than replaces."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "let scatterAnchor = null;" in js
    assert "let layersAnchor = null;" in js
    assert "if (event.shiftKey && scatterAnchor && keys.includes(scatterAnchor))" in js
    assert "for (let i = lo; i <= hi; i++) gatheredProps.add(members[i]);" in js
    # The anchor is the last click WITHOUT shift, or a run cannot be widened.
    assert "scatterAnchor = here;" in js
    assert "layersAnchor = index;" in js


def test_the_scatter_groups_are_chips_like_props_and_materials():
    """Param: "On scatter can we also put the categories into the
    clickable menus like we have with the props and materials."

    The same chips in the drawer head, through the same helper, "all"
    first. The grid shows only the lit group, a shift run stays inside
    what is on screen, and the group is the scatter's OWN: openShelf
    resets the shared one, and the brush and the area bring the drawer
    back through openShelf("scatter") on Escape."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    doc = (REPO / "docs" / "studio-interface-language.md").read_text(
        encoding="utf-8")
    body = _js_function(js, "function renderShelfScatter()")
    assert 'let scatterCategory = "all";' in js
    assert 'shelfChips(cats, ["all", ...groups], scatterCategory' in body
    # A chip click redraws, or the grid and the lit chip sit still until
    # some other click. "renderShelfScatter();" alone is in the body many
    # times over, so the whole callback is pinned as one piece.
    assert ("scatterCategory = name;\n    renderShelfScatter();\n  });"
            in body), "a chip click must redraw the drawer"
    # The chips are only the groups this list holds, after the fixtures
    # are taken out, so none of them opens onto an empty grid.
    assert 'const groups = [...new Set(ordered.map((e) => e.group || "other"))];' in body
    # A remembered group that is no longer in the list falls back to "all",
    # or a changed library leaves an empty grid with no chip lit.
    assert 'if (!groups.includes(scatterCategory)) scatterCategory = "all";' in body
    assert ': ordered.filter((e) => (e.group || "other") === scatterCategory);' in body
    assert "for (const entry of shown) {" in body
    assert "const keys = shown.map((item) => item.key);" in body
    # The group survives a brush or area session. Those put the drawer away
    # through closeShelf and bring it back through openShelf and
    # renderShelf's scatter line, so none of the three may touch it.
    opener = _js_function(js, "function openShelf(kind)")
    assert "scatterCategory" not in opener, (
        "openShelf must leave the scatter's group alone")
    closer = _js_function(js, "function closeShelf()")
    assert "scatterCategory" not in closer, (
        "closeShelf must leave the scatter's group alone")
    shelf_line = next(line for line in js.splitlines()
                      if 'if (shelfKind === "scatter")' in line
                      and "renderShelfScatter(); return; }" in line)
    assert "scatterCategory" not in shelf_line, (
        "renderShelf's scatter line must leave the scatter's group alone")
    # And nothing else anywhere may either: the only writes are the
    # declaration, the vanished-group fallback and the chip click.
    import re

    writes = re.findall(r"\bscatterCategory\s*=(?!=)", js)
    assert len(writes) == 3, (
        f"scatterCategory is written {len(writes)} times; only the "
        "declaration, the fallback and the chip click may write it")
    # Every chip is a button, and every button says what it does.
    chips = _js_function(js, "function shelfChips(holder, names, chosen, pick)")
    assert 'chip.title = name === "all" ? "Show every group" : "Show only " + name;' in chips
    assert 'offers them as chips in the drawer\n  head (`#shelf-cats`) through `shelfChips`, with "all" first.' in doc


def _dial_blocks(html):
    """Every .dial-block in the page, as (id, inner html)."""

    import re

    out = []
    # EITHER ORDER of id and class. The first cut required id first, and
    # the Scatter and Lights blocks are written class first, so it found
    # only the Skies block and reported coverage it did not have: every
    # mutation to a scatter dial walked straight through it.
    for match in re.finditer(r'<div(?=[^>]*class="[^"]*dial-block)'
                             r'(?=[^>]*id="([^"]+)")[^>]*>', html):
        start = match.end()
        depth = 1
        i = start
        while depth and i < len(html):
            nxt_open = html.find("<div", i)
            nxt_close = html.find("</div>", i)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                i = nxt_open + 4
            else:
                depth -= 1
                i = nxt_close + 6
        out.append((match.group(1), html[start:i]))
    return out


def test_every_dial_wears_the_four_part_shape():
    """docs/studio-interface-language.md section 3, made executable.

    Name, dial, reading, unit -- in that order, inside a .dial-block, so
    the four columns line up down the whole block instead of each row
    finding its own edges. A dial with no reading can be neither read nor
    typed into, and makeValueTypable needs the cell to exist.

    Written because three shapes had accumulated: 13 sliders in the old
    form, 11 in this one, and 9 with no readout markup at all."""

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    blocks = _dial_blocks(html)
    names = [name for name, _ in blocks]
    # Named, not counted: "at least one" is what let this test cover a
    # third of what it claimed to.
    # NAMED, and all of them. The first cut asserted "at least one" and
    # scanned one block of three; the second scanned only the blocks that
    # happened to carry an id, so every dial converted in the sweep went
    # unchecked. Scan the population, not the containers you know about.
    for expected in ("scatter-controls", "lights-controls",
                     "shelf-sky-settings", "skin-appearance-dials",
                     "skin-outline-dials", "skin-cut-dials",
                     "analysis-dials", "animation-dials", "camera-dials",
                     "scene-background-dials", "scene-ground-dials"):
        assert expected in names, expected
    import re as _re
    assert len(names) == len(_re.findall(r'class="[^"]*dial-block', html)), (
        "every dial-block is named, or the scan silently skips it")
    for name, body in blocks:
        for label in re.findall(r"<label[^>]*>(.*?)</label>", body, re.S):
            if 'type="range"' not in label:
                continue          # a select or a number box, not a dial
            assert re.match(r"\s*<span>", label), (
                "{}: a dial names itself in a <span> first".format(name))
            slider = re.search(r'<input[^>]*id="([^"]+)"[^>]*type="range"', label)
            assert slider, name
            ident = slider.group(1)
            # A paired range -- a low and a high sharing one reading, as
            # the size ratio does -- is one dial with two grips, so one
            # reading between them is the shape rather than a missing one.
            pair = len(re.findall(r'type="range"', label)) == 2
            shared = re.search(r'<b id="([^"]+)-value"', label)
            if pair and shared and ident.startswith(shared.group(1)):
                pass
            else:
                assert '<b id="{}-value"'.format(ident) in label, (
                    "{}: {} has no reading, so it cannot be read or typed "
                    "into".format(name, ident))
            assert "<em>" in label, (
                "{}: {} states no unit".format(name, ident))


def test_a_dial_that_can_rest_at_zero_declares_its_unit():
    """panel.js derives the unit factor from shown / raw, and at zero the
    derivation gives up: 0 mm and 0 m read the same, so a typed 20 lands
    as a raw 20. Any dial whose floor is zero declares the factor.

    And a dial that CANNOT reach zero must not declare one, or a later
    change to its handler silently stops being honoured."""

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    for name, body in _dial_blocks(html):
        for tag in re.findall(r"<input([^>]*type=\"range\"[^>]*)>", body):
            ident = re.search(r'id="([^"]+)"', tag)
            low = re.search(r'min="([^"]+)"', tag)
            high = re.search(r'max="([^"]+)"', tag)
            unit = re.search(r'data-unit="([^"]+)"', tag)
            if not ident or not low or not high:
                continue
            # "Can rest at zero" is about the RANGE, not the floor: the
            # derivation fails at a raw value of zero whatever min says,
            # and contrast runs from -0.5 to 0.5 through it.
            spans_zero = float(low.group(1)) <= 0 <= float(high.group(1))
            if not spans_zero:
                assert not unit, (
                    "{}: {} cannot reach zero, so its factor derives "
                    "itself; declaring one freezes it".format(
                        name, ident.group(1)))
                continue
            # Zero alone is not the test. Where the reading IS the raw
            # value the derivation returns 1, which is right, and a
            # declared factor would be wrong: data-unit="100" on a dial
            # already reading 100 makes a typed 50 set the slider to 0.5,
            # which its own step then rounds away. That was a real bug in
            # sky-brightness, found by this test on the day it was
            # written.
            shown = re.search(
                r'<b id="' + re.escape(ident.group(1))
                + r'-value">\s*([-\d.]+)', body)
            raw = re.search(r'value="([^"]+)"', tag)
            if not shown or not raw:
                continue
            # THE RESTING VALUE decides, not the comparison. A dial that
            # rests AT zero shows 0 beside a raw 0, which says nothing
            # about its factor, and the derivation gives up there anyway:
            # so it states its factor outright. outline-width rests at
            # zero and is millimetres of a metre; contrast rests at zero
            # and is a percentage of a multiplier. Neither could be
            # inferred from the markup at rest.
            if abs(float(raw.group(1))) <= 1e-9:
                assert unit, (
                    "{}: {} rests at zero, where the factor cannot be "
                    "derived, so it must state one".format(
                        name, ident.group(1)))
                continue
            # Away from zero the markup DOES say: a reading equal to its
            # raw value has a factor of 1 already, and declaring one there
            # is what broke sky-brightness.
            if abs(float(shown.group(1)) - float(raw.group(1))) <= 1e-9:
                assert not unit, (
                    "{}: {} reads its own raw value, so the derived factor "
                    "is already 1 and a declared one breaks typing".format(
                        name, ident.group(1)))
                continue
            if abs(float(shown.group(1)) - float(raw.group(1))) > 1e-9:
                assert unit, (
                    "{}: {} rests at zero and its reading is not its raw "
                    "value, so typing into it needs data-unit".format(
                        name, ident.group(1)))


def test_a_restored_scene_moves_the_readings_with_the_sliders():
    """A dial whose slider jumps and whose number does not is worse than
    one that shows nothing: it states a value the scene does not have."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert 'const reading = document.getElementById(id + "-value");' in js, (
        "the HDRI restore writes each dial's reading by the id pairing")
    assert "paintScrub(control(id));" in js


def test_every_reading_has_something_that_writes_it():
    """A reading cell with no writer is the Glow bug: a number that looks
    live, has never moved, and fails silently for ever. Each of these had
    no writer because until the sweep it had no cell."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    for reading in ("exaggeration-value", "orbit-speed-value",
                    "background-tone-value", "hdri-scale-value",
                    "hdri-height-value", "hdri-rotation-value",
                    "brightness-value", "contrast-value"):
        assert reading in js, (
            "{} is a reading nothing writes".format(reading))
    # And the grade follows a restored scene, or a dial states a value
    # the scene does not have.
    assert js.count("paintGradeReadings();") >= 3, (
        "written on both dials and on the scene restore")


def test_the_interface_language_is_written_down():
    """Param: "spend a while writing a md or specific document that
    describes a language style for how all types of objects and
    interfaces should be made for this application"."""

    doc = REPO / "docs" / "studio-interface-language.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    # The HEADINGS, not the words. "Tiles" appears in the body of its own
    # section, so testing for the bare word passed even with the heading
    # renamed.
    for heading in ("## 1. The four planes",
                    "## 3. A dial is always the same four things",
                    "## 4. Naming", "## 5. Buttons", "## 6. Tiles",
                    "## 7. Drawers", "## 8. Messages",
                    "## 9. What must never regress", "## 10. The sweep"):
        assert heading in text, heading
    assert "\u2014" not in text, "no em dashes, in the interface or the source"


def test_the_sweep_is_finished_and_stays_finished():
    """Param: "then do a sweep to check all the ui as it is to make sure
    that new standard is being used."

    It is. Every visible slider now names itself, shows a reading and
    states a unit, except three that are exempt for stated reasons. This
    test is the ratchet: a new slider added in the old shape fails here
    rather than quietly becoming the fourth dialect.
    """

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")

    # The three exemptions, each for a reason, not for convenience.
    #
    # timeline-scrubber is a TRANSPORT, not a dial: its position is the
    # time and it is read off the animation's own readout.
    # scatter-size-min and -max are one dial with two grips, sharing the
    # single reading "0.80 to 1.30".
    exempt = {"timeline-scrubber", "scatter-size-min", "scatter-size-max"}

    stragglers = []
    for match in re.finditer(r"<input([^>]*type=\"range\"[^>]*)>", html):
        tag = match.group(1)
        ident = re.search(r'id="([^"]+)"', tag)
        if not ident:
            stragglers.append("a slider with no id at all")
            continue
        ident = ident.group(1)
        if ident in exempt:
            continue
        # A hidden input is the model behind a custom control (the sun
        # dial drives three of them), not a dial anyone reads.
        if 'class="hidden"' in tag:
            continue
        label = re.search(r"<label[^>]*>(?:(?!</label>).)*id=\"" + re.escape(ident)
                          + r"\"(?:(?!</label>).)*</label>", html, re.S)
        body = label.group(0) if label else ""
        if '<b id="{}-value"'.format(ident) not in body:
            stragglers.append(ident)

    assert not stragglers, (
        "these sliders are not in the interface language: "
        + ", ".join(stragglers))


def test_no_slider_keeps_the_old_reading_shape():
    """The old form put the reading in a <span id="..-value"> beside bare
    text. Thirteen sliders used it, and mixing three dialects is what the
    document was written to end."""

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    old = re.findall(r'<span id="([a-z0-9-]+)-value"', html)
    # sun-time and sun-angles are the sun dial's compound readout, not a
    # slider reading, and camera-mm and the piece counts sit INSIDE a
    # unit cell as the equivalent focal length and the cut's own tally.
    allowed = {"sun-time", "sun-angles", "camera-mm", "size-units",
               "piece-count", "course-count"}
    left = [name for name in old if name not in allowed]
    assert not left, (
        "still in the old reading shape: " + ", ".join(left))


def test_the_setting_and_the_weather_live_in_the_skies_drawer():
    """Param: "in skies tile lets also put the tab to studio and sky
    modes and choose from the options they have too."

    MOVED, not copied. Two controls over one piece of state is how they
    come to disagree, and the studio already has the precedent: the HDRI
    projection, scale, height and rotation went the same way, "beside the
    pictures they tune"."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")

    drawer = html[html.index('<div id="shelf-sky-modes"'):]
    drawer = drawer[:drawer.index('<div id="shelf-sky-settings"')]
    for control in ('id="environment-segments"', 'id="environment-mode"',
                    'id="weather-picker"', 'id="weather-preset"'):
        assert control in drawer, control

    scene = html[html.index('<details id="scene-section">'):]
    scene = scene[:scene.index("</details>")]
    for control in ('id="environment-segments"', 'id="environment-mode"',
                    'id="weather-picker"'):
        assert control not in scene, (
            control + " is left behind in the panel as a second control")

    # And the drawer shows them with its own dials, not on its own clock.
    assert 'document.getElementById("shelf-sky-modes").classList\n' \
        '    .toggle("hidden", shelfKind !== "skies");' in js


def test_a_scatter_layer_does_not_hang_the_layers_drawer():
    """Each tile in that drawer clones its template and runs a full
    offscreen WebGL render, and refreshLayersShelf re-runs the whole
    drawer after every placement. One brush click can now put six
    hundred props on a layer, so opening the tab he was told to use
    would have tried six hundred renders.

    Above the cap the drawer says what is on the layer instead of
    drawing it, and the tab strip, the eye and the cross keep working --
    which is what Layers is for on a scattered field anyway. Measured at
    300 props: the drawer opens in a millisecond."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const LAYER_TILE_CAP = 40;" in js
    body = _js_function(js, "function renderShelfLayers(grid)")
    assert "if (members.length > LAYER_TILE_CAP) {" in body
    # The guard must come BEFORE the loop that renders, or it guards
    # nothing at all.
    assert body.index("LAYER_TILE_CAP") < body.index("members.forEach")
    # And it leaves the parts of the drawer that still work.
    guard = body[body.index("if (members.length > LAYER_TILE_CAP) {"):]
    guard = guard[:guard.index("members.forEach")]
    assert "renderLayerTabs();" in guard
    assert "paintStampButton();" in guard
    assert "return;" in guard


def test_a_decal_is_a_prop_that_lies_on_the_floor():
    """Param: "Can we include some decals too in the props".

    A DECAL IS A PROP WHOSE GEOMETRY IS A PLANE, which is the whole
    design: arriving as an ordinary GLB it goes through placeProp and
    inherits the gumball, the layers, rotation, scale, undo, the scene
    round trip and the scatter brush with no new client code, and gets
    the right shadow behaviour free because castsShadow keys on height.

    The one thing it cannot inherit is where it sits. loadPropTemplate
    stands every prop on its feet by shifting min.z to 0, and propsGroup
    sits AT groundLevel, so a plane placed at z = 0 is exactly coplanar
    with the floor and z-fights. The two millimetres baked into the GLB
    were eaten by that same normalisation -- the plane's lowest point WAS
    the lift -- so the lift is applied at placement instead."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "const DECAL_LIFT = 0.002;" in js
    place = _js_function(js, "function isDecal(type)")
    assert 'entry.group === "decals"' in place
    assert "  if (!z && isDecal(type)) z = DECAL_LIFT;" in js, (
        "falsy rather than undefined: a restore hands back the saved "
        "0.002, which is truthy and kept")
    # No DecalGeometry, and there should not be: it projects onto
    # arbitrary meshes and the floor is a flat disc.
    assert "DecalGeometry" not in js


def test_the_decal_importer_refuses_anything_without_a_cutout():
    """Not every ambientCG asset filed under Decal is one. The whole
    Leaking family is a surface texture -- colour, normal, roughness,
    and nothing saying which part is stain. Composited with a white
    alpha it lays an opaque grey square on the floor, which loads
    without complaint and reads as a bug in the studio. Four of the
    first ten came out that way."""

    tool = (REPO / "tools" / "props" / "fetch_decals.py").read_text(
        encoding="utf-8")
    assert "no opacity map: this is a surface texture, not a decal" in tool
    assert "the opacity map is flat at" in tool
    # An ACTIVE entry, not the string: the set names TireTracks001 in a
    # comment saying why it is absent, and testing for the bare word
    # would fail on the explanation.
    block = tool.split("CURATED = [")[1].split(chr(10) + "]")[0]
    active = [line.strip() for line in block.splitlines()
              if line.strip().startswith("(")]
    assert not any("TireTracks" in line or "Leaking" in line
                   for line in active), (
        "the ones with no cutout are out of the curated set, not merely "
        "guarded against")
    assert len(active) >= 8, "the set is still a set"
    # And the manifest merges by key, as fetch.mjs does, so a later prop
    # run adds to the decals rather than replacing them.
    assert "by_key[entry[\"key\"]] = entry" in tool


def test_the_scatter_remembers_its_rules_but_not_its_output():
    """The props a scatter made are already saved as ordinary records.
    What would otherwise be lost on a reload is the species he picked,
    the spacing he tuned and the seed that produced a field he liked --
    and a dice with no seed to go back to is not a dice.

    Species are filtered against the library that is actually present: a
    layout written when a prop pack was installed must not put a species
    in the mix that nothing can place, or the first brush stroke fails
    with nothing to say why."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    save = _js_function(js, "function saveProps()")
    assert "scatter: state.scatter," in save
    adopt = _js_function(js, "function adoptScatter(saved)")
    assert "known.has(one.type)" in adopt, "species checked against the library"
    assert "Math.max(1, Math.min(9, +one.weight || 1))" in adopt
    assert "Math.max(1, Math.min(99999," in adopt, "a seed out of range is clamped"
    assert "adoptScatter(layout.scatter);" in js
    # And the dials show the restored rules, or each states a value the
    # scene does not have -- section 3 of the interface language.
    sync = _js_function(js, "function syncScatterControls()")
    for dial in ("scatter-radius", "scatter-spacing", "scatter-clump",
                 "scatter-clump-size", "scatter-clearance"):
        assert dial in sync, dial
    assert "syncScatterControls();" in _js_function(js, "function renderShelfScatter()")


def test_every_hour_the_studio_shows_is_the_site_s_own():
    """One clock, one meaning. state.sunMinutes reads as local mean time
    at the site, so every route from a minute to an instant has to spend
    the offset -- and every route from an instant back to a reading has
    to earn it.

    The route that was missed the first time was the day cycle:
    timeAtElevation answers in UTC, and its dawn went straight into
    state.sunMinutes. In Sydney that swept from 19:00 to 08:00, through
    the night, with every frame correctly computed for the wrong hours.
    """

    js = STUDIO_JS.read_text(encoding="utf-8")

    # Minute to instant: the offset comes off.
    assert "minutes - siteUtcOffsetMinutes()" in js, (
        "minutesToDate must take the site's clock back to UTC")

    # Instant to reading: the offset goes on, for BOTH ends of the cycle.
    for name in ("function dayCycleStart()", "function dayCycleEnd()"):
        body = _js_function(js, name)
        assert "localMinutes(" in body, (
            "{} reads a UTC answer onto the site's clock".format(name))
        assert "getUTCHours()" not in body, (
            "{} must not read raw UTC parts again".format(name))

    # And the rule itself lives where it can be executed by a test, not
    # buried in the module that needs a DOM and a WebGL context to load.
    fields = (REPO / "bench" / "studio" / "static" / "fields.js").read_text(
        encoding="utf-8")
    assert "export function utcOffsetMinutes(longitude)" in fields
    assert "export function localClockMinutes(when, longitude)" in fields

    # A clock that silently means something other than UTC is how the
    # Sydney fault got in, so the reading says which one it is.
    assert '" UTC" + (offset > 0 ? "+" : "") + offset' in js, (
        "the sun readout states its zone whenever there is one")


def test_a_scene_remembers_where_and_when_its_sun_was():
    """Azimuth and elevation were saved; the place and the day that
    produced them were not. Reopen a June noon in December and the two
    angles restore while the reason for them is gone, which is the same
    picture by accident rather than on purpose.

    The restore is guarded, because a scene saved before the site existed
    holds angles and NO place: re-solving those against today's date at
    London would move its sun out from under a camera framed around it.
    """

    js = STUDIO_JS.read_text(encoding="utf-8")

    for field in ("latitude: SUN_SITE.latitude",
                  "longitude: SUN_SITE.longitude",
                  "northOffset: SUN_SITE.northOffset",
                  "day: isoDay(sunDay())",
                  "minutes: state.sunMinutes"):
        assert field in js, "a saved scene carries {}".format(field)

    assert "const siteState = scene_.site;" in js
    assert 'if (siteState && typeof siteState.latitude === "number")' in js, (
        "an older scene carries no site, and must keep its own angles")


def test_the_studio_keeps_two_real_cameras_not_one_faked_projection():
    """You can write an orthographic projectionMatrix into a
    PerspectiveCamera and it renders perfectly. It also picks wrongly
    for ever after, because Raycaster.setFromCamera branches on
    isPerspectiveCamera and goes on building cone rays through a
    parallel frame. The gumball drifts from the pointer and nothing in
    the code says why.

    So there are two real cameras and `camera` is a binding that moves
    between them, which is also why the hundred-odd places that read it
    needed no edit at all."""

    js = STUDIO_JS.read_text(encoding="utf-8")

    assert "const perspectiveCamera = new THREE.PerspectiveCamera" in js
    assert "const orthographicCamera = new THREE.OrthographicCamera" in js
    assert "let camera = perspectiveCamera;" in js, (
        "a const camera cannot be swapped, and every reader would need "
        "rewriting to an accessor")

    swap = _js_function(js, "function setProjection(kind)")
    assert "renderPass.camera = camera;" in swap, (
        "the render pass holds its own reference and would keep drawing "
        "through the old projection")
    assert "controls.object = camera;" in swap, (
        "OrbitControls reads .object on every update, so rebinding it is "
        "the whole of handing the mouse over")
    assert "wanted.quaternion.copy(camera.quaternion);" in swap, (
        "the new camera inherits the old aim, or the toggle spins the view")

    # No stray reader of a lens the orthographic camera does not have.
    # CODE lines only: the comment explaining the trap says "camera.fov"
    # itself, and banning the explanation along with the defect is the
    # same mistake the NOTICE writers caught me making.
    import re as _re
    stray = [line for line in js.splitlines()
             if not line.lstrip().startswith(("//", "*", "/*"))
             and _re.search(r"(?<!perspective)(?<!Perspective)\bcamera\.fov\b",
                            line)]
    assert not stray, (
        "every lens reader must name the perspective camera; an "
        "orthographic one has no fov and hands back undefined: "
        + "; ".join(s.strip() for s in stray[:3]))


def test_a_resize_writes_planes_when_the_camera_has_no_aspect():
    """An orthographic camera has no .aspect: its shape is four planes.
    A resize that wrote .aspect and called updateProjectionMatrix would
    do nothing whatsoever and leave the drawing stretched, silently."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    frustum = _js_function(js, "function applyCameraFrustum(aspect)")
    assert "camera.isOrthographicCamera" in frustum
    for plane in ("camera.top =", "camera.bottom =", "camera.right =",
                  "camera.left ="):
        assert plane in frustum, plane
    assert "camera.aspect = aspect;" in frustum, "and the other one still"

    # BOTH resize paths, the live viewport and the recorder's forced
    # frame. The recorder was the one that would have gone unnoticed:
    # nobody watches a take being written.
    assert js.count("applyCameraFrustum(") >= 4, (
        "the definition, the switch, the viewport resize and the recorder")
    assert "applyCameraFrustum(w / h);" in js, "the live viewport"
    assert "applyCameraFrustum(frame.width / frame.height);" in js, (
        "the recorder's forced frame")


def test_the_scale_bar_states_a_measurement_only_where_one_is_true():
    """In perspective a scale bar is a lie that looks like a
    measurement: a metre at the back of the frame is a fraction of a
    metre at the front. So it is hidden rather than approximated."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    bar = _js_function(js, "function paintScaleBar()")
    assert "if (!camera.isOrthographicCamera) { bar.hidden = true; return; }" in bar

    # Round lengths only. A bar reading 37 m is a number, not a scale.
    assert "const SCALE_STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];" in js
    assert "for (const step of SCALE_STEPS) if (step <= target) metres = step;" in bar, (
        "the nearest round length AT OR UNDER the target, so the bar never "
        "claims more of the frame than it has")

    # The width is the statement, and it comes from metres per pixel.
    assert "bar.style.width = Math.round(metres / metresPerPixel)" in bar
    assert "(orthoFrameHeight / (camera.zoom || 1)) / pixels" in bar, (
        "zoom is how OrbitControls dollies an orthographic camera, so a "
        "bar that ignored it would be wrong after the first scroll")


def test_a_snapped_view_stands_on_the_axis_it_names():
    """Six standing places, at the distance the camera already had, so a
    snap turns the model rather than walking away from it."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    for view, axis in (("front", "[0, -1, 0]"), ("back", "[0, 1, 0]"),
                       ("left", "[-1, 0, 0]"), ("right", "[1, 0, 0]"),
                       ("top", "[0, 0, 1]")):
        assert "{}: {}".format(view, axis) in js, view

    snap = _js_function(js, "function snapCameraTo(name)")
    assert 'if (name === "top") camera.up.set(0, 1, 0);' in js, (
        "looking straight down, the camera's own up is parallel to the "
        "view and the matrix degenerate; +Y there is plan north up")
    assert 'if (name !== "top") clampCameraAboveFloor();' in snap, (
        "the floor guard exists for the orbit, and would shove a plan up "
        "out of its own view")
    assert "camera.position.distanceTo(controls.target) || 30" in snap, (
        "the distance is kept, so a snap turns rather than travels")


def test_a_section_cuts_the_shell_and_fills_the_face():
    """The argument is inside the shell. Voussoir joint geometry, shell
    thickness varying with thrust, the net under the masonry, the
    interface between permanent works and plant -- none of it is visible
    from outside.

    A clipped shell with no cap reads as a hollow eggshell, which is the
    opposite of the claim being made, so the cap is not a refinement of
    this feature: it IS the feature."""

    js = STUDIO_JS.read_text(encoding="utf-8")

    assert "renderer.localClippingEnabled = true;" in js, (
        "LOCAL, not global. A plane on the renderer cuts the gumball, "
        "the thrust arrows and the sun helpers along with the vault, and "
        "makes cutting the shell while the machine stands impossible")

    apply = _js_function(js, "function applySection()")
    assert "material.clippingPlanes = mine;" in apply, (
        "the planes go on the materials, in one walk of the scene")
    assert "const spared = isMachinePart(object) && !state.section.cutMachine;" in apply, (
        "Param asked to choose whether the machine is cut with the vault")
    assert "material.clipShadows = true;" in apply, (
        "or a sectioned vault goes on casting the shadow of the half "
        "that is no longer drawn")
    # Ancestry, not material. The machine shares material instances with
    # the permanent works, so a material-level test would cut both or
    # neither and the toggle would do nothing at all.
    machine = _js_function(js, "function isMachinePart(object)")
    assert "node = node.parent" in machine
    # CODE lines only. The comment that explains this decision says
    # "needsUpdate" itself, and banning the explanation along with the
    # defect is a mistake I have now made twice.
    forced = [line for line in apply.splitlines()
              if not line.lstrip().startswith("//") and "needsUpdate" in line]
    assert not forced, (
        "the renderer keeps the plane COUNT in its program cache key and "
        "recompiles by itself; forcing it rebuilds every shader in the "
        "scene on every tick of the offset dial: " + "; ".join(forced))

    # AND THERE IS NO CAP, which is measured rather than forgotten.
    # The folklore cheap cap -- a coloured plane a millimetre behind the
    # cut -- was built, photographed and deleted: a section is viewed
    # FACE ON, so a plane whose normal points at the camera fills the
    # frame as a backdrop rather than reading as a cut face. It is also
    # not needed here, because every vault material in this studio is
    # already double-sided, so a clipped closed solid draws its own
    # interior and the cut caps itself.
    assert "buildSectionCap" not in js, (
        "the plane cap was measured and removed; a flat poche needs the "
        "stencil two-pass, not a bigger plane")
    assert "THERE IS NO CAP, AND THAT IS THE FINDING." in js, (
        "and the reason stays in the file, or somebody rebuilds it")
    # The property the self-capping depends on. If the vault materials
    # ever go single-sided, a section becomes a hollow eggshell and this
    # is the line that says why.
    assert js.count("side: THREE.DoubleSide") >= 8, (
        "the vault materials are double-sided, which is what makes a "
        "clipped solid show its own interior")

    # THREE.Plane holds signed distance from the origin along its
    # normal, so a plane standing at offset d has constant -d. Positive
    # by mistake and every positive offset puts the cut behind the
    # model, which reads as the feature doing nothing.
    plane = _js_function(js, "function sectionPlane()")
    assert "new THREE.Plane(sectionNormal(), -state.section.offset)" in plane

    # The dial's travel comes from the model. Shipped at -30 to 30 it ran
    # over a barrel 3.2 m deep, so nine tenths of it did nothing and the
    # useful part was four pixels wide.
    fit = _js_function(js, "function fitSectionRange()")
    assert "box.setFromObject(shell)" in fit
    assert "dial.min =" in fit and "dial.max =" in fit and "dial.step =" in fit
    assert "if (box.isEmpty()) return;" in fit, (
        "no study yet means keep the shipped default, not collapse the "
        "dial onto zero")
    assert "fitSectionRange();" in _js_function(js, "function paintSectionControls()")

    # Every rebuild re-cuts. A clipping plane lives on a material, so a
    # re-cut or a change of study would otherwise heal the section while
    # the control still reads Plane.
    build = js[js.index("function buildScene(bundle, preserve) {"):]
    build = build[:build.index(chr(10) + "function ")]
    assert "applySection();" in build, (
        "buildScene builds new materials, and they arrive uncut")


def test_a_dial_block_holds_nothing_but_dials():
    """The containment rule, which nothing enforced until it broke.

    `.dial-block` is `grid-template-columns: repeat(2, auto 1fr auto auto)`
    -- eight columns -- and `.dial-block label { display: contents }`, so
    each dial dissolves into exactly four cells and two dials fill a row.
    That only holds while EVERY child is a label. A bare div takes one
    cell, shifts every dial after it by a column, and overflows the
    panel.

    Three had accumulated in `#camera-dials` and the Camera section
    measured 302 px of content in a 235 px box, with Front, Back, Right
    and Plan hanging off the right-hand edge of the panel. No existing
    test could see it: they all read source text, and this is a layout
    fault. So this one reads STRUCTURE.

    Section is the pattern to copy: `#section-axis-segments` sits above
    `<div class="dial-block" id="scene-section-dials">`, not inside it.
    """

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")

    # The grid is what makes the rule load-bearing, so pin it too: a
    # future widening of the grid would change what "four cells" means.
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    assert "grid-template-columns: repeat(2, auto 1fr auto auto)" in css
    assert ".dial-block label { display: contents;" in css
    # AND the half that only matters inside #panel. upgradeSliders scopes
    # to #panel and REPLACES each label containing a range input with a
    # div.scrub, so there is no label left for display:contents to
    # dissolve and every scrub lands as one grid item. Without this rule
    # three dials sat side by side in a 235 px panel reading "Field of
    # v", "Br", "Contrast", and Skin read "Shine  Re  Occlu  Varia".
    assert ".dial-block > .scrub { grid-column: 1 / -1; }" in css, (
        "an upgraded row takes the whole width; the four-column "
        "alignment the language describes belongs to the shelf, which "
        "is outside #panel and keeps its labels")

    offenders = []
    for name, body in _dial_blocks(html):
        # Strip comments before looking, or a commented-out example reads
        # as a real child.
        clean = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        # Top-level tags only: a <div> nested inside a label is that
        # label's business, and there are none today.
        depth = 0
        for match in re.finditer(r"<(/?)([a-zA-Z]+)", clean):
            closing, tag = match.group(1), match.group(2).lower()
            if closing:
                if tag in ("label", "div"):
                    depth = max(0, depth - 1)
                continue
            if depth == 0 and tag not in ("label", "select", "input", "option"):
                offenders.append("{}: <{}>".format(name, tag))
            if tag in ("label", "div"):
                depth += 1
    assert not offenders, (
        "a .dial-block takes labels only; these take a grid cell each and "
        "shift every dial after them: " + ", ".join(offenders))


def _css_rules(css):
    """Every plain rule in a stylesheet, as (selector, body, offset).

    Comments are blanked to spaces first, so offsets still order the
    rules as the cascade does. An @media wrapper's own brace is skipped
    by construction: a selector may not contain a brace, so the first
    rule inside a media block still reads as its own selector."""

    import re

    clean = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), css,
                   flags=re.S)
    return [(m.group(1).strip(), m.group(2), m.start())
            for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", clean)]


def _declarations(body):
    """A rule body as {property: value}, the later of a repeat winning."""

    out = {}
    for part in body.split(";"):
        if ":" in part:
            name, value = part.split(":", 1)
            out[name.strip().lower()] = " ".join(value.split())
    return out


def _specificity(selector):
    """(ids, classes and pseudo-classes, elements) for one plain
    selector, which is all this stylesheet uses."""

    import re

    ids = selector.count("#")
    classes = len(re.findall(r"\.[\w-]|\[|(?<!:):[\w-]", selector))
    elements = len(re.findall(r"(?:^|[\s>+~])[a-zA-Z][\w-]*", selector))
    return (ids, classes, elements)


def test_no_id_rule_undoes_a_dial_block_grid():
    """The Skies dials landed in the wrong cells, and every dial test
    passed while they did: they read the markup, and the markup was
    right. The fault was one rule, `#shelf-sky-settings { display: grid;
    grid-template-columns: 1fr 1fr; ... }`, left over from before the
    block joined the dial language. An id outranks `.dial-block`, so the
    eight-column grid never applied and each dial's four cells poured
    into two columns (Param: "ui is messed up here").

    So no rule aimed at a dial block's own id may set display, or a
    grid other than the dial grid itself. `#graphs-dials` is a deliberate
    one-dial block, so one or two repeats of the four cells both pass.
    The `.hidden` form of the block may still say `display: none`: an id
    rule is what it takes to beat `.dial-block { display: grid }`."""

    import re

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    blocks = [name for name, _ in _dial_blocks(html)]
    assert "shelf-sky-settings" in blocks
    allowed = {"auto 1fr auto auto", "repeat(2, auto 1fr auto auto)"}
    offenders = []
    for selector, body, _ in _css_rules(css):
        for one in selector.split(","):
            # The block itself, not something inside it: the last
            # compound of the selector is the one the rule lands on.
            last = re.split(r"[\s>+~]+", one.strip())[-1]
            for name in blocks + ["graphs-dials"]:
                match = re.fullmatch("#" + re.escape(name)
                                     + r"((?:[.:][\w-]+)*)", last)
                if not match:
                    continue
                said = _declarations(body)
                if "display" in said and not (
                        match.group(1) == ".hidden"
                        and said["display"] == "none"):
                    offenders.append(one.strip() + " sets display: "
                                     + said["display"])
                columns = said.get("grid-template-columns")
                if columns is not None and columns not in allowed:
                    offenders.append(one.strip() + " sets columns: "
                                     + columns)
                # The shorthands reset the columns too: `grid: auto /
                # 1fr 1fr` is the original fault in other words.
                for shorthand in ("grid", "grid-template",
                                  "grid-template-areas"):
                    if shorthand in said:
                        offenders.append(one.strip() + " sets "
                                         + shorthand + ": "
                                         + said[shorthand])
    assert not offenders, (
        "an id rule outranks .dial-block and throws every dial's four "
        "cells out of line: " + "; ".join(offenders))


def test_a_drawer_stays_on_screen_and_hides_what_it_hides():
    """Param: "in some instances i cant reach the close button for the
    open tile and therefore am stuck with it open unless i press the
    tile again". The drawer is anchored to the bottom and grew upward
    with nothing to stop it: the Skies drawer in Sky mode, weather grid
    open, put its close button 203 px above a 720 px screen.

    Bounded now, with the head pinned: #shelf is capped to the viewport,
    the body scrolls, and the head (the close button's home) sticks to
    the body's top on an opaque ground. And the drawer's own twin of
    `#panel .hidden`, because outside #panel `.dial-block label` and
    `.picker` both outrank a bare `.hidden`: rows tagged hidden stayed
    on screen."""

    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    rules = _css_rules(css)

    def cascade(selector):
        """Every declaration any rule makes for `selector`, a grouped
        selector (`#shelf, #x { ... }`) included, in cascade order, from
        the comment-stripped sheet: a rule commented out says nothing."""
        out = []
        for group, body, _ in rules:
            if selector in (" ".join(s.split()) for s in group.split(",")):
                for part in body.split(";"):
                    if ":" in part:
                        name, value = part.split(":", 1)
                        out.append((name.strip().lower(),
                                    " ".join(value.split())))
        return out

    def said(selector):
        return dict(cascade(selector))

    assert said("#shelf .hidden").get("display") == "none !important", (
        "without it a hidden dial row or the weather picker stays on "
        "screen in the drawer")
    heights = [value for name, value in cascade("#shelf")
               if name == "max-height"]
    assert heights[-2:] == ["calc(100vh - 28px)", "calc(100dvh - 28px)"], (
        "the vh fallback, then dvh, and nothing later undoing the bound: "
        + repr(heights))
    body = said("#shelf-body")
    assert body.get("overflow-y") == "auto", "the body scrolls"
    assert body.get("min-height") == "0", "or the flex child never shrinks"
    assert "overflow" not in body, (
        "overflow: hidden clipped the drawer instead of scrolling it")
    head = said("#shelf-head")
    assert head.get("position") == "sticky" and head.get("top") == "0"
    assert head.get("background") == "var(--panel)", (
        "an opaque, themed ground: the scrim would show tiles through it")
    assert int(head.get("z-index", "0")) >= 2, "above the tiles it covers"
    assert said("#shelf-tabs").get("flex") == "0 0 auto", (
        "the tab strip keeps its height; the body is what gives way")

    doc = (REPO / "docs" / "studio-interface-language.md").read_text(
        encoding="utf-8")
    drawers = doc[doc.index("## 7. Drawers"):doc.index("## 8. Messages")]
    assert "never leaves the screen" in drawers
    assert "hidden rather than\nshown dead" in drawers
    assert "The grid is the only part that scrolls" not in doc


def test_the_weather_tiles_are_skies_not_squares():
    """The weather presets are 2:1 skies, painted into a 2:1 buffer.
    When the grid moved into the drawer, `#shelf-body .tile canvas
    { aspect-ratio: 1 }` came to match them at the same specificity as
    the 2:1 rule and later, so it won: 198 px squares, two rows of
    them, 454 px of drawer. The 2:1 rule must outrank the square one by
    the cascade, not by luck of order, and the five presets sit on one
    row. The pinned four-column `#shelf-body .tile-grid` is untouched."""

    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    rules = _css_rules(css)
    square, wide = [], []
    for selector, body, at in rules:
        said = _declarations(body)
        for one in (s.strip() for s in selector.split(",")):
            if one == "#shelf-body .tile canvas" \
                    and said.get("aspect-ratio") == "1":
                square.append((_specificity(one), at))
            if one.endswith("#weather-tiles .tile canvas") \
                    and said.get("aspect-ratio") == "2 / 1":
                wide.append((_specificity(one), at))
    assert square and wide
    assert max(wide) > max(square), (
        "the square thumbnail rule wins over the weather skies: "
        + repr((max(wide), max(square))))

    five = [(_specificity(s.strip()), at) for selector, body, at in rules
            for s in selector.split(",")
            if s.strip() == "#shelf-body #weather-tiles"
            and _declarations(body).get("grid-template-columns")
            == "repeat(5, 1fr)"]
    four = [(_specificity(s.strip()), at) for selector, body, at in rules
            for s in selector.split(",")
            if s.strip() == "#shelf-body .tile-grid"
            and "grid-template-columns" in _declarations(body)]
    assert five and four and max(five) > max(four), (
        "the five presets go on one row by a rule that outranks the "
        "drawer's four-column grid")


def test_the_hdri_dials_show_only_in_hdri_mode():
    """Param's ruling: a control that does nothing in the current mode is
    hidden, not shown dead. Projection tunes the HDRI photograph, and
    Scale and Height only its grounded dome, yet all three showed under
    the Sky presets. Brightness and Rotation act in every mode and stay.

    One painter, called wherever the mode (applyEnvironment), the
    projection (applyHdriBackdrop) or the drawer (renderShelf) changes."""

    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")

    row = html[html.index('<label id="hdri-projection-row"'):]
    row = row[:row.index("</label>")]
    assert 'id="hdri-projection"' in row, "the row is the Projection dial"

    paint = _js_function(js, "function paintSkyDials()")
    assert 'const hdri = state.environmentMode === "hdri";' in paint
    assert 'const dome = hdri && state.hdriProjection === "projected";' in paint
    assert ('document.getElementById("hdri-projection-row").classList'
            '.toggle("hidden", !hdri);') in paint
    for name in ("scale", "height"):
        assert ('document.getElementById("hdri-' + name + '-row").classList'
                '.toggle("hidden", !dome);') in paint, name
    for kept in ("sky-brightness", "hdri-rotation"):
        assert kept not in paint, kept + " acts in every mode"
    for header in ("function applyEnvironment()", "function applyHdriBackdrop()",
                   "function renderShelf()"):
        assert "paintSkyDials();" in _js_function(js, header), header
    # One painter: nothing else decides these rows on its own terms.
    assert js.count('getElementById("hdri-scale-row")') == 1
    assert js.count('getElementById("hdri-height-row")') == 1


def test_the_hdri_dials_follow_the_mode_when_painted(tmp_path):
    """The statements above can all be present in a painter that never
    runs them (a `return;` at its top left every one in place). So the
    painter is run, under node, against a stub document, walking the
    modes and projections in an order where every step changes at least
    one row: Projection shows only in HDRI, Scale and Height only in
    HDRI with the projected dome, and nothing else is touched."""

    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    paint = _js_function(STUDIO_JS.read_text(encoding="utf-8"),
                         "function paintSkyDials()")
    steps = [("hdri", "projected"), ("studio", "projected"),
             ("hdri", "infinite"), ("sky", "infinite"),
             ("hdri", "projected"), ("sky", "projected")]
    script = tmp_path / "paint.mjs"
    script.write_text("""
const rows = {};
const document = { getElementById(id) {
  if (!rows[id]) {
    const row = { hidden: null };
    row.classList = { toggle(name, force) {
      if (name === "hidden") row.hidden = Boolean(force); } };
    rows[id] = row;
  }
  return rows[id];
} };
const state = {};
const paintSkyDials = new Function("state", "document",
  %s + "\\nreturn paintSkyDials;")(state, document);
const out = [];
for (const [mode, projection] of %s) {
  state.environmentMode = mode;
  state.hdriProjection = projection;
  paintSkyDials();
  const seen = {};
  for (const id of Object.keys(rows)) seen[id] = rows[id].hidden;
  out.push(seen);
}
console.log(JSON.stringify(out));
""" % (json.dumps(paint), json.dumps(steps)), encoding="utf-8")
    run = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    seen = json.loads(run.stdout)
    for (mode, projection), rows in zip(steps, seen):
        dome = mode == "hdri" and projection == "projected"
        assert rows == {"hdri-projection-row": mode != "hdri",
                        "hdri-scale-row": not dome,
                        "hdri-height-row": not dome}, (mode, projection, rows)


def test_a_restored_orthographic_scene_keeps_the_framing_it_was_saved_with():
    """Shipped broken, and the static test that "the fields are saved"
    said nothing about it.

    applyScene wrote orthoFrameHeight and orthographicCamera.zoom from
    the scene, then called setProjection, whose orthographic branch
    re-seeds BOTH -- orthoFrameHeight from perspectiveFrameHeight() and
    zoom to 1 -- because that is exactly what makes a live toggle
    seamless. On a restore it threw the saved numbers away and derived
    them from a perspective eye that applyScene had not yet
    repositioned. A saved plan reopened at a different width every time.

    The pair is therefore written TWICE on purpose: before, because
    setProjection's perspective branch reads both to place the eye; and
    after, to survive the orthographic branch.
    """

    js = STUDIO_JS.read_text(encoding="utf-8")

    # The re-seed that makes the second write necessary is still there,
    # and is still right for a live toggle.
    swap = _js_function(js, "function setProjection(kind)")
    assert "orthoFrameHeight = perspectiveFrameHeight();" in swap
    assert "wanted.zoom = 1;" in swap

    restore = js[js.index("// The projection BEFORE the position"):]
    restore = restore[:restore.index("state.cameraView = scene_.cameraView")]
    assert restore.count("orthoFrameHeight = scene_.orthoHeight;") == 2, (
        "written before the switch for the perspective branch, and again "
        "after it to survive the orthographic one")
    assert restore.count("orthographicCamera.zoom = scene_.orthoZoom;") == 2
    # And the frustum is rebuilt from the restored numbers, or the planes
    # still hold whatever the re-seed put there.
    after = restore[restore.index("setProjection(scene_.projection);"):]
    assert "orthographicCamera.updateProjectionMatrix();" in after
    assert "applyCameraFrustum(viewportAspect());" in after
    assert "paintScaleBar();" in after, (
        "the bar reads metres per pixel, so a restored zoom moves it")


def test_the_sun_shadow_map_is_fitted_to_what_casts():
    """The research report said the shadow camera was framed for the
    perspective view and would break under a parallel one. It was framed
    for NEITHER: a hard-coded 60 m square, written once at boot and
    never touched, which is exactly why the orthographic camera changed
    nothing about it.

    But a 2048 map over 60 m is 29.3 mm texels, and every vault on disk
    is 22.8 m wide, so two thirds of the map was spent on empty ground.
    Measured live after fitting: 11.1 mm on the 2 Sided Vault, 15.7 on
    the 3 Sided, 16.0 on the 5 Sided, 14.9 on Complex geometry, so
    between 1.8 and 2.6 times finer. On a 200 mm voussoir that is a bed
    joint casting a readable line rather than a stepped one. It also
    covers the case the constant could not: anything scattered beyond
    30 m used to lose its shadow silently.
    """

    js = STUDIO_JS.read_text(encoding="utf-8")
    fit = _js_function(js, "function fitSunShadow()")

    assert "object.isMesh && object.castShadow" in fit, (
        "fitted to what CASTS, not to what is in the scene: the ground "
        "disc is 200 m across and would put the box back where it was")
    assert "getBoundingSphere(shadowSphere)" in fit, (
        "a sphere, not a box. The shadow camera looks down the sun's own "
        "axis, so a world-axis box would need re-measuring every time "
        "the sun moved; a sphere is the same size seen from anywhere, "
        "which is what lets the day cycle skip this entirely")
    assert "shadowSphere.center.length() + shadowSphere.radius" in fit, (
        "the light aims at the origin, so the reach is measured from "
        "THERE; a vault sitting off-origin would fall out of its own "
        "shadow map")
    assert "box.near = Math.max(0.1, SUN_DISTANCE - reach);" in fit
    assert "box.far = SUN_DISTANCE + reach;" in fit, (
        "a tight slab is what gives the depth test its precision")
    assert "box.updateProjectionMatrix();" in fit, (
        "an orthographic camera's planes do nothing until it is rebuilt")

    # Settled once a frame, not once per caster: a scatter places
    # hundreds in a burst and re-measuring per prop would be quadratic.
    assert "let shadowFitPending = true;" in js
    render = _js_function(js, "function renderView()")
    assert "if (shadowFitPending) fitSunShadow();" in render, (
        "renderView is the one choke point every render path passes "
        "through, the recorder's included")
    assert js.count("noteCastersChanged();") >= 3, (
        "declared, plus a rebuild and a placement at least")

    # One constant for where the sun stands, or the slab is measured off
    # a distance the light does not actually keep.
    assert "const SUN_DISTANCE = 60;" in js
    assert "const r = SUN_DISTANCE;" in _js_function(
        js, "function applySunAt(azimuthDeg, elevationDeg)")


def test_the_lens_gives_way_to_a_frame_width_in_orthographic():
    """A parallel projection has no focal length, so "45 deg approx 29
    mm" is meaningless there. The frame's real width is not: it is the
    number an architect reads off a drawing, and typing it is how a
    plate gets reproduced at a stated width.

    Measured in the browser: the reading agreed with the geometry to
    two decimals (46.39 against 46.39, taken by projecting two points a
    metre apart), and typing 12 gave a frame exactly 12.00 m across with
    the scale bar following to 2 m.
    """

    js = STUDIO_JS.read_text(encoding="utf-8")
    html = (REPO / "bench" / "studio" / "static" / "index.html").read_text(
        encoding="utf-8")

    # Two rows, one row's worth of space, swapped by the projection.
    assert 'id="camera-fov-row"' in html and 'id="camera-width-row"' in html
    # NEITHER carries .hidden in the markup, and that is load-bearing:
    # upgradeSliders skips a label already hidden, so a row hidden before
    # it runs stays a bare slider for ever, never typable.
    for row in ("camera-fov-row", "camera-width-row"):
        line = [ln for ln in html.splitlines() if 'id="' + row + '"' in ln][0]
        assert "hidden" not in line, row

    paint = _js_function(js, "function paintFrameWidth()")
    assert "camera.isOrthographicCamera" in paint, (
        "keyed on the camera itself, so it follows the binding rather "
        "than a remembered word")
    assert 'lens.classList.toggle("hidden", ortho);' in paint
    assert 'width.classList.toggle("hidden", !ortho);' in paint

    width = _js_function(js, "function frameWidthMetres()")
    assert "(orthoFrameHeight / (orthographicCamera.zoom || 1)) * viewportAspect()" in width, (
        "height is what the frustum is built from; width is that times "
        "the aspect, so it moves with the viewport and the frame ratio")

    setter = _js_function(js, "function setFrameWidthMetres(metres)")
    assert "orthographicCamera.zoom = (orthoFrameHeight * viewportAspect()) / wanted;" in setter, (
        "typing writes ZOOM, never orthoFrameHeight: zoom is what "
        "OrbitControls owns, so the next wheel notch carries on from the "
        "typed value instead of fighting it, and applyCameraFrustum "
        "builds its planes from the height alone")
    assert "orthographicCamera.updateProjectionMatrix();" in setter
    assert "paintScaleBar();" in setter, "metres per pixel just changed"

    # Painted after upgradeSliders at boot, for the reason above.
    boot = js[js.index('guarded("the slider rows"'):]
    boot = boot[:boot.index("guarded(\"the panel groups\"")]
    assert "paintFrameWidth" in boot, (
        "hiding a row before upgradeSliders runs leaves that dial "
        "unupgraded and untypable for the whole session")

    # And it follows a wheel, which in orthographic changes zoom and
    # moves nothing else.
    assert js.count("paintFrameWidth()") >= 4, (
        "the swap, the controls change, the resize and the boot")


def test_a_still_is_tiled_through_its_own_endpoint_and_covers_the_viewport():
    """An A3 plate at 300 dpi is 4961 by 3508 and the recorder stops at
    1920. Tiled through camera.setViewOffset, read off the canvas the
    way the recorder already proves, POSTed to the still's OWN endpoint,
    stitched server-side.

    Three things this pins were each found the hard way on the same
    evening. The offscreen read is refused because the composer target
    is HalfFloatType and reading it into bytes gives a black plate. The
    viewport is covered because each tile reassigns the canvas backing
    store and the picture leaps from tile to tile. And the result line
    survives, because the first cut wiped it the instant it was written
    and a render that reports nothing reads exactly like one that never
    saved."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    still = _js_function(js, "async function renderStill()")

    assert '"/api/still/" + target + "?tile="' in still, (
        "its OWN endpoint: post_frame deletes every frame in a take when "
        "handed frame 1, so a still through /api/frames destroys a take")
    assert "/api/frames/" not in still
    assert "camera.setViewOffset(frame.width, frame.height, x, y, width, height);" in still
    assert "applyCameraFrustum(frame.width / frame.height);" in still, (
        "the frustum is the WHOLE plate's, narrowed to this tile; hand "
        "it the tile's aspect and every tile is framed as the picture")
    assert "camera.clearViewOffset();" in still, "or the viewport stays cropped"
    assert 'canvas.toBlob(resolve, "image/png")' in still, (
        "PNG, and off the canvas: a plate is printed, and the composer "
        "target is half float so reading it into bytes returns black")
    assert "readRenderTargetPixels" not in still, (
        "measured: 2048 by 1316 of pure black, every channel (0, 0)")
    # The page's one read of a render target is the atmosphere's horizon
    # strip (T6, 2026-09-11), and it reads its half floats AS half floats,
    # into a Uint16Array decoded by fromHalfFloat, never into bytes.
    assert js.count("readRenderTargetPixels") == 1
    horizon = _js_function(js, "function readSkyHorizon(holder)")
    assert "readRenderTargetPixels" in horizon
    assert "new Uint16Array(HORIZON_STRIP.width * HORIZON_STRIP.height * 4)" in horizon
    assert "THREE.DataUtils.fromHalfFloat(" in horizon
    assert 'document.body.classList.add("stilling");' in still
    assert 'document.body.classList.remove("stilling");' in still
    css = (REPO / "bench" / "studio" / "static" / "studio.css").read_text(
        encoding="utf-8")
    assert "body.stilling #view { visibility: hidden; }" in css

    # The result line is not wiped on the way out.
    paint = _js_function(js, "function paintStillControls()")
    assert "paintStillReadout" not in paint, (
        "the size line belongs to paintStillSize, written when the size "
        "changes and never in the finally clause of a render")
    assert "written in " in still

    # Named for the page.
    assert '{ key: "a3-300", label: "A3", long: 4961 }' in js
    assert '{ key: "a2-300", label: "A2", long: 7016 }' in js
