"""The Cable net lenses on the model, pinned by reading studio.js (spec
2026-10-09 Cable net display, section 5): the grey shell, colour and a legend
on every lens, the arrows behind a tick, numbers on the model and the card a
click opens. The figures themselves come from cablenet_model.js and are tested
under node in test_cablenet_lenses.py."""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
JS = (STATIC / "studio.js").read_text(encoding="utf-8")
CONTROLLER = (STATIC / "cablenet.js").read_text(encoding="utf-8")
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "studio.css").read_text(encoding="utf-8")


def _function_body(js, name):
    start = js.index("function {}(".format(name))
    line_start = js.rfind("\n", 0, start) + 1
    line = js[line_start:start]
    indent = line[:len(line) - len(line.lstrip())]
    return js[start:js.index("\n" + indent + "}", start)]


def test_the_shell_is_light_transparent_grey_while_a_lens_is_up_and_itself_after():
    assert "const GHOST_GREY = 0xdcdcdc;" in JS and "const GHOST_OPACITY = 0.3;" in JS
    ghost = _function_body(JS, "ghostPiece")
    assert "material.opacity = GHOST_OPACITY;" in ghost
    assert "material.color.setHex(GHOST_GREY);" in ghost and "material.map = null;" in ghost
    # each piece's own colour, texture and opacity are kept and come back
    for kept in ("kept.ghostColor = ", "kept.ghostMap = ", "material.map = kept.ghostMap;",
                 "material.color.setHex(kept.ghostColor);", "delete kept.ghostColor;",
                 "delete kept.ghostMap;"):
        assert kept in ghost, kept


def test_node_force_colours_the_nodes_and_each_new_lens_draws_its_legend():
    paint = _function_body(JS, "applyCableNetPaint")
    assert 'const keyed = ["nodeforce", "prestress", "reel"].filter(up);' in paint
    assert "paintNodeForces(stage)" in paint
    # sag colours the nodes itself, so node force paints them only when sag is down
    assert 'const forceNodes = !sagOn && !!stage && keyed.includes("nodeforce");' in paint
    assert "paintLensLegend(keyed[0], stage)" in paint
    nodes = _function_body(JS, "paintNodeForces")
    assert "TENSION_SCALE(sizes[i] || 0, top)" in nodes
    legend = _function_body(JS, "paintLensLegend")
    assert "lensLegend(lens, state.cablenet, stage, state.cablenetCeiling)" in legend


def test_the_arrows_stand_behind_a_tick_off_for_node_force_on_for_the_wires():
    assert 'const CABLENET_ARROW_LENSES = ["nodeforce", "prestress", "reel"];' in JS
    assert "cablenetArrows: { nodeforce: false, prestress: true, reel: true }," in JS
    vectors = _function_body(JS, "updateCableNetVectors")
    for lens in ("nodeforce", "reel", "prestress"):
        assert "state.layers.{0} && state.cablenetArrows.{0}".format(lens) in vectors, lens
    lenses = _function_body(JS, "buildLensButtons")
    assert "CABLENET_ARROW_LENSES.includes(name)" in lenses
    assert 'box.type = "checkbox";' in lenses
    assert "state.cablenetArrows[name] = box.checked;" in lenses


def test_numbers_ride_the_model_from_the_models_targets():
    assert '<div id="model-labels"></div>' in HTML
    assert "const MODEL_LABEL_MAX = 125;" in JS
    update = _function_body(JS, "updateModelLabels")
    assert "labelTargets(lens, state.cablenet, stage, state.cablenetCeiling)" in update
    assert "targets.slice(0, MODEL_LABEL_MAX)" in update
    # the labels and the card read the instant the lenses were painted at
    assert "updateModelLabels(stage);" in _function_body(JS, "paintCableNetLenses")
    place = _function_body(JS, "placeModelLabels")
    # projected every frame as the hover badge is; behind the eye or off the view: not drawn
    assert ".project(camera)" in place
    assert "projected.z <= 1 && x >= 0 && x <= 1 && y >= 0 && y <= 1" in place
    # labels that would print over one another give way (found on screen)
    assert "const LABEL_GAP_X = 44;" in JS and "const LABEL_GAP_Y = 16;" in JS
    assert "spreadLabels(points, LABEL_GAP_X, LABEL_GAP_Y)" in place
    # under the legend, never over it
    assert "#model-labels { position: fixed; inset: 0; pointer-events: none; z-index: 14; }" in CSS
    assert "placeModelLabels();" in _function_body(JS, "renderView")
    assert "body.stilling #model-labels" in CSS


def test_a_click_on_a_node_opens_its_card_and_a_drag_does_not():
    assert '<div id="cablenet-pick" class="hidden"></div>' in HTML
    assert 'canvas.addEventListener("pointerdown", noteCableNetPress);' in JS
    assert 'canvas.addEventListener("pointerup", releaseCableNetPress);' in JS
    # a press a stamp, an aim, a carry or prop editing owns never opens the card
    press = _function_body(JS, "noteCableNetPress")
    for owner in ("!stampRig", "!aimingLight", "!state.carrying", "!state.propEdit"):
        assert owner in press, owner
    up = _function_body(JS, "releaseCableNetPress")
    assert "Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 4" in up
    assert "pickCableNetNode(event);" in up
    pick = _function_body(JS, "pickCableNetNode")
    assert "const stage = modelLabels.stage;" in pick and "cableNetLensUp()" in pick
    assert "pickHtml(state.cablenet, stage, best.i, state.cablenetVerdict)" in pick
    assert 'card.classList.add("hidden");' in pick
    # above the bottom shelf (z-index 25) and inside the view, found on screen
    # cut off under the shelf
    assert "#cablenet-pick { position: fixed; z-index: 27;" in CSS
    assert "innerHeight - card.offsetHeight - CARD_CLEAR_BOTTOM" in pick


def test_the_card_reads_each_wires_own_ceiling_from_the_scored_row():
    assert ("onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, "
            "ok ? row.verdict : null);") in CONTROLLER
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict) => {" in mount
    assert "state.cablenetVerdict = verdict || null;" in mount
