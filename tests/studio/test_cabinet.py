"""The control cabinet each machine needs, by T1 note 14's rules (spec
2026-10-09 mechanism choices, section 5)."""

import copy
import math
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import cabinet  # noqa: E402
import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}
SEVEN = [300.0] * 7


@pytest.fixture(scope="module")
def parts():
    return catalogue.load_parts()


def _built(parts, **changes):
    choices = {"motor": "23HS45-4204D-E1000", "ratio": 20, "pulley": "Pfaff-DSRB-90-4",
               "rope": "rope-4mm", "wires_per_motor": 1}
    choices.update(changes)
    return machine.derive(parts, choices, FACTS, 10.0)


def _counts(result):
    return {line["part"]: line["count"] for line in result["lines"]}


def test_note_14s_seven_23hs45s_take_the_21_amp_supply(parts):
    # each motor (4.2^2 x 0.82 + 3.0 x 2 pi) / (0.85 x 48) = 0.817 A, the 24 V
    # rail (0.5 + 7 x 0.8) A through the buck 3.59 A: 9.30 A, twice it 18.6 A
    result = cabinet.cabinet_for(parts, _built(parts), SEVEN)
    supply = result["supply"]
    assert supply["per_motor_a"] == pytest.approx(
        (4.2 ** 2 * 0.82 + 3.0 * 2 * math.pi) / (0.85 * 48))
    assert supply["worst_a"] == pytest.approx(7 * supply["per_motor_a"] + 24 * 6.1 / 0.85 / 48)
    assert (supply["model"], supply["count"]) == ("UHP-1000-48", 1)


def test_seven_12_newton_metre_nema_34s_need_two_supplies(parts):
    result = cabinet.cabinet_for(parts, _built(parts, motor="34HS59-6004D-E1000"), SEVEN)
    assert result["supply"]["needed_a"] > 21.0
    assert (result["supply"]["model"], result["supply"]["count"]) == ("UHP-1000-48", 2)


def test_two_wires_a_motor_halve_the_motor_parts(parts):
    counts = _counts(cabinet.cabinet_for(parts, _built(parts, wires_per_motor=2), SEVEN))
    assert counts["CL57T-V41"] == 4
    assert counts["driver-adapter"] == 4 and counts["rs-177-0114"] == 4
    assert counts["atc-7.5a"] == 4 and counts["jorest-atc-holder"] == 5
    assert counts["octopus-pro-h723"] == 1 and counts["sequent-8-mosfet"] == 1
    assert counts["cy4x1-10m"] == 1 and counts["cy7x05"] == 8


def test_a_mains_fed_drive_has_no_48_volt_supply_but_a_24_volt_one(parts):
    built = _built(parts, motor="A6-RS750H2A1-M17", ratio=5, wires_per_motor=2)
    result = cabinet.cabinet_for(parts, built, SEVEN)
    counts = _counts(result)
    assert result["supply"]["kind"] == "mains"
    assert "UHP-1000-48" not in counts and "F60J24V10A5L" not in counts
    # (0.5 + 4 x 0.8) A twice is 7.4 A: past the HDR-150-24, so the NDR-240-24
    assert (result["supply"]["model"], result["supply"]["count"]) == ("NDR-240-24", 1)
    fuse = next(line for line in result["lines"] if line["part"] == "driver fuse")
    assert fuse["unit_gbp"] is None and fuse["count"] == 4
    driver = next(line for line in result["lines"] if line["part"] == "A6-750RS")
    assert driver["line_gbp"] == 0.0


def test_each_wire_takes_the_smallest_zemic_cell_that_covers_its_peak_and_one_spare(parts):
    result = cabinet.cabinet_for(parts, _built(parts), [300.0, 600.0, 2000.0, 36000.0])
    counts = _counts(result)
    assert counts["zemic-H3-50kg"] == 1 and counts["zemic-H3-100kg"] == 1
    assert counts["zemic-H3-250kg"] == 1
    assert counts["zemic-H3-5000kg"] == 2            # the 36 kN wire's and the spare
    assert counts["hx711-sparkfun"] == 5 and counts["pico"] == 1


def test_a_peak_beyond_the_largest_cell_is_refused(parts):
    with pytest.raises(cabinet.CabinetError, match=r"^load cell: none rated for 400000 N$"):
        cabinet.load_cell_for(parts, 400000.0)


def test_the_formal_safety_upgrade_is_listed_and_kept_out_of_the_total(parts):
    result = cabinet.cabinet_for(parts, _built(parts), SEVEN)
    upgrade = [line for line in result["lines"] if not line["in_total"]]
    assert sorted(line["part"] for line in upgrade) == ["albright-sw185-108", "psr-spp"]
    counted = [line for line in result["lines"] if line["in_total"]]
    assert result["priced_gbp"] == pytest.approx(
        sum(line["line_gbp"] for line in counted if line["line_gbp"] is not None))
    assert result["unpriced"] == sum(1 for line in counted if line["line_gbp"] is None)
    assert result["unpriced"] > 0


def test_the_study_adds_every_machines_cabinet(parts):
    built = _built(parts)
    study = cabinet.cabinets(parts, built, [300.0] * 14, [list(range(7)), list(range(7, 14))])
    assert len(study["cabinets"]) == 2
    assert study["priced_gbp"] == pytest.approx(2 * study["cabinets"][0]["priced_gbp"])


def test_a_24_volt_load_past_the_buck_is_refused(parts):
    small = copy.deepcopy(parts)
    small["cabinet"]["F60J24V10A5L"]["amps"] = 5.0
    with pytest.raises(cabinet.CabinetError, match=r"^F60J24V10A5L: 24 V load 6.1 A over 5 A$"):
        cabinet.cabinet_for(small, _built(small), SEVEN)


def test_every_line_says_who_quoted_its_price_in_what_and_from_where(parts):
    """Spec section 5.5: the unit price is pounds without VAT; the line says
    the currency and VAT basis it was quoted in, who quoted it and the source."""

    lines = cabinet.cabinet_for(parts, _built(parts), SEVEN)["lines"]
    supply = next(line for line in lines if line["part"] == "UHP-1000-48")
    assert supply["supplier"] == "RS America" and supply["quoted"] == "USD, VAT unclear"
    assert supply["source"].startswith("T1 note 14")
    cell = next(line for line in lines if line["part"].startswith("zemic-"))
    assert cell["quoted"] == "GBP, VAT exc" and cell["source"].startswith("https://")
    driver = next(line for line in lines if line["part"] == "CL57T-V41")
    assert driver["supplier"] == "StepperOnline UK"
    # a line with no price was quoted in nothing
    adapter = next(line for line in lines if line["part"] == "driver-adapter")
    assert adapter["unit_gbp"] is None and adapter["quoted"] is None
    assert all({"supplier", "quoted", "source"} <= set(line) for line in lines)
