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
    assert 'for (const id of ["prop-edit", "shelf-prop-edit"]) {\n'\
        "    const button = document.getElementById(id);" in js
    assert 'for (const id of ["prop-edit", "shelf-prop-edit"]) {\n'\
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
