"""Each wire's limit and verdict, and its drum and carriage (spec 2026-10-09
mechanism choices, sections 4.1 to 4.5)."""

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
ADVANTAGE = (1.0 - 0.98 ** 4) / (1.0 - 0.98)        # four falls on ball-bearing pulleys


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "34HS59-6004D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def test_the_machine_winds_at_its_own_radius_with_its_gearbox_and_its_sharing(parts):
    mechanism = catalogue.mechanism_for(parts, _built(parts, wires_per_motor=2), 10.0)
    assert mechanism.drum_radius == 33.9
    assert mechanism.gearbox_torque == 90000.0
    assert mechanism.wires_per_motor == 2


def test_a_wire_is_limited_by_its_own_rope_when_its_motor_has_room(parts):
    # 2,000 N against the 4 mm rope's 9,091 N over 5; the gearbox at the drum
    # carries 2,000 / 3.88 x 33.9 = 17,469 N mm of its 90,000
    verdict = machine.judge(parts, _built(parts), [2000.0], [[0]], 10.0)
    wire = verdict["wires"][0]
    assert (wire["limit"], wire["part"], wire["holds"]) == ("rope tension", "rope-4mm", False)
    assert wire["margin"] == pytest.approx(9091.0 / 5.0 / 2000.0)


def test_two_wires_on_one_motor_are_limited_together_by_its_gearbox(parts):
    # straight off the drum: 2 x 1,500 N x 33.9 mm = 101,700 N mm against the
    # EG34-G20's 90,000, though each rope alone holds 1,818 N
    built = _built(parts, pulley=None, wires_per_motor=2)
    verdict = machine.judge(parts, built, [1500.0, 1500.0], [[0, 1]], 10.0, motors=[[[0, 1]]])
    for wire in verdict["wires"]:
        assert (wire["limit"], wire["part"], wire["holds"]) == ("gearbox torque", "EG34-G20", False)
        assert wire["margin"] == pytest.approx(90000.0 / (3000.0 * 33.9))
    assert verdict["pairing"] == "run" and not verdict["holds"]


def test_without_a_run_every_motor_carries_its_machines_largest_demands(parts):
    built = _built(parts, pulley=None, wires_per_motor=2)
    demands = [1500.0, 1500.0, 100.0, 100.0]
    bound = machine.judge(parts, built, demands, [[0, 1, 2, 3]], 10.0)
    assert bound["pairing"] == "bound"
    assert [wire["limit"] for wire in bound["wires"]] == ["gearbox torque"] * 4
    assert not bound["holds"]
    paired = machine.judge(parts, built, demands, [[0, 1, 2, 3]], 10.0,
                           motors=[[[0, 2], [1, 3]]])
    assert paired["holds"]
    assert [wire["limit"] for wire in paired["wires"][:2]] == ["rope tension", "rope tension"]


def test_one_wire_a_motor_carries_only_its_own_wire(parts):
    # straight off the drum, a 100 N wire's motor is not charged with its
    # neighbour's 1,500 N: there is nothing to pair
    built = _built(parts, pulley=None)
    verdict = machine.judge(parts, built, [1500.0, 100.0], [[0, 1]], 10.0)
    assert verdict["pairing"] == "own"
    assert verdict["wires"][1]["limit"] == "rope tension"
    assert verdict["wires"][1]["margin"] == pytest.approx(9091.0 / 5.0 / 100.0)


def test_the_worst_wire_of_each_machine_and_of_the_study_are_named(parts):
    verdict = machine.judge(parts, _built(parts), [500.0, 1900.0, 800.0], [[0, 1], [2]], 10.0)
    assert [row["worst_wire"] for row in verdict["machines"]] == [1, 2]
    assert verdict["worst"]["wire"] == 1
    assert [row["holds"] for row in verdict["machines"]] == [False, True]


def test_a_wire_with_no_demand_holds_with_no_margin(parts):
    verdict = machine.judge(parts, _built(parts), [0.0], [[0]], 10.0)
    assert verdict["wires"][0]["margin"] is None and verdict["holds"]


def test_without_pulleys_a_wire_runs_on_one_fall_whatever_the_export_says(parts):
    built = _built(parts, pulley=None)
    verdict = machine.judge(parts, built, [1000.0], [[0]], 10.0, reeves=[4])
    single = catalogue.ceiling_terms(
        catalogue.mechanism_for(parts, built, 10.0)._replace(wires_per_motor=1))
    assert built["reeve_factor"] == 1
    assert verdict["wires"][0]["ceiling"] == pytest.approx(
        min(v for k, v in single.items() if k not in machine.SHARED_TERMS))


def test_the_real_studys_take_up_fits_the_drum_and_the_rail(parts):
    # 64 mm taken in at the anchor, four falls: 256 mm onto a 33.9 mm spool
    # grooved for 4 mm rope at 4.4 mm, which holds 34 turns, above two dead turns
    result = machine.travel(parts, _built(parts), [[0.0, 30.0, 64.0, 20.0]])
    wire = result["wires"][0]
    turn = 2.0 * math.pi * 33.9
    assert wire["drum_rope_mm"] == pytest.approx(2 * turn + 4 * 64.0)
    assert wire["drum_capacity_mm"] == pytest.approx(34 * turn)
    assert wire["carriage_mm"] == pytest.approx(64.0)
    assert wire["drum_fits"] and wire["rail_fits"] and result["fits"]
    assert wire["in_and_out_mm"] == pytest.approx(4 * (30.0 + 34.0 + 44.0))


def test_a_carriage_past_its_stroke_and_a_drum_past_its_layer_do_not_fit(parts):
    result = machine.travel(parts, _built(parts), [[350.0], [2000.0]])
    far, deep = result["wires"]
    assert not far["rail_fits"] and far["drum_fits"]
    assert not deep["drum_fits"]
    assert not result["fits"]


def test_rope_paid_out_past_the_start_must_be_on_the_drum_from_the_beginning(parts):
    wire = machine.travel(parts, _built(parts), [[-10.0, 5.0]])["wires"][0]
    assert wire["paid_out_mm"] == 10.0
    assert wire["drum_rope_mm"] == pytest.approx(2 * 2.0 * math.pi * 33.9 + 4 * 10.0 + 4 * 5.0)
    assert wire["carriage_mm"] == pytest.approx(15.0)


def test_the_drum_and_pulley_diameters_over_the_ropes_are_numbers_with_no_verdict(parts):
    result = machine.travel(parts, _built(parts), [[0.0]])
    assert result["drum_over_rope"] == pytest.approx(67.8 / 4.0)
    assert result["pulley_over_rope"] == pytest.approx(90.0 / 4.0)


def test_the_cable_net_runs_reel_commands_become_each_wires_take_up():
    series = machine.take_ups_from_commands([[-5.0, 0.0], [-3.0, 2.0], [4.0, 0.0]])
    assert series == [[5.0, 8.0, 4.0], [0.0, -2.0, -2.0]]
