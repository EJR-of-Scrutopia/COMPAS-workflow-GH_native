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
    for name in ("index.html", "studio.js", "studio.css", "fields.js"):
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
    # applySceneAtTime is the scene-only helper applyTimeline delegates to
    # (setLayer and rebuildWiresAndNodes call it directly so they never move
    # the camera); it must stay just as pure in t as applyTimeline itself.
    helper_start = js.index("function applySceneAtTime(")
    helper_end = js.index("\n}", helper_start)
    helper_body = js[helper_start:helper_end]
    for clock in ("performance.now", "Date.now", "requestAnimationFrame"):
        assert clock not in helper_body, (
            "applySceneAtTime reads {}; it must be pure in t or recording "
            "will not be deterministic".format(clock)
        )


def test_the_layer_registry_has_the_agreed_names():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("stress", "deflection", "loads", "reactions", "overlays", "pulse", "wires", "falsework"):
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


def test_sprayed_concrete_is_offered_and_styled():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'value="concrete-sprayed"' in html
    assert '"concrete-sprayed"' in js


def test_load_arrows_draw_along_the_shipped_vector():
    # The contract ships loads already pointing down (negative z). The old
    # direction argument multiplied the vector by -1 twice over, so loads
    # rendered upward. Arrows must draw exactly along the shipped vector.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function arrowField(entries, colour)" in js
    start = js.index("function arrowField(")
    end = js.index("\n}", start)
    assert "direction" not in js[start:end]


def test_the_strike_takes_wires_nodes_and_falsework():
    # Strike-dependent visibility lives in applySceneAtTime, the scene-only
    # helper applyTimeline delegates to -- setLayer and rebuildWiresAndNodes
    # call this helper directly (never applyTimeline) so a layer checkbox or
    # a size-slider rebuild cannot also reposition the camera.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applySceneAtTime(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "strikeU" in body
    assert "state.layers.falsework" in body
    assert "state.layers.wires" in body
    for name in ("wires", "nodes"):
        assert '"{}"'.format(name) in body, "the strike must drive {}".format(name)


def test_set_layer_does_not_call_applytimeline_directly():
    # FINDING 1 (camera snap): setLayer's wires/falsework branch used to call
    # applyTimeline, whose autoSpin branch repositions the camera onto the
    # orbit ring -- so ticking a layer checkbox teleported a user-positioned
    # camera. It must call the scene-only applySceneAtTime helper instead.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function setLayer(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "applySceneAtTime(state.timeline.t)" in body
    assert "applyTimeline(" not in body, (
        "setLayer must never call applyTimeline directly; that would move "
        "the camera on a layer toggle"
    )


def test_falsework_is_a_translucent_ghost_with_a_toggle():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"falsework", "Falsework ghost"' in js
    assert "opacity: 0.3" in js
    assert "wireMaterial.transparent = true" in js
    assert "nodeMaterial.transparent = true" in js


def test_node_and_wire_size_sliders_rebuild_the_thrust_network():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control_id in ("node-radius", "wire-radius", "node-radius-value", "wire-radius-value"):
        assert 'id="{}"'.format(control_id) in html, "index.html lost {}".format(control_id)
    assert "state.nodeRadius" in js and "state.wireRadius" in js
    assert "function rebuildWiresAndNodes(" in js
    start = js.index("function rebuildWiresAndNodes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "geometry.dispose()" in body, "a rebuild must dispose the old geometry"
    assert "material.dispose()" in body, "a rebuild must dispose the old material"
    # FINDING 2 (GPU leak): in three 0.185, InstancedMesh.dispose() is what
    # frees the instanceMatrix/instanceColor GPU buffers; disposing only the
    # geometry and material leaks them on every slider drag.
    assert "object.dispose()" in body, "a rebuild must dispose the InstancedMesh itself"
    assert "applyWireForces()" in body, "the forces layer must survive a rebuild"
    # FINDING 1 (camera snap): the rebuild must recompute strike-dependent
    # scene state through the scene-only helper, never applyTimeline itself,
    # or a size-slider drag would also teleport the camera.
    assert "applySceneAtTime(" in body, "the strike state must survive a rebuild"
    assert "applyTimeline(" not in body, (
        "rebuildWiresAndNodes must never call applyTimeline directly; that "
        "would move the camera on a slider drag"
    )


def test_node_and_wire_size_sliders_rebuild_only_on_change():
    # FINDING 2: a drag must fire one rebuild, not dozens -- the mm label
    # updates live on "input", the rebuild itself waits for "change" (drag
    # release), same pattern as the thickness slider.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control_id in ("node-radius", "wire-radius"):
        input_start = js.index('getElementById("{}").addEventListener("input"'.format(control_id))
        input_end = js.index("\n});", input_start)
        input_body = js[input_start:input_end]
        assert "rebuildWiresAndNodes()" not in input_body, (
            "{} must not rebuild on every input event".format(control_id)
        )
        change_start = js.index('getElementById("{}").addEventListener("change"'.format(control_id))
        change_end = js.index("\n});", change_start)
        change_body = js[change_start:change_end]
        assert "rebuildWiresAndNodes()" in change_body, (
            "{} must rebuild on change".format(control_id)
        )


def test_segments_are_extruded_to_the_bundles_thickness():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "fields.js" in js, "studio.js must import the pure fields module"
    start = js.index("function buildSegmentMeshes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "state.bundle.provenance.thickness" in body, (
        "extrusion must use the thickness the bundle was actually built at"
    )
    for name in ("vertexNormals", "extrudeSegment", "boxUVs", "segmentUVOffset"):
        assert name in body, "buildSegmentMeshes lost {}".format(name)
    assert "basePositions" in body


def test_recolour_consumes_the_corner_metadata():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "userData.corners" in body
    assert "userData.basePositions" in body


def test_stress_smoothing_is_wired_and_per_surface_is_the_default():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '<option value="per" selected>' in html
    assert "smoothStressField" in js and "interpolateScalarField" in js
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "corner.surface" in body, "per-surface mode must pick the field by skin"


def test_the_legend_exists_and_tracks_the_layers():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    for element_id in ("legend", "legend-title", "legend-bar", "legend-min", "legend-zero", "legend-max"):
        assert 'id="{}"'.format(element_id) in html, "index.html lost {}".format(element_id)
    assert "function updateLegend(" in js
    assert "peaks only" in js, "the fallback legend must say peaks only"
    assert "#legend-bar" in css
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    assert "updateLegend(" in js[start:end], "recolourSegments must refresh the legend"
    # FINDING 3 (legend honesty): with neither staging nor verification data,
    # stressMagnitude/deflectionMax are just floors (1 Pa / 1e-9), so the
    # legend must hide instead of printing a fabricated "-0.00 / 0.00" scale.
    # This mirrors layerAvailability's own stress/deflection rule: available
    # only when a converged final stage exists or bundle.verification does.
    legend_start = js.index("function updateLegend(")
    legend_end = js.index("\n}", legend_start)
    legend_body = js[legend_start:legend_end]
    assert "state.bundle.verification" in legend_body, (
        "updateLegend must check availability the same way layerAvailability does"
    )
    assert 'classList.add("hidden")' in legend_body, (
        "updateLegend must hide the legend when the layers that are on have no data"
    )


def test_stress_scale_and_legend_gradient_share_the_same_hexes():
    # FINDING 4 (ramp duplication): studio.css's #legend-bar gradient hand-
    # mirrors STRESS_SCALE's compression/zero/tension constants in
    # studio.js. Pin the three hexes in both files so the two cannot drift
    # apart silently.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    for hexcode in ("2255cc", "f2efe8", "cc2211"):
        assert hexcode in js, "STRESS_SCALE lost {}".format(hexcode)
        assert hexcode in css, "the legend gradient lost {}".format(hexcode)
    # Each file must name the other so a future edit to one is prompted to
    # check the other.
    assert "studio.css" in js, "STRESS_SCALE must point at studio.css's mirrored gradient"
    assert "studio.js" in css, "the legend gradient must point at STRESS_SCALE in studio.js"


def test_stop_and_restart_transport_controls():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="stop-button"' in html and 'id="restart-button"' in html
    stop_start = js.index('getElementById("stop-button")')
    stop_end = js.index("\n});", stop_start)
    stop_body = js[stop_start:stop_end]
    assert "applyTimeline(0)" in stop_body
    assert "playing = false" in stop_body
    restart_start = js.index('getElementById("restart-button")')
    restart_end = js.index("\n});", restart_start)
    restart_body = js[restart_start:restart_end]
    assert "applyTimeline(0)" in restart_body
    assert "playing = true" in restart_body


def test_cra_badge_hud_and_pulse_are_wired():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="cra-badge"' in html
    for class_name in ("cra-stands", "cra-fails", "cra-unknown"):
        assert class_name in css
    assert "function craVerdict(" in js and "function updateCraBadge(" in js
    pulse_start = js.index("function applyPulse(")
    pulse_end = js.index("\n}", pulse_start)
    assert "cra.stands" in js[pulse_start:pulse_end], (
        "the pulse must require the CRA verdict as well as the FEA solve"
    )
    hud_start = js.index("function updateHud(")
    hud_end = js.index("\n}", hud_start)
    assert "CRA:" in js[hud_start:hud_end]
    build_start = js.index("function buildScene(")
    build_end = js.index("\n}", build_start)
    assert "updateCraBadge()" in js[build_start:build_end]


def test_data_panel_reports_the_cra_verdict_with_provenance():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert "craVerdict()" in body
    assert "EN 1992-1-1 clause 6.2.5" in js
    assert "timber on timber" in js
    # The CRA section must render BEFORE the verification early-out, so it
    # always appears even on staged-but-unverified studies. Verify source order.
    cra_index = body.index("craVerdict()")
    verify_early_out = body.index("no verification run embedded yet")
    assert cra_index < verify_early_out, (
        "CRA section must come before the verification early-return guard, "
        "or staged-but-unverified studies will never show the verdict"
    )
