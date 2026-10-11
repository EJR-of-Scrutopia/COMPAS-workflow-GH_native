"""The one Cable net tab's answer, from the physics run alone (spec 2026-10-11
one Cable net tab, sections 4.3, 4.4 and 7): the force needed, one spool's
pull, what is missing or to spare, the form against the tolerance, the lines
that say the run is out of date, and the trees judged again for a new wall."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document, pack, with_holds

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"
CHOSEN = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
          "rope": "rope-4mm", "wires_per_motor": 1}


def _run(have=1200.0):
    doc = document()
    doc["options"].update({"mechanism": dict(CHOSEN), "have_newtons": have,
                           "have_limit": "motor torque", "have_part": "23HS45-4204D-E1000",
                           "described": "23HS45-4204D-E1000 on EG23 20:1, Pfaff DSRB 90/4 "
                                        "pulleys, 4 mm 7x19, one wire a motor",
                           "rope_working_newtons": 1800.0})
    doc["net"]["sides"] = [0, 0, 1, 1]
    doc["checks"] = {"drum": {"value_mm": 900.0, "limit_mm": 3616.0, "fits": True, "wire": 0},
                     "carriage": {"value_mm": 12.0, "limit_mm": 300.0, "fits": True, "wire": 1}}
    return doc


HARNESS = """
import * as m from %(module)r;
const out = {};
const sim = m.readSim(%(doc)s);
const spare = m.readSim(%(spare)s);
const plain = m.readSim(%(plain)s);
const held = m.readSim(%(held)s);
out.read = { sides: sim.sides, checks: sim.checks, axial: Array.from(sim.captures[2].treeAxial) };
out.answer = m.answer(sim, 20);
out.html = m.answerHtml(out.answer);
out.staleHtml = m.answerHtml(out.answer, { stale: true });
out.spare = m.answerHtml(m.answer(spare, 30));
out.plain = [m.answer(plain, 20), m.answerHtml(m.answer(plain, 20))];
out.none = [m.answer(null, 20), m.answerHtml(null)];
out.held = [m.answer(held, 20).holds, m.answerHtml(m.answer(held, 20)), out.answer.holds];
const treesOver = m.readSim(%(treesOver)s);
const judged = m.withWall(sim, 3.2);
out.trees = { over: m.answer(treesOver, 20).trees, overHtml: m.answerHtml(m.answer(treesOver, 20)),
              within: m.answer(judged, 20).trees, withinHtml: m.answerHtml(m.answer(judged, 20)) };
const chosen = %(chosen)s;
out.warnings = {
  none: m.formworkWarnings(null, { mechanism: chosen }),
  same: m.formworkWarnings(sim, { mechanism: chosen }),
  changed: m.formworkWarnings(sim, { mechanism: { ...chosen, ratio: 50 } }),
  wires: m.formworkWarnings(sim, { mechanism: { ...chosen, wires_per_motor: 2 } }),
  noChoice: m.formworkWarnings(sim, { mechanism: null }),
  plainRun: m.formworkWarnings(plain, { mechanism: chosen }),
  older: m.formworkWarnings(m.readSim(%(older)s), { mechanism: chosen }),
  rodsSame: m.formworkWarnings(sim, { mechanism: chosen, holdsPerSide: 0 }),
  rods: m.formworkWarnings(sim, { mechanism: chosen, holdsPerSide: 3 }),
  rodsAndMechanism: m.formworkWarnings(sim, { mechanism: { ...chosen, ratio: 50 }, holdsPerSide: 3 }),
};
const thicker = m.withWall(sim, 4.0);
out.wall = { utilisation: thicker.captures.map((c) => Array.from(c.treeUtilisation)),
             scale: thicker.scales.utilisation, wall: thicker.trees.wall,
             untouched: Array.from(sim.captures[2].treeUtilisation) };
console.log(JSON.stringify(out));
"""


def _resistance(diameter, wall, length, compression):
    # trees.resistance, EN 1993-1-1 6.3.1 curve a, S355
    inner = diameter - 2.0 * wall
    area = math.pi / 4.0 * (diameter ** 2 - inner ** 2)
    inertia = math.pi / 64.0 * (diameter ** 4 - inner ** 4)
    plastic = area * 355.0
    if not compression:
        return plastic
    critical = math.pi ** 2 * 210000.0 * inertia / length ** 2
    slenderness = math.sqrt(plastic / critical)
    phi = 0.5 * (1.0 + 0.21 * (slenderness - 0.2) + slenderness ** 2)
    return min(1.0, 1.0 / (phi + math.sqrt(phi ** 2 - slenderness ** 2))) * plastic


def _trees_over():
    # the tree member at the last capture pushed 250,000 N, over its 60.3 x
    # 3.2 tube's resistance at its 500 mm, and judged so by the engine
    doc = _run()
    load = 250000.0
    doc["captures"][3]["tree_axial"] = pack([-load])
    doc["captures"][3]["tree_utilisation"] = pack([load / _resistance(60.3, 3.2, 500.0, True)])
    return doc


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    plain = document()
    script = tmp_path_factory.mktemp("cable_net_answer") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "formwork_model.js").resolve().as_uri(),
        "doc": json.dumps(_run()), "spare": json.dumps(_run(2000.0)),
        "plain": json.dumps(plain), "older": json.dumps(document(older=True)),
        "held": json.dumps(with_holds(_run())),
        "treesOver": json.dumps(_trees_over()),
        "chosen": json.dumps(CHOSEN)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_run_carries_each_nodes_side_its_checks_and_its_trees_forces(out):
    read = out["read"]
    assert read["sides"] == [0, 0, 1, 1]
    assert read["checks"]["carriage"]["value_mm"] == 12.0
    assert read["axial"] == [-900.0]


def test_the_answer_is_the_force_needed_one_spools_pull_and_the_gap(out):
    a = out["answer"]
    # the largest wire tension anywhere in the run: wire w0, 1500 N, at S1 q1
    assert a["needed"] == {"newtons": 1500.0, "wire": 0, "name": "w0", "capture": 2,
                          "label": "S1 q1"}
    assert a["have"]["newtons"] == 1200.0 and a["have"]["part"] == "23HS45-4204D-E1000"
    assert a["gap"] == {"newtons": 300.0, "missing": True}
    # the form: the worst offset and the mean at the end of the tiling against
    # the tolerance (his ask of 11 October 2026: the mean and the worst both)
    assert a["form"] == {"mm": 25.0, "tolerance": 20.0, "within": False}
    assert a["mean"] == {"mm": 10.25, "within": True}
    html = out["html"]
    assert ('<tr data-capture="2" data-wire="0"><th>Needed</th><td>1,500 N</td>'
            "<td>worst wire w0, at S1 q1</td></tr>") in html
    assert "<th>Have</th><td>1,200 N</td><td>one spool, 23HS45-4204D-E1000 20:1</td>" in html
    # what falls short is in deep red, not marked with a cross (his ask of 11
    # October 2026)
    assert '<th>Missing</th><td><span class="over">300 N</span></td>' in html
    assert ('<th>Worst offset</th><td><span class="over">25 mm</span></td>'
            "<td>at the end, tolerance 20 mm</td>") in html
    assert "<th>Mean offset</th><td>10 mm</td><td>at the end</td>" in html
    assert 'class="answer stale"' in out["staleHtml"] and 'class="answer stale"' not in html
    # a spool that pulls more than the run needs: spare, and the form within 30 mm
    assert "<th>Spare</th><td>500 N</td>" in out["spare"]
    assert "<th>Worst offset</th><td>25 mm</td><td>at the end, tolerance 30 mm</td>" in out["spare"]
    for marked in (html, out["spare"]):
        assert "✗" not in marked and "✓" not in marked and "<th>Form</th>" not in marked


def test_the_answer_gives_the_trees_load_and_what_its_tube_takes(out):
    # his ask of 11 October 2026: the trees as a load, not a bare ratio. The
    # member and capture the run judges worst, its force and its tube's
    # resistance, in deep red past it
    resistance = _resistance(60.3, 3.2, 500.0, True)
    over = out["trees"]["over"]
    assert over["capture"] == 3 and over["member"] == 0 and over["label"] == "S1 q2"
    assert over["newtons"] == 250000.0
    assert over["capacity"] == pytest.approx(resistance, rel=1e-6)
    assert over["utilisation"] == pytest.approx(250000.0 / resistance, rel=1e-5)
    tube = "{:,} N".format(round(resistance))
    assert ('<th>Trees load</th><td><span class="over">250,000 N</span></td>'
            "<td>worst member, its tube takes " + tube + "</td>") in out["trees"]["overHtml"]
    within = out["trees"]["within"]
    assert within["capture"] == 2 and within["newtons"] == 900.0
    assert ("<th>Trees load</th><td>900 N</td><td>worst member, its tube takes " + tube + "</td>"
            in out["trees"]["withinHtml"])


def test_a_run_with_no_mechanism_says_none_for_what_one_spool_pulls(out):
    answer, html = out["plain"]
    assert answer["have"] is None and answer["gap"] is None
    assert "<th>Have</th><td>none</td>" in html and "Missing" not in html and "Spare" not in html
    assert out["none"] == [None, ""]


def test_the_run_is_out_of_date_when_the_mechanism_changes(out):
    w = out["warnings"]
    assert w["none"] == ["No run yet: Run"]
    assert w["same"] == [] and w["noChoice"] == []
    assert w["changed"] == ["Run again: mechanism changed"]
    assert w["wires"] == ["Run again: mechanism changed"]
    # a run cut for a named prestress, or an older one, is not the mechanism's
    assert w["plainRun"] == ["Run again: mechanism changed"]
    assert w["older"][0] == "Run again: older run"


def test_the_answer_says_the_rods_a_side_and_how_many_went_on(out):
    # spec 2026-10-11 one Cable net tab, section 4.3: Holds, 3 a side, 15 rods
    holds, html, plain = out["held"]
    assert holds == {"perSide": 1, "rods": 1}
    assert "<th>Holds</th><td>1 a side, 1 rod</td>" in html
    assert plain == {"perSide": 0, "rods": 0}
    assert "<th>Holds</th><td>none</td>" in out["html"]


def test_the_run_is_out_of_date_when_the_rods_a_side_change(out):
    # spec section 7: rods a side changed, a run from the hold
    w = out["warnings"]
    assert w["rodsSame"] == []
    assert w["rods"] == ["Run again: rods a side changed"]
    assert w["rodsAndMechanism"] == ["Run again: mechanism changed",
                                     "Run again: rods a side changed"]


def test_a_new_wall_judges_the_trees_again_from_the_runs_own_forces(out):
    wall = out["wall"]
    assert wall["wall"] == 4.0
    # the member is 500 mm long once lifted and pushed 800, 900 and 0 N:
    # its buckling resistance in a 60.3 x 4.0 tube, S355, curve a
    resistance = _resistance(60.3, 4.0, 500.0, True)
    assert wall["utilisation"][0] == [0.0]                   # folded: the tree not yet lifted
    assert wall["utilisation"][1][0] == pytest.approx(800.0 / resistance, rel=1e-5)
    assert wall["utilisation"][2][0] == pytest.approx(900.0 / resistance, rel=1e-5)
    assert wall["utilisation"][3][0] == pytest.approx(0.0)
    assert wall["scale"] == pytest.approx(900.0 / resistance, rel=1e-5)
    # the run as read is left as it was
    assert wall["untouched"] == pytest.approx([0.5])
