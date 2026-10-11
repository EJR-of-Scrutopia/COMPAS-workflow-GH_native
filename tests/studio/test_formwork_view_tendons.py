"""The across tendons drawn (spec 2026-10-11 across tendons, section 6): the
net coloured by Along, Across and Both with the other family grey, each rope
judged against its working load (his answer of 11 October 2026), and the
Tendons chip's tendons proud of the net with a reel at each column head, in
the colours of the ropes they run beside and white otherwise."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_tendons import with_tendons
from test_formwork_model import document
from test_formwork_view import STATIC, judged, linear

HARNESS = """
import * as THREE from %(three)r;
import * as m from %(model)r;
import { createFormworkView } from %(view)r;
const view = createFormworkView(THREE);
const out = {};
const every = { net: true, trees: true, heads: true, wires: true, anchors: true, ground: true,
                skin: true, design: true, tendons: true };
const arr = (attribute, from, count) => Array.from(attribute.array.slice(from, from + count));
const at = (mesh, i) => { const m4 = new THREE.Matrix4(); mesh.getMatrixAt(i, m4);
  const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  m4.decompose(p, q, s); return p.toArray(); };
const colourAt = (mesh, i) => { const c = new THREE.Color(); mesh.getColorAt(i, c); return [c.r, c.g, c.b]; };
view.build(m.readSim(%(doc)s));
const parts = view.parts();
const capture = { from: 2, to: 2, blend: 0, nearer: 2 };
const seen = (by, show = every) => {
  view.show(capture, { show, colour: by, tolerance: 20 });
  const net = parts.net.geometry.attributes.color;
  const tendons = parts.tendons.geometry.attributes;
  return { net: [0, 1, 2, 3].map((e) => arr(net, 6 * e, 3)),
           tendons: [arr(tendons.color, 0, 3), arr(tendons.color, 3, 3), arr(tendons.color, 6, 3)],
           reels: [colourAt(parts.reels, 0), colourAt(parts.reels, 1)],
           visible: [parts.tendons.visible, parts.reels.visible] };
};
out.across = seen("across");
out.along = seen("along");
out.both = seen("both");
out.offset = seen("deviation");
const colours = (part, from) => arr(part.geometry.attributes.color, from, 3);
out.offsetEdge1 = [colours(parts.net, 6), colours(parts.net, 9)];
out.offsetTendon0 = [colours(parts.tendons, 0), colours(parts.tendons, 3)];
out.wire = seen("wire");
out.hidden = seen("across", { ...every, tendons: false }).visible;
out.where = [arr(parts.tendons.geometry.attributes.position, 0, 12), parts.tendons.geometry.drawRange.count,
             at(parts.reels, 0), at(parts.reels, 1), parts.reels.count];
view.clear();
view.build(m.readSim(%(plain)s));
view.show(capture, { show: every, colour: "across", tolerance: 20 });
out.plain = [view.parts().tendons.visible, view.parts().reels.visible, view.parts().reels.count];
console.log(JSON.stringify(out));
"""

OTHER = linear([0x7d / 255, 0x82 / 255, 0x8a / 255])
WHITE = [1.0, 1.0, 1.0]


def _tendons():
    # the ropes' working load, 1,800 N, which each rope is judged against
    doc = with_tendons(document())
    doc["options"]["rope_working_newtons"] = 1800.0
    return doc


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("formwork_view_tendons") / "harness.mjs"
    script.write_text(HARNESS % {
        "three": (STATIC / "vendor" / "three.module.js").resolve().as_uri(),
        "model": (STATIC / "formwork_model.js").resolve().as_uri(),
        "view": (STATIC / "formwork_view.js").resolve().as_uri(),
        "doc": json.dumps(_tendons()), "plain": json.dumps(document())},
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_across_colours_each_across_rope_and_greys_the_rest(out):
    across = out["across"]
    # S1 q1: edge 1's rope at 3,000 N and edge 2's at 400 N against their
    # 1,800 N working load, the tendons' pull left out; edges 0 and 3 run
    # along, grey
    assert across["net"][1] == pytest.approx(judged(3000 / 1800), abs=1e-6)
    assert across["net"][2] == pytest.approx(judged(400 / 1800), abs=1e-6)
    assert across["net"][0] == pytest.approx(OTHER, abs=1e-6)
    assert across["net"][3] == pytest.approx(OTHER, abs=1e-6)
    # each tendon in the colour of the rope beside it, so it does not hide
    # it, and its reel too
    assert across["tendons"][0] == across["tendons"][1] == across["net"][1]
    assert across["tendons"][2] == pytest.approx(across["net"][2])
    assert across["reels"][0] == pytest.approx(across["net"][1])
    assert across["reels"][1] == pytest.approx(across["net"][2])
    assert across["visible"] == [True, True]


def test_along_colours_the_along_members_and_greys_the_tendons_with_their_family(out):
    # found on screen: white tendons over the grey across members were the
    # loudest thing in the Along view
    along = out["along"]
    assert along["net"][0] == pytest.approx(judged(200 / 1800), abs=1e-6)
    assert along["net"][1] == pytest.approx(OTHER, abs=1e-6)
    assert along["tendons"][0] == pytest.approx(OTHER, abs=1e-6)
    assert along["reels"][1] == pytest.approx(OTHER, abs=1e-6)


def test_under_offset_each_tendon_wears_its_members_colours_and_white_on_a_plain_net(out):
    # found on screen: white tendons hid the offsets of the members they run
    # along; under Wires the net is plain and the tendons stand out white
    # tendon 0 runs from node 2 out to node 1, along edge 1 (1 to 2): its head
    # end wears node 2's offset colour (12 mm), its free end node 1's (0 mm)
    node1, node2 = out["offsetEdge1"]
    head_end, free_end = out["offsetTendon0"]
    assert head_end == pytest.approx(node2, abs=1e-6) and free_end == pytest.approx(node1, abs=1e-6)
    assert node1 != pytest.approx(node2, abs=1e-3)
    wire = out["wire"]
    assert wire["tendons"][0] == pytest.approx(WHITE) and wire["reels"][0] == pytest.approx(WHITE)


def test_both_colours_every_rope_by_its_own_tension(out):
    both = out["both"]
    assert both["net"][0] == pytest.approx(judged(200 / 1800), abs=1e-6)
    assert both["net"][1] == pytest.approx(judged(3000 / 1800), abs=1e-6)
    assert both["tendons"][0] == both["net"][1]


def test_the_tendons_run_proud_of_the_net_with_a_reel_by_each_head(out):
    tendons, drawn, reel0, reel1, reels = out["where"]
    # tendon 0 from the head's node 2 (1, 1, 0.5) out to node 1 (1, 0, 0),
    # tendon 1 to node 3 (0, 1, 0), each 20 mm above the net
    assert tendons == pytest.approx([1, 1, 0.52, 1, 0, 0.02, 1, 1, 0.52, 0, 1, 0.02], abs=1e-6)
    assert drawn == 4
    assert reels == 2
    # each reel 60 mm out along its own tendon from the head
    assert math.dist(reel0, [1, 1, 0.52]) == pytest.approx(0.06, abs=1e-6)
    assert reel0[0] == pytest.approx(1.0) and reel0[1] < 1.0
    assert reel1[1] == pytest.approx(1.0) and reel1[0] < 1.0
    assert out["hidden"] == [False, False]


def test_a_run_without_tendons_draws_none(out):
    assert out["plain"] == [False, False, 0]
