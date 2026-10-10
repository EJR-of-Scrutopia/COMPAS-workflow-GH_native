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


def test_the_holds_lens_paints_the_nodes_to_hold_and_follows_the_machine():
    # spec 2026-10-10 prestress and holds, section 7
    table = JS[JS.index("const CABLENET_LAYERS = ["):]
    assert '["holds", "Holds"]' in table[:table.index("];")]
    availability = _function_body(JS, "layerAvailability")
    assert 'name === "holds" && !(state.cablenet.needs && Array.isArray(state.cablenet.needs.steps))' in availability
    paint = _function_body(JS, "applyCableNetPaint")
    assert 'const keyed = ["holds", "nodeforce", "prestress", "reel"].filter(up);' in paint
    assert 'const holdNodes = !sagOn && !!stage && keyed.includes("holds");' in paint
    assert 'const forceNodes = !sagOn && !!stage && !holdNodes && keyed.includes("nodeforce");' in paint
    assert "paintHoldNodes()" in paint
    holds = _function_body(JS, "paintHoldNodes")
    assert "holdsFor(state.cablenet, state.cablenetCeiling)" in holds
    assert "HOLD_COLOURS.hold" in holds and "HOLD_COLOURS.head" in holds
    # the held nodes and the column heads marked large enough to be seen at a
    # whole-vault framing (found on screen: 640 red dots the size of the net's
    # nodes could not be made out), riding with the net, gone with the lens
    assert "paintHoldMarkers(hold, heads);" in holds
    markers = _function_body(JS, "paintHoldMarkers")
    assert "new THREE.InstancedMesh(nodes.geometry" in markers
    assert "nodes.getMatrixAt(" in markers and "HOLD_MARKER_SCALE" in markers
    assert "markers.position.copy(nodes.position);" in markers
    assert "clearHoldMarkers();" in markers
    assert "const HOLD_MARKER_SCALE = 3;" in JS
    assert "if (!holdNodes) clearHoldMarkers();" in paint
    assert '"holds"' in _function_body(JS, "updateModelLabels")
    assert ("lensLegend(lens, state.cablenet, stage, state.cablenetCeiling, state.cablenetMost)"
            in _function_body(JS, "paintLensLegend"))
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict, most) => {" in mount
    assert "state.cablenetMost = most == null ? null : most;" in mount
    assert "(state.layers.prestress || state.layers.holds)" in mount


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
    assert "paintNodeForces(stage)" in paint
    # sag colours the nodes itself, so node force paints them only when sag is
    # down (and Holds, which colours them too, is not up)
    assert 'keyed.includes("nodeforce")' in paint and "!sagOn" in paint
    assert "paintLensLegend(keyed[0], stage)" in paint
    nodes = _function_body(JS, "paintNodeForces")
    assert "TENSION_SCALE(sizes[i] || 0, top)" in nodes
    legend = _function_body(JS, "paintLensLegend")
    assert "lensLegend(lens, state.cablenet, stage, state.cablenetCeiling" in legend
    # a banded lens is keyed by its bands, and every other legend clears them
    assert "if (legend.bands) paintBandLegend(legend.title, legend.bands, legend.min, legend.max);" in legend
    bands = _function_body(JS, "paintBandLegend")
    assert 'legend.classList.add("bands");' in bands and "escapeHtml(band.name)" in bands
    for writer in ("paintScalarLegend", "paintForceLegend", "updateLegend"):
        assert 'legend.classList.remove("bands");' in _function_body(JS, writer), writer
    assert '<div id="legend-bands"></div>' in HTML
    assert "#legend.bands #legend-bar { display: none; }" in CSS
    assert "#legend.bands #legend-bands { display: flex; }" in CSS


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
    # never over the side menu: a point past the panel's left edge is not drawn
    # (review 4)
    assert "const right = viewRight();" in place and "sx < right" in place
    edge = _function_body(JS, "viewRight")
    assert 'document.body.classList.contains("panel-collapsed")' in edge
    assert ".getBoundingClientRect().left" in edge
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
    assert "innerHeight - card.offsetHeight - CARD_CLEAR_BOTTOM" in _function_body(JS, "placeCard")
    assert "placeCard(card, best.x, best.y);" in pick
    assert "viewRight() - CARD_WIDTH" in _function_body(JS, "placeCard")
    # the card rides with its node as the view moves, as the labels do
    # (review 7), and a press the scatter tools own opens none (review 11)
    assert "cablenetPick.at = " in pick
    assert "placeCablenetPick(rect, lift);" in _function_body(JS, "placeModelLabels")
    ride = _function_body(JS, "placeCablenetPick")
    assert "cablenetPick.at" in ride and 'card.classList.add("hidden")' in ride
    assert "!state.scatterArmed" in press


def test_the_card_reads_each_wires_own_ceiling_from_the_scored_row():
    assert ("onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, "
            "ok ? row.verdict : null, panel.strongest ? panel.strongest.ceiling_newtons : null);"
            ) in CONTROLLER
    mount = JS[JS.index("const cableNet = mountCableNet({"):]
    assert "onCeiling: (ceiling, verdict, most) => {" in mount
    assert "state.cablenetVerdict = verdict || null;" in mount
