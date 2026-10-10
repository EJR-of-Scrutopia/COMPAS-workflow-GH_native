"""The Formwork tab's controller and the studio's side of it (spec 2026-10-10
formwork tab, sections 5 to 9): what the run sends, what the player draws, and
how the studio stands still for the tab. Every figure comes from the model,
tested under node, and the drawing from the view, tested with three.js; this
pins the wiring, as the Cable net tab's tests do."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "formwork.js").read_text(encoding="utf-8")
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")
CABLENET = (STATIC / "cablenet.js").read_text(encoding="utf-8")
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


def test_the_run_sends_the_cut_the_machine_and_the_wall_and_never_a_prestress():
    # the server takes the cable net run's design prestress (section 6)
    body = _inner(JS, "startRun")
    assert "...sentOptions(options), wires_per_motor: c.wires_per_motor," in body
    assert "pulleys: c.pulleys, wall: c.wall" in body and "body.rope = c.rope" in body
    # the holds' choice, and the Cable net tab's tolerance the search meets
    assert "holds: holdsChoice(), tolerance_mm: Number(tolerance())" in body
    assert "/formwork/run" in body and "prestress" not in body
    watch = _inner(JS, "watch")
    assert "`capture ${run.stage} of ${run.of}`" in watch and "await load();" in watch
    # a search says which try it is on, and that it takes longer (found by the
    # final review: the counter climbed to 101 and dropped back with no word)
    assert 'tab.searching = holdsChoice() === "search";' in body
    assert ('el.runStatus.textContent = tab.searching ? "starting: a few minutes, one run a '
            'spacing tried" : "starting: about two minutes";') in body
    assert 'const named = tab.searching && typeof run.message === "string" && run.message.includes(": ");' in watch
    assert 'named ? run.message.split(": ")[0] + ": " + counter : counter' in watch


def test_no_run_is_said_only_once_the_document_has_been_looked_for():
    # found on screen: opening the tab drew "No formwork run: Run formwork
    # analysis" while the 6 MB document was still loading, an invitation to
    # start a search of several minutes for nothing
    load = _inner(JS, "load")
    assert load.index("tab.loading = true;") < load.index("await getJson(simUrl(")
    assert load.index("if (mine !== tab.ticket) return;") < load.index("tab.loading = false;")
    warnings = _inner(JS, "renderWarnings")
    assert warnings.startswith('function renderWarnings() {\n'
                               '    if (tab.loading) { el.warnings.innerHTML = ""; return; }')


def test_the_machine_is_the_cable_net_tabs_one_a_study():
    chosen = _inner(JS, "chosen")
    assert "const choices = machine();" in chosen and "choices.pulley != null" in chosen
    assert "wall: Number(el.wall.value), prestress: designPrestress()" in chosen
    assert "machine: () => (cableNet.choices ? cableNet.choices() : null)," in STUDIO
    assert "choices: () => panel.choices" in CABLENET


def test_the_player_draws_blended_and_shows_the_nearer_capture():
    draw = _inner(JS, "draw")
    assert "const head = playhead(tab.times, tab.at);" in draw
    assert "view.show(head, now);" in draw and "hooks.showMachine(!!now.show.wires);" in draw
    assert "el.label.textContent = captureLabel(capture);" in draw
    assert "el.line.innerHTML = frameLineHtml(frameLine(tab.sim, head.nearer));" in draw
    assert "rebuildLabels(head.nearer, labelKindsInView(now.labels, now.show));" in draw
    assert "hooks.legend(colourKey(now.colour, tab.sim, now.tolerance));" in draw
    tick = _inner(JS, "tick")
    assert "tab.at = Math.min(tab.at + seconds * tab.speed, end());" in tick
    load = _inner(JS, "load")
    assert "tab.times = sim ? captureTimes(sim.captures) : [];" in load
    assert "tab.worst = sim ? worstTables(sim) : null;" in load and "view.build(sim);" in load
    assert 'el.holds.innerHTML = sim ? holdsHtml(sim) : "";' in load
    assert 'el.holds.innerHTML = "";' in _inner(JS, "clear")


def test_a_worst_header_sorts_and_a_row_moves_the_player_and_the_camera():
    assert ('tab.sort = key === tab.sort.key ? { key, descending: !tab.sort.descending }'
            in JS)
    assert "goTo(Number(row.dataset.capture));" in JS
    assert ("hooks.aim(view.point({ kind: row.dataset.kind, index: Number(row.dataset.index) }));"
            in JS)
    aim = _top(STUDIO, "aimFormworkAt")
    assert "camera.position.add(target.clone().sub(controls.target));" in aim
    assert "controls.target.copy(target);" in aim


def test_the_studio_stands_still_while_the_tab_is_open():
    assert "let formworkTab = null;" in STUDIO
    # declared above renderView, which a render during boot calls
    assert STUDIO.index("let formworkTab = null;") < STUDIO.index("function renderView()")
    frame = _top(STUDIO, "frame")
    assert "if (formworkTab && formworkTab.active()) {" in frame
    assert "holdStudioForFormwork();" in frame and "formworkTab.tick(delta);" in frame
    assert frame.index("formworkTab.tick(delta);") < frame.index(
        "applyTimeline(Math.min(state.timeline.t + delta * state.timeline.speed")
    assert ('if (formworkTab) formworkTab.setActive(sectionId === "formwork-section");'
            in _top(STUDIO, "activateTab"))
    assert "if (formworkTab) formworkTab.place();" in _top(STUDIO, "renderView")
    hold = _top(STUDIO, "studioFormworkObjects")
    for name in ("shell", "falsework", "wires", "nodes", "principal", "columns", "holdMarkers"):
        assert "state.objects." + name in hold, name
    assert 'key.endsWith("Arrows")' in hold
    leave = _top(STUDIO, "leaveFormworkTab")
    for line in ("formworkView.group.visible = false;",
                 "for (const object of formworkHidden) object.visible = true;",
                 "applySceneAtTime(formworkTakeT);", "applyShowMode();",
                 "if (cableNetLensUp()) paintCableNetLenses(true);"):
        assert line in leave, line
    assert "formworkView.group.visible = true;" in _top(STUDIO, "enterFormworkTab")
    assert "formworkTab.setActive(!document.getElementById(\"formwork-section\").classList.contains(\"hidden\"));" in STUDIO


def test_a_click_goes_to_the_formwork_card_while_the_tab_is_open():
    up = _top(STUDIO, "releaseCableNetPress")
    assert "if (formworkTab && formworkTab.active()) formworkTab.pick(event);" in up
    assert "else pickCableNetNode(event);" in up
    pick = _inner(JS, "pick")
    assert "view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY)" in pick
    assert "formworkPickHtml(tab.sim, head.nearer, node)" in pick


def test_a_new_study_clears_the_tab_and_reloads_it():
    assert STUDIO.count("if (formworkTab) formworkTab.clear();") == 2
    assert STUDIO.count("formworkTab.reload();") == 2
    # a change of machine or of the cable net run reaches the warnings
    assert STUDIO.count("if (formworkTab) formworkTab.refresh();") == 2


def test_the_pop_ups_and_the_data_sheet_take_turns_on_the_left():
    mount = STUDIO[STUDIO.index("const cableNet = mountCableNet({"):]
    hand = mount[mount.index("onPopup: () => {"):]
    hand = hand[:hand.index("\n  },")]
    assert "if (formworkTab) formworkTab.closePopup();" in hand
    mine = STUDIO[STUDIO.index("formworkTab = mountFormwork({"):]
    mine = mine[mine.index("onPopup: () => {"):]
    mine = mine[:mine.index("\n    },")]
    assert "cableNet.closePopup();" in mine
    assert 'document.getElementById("data-panel").classList.add("hidden");' in mine
    data = STUDIO[STUDIO.index('document.getElementById("data-button").addEventListener("click"'):]
    data = data[:data.index("});")]
    assert "if (formworkTab) formworkTab.closePopup();" in data


def test_the_check_on_screen_reaches_the_drawing_and_never_his_studio():
    # spec section 12: the check finds the Formwork drawing through the probe
    # hook, and runs against a spare port, never Param's 8600
    hook = STUDIO[STUDIO.index("window.__studio = {"):]
    hook = hook[:hook.index("};") + 2]
    assert "formworkView" in hook
    # and the props, which the check puts out of view: a forest streaming in
    # under SwiftShader makes a frame take a quarter of an hour
    assert "formworkView, propsGroup" in hook
    script = (STATIC.parents[1] / "scripts" / "formwork_screens.mjs").read_text(encoding="utf-8")
    assert 'process.env.STUDIO_URL || "http://127.0.0.1:8601"' in script
    assert "8600" not in script.replace("never Param's 8600", "")
    for step in ("03-raise", "04-finish", "05-hold", "06-tiling", "-colour-", "-show-",
                 "-labels", "-worst-", "-fly-to", "-card", "-left"):
        assert step in script, step


def test_the_capture_label_keeps_to_one_line():
    # found on screen: "t 100 hold" wrapped onto three lines beside the buttons
    assert ("#panel #formwork-label { color: var(--ink); font-size: var(--t-2); "
            "margin-left: var(--s2);\n  white-space: nowrap; }") in CSS


def test_the_studio_s_own_act_is_hidden_and_the_take_comes_back_as_it_was():
    # final review 1 and 5: the act's net and columns are the studio's own;
    # the machine stands at its working place (the act's end) while the tab is
    # open; leaving puts the take's clock back and repaints the Forces key
    hold = _top(STUDIO, "studioFormworkObjects")
    assert "formworkObjects && formworkObjects.group" in hold
    enter = _top(STUDIO, "enterFormworkTab")
    assert "formworkTakeT = state.timeline ? state.timeline.t : null;" in enter
    assert ("if (state.bundle && state.timeline && formworkSeconds() > 0) "
            "applySceneAtTime(formworkSeconds());") in enter
    leave = _top(STUDIO, "leaveFormworkTab")
    assert "if (state.bundle && formworkTakeT != null) applySceneAtTime(formworkTakeT);" in leave
    assert "applySceneAtTime(state.timeline.t);" not in leave
    assert "if (state.bundle) applyWireForces();" in leave
    assert leave.index("applyShowMode();") < leave.index("applyWireForces();")
    # the tab opened at boot (the remembered tab) is entered only once the whole
    # module has run: the hook reads the act's objects, declared further down
    boot = 'formworkTab.setActive(!document.getElementById("formwork-section").classList.contains("hidden"));'
    assert STUDIO.count(boot) == 1
    assert STUDIO.index("let formworkObjects = null;") < STUDIO.index(boot)
    assert STUDIO.index(boot) > STUDIO.index("window.__studioReady = true;")


def test_the_take_stands_still_while_the_tab_is_open():
    # final review 2: the shelf's Play and Restart and the space bar would
    # switch the studio into the take's view under the tab
    for name in ("togglePlay", "restartTake", "rewindTake"):
        body = _top(STUDIO, name)
        first = body.split("{", 1)[1].strip().splitlines()[0]
        assert first == "if (formworkTab && formworkTab.active()) return;", name


def test_a_throw_in_the_player_stops_the_player_and_not_the_studio():
    # final review 9: frame() reschedules itself only on a normal exit
    tick = _inner(JS, "tick")
    assert "try {" in tick and "} catch (error) {" in tick
    assert "setPlaying(false);" in tick[tick.index("} catch (error) {"):]
    assert "el.runStatus.textContent = error.message;" in tick


def test_the_tab_records_the_raise_through_the_studio_s_recorder():
    # the owner's choice of 10 October 2026: Record in the Formwork tab plays
    # the captures through the studio's recorder, with the tab's labels and key
    assert 'el.record.addEventListener("click", () => hooks.record());' in JS
    assert "record: toggleRecording," in STUDIO
    seek = JS[JS.index("    seek(seconds) {"):]
    seek = seek[:seek.index("\n    },")]
    assert "tab.at = Math.min(Math.max(seconds, 0), end());" in seek and "draw();" in seek
    overlay = JS[JS.index("    overlay(ctx, width, height) {"):]
    overlay = overlay[:overlay.index("\n    },")]
    assert "const rect = { left: 0, top: 0, width, height };" in overlay
    assert "labelKindsInView(now.labels, now.show)" in overlay
    assert "paintOverlay(ctx, { width, height, caption: recordingCaption(tab.sim, head.nearer)," in overlay
    take = _top(STUDIO, "recordAnimation")
    assert "const formwork = !!(formworkTab && formworkTab.active());" in take
    assert ('const status = document.getElementById(formwork ? "formwork-record-status" '
            ': "record-status");') in take
    assert "const speed = formwork ? formworkTab.recording.speed() : state.timeline.speed;" in take
    assert "Math.ceil(formworkTab.recording.duration() / speed * fps)" in take
    # the camera stays where he put it: no turntable, no take view
    assert "if (!formwork) captureOrbitBase(0);" in take
    assert "if (formwork) formworkTab.recording.seek(frameIndex * speed / fps);" in take
    assert "if (formwork) blob = await formworkFrame(canvas);" in take
    assert '(formwork ? "&kind=formwork" : "")' in take
    frame = _top(STUDIO, "formworkFrame")
    assert "ctx.drawImage(source, 0, 0);" in frame
    assert "formworkTab.recording.overlay(ctx, source.width, source.height);" in frame


def test_the_cable_net_labels_and_card_stand_down_while_the_tab_is_open():
    assert ("body.formwork-open #model-labels, body.formwork-open #cablenet-pick "
            "{ display: none; }") in CSS
    assert 'document.body.classList.toggle("formwork-open", on);' in _inner(JS, "setActive")
