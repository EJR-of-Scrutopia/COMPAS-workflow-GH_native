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
        # Comments are not references. A stylesheet that cites where a
        # design token's value came from is documenting itself, and nothing
        # fetches a URL out of a comment; the claim this test defends is
        # that the studio works with no network, which is about what the
        # BROWSER loads.
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
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
    assert "NeutralToneMapping" in js


def test_the_renderer_uses_the_settings_r185_did_not_deprecate():
    """r185 deprecated one of these and made the other dishonest.

    PCFSoftShadowMap is downgraded to PCFShadowMap with a console warning,
    so asking for it buys nothing. ACESFilmicToneMapping opens its shader
    with `color *= toneMappingExposure / 0.6` and then applies a film-print
    curve that shifts saturated hues, which a material studio cannot use.
    Both must stay gone, and the exposure gain that compensates for ACES's
    hidden 1/0.6 must stay applied or the studio darkens by two thirds of a
    stop.
    """
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # The constants as USED, not as named. The comments beside those lines
    # explain what was wrong with the old settings and must go on saying so,
    # which a bare substring test would forbid.
    assert "THREE.PCFSoftShadowMap" not in js
    assert "THREE.ACESFilmicToneMapping" not in js
    assert "THREE.PCFShadowMap" in js
    assert "THREE.NeutralToneMapping" in js
    assert "const EXPOSURE_GAIN = 1 / 0.6;" in js
    assert js.count("EXPOSURE_GAIN") >= 4, (
        "the gain is declared once and applied at every exposure site: "
        "the viewport grade, the preview rig and the weather swatch"
    )


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
    # Rewritten: the old version checked these names were present ANYWHERE
    # in studio.js, which every one of them is for unrelated reasons
    # ("wires" and "shell" name scene objects throughout the file, not
    # layers) -- the assertion passed whether or not LAYERS itself agreed.
    # Read LAYERS' own literal and check it directly.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("const LAYERS = [") + len("const LAYERS = [")
    end = js.index("];", start)
    body = js[start:end]
    for name in ("stress", "deflection", "loads", "reactions", "overlays", "pulse", "forces"):
        assert '"{}"'.format(name) in body, "LAYERS is missing {}".format(name)
    for name in ("shell", "wires"):
        assert '"{}"'.format(name) not in body, (
            "{} is not a layer; the Show select owns it, not a checkbox".format(name)
        )
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
        # Re-pinned 2026-09-04: the hand-upload controls are gone with the
        # folder chooser (Param: "remove upload files by hand"). The status
        # line stays, because the folder chooser writes to it.
        "import-status", "folder-choose", "study-refresh",
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


def test_every_columns_reload_disposes_before_it_adds():
    # M1: boot() used to add a fresh columns group on every call with no
    # dispose, so each export-pair re-import (which calls boot()) stacked
    # another copy into the scene. Both call sites must route through the
    # same dispose-then-reload helper importColumns already modelled.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # Re-pinned 2026-09-04: importColumns is gone with the hand-upload
    # controls, but the finding it was written for is unchanged and now has
    # more callers, not fewer. Boot, a study load and a folder change all
    # reload the columns, and every one of them must dispose first.
    assert "async function reloadColumns(" in js
    assert "async function importColumns(" not in js
    reload_body = _function_body(js, "reloadColumns")
    assert "scene.remove(state.objects.columns)" in reload_body
    assert "state.objects.columns = null" in reload_body
    boot_start = js.index("async function boot(")
    boot_end = js.index("\n}", boot_start)
    assert "reloadColumns(" in js[boot_start:boot_end]
    assert "reloadColumns(" in _function_body(js, "loadStudy")


def test_choosing_a_folder_lands_on_a_vault_from_it():
    # M2 was about landing on the study that had just arrived rather than on
    # studies[0]. Re-pinned 2026-09-04 to where a study now arrives from: a
    # folder. Choosing one empties the scene, because the vault on screen
    # came from the old folder and may not exist in the new one, then
    # selects and loads a vault from the new folder.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    boot_start = js.index("async function boot(preferredExport)")
    boot_end = js.index("\n}", boot_start)
    boot_body = js[boot_start:boot_end]
    assert "select.value = toLoad" in boot_body
    assert "async function importExportPair(" not in js
    chooser = js[js.index('getElementById("folder-choose")'):]
    chooser = chooser[:chooser.index("\n});")]
    assert "clearScene()" in chooser
    assert "refreshStudies(" in chooser
    assert "loadStudy(names[0])" in chooser


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
    assert "function arrowField(entries, colour, anchor)" in js
    start = js.index("function arrowField(")
    end = js.index("\n}", start)
    assert "direction" not in js[start:end]


def test_load_arrows_arrive_tip_first_and_reactions_leave_the_support():
    # A downward load whose tail sits at the node hangs under the shell
    # and reads as suction pulling the vault down. The head belongs at
    # the point of application, so loads are tip-anchored; reactions
    # genuinely emerge from the supports and stay tail-anchored.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "updateVectorLayers")
    assert '0x66aaff, "tip"' in body, "loads must be tip-anchored"
    assert '0x66dd77, "tail"' in body, "reactions must stay tail-anchored"
    arrow_body = _function_body(js, "arrowField")
    assert 'anchor === "tip"' in arrow_body


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
    assert "state.formworkMode" in body
    # Task 4: the wires layer checkbox is gone (the Show select owns net
    # visibility now), so the strike no longer reads state.layers.wires --
    # timeline mode shows the net per the strike clock alone.
    assert "state.layers.wires" not in body
    for name in ("wires", "nodes"):
        assert '"{}"'.format(name) in body, "the strike must drive {}".format(name)


def test_set_layer_does_not_call_applytimeline_directly():
    # FINDING 1 (camera snap): setLayer's old wires/shell branch used to call
    # applyTimeline, whose autoSpin branch repositions the camera onto the
    # orbit ring -- so ticking a layer checkbox teleported a user-positioned
    # camera. Task 4 removed that branch entirely (wires/shell moved to the
    # Show select, applyShowMode), but the invariant it protected still
    # holds: no code path inside setLayer may reposition the camera.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("function setLayer(")
    end = js.index("\n}", start)
    body = js[start:end]
    assert 'name === "wires" || name === "shell"' not in body
    assert "applyTimeline(" not in body, (
        "setLayer must never call applyTimeline directly; that would move "
        "the camera on a layer toggle"
    )


def test_the_formwork_ghost_is_hidden_and_has_no_control():
    """Replaced 2026-09-04. Param: "remove the formwork dropdown all
    together. not needed. its just plays animation as it should". The ghost
    was a second, translucent copy of a surface the formwork act now draws
    properly, and its control had defaulted to hidden since the finish wave,
    which is the state every take has been watched at. The rules that read
    the mode are untouched, so restoring the control would be a control and
    a handler rather than an engine change.

    What this still guards is the finding underneath it: the ghost is NOT a
    layer checkbox. A checkbox could not resurrect what the strike had
    removed, and at the finished vault it did nothing in either direction.
    """

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="formwork-mode"' not in html
    assert 'getElementById("formwork-mode")' not in js
    assert 'formworkMode: "hidden"' in js
    assert '"falsework", "Formwork"' not in js, "the checkbox entry is gone"
    assert "falsework: true" not in js, (
        "state.layers must not carry falsework any more"
    )
    # The three rules the mode drives are still there and still read it.
    scene_body = _function_body(js, "applySceneAtTime")
    assert "state.formworkMode" in scene_body


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


def test_the_finished_shell_is_governed_by_show_mode_not_a_checkbox():
    # Task 4: the shell and wires checkboxes are gone from LAYERS; the
    # Show select owns both now (test_the_show_select_offers_four_
    # exclusive_modes, applyShowMode). The timeline's own segment gate no
    # longer reads a layers flag at all -- inflate is the only gate left.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert '"shell", "Finished shell"' not in js
    assert '"wires", "Thrust wires and nodes"' not in js
    scene_body = _function_body(js, "applySceneAtTime")
    assert "state.layers.shell" not in scene_body
    layer_body = _function_body(js, "setLayer")
    assert 'name === "wires" || name === "shell"' not in layer_body


def test_the_thrust_network_is_freed_whenever_it_is_replaced():
    """Replaced 2026-09-04. The two size sliders that used to drive this are
    gone (Param fixed the sizes at 30 mm nodes and 20 mm wires and removed
    the View panel), and rebuildWiresAndNodes went with them, but the
    discipline they were written to enforce is unchanged and still matters:
    a study load, a cut change and a cleared scene all REPLACE the network,
    and whatever is replaced owns GPU buffers that nothing else frees.

    FINDING 2 of the original wave, kept verbatim because it is the subtle
    one: in three 0.185 it is InstancedMesh.dispose() that frees the
    instanceMatrix and instanceColor buffers. Disposing only the geometry
    and the material leaks them on every replacement."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function rebuildWiresAndNodes(" not in js, "no callers, no function"
    assert "state.nodeRadius" in js and "state.wireRadius" in js
    dispose_body = _function_body(js, "disposeWiresAndNodes")
    assert "geometry.dispose()" in dispose_body
    assert "material.dispose()" in dispose_body
    assert "object.dispose()" in dispose_body, (
        "the InstancedMesh itself owns instanceMatrix and instanceColor"
    )
    for caller in ("buildScene", "clearScene"):
        assert "disposeWiresAndNodes()" in _function_body(js, caller), caller


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


def test_the_heatmaps_are_unlit_data_colours():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "recolourSegments")
    assert "MeshBasicMaterial" in body and "toneMapped: false" in body, (
        "a staged per-vertex field must not depend on lighting or tone mapping")
    # The peaks-only fallback (no stage, verification only) is one flat
    # tint standing in for a whole surface, not a field: it keeps the
    # previous lit material rather than claiming an unlit exemption a
    # single colour has no field to earn.
    assert "MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })" in body


def test_missing_coverage_reads_as_grey_not_white():
    # Root cause 2 from the stress-map report: sampleScalar used to return
    # null the instant ANY weighted corner lacked data, and recolourSegments
    # painted null straight to white -- indistinguishable from the pale
    # zero-stress end of STRESS_SCALE (0xf2efe8). sampleScalar now
    # renormalises over whatever corners DO have data (see test_fields.py),
    # so null only remains when every weighted corner is missing; that
    # honest "no data" case must read as a neutral grey the scale never
    # produces, not white.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "recolourSegments")
    assert "0x808080" in body, "no-data colour must be a neutral grey, not white"
    assert "0xffffff" not in body, (
        "recolourSegments must not paint missing data as white; white sits "
        "inside the stress scale's own pale-zero region"
    )
    assert "colour = value === null ? noData :" in body
    assert "if (!colour) colour = noData;" in body


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
    # Re-pinned 2026-09-04: both transport buttons go through startPlaying,
    # which also switches to the animation view and reads the framing off
    # the viewport, so a take can never begin in the wrong mode or from a
    # camera the user did not choose.
    restart_start = js.index('getElementById("restart-button")')
    restart_body = js[restart_start:js.index("\n});", restart_start)]
    assert "startPlaying(true)" in restart_body
    start_body = _function_body(js, "startPlaying")
    assert "applyTimeline(0)" in start_body
    assert "playing = true" in start_body
    assert 'state.showMode = "timeline"' in start_body
    assert "captureOrbitBase()" in start_body


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
    # The HUD carries the explanation, because a sentence belongs where
    # there is room for one.
    assert "size control is not used" in _function_body(js, "updateHud")
    # The panel carries the correction and nothing more. It used to carry
    # the sentence too -- 466 pixels of it inside a 300 pixel panel, which
    # printed through the words "Piece size" and then off the right edge.
    # The claim the original test was defending is unchanged: an authored
    # size is never called a target.
    cut = _function_body(js, "applyCut")
    assert '" mm requested"' in cut and '" mm target"' in cut
    assert "size control is not used" not in cut, (
        "the panel row is a readout, not a paragraph; the HUD says why"
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


def test_hdri_mode_loads_estimates_and_persists():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "HDRLoader" in js and "three/addons/loaders/HDRLoader.js" in js
    body = _function_body(js, "loadHdri")
    assert "setDataType(THREE.FloatType)" in body, (
        "the estimator needs Float32 pixels, not half floats")
    assert "EquirectangularReflectionMapping" in body
    assert "estimateSunFromEquirect" in body
    assert 'localStorage.setItem("bench-studio-hdri"' in body
    assert ".dispose()" in body, "replacing an hdri must free the old texture"
    assert "180 - estimate.azimuthDeg" in body, (
        "world azimuth = 180 - image azimuth under three's equirect convention")
    refresh = _function_body(js, "refreshHdriList")
    assert '"/api/hdri"' in refresh
    assert 'localStorage.getItem("bench-studio-hdri")' in refresh
    assert "no HDRIs installed" in refresh
    # The sky is now TWO files with one job each. The lighting file is
    # 1024 across because three.js derives its environment cube from the
    # source width over four and keeps a ping-pong target beside it, so an
    # 8k source costs about a gigabyte of peak video memory to prefilter for
    # a picture the prefilter then blurs into a 256 pixel cube.
    assert '"/light"' in body or '+ "/light"' in body, (
        "loadHdri must take the derived lighting file, not the original"
    )
    assert "loadHdriBackdrop" in js, (
        "the sharp visible sky is a separate, tone-mapped texture"
    )
    backdrop = _function_body(js, "loadHdriBackdrop")
    assert '"/background"' in backdrop or '+ "/background"' in backdrop
    assert "THREE.SRGBColorSpace" in backdrop, (
        "a tone-mapped PNG is colour data and must say so"
    )
    assert "state.hdriName !== wanted" in backdrop, (
        "a slow sky that lost the race must not replace the one that won it"
    )
    # And the folder picker replaced the upload control outright.
    assert '"/api/uploads/hdri/"' not in js
    assert 'getElementById("hdri-folder-choose")' in js


def test_hdri_failures_reach_the_banner():
    """refreshHdriList and loadHdri must not fail silently into #hdri-status
    alone; every failure routes through the studio's own error banner
    (showBanner) or its fetchJson wrapper, which throws with the failing URL
    in the message.

    The upload handler this used to cover as well is gone with its control:
    a folder picker answers the question it was asked to answer. What is
    checked in its place is that the folder handler says which of its two
    steps failed, since "it did not work" about a dialog and a validation is
    two different problems.
    """
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("refreshHdriList", "loadHdri"):
        assert "showBanner" in _function_body(js, name) or "fetchJson" in _function_body(js, name), name
    folder = _function_body(js, "chooseLibraryFolder")
    assert "the folder dialog could not be opened" in folder
    assert "not a folder: " in folder
    assert "body.detail" in folder, "the server's own reason must be shown"


def test_props_come_from_a_library_of_real_models():
    """Replaced 2026-09-04. Param: "we should also massively work on bringing
    in way better props. like using serious 3d asset libraries instead of
    random ugly props we have made right now."

    The props are GLB models now, listed by a manifest that carries three
    things the file itself cannot: what the model is called, how tall it
    stands in the world, and who made it. The height is the one that matters
    structurally: a GLB carries whatever units its author worked in, so a
    figure is only a SCALE figure if the studio scales it to a stated
    height. Everything in the library is CC0 and credited anyway.

    The row is a Library button, a Place and a Clear; the library opens as
    the same tile grid the materials use, because a model is a look too. The
    hand-modelled props remain as the fallback for a studio whose library
    folder is empty, which is also what makes this change safe to ship."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # Re-pinned 2026-09-04: the Place button is gone. Param: "why would i
    # have to press place and then select a prop... it should just be a drop
    # down and i click that it gets attached to my cursor". Choosing IS
    # picking up, so there is nothing to arm and nothing to press first.
    assert 'id="prop-place"' not in html
    assert "function carryNewProp(" in js and "function carryExistingProp(" in js
    assert "state.carrying" in js
    assert "if (state.carrying) {" in _function_body(js, "cancelCarry") or True
    for control in ("prop-browse", "props-clear", "prop-tiles",
                    "prop-credit", "prop-type"):
        assert 'id="{}"'.format(control) in html, control
    assert 'id="prop-figure"' not in html, "the five buttons are gone"
    # The manifest, not the file, is the authority on scale.
    loader = _function_body(js, "loadPropTemplate")
    assert "entry.heightMetres" in loader
    assert "model.scale.multiplyScalar(wanted / height)" in loader
    assert "model.rotation.x = Math.PI / 2" in loader, "glTF is Y-up, the studio is Z-up"
    assert "model.position.z -= stood.min.z" in loader, "a prop stands on the ground"
    # Clones share the template's geometry, which is what makes twenty
    # figures cost one model, and is why disposing one must not free it.
    assert "template ? template.clone() : makeProp(type)" in js
    assert "if (object.userData.fromLibrary) return;" in _function_body(js, "disposeProp")
    # An empty library leaves the studio exactly as it was.
    assert "if (!entries.length) return;" in _function_body(js, "loadPropLibrary")
    assert "function makeProp(" in js, "the fallback props stay"


def test_the_prop_library_is_credited_and_reachable():
    """Everything in the library is CC0, so nothing has to be credited. It is
    credited anyway, in the manifest, on the tile and in a NOTICE beside the
    files: a studio that shows somebody else's work without saying whose is
    not to be trusted about anything else either."""

    import json as json_module

    props = STATIC.parent / "props"
    manifest = json_module.loads((props / "props.json").read_text(encoding="utf-8"))
    assert manifest["props"], "the library has models in it"
    for entry in manifest["props"]:
        assert (props / entry["file"]).is_file(), entry["file"]
        assert entry["credit"] and entry["licence"].startswith("CC0"), entry["key"]
        assert entry["heightMetres"] > 0, entry["key"]
        assert entry["source"].startswith("https://"), entry["key"]
    assert (props / "NOTICE.txt").is_file()
    # A person is a person's height, and the scale figure is the whole point.
    figure = next(e for e in manifest["props"] if e["key"] == "figure-standing")
    assert 1.6 <= figure["heightMetres"] <= 1.9


def test_props_persist_per_study_and_stay_out_of_the_analysis():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    key = _function_body(js, "propsKey")
    assert "bench-studio-props:" in key and "state.bundle.export" in key
    make = _function_body(js, "makeProp")
    assert "castShadow = true" in make
    restore = _function_body(js, "restoreProps")
    assert "localStorage.getItem" in restore
    save = _function_body(js, "saveProps")
    assert "localStorage.setItem" in save
    # A prop leaves its own geometry and material behind on the GPU when it
    # is dropped; every site that removes one from propsGroup must dispose
    # it first, the same rule disposeShell already follows.
    assert "disposeProp(" in _function_body(js, "restoreProps")
    assert js.count("disposeProp(") >= 4
    # buildScene restores the layout for the study it just built.
    assert "restoreProps()" in _function_body(js, "buildScene")
    # The placement layer pauses the camera, never fights it.
    assert "controls.enabled = false" in js and "controls.enabled = true" in js
    # Props never join analysis recolouring: recolourSegments touches
    # segment meshes only, and props live in their own group.
    assert "propsGroup" in js
    assert "propsGroup" not in _function_body(js, "recolourSegments")
    # A drag that ends over a fixed panel overlay never reaches the canvas
    # with a pointerup, so the drag must hold pointer capture for its whole
    # life and release it on both pointerup and pointercancel.
    assert "setPointerCapture" in js and "releasePointerCapture" in js, (
        "a prop drag must capture the pointer or ending it over #panel or "
        "#data-panel leaves controls.enabled stuck false"
    )
    assert 'addEventListener("pointercancel"' in js


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
    # Re-pinned 2026-09-04: the gap lost its control (Param: it should
    # always be 0.001) but not its behaviour. The cut still opens a joint,
    # still proportionally, so only the farthest vertex of a casting moves
    # the full half gap and everything nearer its centroid moves less.
    assert 'id="joint-gap"' not in html
    assert "jointGap: 0.001," in js, "a hairline, and a constant"
    assert "function buildPieceMeshes(" in js
    assert "state.bundle.pieces" in js
    assert "state.jointGap" in js
    assert "function buildSegmentMeshes(" not in js, "the old extruder is retired"


def test_the_joint_gap_is_marked_inert_where_it_does_nothing():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # Re-pinned 2026-09-04: with the slider gone there is no control to
    # disable, so the fact says itself in the event log instead of sitting
    # as a note beside a control the user cannot touch. The honesty is the
    # same and the panel is quieter.
    assert 'id="joint-gap-note"' not in html
    start = js.index("function updateMaterialControls(")
    body = js[start:js.index("\n}", start)]
    assert "sprayedMaterial()" in body
    assert "logStudio(" in body and "monolithic" in body, (
        "sprayed concrete opens no joints, and the studio still says so"
    )
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
    # Re-pinned 2026-09-04: the slider is gone (Param: the animation belongs
    # to Grasshopper, and where there are frames the machine IS the reveal),
    # so the fallback reveal is a constant. The maths below is unchanged.
    assert 'id="inflate-seconds"' not in html
    assert "const INFLATE_SECONDS = 3;" in js
    assert "inflateSeconds: INFLATE_SECONDS," in js
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
    # Re-pinned 2026-09-04: the control is retired and the value pinned at
    # zero, because it thinned pieces in the DRAWING while the analysis
    # stayed uniform, and a picture that disagrees with its own numbers is
    # worse than no picture. The maths and the HUD disclosure both stay, so
    # bringing it back is a control and a handler, not an engine change.
    assert 'id="taper"' not in html
    assert "taper: 0," in js
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
    # readout has counted every casting. Drawn from the file's own
    # constants through the same regexes pinned above, not restated as
    # bare literals, so the replay is honestly about what studio.js holds.
    build_target = float(re.search(r"BUILD_TARGET_SECONDS = ([\d.]+)", js).group(1))
    drop_seconds = float(re.search(r"DROP_SECONDS = ([\d.]+)", js).group(1))
    for placements in (38, 1200):
        step = build_target / max(1, placements)
        assert abs(placements * step - build_target) < 1e-9, "the build must be constant"
        lands = (placements - 1) * step + drop_seconds
        build_end = placements * step + drop_seconds
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


def test_the_dead_controls_are_gone_not_merely_hidden():
    """Replaced 2026-09-04. Three controls stopped meaning anything and were
    removed rather than left to mislead: the inflation seconds (the reveal
    is Grasshopper's animation now, or a constant where there is none), the
    orbit distance (the take orbits from wherever the camera is left, so the
    distance is the camera's), and the node and wire sizes (fixed at the
    30 mm and 20 mm Param settled on). A control that no longer decides
    anything is worse than no control."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for dead in ('id="inflate-seconds"', 'id="inflate-value"', 'id="orbit-distance"',
                 'id="node-radius"', 'id="wire-radius"'):
        assert dead not in html, dead
        assert 'getElementById("' + dead[4:-1] + '")' not in js, dead
    # The values they used to carry are still the values.
    assert "nodeRadius: 0.03," in js and "wireRadius: 0.02," in js
    assert "const INFLATE_SECONDS = 3;" in js
    # Spin rate survives, because the rate is not something the viewport
    # can tell us.
    assert 'id="orbit-speed"' in html


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
    # Task 4 reorganised the panel: Import, Study, Analysis, View,
    # Animation, Scene. Study, View and Animation open; the rest
    # collapsed. Record's controls moved inside Animation, and the
    # Styling sub-section was flattened into Analysis, so neither
    # "record-section" nor a Styling summary exists any more.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    positions = []
    # Re-pinned 2026-09-04: View is gone (Param), its Show select is now the
    # three buttons at the foot of the panel, its formwork ghost joined
    # Animation, and its two size sliders were removed outright.
    for section_id, is_open in (
        ("import-section", False), ("study-section", True),
        ("analysis-section", False),
        ("animation-section", True), ("scene-section", False),
    ):
        at = html.index('id="{}"'.format(section_id))
        positions.append(at)
        tag = html[html.rindex("<details", 0, at):html.index(">", at) + 1]
        assert (" open" in tag) == is_open, section_id
    assert positions == sorted(positions), "sections out of order"
    assert "<h2>" not in html, "summaries are the section headers now"
    assert 'id="record-section"' not in html
    assert 'id="styling-section"' not in html
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#panel summary" in css


def test_three_buttons_replace_the_show_select():
    """Re-pinned 2026-09-04 to Param's design: three buttons at the foot of
    the panel, Formwork, Shell and Both, the chosen one lit, Both by
    default. Timeline is not among them because playing is its own way of
    looking and switches to it by itself, and choosing a view during a take
    stops the take: the buttons and the animation cannot both own the
    scene. The applyShowMode assertions below are unchanged."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="show-mode"' not in html, "the select is gone"
    assert 'id="view-section"' not in html, "and so is the panel it sat in"
    row = html[html.index('id="mode-row"'):html.index("</aside>")]
    for button, word in (("show-formwork", "Formwork"), ("show-shell", "Shell"),
                         ("show-both", "Both")):
        assert 'id="{}"'.format(button) in row and ">" + word + "<" in row
    assert 'id="show-both" class="mode active"' in row, "Both is the default"
    assert 'showMode: "both",' in js
    stop = _function_body(js, "setShowMode")
    assert "playing = false" in stop, "picking a view stops the take"
    assert "applyShowMode()" in _function_body(js, "applySceneAtTime")
    body = _function_body(js, "applyShowMode")
    assert "camera.position" not in body and "controls.target" not in body
    # The strike (applySceneAtTime) fades wires/nodes toward opacity 0 and
    # position.z -1.5; leaving Timeline for Framework/Shell/Both must
    # restore both to their built values, or a mid-strike scrub leaves the
    # net faded and sunk in every other Show mode.
    assert "material.opacity = 1" in body
    # Crown seam (2026-08-16-studio-finish task 4): the flat restore to
    # "position.z = 0" pinned since the repairs wave held for every non
    # Timeline mode alike, but Both mode's net sits directly on the shell's
    # mid-surface with no clearance from the extrados, and pokes through it
    # at the crown (test_static.py cannot see the picture; the probe
    # captures crown-seam-both-before.png / -closeup-before.png are the
    # evidence). Framework still restores the true z = 0; Both now clears
    # the shell by half its thickness plus each object's OWN radius --
    # fix round 1 gave wires and nodes separate clearances (see
    # test_both_mode_and_the_pre_strike_timeline_clear_the_net_of_the_crown_seam),
    # since a shared wireRadius-only clearance under-cleared the nodes.
    assert 'state.showMode === "both"' in body
    # Re-pinned 2026-09-04: the two locals became the one netClearance()
    # record that the finished net, Both mode and the formwork act all read.
    # Still two lifts, still one per object's own radius.
    assert 'position.z = state.showMode === "both" ? clearance.wires' in body
    assert 'position.z = state.showMode === "both" ? clearance.nodes' in body


def test_both_mode_and_the_pre_strike_timeline_clear_the_net_of_the_crown_seam():
    # Task 4 of the 2026-08-16-studio-finish wave. Diagnosis: the net
    # (buildWiresAndNodes) is drawn straight off bundle.analysis_mesh, the
    # raw mid-surface, with no display offset; the shell (buildPieceMeshes)
    # is offset off that same mid-surface family by half the built
    # thickness a side. Nothing guarantees those two independently-built
    # surfaces stay clear of one another, and at the crown -- this vault's
    # shallowest, most tightly curved region -- the net's own wire/node
    # radius is enough to break through the shell's extrados: a black line
    # with regularly spaced white dots along the ridge. Probed against the
    # real "Algebraic TNA method" export, camera close on the crown, in
    # both Show=both and Show=timeline just before the strike hides the
    # net; captures alongside this file:
    #   .superpowers/sdd/2026-08-16-studio-finish/crown-seam-both-before.png
    #   .superpowers/sdd/2026-08-16-studio-finish/crown-seam-both-closeup-before.png
    #   .superpowers/sdd/2026-08-16-studio-finish/crown-seam-timeline-strike-950-before.png
    # and their -after equivalents once the fix below landed. The fix is a
    # display-only nudge along +Z by half the built thickness plus each
    # object's OWN radius -- an approximation of "outward along the local
    # normal" that only holds where that normal is close to vertical, which
    # is exactly the shallow crown where the seam showed (see the comments
    # beside each assertion's source for the caveat spelled out in full).
    #
    # Fix round 1 (review finding, Medium): the first cut shared one
    # clearance (thickness/2 + wireRadius) between wires AND nodes, but
    # nodes are a separate InstancedMesh at state.nodeRadius (default 0.03
    # vs wireRadius's 0.02, independently adjustable up to 0.10 via the
    # Node size slider) -- a node's nearest point sat at
    # clearance - nodeRadius, under-cleared by the radius difference, and
    # growing Node size alone could push the white dots back through the
    # shell: the exact reported symptom. Each object now clears by its own
    # radius, both sites.
    # Re-pinned 2026-09-04, twice. First: the same two expressions moved
    # into netClearance(), read by all three callers, the third being the
    # formwork act, whose raising net has to sit exactly where the finished
    # net sits or the handover at the end of the act jumps. Second, and the
    # reason for the minus signs: the offset was a LIFT, which cured this
    # seam by drawing the whole vault hanging underneath its own formwork.
    # The net is the mould, so it hangs BELOW the surface it is solved on
    # and the vault is cast on top of it. The seam is cured by the same
    # margin, from the other side, and the placement now agrees with the
    # falsework ghost, which has always sat at -(thickness / 2) - 0.05.
    # Each object still clears by its OWN radius, which is the invariant
    # this test exists for.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    clearance_body = _function_body(js, "netClearance")
    assert "wires: -(thickness / 2 + state.wireRadius)," in clearance_body
    assert "nodes: -(thickness / 2 + state.nodeRadius)," in clearance_body
    show_body = _function_body(js, "applyShowMode")
    assert "clearance.wires" in show_body and "clearance.nodes" in show_body
    assert "netClearance()" in show_body
    scene_body = _function_body(js, "applySceneAtTime")
    assert "netClearance()" in scene_body
    act_body = _function_body(js, "applyFormworkAct")
    assert "netClearance()" in act_body
    # The strike's own drop is additive with the clearance, so the net still
    # lands 1.5 m clear of the shell once fully struck (strikeU = 1).
    assert "clearance[key] - 1.5 * strikeU" in scene_body


def test_the_panel_reorganises_into_six_sections():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    # Re-pinned 2026-09-04: five sections, View removed.
    order = [html.index('id="{}-section"'.format(name))
             for name in ("import", "study", "analysis", "animation", "scene")]
    assert order == sorted(order), "section order is Import, Study, Analysis, Animation, Scene"
    assert 'id="record-section"' not in html
    assert 'id="styling-section"' not in html
    # Record's controls live inside Animation now.
    animation = html[html.index('id="animation-section"'):html.index('id="scene-section"')]
    assert 'id="record-button"' in animation and 'id="record-status"' in animation
    # The analysis section owns the toggles and the analysis controls.
    analysis = html[html.index('id="analysis-section"'):html.index('id="animation-section"')]
    for control in ("run-button", "layer-toggles", "stress-surface",
                    "exaggeration", "data-button"):
        assert control in analysis, control


def test_textures_are_anisotropic_and_sprayed_shades_as_one_surface():
    # Two artefacts from the sprayed close-up. Fine wavy ripples at
    # grazing angles: the procedural textures rendered at anisotropy 1,
    # textbook texture moire. And tonal steps at every course joint:
    # normals were welded within each piece only, so neighbouring pieces
    # disagreed about the light at their shared boundary even though a
    # zero joint gap makes sprayed concrete one continuous surface.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("noiseTexture", "grainTexture"):
        assert "getMaxAnisotropy()" in _function_body(js, name), (
            "{} must set max anisotropy".format(name)
        )
    body = _function_body(js, "buildPieceMeshes")
    assert "welded" in body, (
        "a monolithic surface must weld normals across the whole shell"
    )
    assert "shrink === 1" in body, (
        "shrink 1 must push the raw point: c + (p - c) is not p in "
        "floats, and the weld groups corners by exact bit pattern"
    )


def test_the_cut_overlay_shows_while_a_cut_is_in_flight():
    # The status line in the panel was not enough: a slow material change
    # read as a hang. The overlay is a signal, not a modal lock: it dims
    # nothing and blocks no clicks.
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert 'id="cut-overlay" class="hidden"' in html
    assert 'id="cut-spinner"' in html
    overlay_at = html.index('id="cut-overlay"')
    assert html.index('id="cut-status"') > overlay_at, (
        "the status line lives inside the overlay now"
    )
    load_start = js.index("async function loadStudy(")
    load_body = js[load_start:js.index("\n}", load_start)]
    assert 'overlay.classList.remove("hidden")' in load_body
    assert load_body.count('overlay.classList.add("hidden")') == 2, (
        "the overlay must hide on the landing path and the failure path"
    )
    assert "#cut-overlay" in css
    assert "pointer-events: none" in css
    assert "@keyframes" in css


def test_the_deflection_reset_restores_the_welded_normals():
    # Deflection on then off wrote basePositions back but recomputed the
    # normals PER PIECE, so a sprayed shell came back with the course
    # joint steps the whole-shell weld exists to remove, and stayed that
    # way until the next rebuild. The reset restores the stored buffer.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "userData.baseNormals = normals" in _function_body(js, "buildPieceMeshes")
    body = _function_body(js, "recolourSegments")
    assert "userData.baseNormals.slice()" in body


def test_the_environment_addons_are_vendored():
    # Task E1/E2/E3 groundwork: the Sky shader and the Radiance loader sit
    # beside RoomEnvironment, same pinned three version, importable through
    # the importmap's three/addons/ prefix.
    sky = STATIC / "vendor" / "addons" / "objects" / "Sky.js"
    hdr = STATIC / "vendor" / "addons" / "loaders" / "HDRLoader.js"
    skybox = STATIC / "vendor" / "addons" / "objects" / "GroundedSkybox.js"
    assert sky.is_file() and hdr.is_file() and skybox.is_file()
    assert not (STATIC / "vendor" / "addons" / "loaders" / "RGBELoader.js").exists(), "only the 0.185 HDRLoader is vendored"
    sky_text = sky.read_text(encoding="utf-8")
    hdr_text = hdr.read_text(encoding="utf-8")
    skybox_text = skybox.read_text(encoding="utf-8")
    assert "turbidity" in sky_text, "Sky.js must be the scattering shader"
    assert "RGBE" in hdr_text, "HDRLoader.js must decode Radiance files"
    assert "GroundedSkybox" in skybox_text, "GroundedSkybox.js must export the ground-projected skybox"
    for text in (sky_text, hdr_text, skybox_text):
        assert "from 'three'" in text or 'from "three"' in text, (
            "addons must import bare 'three' so the importmap resolves them"
        )


def test_the_environment_select_owns_three_exclusive_modes():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="environment-mode"' in html
    for value in ("studio", "sky", "hdri"):
        assert '<option value="{}"'.format(value) in html
    assert '<option value="studio" selected' in html
    assert 'environmentMode: "studio"' in js
    # Mode switches recompute the scene through the environment functions
    # and never touch the camera: no camera writes in any of them.
    for name in ("applyEnvironment", "regenerateEnvironment", "applySunFromSliders"):
        body = _function_body(js, name)
        assert "camera.position" not in body
        assert "controls.target" not in body


def test_the_weather_presets_are_parameter_bundles_on_one_sky():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="weather-preset"' in html
    for value in ("clear", "hazy", "overcast", "golden-hour", "night"):
        assert '<option value="{}"'.format(value) in html
    for key in ("turbidity", "rayleigh", "mieCoefficient", "mieDirectionalG",
                "sunIntensity", "sunColor", "shadowRadius", "exposure",
                "hemisphere", "fogColor", "fogNear", "fogFar"):
        assert key in js, "WEATHER presets must carry {}".format(key)
    # The sky is one shared mesh in a Z-up world.
    assert "new Sky()" in js
    assert "uniforms.up.value.set(0, 0, 1)" in js
    # The vendored Sky's cloud block is hardcoded Y-up; scattering respects
    # the up uniform above but the clouds do not, so they must be switched
    # off rather than ship wrongly oriented on every preset.
    assert "cloudCoverage.value = 0" in js


def test_pmrem_regeneration_stays_off_the_input_path():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # The only fromScene/fromEquirectangular calls after boot live in
    # regenerateEnvironment; applyEnvironment and the slider input path
    # stay cheap.
    for name in ("applyEnvironment", "applySunFromSliders"):
        body = _function_body(js, name)
        assert "fromScene" not in body and "fromEquirectangular" not in body
    regen = _function_body(js, "regenerateEnvironment")
    assert "fromScene" in regen and "fromEquirectangular" in regen
    # Sun slider input events move the light only; regeneration hangs on
    # the change event gated to sky mode.
    assert 'addEventListener("input", applySunFromSliders)' in js


def test_each_environment_mode_owns_background_fog_and_rotation():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "applyEnvironment")
    assert "scene.fog = null" in body, "studio and hdri modes must clear fog"
    assert "new THREE.Fog(" in body, "sky mode must set fog"
    assert "backgroundRotation" in js and "environmentRotation" in js
    # The tone slider is a studio-mode control; sky and hdri rows swap in.
    assert 'id="background-row"' in (STATIC / "index.html").read_text(encoding="utf-8")


def test_the_hdri_backdrop_projects_and_rotates():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="hdri-projection"' in html
    for control in ("hdri-scale", "hdri-height", "hdri-rotation"):
        assert 'id="{}"'.format(control) in html
    assert "GroundedSkybox" in js
    body = _function_body(js, "applyHdriBackdrop")
    assert "new GroundedSkybox(" in body and "dispose" in body
    # Rotation tracks the sun: the estimate's azimuth gets the rotation added.
    assert "state.hdriRotation" in _function_body(js, "loadHdri")
    assert "HDRI_MAX_BYTES" not in (
        (Path(__file__).resolve().parents[2] / "bench" / "studio" / "app.py")
        .read_text(encoding="utf-8"))


def test_environment_functions_never_read_the_clock_or_the_timeline():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("applyEnvironment", "regenerateEnvironment", "applySunFromSliders"):
        body = _function_body(js, name)
        for banned in ("performance.now", "Date.now", "state.timeline"):
            assert banned not in body, "{} reads {}".format(name, banned)


def test_the_ground_presets_swap_one_discs_material():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="ground-preset"' in html
    # One built-in floor. The procedural slab/paver/tile stand-ins went when
    # the ground gained its own curated library folder (Param, 2026-09-04).
    assert '<option value="dark-studio"' in html
    for value in ("concrete-slab", "patio-pavers", "tiles"):
        assert '<option value="{}"'.format(value) not in html
    assert '"/api/ground-materials"' in js, (
        "the ground grid reads its own library, not the skin one"
    )
    assert 'groundPreset: "dark-studio"' in js
    # One disc, materials cached for the session. Re-pinned 2026-09-04:
    # the disc is now built by rebuildGround, which buildScene and both
    # ground controls call, because a resizable floor has to recompute its
    # joint repeat and a material swap alone cannot (see
    # test_the_ground_takes_its_size_from_one_slider).
    assert "groundMaterialCache" in js
    assert "rebuildGround()" in _function_body(js, "buildScene")
    assert "groundMaterial(state.groundPreset)" in _function_body(js, "rebuildGround")
    # The joint texture is procedural canvas work like every other texture.
    joint = _function_body(js, "groundJointTexture")
    assert "createElement" in joint and "getMaxAnisotropy" in joint


def test_the_probe_hook_exposes_state_and_scene():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert ("window.__studio = { state, scene, camera, controls, "
            "applyDayCycle, placeProp }" in js), (
        "the probe rig reads app state through this hook, and frames "
        "detail captures through the camera and controls; applyDayCycle is "
        "exposed too (Task 3) so a probe can drive the day cycle directly "
        "instead of re-deriving its formula in probe script JS, which would "
        "drift from the pure function it is meant to be checking; and "
        "placeProp, so a probe can populate a scene without synthesising a "
        "pointer gesture per prop, which is how a check nobody runs gets "
        "written")


def test_the_postprocessing_addons_are_vendored():
    base = STATIC / "vendor" / "addons"
    for name in ("postprocessing/EffectComposer.js", "postprocessing/RenderPass.js",
                 "postprocessing/ShaderPass.js", "postprocessing/OutputPass.js",
                 "shaders/BrightnessContrastShader.js"):
        assert (base / name).is_file(), name


def test_brightness_and_contrast_grade_every_render():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="brightness"' in html and 'id="contrast"' in html
    assert "state.exposureBase * state.brightness" in _function_body(js, "applyGrade")
    assert "contrast.value = state.contrast" in _function_body(js, "applyGrade")
    # One render entry point; both the frame loop and the recorder use it.
    assert "composer.render()" in _function_body(js, "renderView")
    assert "renderView()" in _function_body(js, "frame")
    assert "renderView()" in _function_body(js, "recordAnimation"), (
        "recordings must carry the grade too")
    assert js.count("renderer.render(scene, camera)") == 0, (
        "all rendering goes through the composer now")
    # The composer, not the renderer, must be the one resized: a live
    # window resize and a 1080p recording that skipped composer.setSize
    # would render into a stale-sized target and stretch or crop.
    assert "composer.setSize" in _function_body(js, "resize")
    assert "composer.setSize" in _function_body(js, "recordAnimation")
    for name in ("applyGrade", "renderView", "applyShowMode"):
        body = _function_body(js, name)
        for banned in ("performance.now", "Date.now", "state.timeline"):
            assert banned not in body


def test_the_run_button_lives_in_analysis():
    """Re-pinned 2026-09-04: the run button still belongs to Analysis rather
    than to Study. The half of this test about the node and wire sizes is
    gone with the sizes themselves, which are fixed now (see
    test_the_dead_controls_are_gone_not_merely_hidden)."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    analysis = html[html.index('id="analysis-section"'):html.index('id="animation-section"')]
    assert 'id="run-button"' in analysis and 'id="run-status"' in analysis
    study = html[html.index('id="study-section"'):html.index('id="analysis-section"')]
    assert 'id="run-button"' not in study


def test_the_event_log_reports_studio_events():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert 'id="event-log"' in html
    assert "#event-log" in css and "pointer-events: none" in css.split("#event-log", 1)[1][:400]
    # F6: the log sat at right: 16px, painting over the control panel
    # (#legend already solves the identical collision). The clearance is
    # DERIVED from the panel width token now, so the two cannot drift when
    # the panel is resized: it hard-coded 276px while the panel was 260,
    # and 316px while it was 300, and each number went stale in turn.
    clearance = "right: calc(var(--panel-w) + var(--s4))"
    assert clearance in css.split("#event-log", 1)[1][:400]
    assert clearance in css.split("#legend {", 1)[1][:400]
    body = _function_body(js, "logStudio")
    assert "toLocaleTimeString" in body or "toTimeString" in body
    # The banner helper mirrors into the log, and the named sites report.
    assert "logStudio(" in _function_body(js, "showBanner")
    assert "logStudio(" in _function_body(js, "loadStudy")
    assert "logStudio(" in _function_body(js, "loadHdri")


def test_banners_dismiss_themselves_and_close():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="banner-close"' in html
    body = _function_body(js, "showBanner")
    assert "setTimeout" in body
    assert "mouseenter" in js and "mouseleave" in js
    for name in ("logStudio", "showBanner"):
        assert "state.timeline" not in _function_body(js, name)


def test_the_sun_colour_is_overridable_until_the_next_preset():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="sun-colour"' in html and 'type="color"' in html
    assert "sunColourOverride" in js
    # F4: the intensity override is a second, symmetrical flag; a captured
    # day-cycle intensity must survive an environment redraw exactly like
    # the captured colour already does.
    assert "sunIntensityOverride" in js
    # Preset changes reset the override; the override wins between presets.
    # Re-pinned 2026-09-04: the weather presets are a tile grid now, so the
    # first mention of the select is the grid that builds them and the
    # handler has to be found by its listener rather than by that name.
    weather = js[js.index('getElementById("weather-preset").addEventListener'):]
    assert "sunColourOverride = null" in weather[:600]
    assert "sunIntensityOverride = null" in weather[:600]
    # F3, re-pinned the same day: the swatch must never show a colour the
    # sun is not lit with. It used to be applyEnvironment's job to keep them
    # together; the sun instrument owns the colour now, applyEnvironment
    # calls it, and it writes the input every time it places the sun.
    placer = _function_body(js, "applySunFromTime")
    assert 'getElementById("sun-colour")' in placer
    assert "if (!state.sunColourOverride) sun.color.copy(colour);" in placer, (
        "an override still wins over the derived colour"
    )
    assert "if (sunInstrumentReady) applySunFromTime();" in _function_body(js, "applyEnvironment")


def test_the_day_cycle_is_a_pure_second_clock():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for control in ("day-cycle-button", "day-cycle-seconds", "day-cycle-record"):
        assert 'id="{}"'.format(control) in html
    body = _function_body(js, "applyDayCycle")
    for banned in ("performance.now", "Date.now", "state.timeline", "setTimeout"):
        assert banned not in body
    # Re-pinned 2026-09-04: the cycle used to synthesise its own arc, an
    # azimuth sweep from 270 to 90 and a sine elevation whose peak came off
    # a slider. It now runs the CLOCK from dawn to dusk on the real day at
    # the real site and lets the solar model place the sun, which is the
    # same code path a chosen time takes, so the cycle cannot look
    # different from the still it passes through. Purity in u is unchanged,
    # and that is what this test exists for.
    assert "state.sunMinutes = from + (to - from)" in body
    assert "applySunFromTime()" in body
    # F1 survives the change and matters more, not less: the display write
    # is clamped by the slider's own min="5" but the sun is placed from the
    # unclamped elevation, so a dawn or a dusk does not flatten.
    placer = _function_body(js, "applySunFromTime")
    assert "applySunAt(" in placer
    assert 'Math.round(Math.max(0, placed.elevation))' in placer, (
        "the display value is clamped"
    )
    assert "Math.max(-2, placed.elevation)" in placer, (
        "the placed sun is not"
    )
    # frame() is the only advancer; recording drives u deterministically.
    assert "state.dayCycle.t" in _function_body(js, "frame")
    assert "applyDayCycle(" in _function_body(js, "recordAnimation")
    # F2: recordAnimation must pause a live day cycle the same way it
    # already pauses the build timeline, or the two clocks race the same
    # state (state.dayCycle.t) while a recording drives it off frameIndex.
    assert "dayCycle.playing" in _function_body(js, "recordAnimation")


def test_the_day_cycle_peak_comes_from_the_sky_not_from_a_slider():
    """Replaced 2026-09-04. The peak elevation of the arc used to be
    captured off the elevation slider, because the arc was invented and
    something had to say how high it went. It is not invented any more: the
    peak of a real day comes from the date and the latitude, and the model
    gives it. The capture, the slider it captured from, and the reason both
    existed are gone together.

    What replaces it is the thing that was really wanted: the cycle runs
    between dawn and dusk, which are solved for the day rather than assumed,
    and it falls back to plain hours only where the sun never crosses those
    heights at all."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start_body = _function_body(js, "dayCycleStart")
    end_body = _function_body(js, "dayCycleEnd")
    assert "timeAtElevation(" in start_body and "-6, false" in start_body
    assert "timeAtElevation(" in end_body and "-6, true" in end_body
    assert "5 * 60" in start_body and "21 * 60" in end_body, (
        "a day with no dawn still has a cycle"
    )
    assert "state.dayCycle.peakElevation" not in _function_body(js, "applyDayCycle")


def test_appearance_overrides_are_render_only_and_persist():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    for control in ("material-tint", "material-finish", "material-reset", "render-skin"):
        assert 'id="{}"'.format(control) in html
    # F5: #appearance-note (the "render tint only" disclosure) must read as
    # a note, styled like every other sibling status/note line, not as
    # unstyled body text.
    assert "#appearance-note" in css
    # Fix round 1: the slider floors at the spec's 0.3, not an arbitrary
    # low bound -- roughness 0.05 gives a near-mirror gloss no registry
    # material approaches. Pinned against the tag's own markup so the
    # bound cannot silently drift again.
    finish_start = html.index('id="material-finish"')
    finish_tag = html[finish_start:html.index(">", finish_start)]
    assert 'min="0.3"' in finish_tag
    # Re-pinned 2026-09-04: the disclosure left the panel with the rest of
    # the prose (Param: the text display at the bottom left is what that is
    # for) and is said once in the event log when a skin or tint is first
    # applied. The claim it makes is the thing that matters, and it is still
    # made, in a place that does not cost a line of the panel forever.
    assert "render only: the analysis is unchanged" in js
    assert "function discloseAppearance(" in js
    assert '"bench-studio-appearance:"' in js
    # The three procedural skins are gone (Param, 2026-09-04): the library
    # is the skin catalogue, and "none" is the one built-in.
    for skin in ("white-presentation", "basalt-dark", "timber-ply"):
        assert '"{}"'.format(skin) not in js
    # The skin never reaches the server: no fetch uses the skin value.
    body = _function_body(js, "appearanceMaterialBase")
    assert "SKINS" in body
    assert "state.appearance.skin" not in _function_body(js, "loadStudy")


def test_a_columns_reload_settles_the_scene_it_joins():
    """The columns group is added AFTER buildScene, whose rebuildTimeline was
    the last thing to rule on what the scene shows. Nothing then decided
    anything about the group just added, so on every study load the exported
    column solids stood at their finished height above a net still lying flat
    on the ground at t = 0: one machine drawn in two instants at once
    (reported from the screen, 2026-09-04). Ending the reload with the
    scene-only applier hands the new group to the one function that owns
    machine visibility, and, being scene-only, never moves the camera."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "reloadColumns")
    assert "applySceneAtTime(state.timeline.t)" in body
    # Scene-only: a columns reload is not a timeline event.
    assert "applyTimeline(" not in body


def test_the_ground_takes_its_size_from_one_slider():
    """Param asked to be able to choose how much flooring there is, so the
    floor disc's radius is a control rather than the 60 m constant it was
    built at. Everything that can change the floor goes through the one
    rebuild, so a preset switch cannot leave a paver scaled for the previous
    disc, and the cached material is never disposed on the way out (it is
    shared through groundMaterialCache, and disposing it would take the
    texture with it)."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = html.index('id="ground-radius"')
    tag = html[html.rindex("<input", 0, start):html.index(">", start)]
    assert 'type="range"' in tag and 'min="2"' in tag and 'max="200"' in tag
    assert 'id="ground-radius-value"' in html
    assert "groundRadius: 60," in js
    body = _function_body(js, "rebuildGround")
    assert "new THREE.CircleGeometry(state.groundRadius, 64)" in body
    assert "groundRepeat(state.groundRadius" in body
    assert "material.dispose()" not in body
    assert "rebuildGround()" in _function_body(js, "buildScene")


def test_live_is_a_button_that_says_which_state_it_is_in():
    """Param asked for live text with a red beacon beside it when on and
    nothing when off. Live is a state the window is in, so it reads as a
    word and a light rather than a coloured dot with no label: on means this
    window follows Grasshopper's pushes, off means it ignores them, and the
    poll obeys the button rather than the button merely reporting on the
    poll."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="live-toggle"' in html
    assert '<span class="beacon"></span>LIVE' in html
    assert 'id="live-dot"' not in html, "the unlabelled dot is gone"
    # Red, and only when on. Off carries no beacon at all.
    assert "#live-toggle.on .beacon { background: #e03a3a" in css
    assert "#live-toggle .beacon { width: 7px; height: 7px; border-radius: 50%;" in css
    assert "background: transparent; }" in css
    assert "live: true," in js
    body = _function_body(js, "paintLive")
    assert 'state.live ? (flaring ? "on fresh" : "on") : "off"' in body
    # The poll obeys the button: Live off is not a label, it is a stop.
    assert "if (!state.live) { paintLive(false); return; }" in js
    # And Live follows Grasshopper rather than watching one study: a push to
    # a vault that is not the one on screen brings that vault up, which is
    # what a live link to a modeller means (Param, 2026-09-04).
    assert 'logStudio("live: following Grasshopper to " + pushed)' in js
    assert "liveStamps = stamps;" in js


def test_a_refusal_reaches_the_screen_in_the_servers_own_words():
    """The server refuses in sentences: this plan is not star shaped about
    its axis, this rim is more than one loop. Every one of them used to
    arrive wrapped in a URL and a JSON envelope, which reads as a crash
    rather than an answer, and switching between the Grasshopper Skin and
    the studio's own cut is where Param met them. The sentence is the
    message, the address goes to the log, and the reason stays under the
    control that caused it after the banner has gone."""

    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "fetchJson")
    assert "body.detail" in body
    assert "new Error(detail)" in body
    assert "logStudio(" in body
    assert "url + \" -> \"" not in body, "the URL is not the message"
    assert "lastRefusal: null," in js
    assert "state.lastRefusal = error.detail || error.message;" in js
    # Re-pinned 2026-09-04: the refusal goes to the event log at the foot
    # of the screen rather than a line under the control. Param: "this is
    # what the text display is for at the bottom left".
    assert 'logStudio("skin refused: " + state.lastRefusal)' in js


def test_the_import_panel_is_the_way_in():
    """Param's reorganisation: everything about getting a vault on screen
    lives in Import. The folder it is read from, the vault list with a
    refresh for new saves, Live, Delete, and the skin choice, which is one
    switch between two named ends rather than a list of two, because a
    study either wears the skin Grasshopper authored or the one the studio
    cuts."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    imports = html[html.index('id="import-section"'):html.index('id="study-section"')]
    for control in ('id="folder-choose"', 'id="folder-path"', 'id="study-select"',
                    'id="study-refresh"', 'id="live-toggle"', 'id="delete-study"',
                    'id="source-toggle"'):
        assert control in imports, control + " belongs in the Import panel"
    # The old select is gone, both in the markup and in the wiring.
    assert 'id="source-select"' not in html
    assert 'getElementById("source-select")' not in js
    assert 'class="toggle"' in html and ".toggle input:checked + .track" in css
    # Checked is the studio's own cut, at the right-hand end of the switch.
    assert 'state.source = e.target.checked ? "generated" : "authored";' in js
    # Refresh re-reads the folder rather than reloading the page.
    body = _function_body(js, "refreshStudies")
    assert '"/api/studies"' in body and "populateStudySelect" in body


def test_the_take_orbits_from_wherever_the_camera_is_left():
    """Param's ruling, and the simpler thing as well as the one he asked
    for: the framing IS the shot. The orbit's distance, height and bearing
    are read off the viewport when a take starts, and again when a drag ends
    mid-take, so moving the camera moves the take with it instead of
    snapping back. The current rotation is subtracted out of the captured
    bearing, or a capture taken mid-take would jump the camera by however
    far the take had already turned. Until a take has been started the
    timeline does not touch the camera at all, so loading a study leaves the
    view where it was."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    capture = _function_body(js, "captureOrbitBase")
    assert "camera.position.clone().sub(state.centre)" in capture
    assert "Math.atan2(offset.y, offset.x)" in capture
    assert ("- state.timeline.orbitSpeed * "
            "Math.max(0, state.timeline.t - openingSeconds())") in capture, (
        "the bearing must have the current rotation taken out of it, on the "
        "same clamped clock applyTimeline adds back (the orbit waits out "
        "the opening act, so the capture must subtract the same wait)"
    )
    body = _function_body(js, "applyTimeline")
    assert "base.radius" in body and "centre.z + base.height" in body
    assert "const base = state.timeline.orbitBase;" in body
    assert "if (base &&" in body, "no framing captured yet means hands off the camera"
    assert "orbitDistance" not in js, "the distance comes from the camera now"
    assert "if (state.timeline && state.timeline.playing) captureOrbitBase();" in js


def test_every_control_the_script_asks_for_exists_on_the_page():
    """The whole class of bug behind "Cannot set properties of null".

    Restoring a saved scene died on getElementById("scrubber"): the element
    is called "timeline-scrubber", the lookup returned null, and the failure
    surfaced as a symptom with no name in it (reported from the screen,
    2026-09-04). Panels are being reorganised week by week and controls are
    being removed outright, so a stale id is not a one-off: this walks every
    id the script asks for and checks the page still has it.

    The exceptions below are ids the script CREATES or looks up defensively,
    which are honest and stay listed by name rather than by pattern."""

    import re

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    # Whole-line comments are dropped first: this file explains its own
    # fixes in prose, and a comment naming the id that USED to be wrong
    # would fail the check it was written to describe. Only lines that are
    # entirely a comment are removed, so no string literal is touched.
    code = " ".join(
        "" if line.lstrip().startswith("//") else line for line in js.splitlines())
    asked = set(re.findall(r'getElementById\("([a-z0-9-]+)"\)', code))
    present = set(re.findall(r'id="([a-z0-9-]+)"', html))
    created = set()  # nothing is built by script id today; add names here, never patterns
    missing = sorted(asked - present - created)
    assert not missing, "the script talks to controls the page does not have: {}".format(missing)


def test_the_hdri_ground_sits_below_the_studio_floor():
    """Photographed 2026-09-04: with the two grounds at exactly the same
    height, the floor tore into interleaved stripes of grass and paving
    across its whole width. That is the depth test with nothing to decide.
    The photograph now sits a finger's width below the studio's floor, so
    the floor wins everywhere it exists and the photograph carries on
    beyond its rim. Both places that position the dome apply the drop: the
    one that builds it, and the one that re-levels an existing dome when
    the shell thickness changes."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "const HDRI_DROP = 0.05;" in js
    assert js.count("groundLevel() - HDRI_DROP") == 1
    assert js.count("level - HDRI_DROP") == 1
    backdrop = _function_body(js, "applyHdriBackdrop")
    assert "groundLevel() - HDRI_DROP" in backdrop
    ground = _function_body(js, "rebuildGround")
    assert "level - HDRI_DROP" in ground
    assert "ground.position.z = level;" in ground, (
        "the studio's own floor stays at the level everything stands on"
    )


def test_the_studio_opens_where_it_was_left():
    """Param: "can we get the bench studio to remember the last vault that
    was selected and shown, and the same view and scene too". It keeps the
    same record a saved scene carries, in browser storage rather than beside
    the scenes on disk: this is a per-window convenience, not a document,
    and it must never turn up in the scene picker as a scene nobody saved.

    A freshly imported export still wins over the memory, because that is
    the studio being asked to show something now. And a remembered cut that
    is no longer possible (a Skin that has gone, a re-export the studio's
    own cutter refuses) falls back to opening the study plainly rather than
    leaving the viewport empty."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'const SESSION_KEY = "bench-studio-session";' in js
    remember = _function_body(js, "rememberSession")
    assert "collectScene()" in remember
    # The whole line, indentation included: a text pin that matched the
    # call anywhere would pass a write that had been commented out or
    # guarded off, which is exactly the mutation this was proved against.
    assert "\n    localStorage.setItem(SESSION_KEY, JSON.stringify({" in remember
    assert '"beforeunload", rememberSession' in js
    boot = _function_body(js, "boot")
    assert "rememberedSession()" in boot
    assert "applyScene(remembered)" in boot
    assert "const remembered = preferredExport ? null : rememberedSession();" in boot, (
        "a fresh import beats the memory"
    )
    assert "if (restored === false && toLoad)" in boot, (
        "a remembered cut that is no longer possible must not leave an empty viewport"
    )


def test_the_take_ends_on_the_vault_not_on_the_strike():
    """Param: "at the end of the animation when the form work drops away,
    can we continue the rotation one more time so we look at the final form
    once too". The timeline gains a last act after the strike, one
    revolution at the spin rate in force, floored so a still camera still
    pauses on the result and capped so a very slow spin cannot quietly add a
    minute to every take and every recording."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    duration = _function_body(js, "timelineDuration")
    assert "admireSeconds()" in duration
    admire = _function_body(js, "admireSeconds")
    assert "(2 * Math.PI) / spin" in admire
    assert "ADMIRE_MIN_SECONDS" in admire and "ADMIRE_MAX_SECONDS" in admire
    # The strike itself is unchanged: it still clamps at 1, so the tail
    # holds the struck state rather than replaying it.
    assert "Math.min(1, (build - buildEnd) / STRIKE_SECONDS)" in js


def test_a_scene_keeps_the_prop_sizes_and_the_floors_lay_angle():
    """Param's walk found the floor Randomise doing nothing: sliding a
    periodic pattern lands the grid back on itself, so the button now
    deals a fresh LAY ANGLE too -- and what the eye composed must survive
    a scene round trip. Prop scale was saved to layouts but silently
    dropped from scenes; both it and the rotation ride along now."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    # The save carries them...
    assert "rotation: state.ground.rotation" in js
    assert "scale: record.scale," in js
    # ...the restore reads them back...
    assert ('if (typeof scene_.ground.rotation === "number") '
            "state.ground.rotation = scene_.ground.rotation;") in js
    # ...and the button actually deals an angle the floor then wears.
    assert "state.ground.rotation = Math.random() * Math.PI * 2;" in js
    assert js.count("texture.rotation = state.ground.rotation || 0;") == 1
    assert "material.map.rotation = state.ground.rotation || 0;" in js
    # The picker thumbnails stay squared up: the lay angle is the floor's.
    assert "material.map.rotation = 0;" in js


def test_asset_loads_announce_themselves_on_the_glass():
    """Param: "lets have it say its loading in translucent pop up message
    with a loading animation". One counted toast covers the four asset
    loaders -- skin material, floor material, sky, props -- so overlapping
    loads keep a single card up until the last of them lands."""

    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="loading-toast"' in page and 'id="loading-spin"' in page
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = _function_body(js, "beginLoading")
    assert "loadingHeld += 1" in body
    assert 'classList.remove("hidden")' in body
    # The four wired loaders, each with a fitting label.
    assert 'beginLoading("Loading sky " + name)' in js
    assert 'beginLoading("Preparing sky " + name + " at full quality")' in js
    assert 'beginLoading("Loading " + (entry.label || "material"))' in js
    assert 'beginLoading("Loading floor " + (entry.label || key))' in js
    assert 'beginLoading("Loading " + entries.length + " props")' in js
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "#loading-toast {" in css and "var(--scrim)" in css.split("#loading-toast {")[1][:400]


def test_the_visible_sky_is_served_at_source_resolution():
    """Param: "some say 24k others 16k most i downloaded at 8k and they
    are all so blurry... i would like them at maximum quality please".
    The lighting file stays small by design; the BACKDROP the eye looks
    at is now derived at the GPU texture ceiling, clamped by each sky's
    own source width, under a versioned name so stale 2048-wide
    derivations cannot shadow the new builds."""

    import hdri_preview
    assert hdri_preview.BACKGROUND_WIDTH == 16384
    assert hdri_preview.LIGHTING_WIDTH == 1024, "lighting stays prefilter-sized"
    app_source = (STATIC.parent / "app.py").read_text(encoding="utf-8")
    assert '".bg-full.png"' in app_source
    assert '".bg.png"' not in app_source


def test_the_shelf_is_the_asset_browser_and_stays_open():
    """Param: "a little tile at the bottom where if you click it, it
    expands... 4 columns a row, more space to breathe, scroll around it,
    give it categories to click through" -- and for materials "a button
    in this expandable tile where it says assign to skin or assign to
    ground". The panel pickers open the shelf now; the props grid lives
    in it; a prop click carries but never closes it."""

    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="shelf-body"' in page and 'id="shelf-tabs"' in page
    for kind in ("props", "materials", "skies"):
        assert 'data-shelf="' + kind + '"' in page
    assert 'id="shelf-assign-skin"' in page and 'id="shelf-assign-ground"' in page
    # The sky dials live in the drawer, beside the pictures they tune.
    assert page.index('id="hdri-projection"') > page.index('id="shelf-sky-settings"')
    assert 'id="prop-library"' not in page, "the old inline prop popover is gone"
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function openShelf(kind)" in js
    assert "if (openInstead) { openInstead(); return; }" in js, (
        "the asset pickers open the shelf instead of the inline grids"
    )
    assert 'assignShelfMaterial("render-skin")' in js
    assert 'assignShelfMaterial("ground-preset")' in js
    grid = (STATIC / "studio.css").read_text(encoding="utf-8")
    assert "repeat(4, 1fr)" in grid.split("#shelf-body .tile-grid {")[1][:200]


def test_picking_survives_the_frame_it_was_born_in():
    """Raycast trusts matrixWorld as stored, and an object created this
    frame has not rendered yet: the gumball raycast against a ring still
    sitting at the origin, and returned null -- measured live before the
    updateMatrixWorld calls went in. The outline must also never catch
    the pointer: a line raycast has a one-metre default threshold."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "propGumball.updateMatrixWorld(true);" in js
    assert "propsGroup.updateMatrixWorld(true);" in js
    assert "propOutline.raycast = () => {};" in js
    # The slim look hides a fat invisible grab twin, Rhino's own trick.
    assert 'grabRing.userData.handle = "rotate";' in js
    assert 'grabGrip.userData.handle = "scale";' in js
