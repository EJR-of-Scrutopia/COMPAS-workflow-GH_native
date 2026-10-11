"""The pop-up's Cost and Graphs (spec 2026-10-11 one Cable net tab, sections
8.2 and 8.3): one spooling mechanism priced, the spools, the cabinets and the
total, VAT excluded; and two graphs over the run's captures, the worst wire
against one spool's pull and the worst offset against the tolerance."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_formwork_model import document

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

COST = {"described": "34HS31-6004D-E1000 on EG34 50:1, Pfaff DSRB 185/8 pulleys, 8 mm 7x19",
        "spools": 105, "spool_gbp": 412.304, "cabinets": 15, "cabinets_gbp": 5250.0,
        "total_gbp": 48541.92, "unpriced": 2, "unpriced_parts": ["drum-72", "pico"]}

HARNESS = """
import * as m from %(module)r;
import { readSim } from %(formwork)r;
const out = {};
out.cost = m.costHtml(%(cost)s);
out.priced = m.costHtml({ ...%(cost)s, unpriced: 0, unpriced_parts: [] });
out.none = m.costHtml(null);
const sim = readSim(%(doc)s);
out.series = m.graphSeries(sim);
out.graph = m.graphSvg([1, 3, 2], 2.5, { title: "worst wire, N", limitText: "one spool 2.5 N" });
out.flat = m.graphSvg([0, 0], 0, { title: "t", limitText: "" });
out.graphs = m.graphsHtml(sim, 1200, 20);
out.noHave = m.graphsHtml(sim, null, 20);
out.noRun = m.graphsHtml(null, 1200, 20);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path_factory.mktemp("run_popup") / "harness.mjs"
    script.write_text(HARNESS % {
        "module": (STATIC / "run_popup_model.js").resolve().as_uri(),
        "formwork": (STATIC / "formwork_model.js").resolve().as_uri(),
        "cost": json.dumps(COST), "doc": json.dumps(document())}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_cost_is_one_spool_the_spools_the_cabinets_and_the_total(out):
    html = out["cost"]
    # figures only (his ruling of 11 October 2026): the mechanism is named under
    # its button, and VAT goes into the total's name
    assert "<tr><th>One spool</th><td>£412.30</td><td></td></tr>" in html
    assert "<tr><th>Spools</th><td>105 × £412.30</td><td>£43,292</td></tr>" in html
    assert "<tr><th>Cabinets</th><td>15</td><td>£5,250</td></tr>" in html
    assert "<tr><th>Total ex VAT</th><td>£48,542</td><td></td></tr>" in html
    assert "Pfaff" not in html and "VAT excluded" not in html
    # the count, the parts' names on hover: found on screen, fifteen names
    # crowded the tab
    assert '<tr title="drum-72, pico"><th>Unpriced</th><td>2</td><td></td></tr>' in html
    assert "Unpriced" not in out["priced"]
    assert out["none"] == ""


def test_the_graphs_read_the_worst_wire_and_the_worst_offset_at_every_capture(out):
    series = out["series"]
    # the fixture's wires: 1000, 1200 then 1500 N at the end of the tiling
    assert len(series["wire"]) == len(series["offset"]) == 4
    assert max(series["wire"]) == 1500.0
    assert series["offset"][-1] == 25.0


def test_a_graph_is_its_line_and_its_limit_dashed_at_its_place(out):
    svg = out["graph"]
    assert svg.startswith("<svg") and "worst wire, N" in svg and "one spool 2.5 N" in svg
    points = re.search(r'<polyline points="([^"]+)"', svg).group(1).split()
    assert len(points) == 3
    ys = [float(p.split(",")[1]) for p in points]
    assert ys[1] < ys[2] < ys[0]                       # SVG y runs down: 3 highest
    dash = re.search(r'<line [^>]*y1="([\d.]+)"[^>]*stroke-dasharray', svg)
    assert dash is not None
    # the limit, 2.5, between the 2 and the 3
    assert ys[1] < float(dash.group(1)) < ys[2]
    assert "NaN" not in out["flat"] and "Infinity" not in out["flat"]


def test_the_graphs_tab_is_two_graphs_or_says_there_is_no_run(out):
    assert out["graphs"].count("<svg") == 2
    assert "one spool 1,200 N" in out["graphs"] and "tolerance 20 mm" in out["graphs"]
    # with no mechanism, the wire graph has no limit line to draw
    assert out["noHave"].count("<svg") == 2 and "one spool" not in out["noHave"]
    assert out["noRun"] == ""
