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
                  "cablenet-speed-note", "cablenet-demand", "cablenet-configuration",
                  "cablenet-configuration-note", "cablenet-recommend", "cablenet-recommend-note",
                  "cablenet-vary-toggle", "cablenet-parts", "cablenet-settled", "cablenet-holds",
                  "cablenet-grab", "cablenet-export", "cablenet-export-choose",
                  "cablenet-export-path", "cablenet-export-result"):
        assert '"{}"'.format(ident) in JS, ident
    assert 'from "./cablenet_model.js"' in JS
    # newtons is not among them: the controller writes no force of its own, the
    # prestress sentence having moved into the model beside the rope's
    for name in ("verdictOf", "demandSentences", "grabText", "curveSvg", "modifiedFrom",
                 "fallbackKey", "settledText", "rpmText", "shapeOf",
                 "ropeMismatch", "prestressNote"):
        assert name in JS, name
    assert "export function mountCableNet({" in JS


def test_price_never_reaches_the_panel():
    assert "money(" not in JS
    assert "unit_price" not in JS
    assert ".price" not in JS
    assert "£" not in JS


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
    for ident in ("cablenet-holds", "cablenet-grab", "cablenet-demand"):
        assert ident not in body, ident


def test_each_dial_keeps_its_reading_beside_the_track():
    """The interface language: a dial states the value it has, in a reading
    named <slider-id>-value, written by whoever owns the dial."""

    for ident in ("cablenet-prestress-value", "cablenet-speed-value"):
        assert '"{}"'.format(ident) in JS, ident
    body = _function_body(JS, "showDials")
    assert "el.prestressValue.textContent = el.prestress.value" in body
    assert "el.speedValue.textContent = el.speed.value" in body
    # and every move of either dial writes its reading
    for dial in ("prestress", "speed"):
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


def test_the_drive_is_shown_not_chosen_and_the_gearbox_follows_the_family():
    body = _function_body(JS, "renderParts")
    assert "pairing.drive_for" in body and "pairing.gearboxes_for" in body
    assert "parts.pairing || { drive_for: {}, gearboxes_for: {} }" in body
    assert "entries.filter(([key]) => allowed.includes(key))" in body
    kinds = body.split("const kinds")[1].split("];")[0]
    assert '"drive"' not in kinds
    assert "follows the motor" in JS


def test_vary_parts_opens_and_closes_the_block_and_the_button_wears_the_state():
    assert 'id="cablenet-parts" class="hidden"' in (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'el.parts.classList.toggle("hidden")' in JS
    assert 'el.varyToggle.classList.toggle("active", !el.parts.classList.contains("hidden"))' in JS


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


def test_the_recommend_note_gives_the_servers_reason_after_the_rule():
    body = _function_body(JS, "recommend")
    assert '(body.demand_note ? `<p>${esc(body.demand_note)}</p>` : "")' in body
    assert body.index("esc(body.rule)") < body.index("esc(body.demand_note)")


def test_the_reason_there_is_no_load_factor_is_said_once_through_the_model():
    """A row with no load factor carries the reason in load_factor_note: no demand
    at all, or one with no sizing block. The model words a missing capacity from
    its detail, so the reason goes in there and the first line says what is true.
    Printed as a paragraph of its own it said the same thing twice for an old
    document, and for a study with no demand at all the first line blamed a
    sizing block that was not there."""

    body = _function_body(JS, "renderHolds")
    assert "detail: row.load_factor_note" in body
    assert "<p>${esc(row.load_factor_note)}</p>" not in body


def test_the_demand_readout_carries_the_models_two_notes_and_follows_the_chosen_rope():
    """The rope the analysis ran for and the prestress it ran at are said in the
    model's words beside the demand. The rope note depends on the system chosen
    here, so every change of system redraws the readout: each of them ends in
    refresh."""

    body = _function_body(JS, "renderDemand")
    assert "ropeMismatch(panel.parts, demand, panel.configuration)" in body
    assert "prestressNote(demand, Number(el.prestress.value))" in body
    assert "the dial reads" not in JS, "that sentence is the model's, not the controller's"
    assert "renderDemand();" in _function_body(JS, "refresh")


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
    assert "return { reload, clear };" in JS
    # and a page without the section hands back one too, so the studio's call cannot throw
    assert "return { reload: async () => {}, clear: () => {} };" in JS
    body = _function_body(JS, "clear")
    for dropped in ("panel.demand = null", "panel.row = null", "panel.demandNote = null"):
        assert dropped + ";" in body, dropped
    for emptied in ('el.demand.innerHTML = ""', 'el.holds.innerHTML = ""', 'el.grab.innerHTML = ""',
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
    assert JS.count("esc(") >= 12
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
