"""No JS runtime in CI, so pin what Python can see: files exist, the
importmap wires the vendored three, the page and app agree on element ids,
and the vendor files are the pinned build."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def test_vendor_files_are_present_and_pinned():
    core = STATIC / "vendor" / "three.core.js"
    module = STATIC / "vendor" / "three.module.js"
    assert core.is_file() and core.stat().st_size > 100_000
    assert module.is_file()
    assert "185" in module.read_text(encoding="utf-8")[:20_000] or "185" in core.read_text(encoding="utf-8")[:20_000]
    assert (STATIC / "vendor" / "addons" / "controls" / "OrbitControls.js").is_file()
    assert (STATIC / "vendor" / "addons" / "environments" / "RoomEnvironment.js").is_file()


def test_index_wires_the_importmap_and_scripts():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '"three"' in html and "vendor/three.module.js" in html
    assert "three/addons/" in html
    assert "studio.js" in html and "studio.css" in html


def test_no_external_urls_in_the_page_or_scripts():
    for name in ("index.html", "studio.js", "studio.css"):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), (
            "{} references the network; the studio must work offline".format(name)
        )


def test_binning_js_avoids_the_known_parity_traps():
    js = (STATIC / "binning.js").read_text(encoding="utf-8")
    assert "Math.round" not in js, "use floor(x + 0.5); Math.round differs from Python round at .5"
    assert "halfUp" in js
    assert "theta < 0" in js, "JS % keeps sign; the fold to [0, 2pi) must be explicit"
    assert "WEDGES_AT_RIM = 12" in js


def test_pbr_helpers_and_column_loader_exist():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("noiseTexture", "grainTexture", "columnGeometryFrom", "loadColumns"):
        assert name in js, "studio.js lost {}".format(name)
    assert "MeshPhysicalMaterial" in js
    assert "ACESFilmicToneMapping" in js


def test_the_timeline_is_a_pure_function_of_time():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "applyTimeline" in js and "timelineDuration" in js
    start = js.index("function applyTimeline")
    end = js.index("\n}", start)
    body = js[start:end]
    for clock in ("performance.now", "Date.now", "requestAnimationFrame"):
        assert clock not in body, (
            "applyTimeline reads {}; it must be pure in t or recording "
            "will not be deterministic".format(clock)
        )


def test_the_layer_registry_has_the_agreed_names():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("stress", "deflection", "loads", "reactions", "overlays", "pulse", "wires"):
        assert '"{}"'.format(name) in js
    assert "layerAvailability" in js
    assert "no staging" in js or "staged run" in js, "disabled layers must say why"


def test_wire_forces_layer_is_registered_and_instanced():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"forces"' in js and "Wire forces" in js
    assert "setColorAt" in js
    assert "member_forces" in js
    # setColorAt alone never reaches the screen: InstancedMesh.instanceColor
    # only tints pixels when the material opts into the vertex-colour path.
    assert "vertexColors" in js


def test_record_mode_is_frame_indexed_not_clock_driven():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "recordAnimation" in js
    assert "frameIndex / fps" in js, "frames must come from applyTimeline(frame/fps)"
    assert "study-" in js
    assert "state.recording" in js


def test_import_controls_exist_and_wire_the_uploads_endpoint():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control_id in (
        "import-export-input", "import-export-button",
        "import-columns-input", "import-columns-button", "import-status",
    ):
        assert 'id="{}"'.format(control_id) in html, "index.html lost {}".format(control_id)
    assert "uploads/exports" in js


def test_thickness_control_is_wired_and_honest():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="thickness-input"' in html and 'id="thickness-value"' in html
    assert "state.thickness" in js
    assert "thickness=" in js, "loadStudy must send the thickness parameter"
    assert "verified run used" in js, "the HUD must flag a thickness mismatch"


def test_hud_captions_the_thickness_the_bundle_is_actually_built_at():
    # M3: the HUD must caption the provenance thickness (what's on screen),
    # not the thickness control's current value, which can drift from the
    # loaded bundle (a mid-run slider nudge, a still-loading bundle).
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function updateHud(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "state.bundle.provenance.thickness" in body
    assert "Math.round(state.thickness * 1000)" not in body


def test_boot_and_import_columns_share_the_dispose_before_reload_helper():
    # M1: boot() used to add a fresh columns group on every call with no
    # dispose, so each export-pair re-import (which calls boot()) stacked
    # another copy into the scene. Both call sites must route through the
    # same dispose-then-reload helper importColumns already modelled.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "async function reloadColumns(" in js
    boot_start = js.index("async function boot(")
    boot_end = js.index("\n}", boot_start)
    assert "reloadColumns(" in js[boot_start:boot_end]
    import_start = js.index("async function importColumns(")
    import_end = js.index("\n}", import_start)
    assert "reloadColumns(" in js[import_start:import_end]


def test_export_import_selects_and_loads_the_imported_study():
    # M2: after a successful export-pair import, the studio must select and
    # load the export that was just imported, not fall back to studies[0].
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    boot_start = js.index("async function boot(preferredExport)")
    boot_end = js.index("\n}", boot_start)
    boot_body = js[boot_start:boot_end]
    assert "select.value = toLoad" in boot_body
    import_start = js.index("async function importExportPair(")
    import_end = js.index("\n}", import_start)
    assert "boot(contractPrefix)" in js[import_start:import_end]


def test_run_completion_reloads_with_the_params_captured_at_post_time():
    # M5: a slider nudge mid-run must not orphan the run's own result --
    # watchRun must reload with the material/rings/thickness the run was
    # actually started with, captured at POST time, and sync the controls
    # to match so the display stays consistent with what's on screen.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function applyRunParamsToControls(" in js
    assert "function watchRun(runId, exportName, status, params)" in js
    watch_start = js.index("function watchRun(runId, exportName, status, params)")
    watch_end = js.index("\n}", watch_start)
    watch_body = js[watch_start:watch_end]
    assert "applyRunParamsToControls(params)" in watch_body
    start_start = js.index("async function startRun(")
    start_end = js.index("\n}", start_start)
    start_body = js[start_start:start_end]
    assert "watchRun(body.run, exportName, status, params)" in start_body


def test_hud_refreshes_while_scrubbing_and_throttled_while_playing():
    # M6: the HUD's stage/formwork lines read state.timeline.t, so they must
    # refresh as the timeline is scrubbed and while it plays -- but not on
    # every unthrottled render frame, since updateHud is string work.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    scrub_start = js.index("scrubber.addEventListener")
    scrub_end = js.index("\n});", scrub_start)
    assert "updateHud()" in js[scrub_start:scrub_end]
    frame_start = js.index("function frame(now)")
    frame_end = js.index("\n}", frame_start)
    frame_body = js[frame_start:frame_end]
    assert "updateHud()" in frame_body
    assert "% 15" in frame_body


def test_the_scrubber_is_wired_to_the_pure_timeline():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="timeline-scrubber"' in html
    assert "timeline-scrubber" in js
    assert "timelineDuration()" in js
