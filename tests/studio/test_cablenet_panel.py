"""The section's controller, pinned by reading its text: there is no DOM in
the suite, so what can be held is what it fetches, what it never shows, and
that its judgement comes from the model file."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "cablenet.js").read_text(encoding="utf-8")
STUDIO = (STATIC / "studio.js").read_text(encoding="utf-8")


def _function_body(js, name):
    """One function's source, nested or not: it ends at the first closing
    brace standing at the same indentation as the declaration. The
    indentation is the line's own, so an `async` before the word `function`
    is not mistaken for part of it."""

    start = js.index("function {}(".format(name))
    line_start = js.rfind("\n", 0, start) + 1
    line = js[line_start:start]
    indent = line[:len(line) - len(line.lstrip())]
    return js[start:js.index("\n" + indent + "}", start)]


def test_the_controller_fills_the_skeleton_and_judges_through_the_model():
    for ident in ("cablenet-run", "cablenet-run-status", "cablenet-prestress", "cablenet-speed",
                  "cablenet-tolerance", "cablenet-tolerance-value",
                  "cablenet-speed-note", "cablenet-demand", "cablenet-motor", "cablenet-ratio",
                  "cablenet-pulley", "cablenet-rope", "cablenet-wires", "cablenet-recommend",
                  "cablenet-recommend-note", "cablenet-machine", "cablenet-holds",
                  "cablenet-travel", "cablenet-buy", "cablenet-price",
                  "cablenet-graphs", "cablenet-limits", "cablenet-motors",
                  "cablenet-wires-value", "cablenet-popup", "cablenet-popup-toggle",
                  "cablenet-popup-close", "cablenet-export", "cablenet-export-choose",
                  "cablenet-export-path", "cablenet-export-result"):
        assert '"{}"'.format(ident) in JS, ident
    assert 'from "./cablenet_model.js"' in JS
    # newtons is not among them: the controller writes no force of its own
    for name in ("menuAnswers", "answersHtml", "runWarnings", "graphsHtml", "rpmText",
                 "choiceOptions", "validChoices", "machineHtml", "verdictHtml", "travelHtml",
                 "buyHtml", "priceHtml", "recommendHtml", "limitsHtml", "motorsHtml",
                 "eyeBoltHtml"):
        assert name in JS, name
    assert "export function mountCableNet({" in JS


def test_the_run_sends_the_tolerance_dial_and_the_demand_says_when_it_has_moved():
    assert "tolerance_mm: Number(el.tolerance.value)" in _function_body(JS, "startRun")
    assert "tolerance: Number(el.tolerance.value)" in _function_body(JS, "renderDemand")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    # 20 mm: the placement tolerance the T1 brief sets at full scale
    assert ('<input id="cablenet-tolerance" type="range" min="1" max="100" step="1" '
            'value="20">') in html
    assert '<b id="cablenet-tolerance-value">20</b><em>mm</em>' in html


def test_prices_show_in_the_panel_through_the_model():
    """The owner's ruling of 9 October 2026 reverses 8 October's: the panel shows
    each part's price, the cabinet list and the study total, a floor where a
    line is unpriced, in the model's words."""

    body = _function_body(JS, "renderHolds")
    assert "priceHtml(row.price)" in body
    assert "buyHtml(row.price, row.cut_lengths)" in body
    assert "£" not in JS, "the controller writes no money of its own"


def test_the_demand_run_score_and_export_all_carry_the_study_options():
    assert "studyOptions()" in JS
    body = _function_body(JS, "demandUrl")
    for key in ("material", "pattern", "size", "thickness", "density", "source"):
        assert key in body, key
    assert "/cablenet/run" in JS and "/api/runs/" in JS
    assert "/cablenet/recommend" in JS and "/cablenet/configurations" in JS
    assert "/cablenet/exports" in JS
    # the score, the recommend and the export each send the options
    for name in ("score", "recommend", "runExport"):
        assert "options" in _function_body(JS, name), name


def test_a_null_or_empty_option_is_left_out_of_every_query_and_body():
    """studyOptions() may carry source: null. The server reads a null material
    or size as the text "None" or refuses it, so a value the study does not
    have is not sent: not in the demand's query string, and not in the body of
    the score, the recommend, the run or the export."""

    helper = _function_body(JS, "sentOptions")
    assert "!= null" in helper and '!== ""' in helper
    assert '!= null && options[key] !== ""' in _function_body(JS, "demandUrl")
    for name in ("score", "recommend", "startRun", "runExport"):
        assert "sentOptions(" in _function_body(JS, name), name
    # no request spreads the raw options
    assert "...options" not in JS


def test_the_speed_dial_only_annotates():
    body = _function_body(JS, "annotateSpeed")
    assert "cablenet-speed-note" in body
    for ident in ("cablenet-holds", "cablenet-graphs", "cablenet-demand"):
        assert ident not in body, ident


def test_each_dial_keeps_its_reading_beside_the_track():
    """The interface language: a dial states the value it has, in a reading
    named <slider-id>-value, written by whoever owns the dial."""

    for ident in ("cablenet-prestress-value", "cablenet-speed-value", "cablenet-wires-value"):
        assert '"{}"'.format(ident) in JS, ident
    body = _function_body(JS, "showDials")
    assert "el.prestressValue.textContent = el.prestress.value" in body
    assert "el.speedValue.textContent = el.speed.value" in body
    assert "el.wiresValue.textContent = el.wires.value" in body
    # and every move of a dial writes its reading
    for dial in ("prestress", "speed", "wires"):
        listener = JS[JS.index('el.{}.addEventListener("input"'.format(dial)):]
        assert "showDials();" in listener[:listener.index("});")], dial


def test_nothing_is_asked_of_the_server_before_a_study_is_open():
    """Mounted at boot, before any study is open, the section would otherwise
    call /api/studies//cablenet/... and paint the 404 over a panel that has
    done nothing wrong."""

    for name in ("refresh", "annotateSpeed", "recommend", "startRun"):
        assert "!studyName()" in _function_body(JS, name), name


def test_a_late_answer_cannot_overwrite_a_newer_one_nor_the_speed_dial_swallow_a_verdict():
    """The verdict and the speed note have a ticket each. Sharing one, a move of
    the speed dial while the parts were being scored threw the verdict away and
    left the panel describing the previous parts."""

    speed = _function_body(JS, "annotateSpeed")
    assert "panel.speedTicket" in speed and "panel.ticket" not in speed
    verdict = _function_body(JS, "refresh")
    assert "++panel.ticket" in verdict and "panel.speedTicket" in verdict
    # an answer is drawn only if it is still the newest, whether it succeeded or failed
    assert verdict.count("mine !== panel.ticket") == 2
    assert speed.count("mine !== panel.speedTicket") == 2


def test_the_five_selects_offer_only_what_the_catalogue_can_build():
    assert "choiceOptions(panel.options, panel.parts, panel.choices)" in _function_body(
        JS, "renderChoices")
    # every change is made valid before it is kept: a ratio the new motor's frame
    # does not offer, or a pulley the new wire does not fit, gives way
    assert "validChoices(panel.options," in JS
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for ident in ("cablenet-motor", "cablenet-ratio", "cablenet-pulley", "cablenet-rope",
                  "cablenet-wires"):
        assert 'id="{}"'.format(ident) in html, ident
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    for gone in ("cablenet-configuration", "cablenet-vary-toggle", "cablenet-parts",
                 "cablenet-settled"):
        assert gone not in html and gone not in JS and gone not in css, gone


def test_the_choices_are_remembered_per_study_in_this_browser():
    assert "REMEMBERED_PREFIX + studyName()" in _function_body(JS, "restoreChoices")
    assert "REMEMBERED_PREFIX + studyName()" in _function_body(JS, "saveChoices")
    assert "restoreChoices();" in _function_body(JS, "reload")


def test_a_409_is_watched_only_when_the_live_run_is_a_cable_net_run():
    """The Analysis section's own watcher reloads the study when a run it knows
    ends and calls it an analysis, so a staged run is never watched from here:
    the status line says one is live and the button is given back."""

    body = _function_body(JS, "startRun")
    after = body[body.index("409"):]
    checked = after.index('kind === "cable net"')
    assert after.index("/api/runs/") < checked < after.index("watch(")
    assert checked < after.index("a staged analysis is live on this study")
    assert "the cable net run can start when it finishes" in after
    # in the staged branch itself, not merely somewhere later in the function
    staged = after[after.index("a staged analysis is live on this study"):]
    assert "el.run.disabled = false" in staged[:staged.index("return;")]


def test_recommend_searches_the_choices_and_fills_the_selects():
    body = _function_body(JS, "recommend")
    assert 'search: "choices"' in body
    assert "recommendHtml(body)" in body
    assert "panel.choices = validChoices(panel.options, body.choices)" in body


def test_the_machine_verdict_travel_wire_and_price_are_the_models_tables():
    body = _function_body(JS, "renderHolds")
    for call in ("machineHtml(row, panel.parts)", "verdictHtml(row.verdict)",
                 "travelHtml(row.travel)"):
        assert call in body, call
    assert "verdictOf" not in JS


def test_the_menu_answers_in_values_and_warns_in_one_line_each():
    """Needed, Gives and Most, then a line for each dial or wire the run on
    screen differs from (spec 2026-10-09 Cable net display, section 3). The
    answers follow the machine chosen, so the scored row redraws them."""

    body = _function_body(JS, "renderDemand")
    assert "answersHtml(menuAnswers(demand, panel.row, panel.strongest))" in body
    assert ("runWarnings(demand, { prestress: Number(el.prestress.value), "
            "tolerance: Number(el.tolerance.value) }, panel.parts, "
            "panel.choices && panel.choices.rope)") in body
    assert '<div class="cablenet-warning">${esc(line)}</div>' in body
    assert "<p>" not in body
    assert "renderDemand();" in _function_body(JS, "refresh")
    assert "renderDemand();" in _function_body(JS, "renderHolds")
    assert "panel.strongest = scored.strongest || null;" in _function_body(JS, "score")


def test_the_graphs_tab_is_the_models_and_follows_the_demand_and_the_machine():
    body = _function_body(JS, "renderGraphs")
    assert "el.graphs.innerHTML = graphsHtml(panel.demand, ceiling);" in body
    assert "renderGraphs();" in _function_body(JS, "loadDemand")
    assert "renderGraphs();" in _function_body(JS, "renderHolds")


def test_the_menu_is_short_and_the_mechanism_cost_and_graphs_are_in_the_pop_up():
    """Spec 2026-10-09 Cable net display, sections 3 and 4."""

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<details id="cablenet-section">'
    section = html[html.index(opening):]
    section = section[:section.index("</details>")]
    order = ["cablenet-run", "cablenet-tolerance", "cablenet-prestress", "cablenet-wires",
             "cablenet-demand", "cablenet-popup-toggle", "cablenet-lenses", "cablenet-stage"]
    places = [section.index('id="{}"'.format(ident)) for ident in order]
    assert places == sorted(places)
    assert '<input id="cablenet-wires" type="range" min="1" max="7" step="1" value="1">' in section
    for moved in ("cablenet-motor", "cablenet-recommend", "cablenet-machine", "cablenet-price",
                  "cablenet-export", "cablenet-speed", "cablenet-graphs"):
        assert 'id="{}"'.format(moved) not in section, moved
    popup = html[html.index('<div id="cablenet-popup" class="hidden">'):]
    popup = popup[:popup.index("<!-- the end of the cable net pop-up -->")]
    assert html.index('<div id="cablenet-popup"') > html.index("</aside>"), "outside the side menu"
    for tab, members in (("cn-mechanism", ("cablenet-motor", "cablenet-ratio", "cablenet-pulley",
                                            "cablenet-rope", "cablenet-recommend",
                                            "cablenet-limits", "cablenet-motors",
                                            "cablenet-machine", "cablenet-holds",
                                            "cablenet-travel", "cablenet-speed")),
                         ("cn-cost", ("cablenet-price", "cablenet-buy", "cablenet-export")),
                         ("cn-graphs", ("cablenet-graphs",))):
        assert '<button data-cn-tab="{}"'.format(tab) in popup, tab
        pane = popup[popup.index('<div id="{}"'.format(tab)):]
        pane = pane[:pane.index("<!-- /{} -->".format(tab))]
        for ident in members:
            assert 'id="{}"'.format(ident) in pane, (tab, ident)


def test_the_pop_up_opens_and_shuts_from_the_menu_and_remembers_its_tab():
    body = _function_body(JS, "setPopup")
    assert 'el.popup.classList.toggle("hidden", !open);' in body
    assert "if (open) onPopup();" in body and "savePopup();" in body
    assert 'el.popupToggle.addEventListener("click", () => setPopup(el.popup.classList.contains("hidden")));' in JS
    assert 'el.popupClose.addEventListener("click", () => setPopup(false));' in JS
    assert 'const POPUP_KEY = "vaulted-cablenet-popup";' in JS
    tab = _function_body(JS, "showTab")
    assert 'pane.classList.toggle("hidden", pane.id !== id)' in tab and "savePopup();" in tab
    assert "return { reload, clear, closePopup: () => setPopup(false) };" in JS


def test_the_pop_up_takes_the_left_from_the_data_sheet_and_the_live_graphs():
    mount = STUDIO[STUDIO.index("const cableNet = mountCableNet({"):]
    hand = mount[mount.index("onPopup: () => {"):]
    hand = hand[:hand.index("\n  },")]
    assert 'document.getElementById("data-panel").classList.add("hidden");' in hand
    assert "setGraphsTucked(true);" in hand
    data = STUDIO[STUDIO.index('document.getElementById("data-button").addEventListener("click"'):]
    data = data[:data.index("});")]
    assert "cableNet.closePopup();" in data


def test_every_motor_is_scored_only_while_the_mechanism_tab_is_in_view():
    body = _function_body(JS, "renderMotors")
    assert 'el.popup.classList.contains("hidden") || panel.tab !== "cn-mechanism"' in body
    assert "validChoices(panel.options, { ...panel.choices, motor: motor.key })" in body
    assert "++panel.motorsTicket" in body and body.count("mine !== panel.motorsTicket") == 2
    assert "motorsHtml(scored.rows, panel.choices.motor)" in body
    assert "renderMotors();" in _function_body(JS, "renderHolds")
    click = JS[JS.index('el.motors.addEventListener("click"'):]
    click = click[:click.index("\n  });")]
    assert 'event.target.closest("tr[data-motor]")' in click and "refresh();" in click


def test_every_motor_is_scored_once_for_what_it_depends_on():
    """Review 6: the rows depend on the study, its options, the choices but
    the motor, and the demand; opening the pop-up again or choosing a motor
    redraws them from what was scored, and clear() forgets it."""

    body = _function_body(JS, "renderMotors")
    assert "const key = JSON.stringify([studyName(), body, panel.demandTicket]);" in body
    assert "if (key === panel.motorsKey && panel.motorsRows) {" in body
    assert "panel.motorsKey = key;" in body and "panel.motorsRows = scored.rows;" in body
    clear = _function_body(JS, "clear")
    assert "panel.motorsKey = null;" in clear and "panel.motorsRows = null;" in clear


def test_the_wires_slider_chooses_wires_a_motor():
    listener = JS[JS.index('el.wires.addEventListener("change"'):]
    listener = listener[:listener.index("\n  });")]
    assert "wires_per_motor: Number(el.wires.value)" in listener
    assert "refresh();" in listener
    assert "el.wires.value = String(panel.choices.wires_per_motor);" in _function_body(
        JS, "renderChoices")


def test_the_chosen_motor_is_marked_by_more_than_a_tint():
    # found on screen: the chosen row's colour alone read like every other row
    css = (STATIC / "studio.css").read_text(encoding="utf-8")
    rule = css[css.index("#cablenet-motors tr.chosen td {"):]
    rule = rule[:rule.index("}")]
    assert "background: var(--raised);" in rule and "font-weight: 600;" in rule


def test_the_limits_and_the_eye_bolt_are_tables_and_no_readout_is_a_paragraph():
    body = _function_body(JS, "renderHolds")
    assert "limitsHtml(row.terms)" in body
    assert "eyeBoltHtml(ASSUMED_ANGLE_DEGREES)" in body
    assert "<p>" not in JS


def test_a_late_demand_cannot_replace_a_newer_one():
    body = _function_body(JS, "loadDemand")
    assert "++panel.demandTicket" in body
    # the answer is applied after the wait, and only if it is still the newest
    assert body.index("mine !== panel.demandTicket") < body.index("panel.demand = demand")
    assert "if (mine !== panel.demandTicket) return false;" in body
    # a load that was overtaken (or cleared) leaves the rescoring to whoever overtook it
    for name in ("reload", "watch"):
        assert "if (await loadDemand()) await refresh();" in _function_body(JS, name), name


def test_clear_empties_everything_that_belongs_to_the_study_on_screen():
    assert "return { reload, clear, closePopup: () => setPopup(false) };" in JS
    # and a page without the section hands back one too, so the studio's call cannot throw
    assert "return { reload: async () => {}, clear: () => {}, closePopup: () => {} };" in JS
    body = _function_body(JS, "clear")
    for dropped in ("panel.demand = null", "panel.row = null", "panel.demandNote = null"):
        assert dropped + ";" in body, dropped
    for emptied in ('el.demand.innerHTML = ""', 'el.holds.innerHTML = ""', 'el.graphs.innerHTML = ""',
                    'el.limits.innerHTML = ""', 'el.motors.innerHTML = ""',
                    'el.runStatus.textContent = ""', 'el.recommendNote.innerHTML = ""',
                    'el.result.innerHTML = ""'):
        assert emptied + ";" in body, emptied
    # Export is disabled, with its reason, because there is no demand left
    assert "showExport();" in body
    assert "el.exportButton.disabled = !panel.demand" in _function_body(JS, "showExport")
    assert "onDemand(null);" in body and "onCeiling(null);" in body
    # an answer still in flight cannot paint over the emptiness, and neither can a run being watched
    for ticket in ("panel.ticket += 1", "panel.speedTicket += 1", "panel.demandTicket += 1"):
        assert ticket + ";" in body, ticket
    assert "stopWatching();" in body and "el.run.disabled = false;" in body
    watch = _function_body(JS, "watch")
    assert watch.count("panel.watcher !== poll") == 2
    stop = _function_body(JS, "stopWatching")
    assert "clearInterval(panel.watcher)" in stop and "panel.watcher = null" in stop


def test_export_is_off_while_it_writes_and_given_back_with_its_reason():
    body = _function_body(JS, "runExport")
    assert body.index("el.exportButton.disabled = true;") < body.index("} finally {\n      showExport();")


def test_every_server_string_is_escaped_and_nothing_is_rounded_to_whole_newtons():
    # the tables escape inside the model (test_cablenet_choices.py)
    assert JS.count("esc(") >= 9
    assert not re.search(r"toFixed\(\d\)\}? N\b", JS)


def test_the_controller_loads_where_there_is_no_page(tmp_path):
    """Importing it touches no document, and every name it takes from the model
    is a name the model gives: a mismatch would leave the section dead in the
    browser, with nothing else in the suite to say so."""

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path / "load.mjs"
    module = (STATIC / "cablenet.js").resolve().as_uri()
    script.write_text(
        "import * as controller from {!r};\nconsole.log(Object.keys(controller).join());\n".format(module),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "mountCableNet"


def test_the_studio_mounts_the_section_and_not_the_data_tab():
    assert "cablenet-panel" not in STUDIO
    assert "mountCableNet({" in STUDIO


def test_the_scoring_call_sends_the_choices_and_the_study_and_nothing_else():
    # the route judges the choices on the study's demand; a floor or a wound
    # length of the panel's own is read by nothing
    body = _function_body(JS, "score")
    assert "choices: [panel.choices]" in body
    assert "prestress_floor" not in body and "rope_wound_mm" not in body
