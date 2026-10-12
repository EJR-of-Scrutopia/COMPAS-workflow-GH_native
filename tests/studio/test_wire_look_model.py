"""The wires drawn as the rope chosen, as values (Param, 2026-10-12): the
rope's own radius and colour at 1x, a viewing multiplier from 1 to 10, the
nodes drawn as a clamp 2.5 times the rope's diameter across, and the rope a
study wears (its own pick, else the default)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

GALVANISED = {"key": "rope-8mm", "label": "8 mm 7x19 galvanised", "diameter_mm": 8.0,
              "render": {"colour": "#8e9399", "metalness": 0.6, "roughness": 0.55}}
STAINLESS = {"key": "rope-2mm-7x19-ss", "label": "2 mm 7x19 stainless 316", "diameter_mm": 2.0,
             "render": {"colour": "#cdd2d7", "metalness": 0.9, "roughness": 0.25}}

HARNESS = """
import * as m from %(module)r;
const out = {};
const galvanised = %(galvanised)s;
const stainless = %(stainless)s;
out.eight = m.wireLook(galvanised, 1);
out.eightTripled = m.wireLook(galvanised, 3);
out.two = m.wireLook(stainless);
out.clamped = [0, 0.5, 10, 50, "x", null].map((s) => m.wireLook(galvanised, s).wireRadius);
out.none = m.wireLook(null);
out.noSize = m.wireLook({ key: "odd", diameter_mm: 0, render: galvanised.render });
const ropes = [stainless, galvanised];
out.pick = [
  m.ropeFor(ropes, "rope-2mm-7x19-ss", "rope-8mm"),
  m.ropeFor(ropes, "gone", "rope-8mm"),
  m.ropeFor(ropes, null, "gone"),
  m.ropeFor([], "rope-8mm", "rope-8mm"),
];
out.options = m.ropeOptionsHtml([...ropes, { key: "a&b", label: "<odd>", diameter_mm: 1 }], "rope-8mm");
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("wire_look") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "wire_look_model.js").as_uri(),
        "galvanised": json.dumps(GALVANISED), "stainless": json.dumps(STAINLESS),
    }, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_wire_is_drawn_at_the_ropes_own_radius_and_colour(out):
    eight = out["eight"]
    assert eight["wireRadius"] == pytest.approx(0.004)
    assert eight["colour"] == "#8e9399"
    assert eight["metalness"] == 0.6 and eight["roughness"] == 0.55
    two = out["two"]
    assert two["wireRadius"] == pytest.approx(0.001)
    assert two["colour"] == "#cdd2d7"


def test_the_nodes_follow_the_rope_as_a_clamp_two_and_a_half_diameters_across(out):
    assert out["eight"]["nodeRadius"] == pytest.approx(0.010)
    assert out["two"]["nodeRadius"] == pytest.approx(0.0025)


def test_the_wire_size_thickens_both_for_viewing_and_one_is_the_real_rope(out):
    assert out["eightTripled"]["wireRadius"] == pytest.approx(0.012)
    assert out["eightTripled"]["nodeRadius"] == pytest.approx(0.030)
    # held to 1x to 10x; anything unreadable is the real rope
    assert out["clamped"] == pytest.approx([0.004, 0.004, 0.040, 0.040, 0.004, 0.004])


def test_with_no_rope_the_drawing_keeps_its_old_sizes(out):
    for look in (out["none"], out["noSize"]):
        assert look["wireRadius"] == pytest.approx(0.02)
        assert look["nodeRadius"] == pytest.approx(0.03)
        assert look["colour"] is None


def test_a_study_wears_its_own_pick_else_the_default_else_the_first(out):
    assert out["pick"] == ["rope-2mm-7x19-ss", "rope-8mm", "rope-2mm-7x19-ss", None]


def test_the_wire_select_lists_the_ropes_by_name_with_the_choice_selected(out):
    html = out["options"]
    assert '<option value="rope-8mm" selected>8 mm 7x19 galvanised</option>' in html
    assert '<option value="rope-2mm-7x19-ss">2 mm 7x19 stainless 316</option>' in html
    assert "&lt;odd&gt;" in html and 'value="a&amp;b"' in html


URL_HARNESS = """
import { mechanismsUrl } from %(module)r;
console.log(JSON.stringify([
  mechanismsUrl("2 sided prototype", 1, "rope-2mm-7x7"),
  mechanismsUrl("Tiny", 3, null),
  mechanismsUrl("a&b", 2, "rope-8mm"),
]));
"""


def test_the_mechanisms_are_asked_for_the_rope_the_study_wears(tmp_path):
    """Changing the wire changes the mechanisms the run can be made with, so
    the run is made with the rope on screen."""

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path / "url.mjs"
    script.write_text(URL_HARNESS % {"module": (STATIC / "mechanism_pick_model.js").as_uri()},
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        "/api/studies/2%20sided%20prototype/mechanisms?wires_per_motor=1&rope=rope-2mm-7x7",
        "/api/studies/Tiny/mechanisms?wires_per_motor=3",
        "/api/studies/a%26b/mechanisms?wires_per_motor=2&rope=rope-8mm",
    ]
