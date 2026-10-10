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

from test_formwork_model import document

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

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
out.wire = [arr(parts.wires.geometry.attributes.position, 0, 6), arr(parts.wires.geometry.attributes.color, 0, 3)];
out.ground = [parts.ground.count, at(parts.ground, 0).p];
out.skin = [parts.skin.geometry.index.count, parts.skin.visible];
out.point = view.point({ kind: "node", index: 2 });
// the first tiling quarter: its face on, the skin riding the net
view.show({ from: 2, to: 2, blend: 0, nearer: 2 }, { show: every, colour: "deviation", tolerance: 20 });
out.skinOn = [Array.from(parts.skin.geometry.index.array), parts.skin.visible,
              arr(parts.skin.geometry.attributes.position, 6, 3)];
out.deviation = [arr(parts.net.geometry.attributes.color, 0, 3), arr(parts.net.geometry.attributes.color, 9, 3)];
view.show({ from: 3, to: 3, blend: 0, nearer: 3 }, { show: every, colour: "utilisation", tolerance: 20 });
out.utilisation = [colourAt(parts.trees, 0), arr(parts.net.geometry.attributes.color, 0, 3),
                   colourAt(parts.heads, 0)];
view.show({ from: 1, to: 1, blend: 0, nearer: 1 }, { show: every, colour: "wire", tolerance: 20 });
out.wireColour = arr(parts.wires.geometry.attributes.color, 0, 3);
view.show({ from: 1, to: 1, blend: 0, nearer: 1 },
          { show: { ...every, trees: false, heads: false, design: false, ground: false },
            colour: "off", tolerance: 20 });
out.hidden = [parts.trees.visible, parts.heads.visible, parts.push.visible, parts.design.visible,
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
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork_view") / "harness.mjs"
    script.write_text(HARNESS % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "model": (STATIC / "formwork_model.js").resolve().as_uri(),
        "view": (STATIC / "formwork_view.js").resolve().as_uri(),
        "doc": json.dumps(document())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_view_builds_its_own_objects_and_the_still_ones_once(out):
    # net, design, wires, push, trees, heads, anchors, ground and skin
    assert out["children"] == 9
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
    assert out["netColour"] == pytest.approx([(c + (r - c) * f) / 255 for c, r in zip(cream, red)],
                                             abs=1e-6)
    # the tree member from its foot to its head, as long as the lift so far
    assert out["tree"]["p"] == pytest.approx([1.0, 1.0, 0.125])
    assert out["tree"]["s"][1] == pytest.approx(0.25)
    # and a label rides the drawing, not the capture
    assert out["point"] == pytest.approx([1.0, 1.0, 0.25])


def test_a_head_is_marked_while_it_pushes_and_its_push_is_drawn(out):
    position, colour = out["head"]
    assert position == pytest.approx([1.0, 1.0, 0.25])
    assert colour == pytest.approx([0x3f / 255, 0x9e / 255, 0x57 / 255])
    # 800 N up, half a metre a kilonewton
    assert out["push"] == pytest.approx([1.0, 1.0, 0.25, 1.0, 1.0, 0.65])
    # and a head that has let go is drawn clear
    assert out["utilisation"][2] == pytest.approx([0x9a / 255, 0xa4 / 255, 0xb2 / 255])


def test_each_wire_runs_from_its_node_the_way_it_runs_in(out):
    line, colour = out["wire"]
    assert line == pytest.approx([0, 0, 0, -0.3, 0, 0])
    assert colour == pytest.approx([0.86, 0.86, 0.86])
    f = 1200 / 1500
    assert out["wireColour"] == pytest.approx(
        [(c + (r - c) * f) / 255 for c, r in zip([0xf2, 0xef, 0xe8], [0xcc, 0x22, 0x11])], abs=1e-6)


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
    assert within == pytest.approx([0xf2 / 255, 0xef / 255, 0xe8 / 255])
    assert near == pytest.approx([0xc9 / 255, 0x9a / 255, 0x2e / 255])
    tree, net, _ = out["utilisation"]
    assert tree == pytest.approx([0xcc / 255, 0x22 / 255, 0x11 / 255], abs=1e-6)
    assert net == pytest.approx([0.86, 0.86, 0.86])


def test_the_ticks_show_and_hide_each_part(out):
    assert out["hidden"] == [False, False, False, False, False, True, True, True]


def test_a_click_finds_the_nearest_node_on_screen(out):
    on, off = out["projected"]
    assert on == pytest.approx([300, 100]) and off is None
    assert out["nearest"] == [2, None]


def test_closing_the_tab_removes_everything(out):
    assert out["cleared"] == [0, None, None]
