"""The study's price and Recommend (spec 2026-10-09 mechanism choices,
sections 5.5 and 6)."""

import copy
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402
import recommend  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
MACHINES = [list(range(0, 7)), list(range(7, 14))]
ROUTES = [2000.0] * 14
TAKE_UPS = [[0.0, 64.0]] * 14


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 2}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def test_the_study_is_priced_part_by_part_for_every_machine(parts):
    price = recommend.study_price(parts, _built(parts), [300.0] * 14, MACHINES, ROUTES)
    counts = {line["part"]: line["count"] for line in price["lines"]}
    # two machines of seven wires, two wires a motor: four motors each
    assert counts["23HS45-4204D-E1000"] == 8 and counts["EG23-G20-D8"] == 8
    assert counts["drum-72"] == 14 and counts["MGN15H-300"] == 14
    assert counts["Pfaff-DSRB-90-4"] == 14 * 4            # four falls on every wire
    assert "drum-72" in price["unpriced"]                    # the workshop drum has no price
    assert price["priced_gbp"] == pytest.approx(
        sum(line["line_gbp"] for line in price["lines"] if line["line_gbp"] is not None)
        + price["rope"]["best"]["cost_gbp"] + price["cabinets"]["priced_gbp"])


def test_recommend_fills_the_selects_with_the_cheapest_combination_that_holds(parts):
    demands = [300.0] * 14
    best = recommend.recommend(parts, FACTS, demands, MACHINES, ROUTES, TAKE_UPS, 10.0)
    assert best["holds"] and best["choices"] is not None
    built = machine.derive(parts, best["choices"], FACTS, 10.0)
    assert machine.judge(parts, built, demands, MACHINES, 10.0)["holds"]
    # nothing priced and cheaper holds
    for choices in recommend.combinations(parts):
        try:
            other = machine.derive(parts, choices, FACTS, 10.0)
        except machine.MachineError:
            continue
        price = recommend.study_price(parts, other, demands, MACHINES, ROUTES)
        if recommend._chosen_unpriced(parts, other) or price["priced_gbp"] >= best["priced_gbp"]:
            continue
        holds = (machine.judge(parts, other, demands, MACHINES, 10.0)["holds"]
                 and machine.travel(parts, other, TAKE_UPS)["fits"])
        assert not holds, choices


def test_when_nothing_holds_the_closest_combination_and_its_failing_part_are_named(parts):
    result = recommend.recommend(parts, FACTS, [36459.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0)
    assert result["choices"] is None and not result["holds"]
    closest = result["closest"]
    # no catalogued rope carries 36.5 kN at a safety factor of five
    assert closest["margin"] < 1.0
    assert (closest["limit"], closest["part"]) == ("rope tension", "rope-8mm")


def test_a_combination_that_changes_the_net_is_tagged_to_be_confirmed_by_a_run(parts):
    run = {"rope": "rope-8mm", "pulleys": True, "wires_per_motor": 1}
    best = recommend.recommend(parts, FACTS, [300.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0,
                               run=run)
    assert best["confirm_run"] is True


def test_a_combination_with_an_unpriced_chosen_part_ranks_after_every_priced_one(parts):
    first = recommend.recommend(parts, FACTS, [300.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0)
    hidden = copy.deepcopy(parts)
    hidden["motor"][first["choices"]["motor"]]["price_gbp"] = None
    second = recommend.recommend(hidden, FACTS, [300.0] * 14, MACHINES, ROUTES, TAKE_UPS, 10.0)
    assert second["holds"] and second["unpriced"] == []
    assert second["choices"]["motor"] != first["choices"]["motor"]
