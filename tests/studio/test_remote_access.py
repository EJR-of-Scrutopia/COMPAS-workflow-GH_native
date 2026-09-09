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
    push = _js_function(js, "function pushUndo(label, undo)")
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
    remove = _js_function(js, "function removePropRecord(record)")
    assert "refreshLayersShelf();" in remove
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


def test_ctrl_z_undoes_as_well_as_the_tile():
    """Param: "Can we also get ctrl + z to also run an undo instead of
    just the button". Cmd+Z too, and never while text has focus, where
    the gesture belongs to the text rather than to the scene."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    start = js.index('document.getElementById("shelf-undo").addEventListener')
    block = js[start:start + 1200]
    assert "event.ctrlKey || event.metaKey" in block.replace(
        "!event.ctrlKey && !event.metaKey", "event.ctrlKey || event.metaKey")
    assert 'if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;' in block
    assert "if (event.shiftKey) return;" in block, "redo is not built"
    assert "undoLast();" in block
    assert "event.preventDefault();" in block


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

    # In the Scene section, where he asked for it.
    scene = html[html.index('<details id="scene-section">'):]
    scene = scene[:scene.index("</details>")]
    assert 'id="outline-width"' in scene, "the slider lives in the Scene menu"
    row = scene[scene.index('id="outline-width"'):]
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
    assert 'const LAMP_TYPES = new Set(["orb-light"]);' in js
    assert "new THREE.PointLight(0xffffff, 1, 0, 2)" in js, (
        "decay 2 is the inverse square, which is what makes a lamp read "
        "as a lamp rather than as a flood")

    # Kelvin, not two swatches. The coefficients are gamma-encoded bytes,
    # so they must go in through SRGBColorSpace or they come out pale.
    kelvin = _js_function(js, "function kelvinColour(kelvin)")
    assert "99.4708025861 * Math.log(t) - 161.1195681661" in kelvin
    assert "THREE.SRGBColorSpace);" in kelvin

    lit = _js_function(js, "function applyPropLight(record)")
    assert "child.color.copy(colour);" in lit
    assert "child.power = lumens;" in lit, "three.js takes lumens directly"
    # The globe is the source: unlit, and pushed above 1 so it reads as
    # brighter than white rather than as a pale ball.
    assert "1.2 + 1.8 * Math.min(1, lumens / 3000)" in lit
    # The halo is the glow, and it dies with the lamp.
    assert "child.visible = spread > 0;" in lit

    # A source casting a hard sun shadow of ITSELF reads as plastic.
    made = _js_function(js, "function makeProp(type)")
    assert "if (child.isMesh && !child.userData.lampGlobe) {" in made

    # The halo is depth tested, so the vault hides it exactly as it hides
    # the globe. depthWrite is off so it never occludes what is behind it.
    assert "blending: THREE.AdditiveBlending, depthWrite: false" in js
    assert "depthTest: false" not in _js_function(js, "function propOrbLight()")
    # And its material is freed with the prop: a Sprite is not a Mesh, so
    # the mesh branch above it never sees one.
    assert "if (child.isSprite) child.material.dispose();" in js

    # Both numbers survive a reload and a scene.
    assert "lumens: p.lumens, kelvin: p.kelvin })" in js, "the study layout"
    assert "lumens: record.lumens, kelvin: record.kelvin," in js, "the scene"
    assert js.count("adoptLampSettings(record, entry);") == 2, (
        "restoreProps and applyScene both give a lamp its numbers back")
    adopt = _js_function(js, "function adoptLampSettings(record, entry)")
    assert "state.lampLumens;" in adopt and "state.lampKelvin;" in adopt, (
        "a prop saved before lamps existed restores lit, not dark")

    # The controls, in the Scene menu, and what they aim at.
    scene = html[html.index('<details id="scene-section">'):]
    scene = scene[:scene.index("</details>")]
    for control in ("lamp-lumens", "lamp-kelvin", "glow-strength"):
        assert 'id="%s"' % control in scene, control
    aim = _js_function(js, "function lampTargets()")
    assert "if (isLamp(state.selectedProp)) return [state.selectedProp];" in aim
    assert "return state.props.filter(isLamp);" in aim
    # The heading says which of the two is about to happen, and it has to
    # be told when the count changes -- it read "Lights" over two lamps
    # until a placement started saying so.
    sync = _js_function(js, "function syncLightControls()")
    assert '"Lights (all " + lamps.length + ")"' in sync
    assert "  if (isLamp(record)) syncLightControls();\n  if (save) saveProps();" in js

    # The lamp is offered even with no prop library at all: it is code,
    # not a file, so no folder needs choosing and no fetch can fail it.
    assert 'key: "orb-light", label: "Orb light", group: "lights", builtIn: true' in js
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
    assert 'canvas.toBlob(resolve, "image/png")' not in js

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
    assert "type: p.type, x: p.x, y: p.y, z: p.z || 0, rotation: p.rotation," in js
    assert "type: record.type, x: record.x, y: record.y, z: record.z || 0," in js
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
    assert "camera.position.distanceTo(propGumball.position)" in size
    assert "Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)" in size, (
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
    assert "rotX: p.rotX || 0, rotY: p.rotY || 0," in js, "the layout keeps tilt"
    assert "rotX: record.rotX || 0, rotY: record.rotY || 0," in js, (
        "a saved scene keeps tilt")
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
