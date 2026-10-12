"""The across tendons drawn (spec 2026-10-11 across tendons, section 6): the
net coloured by Along, Across and Both with the other family grey, each rope
judged against its working load (his answer of 11 October 2026). The tendons
ARE the across wires (Param, 2026-10-12: "the tendons should just be the wires
that are already there in that direction not overlayed lines"), so no line is
drawn over the net: the Tendons chip shows the reel at each column head, on
the net, in the colour of the wire it pulls and white otherwise."""

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
  return { net: [0, 1, 2, 3].map((e) => arr(net, 6 * e, 3)),
           reels: [colourAt(parts.reels, 0), colourAt(parts.reels, 1)],
           visible: parts.reels.visible };
};
out.noOverlay = [parts.tendons === undefined, view.group.children.length];
out.across = seen("across");
out.along = seen("along");
out.both = seen("both");
out.offset = seen("deviation");
out.wire = seen("wire");
out.hidden = seen("across", { ...every, tendons: false }).visible;
out.where = [at(parts.reels, 0), at(parts.reels, 1), parts.reels.count];
view.clear();
view.build(m.readSim(%(plain)s));
view.show(capture, { show: every, colour: "across", tolerance: 20 });
out.plain = [view.parts().reels.visible, view.parts().reels.count];
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
    # each reel in the colour of the wire it pulls
    assert across["reels"][0] == pytest.approx(across["net"][1])
    assert across["reels"][1] == pytest.approx(across["net"][2])
    assert across["visible"] is True


def test_no_line_is_drawn_over_the_net_for_a_tendon(out):
    # his correction of 12 October 2026: the double lines were the tendons
    # drawn 20 mm proud of the wires they are
    no_part, children = out["noOverlay"]
    assert no_part
    assert children == 12


def test_along_colours_the_along_members_and_greys_the_tendons_with_their_family(out):
    # found on screen: white tendons over the grey across members were the
    # loudest thing in the Along view
    along = out["along"]
    assert along["net"][0] == pytest.approx(judged(200 / 1800), abs=1e-6)
    assert along["net"][1] == pytest.approx(OTHER, abs=1e-6)
    assert along["reels"][1] == pytest.approx(OTHER, abs=1e-6)


def test_on_a_plain_net_the_reels_are_white(out):
    wire = out["wire"]
    assert wire["reels"][0] == pytest.approx(WHITE)


def test_both_colours_every_rope_by_its_own_tension(out):
    both = out["both"]
    assert both["net"][0] == pytest.approx(judged(200 / 1800), abs=1e-6)
    assert both["net"][1] == pytest.approx(judged(3000 / 1800), abs=1e-6)
    assert both["reels"][0] == pytest.approx(both["net"][1])


def test_a_reel_sits_on_the_net_by_each_head_out_along_its_wire(out):
    reel0, reel1, reels = out["where"]
    assert reels == 2
    # tendon 0 runs from the head's node 2 (1, 1, 0.5) out to node 1 (1, 0, 0),
    # tendon 1 to node 3 (0, 1, 0): each reel 60 mm out along its own wire
    assert math.dist(reel0, [1, 1, 0.5]) == pytest.approx(0.06, abs=1e-6)
    assert reel0[0] == pytest.approx(1.0) and reel0[1] < 1.0
    assert reel1[1] == pytest.approx(1.0) and reel1[0] < 1.0
    assert out["hidden"] is False


def test_a_run_without_tendons_draws_none(out):
    assert out["plain"] == [False, 0]
