"""The run's cost and its bill of materials (spec 2026-10-11 one Cable net
tab, section 8.2): the run's mechanism priced on the study's machines, each
wire's demand its peak tension in the run; one spooling mechanism, the spools,
the cabinets and the total, VAT excluded; Export BOM writes it as a workbook
in the export folder."""

from __future__ import annotations

import base64
import struct
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
sys.path.insert(0, str(STUDIO))

import bom  # noqa: E402
import catalogue  # noqa: E402
import machine  # noqa: E402
import recommend  # noqa: E402
from test_app import make_client, wait_for  # noqa: E402
from test_formwork_routes import MECHANISM, RUN, _plant  # noqa: E402

ANGLE = 10.0
# the Tiny study's machine: four wires on one machine, each straight off its drum
FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 1, "spools": 7, "nodes": [0, 2, 6, 8],
         "reeves": [1, 1, 1, 1], "routes_mm": [1500.0, 1600.0, 1700.0, 1800.0],
         "machines": [[0, 1, 2, 3]]}


def pack(values):
    return {"shape": [len(values)],
            "f32": base64.b64encode(struct.pack("<%df" % len(values), *values)).decode()}


def _document():
    # three captures: the second wire peaks at the hold, the fourth while tiling
    tensions = [[100.0, 200.0, 50.0, 10.0], [300.0, 900.0, 60.0, 20.0],
                [250.0, 400.0, 70.0, 1200.0]]
    return {"schema": "bench.formwork-sim/1",
            "options": {"mechanism": dict(MECHANISM), "have_newtons": 1000.0},
            "rim": {"nodes": [0, 2, 6, 8], "names": ["a", "b", "c", "d"]},
            "captures": [{"phase": phase, "wire_tension": pack(t)}
                         for phase, t in zip(("raise", "hold", "tiling"), tensions)]}


def test_each_wire_s_demand_is_its_peak_tension_in_the_run():
    peaks = bom.run_peaks(_document())
    assert peaks == {0: (300.0, 1), 2: (900.0, 1), 6: (70.0, 2), 8: (1200.0, 2)}


def test_the_cost_is_one_spooling_mechanism_the_spools_the_cabinets_and_the_total():
    parts = catalogue.load_parts()
    built = machine.derive(parts, MECHANISM, FACTS, ANGLE)
    cost = bom.run_cost(parts, built, FACTS, _document())
    price = recommend.study_price(parts, built, [300.0, 900.0, 70.0, 1200.0],
                                  FACTS["machines"], FACTS["routes_mm"], reeves=FACTS["reeves"])
    assert cost["spools"] == 4 and cost["cabinets"] == 1
    assert cost["total_gbp"] == pytest.approx(price["priced_gbp"])
    assert cost["cabinets_gbp"] == pytest.approx(price["cabinets"]["priced_gbp"])
    assert cost["spool_gbp"] * 4 + cost["cabinets_gbp"] == pytest.approx(cost["total_gbp"])
    assert cost["described"] == machine.describe(parts, built)
    assert [w["peak_newtons"] for w in cost["wires"]] == [300.0, 900.0, 70.0, 1200.0]
    assert [w["name"] for w in cost["wires"]] == ["a", "b", "c", "d"]
    assert cost["have_newtons"] == 1000.0
    # each unpriced part named once, however many cabinets carry it
    assert cost["unpriced"] == len(cost["unpriced_parts"])
    assert len(set(cost["unpriced_parts"])) == len(cost["unpriced_parts"])


def test_the_bill_of_materials_is_a_workbook_of_the_parts_and_the_wires(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    parts = catalogue.load_parts()
    built = machine.derive(parts, MECHANISM, FACTS, ANGLE)
    cost = bom.run_cost(parts, built, FACTS, _document())
    path = bom.write_bom(tmp_path / "tiny-bom.xlsx", cost, "Tiny")
    book = openpyxl.load_workbook(path)
    assert book.sheetnames == ["Bill of materials", "Wires"]
    rows = [[cell.value for cell in row] for row in book["Bill of materials"].iter_rows()]
    assert rows[0] == ["Part", "Count", "Unit (GBP)", "Line (GBP)", "Note"]
    parts_listed = [row[0] for row in rows]
    assert MECHANISM["motor"] in parts_listed
    total = next(row for row in rows if row[0] == "Total, VAT excluded")
    assert total[3] == pytest.approx(cost["total_gbp"])
    wires = [[cell.value for cell in row] for row in book["Wires"].iter_rows()]
    assert wires[0] == ["Wire", "Rim node", "Peak tension (N)", "One spool's pull (N)", "Within"]
    assert wires[2][:3] == ["b", 2, 900.0] and wires[4][4] == "no"


def test_the_routes_price_the_run_and_write_its_bill_of_materials(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=lambda r, p=None: _document())
    _plant(tmp_path)
    body = {key: value for key, value in RUN.items() if key != "prestress"}
    started = client.post("/api/studies/Tiny/formwork/run", json={**body, "mechanism": MECHANISM})
    assert wait_for(client, started.json()["run"])["state"] == "done"
    cost = client.get("/api/studies/Tiny/formwork/cost", params=RUN)
    assert cost.status_code == 200, cost.text
    assert cost.json()["spools"] == 4 and cost.json()["total_gbp"] > 0
    import app as app_module
    written = client.post("/api/studies/Tiny/formwork/bom", json=RUN)
    assert written.status_code == 200, written.text
    path = Path(written.json()["path"])
    # in the export folder, never one of his own folders while testing
    assert path.parent == Path(app_module.CABLENET_EXPORTS_DIR) and path.is_file()
    assert path.parent.is_relative_to(tmp_path)
    assert path.name.startswith("tiny-bom-") and path.suffix == ".xlsx"


def test_a_study_with_no_run_or_a_run_with_no_mechanism_has_no_cost(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch,
                            formwork_runner=lambda r, p=None: {**_document(), "options": {}})
    _plant(tmp_path)
    none = client.get("/api/studies/Tiny/formwork/cost", params=RUN)
    assert none.status_code == 404
    started = client.post("/api/studies/Tiny/formwork/run", json=RUN)     # a named prestress
    assert wait_for(client, started.json()["run"])["state"] == "done"
    plain = client.get("/api/studies/Tiny/formwork/cost", params=RUN)
    assert plain.status_code == 400 and "no mechanism" in plain.json()["detail"]
    refused = client.post("/api/studies/Tiny/formwork/bom", json=RUN)
    assert refused.status_code == 400
