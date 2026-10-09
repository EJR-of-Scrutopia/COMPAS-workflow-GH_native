"""The parts the five choices are made from (spec 2026-10-09 mechanism choices,
sections 2 and 7.1): what the studio derives from each entry when it loads the
catalogue, and the parts it refuses at start-up for a missing figure."""

import json
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402

G = 9.80665
OFFERED = ["23HS45-4204D-E1000", "34HS31-6004D-E1000", "34HS39-6004D-E1000",
           "34HS46-6004D-E1000", "34HS59-6004D-E1000", "ES-MH342200", "A6-RS400H2A1-M17",
           "A6-RS750H2A1-M17", "A6-RS1000H2A1-M17"]


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _loaded_with(tmp_path, change):
    data = json.loads(catalogue.PARTS_PATH.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "parts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return catalogue.load_parts(path)


def test_every_offered_motor_runs_on_a_drive_of_its_own_family(parts):
    offered = [key for key, entry in parts["motor"].items() if entry.get("frame")]
    assert offered == OFFERED
    for key in offered:
        drive = catalogue.drive_for(parts, key)
        assert parts["drive"][drive]["family"] == parts["motor"][key]["family"]


def test_a_stepper_is_judged_at_half_its_holding_torque_and_a_servo_at_its_rated(parts):
    stepper = parts["motor"]["34HS59-6004D-E1000"]
    servo = parts["motor"]["A6-RS750H2A1-M17"]
    assert (stepper["motor_torque"], stepper["torque_margin"]) == (12000.0, 0.5)
    assert (servo["motor_torque"], servo["torque_margin"]) == (2390.0, 0.8)


def test_a_gearbox_carries_its_output_torque_in_newton_millimetres(parts):
    assert parts["gearbox"]["EG34-G10"]["gearbox_torque"] == 39000.0
    assert parts["gearbox"]["PLG120-20"]["gearbox_torque"] == 230000.0


def test_a_pulley_is_rated_at_180_degrees_and_at_the_lower_figure_when_they_conflict(parts):
    sheave = parts["sheave"]
    assert sheave["Pfaff-DSRB-90-4"]["sheave_swl"] == pytest.approx(500 * G)
    # the page prints 500 kg at 180 degrees and 375 at 90: the lower stands
    assert sheave["GPS-WZ12.5K"]["sheave_swl"] == pytest.approx(375 * G)
    # one load with no angle is taken as given
    assert sheave["GPS-SS-100"]["sheave_swl"] == pytest.approx(500 * G)


def test_an_unpublished_pulley_efficiency_is_the_bearings_usual_figure_and_says_so(parts):
    ball, plain = parts["sheave"]["Pfaff-DSRB-90-4"], parts["sheave"]["GPS-WZ3-60"]
    assert (ball["sheave_efficiency"], ball["efficiency_assumed"]) == (0.98, True)
    assert (plain["sheave_efficiency"], plain["efficiency_assumed"]) == (0.95, True)


def test_every_price_is_compared_in_pounds_without_vat(parts):
    assert parts["gearbox"]["EG23-G20-D8"]["price_gbp"] == pytest.approx(37.03)
    assert parts["sheave"]["Pfaff-DSRB-90-4"]["price_gbp"] == pytest.approx(159.18 / 1.2)
    assert parts["gearbox"]["PLG120-3"]["price_gbp"] == pytest.approx(499.0 / 1.3226)
    # a German price includes German VAT
    assert parts["drive"]["ES-DH2306"]["price_gbp"] == pytest.approx(289.90 / 1.18 / 1.19)
    assert parts["sheave"]["GPS-WZ3-60"]["price_gbp"] is None
    assert parts["rope"]["rope-4mm"]["reels"][0]["price_gbp"] == pytest.approx(37.20)


def test_the_thin_ropes_scale_their_stiffness_as_the_others_and_say_it_is_assumed(parts):
    three = parts["rope"]["rope-3mm"]
    assert three["ea_newtons"] == pytest.approx(450000.0 * (3.0 / 4.0) ** 2)
    assert three["ea_confidence"] == "assumed"


def test_a_ropes_breaking_load_is_the_lower_of_two_sources(parts):
    four = parts["rope"]["rope-4mm"]
    assert four["rope_mbl"] == 9091.0
    assert "10250" in four["mbl_note"]


def test_an_offered_stepper_on_48_volts_with_no_phase_resistance_is_refused(tmp_path):
    def change(data):
        del data["motor"]["23HS45-4204D-E1000"]["phase_resistance_ohm"]
    with pytest.raises(catalogue.CatalogueError, match=r"^23HS45-4204D-E1000: no phase resistance ohm$"):
        _loaded_with(tmp_path, change)


def test_a_mains_fed_motor_needs_no_phase_resistance(parts):
    assert parts["motor"]["ES-MH342200"].get("phase_resistance_ohm") is None


def test_an_offered_pulley_with_no_working_load_is_refused(tmp_path):
    def change(data):
        for name in ("wll_kg_180", "wll_kg_90", "wll_kg"):
            data["sheave"]["Pfaff-DSRB-90-4"].pop(name, None)
    with pytest.raises(catalogue.CatalogueError, match=r"^Pfaff-DSRB-90-4: no working load$"):
        _loaded_with(tmp_path, change)


def test_a_price_in_a_currency_with_no_rate_is_refused(tmp_path):
    def change(data):
        del data["currency"]["USD_per_GBP"]
    with pytest.raises(catalogue.CatalogueError, match="no USD rate"):
        _loaded_with(tmp_path, change)


def test_the_catalogue_holds_only_what_the_five_choices_reach():
    """Spec section 7.1: the six configurations, the AC and boat-lift motors,
    the worm gearboxes, the inverter and the "none" drive are gone. Every motor
    is one the selects offer, every driver is some motor's, every gearbox is a
    planetary on a frame or none, and every pulley names the wire it takes."""

    import machine

    parts = catalogue.load_parts()
    assert "configurations" not in parts and "pairing" not in parts
    assert machine.offered_motors(parts) == list(parts["motor"])
    assert {entry["family"] for entry in parts["motor"].values()} == {"A", "S"}
    assert {entry["drive"] for entry in parts["motor"].values()} == set(parts["drive"])
    for key, entry in parts["gearbox"].items():
        assert key == "direct" or (entry["kind"] == "planetary" and entry.get("frame")), key
    for key, entry in parts["sheave"].items():
        assert entry.get("wire_min_mm") is not None, key


def test_the_presets_and_the_ranking_of_them_are_gone_from_the_catalogue():
    for name in ("configurations", "configuration_of", "recommend", "part_count",
                 "gearboxes_for"):
        assert not hasattr(catalogue, name), name


def test_each_ratio_is_offered_once_with_the_strongest_gearbox_at_it():
    """A frame can carry two series at one ratio: the NEMA 42 has the EG42-G100
    and the PLG120-100. The ratio is offered once, with the stronger gearbox
    (ties to the cheaper), so Recommend never judges one machine twice."""

    import machine

    parts = catalogue.load_parts()
    for motor in machine.offered_motors(parts):
        ratios = [option["ratio"] for option in machine.ratio_options(parts, motor)]
        assert len(ratios) == len(set(ratios)), motor
    offered = {option["ratio"]: option["gearbox"]
               for option in machine.ratio_options(parts, "ES-MH342200")}
    assert offered[100.0] == "EG42-G100"            # 260 N m against 175 N m
    assert machine.gearbox_for(parts, "ES-MH342200", 100) == "EG42-G100"
