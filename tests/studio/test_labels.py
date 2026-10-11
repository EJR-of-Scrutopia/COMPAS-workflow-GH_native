"""What the one Cable net tab's labels share (spec 2026-10-11 one Cable net
tab, section 9: the old Cable net goes, and the three helpers its model lent
the tab move to labels.js), and that nothing of the old tab is left in the
browser."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
console.log(JSON.stringify({
  escaped: m.escapeHtml(`<b class="x">'&'</b>`),
  forces: [12.34, 123.4, 1234, -2500, null, NaN].map(m.forceLabel),
  spread: m.spreadLabels([[0, 0], [10, 5], [100, 0], null, [100, 30]], 44, 16),
}));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("labels") / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "labels.js").resolve().as_uri()},
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_text_is_escaped_for_the_page(out):
    assert out["escaped"] == "&lt;b class=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/b&gt;"


def test_a_force_is_short_with_its_unit(out):
    assert out["forces"] == ["12.3 N", "123 N", "1.2 kN", "-2.5 kN", "", ""]


def test_where_labels_crowd_the_first_is_kept(out):
    # the second falls within 44 px across and 16 down of the first
    assert out["spread"] == [True, False, True, False, True]


def test_nothing_of_the_old_cable_net_is_left_in_the_browser():
    for gone in ("cablenet.js", "cablenet_model.js"):
        assert not (STATIC / gone).exists(), gone
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for gone in ("mountCableNet", "cableNet.", "CABLENET_LAYERS", "paintCableNetLenses",
                 "cableNetLensUp", "state.cablenet", "ghostPiece", "modelLabels",
                 "cablenet_model.js", "cablenet.js"):
        assert gone not in js, gone
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for gone in ('id="cablenet-section"', 'id="cablenet-popup"', 'id="model-labels"',
                 'id="cablenet-pick"', 'id="cablenet-lenses"'):
        assert gone not in html, gone
    for module in ("formwork.js", "formwork_model.js"):
        source = (STATIC / module).read_text(encoding="utf-8")
        assert 'from "./labels.js"' in source and "cablenet_model.js" not in source, module
