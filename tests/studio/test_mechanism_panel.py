"""The one Cable net tab's mechanism pop-up (spec 2026-10-11 one Cable net
tab, section 8.1): one dropdown of whole spooling mechanisms, and under it one
spool's pull, the part that sets it, and the run's drum and carriage checks."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

LIST = [
    {"choices": {"motor": "ES-MH342200", "ratio": 7, "pulley": "Pfaff-DSRB-185-8",
                 "rope": "rope-8mm", "wires_per_motor": 1},
     "have_newtons": 6660.0, "limit": "rope tension", "part": "rope-8mm",
     "part_name": "8 mm 7x19",
     "label": "ES-MH342200, 7:1, 185 mm pulleys, 8 mm 7x19: 6,660 N"},
    {"choices": {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-6",
                 "rope": "rope-6mm", "wires_per_motor": 1},
     "have_newtons": 3229.4, "limit": "motor torque", "part": "23HS45-4204D-E1000",
     "label": "23HS45-4204D-E1000, 20:1, 90 mm pulleys, 6 mm 7x19: 3,229 N"},
]

HARNESS = """
import * as m from %(model)r;
const list = %(list)s;
const out = {};
out.picked = [m.pickIndex(list, "23HS45-4204D-E1000"), m.pickIndex(list, "gone"), m.pickIndex(list, null),
              m.pickIndex([], "x")];
out.options = m.optionsHtml(list, 1);
const pass = { drum: { value_mm: 900, limit_mm: 3616.4, fits: true, wire: 0 },
               carriage: { value_mm: 12, limit_mm: 300, fits: true, wire: 1 } };
const fail = { drum: { value_mm: 4000, limit_mm: 3616.4, fits: false, wire: 3 },
               carriage: { value_mm: 400, limit_mm: 300, fits: false, wire: 3 } };
out.html = { pass: m.mechanismHtml(list[1], pass), fail: m.mechanismHtml(list[1], fail),
             before: m.mechanismHtml(list[0], null), none: m.mechanismHtml(null, pass) };
const controller = await import(%(controller)r);
out.stub = Object.keys(controller.mountMechanism({ studyName: () => null, onChange: () => {} })).sort();
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("mechanism_panel") / "harness.mjs"
    script.write_text(HARNESS % {
        "model": (STATIC / "mechanism_pick_model.js").resolve().as_uri(),
        "controller": (STATIC / "mechanism_pick.js").resolve().as_uri(),
        "list": json.dumps(LIST)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_choice_is_the_motor_this_browser_left_else_the_strongest(out):
    assert out["picked"] == [1, 0, 0, -1]


def test_the_dropdown_lists_each_mechanism_by_its_label(out):
    options = out["options"]
    assert options == ('<option value="0">ES-MH342200, 7:1, 185 mm pulleys, 8 mm 7x19: '
                       '6,660 N</option><option value="1" selected>23HS45-4204D-E1000, '
                       '20:1, 90 mm pulleys, 6 mm 7x19: 3,229 N</option>')


def test_under_it_three_lines_have_limited_by_and_checks(out):
    html = out["html"]
    assert "<th>Have</th><td>3,229 N</td>" in html["pass"]
    # what gives way first, then the part by the name it is bought by; a
    # list from before the names were sent falls back on the part's key
    assert "<th>Limited by</th><td>motor, 23HS45-4204D-E1000</td>" in html["pass"]
    # nothing to say when every check passes (his ruling of 11 October 2026)
    assert "Checks" not in html["pass"] and "pass" not in html["pass"]
    # only what fails, a line each, in deep red rather than marked with a
    # cross (his ask of 11 October 2026)
    assert ('<th>Checks</th><td><span class="over">rope on drum 4,000 of 3,616 mm</span></td>'
            in html["fail"])
    assert '<td><span class="over">carriage 400 of 300 mm</span></td>' in html["fail"]
    assert "✗" not in html["fail"] and "✓" not in html["pass"]
    assert "all pass" not in html["fail"]
    # before a run there is nothing to check yet
    assert "Checks" not in html["before"] and "after a run" not in html["before"]
    assert "<th>Limited by</th><td>rope, 8 mm 7x19</td>" in html["before"]
    assert html["none"] == ""
    # three lines, no paragraph
    assert "<p" not in html["pass"] + html["fail"] + html["before"]


def test_the_controller_loads_where_there_is_no_page(out):
    assert out["stub"] == ["adopt", "chosen", "clear", "closePopup", "entry", "reload",
                           "setChecks", "setWires", "toggle"]


def test_the_pop_up_has_three_tabs_mechanism_cost_and_graphs():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    start = html.index('<div id="mechanism-popup"')
    popup = html[start:html.index("<!-- the end of the mechanism pop-up -->", start)]
    assert re.findall(r'data-mech-tab="([a-z-]+)"', popup) == ["mech-choose", "mech-cost",
                                                              "mech-graphs"]
    for pane in ("mech-choose", "mech-cost", "mech-graphs"):
        assert 'id="{}" class="mech-tab'.format(pane) in popup, pane
    assert '<button id="cost-export" type="button"' in popup and ">Export BOM</button>" in popup
    for ident in ("cost-body", "cost-export-status", "graphs-body", "cost-folder-choose",
                  "cost-folder-path"):
        assert 'id="{}"'.format(ident) in popup, ident


def test_the_page_carries_the_pop_up_with_one_dropdown():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    opening = '<div id="mechanism-popup" class="hidden">'
    assert opening in html
    popup = html[html.index(opening):]
    popup = popup[:popup.index("<!-- the end of the mechanism pop-up -->")]
    for ident in ("mechanism-popup-close", "mechanism-preset", "mechanism-have"):
        assert 'id="{}"'.format(ident) in popup, ident
    assert popup.count("<select") == 1
