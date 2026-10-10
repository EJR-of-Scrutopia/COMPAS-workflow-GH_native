"""The Formwork tab's drawing, run under node with the studio's own three.js
(spec 2026-10-10 formwork tab, sections 7 and 8): its own objects built from
the capture document, moved and coloured from the captures, shown by the
ticks, and gone when the tab closes."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document, with_holds

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def linear(rgb):
    """An sRGB colour, 0 to 1, as three draws vertex and instance colours: in
    the linear working space. The key is painted in sRGB, so the model must be
    given these or it draws lighter than its key (found on screen: the net
    orange where the key says red)."""

    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]

HARNESS = """
import * as THREE from %(three)r;
import * as m from %(model)r;
import { createFormworkView } from %(view)r;
const sim = m.readSim(%(doc)s);
const view = createFormworkView(THREE);
const out = {};
const every = { net: true, trees: true, heads: true, wires: true, anchors: true, ground: true,
                skin: true, design: true };
const arr = (attribute, from, count) => Array.from(attribute.array.slice(from, from + count));
const at = (mesh, i) => { const m4 = new THREE.Matrix4(); mesh.getMatrixAt(i, m4);
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  m4.decompose(p, q, s); return { p: p.toArray(), s: s.toArray() }; };
const colourAt = (mesh, i) => { const c = new THREE.Color(); mesh.getColorAt(i, c); return [c.r, c.g, c.b]; };
view.build(sim);
const parts = view.parts();
out.children = view.group.children.length;
out.design = arr(parts.design.geometry.attributes.position, 6, 6);
out.anchors = [at(parts.anchors, 0).p, at(parts.anchors, 1).p, parts.anchors.count];
// half way from the first capture to the hold, the hold the nearer
view.show({ from: 0, to: 1, blend: 0.5, nearer: 1 }, { show: every, colour: "tension", tolerance: 20 });
out.net = arr(parts.net.geometry.attributes.position, 6, 6);
out.netColour = arr(parts.net.geometry.attributes.color, 6, 3);
out.tree = at(parts.trees, 0);
out.head = [at(parts.heads, 0).p, colourAt(parts.heads, 0)];
out.push = arr(parts.push.geometry.attributes.position, 0, 6);
out.tip = at(parts.tips, 0);
out.wire = [arr(parts.wires.geometry.attributes.position, 0, 6), arr(parts.wires.geometry.attributes.color, 0, 3)];
out.ground = [parts.ground.count, at(parts.ground, 0).p];
out.skin = [parts.skin.geometry.index.count, parts.skin.visible];
out.point = view.point({ kind: "node", index: 2 });
// the first tiling quarter: its face on, the skin riding the net
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "deviation", tolerance: 20 });
out.pushLongest = arr(parts.push.geometry.attributes.position, 0, 6);
out.skinOn = [Array.from(parts.skin.geometry.index.array), parts.skin.visible,
              arr(parts.skin.geometry.attributes.position, 6, 3)];
out.deviation = [arr(parts.net.geometry.attributes.color, 0, 3), arr(parts.net.geometry.attributes.color, 9, 3)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: every, colour: "utilisation", tolerance: 20 });
out.utilisation = [colourAt(parts.trees, 0), arr(parts.net.geometry.attributes.color, 0, 3),
                   colourAt(parts.heads, 0)];
view.show({ from: 1, to: 1, blend: 0, nearer: 1 }, { show: every, colour: "wire", tolerance: 20 });
out.wireColour = arr(parts.wires.geometry.attributes.color, 0, 3);
out.anchorColours = [colourAt(parts.anchors, 0), colourAt(parts.anchors, 1)];
view.show({ from: 1, to: 1, blend: 0, nearer: 1 },
          { show: { ...every, trees: false, heads: false, design: false, ground: false },
            colour: "off", tolerance: 20 });
out.anchorPlain = colourAt(parts.anchors, 0);
out.hidden = [parts.trees.visible, parts.heads.visible && parts.tips.visible === parts.heads.visible,
              parts.push.visible, parts.design.visible,
              parts.ground.visible, parts.net.visible, parts.wires.visible, parts.anchors.visible];
// a camera looking straight down on the square, 400 px a side for 4 m
const camera = new THREE.OrthographicCamera(-2, 2, 2, -2, 0.1, 100);
camera.position.set(0, 0, 10);
camera.lookAt(0, 0, 0);
camera.updateMatrixWorld();
camera.updateProjectionMatrix();
const rect = { left: 0, top: 0, width: 400, height: 400 };
out.projected = [view.project([1, 1, 0], camera, rect), view.project([3, 0, 0], camera, rect)];
out.nearest = [view.nearestNode(camera, rect, 302, 99), view.nearestNode(camera, rect, 250, 250)];
out.placed = [0, 1, 2, 3].map((i) => m.placedFaces(sim, i));
view.clear();
out.cleared = [view.group.children.length, view.parts(), view.point({ kind: "node", index: 0 })];
// the holds' props (spec 2026-10-10 formwork holds, section 5): node 2 held
const held = m.readSim(%(held)s);
view.build(held);
const props = () => view.parts().props;
const withHolds = { ...every, holds: true };
out.propsCount = view.group.children.length;
view.show({ from: 0, to: 0, blend: 0, nearer: 0 }, { show: withHolds, colour: "off", tolerance: 20 });
out.propsBefore = props().visible;
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: withHolds, colour: "off", tolerance: 20 });
out.propPushing = [props().visible, props().count, at(props(), 0), colourAt(props(), 0)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: withHolds, colour: "off", tolerance: 20 });
out.propPulling = [at(props(), 0), colourAt(props(), 0)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: every, colour: "off", tolerance: 20 });
out.propUnticked = props().visible;
view.clear();
// a hold set leaning: pulling 50 N down and sideways after the jacking
view.build(m.readSim(%(leaning)s));
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: withHolds, colour: "off", tolerance: 20 });
out.propLeaning = [at(props(), 0), colourAt(props(), 0)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: withHolds, colour: "off", tolerance: 20 });
out.propIdle = [at(props(), 0), colourAt(props(), 0)];
view.clear();
// a run with the capture after the jacking, after the hold at the same time
view.build(m.readSim(%(jacked)s));
view.show({ from: 1, to: 1, blend: 0, nearer: 1 }, { show: withHolds, colour: "off", tolerance: 20 });
out.jackedHold = props().visible;
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: withHolds, colour: "off", tolerance: 20 });
out.jackedSet = [props().visible, at(props(), 0), colourAt(props(), 0)];
view.clear();
console.log(JSON.stringify(out));
"""


def _held():
    doc = with_holds(document())
    doc["net"]["holds"] = [2]                      # a node with a height, for its prop
    return doc


def _jacked():
    # the hold, then the capture after the jacking at the same machine time,
    # the hold pushing 40 N straight up
    doc = _held()
    jacked = json.loads(json.dumps(doc["captures"][2]))
    jacked.update({"phase": "holds", "time": 100.0, "row": None, "quarter": None})
    doc["captures"].insert(2, jacked)
    return doc


def _leaning():
    doc = _held()
    doc["captures"][2]["hold_push"] = doc["captures"][3]["hold_push"]     # 30, 0, -40
    doc["captures"][3]["hold_push"] = doc["captures"][0]["hold_push"]     # nothing
    return doc


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork_view") / "harness.mjs"
    script.write_text(HARNESS % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "model": (STATIC / "formwork_model.js").resolve().as_uri(),
        "view": (STATIC / "formwork_view.js").resolve().as_uri(),
        "doc": json.dumps(document()), "held": json.dumps(_held()),
        "leaning": json.dumps(_leaning()), "jacked": json.dumps(_jacked())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_view_builds_its_own_objects_and_the_still_ones_once(out):
    # net, design, wires, push, its heads, trees, heads, anchors, ground, skin
    # and the holds' props
    assert out["children"] == 11
    # the designed form as a light line net: the second member, node 1 to 2
    assert out["design"] == pytest.approx([1.0, 0.0, 0.0, 1.0, 1.0, 0.5])
    first, second, count = out["anchors"]
    assert first == pytest.approx([0, 0, 0]) and second == pytest.approx([1.0, 0, 0]) and count == 2


def test_the_drawing_blends_the_positions_and_colours_from_the_nearer_capture(out):
    # half way through the lift: node 2 at 250 mm
    assert out["net"] == pytest.approx([1.0, 0.0, 0.0, 1.0, 1.0, 0.25])
    # the member's colour is the hold's 2.5 kN on the run's 3 kN scale
    cream, red = [0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11]
    f = 2500 / 3000
    assert out["netColour"] == pytest.approx(
        linear([(c + (r - c) * f) / 255 for c, r in zip(cream, red)]), abs=1e-6)
    # the tree member from its foot to its head, as long as the lift so far
    assert out["tree"]["p"] == pytest.approx([1.0, 1.0, 0.125])
    assert out["tree"]["s"][1] == pytest.approx(0.25)
    # and a label rides the drawing, not the capture
    assert out["point"] == pytest.approx([1.0, 1.0, 0.25])


def test_a_head_is_marked_while_it_pushes_and_its_push_is_drawn(out):
    position, colour = out["head"]
    assert position == pytest.approx([1.0, 1.0, 0.25])
    assert colour == pytest.approx(linear([0x3f / 255, 0x9e / 255, 0x57 / 255]))
    # 800 N up, on the run's own scale: the 95th percentile of its pushes,
    # 900 N here, drawn 1 m long (found on screen: at half a metre a
    # kilonewton the finish's pushes ran metres out of the picture; final
    # review 4: by the single largest, a spike, they vanished elsewhere)
    assert out["push"] == pytest.approx([1.0, 1.0, 0.25, 1.0, 1.0, 0.25 + 800 / 900])
    # and its head at the tip, pointing along the push
    assert out["tip"]["p"] == pytest.approx([1.0, 1.0, 0.25 + 800 / 900])
    # a push at the scale or over it is drawn 1 m long, no longer
    assert out["pushLongest"] == pytest.approx([1.0, 1.0, 0.5, 1.0, 1.0, 1.5])
    # and a head that has let go is drawn clear
    assert out["utilisation"][2] == pytest.approx(linear([0x9a / 255, 0xa4 / 255, 0xb2 / 255]))


def test_each_wire_runs_from_its_node_the_way_it_runs_in(out):
    line, colour = out["wire"]
    assert line == pytest.approx([0, 0, 0, -0.3, 0, 0])
    assert colour == pytest.approx(linear([0.86, 0.86, 0.86]))
    f = 1200 / 1500
    assert out["wireColour"] == pytest.approx(
        linear([(c + (r - c) * f) / 255 for c, r in zip([0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11])]),
        abs=1e-6)


def test_under_colour_by_wires_each_anchor_wears_its_wires_colour(out):
    # a wire runs straight down into its anchor, so its stub is hidden in the
    # rim beam: the anchor mark carries the wire's colour (found on screen)
    ramp = lambda f: linear([(c + (r - c) * f) / 255
                             for c, r in zip([0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11])])
    first, second = out["anchorColours"]
    assert first == pytest.approx(ramp(1200 / 1500), abs=1e-6)
    assert second == pytest.approx(ramp(900 / 1500), abs=1e-6)
    # and the anchors' own blue under any other choice
    assert out["anchorPlain"] == pytest.approx(linear([0x66 / 255, 0xaa / 255, 0xff / 255]), abs=1e-6)


def test_the_ground_contacts_are_the_nearer_captures(out):
    count, first = out["ground"]
    assert count == 1 and first == pytest.approx([0, 1.0, 0])


def test_the_skin_is_the_faces_placed_riding_the_net(out):
    assert out["skin"] == [0, False]
    index, visible, corner = out["skinOn"]
    assert index == [0, 1, 2, 0, 2, 3] and visible is True
    assert corner == pytest.approx([1.0, 1.0, 0.5])
    assert out["placed"] == [[], [], [0], [0]]


def test_each_colour_by_colours_its_own_part(out):
    within, near = out["deviation"]
    # node 0 at 5 mm is within 20; node 2 at 12 mm is near it
    assert within == pytest.approx(linear([0xf2 / 255, 0xef / 255, 0xe8 / 255]))
    assert near == pytest.approx(linear([0xc9 / 255, 0x9a / 255, 0x2e / 255]))
    tree, net, _ = out["utilisation"]
    # over its capacity: the over band (final review 3)
    assert tree == pytest.approx(linear([0xc2 / 255, 0x49 / 255, 0x36 / 255]), abs=1e-6)
    assert net == pytest.approx(linear([0.86, 0.86, 0.86]))


def test_the_ticks_show_and_hide_each_part(out):
    assert out["hidden"] == [False, False, False, False, False, True, True, True]


def test_a_click_finds_the_nearest_node_on_screen(out):
    on, off = out["projected"]
    assert on == pytest.approx([300, 100]) and off is None
    assert out["nearest"] == [2, None]


def test_closing_the_tab_removes_everything(out):
    assert out["cleared"] == [0, None, None]


GREEN = linear([0x3f / 255, 0x9e / 255, 0x57 / 255])
BLUE = linear([0x2f / 255, 0x6f / 255, 0xd0 / 255])
GREY = linear([0x9a / 255, 0xa4 / 255, 0xb2 / 255])


def test_each_hold_is_a_rod_from_the_ground_along_its_force_from_the_jacking_on(out):
    # ten objects with the holds' rods
    assert out["propsCount"] == 11
    # not in before the jacking
    assert out["propsBefore"] is False
    visible, count, prop, colour = out["propPushing"]
    assert visible is True and count == 1
    # node 2's design point is (1, 1, 0.5), pushed straight up after the
    # jacking: a strut half a metre tall standing under it, green
    assert prop["p"] == pytest.approx([1.0, 1.0, 0.25]) and prop["s"][1] == pytest.approx(0.5)
    assert colour == pytest.approx(GREEN)
    # later it pulls: the rod stays where it was set, blue
    later, pulling = out["propPulling"]
    assert later["p"] == pytest.approx([1.0, 1.0, 0.25]) and pulling == pytest.approx(BLUE)
    # the tick hides them
    assert out["propUnticked"] is False


def test_the_rods_stand_from_the_capture_after_the_jacking_and_not_at_the_hold(out):
    assert out["jackedHold"] is False
    visible, rod, colour = out["jackedSet"]
    assert visible is True and colour == pytest.approx(GREEN)
    assert rod["p"] == pytest.approx([1.0, 1.0, 0.25]) and rod["s"][1] == pytest.approx(0.5)


def test_a_hold_set_pulling_sideways_is_a_tie_down_along_its_pull(out):
    # 30, 0, -40 N at (1, 1, 0.5): the tie runs 0.6 out and 0.8 down a unit,
    # 0.625 m to the ground at (1.375, 1, 0), its middle at (1.1875, 1, 0.25)
    rod, colour = out["propLeaning"]
    assert rod["p"] == pytest.approx([1.1875, 1.0, 0.25]) and rod["s"][1] == pytest.approx(0.625)
    assert colour == pytest.approx(BLUE)
    # carrying nothing later: grey, still set at its angle
    idle, grey = out["propIdle"]
    assert idle["p"] == pytest.approx([1.1875, 1.0, 0.25]) and grey == pytest.approx(GREY)
