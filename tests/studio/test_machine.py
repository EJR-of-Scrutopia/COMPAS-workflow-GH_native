"""The machine five choices make on the exported machine (spec 2026-10-09
mechanism choices, sections 2 and 3)."""

import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4}


def _parts():
    planetary = dict(kind="planetary", gear_efficiency=0.94)
    return {
        "rules": {"groove_pitch_factor": 1.1},
        "motor": {
            "23HS45": {"family": "A", "frame": "NEMA 23", "motor_torque": 3000.0, "drive": "CL57T"},
            "34HS59": {"family": "A", "frame": "NEMA 34", "motor_torque": 12000.0, "drive": "CL86T"},
            "old-34": {"family": "A", "motor_torque": 9000.0, "drive": "CL86T"},
        },
        "drive": {"CL57T": {"family": "A"}, "CL86T": {"family": "A"}},
        "gearbox": {
            "direct": {"kind": "none", "gear_ratio": 1.0, "gear_efficiency": 1.0},
            "EG23-G20": dict(planetary, frame="NEMA 23", series="EG23", gear_ratio=20.0,
                             gearbox_torque=30000.0),
            "EG23-G5": dict(planetary, frame="NEMA 23", series="EG23", gear_ratio=5.0,
                            gearbox_torque=28000.0),
            "EG23-G10": dict(planetary, frame="NEMA 23", series="EG23", gear_ratio=10.0,
                             gearbox_torque=None),
            "EG34-G20": dict(planetary, frame="NEMA 34", series="EG34", gear_ratio=20.0,
                             gearbox_torque=90000.0),
        },
        "rope": {
            "rope-4mm": {"diameter_mm": 4.0, "rope_mbl": 9091.0, "construction": "7x19"},
            "rope-8mm": {"diameter_mm": 8.0, "rope_mbl": 33300.0, "construction": "7x19"},
            "rope-huge": {"diameter_mm": 8.0, "rope_mbl": 100000.0, "construction": "7x19"},
        },
        "sheave": {
            "Pfaff-90-4": {"model": "Pfaff DSRB 90", "wire_min_mm": 3.0, "wire_max_mm": 4.0},
            "Pfaff-185-8": {"model": "Pfaff DSRB 185/8", "wire_min_mm": 8.0, "wire_max_mm": 8.0},
            "unranged": {"model": "48 mm sheave", "wire_min_mm": None, "wire_max_mm": 16.0},
        },
        "eye_bolt": {
            "eye-M12": {"axial_newtons": 3334.0, "angled_newtons": 2353.0},
            "eye-M20": {"axial_newtons": 11768.0, "angled_newtons": 8238.0},
        },
        "turnbuckle": {
            "tb-M10": {"working_load_newtons": 1471.0},
            "tb-M20": {"working_load_newtons": 9807.0},
        },
    }


def _choices(**changes):
    choices = {"motor": "23HS45", "ratio": 20, "pulley": "Pfaff-90-4", "rope": "rope-4mm",
               "wires_per_motor": 2}
    choices.update(changes)
    return choices


def test_five_choices_make_the_whole_machine_on_the_exported_one():
    built = machine.derive(_parts(), _choices(), FACTS, 10.0)
    assert built["drive"] == "CL57T"
    assert built["gearbox"] == "EG23-G20"
    assert built["reeve_factor"] == 4                     # the export's reeving
    assert built["winding_radius_mm"] == 33.9             # the machine's, not the drum's
    assert built["groove_pitch_mm"] == pytest.approx(4.4)  # grooved for 4 mm rope
    assert built["wires_per_motor"] == 2
    assert (built["drum"], built["rail"], built["sheave"]) == ("drum-72", "MGN15H-300",
                                                             "Pfaff-90-4")


def test_without_pulleys_each_wire_runs_straight_off_its_drum():
    built = machine.derive(_parts(), _choices(pulley=None), FACTS, 10.0)
    assert built["reeve_factor"] == 1 and built["sheave"] is None


def test_no_ratio_is_direct_drive():
    assert machine.derive(_parts(), _choices(ratio=None), FACTS, 10.0)["gearbox"] == "direct"


def test_the_chain_is_the_lightest_that_holds_the_ropes_working_load():
    # 4 mm rope: 9,091 N over 5 is 1,818 N. At 10 degrees the M12 eye gives
    # 2,353 N and the M10 turnbuckle 1,471 N, so the M12 eye with the M20
    # turnbuckle (2,353 N) is the least that holds
    assert machine.lightest_chain(_parts(), "rope-4mm", 10.0) == ["eye-M12", "tb-M20"]


def test_when_no_chain_holds_the_rope_the_strongest_is_taken():
    assert machine.lightest_chain(_parts(), "rope-huge", 10.0) == ["eye-M20", "tb-M20"]


def test_a_ratio_the_frame_does_not_offer_is_refused_in_one_line():
    with pytest.raises(machine.MachineError, match=r"^NEMA 23: no 30:1$"):
        machine.derive(_parts(), _choices(ratio=30), FACTS, 10.0)


def test_a_gearbox_with_no_published_torque_is_not_offered():
    ratios = [option["ratio"] for option in machine.ratio_options(_parts(), "23HS45")]
    assert ratios == [None, 5.0, 20.0]
    with pytest.raises(machine.MachineError, match="no 10:1"):
        machine.derive(_parts(), _choices(ratio=10), FACTS, 10.0)


def test_a_wire_outside_the_pulleys_range_is_refused_in_one_line():
    with pytest.raises(machine.MachineError, match=r"^Pfaff DSRB 185/8: 8 mm wire, not 4 mm$"):
        machine.derive(_parts(), _choices(pulley="Pfaff-185-8"), FACTS, 10.0)


def test_only_pulleys_whose_maker_states_the_wire_size_are_offered():
    assert machine.pulleys_for(_parts(), "rope-4mm") == ["Pfaff-90-4"]
    assert machine.pulleys_for(_parts(), "rope-8mm") == ["Pfaff-185-8"]


def test_a_motor_with_no_frame_is_not_offered():
    assert machine.offered_motors(_parts()) == ["23HS45", "34HS59"]
    with pytest.raises(machine.MachineError, match=r"^old-34: not offered$"):
        machine.derive(_parts(), _choices(motor="old-34"), FACTS, 10.0)


@pytest.mark.parametrize("value", [0, 8, 1.5, "two"])
def test_wires_per_motor_is_one_to_seven(value):
    with pytest.raises(machine.MachineError, match="wires per motor"):
        machine.derive(_parts(), _choices(wires_per_motor=value), FACTS, 10.0)


def test_the_fewest_motors_carry_a_machines_seven_spools():
    assert [machine.motors_per_machine(n) for n in range(1, 8)] == [7, 4, 3, 2, 2, 2, 1]


def test_a_machine_with_no_winding_radius_is_refused():
    with pytest.raises(machine.MachineError, match=r"^machine: no winding radius$"):
        machine.derive(_parts(), _choices(), {"reeve_factor": 4}, 10.0)


def test_the_machine_is_named_by_its_parts_never_as_a_rig():
    parts = _parts()
    built = machine.derive(parts, _choices(), FACTS, 10.0)
    assert machine.describe(parts, built) == (
        "23HS45 on EG23 20:1, Pfaff DSRB 90 pulleys, 4 mm 7x19, two wires a motor")
    plain = machine.derive(parts, _choices(ratio=None, pulley=None, wires_per_motor=1),
                           FACTS, 10.0)
    assert machine.describe(parts, plain) == "23HS45 direct, no pulleys, 4 mm 7x19, one wire a motor"


def test_the_facts_name_each_wires_node_in_the_exports_order():
    import formwork_sim
    from test_formwork_sim import EA, _design_mm, _route_mechanism

    document = dict(_route_mechanism(), mechanism={"spoolRadius": 0.0339})
    facts = machine.facts_from(document, _design_mm(), [0, 2, 6, 8], EA)
    rim = formwork_sim.rim_wires(document, _design_mm(), [0, 2, 6, 8], EA)
    assert facts["nodes"] == [wire["node"] for wire in rim]
