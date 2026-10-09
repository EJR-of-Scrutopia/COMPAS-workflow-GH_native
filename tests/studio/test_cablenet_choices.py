"""The panel's five choices and its tables, run under node against the server's
own answers (spec 2026-10-09 mechanism choices, section 7)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402
from test_machine_routes import CHOICE, OPTIONS, _plant  # noqa: E402

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"

HARNESS = """
import * as m from %(module)r;
import { readFileSync } from "node:fs";
const given = JSON.parse(readFileSync(%(given)r, "utf8"));
const o = given.parts.choices;
const out = {};
out.offered = m.choiceOptions(o, given.parts, given.choice);
out.kept = m.validChoices(o, given.choice);
out.newMotor = m.validChoices(o, { ...given.choice, motor: "34HS31-6004D-E1000", ratio: 50 });
out.newRope = m.validChoices(o, { ...given.choice, rope: "rope-8mm" });
out.noPulley = m.validChoices(o, { ...given.choice, pulley: null });
out.empty = m.validChoices(o, null);
out.machine = m.machineHtml(given.row, given.parts);
out.refused = m.machineHtml({ refused: "NEMA 23: no 30:1 <b>" }, given.parts);
out.verdict = m.verdictHtml(given.row.verdict);
out.travel = m.travelHtml(given.row.travel);
out.buy = m.buyHtml(given.row.price, given.row.cut_lengths);
out.price = m.priceHtml(given.row.price);
out.recommend = m.recommendHtml(given.recommend);
out.none = m.recommendHtml({ holds: false, choices: null, closest: {
  described: "rope <b>", limit: "rope tension", part: "rope-8mm", margin: 0.183 } });
out.escaped = m.escapeHtml(`<a href="x">'&'</a>`);
out.pounds = [m.pounds(12.5), m.pounds(null)];
out.marks = [m.mark(true), m.mark(false)];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    tmp_path = tmp_path_factory.mktemp("choices")
    monkeypatch = pytest.MonkeyPatch()
    try:
        client, _ = make_client(tmp_path, monkeypatch)
        _plant(tmp_path)
        parts = client.get("/api/catalogue").json()
        row = client.post("/api/studies/Tiny/cablenet/configurations",
                          json={"choices": [CHOICE], "options": OPTIONS}).json()["rows"][0]
        best = client.post("/api/studies/Tiny/cablenet/recommend",
                           json={"search": "choices", "options": OPTIONS}).json()
    finally:
        monkeypatch.undo()
    given = tmp_path / "given.json"
    given.write_text(json.dumps({"parts": parts, "choice": CHOICE, "row": row,
                                 "recommend": best}), encoding="utf-8")
    script = tmp_path / "harness.mjs"
    script.write_text(HARNESS % {"module": (STATIC / "cablenet_model.js").resolve().as_uri(),
                                 "given": str(given)}, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True,
                            encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return {"given": json.loads(given.read_text(encoding="utf-8")), **json.loads(result.stdout)}


def test_the_selects_offer_what_the_catalogue_can_build(out):
    offered = out["offered"]
    assert offered["motor"][0]["value"] == "23HS45-4204D-E1000"
    assert [r["label"] for r in offered["ratio"]] == ["none", "5:1", "10:1", "20:1", "50:1"]
    pulleys = [p["value"] for p in offered["pulley"]]
    assert pulleys[0] is None and "Pfaff-DSRB-90-4" in pulleys
    assert "Pfaff-DSRB-185-8" not in pulleys
    assert {p["label"] for p in offered["pulley"]} >= {"none", "Pfaff DSRB 90/4"}
    assert [w["value"] for w in offered["wires_per_motor"]] == [1, 2, 3, 4, 5, 6, 7]


def test_a_change_the_catalogue_cannot_build_gives_way_to_the_first_it_can(out):
    assert out["kept"] == CHOICE
    # a new motor keeps the ratio only where its frame offers it, else takes
    # the frame's first rated ratio
    ratios = [r["ratio"] for r in out["given"]["parts"]["choices"]["ratios"]["34HS31-6004D-E1000"]]
    assert out["newMotor"]["ratio"] in ratios and out["newMotor"]["ratio"] is not None
    # an 8 mm wire does not run on a pulley for 4 mm wire
    assert out["newRope"]["pulley"] != "Pfaff-DSRB-90-4"
    assert out["newRope"]["pulley"] in out["given"]["parts"]["choices"]["pulleys"]["rope-8mm"] + [None]
    assert out["noPulley"]["pulley"] is None
    assert out["empty"] == {"motor": "23HS45-4204D-E1000",
                            "ratio": out["empty"]["ratio"], "rope": "rope-4mm",
                            "pulley": out["empty"]["pulley"], "wires_per_motor": 1}
    assert out["empty"]["ratio"] is not None


def test_the_machine_is_named_by_its_parts_with_every_derived_part_in_a_table(out):
    html = out["machine"]
    assert ("23HS45-4204D-E1000 on EG23 20:1, Pfaff DSRB 90/4 pulleys, 4 mm 7x19, "
            "two wires a motor") in html
    for cell in ("Driver", "Gearbox", "EG23-G20-D8", "Pfaff-DSRB-90-4, 4 falls",
                 "Winding radius", "Groove pitch", "Wires a motor"):
        assert cell in html, cell
    assert out["refused"] == "<p>NEMA 23: no 30:1 &lt;b&gt;</p>"


def test_the_verdict_is_the_worst_margin_and_a_row_per_machine(out):
    html = out["verdict"]
    verdict = out["given"]["row"]["verdict"]
    assert html.startswith("<p><b>" + ("✓" if verdict["holds"] else "✗"))
    assert "pairing bound" in html
    assert html.count("<tr>") == 1 + len(verdict["machines"])
    assert "800.0" in html            # the worst wire's tension, one decimal


def test_travel_wire_and_price_are_numbers_against_their_limits(out):
    travel = out["travel"]
    assert "Rope on drum, mm" in travel and "Carriage, mm" in travel
    assert "3.00" in travel           # 3 mm of carriage for the first wire
    buy = out["buy"]
    assert "Total, m" in buy and "Cut lengths, m" in buy and "Bought" in buy
    price = out["price"]
    total = out["given"]["row"]["price"]["priced_gbp"]
    assert "£{:.2f}".format(total) in price
    assert "1 cabinets, exc VAT" in price
    assert "23HS45-4204D-E1000" in price and "Cabinet, each" in price
    # the workshop drum has no price, so the total is a floor
    assert "floor" in price and "no price" in price


def test_each_cabinet_line_says_who_quoted_it_in_what_and_links_its_source(out):
    price = out["price"]
    assert "<th>Supplier</th><th>Quoted</th>" in price
    driver = next(line for line in out["given"]["row"]["price"]["cabinets"]["cabinets"][0]["lines"]
                  if line["part"] == "CL57T-V41")
    assert driver["source"].startswith("https://")
    assert '<a href="{}" target="_blank" rel="noopener">StepperOnline UK</a>'.format(
        driver["source"]) in price
    assert "<td>GBP, VAT unclear</td>" in price
    # a source that is a note, not a page, is the cell's title
    assert '<span title="T1 note 14' in price


def test_recommend_reads_as_its_pick_or_the_closest_and_its_part(out):
    best = out["given"]["recommend"]
    assert out["recommend"].startswith("<p><b>" + best["described"])
    assert "£{:.2f}".format(best["priced_gbp"]) in out["recommend"]
    assert out["none"] == ("<p><b>none holds</b>; closest rope &lt;b&gt;, rope tension "
                           "rope-8mm 0.2x</p>")


def test_nothing_is_written_without_escaping_and_no_sentence_says_why(out):
    assert out["escaped"] == "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;"
    assert out["pounds"] == ["£12.50", "no price"]
    assert out["marks"] == ["✓", "✗"]
    for key in ("machine", "verdict", "travel", "buy", "price", "recommend"):
        for word in ("because", "should", "cannot", "means"):
            assert word not in out[key].lower(), (key, word)
