"""What the one Cable net tab draws on the model, as values (spec 2026-10-11
one Cable net tab, sections 5.1 to 5.3): each Colour by on a full ramp over
the run with its limit on the key, the values put on the model, and the
weakest parts at a capture."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_cable_net_answer import _run

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
const out = {};
const sim = m.readSim(%(doc)s);
out.order = m.COLOUR_BY.map(([key]) => key);
out.ramp = [m.ramp(0), m.ramp(0.5), m.ramp(1)];
out.colours = { deviation: m.colourOf("deviation", 250, sim, 20), wire: m.colourOf("wire", 1500, sim, 20),
                trees: m.colourOf("utilisation", 0, sim, 20), off: m.colourOf("off", 3, sim, 20) };
const limits = { have: 1200, rope: 1800, tolerance: 20 };
out.keys = ["wire", "tension", "deviation", "utilisation", "off"].map((by) => m.colourKey(by, sim, limits));
out.pastScale = m.colourKey("wire", sim, { ...limits, have: 6000 });
out.noHave = m.colourKey("wire", sim, { ...limits, have: null });
out.labels = {
  deviation: m.colourLabels(sim, 2, "deviation", 2).map((l) => [l.kind, l.index, l.text]),
  wire: m.colourLabels(sim, 2, "wire", 1).map((l) => [l.kind, l.index, l.text]),
  tension: m.colourLabels(sim, 2, "tension", 1).map((l) => [l.kind, l.index, l.text]),
  trees: m.colourLabels(sim, 2, "utilisation", 5).map((l) => [l.kind, l.index, l.text]),
  off: m.colourLabels(sim, 1, "off", 5).map((l) => [l.kind, l.index, l.text]),
};
out.shown = [m.labelsShown("wire", { wires: true }), m.labelsShown("wire", { net: true }),
             m.labelsShown("deviation", { net: true }), m.labelsShown("utilisation", { trees: true }),
             m.labelsShown("off", { heads: true }), m.labelsShown("off", { net: true })];
out.weakest = m.weakestAt(sim, 2, limits);
out.closest = m.weakestAt(sim, 1, { have: 5000, rope: 9000, tolerance: 100 });
out.noLimits = m.weakestAt(sim, 1, { have: null, rope: null, tolerance: 100 });
const flat = (list) => list.map((l) => [l.kind, l.index, l.text]);
out.model = {
  weakest: flat(m.modelLabels(sim, 2, { weakest: out.weakest })),
  closest: flat(m.modelLabels(sim, 1, { weakest: out.closest })),
  compare: flat(m.modelLabels(sim, 2, { by: "wire", compare: true })),
  both: flat(m.modelLabels(sim, 2, { by: "deviation", compare: true })),
  none: m.modelLabels(sim, 2, {}),
  wire: flat(m.colourLabels(sim, 2, "wire")),
  deviation: flat(m.colourLabels(sim, 2, "deviation")),
};
console.log(JSON.stringify(out));
"""


def _srgb(hex_colour):
    n = int(hex_colour[1:], 16)
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("cable_net_colours") / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "formwork_model.js").resolve().as_uri(),
                                 "doc": json.dumps(_run())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_colour_by_is_wires_along_across_both_offset_trees_or_off(out):
    # Ropes became Along, Across and Both (spec 2026-10-11 across tendons,
    # section 6)
    assert out["order"] == ["wire", "along", "across", "both", "deviation", "utilisation", "off"]


def test_the_ramp_starts_from_a_colour_that_shows_and_ends_red(out):
    low, middle, high = out["ramp"]
    assert low == pytest.approx(_srgb("#3a6fc4"))           # a cool blue, not the paper white
    assert high == pytest.approx(_srgb("#cc2211"))
    assert middle == pytest.approx(_srgb("#e8c547"), abs=0.02) or middle != low
    colours = out["colours"]
    # every kind on the ramp over the run: half the run's largest offset (500 mm)
    assert colours["deviation"] == pytest.approx(out["ramp"][1], abs=1e-6)
    assert colours["wire"] == pytest.approx(high)            # the run's largest wire
    assert colours["trees"] == pytest.approx(low)
    assert colours["off"] is None


def test_each_key_is_a_real_scale_with_its_limit_at_its_true_place(out):
    wire, ropes, offset, trees, off = out["keys"]
    assert wire == {"title": "wire tension, N", "min": "0", "max": "1,500 N",
                    "limitText": "one spool 1,200 N", "fraction": pytest.approx(0.8)}
    assert ropes["title"] == "rope tension, kN" and ropes["max"] == "3.0 kN"
    assert ropes["limitText"] == "working load 1.8 kN" and ropes["fraction"] == pytest.approx(0.6)
    assert offset["max"] == "500 mm" and offset["limitText"] == "tolerance 20 mm"
    assert offset["fraction"] == pytest.approx(20 / 500)
    assert trees["max"] == "1.20" and trees["limitText"] == "capacity 1.0"
    assert trees["fraction"] == pytest.approx(1 / 1.2)
    assert off is None
    # a limit past the run's largest is named, with no place on the bar
    assert out["pastScale"]["fraction"] is None and out["pastScale"]["limitText"] == "one spool 6,000 N"
    assert out["noHave"]["limitText"] is None and out["noHave"]["fraction"] is None


def test_the_values_on_the_model_are_the_worst_and_the_worst_of_each_side(out):
    labels = out["labels"]
    # capture S1 q1, offsets 5, 0, 12, 40 mm; sides 0, 0, 1, 1: the worst two,
    # then side 0's worst, which is not yet among them
    assert labels["deviation"] == [["node", 3, "40 mm"], ["node", 2, "12 mm"], ["node", 0, "5.0 mm"]]
    # wires: w0 1500 N on side 0, w1 1000 N on side 0: the worst alone
    assert labels["wire"] == [["wire", 0, "1,500 N"]]
    # ropes: member 1 (1 to 2, side 0) at 3.0 kN, then side 1's worst, member 2 (2 to 3)
    assert labels["tension"] == [["member", 1, "3.0 kN"], ["member", 2, "0.4 kN"]]
    assert labels["trees"] == [["tree", 0, "0.50"]]
    # with Colour by off, each head's push
    assert labels["off"] == [["node", 2, "800 N"]]
    assert out["shown"] == [True, False, True, True, True, False]


def test_the_weakest_are_every_part_over_its_limit(out):
    weakest = out["weakest"]
    # at S1 q1: node 3 at 40 of 20 mm, member 1 at 3000 of 1800 N, wire w0 at
    # 1500 of 1200 N; the tree at 0.5 is within
    assert [(w["kind"], w["index"], w["over"]) for w in weakest] == [
        ("node", 3, True), ("member", 1, True), ("wire", 0, True)]
    assert weakest[0]["ratio"] == pytest.approx(2.0) and weakest[0]["text"] == "40 mm"
    assert weakest[1]["text"] == "3.0 kN" and weakest[2]["text"] == "1,500 N"


def test_with_none_over_the_weakest_are_the_five_closest(out):
    closest = out["closest"]
    assert [(w["kind"], w["index"]) for w in closest] == [
        ("tree", 0), ("node", 3), ("member", 1), ("wire", 0), ("wire", 1)]
    assert not any(w["over"] for w in closest)
    assert closest[0]["ratio"] == pytest.approx(0.4)
    # a kind with no limit is never judged
    assert {w["kind"] for w in out["noLimits"]} <= {"tree", "node"}


def test_the_weakest_wear_their_values_and_compare_its_offsets(out):
    # spec 2026-10-11 sections 5.3 and 5.4 (found by the final review: rings
    # with no numbers, and Compare labelling nothing unless Colour by was
    # Offset): each part over its limit labelled with its value, and with none
    # over the closest with what they have to spare; Compare the largest
    # offsets in mm, whatever the Colour by; one label a part
    model = out["model"]
    assert model["weakest"] == [[w["kind"], w["index"], w["text"]] for w in out["weakest"]]
    assert len(model["closest"]) == len(out["closest"]) == 5
    assert all(label[2].endswith(" spare") for label in model["closest"])
    assert model["compare"] == model["wire"] + model["deviation"]
    assert model["both"] == model["deviation"]
    assert model["none"] == []
