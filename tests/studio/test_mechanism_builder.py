"""The mechanism built by hand (Param, 2026-10-12): "this mechanisms tab i also
want to be able to create my own mechanism, choose whether there is pulley or
not should just be a toggle on this pop up too", then "we should at the end of
that also have it show the newtons max the mechanisms can produce". His
answers: Motor, Ratio, Pulleys on or off and Pulley replace the list, starting
at the strongest for the wire chosen; the toggle is the run's reeving too."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def _option(motor, ratio, pulley, have, drive, limit="rope tension"):
    return {"choices": {"motor": motor, "ratio": ratio, "pulley": pulley, "rope": "rope-6mm",
                        "wires_per_motor": 1},
            "have_newtons": have, "drive_newtons": drive, "limit": limit, "part": "rope-6mm",
            "part_name": "6 mm 7x19",
            "ratio_label": "direct" if ratio is None else "{:g}:1".format(ratio),
            "pulley_label": None if pulley is None else {"P1": "GPS 100 mm", "P2": "Pfaff 90 mm"}[pulley],
            "label": "x"}


OPTIONS = [
    _option("A", None, None, 900.0, 900.0, "motor torque"),
    _option("A", None, "P1", 2000.0, 2000.0, "motor torque"),
    _option("A", 5.0, None, 3000.0, 3500.0),
    _option("A", 5.0, "P1", 3760.0, 4100.0),
    _option("A", 5.0, "P2", 3760.0, 4300.0),
    _option("B", 10.0, None, 3100.0, 3200.0, "motor torque"),
]

HARNESS = """
import * as m from %(model)r;
const options = %(options)s;
const out = {};
const at = (i) => i < 0 ? null : options[i].choices;
out.fresh = at(m.builderPick(options, null));
out.exact = at(m.builderPick(options, { motor: "A", ratio: 5, pulley: "P1" }));
out.off = at(m.builderPick(options, { motor: "A", ratio: 5, pulley: null }));
out.direct = at(m.builderPick(options, { motor: "A", ratio: null, pulley: "P1" }));
out.otherMotor = at(m.builderPick(options, { motor: "B", ratio: 5, pulley: "P1" }));
out.gonePulley = at(m.builderPick(options, { motor: "A", ratio: 5, pulley: "gone" }));
out.legacy = at(m.builderPick(options, "B"));
out.empty = m.builderPick([], null);
out.motors = m.motorOptionsHtml(options, "B");
out.ratios = m.ratioOptionsHtml(options, "A", 5);
out.pulleys = m.pulleyOptionsHtml(options, "A", 5, "P2");
out.hasPulleys = [m.hasPulleys(options, "A", 5), m.hasPulleys(options, "B", 10)];
out.ratioKey = [m.ratioKey(null), m.ratioKey(5), m.ratioFromKey("direct"), m.ratioFromKey("5")];
out.html = m.mechanismHtml(options[3], null);
const controller = await import(%(controller)r);
out.stub = Object.keys(controller.mountMechanism({ studyName: () => null, onChange: () => {} })).sort();
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("mechanism_builder") / "harness.mjs"
    script.write_text(HARNESS % {
        "model": (STATIC / "mechanism_pick_model.js").resolve().as_uri(),
        "controller": (STATIC / "mechanism_pick.js").resolve().as_uri(),
        "options": json.dumps(OPTIONS)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _choices(motor, ratio, pulley):
    return {"motor": motor, "ratio": ratio, "pulley": pulley, "rope": "rope-6mm", "wires_per_motor": 1}


def test_a_study_starts_at_the_strongest_and_the_strongest_drive_among_equals(out):
    # A 5:1 on P1 and on P2 both pull 3,760 N; P2's drive is the stronger
    assert out["fresh"] == _choices("A", 5.0, "P2")
    assert out["empty"] == -1


def test_his_own_mechanism_is_kept_as_he_built_it(out):
    assert out["exact"] == _choices("A", 5.0, "P1")
    # Pulleys off: straight off the drum
    assert out["off"] == _choices("A", 5.0, None)
    assert out["direct"] == _choices("A", None, "P1")


def test_a_choice_the_motor_cannot_make_falls_to_its_strongest(out):
    # B has no 5:1 and no pulley: its one mechanism
    assert out["otherMotor"] == _choices("B", 10.0, None)
    # a pulley no longer offered, with Pulleys on: the strongest pulley there
    assert out["gonePulley"] == _choices("A", 5.0, "P2")
    # a study remembered by its motor alone, before he could build his own
    assert out["legacy"] == _choices("B", 10.0, None)


def test_the_dropdowns_offer_what_the_motor_and_ratio_can_take(out):
    assert out["motors"] == '<option value="A">A</option><option value="B" selected>B</option>'
    assert out["ratios"] == ('<option value="direct">direct</option>'
                             '<option value="5" selected>5:1</option>')
    assert out["pulleys"] == ('<option value="P1">GPS 100 mm</option>'
                              '<option value="P2" selected>Pfaff 90 mm</option>')
    assert out["hasPulleys"] == [True, False]
    assert out["ratioKey"] == ["direct", "5", None, 5]


def test_the_readout_ends_with_the_most_the_drive_pulls(out):
    rows = re.findall(r"<tr><th>([^<]*)</th><td>([^<]*)</td></tr>", out["html"])
    assert rows[0] == ("Have", "3,760 N")
    assert rows[-1] == ("Max", "4,100 N")


def test_the_controller_keeps_its_face(out):
    assert out["stub"] == ["adopt", "chosen", "clear", "closePopup", "entry", "reload",
                           "setChecks", "setWires", "toggle"]


def test_the_pop_up_carries_motor_ratio_pulleys_and_pulley_and_no_list():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    start = html.index('<div id="mech-choose" class="mech-tab">')
    pane = html[start:html.index('<div id="mech-cost"', start)]
    assert 'id="mechanism-preset"' not in html
    for select in ("mechanism-motor", "mechanism-ratio", "mechanism-pulley"):
        assert '<select id="{}"></select>'.format(select) in pane, select
    assert '<input id="mechanism-pulleys" type="checkbox">' in pane
    assert pane.index("mechanism-motor") < pane.index("mechanism-ratio") \
        < pane.index("mechanism-pulleys") < pane.index('id="mechanism-pulley"') \
        < pane.index("mechanism-have")
    js = (STATIC / "mechanism_pick.js").read_text(encoding="utf-8")
    assert "builderPick(state.list, wanted)" in js
    assert ".options || []" in js
