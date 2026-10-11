"""The one Cable net tab's controller and the studio's side of it (spec
2026-10-11 one Cable net tab, sections 4, 5 and 7): what the run sends, what
the player draws, the answer, the reruns, and how the studio stands still for
the tab. Every figure comes from the model, tested under node, and the drawing
from the view, tested with three.js; this pins the wiring."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "formwork.js").read_text(encoding="utf-8")
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")
PICK = (STATIC / "mechanism_pick.js").read_text(encoding="utf-8")
CSS = (STATIC / "studio.css").read_text(encoding="utf-8")


def _top(js, name):
    """A top level function, brace to closing brace (written at column 0)."""

    start = js.index("function {}(".format(name))
    return js[start:js.index("\n}", start)]


def _inner(js, name):
    """A function inside mountFormwork, indented two spaces."""

    start = js.index("function {}(".format(name))
    return js[start:js.index("\n  }\n", start)]


def test_the_controller_loads_where_there_is_no_page(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path / "load.mjs"
    module = (STATIC / "formwork.js").resolve().as_uri()
    script.write_text("import * as controller from {!r};\n"
                      "console.log(Object.keys(controller).join());\n".format(module),
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "mountFormwork"


def test_the_run_sends_the_mechanism_the_wall_and_the_rods_and_never_a_prestress():
    # spec section 4.2: the server cuts the net for one spool's pull; section
    # 7: the tolerance is no run, and a run for other rods starts from the hold
    body = _inner(JS, "startRun")
    assert body.startswith("function startRun(resume = false) {")
    assert "const choices = mechanism.chosen();" in body
    assert 'if (!choices) { el.runStatus.textContent = "Choose a mechanism"; return; }' in body
    assert ("const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),\n"
            "                     holds_per_side: Number(el.holds.value), resume };") in body
    assert "/formwork/run" in body and "prestress" not in body and "tolerance" not in body
    # Run is always a full run: the click's event is not a resume
    assert 'el.run.addEventListener("click", () => startRun(false));' in JS
    assert 'el.runStatus.textContent = "starting: about two minutes";' in body
    watch = _inner(JS, "watch")
    assert "`capture ${run.stage} of ${run.of}`" in watch and "await load();" in watch


def test_no_run_is_said_only_once_the_document_has_been_looked_for():
    # found on screen: "No formwork run" showed while the 6 MB document loaded
    load = _inner(JS, "load")
    assert load.index("tab.loading = true;") < load.index("await getJson(simUrl(")
    assert load.index("if (mine !== tab.ticket) return;") < load.index("tab.loading = false;")
    warnings = _inner(JS, "renderWarnings")
    assert warnings.startswith('function renderWarnings() {\n'
                               '    if (tab.loading) { el.warnings.innerHTML = ""; return; }')


def test_the_mechanism_is_the_pop_ups_and_a_change_reruns_once_it_settles():
    # spec sections 4.4 and 7: a change of mechanism or of wires a motor greys
    # the answer and starts a run one second after the last change
    assert "mechanism: mechanismPick," in STUDIO
    assert "const mechanismPick = mountMechanism({" in STUDIO
    assert STUDIO.index("const mechanismPick = mountMechanism({") < STUDIO.index(
        "formworkTab = mountFormwork({")
    assert ("onChange: (choices, byHand) => { if (formworkTab) formworkTab.mechanismChanged("
            "choices, byHand); },") in STUDIO
    changed = _inner(JS, "mechanismChanged")
    assert ('if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) '
            "scheduleRerun(false);") in changed
    assert "const RERUN_SETTLE_MS = 1000;" in JS
    rerun = _inner(JS, "scheduleRerun")
    assert "}, RERUN_SETTLE_MS);" in rerun and "startRun(tab.resume);" in rerun
    assert "mechanism.setWires(Number(el.wires.value));" in JS
    # the pop-up says whether a change was his hand or a list read again
    assert "onChange(chosen(), true);" in PICK and "onChange(chosen(), false);" in PICK


def test_rods_a_side_rerun_from_the_hold_once_they_settle():
    # spec sections 6 and 7: Holds a side, 0 to 20; a change reruns from the
    # state at the hold one second after the last change, and a full run
    # waiting wins over one from the hold
    rerun = _inner(JS, "scheduleRerun")
    assert rerun.startswith("function scheduleRerun(resume = false) {")
    assert "tab.resume = tab.rerun == null ? resume : tab.resume && resume;" in rerun
    assert "tab.rerun = null;" in rerun and "startRun(tab.resume);" in rerun
    assert ('if (tab.sim && outOfDate().includes("Run again: rods a side changed")) '
            "scheduleRerun(true);") in JS
    out_of_date = _inner(JS, "outOfDate")
    assert ("formworkWarnings(tab.sim, { mechanism: mechanism.chosen(),\n"
            "                                       holdsPerSide: Number(el.holds.value) })"
            ) in out_of_date
    watch = _inner(JS, "watch")
    assert ('if (lines.includes("Run again: mechanism changed")) scheduleRerun(false);\n'
            '          else if (lines.includes("Run again: rods a side changed")) '
            "scheduleRerun(true);") in watch
    # the slider shows the run's rods when a study's run is first read, and
    # is his from then on
    load = _inner(JS, "load")
    assert "const first = !tab.sim;" in load
    assert "if (sim && first) setHolds(sim.holdsPerSide);" in load


def test_the_answer_greys_when_out_of_date_and_its_needed_goes_to_the_wire():
    render = _inner(JS, "renderAnswer")
    assert 'const stale = outOfDate().some((line) => line.startsWith("Run again"));' in render
    assert ("el.answer.innerHTML = answerHtml(answer(tab.judged, Number(el.tolerance.value)), "
            "{ stale });") in render
    assert "goTo(Number(row.dataset.capture));" in JS
    assert 'hooks.aim(view.point({ kind: "wire", index: Number(row.dataset.wire) }));' in JS
    aim = _top(STUDIO, "aimFormworkAt")
    assert "camera.position.add(target.clone().sub(controls.target));" in aim


def test_the_player_draws_blended_values_the_weakest_and_its_key():
    draw = _inner(JS, "draw")
    assert "const head = playhead(tab.times, tab.at);" in draw
    assert ("const weakest = now.weakestOn ? weakestAt(tab.judged, head.nearer, limits()) : [];"
            in draw)
    assert "view.show(head, { ...now, weakest });" in draw
    assert "hooks.legend(colourKey(now.colour, tab.judged, limits()));" in draw
    assert "rebuildLabels(head.nearer, labelled(now));" in draw
    assert "el.line.innerHTML = frameLineHtml(frameLine(tab.judged, head.nearer));" in draw
    # play and pause in the studio's own symbols
    assert 'const PLAY = "▶";' in JS and 'const PAUSE = "❚❚";' in JS
    assert "el.play.textContent = tab.playing ? PAUSE : PLAY;" in _inner(JS, "setPlaying")
    tick = _inner(JS, "tick")
    assert "tab.at = Math.min(tab.at + seconds * tab.speed, end());" in tick
    load = _inner(JS, "load")
    assert "tab.times = sim ? captureTimes(sim.captures) : [];" in load and "view.build(sim);" in load
    assert "mechanism.setChecks(sim ? sim.checks : null);" in load


def test_a_new_wall_is_judged_without_a_run():
    judge = _inner(JS, "judge")
    assert ("tab.judged = tab.sim && tab.sim.trees.wall !== wall ? withWall(tab.sim, wall) : tab.sim;"
            in judge)


def test_compare_and_weakest_are_buttons_that_stay_lit():
    assert 'el.compare.classList.toggle("active", tab.compare);' in JS
    assert 'el.weakest.classList.toggle("active", tab.weakest);' in JS
    assert "el.mechanismToggle.addEventListener(\"click\", () => mechanism.toggle());" in JS


def test_the_studio_stands_still_while_the_tab_is_open():
    assert "let formworkTab = null;" in STUDIO
    assert STUDIO.index("let formworkTab = null;") < STUDIO.index("function renderView()")
    frame = _top(STUDIO, "frame")
    assert "if (formworkTab && formworkTab.active()) {" in frame
    assert "holdStudioForFormwork();" in frame and "formworkTab.tick(delta);" in frame
    assert ('if (formworkTab) formworkTab.setActive(sectionId === "formwork-section");'
            in _top(STUDIO, "activateTab"))
    assert "if (formworkTab) formworkTab.place();" in _top(STUDIO, "renderView")
    leave = _top(STUDIO, "leaveFormworkTab")
    for line in ("formworkView.group.visible = false;",
                 "for (const object of formworkHidden) object.visible = true;",
                 "applySceneAtTime(formworkTakeT);", "applyShowMode();"):
        assert line in leave, line
    assert "formworkView.group.visible = true;" in _top(STUDIO, "enterFormworkTab")
    boot = 'formworkTab.setActive(!document.getElementById("formwork-section").classList.contains("hidden"));'
    assert STUDIO.count(boot) == 1
    assert STUDIO.index(boot) > STUDIO.index("window.__studioReady = true;")


def test_a_tab_remembered_as_the_old_cable_net_opens_the_one_tab():
    assert 'if (remembered === "cablenet-section") remembered = "formwork-section";' in STUDIO


def test_the_key_is_the_ramp_with_its_limit_at_its_place():
    legend = _top(STUDIO, "paintFormworkLegend")
    assert "paintRampLegend(key);" in legend
    ramp = _top(STUDIO, "paintRampLegend")
    assert 'mark.style.left = (100 * key.fraction).toFixed(1) + "%";' in ramp
    assert 'document.getElementById("legend-limit-text").textContent = key.limitText || "";' in ramp


def test_the_old_machine_models_are_not_drawn_for_now():
    # spec section 5.5: "they are the old ones"; the permanent works stay
    assert "const MACHINE_PLANT_SHOWN = false;" in STUDIO
    assert "if (!MACHINE_PLANT_SHOWN) temporary.visible = false;" in STUDIO


def test_the_pop_ups_and_the_data_sheet_take_turns_on_the_left():
    mine = STUDIO[STUDIO.index("const mechanismPick = mountMechanism({"):]
    mine = mine[mine.index("onPopup: () => {"):]
    mine = mine[:mine.index("\n  },")]
    assert 'document.getElementById("data-panel").classList.add("hidden");' in mine
    data = STUDIO[STUDIO.index('document.getElementById("data-button").addEventListener("click"'):]
    data = data[:data.index("});")]
    assert "if (formworkTab) formworkTab.closePopup();" in data


def test_the_check_on_screen_reaches_the_drawing_and_never_his_studio():
    hook = STUDIO[STUDIO.index("window.__studio = {"):]
    hook = hook[:hook.index("};") + 2]
    assert "formworkView, propsGroup" in hook
    script = (STATIC.parents[1] / "scripts" / "formwork_screens.mjs").read_text(encoding="utf-8")
    assert 'process.env.STUDIO_URL || "http://127.0.0.1:8601"' in script
    assert "8600" not in script.replace("never Param's 8600", "")
    for step in ("03-raise", "04-finish", "05-hold", "06-tiling", "-colour-", "-show-",
                 "-values", "-compare", "-weakest", "-skin-", "-mechanism", "-card", "-left"):
        assert step in script, step
    assert "-worst-" not in script


def test_the_capture_label_keeps_to_one_line():
    assert ("#panel #formwork-label { color: var(--ink); font-size: var(--t-2); "
            "margin-left: var(--s2);\n  white-space: nowrap; }") in CSS


def test_the_take_stands_still_while_the_tab_is_open():
    for name in ("togglePlay", "restartTake", "rewindTake"):
        body = _top(STUDIO, name)
        first = body.split("{", 1)[1].strip().splitlines()[0]
        assert first == "if (formworkTab && formworkTab.active()) return;", name


def test_a_throw_in_the_player_stops_the_player_and_not_the_studio():
    tick = _inner(JS, "tick")
    assert "try {" in tick and "} catch (error) {" in tick
    assert "setPlaying(false);" in tick[tick.index("} catch (error) {"):]
    assert "el.runStatus.textContent = error.message;" in tick


def test_the_tab_records_the_raise_through_the_studio_s_recorder():
    assert 'el.record.addEventListener("click", () => hooks.record());' in JS
    assert "record: toggleRecording," in STUDIO
    seek = JS[JS.index("    seek(seconds) {"):]
    seek = seek[:seek.index("\n    },")]
    assert "tab.at = Math.min(Math.max(seconds, 0), end());" in seek and "draw();" in seek
    overlay = JS[JS.index("    overlay(ctx, width, height) {"):]
    overlay = overlay[:overlay.index("\n    },")]
    assert "const by = labelled(now);" in overlay
    assert "paintOverlay(ctx, { width, height, caption: recordingCaption(tab.judged, head.nearer)," in overlay
    take = _top(STUDIO, "recordAnimation")
    assert "const formwork = !!(formworkTab && formworkTab.active());" in take
    assert "if (formwork) formworkTab.recording.seek(frameIndex * speed / fps);" in take
    frame = _top(STUDIO, "formworkFrame")
    assert "formworkTab.recording.overlay(ctx, source.width, source.height);" in frame


def test_the_studio_labels_and_card_stand_down_while_the_tab_is_open():
    assert 'document.body.classList.toggle("formwork-open", on);' in _inner(JS, "setActive")
