"""The wire to buy (spec 2026-10-09 mechanism choices, section 4.6): each cut
length, and the cheaper of buying by the metre or on the supplier's reels."""

import copy
import math
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
TURN = 2.0 * math.pi * 33.9


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "34HS59-6004D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def test_an_eye_takes_thirty_diameters_and_its_ferrule(parts):
    assert machine.termination_mm(parts, "rope-4mm") == pytest.approx(30 * 4 + 18)
    assert machine.termination_mm(parts, "rope-2mm-7x7") == pytest.approx(30 * 2 + 9)


def test_one_wires_cut_length_worked_by_hand(parts):
    # 1,500 mm of route, three extra falls over the 300 mm stroke, two dead
    # turns of the 33.9 mm spool, an eye of 138 mm at each end and 250 mm to cut
    row = machine.cut_lengths(parts, _built(parts), [1500.0])[0]
    assert row["length_mm"] == pytest.approx(1500 + 3 * 300 + 2 * TURN + 2 * 138 + 250)
    assert not row["is_floor"]


def test_rope_the_drum_pays_out_past_its_start_is_bought_with_its_falls(parts):
    stored = machine.cut_lengths(parts, _built(parts), [1500.0], paid_out_mm=[10.0])[0]
    plain = machine.cut_lengths(parts, _built(parts), [1500.0])[0]
    assert stored["length_mm"] - plain["length_mm"] == pytest.approx(4 * 10.0)


def test_without_pulleys_there_are_no_falls_to_buy(parts):
    row = machine.cut_lengths(parts, _built(parts, pulley=None), [1500.0])[0]
    assert row["length_mm"] == pytest.approx(1500 + 2 * TURN + 2 * 138 + 250)


def test_a_rope_size_with_no_ferrule_figure_gives_a_floor(parts):
    bare = copy.deepcopy(parts)
    del bare["rules"]["termination"]["ferrule_length_mm"]["4"]
    row = machine.cut_lengths(bare, _built(bare), [1500.0])[0]
    assert row["is_floor"]
    assert row["length_mm"] == pytest.approx(1500 + 3 * 300 + 2 * TURN + 250)


def test_the_rope_is_bought_the_cheaper_way(parts):
    # ten lengths of 3 m of 4 mm rope: 30 m by the metre at 0.38 is cheaper
    # than a 100 m reel at 37.20
    bought = machine.rope_to_buy(parts, _built(parts), [3000.0] * 10)
    assert bought["total_m"] == pytest.approx(30.0)
    assert bought["best"]["buy"] == "by the metre"
    assert bought["best"]["cost_gbp"] == pytest.approx(30.0 * 0.38)


def test_reels_win_when_the_lengths_pack_well_and_a_metre_costs_more(parts):
    cheap = copy.deepcopy(parts)
    cheap["rope"]["rope-4mm"]["price_gbp"] = 1.0
    bought = machine.rope_to_buy(cheap, _built(cheap), [24000.0] * 8)
    # eight 24 m lengths: four to a 100 m reel, two reels at 37.20
    assert bought["best"] == {"buy": "100 m reels", "reels": 2, "metres": 200.0,
                              "cost_gbp": pytest.approx(2 * 37.20)}


def test_a_length_longer_than_a_reel_never_comes_off_that_reel(parts):
    bought = machine.rope_to_buy(parts, _built(parts), [120000.0])
    assert [option["buy"] for option in bought["options"]] == ["by the metre"]


def test_a_rope_with_no_price_at_all_is_a_floor(parts):
    bare = copy.deepcopy(parts)
    bare["rope"]["rope-4mm"]["price_gbp"] = None
    for reel in bare["rope"]["rope-4mm"]["reels"]:
        reel["price_gbp"] = None
    bought = machine.rope_to_buy(bare, _built(bare), [3000.0])
    assert bought["best"] is None and bought["is_floor"]


def test_each_wire_falls_on_its_own_reeving_where_the_export_gives_one(parts):
    """An export that reeves one wire on four falls and the next on two: the
    drum, the cut length and the pulleys bought follow each wire's own."""

    import recommend

    built = _built(parts)
    reeves = [4, 2]
    travel = machine.travel(parts, built, [[0.0, 10.0], [0.0, 10.0]], reeves=reeves)
    first, second = travel["wires"]
    # 10 mm taken in at the anchor is 40 mm on four falls, 20 mm on two
    assert first["drum_rope_mm"] - second["drum_rope_mm"] == pytest.approx(20.0)
    cuts = machine.cut_lengths(parts, built, [1000.0, 1000.0], reeves=reeves)
    # two more falls over the 300 mm stroke
    assert cuts[0]["length_mm"] - cuts[1]["length_mm"] == pytest.approx(2 * 300.0)
    price = recommend.study_price(parts, built, [300.0, 300.0], [[0, 1]], [1000.0, 1000.0],
                                  reeves=reeves)
    pulleys = next(line for line in price["lines"] if line["part"] == "Pfaff-DSRB-90-4")
    assert pulleys["count"] == 4 + 2
    # without pulleys every wire runs on one fall, whatever the export says
    plain = _built(parts, pulley=None)
    same = machine.cut_lengths(parts, plain, [1000.0, 1000.0], reeves=reeves)
    assert same[0]["length_mm"] == pytest.approx(same[1]["length_mm"])
