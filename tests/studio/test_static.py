"""No JS runtime in CI, so pin what Python can see: files exist, the
importmap wires the vendored three, the page and app agree on element ids,
and the vendor files are the pinned build."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def _function_body(js, name):
    """The source of one top level function, brace to closing brace.

    Every function in studio.js is written at column 0, so the first
    "\\n}" after the declaration is its own closing brace.
    """

    start = js.index("function {}(".format(name))
    return js[start:js.index("\n}", start)]


def _luminance(hexstr):
    """Relative luminance of a 6 hex digit colour string, no 0x prefix."""

    v = int(hexstr, 16)
    return 0.2126 * ((v >> 16) & 255) + 0.7152 * ((v >> 8) & 255) + 0.0722 * (v & 255)


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


def test_the_page_no_longer_mirrors_the_binning():
    assert not (STATIC / "binning.js").exists()
    assert "binning.js" not in (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "segmentation mirror" not in (STATIC / "studio.js").read_text(
        encoding="utf-8").lower()


def test_the_size_control_replaces_the_ring_slider():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="size-slider"' in page
    assert 'id="piece-count"' in page
    assert 'id="rings-slider"' not in page


def test_the_viewer_samples_fields_through_weights():
    source = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "sampleScalar" in source
    assert "sampleVector" in source


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
    for name in ("stress", "deflection", "loads", "reactions", "overlays", "pulse", "wires", "falsework", "shell"):
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
    assert "frameIndex * speed / fps" in js, (
        "frames must come from applyTimeline(frame * speed / fps): pure in "
        "frame number with the rate folded in"
    )
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


def test_the_hud_does_not_call_an_unavailable_material_a_convergence_failure():
    # Fix round 1: brick, tile and stone carry no ananke_fea preset, so
    # staging.py never calls the struck-now runner for them and instead
    # writes struck.status "unavailable". Before this fix the HUD had only
    # two readings, "stands" and "no equilibrium found", so an unattempted
    # solve read exactly like a real convergence failure. A third reading
    # is required, and it must not share the failure branch's wording.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function updateHud(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert 'struck.status === "unavailable"' in body
    assert "not available for this material" in body
    # The two branches must be distinguishable at the text a user reads:
    # the failure line must not be reachable through the unavailable line.
    unavailable_start = body.index('struckLine = "struck now: not available')
    unavailable_line = body[unavailable_start:body.index(";", unavailable_start)]
    assert "no equilibrium found" not in unavailable_line


def test_the_pulse_does_not_tint_an_unavailable_material_red():
    # Fix round 1, the other half: applyPulse used only good/not-good, so a
    # material with no ananke_fea preset pulsed the same red as a real
    # failed solve. Neither green (nothing converged) nor red (nothing
    # failed either) is honest; it must read as a third, neutral state.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applyPulse(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert 'struck.status === "unavailable"' in body
    tint_start = body.index("const tint =")
    tint_line = body[tint_start:body.index(";", tint_start)]
    assert "unavailable ?" in tint_line
    # The neutral tint must be its own colour, distinct from both the good
    # (green) and not-good (red) tints already pinned elsewhere.
    assert "0x2a2a2a" in tint_line
    assert "0x1a3a1a" in tint_line and "0x3a1a1a" in tint_line


def test_every_reader_of_struck_now_gives_the_unavailable_case_its_own_reading():
    # Final fix wave. The two tests above pin updateHud and applyPulse, the
    # two functions commit 022f9c5 fixed, and neither of them looks at
    # layerAvailability -- the third reader of the same state, in the same
    # file, which kept the two-reading logic for the whole wave. It reached
    # the screen twice on shipped exports: limestone with a finished staged
    # run telling the reader to wait "until a staged run exists", and brick
    # with a finished staged run and no verification file disabling the
    # layers for "no staging" while staging sat in the bundle.
    #
    # All three are pinned here together, in one test, so that fixing two
    # of them is not a thing that can pass.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    readers = ("updateHud", "applyPulse", "layerAvailability")
    for name in readers:
        body = _function_body(js, name)
        reads_it = (
            'status === "unavailable"' in body
            or "stagingUnavailable(" in body
        )
        assert reads_it, (
            "{} decides what to show from struck_now but never distinguishes "
            "the unavailable case, so a material with no FEA preset reads as "
            "a failure or as a missing run".format(name)
        )
    # The two that print words must print the SAME words: they are on screen
    # at the same time, describing the same state.
    for name in ("updateHud", "layerAvailability"):
        assert "not available for this material" in _function_body(js, name), (
            "{} must use the wording the other reader already prints on the "
            "same screen".format(name)
        )
    # And layerAvailability must not send a user to run something that has
    # already run and can never change the answer.
    availability = _function_body(js, "layerAvailability")
    unavailable_at = availability.index("stagingUnavailable()")
    stale_at = availability.index("until a staged run exists")
    assert unavailable_at < stale_at, (
        "the unavailable case must be decided before the fallback that "
        "tells the reader to wait for a staged run"
    )
    # The helper must read the staging document, not the material name: the
    # list of materials with no FEA preset lives in staging.py and a copy of
    # it here would be a second source of truth for it.
    helper = _function_body(js, "stagingUnavailable")
    assert "state.bundle.staging" in helper
    for material in ("brick", "tile", "stone"):
        assert '"{}"'.format(material) not in helper, (
            "the viewer must not carry its own copy of staging.py's "
            "FEA_MATERIALS list"
        )

    # ------------------------------------------------------------------
    # Second pass, same wave. finalStage() is null for three different
    # reasons, not two: no staging at all, a material with no preset (the
    # case pinned above), or a staged run that reached a real solver and
    # came back with converged false. That third state fell through to the
    # "no staging at all" branches -- advice to run a staged analysis that
    # has already run and whose answer can never change. Every state below
    # is checked against all three readers, not only the one each fix was
    # sent to correct.
    hud_body = _function_body(js, "updateHud")
    pulse_body = _function_body(js, "applyPulse")

    # State 1: a converged stage exists, so there is a real per-node field
    # to colour with.
    assert "if (stage) return { on: true };" in availability
    assert "struck && struck.converged" in hud_body
    assert '"struck now: stands' in hud_body
    assert "good ? 0x1a3a1a" in pulse_body

    # State 2: staging ran but the final stage has no per-node field,
    # either because the material has no preset or because the solve did
    # not converge. layerAvailability must say which, in updateHud's own
    # words ("no equilibrium found"), and the gate must be the presence of
    # a staged run, not the numeric value of any field on it.
    assert "staging.stages && staging.stages.length" in availability
    assert "no equilibrium found on the last staged run" in availability
    assert "no equilibrium found" in hud_body
    not_converged_peaks_at = availability.index(
        'why: "peaks only: no equilibrium found on the last staged run"')
    not_converged_off_at = availability.index(
        'why: "no equilibrium found on the last staged run, and no verification data"')
    assert unavailable_at < not_converged_peaks_at < not_converged_off_at < stale_at, (
        "both staged-but-no-field readings (no preset, not converged) must "
        "be decided before the fallback that assumes no staging exists at "
        "all, or a finished non-converging run reads as a missing one"
    )

    # State 3: no staging at all. Verification peaks if a file is present,
    # nothing otherwise; neither wording claims a run exists.
    assert 'why: "peaks only until a staged run exists"' in availability
    assert 'why: "no staging and no verification data"' in availability
    staging_guard_at = hud_body.index(
        "if (staging && staging.stages && staging.stages.length)")
    struck_line_at = hud_body.index("let struckLine")
    assert staging_guard_at < struck_line_at, (
        "updateHud must never compute a struck-now line when there is no "
        "staged run to read one from"
    )


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
    assert '"falsework", "Formwork"' in js
    assert "opacity: 0.3" in js
    assert "wireMaterial.transparent = true" in js
    assert "nodeMaterial.transparent = true" in js


def test_analysis_overlays_cast_no_shadows():
    # The thrust wires sit hidden inside the closed shell once the vault is
    # complete, but shadow maps ignore both occlusion and material opacity,
    # so they cast a crisp grid through the shell onto the ground: the
    # shadow of an invisible thing. The net is a diagram, not a scene
    # object; it casts nothing. The formwork ghost already casts nothing
    # (castShadow was never set on it), now as policy rather than accident.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "wires.castShadow = nodes.castShadow = false" in js
    assert "falsework.castShadow" not in js
    # The real objects keep casting.
    build_body = _function_body(js, "buildPieceMeshes")
    assert "mesh.castShadow = mesh.receiveShadow = true" in build_body


def test_the_finished_shell_has_its_own_toggle():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"shell", "Finished shell"' in js
    assert "shell: true" in js, "the layer defaults on"
    scene_body = _function_body(js, "applySceneAtTime")
    assert "state.layers.shell" in scene_body, (
        "the timeline recomputes every casting's visibility, so the gate "
        "must live inside it or a scrub would undo the toggle"
    )
    layer_body = _function_body(js, "setLayer")
    assert '"shell"' in layer_body


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
    # The freeing itself lives in disposeWiresAndNodes, which buildScene
    # calls too: a study load replaces the network just as a size slider
    # does, and since the rings slider started reloading, that is every ring
    # change as well.
    assert "disposeWiresAndNodes()" in body, "a rebuild must free the old network"
    dispose_start = js.index("function disposeWiresAndNodes(")
    dispose_body = js[dispose_start:js.index("\n}", dispose_start)]
    assert "geometry.dispose()" in dispose_body, "a rebuild must dispose the old geometry"
    assert "material.dispose()" in dispose_body, "a rebuild must dispose the old material"
    # FINDING 2 (GPU leak): in three 0.185, InstancedMesh.dispose() is what
    # frees the instanceMatrix/instanceColor GPU buffers; disposing only the
    # geometry and material leaks them on every slider drag.
    assert "object.dispose()" in dispose_body, (
        "a rebuild must dispose the InstancedMesh itself"
    )
    build_start = js.index("function buildScene(")
    assert "disposeWiresAndNodes()" in js[build_start:js.index("\n}", build_start)]
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


def test_the_size_slider_reloads_the_study_rather_than_recutting_locally():
    # C1, carried forward from the ring/wedge binning wave 6 replaces: the
    # pieces the viewer draws are built server-side at the BUNDLE's own
    # size and are looked up in state.segmentIndex by the key the cut gave
    # them. A client-side re-cut at the slider's value rebuilds the index
    # around different cells, so drawn pieces are left holding keys the
    # index has never heard of, and applySceneAtTime throws on the first
    # missing one; while playing that throw escapes frame() before its
    # trailing requestAnimationFrame, so the render loop never restarts.
    # The slider must take the thickness slider's shape instead.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    input_start = js.index('getElementById("size-slider").addEventListener("input"')
    input_body = js[input_start:js.index("\n});", input_start)]
    assert "size-value" in input_body, "input must still move the live label"
    for forbidden in ("applyCut", "loadStudy", "state.size ="):
        assert forbidden not in input_body, (
            "the size slider must not {} on every input event".format(forbidden)
        )
    change_start = js.index('getElementById("size-slider").addEventListener("change"')
    change_body = js[change_start:js.index("\n});", change_start)]
    assert "state.size = +e.target.value" in change_body
    assert "scheduleReload()" in change_body, (
        "the piece size is a property of the bundle: committing it goes "
        "through the settle timer, which reloads the study server-side"
    )
    assert "loadStudy(" not in change_body, (
        "the commit itself must not fire a cut; stepping a slider five "
        "times costs one request, after the settle window"
    )


def test_the_client_side_cut_follows_the_loaded_bundle_not_the_slider():
    # The other half of C1: even with the handler fixed, a mid-drag slider
    # must not be able to desynchronise the segment index from the drawn
    # pieces, so the cut is derived from the bundle itself.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function applyCut(preserve)" in js, "applyCut carries the preserve flag through, never a size"
    for call in re.findall(r"applyCut\(([^)]*)\)", js):
        assert call.strip() in ("", "preserve"), (
            "applyCut must never be handed a size; it reads the loaded "
            "bundle's own size and at most threads the preserve flag"
        )
    start = js.index("function applyCut(")
    body = js[start:js.index("\n}", start)]
    assert "state.bundle.size" in body, (
        "the cut must come from the loaded bundle's own size"
    )
    assert "e.target.value" not in body
    # The index the timeline looks a casting up in has to be keyed by the
    # PIECE's key: pieces.py emits exactly one casting per cell of the cut
    # tessellation, so the cell's own key is the piece's identity too.
    assert "state.bundle.pieces.forEach" in body


def test_applycut_writes_the_piece_and_course_counts_it_reads():
    # Nothing previously asserted that the piece-count/course-count writes
    # actually come from the bundle: test_the_size_control_replaces_the_
    # ring_slider only checks the elements exist in the page. If applyCut
    # stopped writing them, both would sit at their static HTML zero and
    # the suite would stay green.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applyCut(")
    body = js[start:js.index("\n}", start)]
    assert (
        'getElementById("piece-count").textContent = state.bundle.pieces.length'
        in body
    )
    assert (
        'getElementById("course-count").textContent = '
        'state.bundle.tessellation.courses' in body
    )


def test_applycut_only_adopts_a_usable_size_in_range():
    # Task 8 fix round 1, C1: an authored cut's target_size can be None, and
    # bundle.py's own top level "size" field is now fixed to always report
    # the REQUESTED size instead -- but a client that trusts a server value
    # blindly is exactly how that class of bug reached the screen. applyCut
    # must only adopt a usable number in the API's own range, as a second
    # line of defence independent of the server side fix.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "SIZE_MIN = 0.3" in js and "SIZE_MAX = 3.0" in js
    start = js.index("function applyCut(")
    body = js[start:js.index("\n}", start)]
    guard_start = body.index("if (typeof size")
    guard_line = body[guard_start:body.index("{", guard_start) + 1]
    assert "Number.isFinite(size)" in guard_line
    assert "size >= SIZE_MIN" in guard_line and "size <= SIZE_MAX" in guard_line
    guarded = body[guard_start:body.index("\n  }", guard_start)]
    assert "state.size = size" in guarded, (
        "adopting state.size must be inside the range guard, not before it"
    )


def test_applycut_only_adopts_a_pattern_the_server_offers():
    # Task 8 deliberately left this half of C1 open: applyCut synced
    # state.size from the loaded bundle but not state.pattern, so selecting
    # sprayed concrete kept sending whatever pattern the client last held
    # rather than the bundle's own. Same defence as the size guard: only a
    # pattern the server actually offers is adopted, an authored cut's
    # pattern name is not trusted blindly.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applyCut(")
    body = js[start:js.index("\n}", start)]
    guard_start = body.index("if (typeof pattern")
    guard_line = body[guard_start:body.index("{", guard_start) + 1]
    assert "state.patterns" in guard_line and "includes(pattern)" in guard_line
    guarded = body[guard_start:body.index("\n  }", guard_start)]
    assert "state.pattern = pattern" in guarded, (
        "adopting state.pattern must be inside the guard, not before it"
    )


def test_pieces_are_built_at_the_bundles_thickness():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "fields.js" in js, "studio.js must import the pure fields module"
    start = js.index("function buildPieceMeshes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "state.bundle.provenance.thickness" in body, (
        "pieces must be offset at the thickness the bundle was actually built at"
    )
    for name in ("boxUVs", "segmentUVOffset"):
        assert name in body, "buildPieceMeshes lost {}".format(name)
    assert "basePositions" in body


def test_rebuilding_the_shell_frees_what_it_replaces():
    # The shell is rebuilt on every joint gap and taper commit, and
    # recoloured on every layer toggle, so both paths have to free what they
    # drop. rebuildWiresAndNodes already documents and does exactly this for
    # the thrust network.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function disposeShell(")
    body = js[start:js.index("\n}", start)]
    assert "segment.geometry.dispose()" in body and "segment.material.dispose()" in body, (
        "a shell rebuild must dispose the geometries and materials it replaces"
    )
    for caller in ("function buildPieceMeshes(", "function buildScene("):
        caller_body = js[js.index(caller):js.index("\n}", js.index(caller))]
        assert "disposeShell()" in caller_body, (
            "{} replaces the shell, so it must free the old one".format(caller)
        )
    recolour_start = js.index("function recolourSegments(")
    recolour_body = js[recolour_start:js.index("\n}", recolour_start)]
    assert "previous.dispose()" in recolour_body, (
        "recolouring must dispose the material it discards"
    )


def test_recolour_consumes_the_piece_metadata():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function recolourSegments(")
    end = js.index("\n}", start)
    body = js[start:end]
    # A cut piece vertex is not a mesh vertex, so a field is read through
    # its weights, not a bare index; buildPieceMeshes stores them as
    # userData.weights (see test_the_viewer_samples_fields_through_weights).
    assert "userData.weights" in body
    assert "userData.surface" in body
    assert "userData.basePositions" in body


def test_stress_smoothing_is_wired_and_per_surface_is_the_default():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '<option value="per" selected>' in html
    assert "smoothStressField" in js and "interpolateScalarField" in js
    body = _function_body(js, "recolourSegments")
    # Per-surface mode picks the field by the corner's own skin.
    # buildPieceMeshes writes userData.surface as `index < count ? 1 : -1`
    # and nothing else, so a corner is always top or bottom: the two field
    # branch below is exhaustive over what that attribute can hold. The
    # "per" branch used to smooth a third, "worst", field for a case no
    # corner could reach -- a full smoothing pass plus an interpolation
    # onto every render vertex, on every recolour, read by nobody.
    assert "surfaceOf[i] === 1 ? topField : bottomField" in body, (
        "per-surface mode must pick the field by skin"
    )
    assert "smooth(\"worst\")" not in body, (
        "the per-surface branch must not smooth a field no corner reads; "
        "the stress-surface control's own worst option comes through "
        "pickedField, which is read"
    )
    # That control's option must still work: it goes through pickedField.
    assert '<option value="worst"' in html
    assert "pickedField = smooth(surface)" in body


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


def test_transport_is_pause_and_restart_only():
    # The Stop button duplicated Pause (halting) plus Restart (rewind); it
    # is gone. Restart still rewinds and plays; the scrubber covers rewind
    # without playing.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="stop-button"' not in html
    assert 'getElementById("stop-button")' not in js
    assert 'id="play-button"' in html and 'id="restart-button"' in html
    restart_start = js.index('getElementById("restart-button")')
    restart_body = js[restart_start:js.index("\n});", restart_start)]
    assert "applyTimeline(0)" in restart_body
    assert "playing = true" in restart_body


def test_the_cra_badge_is_gone_and_the_pulse_and_hud_no_longer_need_it():
    # Owner ruling, mid wave 6: the CRA verdict is a constant popup, and the
    # studio is always working to funicular form, so proving it stands is
    # not the question -- the form finding already guarantees compression
    # only equilibrium by construction, and separately no size the API
    # permits can bring a real study under the rigid block budget any more.
    # The badge, and every place that made the pulse or the HUD depend on
    # it, are gone. craVerdict() itself survives: the Data panel still reads
    # it where a study happens to carry a verdict (see
    # test_data_panel_reports_the_cra_verdict_with_provenance).
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="cra-badge"' not in html
    for class_name in ("cra-stands", "cra-fails", "cra-unknown"):
        assert class_name not in css
    assert "function craVerdict(" in js
    assert "function updateCraBadge(" not in js
    pulse_start = js.index("function applyPulse(")
    pulse_end = js.index("\n}", pulse_start)
    assert "cra.stands" not in js[pulse_start:pulse_end], (
        "the pulse must pulse on the FEA solve alone, as it did before the "
        "CRA wave"
    )
    hud_start = js.index("function updateHud(")
    hud_end = js.index("\n}", hud_start)
    assert "CRA:" not in js[hud_start:hud_end]
    build_start = js.index("function buildScene(")
    build_end = js.index("\n}", build_start)
    assert "updateCraBadge()" not in js[build_start:build_end]


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


def test_friction_provenance_is_keyed_by_material_not_by_value():
    # Stone's friction is 0.6, the same number staging.py gives concrete, so
    # a lookup keyed by the numeric mu value would attribute stone's dry
    # stone rigid block literature source to concrete's EN 1992-1-1 clause
    # 6.2.5 smooth precast joint. Keying by material name keeps the two
    # apart even though the numbers collide.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("const FRICTION_PROVENANCE = {")
    end = js.index("\n};", start)
    body = js[start:end]
    for material in (
        "concrete", "concrete-c50", "concrete-sprayed", "timber",
        "brick", "tile", "stone",
    ):
        assert '"{}"'.format(material) in body, (
            "FRICTION_PROVENANCE has no entry for {}".format(material)
        )
    assert '"0.6"' not in body and '"0.4"' not in body, (
        "FRICTION_PROVENANCE must not be keyed by the numeric mu value"
    )
    assert "dry stone" in body, "stone must carry its own sourced provenance"
    stone_start = body.index('"stone":')
    stone_line = body[stone_start:]
    assert "EN 1992-1-1" not in stone_line, (
        "stone must not read as sourced from the concrete precast joint clause"
    )
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    panel_body = js[panel_start:panel_end]
    assert "FRICTION_PROVENANCE[state.bundle.material]" in panel_body, (
        "the Data panel must look the provenance up by the loaded study's "
        "own material, not by the numeric verdict.mu it happens to carry"
    )


def test_the_data_panel_has_a_cut_section_with_every_measured_disclosure():
    # A cut that dropped analysis faces, missed a joint plane, or clamped a
    # point off the surface looks identical on screen to a clean one unless
    # every field bundle.py's tessellation summary carries reaches the
    # panel: orphan/double faces, the corner residual, the chord deviation,
    # clamped points, missing planes, and the rim wobble.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert "state.bundle.tessellation" in body
    assert '"Cut"' in body
    for field in (
        "tess.pattern", "tess.source", "tess.target_size",
        "tess.cells", "tess.courses",
        "tess.chord_mm", "tess.clamped_points",
        "tess.missing_planes", "tess.rounds", "tess.limit",
        "tess.backward_turn_degrees", "tess.backward_steps",
        # Final fix wave. The spec lists boundary sub-edges per piece,
        # before and after, under the measurements to report "in BENCH.md
        # and in the Data panel where the user can see them". The bundle
        # carried both the whole wave and the Cut section read neither,
        # which this enumeration is exactly why: it listed twelve fields
        # and omitted these two, so the omission stayed green.
        "tess.facets_per_piece", "tess.boundary_points_per_piece",
        # An authored cut whose cells carry no course puts every cell in
        # course 0, which drives the drop sequence, taperAt and the stage
        # mapping. The flag saying so shipped and reached no screen.
        "tess.courses_inferred",
        # A count with no magnitude cannot be read: the same 137 clamped
        # points are rounding noise or ten times the chord target
        # depending on how far they actually moved.
        "tess.clamped_max_m", "tess.clamped_median_m",
    ):
        assert field in body, "the Cut section must read {}".format(field)
    # The counts need denominators. "137 cap points clamped" and "137 of
    # 41265" are not the same statement, and neither are "0 orphan faces"
    # and "0 of 2400".
    assert "capPointCount(" in body, (
        "the clamped count must be quoted against the total cap points"
    )
    assert "analysis_mesh.faces.length" in body, (
        "the orphan and double face counts must be quoted against the "
        "number of analysis faces there are to orphan"
    )
    # A folded cell still ships a lobe of cap inside out. It enters none of
    # the coverage counts, so the list naming them is the only disclosure
    # there is, and it had no reader at all.
    assert "coverage.folded" in body, (
        "the Cut section must show the folded list beside the coverage report"
    )
    # The residual is disclosed as a sine; BENCH.md gives degrees too.
    assert "residualDegrees(" in body, (
        "the residual must be disclosed in degrees as well as as a sine"
    )
    coverage = ("orphan_faces", "double_faces", "open_facets", "slivers",
                "coverage_holes", "broken_boundary")
    for field in coverage:
        assert "coverage.{}".format(field) in body, (
            "the coverage report must disclose {}".format(field)
        )
    # Fix round 1: a single worst-corner number badly misrepresents the
    # cut, so the whole distribution has to reach the panel, not just the
    # max (tess.corner_residual on its own, kept only as the source of
    # stats.max, is no longer read directly here).
    assert "tess.corner_residual_stats" in body
    for field in (
        "stats.count", "stats.median", "stats.mean", "stats.p99",
        "stats.max", "stats.worst_corner_courses", "stats.over",
    ):
        assert field in body, (
            "the Cut section must read the residual distribution's {}, not "
            "only the single worst corner".format(field)
        )
    assert "median describes the cut" in body, (
        "the panel must say plainly that the median, not the max, "
        "describes the cut"
    )
    assert "rim course" in body, (
        "the panel must say the residual's worst corners cluster in the "
        "rim course, not just list numbers"
    )
    # An imported cut has to quote its own provenance verbatim and the
    # measured z offset, not the generated cut's target size.
    assert "tess.provenance" in body
    assert "tess.z_offset_max" in body
    # A cut piece vertex is not a render mesh vertex, so a heatmap value at
    # a point is an interpolated reading; that change in meaning has to be
    # named, not just left implicit in sampleScalar's own code.
    assert "interpolation" in body
    # The Cut section must render ahead of the verification early-out, the
    # same reason the CRA section does: it must show on a staged-but-
    # unverified study, not only once a verification run exists.
    cut_index = body.index("state.bundle.tessellation")
    verify_early_out = body.index("no verification run embedded yet")
    assert cut_index < verify_early_out, (
        "the Cut section must come before the verification early-return "
        "guard, or an unverified study never shows the cut's own disclosures"
    )


def test_the_data_panel_survives_a_bundle_cached_before_a_field_existed():
    # Final fix wave. corner_residual_stats landed late in the cutting wave
    # and REQUIRED_BUNDLE_KEYS did not name it, so a bundle cached earlier
    # in this branch's life was served as valid and the panel dereferenced
    # tess.corner_residual_stats.count on it. The throw escaped the Data
    # button's click handler AFTER content.innerHTML = "" and BEFORE
    # panel.classList.toggle("hidden"), so the button read as doing nothing
    # whatsoever. Every sub-field the Cut section reads must degrade to a
    # line rather than take the panel down with it.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "renderDataPanel")
    stats_at = body.index("const stats = tess.corner_residual_stats")
    guard = body[stats_at:stats_at + 400]
    assert "if (!stats)" in guard, (
        "the residual distribution must be guarded: a bundle cached before "
        "it existed has no corner_residual_stats to read a count off"
    )
    assert "not measured" in body, (
        "a missing sub-field must degrade to a line saying so, not to a "
        "panel that never opens"
    )
    # Same for the two spreads and the clamp magnitudes, which landed in
    # the same wave and are missing from the same caches.
    for guarded in ("if (fpp)", "if (bpp)", 'typeof tess.clamped_max_m === "number"'):
        assert guarded in body, (
            "{} must be guarded the same way: an older cache has neither "
            "the field nor a reason to crash the panel".format(guarded)
        )


def test_the_hud_and_the_size_control_do_not_call_an_authored_size_a_target():
    # bundle.py is explicit that document["size"] is the REQUESTED size and
    # that an authored (imported) cut ignores it entirely -- its own
    # target_size is None. The Data panel says so in as many words; the HUD,
    # which is what a user reads during playback, printed "900 mm target"
    # for an imported cut anyway, and applyCut wrote the same number into
    # the size control's own label.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="size-units"' in html, (
        "the size label needs its units in their own span, or the authored "
        "case cannot correct them without garbling the number"
    )
    for name in ("updateHud", "applyCut"):
        body = _function_body(js, name)
        assert 'source === "imported"' in body, (
            "{} must branch on whether the cut is authored before quoting "
            "the requested size as a target".format(name)
        )
        assert "size control is not used" in body, (
            "{} must say the size control is not used by an authored "
            "cut".format(name)
        )


def test_a_finished_run_restores_the_material_note_with_the_material():
    # applyRunParamsToControls assigns material-select.value directly, which
    # fires no change event, and the change handler is the only other writer
    # of pattern-note. So: load in limestone with the note showing, click
    # Run, switch material mid-run, let the run finish -- the material is
    # restored and the stone vault is drawn with the note gone, which is the
    # exact failure the note exists to prevent.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "applyRunParamsToControls")
    assert "pattern-note" in body, (
        "restoring the material must restore its honesty note, since "
        "assigning .value fires no change event"
    )
    assert "state.patternNotes[material]" in body
    # The note only. updatePatternForMaterial also forces the material's
    # default pattern, and calling it here would overwrite the pattern this
    # run actually solved with.
    assert "updatePatternForMaterial(" not in body, (
        "the note only: forcing the material's default pattern here would "
        "overwrite the pattern the finished run actually used"
    )


def test_the_run_status_says_cutting_rather_than_stage_zero_of_zero():
    # run["of"] is the number of stages, which is the number of courses the
    # cut produces, so it is 0 until the cut finishes. "stage 0 of 0" reads
    # as a run with nothing to do.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "watchRun")
    assert "run.of ?" in body, "the zero case must be branched on"
    assert "cutting" in body


def test_a_refused_run_reports_the_reason_the_server_gave():
    # app.py 400s a size outside the slider's range, a thickness outside
    # 0.05 to 0.5 m, and a material or pattern it does not offer, each
    # naming what to use instead. Without an ok check the refusal body has
    # no "run" key, watchRun polls /api/runs/undefined, that 404s, and the
    # user is told "lost contact with the server" instead.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "startRun")
    assert "response.ok" in body, (
        "startRun must check the response before watching a run id the "
        "refusal body does not carry"
    )
    assert "body.detail" in body, "the server's own reason must be shown"


def test_the_legend_does_not_sit_on_top_of_the_hud():
    # Both were anchored left: 16px; bottom: 16px, so turning a heatmap on
    # covered the last lines of the HUD -- and the HUD gained the struck-now
    # line in this branch, which is the line a heatmap is most likely to be
    # read against.
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    hud = css[css.index("#hud {"):css.index("}", css.index("#hud {"))]
    legend = css[css.index("#legend {"):css.index("}", css.index("#legend {"))]
    hud_left = "left: 16px" in hud
    legend_left = "left: 16px" in legend
    assert not (hud_left and legend_left), (
        "#hud and #legend must not share an anchor corner"
    )


def test_the_data_panel_says_the_verdict_is_on_a_faceted_model():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert "faceted" in body
    assert "planar" in body or "flat" in body
    # I3: every figure this paragraph used to quote came from
    # bench/scripts/cra_acceptance.py comparing voussoirs.segment_voussoirs
    # against blocks.segment_blocks, the mesh-following prisms the viewer
    # drew at the time. This branch replaced the drawn piece in exactly the
    # dimension those numbers measured: boundary vertices are projected
    # onto flat joint planes, the casting is shrunk by the joint gap, and
    # the crown taper can thin it by half. Quoting them as a distance to
    # what is on screen is a precision the code can no longer support.
    for stale in ("2.389", "1.964", "2.4 m", "51.3", "17.3", "63.7", "12.9", "29.5"):
        assert stale not in body, (
            "{} was measured against a drawing this branch replaced".format(stale)
        )
    # The disclosure itself must not quietly vanish with the numbers. It
    # still has to name what the analysis model does to the surface, which
    # way each error runs, that the segmentation drives both, and where the
    # measurement that does exist was taken.
    assert "slightly" not in body, "the gap is measured, not a rounding error"
    assert "less volume" in body
    assert "coarsens" in body or "ring count" in body
    assert "joint gap" in body and "taper" in body, (
        "the reason a figure would be false is that the drawn casting moved"
    )
    assert "mesh-following block model" in body and "docs/BENCH.md" in body, (
        "the surface actually measured has to be named"
    )


def test_skipped_pieces_are_reported_in_the_data_panel():
    # The badge this used to also check is gone (see
    # test_the_cra_badge_is_gone_and_the_pulse_and_hud_no_longer_need_it);
    # the Data panel still names any piece the rigid-block model could not
    # cover, on the studies that still carry a CRA verdict at all.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    panel_body = js[panel_start:panel_end]
    assert "cra_skipped" in panel_body
    assert "absent from the rigid-block model" in panel_body


def test_the_skipped_piece_sentence_does_not_use_retired_ring_and_wedge_words():
    # Task 8 fix round 1: voussoirs.py keeps entry.ring/entry.wedge as its
    # own internal field names (ring is the course index, wedge the piece's
    # position within it, not a ring/wedge polar bin), unrenamed by Task 7's
    # own ruling. The sentence a user reads must not repeat those retired
    # words even though the field access underneath is unchanged.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    assert '"ring ' not in body, (
        "the studio no longer has a ring/wedge binning; the prose must not "
        "name it"
    )
    assert '"wedge ' not in body
    assert "entry.ring" in body and "entry.wedge" in body, (
        "only the prose changes; the field access stays voussoirs.py's own"
    )
    assert "course " in body and "piece " in body


def test_the_data_panel_shows_nothing_when_there_is_no_cra_verdict():
    # The owner does not want a popup, and does not want an empty section
    # either: with run_staging's include_cra defaulting to False, most
    # studies carry no cra entry on their final stage at all, and the panel
    # must say nothing about CRA in that case rather than rendering a bare
    # heading.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    panel_start = js.index("function renderDataPanel(")
    panel_end = js.index("\n}", panel_start)
    body = js[panel_start:panel_end]
    verdict_start = body.index("const verdict = craVerdict();")
    guard = body[verdict_start:body.index("{", verdict_start) + 1]
    assert re.search(r"if\s*\(\s*verdict\s*\)\s*\{", guard), (
        "the whole CRA section, heading included, must be conditional on a "
        "real verdict, not rendered with a 'no CRA run yet' filler"
    )
    assert "no CRA run yet" not in body


def test_piece_shading_uses_crease_angle_normals():
    # The piece geometry is unindexed triangle soup, so computeVertexNormals
    # gives one flat normal per facet and the caps light up banded. The
    # crease-angle helper smooths within each surface while the cap-to-side
    # edges stay hard. Both builders of piece positions must use it: the
    # initial build and the recolour pass that displaces for deflection.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("buildPieceMeshes", "recolourSegments"):
        body = _function_body(js, name)
        assert "creaseNormals(" in body, "{} must use crease normals".format(name)
        assert "computeVertexNormals" not in body, (
            "{} must not flat-shade the soup".format(name)
        )


def test_the_viewer_draws_bundle_pieces_and_opens_a_joint():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="joint-gap"' in html and 'id="joint-gap-value"' in html
    assert "function buildPieceMeshes(" in js
    assert "state.bundle.pieces" in js
    assert "state.jointGap" in js
    assert "function buildSegmentMeshes(" not in js, "the old extruder is retired"
    # The shrink is proportional: a casting is scaled toward its own
    # centroid, so only its farthest vertex moves the full half gap and
    # everything nearer the middle moves less. A bare millimetre figure
    # overstates what happens at the rest of the joint.
    label = html[html.index('id="joint-gap"'):html.index("</label>", html.index('id="joint-gap"'))]
    assert "widest" in label and "less" in label


def test_the_joint_gap_is_marked_inert_where_it_does_nothing():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="joint-gap-note"' in html
    start = js.index("function updateMaterialControls(")
    body = js[start:js.index("\n}", start)]
    assert "sprayedMaterial()" in body
    assert 'getElementById("joint-gap").disabled' in body, (
        "buildPieceMeshes forces the gap to zero under sprayed concrete, so "
        "the slider must not stay live and labelled in millimetres"
    )
    assert "joint-gap-note" in body, "a disabled control has to say why"
    build_start = js.index("function buildScene(")
    assert "updateMaterialControls()" in js[build_start:js.index("\n}", build_start)], (
        "the availability must be recomputed whenever the material changes"
    )
    # The crown taper is NOT disabled, and that is deliberate: taperAt has
    # no material branch, so the taper thins crown castings under sprayed
    # concrete exactly as it does under the precast presets. Marking a
    # control that works as inert would be its own dishonesty.
    assert 'getElementById("taper").disabled' not in js


def test_each_piece_gets_its_own_tint_and_keeps_it():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function buildPieceMeshes(")
    body = js[start:js.index("\n}", start)]
    assert "segmentUVOffset(" in body, "per piece UVs keep castings from matching"
    assert "pieceMaterial(piece.key)" in body
    tint_start = js.index("function pieceMaterial(")
    tint_body = js[tint_start:js.index("\n}", tint_start)]
    assert "pieceTint(" in tint_body and "offsetHSL" in tint_body
    # I1: the tint used to be applied once at build time, and every caller
    # of buildPieceMeshes calls recolourSegments straight afterwards. With
    # no heatmap layer on at first load, recolourSegments' own branch
    # reassigned a fresh untinted clone, so "no two castings look
    # identical" never once reached the screen. The tint has to be a
    # property of the piece, recomputed from its key wherever the material
    # is handed out.
    recolour_start = js.index("function recolourSegments(")
    recolour_body = js[recolour_start:js.index("\n}", recolour_start)]
    assert "pieceMaterial(segment.userData.key)" in recolour_body, (
        "recolouring must restore the piece's own tinted material"
    )
    assert "materials.concrete).clone()" not in recolour_body, (
        "a bare registry clone here discards the per casting tint"
    )


def test_sprayed_concrete_has_no_joints_at_all():
    # Sprayed concrete is monolithic, so opening a joint between pieces
    # would be a lie about how it is built.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function buildPieceMeshes(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "sprayedMaterial() ? 0 : state.jointGap" in body
    tint_start = js.index("function pieceMaterial(")
    tint_body = js[tint_start:js.index("\n}", tint_start)]
    assert "if (!sprayedMaterial()) own.color.offsetHSL" in tint_body, (
        "the per piece tint must be suppressed for a continuous surface"
    )


def test_the_net_inflates_before_the_build():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="inflate-seconds"' in html
    assert "function inflationFactor(" in js
    start = js.index("function applySceneAtTime(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert "inflationFactor(" in body, "inflation is part of the pure timeline"
    for clock in ("performance.now", "Date.now", "requestAnimationFrame"):
        assert clock not in body
    # At t = 0 exactly, a scale of 0 makes the model matrix singular and the
    # net renders unlit, which is frame 0 of every recording. Floored the
    # same way the sprayed growth is.
    inflation_start = js.index("function applyInflation(")
    inflation_body = js[inflation_start:js.index("\n}", inflation_start)]
    assert "Math.max(0.001" in inflation_body, (
        "the inflation scale must be floored, never exactly zero"
    )


def test_no_piece_shows_while_the_net_is_still_inflating():
    # Reviewer finding: build clamps to 0 for the whole inflation window, so
    # the first casting's drop window (start 0) was already true at build 0
    # -- it hung motionless at DROP_HEIGHT in mid-air while the net was still
    # finding its form. The piece loop must gate on inflation being complete
    # BEFORE the drop-window arithmetic runs, and that gate must reference
    # the inflation factor itself, not a hardcoded number standing in for it.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function applySceneAtTime(")
    end = js.index("\n}", start)
    body = js[start:end]
    loop_start = body.index("for (const segment of state.objects.shell.children)")
    arithmetic_start = body.index(
        "const position = state.segmentIndex.get", loop_start)
    gate = body[loop_start:arithmetic_start]
    assert "inflate" in gate, (
        "the piece loop must gate on the inflation factor, computed from t, "
        "before it ever reaches the drop-window arithmetic"
    )
    assert "segment.visible = false" in gate, (
        "while inflating, every piece must be hidden outright, not just "
        "left at its default drop position"
    )


def test_the_material_presets_read_apart():
    """Closest pair luminance, keyed by name so inserting a preset cannot
    silently move which four are measured."""

    source = (STATIC / "studio.js").read_text(encoding="utf-8")
    colours = dict(re.findall(r'"?([a-z0-9-]+)"?:\s*new THREE\.MeshPhysicalMaterial\(\{\s*\n?\s*color: 0x([0-9a-f]{6})', source))
    wanted = ["concrete", "concrete-c50", "concrete-sprayed", "timber",
              "brick", "tile", "stone"]
    assert all(name in colours for name in wanted)
    values = {name: _luminance(colours[name]) for name in wanted}
    pairs = [(abs(values[a] - values[b]), a, b)
             for i, a in enumerate(wanted) for b in wanted[i + 1:]]
    assert min(pairs)[0] > 4.0, min(pairs)


def test_the_pattern_control_says_what_is_not_built_yet():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="pattern-select"' in page
    assert 'id="pattern-note"' in page


def test_taper_is_a_drawing_parameter_and_the_hud_says_so():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="taper"' in html and 'id="taper-value"' in html
    assert "function taperAt(" in js
    hud_start = js.index("function updateHud(")
    hud_end = js.index("\n}", hud_start)
    body = js[hud_start:hud_end]
    assert "state.taper" in body
    assert "uniform thickness" in body, "the HUD must say the analysis did not taper"


def test_every_clock_reads_the_drop_order_at_the_same_rate():
    # The polish wave replaced the per-piece drop-speed model with a
    # constant total build: placementStep() derives the stagger from the
    # count, so the build takes BUILD_TARGET_SECONDS whatever the cut and
    # pieces overlap in flight. The three consumers stay in step by all
    # reading the one helper, which is the property the old arithmetic pin
    # existed to protect. The sprayed half-window special case died with
    # the derived stagger: overlap now comes free for every material.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    helper = _function_body(js, "placementStep")
    assert "BUILD_TARGET_SECONDS / Math.max(1, placementCount())" in helper
    assert "sprayedMaterial" not in helper, (
        "the stagger no longer branches on material"
    )
    for name in ("applySceneAtTime", "timelineDuration", "currentStageIndex"):
        assert "placementStep()" in _function_body(js, name), (
            "{} must read the stagger from the one helper".format(name)
        )
    # The per-piece fall time is a constant now; the old user setting and
    # every mention of it are gone, comments included.
    assert "dropSeconds" not in js
    assert re.search(r"DROP_SECONDS = 0\.8\b", js)
    assert re.search(r"BUILD_TARGET_SECONDS = 35\b", js)
    # Replay the old C2 scenario arithmetically on the new model, at a
    # small and a large count: the build is constant, the scrubber range
    # covers the last landing, and by the end of the build the stage
    # readout has counted every casting.
    for placements in (38, 1200):
        step = 35 / max(1, placements)
        assert abs(placements * step - 35) < 1e-9, "the build must be constant"
        lands = (placements - 1) * step + 0.8
        build_end = placements * step + 0.8
        assert build_end >= lands
        assert int(build_end // step) >= placements, (
            "at the end of the build the readout must count every casting"
        )


def test_sprayed_concrete_grows_about_its_own_centroid():
    # I2: piece geometry is in absolute world coordinates and the mesh sits
    # at the origin, so a bare scale.z scales about z = 0. On Trial 2 the
    # crown castings sit 6.85 m up, and they were drawn as slivers lying on
    # the ground stretching vertically through the falsework to their true
    # height. Sprayed concrete thickens where it is sprayed, so the growth
    # is taken about the piece's own centroid.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    build_start = js.index("function buildPieceMeshes(")
    build_body = js[build_start:js.index("\n}", build_start)]
    assert "userData.centreZ" in build_body, (
        "each piece must record its own centroid height at build time"
    )
    start = js.index("function applySceneAtTime(")
    body = js[start:js.index("\n}", start)]
    assert "sprayedMaterial()" in body
    assert "DROP_HEIGHT" in body, "other materials still drop"
    sprayed_branch = body[body.index("if (sprayed) {"):body.index("} else {", body.index("if (sprayed) {"))]
    assert "userData.centreZ * (1 - grown)" in sprayed_branch, (
        "growth must compensate the position, or the casting is dragged "
        "down to z = 0 and stretched back up"
    )
    drop_branch = body[body.index("} else {", body.index("if (sprayed) {")):]
    assert "segment.scale.set(1, 1, 1)" in drop_branch and "segment.position.z" in drop_branch, (
        "the drop branch must reset both scale and position, so switching "
        "material cannot leave stale growth state behind"
    )


def test_the_four_materials_are_visually_distinct():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("const materials = {")
    end = js.index("\n};", start)
    body = js[start:end]
    # Keyed on the preset names, not sliced off the front of the registry:
    # by position, inserting a preset before timber would silently measure
    # the wrong four and this test would go on passing.
    values = []
    for name in ("concrete", "concrete-c50", "concrete-sprayed", "timber"):
        match = re.search(
            r'"?{}"?: new THREE\.MeshPhysicalMaterial\(\{{\s*color: (0x[0-9a-fA-F]{{6}})'.format(
                re.escape(name)),
            body)
        assert match, "the {} preset is missing or has no colour".format(name)
        values.append(int(match.group(1), 16))
    assert len(set(values)) == 4, "the presets must not share a colour"

    def luminance(v):
        return 0.2126 * ((v >> 16) & 255) + 0.7152 * ((v >> 8) & 255) + 0.0722 * (v & 255)

    # Overall spread is the wrong measure: today's three concretes sit
    # within a point of each other while white timber stretches the range,
    # so the range alone would pass. What matters is that no PAIR is close.
    closest = min(
        abs(luminance(values[i]) - luminance(values[j]))
        for i in range(len(values)) for j in range(i + 1, len(values))
    )
    assert closest > 15, (
        "two presets sit {:.0f} apart in luminance and will read as the "
        "same material".format(closest)
    )


def test_timeline_speed_is_a_playback_rate_outside_the_pure_timeline():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="timeline-speed"' in html and 'id="timeline-speed-value"' in html
    assert 'id="drop-speed"' not in html
    frame_body = _function_body(js, "frame")
    assert "delta * state.timeline.speed" in frame_body
    for name in ("applyTimeline", "applySceneAtTime"):
        assert "state.timeline.speed" not in _function_body(js, name), (
            "the rate lives in how fast callers advance t; {} must stay "
            "pure in t".format(name)
        )
    record_start = js.index("async function recordAnimation(")
    record_body = js[record_start:js.index("\n}", record_start)]
    assert "timelineDuration() / speed * fps" in record_body


def test_the_inflation_slider_labels_its_seconds():
    # The bare " s" after the inflation input wrapped onto its own line in
    # the panel. The unit rides with a live value now, like the mm sliders.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="inflate-value"' in html
    label = html[html.index("Inflation"):html.index("</label>", html.index("Inflation"))]
    assert "</span> s" in label
    assert 'getElementById("inflate-value")' in js


def test_slider_commits_settle_and_requests_cannot_race():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "RELOAD_SETTLE_MS = 1500" in js
    schedule_body = _function_body(js, "scheduleReload")
    assert "clearTimeout" in schedule_body and "setTimeout" in schedule_body
    assert "loadStudy(" in schedule_body
    assert "requestMatchesLoaded(" in schedule_body, (
        "a commit that matches the loaded bundle must not fire a request"
    )
    for control_id in ("size-slider", "thickness-input"):
        change_start = js.index(
            'getElementById("{}").addEventListener("change"'.format(control_id))
        change_body = js[change_start:js.index("\n});", change_start)]
        assert "scheduleReload()" in change_body, control_id
    load_start = js.index("async function loadStudy(")
    load_body = js[load_start:js.index("\n}", load_start)]
    assert "++state.loadSequence" in load_body
    assert "sequence !== state.loadSequence" in load_body, (
        "a stale response must be dropped, not land over a newer one"
    )
    assert "cut-status" in load_body, "the cut in flight must be visible"
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="cut-status"' in html
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#cut-status" in css


def test_an_explicit_pattern_choice_survives_material_changes():
    # Changing material used to force-write that material's default
    # pattern, so timber plus monolithic bands silently became timber plus
    # bonded courses. The honesty note is written on every material
    # change; the default pattern only while no explicit choice was made.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "patternChosen: false" in js
    select_start = js.index('getElementById("pattern-select").addEventListener("change"')
    select_body = js[select_start:js.index("\n});", select_start)]
    assert "state.patternChosen = true" in select_body
    body = _function_body(js, "updatePatternForMaterial")
    assert "pattern-note" in body
    guard_at = body.index("if (!state.patternChosen)")
    default_at = body.index("state.patternDefaults[material]")
    assert guard_at < default_at, (
        "the default pattern must sit inside the not-chosen guard"
    )


def test_a_same_export_reload_preserves_the_viewing_state():
    # Changing material rebuilt the world: timeline to zero, playing off,
    # camera snapped to the orbit ring, so comparing materials at the
    # finished vault meant re-running the whole animation. A reload of the
    # SAME export now carries the viewing state across: the fraction of
    # the timeline (the honest mapping between two different drop
    # sequences), the playing flag, and the camera untouched, applied
    # through applySceneAtTime, never applyTimeline.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    load_start = js.index("async function loadStudy(")
    load_body = js[load_start:js.index("\n}", load_start)]
    assert "state.bundle.export === fresh.export" in load_body
    assert "state.timeline.t / timelineDuration()" in load_body, (
        "the fraction must be captured BEFORE buildScene replaces the "
        "bundle, or the old duration is unrecoverable"
    )
    assert "function rebuildTimeline(preserve)" in js
    rebuild_body = _function_body(js, "rebuildTimeline")
    assert "applySceneAtTime(preserve.f * timelineDuration())" in rebuild_body
    guard_at = rebuild_body.index("if (!preserve)")
    sync_at = rebuild_body.index("controls.target.copy(state.centre)")
    assert guard_at < sync_at, (
        "the camera target re-aim belongs to the full reset only"
    )
    preserve_at = rebuild_body.index("if (preserve)")
    tail = rebuild_body[preserve_at:rebuild_body.index("} else {", preserve_at)]
    assert "applyTimeline(" not in tail, (
        "the preserve branch must never call applyTimeline; that would "
        "move a user-positioned camera"
    )


def test_the_panel_groups_into_six_collapsible_sections():
    # Sections group by use, not by how the code grew: everything that
    # shows or hides lives in View, everything that moves in Animation,
    # and Scene is deliberately thin because the environment engine wave
    # grows there. Study, View and Animation open; the rest collapsed.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    positions = []
    for section_id, is_open in (
        ("study-section", True), ("view-section", True),
        ("animation-section", True), ("scene-section", False),
        ("import-section", False), ("record-section", False),
    ):
        at = html.index('id="{}"'.format(section_id))
        positions.append(at)
        tag = html[html.rindex("<details", 0, at):html.index(">", at) + 1]
        assert (" open" in tag) == is_open, section_id
    assert positions == sorted(positions), "sections out of order"
    assert "<h2>" not in html, "summaries are the section headers now"
    assert "<summary>Styling</summary>" in html, (
        "the layer styling controls nest collapsed inside View"
    )
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#panel summary" in css
