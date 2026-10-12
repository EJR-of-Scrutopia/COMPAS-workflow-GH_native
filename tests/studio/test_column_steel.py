"""The column as specced, in the steel chosen (Param, 2026-10-12): "i also
would like the column to have a thickness and shape to have what we have
specced also. if we can choose different steel for that would be good too".
His answers: a round tube at the chosen size, the wall showing at its open
ends; the size, the grade and the finish chosen, the run judging the trees in
the tube chosen rather than always a CHS 60.3 in S355; each study starting at
the tube nearest the one its export swept."""

import json
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402

# ISO 4200 / EN 10220 series 1, the circular hollow sections a stockist holds
SERIES_1 = [21.3, 26.9, 33.7, 42.4, 48.3, 60.3, 76.1, 88.9]


def test_the_catalogue_holds_the_tubes_the_grades_and_the_finishes():
    parts = catalogue.load_parts()
    tubes = parts["column_tube"]
    assert sorted(entry["diameter_mm"] for entry in tubes.values()) == SERIES_1
    assert tubes["CHS-60.3"]["diameter_mm"] == 60.3
    grades = parts["column_steel"]
    # EN 1993-1-1 Table 3.1 and Table 6.2: hot-finished hollow sections, curve a
    for key, fy in (("S235", 235.0), ("S275", 275.0), ("S355", 355.0)):
        assert (grades[key]["fy_mpa"], grades[key]["e_mpa"]) == (fy, 210000.0), key
        assert (grades[key]["alpha"], grades[key]["lambda0"]) == (0.21, 0.2), key
    # EN 1993-1-4: 1.4401 (316) on the hollow sections' own curve
    stainless = grades["1.4401"]
    assert (stainless["fy_mpa"], stainless["e_mpa"]) == (220.0, 200000.0)
    assert (stainless["alpha"], stainless["lambda0"]) == (0.49, 0.3)
    assert stainless["finish"] == "stainless"
    finishes = parts["column_finish"]
    assert {"galvanised", "painted", "mill", "stainless"} <= set(finishes)
    for key, finish in finishes.items():
        look = finish["render"]
        assert len(look["colour"]) == 7 and look["colour"].startswith("#"), key
        assert 0.0 <= look["metalness"] <= 1.0 and 0.0 <= look["roughness"] <= 1.0, key


@pytest.mark.parametrize("spoil, word", [
    (lambda parts: parts["column_finish"]["painted"].pop("render"), "painted"),
    (lambda parts: parts["column_steel"]["1.4401"].__setitem__("finish", "gold"), "gold"),
    (lambda parts: parts["column_steel"]["S355"].pop("fy_mpa"), "S355"),
    (lambda parts: parts["column_tube"]["CHS-26.9"].__setitem__("diameter_mm", -1), "CHS-26.9"),
])
def test_a_column_entry_that_cannot_be_drawn_or_judged_is_refused(tmp_path, spoil, word):
    parts = json.loads((STUDIO / "parts.json").read_text(encoding="utf-8"))
    spoil(parts)
    path = tmp_path / "parts.json"
    path.write_text(json.dumps(parts), encoding="utf-8")
    with pytest.raises(catalogue.CatalogueError, match=word):
        catalogue.load_parts(path)


pytest.importorskip("fastapi")

from test_app import make_client, wait_for  # noqa: E402
from test_formwork_routes import RUN, _plant  # noqa: E402


def test_the_route_lists_the_tubes_grades_and_finishes_and_the_spec(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    body = client.get("/api/column-steel").json()
    assert [row["diameter_mm"] for row in body["tubes"]] == SERIES_1
    assert body["tubes"][5] == {"key": "CHS-60.3", "label": "CHS 60.3", "diameter_mm": 60.3}
    grades = {row["key"]: row for row in body["grades"]}
    assert grades["S355"]["label"] == "S355" and grades["S355"]["finish"] is None
    assert grades["1.4401"]["label"] == "316 stainless" and grades["1.4401"]["finish"] == "stainless"
    finishes = {row["key"]: row for row in body["finishes"]}
    assert finishes["galvanised"]["render"] == catalogue.load_parts()[
        "column_finish"]["galvanised"]["render"]
    # the spec of 9 October 2026: CHS 60.3, S355, a 3.2 mm wall
    assert body["spec"] == {"tube": "CHS-60.3", "grade": "S355", "finish": "galvanised",
                            "wall": 3.2}


def _seen_run(tmp_path, monkeypatch, extra):
    seen = {}

    def fake(request, progress=None):
        seen.update(request)
        return {"schema": "bench.formwork-sim/1", "study": request["study"], "captures": []}

    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=fake)
    _plant(tmp_path)
    started = client.post("/api/studies/Tiny/formwork/run", json={**RUN, **extra})
    assert started.status_code == 202, started.text
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]
    return seen


def test_the_run_judges_the_trees_in_the_tube_and_steel_chosen(tmp_path, monkeypatch):
    seen = _seen_run(tmp_path, monkeypatch, {"tube": "CHS-26.9", "grade": "1.4401", "wall": 2.6})
    assert seen["tube"] == {"diameter": 26.9, "grade": "1.4401", "fy": 220.0, "e": 200000.0,
                            "alpha": 0.49, "lambda0": 0.3}
    assert seen["wall"] == 2.6
    assert seen["options"]["tube"] == "CHS-26.9" and seen["options"]["grade"] == "1.4401"


def test_a_run_that_names_no_tube_is_the_spec(tmp_path, monkeypatch):
    seen = _seen_run(tmp_path, monkeypatch, {})
    assert seen["tube"] == {"diameter": 60.3, "grade": "S355", "fy": 355.0, "e": 210000.0,
                            "alpha": 0.21, "lambda0": 0.2}


def test_a_tube_or_grade_not_in_the_catalogue_or_a_wall_too_thick_for_it_is_a_400(
        tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, formwork_runner=lambda request, progress=None: {})
    for bad, word in (({"tube": "CHS-1000"}, "tube"), ({"grade": "S999"}, "grade"),
                      ({"tube": "CHS-26.9", "wall": 13.5}, "wall")):
        response = client.post("/api/studies/Tiny/formwork/run", json={**RUN, **bad})
        assert response.status_code == 400, bad
        assert word in response.json()["detail"], bad
