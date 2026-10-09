"""The real-study script's reading of the formwork captures and its wording of
Recommend's answer (spec 2026-10-09 mechanism choices, section 9)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")
pytest.importorskip("scipy")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "scripts"))
sys.path.insert(0, str(REPO / "bench" / "studio"))

import mechanism_real  # noqa: E402
import solve_formwork  # noqa: E402
from test_solve_formwork import _request  # noqa: E402


def test_each_wires_peak_is_its_greatest_tension_over_every_capture():
    document = solve_formwork.solve(_request())
    peaks, where = mechanism_real.formwork_peaks(document)
    every = [[float(t) for t in solve_formwork.unpack(c["wire_tension"])]
             for c in document["captures"]]
    assert peaks == [max(column) for column in zip(*every)]
    assert max(peaks) == max(map(max, every))
    assert where["phase"] in ("raise", "finish", "hold", "tiling")
    assert max(float(t) for t in solve_formwork.unpack(where["wire_tension"])) == max(peaks)


def test_recommends_answer_is_said_as_numbers_and_part_names():
    held = {"holds": True, "described": "34HS31-6004D-E1000 on EG34 50:1, no pulleys, 5 mm 7x19, "
                                        "seven wires a motor",
            "priced_gbp": 34008.2, "limit": "motor torque", "part": "34HS31-6004D-E1000",
            "margin": 1.27, "confirm_run": True, "unpriced": ["drum-72"]}
    assert mechanism_real.recommend_lines(held) == [
        "recommend: 34HS31-6004D-E1000 on EG34 50:1, no pulleys, 5 mm 7x19, seven wires a motor",
        "  GBP 34008.20 (floor: drum-72); worst motor torque, 34HS31-6004D-E1000, 1.27x; "
        "run to confirm"]
    none = {"holds": False, "choices": None, "closest": {
        "described": "ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor",
        "limit": "rope tension", "part": "rope-8mm", "margin": 0.1827, "priced_gbp": 1.0,
        "travel_fits": True}}
    assert mechanism_real.recommend_lines(none) == [
        "recommend: none holds",
        "  closest ES-MH342200 on EG42 100:1, no pulleys, 8 mm 7x19, one wire a motor; "
        "rope tension, rope-8mm, 0.183x"]


def test_the_captures_over_a_tension_are_named_in_order():
    document = solve_formwork.solve(_request())
    peaks, _ = mechanism_real.formwork_peaks(document)
    assert mechanism_real.captures_over(document, max(peaks) + 1.0) == []
    every = mechanism_real.captures_over(document, -1.0)
    assert every == [mechanism_real.where_of(c) for c in document["captures"]]
    assert every[0] == "raise t 30" and every[-1].startswith("tiling ")
