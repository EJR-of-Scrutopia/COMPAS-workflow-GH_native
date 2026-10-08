from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import catalogue

TURNBUCKLE = "turnbuckle-hook-hook-M10"


def test_every_working_load_is_at_most_its_breaking_load_over_4_9():
    # steelropes24 publish the M12 eye/eye as 1000 kg against 4994 kg, a ratio
    # of 4.994: their rounding, kept as published, so the bound is 4.9.
    parts = catalogue.load_parts()
    for entry in parts["turnbuckle"].values():
        if entry.get("breaking_load_kg"):
            assert entry["breaking_load_kg"] / entry["working_load_kg"] >= 4.9


def test_the_eye_and_eye_is_six_times_the_hook_and_hook_at_the_same_thread():
    parts = catalogue.load_parts()
    hook = parts["turnbuckle"]["turnbuckle-hook-hook-M10"]["working_load_newtons"]
    eye = parts["turnbuckle"]["turnbuckle-eye-eye-M10"]["working_load_newtons"]
    assert round(hook) == 1471
    assert round(eye) == 8826
    assert eye / hook > 5.9


def test_an_eye_bolt_off_axis_takes_the_angled_rating():
    parts = catalogue.load_parts()
    chain = ["eye-M12", "turnbuckle-eye-eye-M10"]
    axial, part = catalogue.chain_limit(parts, chain, angle_degrees=2.0)
    angled, _ = catalogue.chain_limit(parts, chain, angle_degrees=30.0)
    assert round(axial) == 3334 and part == "eye-M12"
    assert round(angled) == 2354
    with pytest.raises(catalogue.CatalogueError, match="45"):
        catalogue.chain_limit(parts, chain, angle_degrees=50.0)
    with pytest.raises(catalogue.CatalogueError, match="45"):
        catalogue.chain_limit(parts, chain, angle_degrees=-1.0)


def test_the_chain_limit_is_the_weakest_part_whatever_the_order():
    parts = catalogue.load_parts()
    a, part_a = catalogue.chain_limit(
        parts, ["eye-M12", "turnbuckle-hook-hook-M10"], angle_degrees=2.0)
    b, part_b = catalogue.chain_limit(
        parts, ["turnbuckle-hook-hook-M10", "eye-M12"], angle_degrees=2.0)
    assert a == b and part_a == part_b == "turnbuckle-hook-hook-M10"
    assert round(a) == 1471


def test_a_motor_and_drive_from_different_families_are_refused():
    parts = catalogue.load_parts()
    good = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rope="rope-4mm", chain=["eye-M12", "turnbuckle-hook-hook-M10"],
                sheave=None, rail="MGN15H-300", reeve_factor=1)
    catalogue.mechanism_for(parts, good, angle_degrees=10.0)
    bad = dict(good, drive="vfd-1ph-in")
    with pytest.raises(catalogue.CatalogueError, match="family") as raised:
        catalogue.mechanism_for(parts, bad, angle_degrees=10.0)
    assert "family A" in str(raised.value) and "family B" in str(raised.value)


def test_a_family_c_motor_is_refused_with_the_capacitor_reason():
    parts = catalogue.load_parts()
    configuration = dict(motor="boatlift-1hp", drive="none", gearbox="worm-50",
                         drum="drum-72", rope="rope-4mm",
                         chain=["eye-M12", "turnbuckle-eye-eye-M10"],
                         sheave=None, rail="MGN15H-300", reeve_factor=1)
    with pytest.raises(catalogue.CatalogueError, match="capacitor"):
        catalogue.mechanism_for(parts, configuration, angle_degrees=10.0)


def test_the_family_torque_uses_the_speed_for_that_family():
    parts = catalogue.load_parts()
    assert round(parts["motor"]["ac-0r75-3ph"]["motor_torque"]) == 4974
    assert round(parts["motor"]["ac-1r5-3ph"]["motor_torque"]) == 9948
    assert round(parts["motor"]["boatlift-1hp"]["motor_torque"]) == 4128
    assert parts["motor"]["34HS46"]["motor_torque"] == 9000.0
    assert parts["motor"]["34HS46"]["torque_margin"] == 0.5
    assert parts["motor"]["ac-0r75-3ph"]["torque_margin"] == 0.8


def test_the_worked_ceiling_rows_come_out_as_the_spec_says():
    parts = catalogue.load_parts()
    base = dict(drum="drum-72", rope="rope-4mm", rail="MGN15H-300",
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    rows = [
        (dict(base, motor="34HS46", drive="CL86Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 1471, TURNBUCKLE),
        (dict(base, motor="34HS46", drive="CL86Y", gearbox="EG23-G20",
              sheave="WZ-11-K", reeve_factor=2), 1214, "sheave"),
        (dict(base, motor="34HS31", drive="CL86Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 1123, "motor torque"),
        (dict(base, motor="23HS45", drive="CL57Y", gearbox="EG23-G20",
              sheave=None, reeve_factor=1), 783, "motor torque"),
    ]
    for configuration, expected, binding in rows:
        ceiling, part = catalogue.ceiling_for(parts, configuration, angle_degrees=2.0)
        assert round(ceiling) == expected, configuration["motor"]
        assert part == binding


def test_the_upgrade_ladder_reaches_the_spec_figures():
    parts = catalogue.load_parts()
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rail="MGN15H-300", sheave=None, reeve_factor=1)
    steps = [
        (dict(base, rope="rope-4mm",
              chain=["eye-M12", "turnbuckle-hook-hook-M10"]), 1471, TURNBUCKLE),
        (dict(base, rope="rope-4mm",
              chain=["eye-M12", "turnbuckle-eye-eye-M10"]), 1818, "rope tension"),
        (dict(base, rope="rope-5mm",
              chain=["eye-M12", "turnbuckle-eye-eye-M10"]), 2350, "motor torque"),
    ]
    for configuration, expected, binding in steps:
        ceiling, part = catalogue.ceiling_for(parts, configuration, angle_degrees=2.0)
        assert round(ceiling) == expected
        assert part == binding


def test_the_pulley_caps_every_rung_of_the_ladder():
    parts = catalogue.load_parts()
    base = dict(motor="34HS46", drive="CL86Y", gearbox="EG23-G20", drum="drum-72",
                rail="MGN15H-300", sheave="WZ-11-K", reeve_factor=2)
    for rope, chain in (
        ("rope-4mm", ["eye-M12", "turnbuckle-hook-hook-M10"]),
        ("rope-5mm", ["eye-M12", "turnbuckle-eye-eye-M10"]),
        ("rope-8mm", ["eye-M20", "turnbuckle-eye-eye-M12"]),
    ):
        ceiling, part = catalogue.ceiling_for(
            parts, dict(base, rope=rope, chain=chain), angle_degrees=2.0)
        assert round(ceiling) == 1214
        assert part == "sheave"


def test_an_unpriced_line_keeps_the_total_a_floor():
    parts = catalogue.load_parts()
    configuration = dict(motor="34HS46", drive="CL86Y", gearbox="EG34-G100",
                         drum="drum-72", rope="rope-4mm", rail="MGN15H-300",
                         chain=["eye-M12", "turnbuckle-eye-eye-M10"],
                         sheave=None, reeve_factor=1)
    total = catalogue.price_of(parts, configuration)
    assert total["is_floor"] is True
    assert total["unpriced"]          # the EG34 carries no price
    assert total["pounds"] > 0.0


def test_importing_the_catalogue_loads_no_solver_stack():
    # A clean interpreter: in this process another test has already imported
    # numpy, so only a subprocess can show the catalogue does not pull it in.
    import subprocess

    script = """
import sys
sys.path.insert(0, {studio!r})
import catalogue
bad = [m for m in ("numpy", "scipy", "compas", "compas_fd") if m in sys.modules]
assert not bad, bad
print("clean")
""".format(studio=str(Path(catalogue.__file__).resolve().parent))
    done = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "clean"


REEVED_NO_SHEAVE = dict(
    motor="23HS45", drive="CL57Y", gearbox="EG23-G20", drum="drum-72",
    rope="rope-8mm", rail="MGN15H-300",
    chain=["eye-M20", "turnbuckle-eye-eye-M12"], sheave=None, reeve_factor=2)


def test_a_reeving_with_no_sheave_named_is_refused():
    parts = catalogue.load_parts()
    with pytest.raises(catalogue.CatalogueError, match="sheave") as raised:
        catalogue.mechanism_for(parts, REEVED_NO_SHEAVE, angle_degrees=2.0)
    assert "doubles the force" in str(raised.value)


def test_the_unchecked_reeved_motor_torque_answer_is_unreachable():
    parts = catalogue.load_parts()
    with pytest.raises(catalogue.CatalogueError):
        catalogue.ceiling_for(parts, REEVED_NO_SHEAVE, angle_degrees=2.0)
    named, binding = catalogue.ceiling_for(
        parts, dict(REEVED_NO_SHEAVE, sheave="WZ-11-K"), angle_degrees=2.0)
    assert round(named) == 1214 and binding == "sheave"


def test_the_briefed_drum_holds_37_wraps_which_is_8369_mm():
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="WZ-11-K", rope="rope-4mm")
    fits = catalogue.drum_and_travel(parts, configuration, 8000.0)
    assert fits["drum_capacity_wraps"] == 37
    assert round(fits["drum_capacity_mm"]) == 8369
    assert fits["drum_fits"] is True
    assert fits["carriage_travel_mm"] == 4000.0 and fits["rail_fits"] is False
    over = catalogue.drum_and_travel(parts, configuration, 8400.0)
    assert over["drum_fits"] is False


def test_the_carriage_travel_is_checked_against_the_stroke():
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="WZ-11-K", rope="rope-4mm")
    ok = catalogue.drum_and_travel(parts, configuration, 600.0)
    assert ok["carriage_travel_mm"] == 300.0 and ok["rail_fits"] is True
    no = catalogue.drum_and_travel(parts, configuration, 601.0)
    assert no["rail_fits"] is False


def test_the_sheave_to_rope_ratio_is_a_number_with_no_verdict():
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="WZ-11-K", rope="rope-4mm")
    result = catalogue.drum_and_travel(parts, configuration, 100.0)
    assert result["sheave_over_rope_diameter"] == 30.0
    assert not any("verdict" in k or "ok" == k for k in result)


def _demand(t1=500.0, sag=1.0, acceptance=2.18, load=66890.0):
    return {"acceptance": acceptance,
            "sizing": {"stage": "S7", "worst_wire_tension_newtons": t1,
                       "worst_actuator_newtons": 0.0, "worst_sag_mm": sag,
                       "load_newtons": load}}


def test_every_configuration_in_the_catalogue_is_buildable_and_described():
    parts = catalogue.load_parts()
    keys = list(catalogue.configurations(parts))
    assert len(keys) >= 6
    for key in keys:
        entry = parts["configurations"][key]
        assert entry["name"] and entry["for"]
        configuration = catalogue.configuration_of(parts, key)
        for field in ("motor", "drive", "gearbox", "drum", "rope", "rail", "chain", "reeve_factor"):
            assert field in configuration, (key, field)
        catalogue.mechanism_for(parts, configuration, 10.0)
        assert configuration["drive"] == catalogue.drive_for(parts, configuration["motor"])
        assert configuration["gearbox"] in catalogue.gearboxes_for(parts, configuration["motor"])
    with pytest.raises(catalogue.CatalogueError, match="no configuration"):
        catalogue.configuration_of(parts, "not-a-rig")


def test_the_drive_follows_the_motor_by_family():
    parts = catalogue.load_parts()
    for key, motor in parts["motor"].items():
        drive = catalogue.drive_for(parts, key)
        assert parts["drive"][drive]["family"] == motor["family"], key
    assert catalogue.drive_for(parts, "23HS45") == "CL57Y"
    assert catalogue.drive_for(parts, "34HS46") == "CL86Y"
    assert catalogue.drive_for(parts, "ac-1r1-3ph") == "vfd-1ph-in"
    with pytest.raises(catalogue.CatalogueError):
        catalogue.drive_for(parts, "not-a-motor")


def test_gearboxes_are_offered_by_family_and_a_capacitor_motor_is_refused():
    parts = catalogue.load_parts()
    stepper = catalogue.gearboxes_for(parts, "34HS46")
    assert "EG23-G20" in stepper and "direct" in stepper and "worm-20" not in stepper
    inverter = catalogue.gearboxes_for(parts, "ac-1r1-3ph")
    assert "worm-20" in inverter and "EG23-G20" not in inverter
    with pytest.raises(catalogue.CatalogueError, match="single-phase"):
        catalogue.gearboxes_for(parts, "boatlift-1hp")


def test_part_count_counts_real_parts_and_part_for_term_names_them():
    configuration = {"motor": "34HS46", "drive": "CL86Y", "gearbox": "EG23-G20",
                     "drum": "drum-72", "rope": "rope-4mm", "rail": "MGN15H-300",
                     "sheave": None, "reeve_factor": 1,
                     "chain": ["eye-M12", TURNBUCKLE]}
    assert catalogue.part_count(configuration) == 8
    assert catalogue.part_count({**configuration, "sheave": "WZ-11-K", "reeve_factor": 2}) == 9
    assert catalogue.part_count({**configuration, "gearbox": "direct", "drive": "none"}) == 6
    assert catalogue.part_for_term(configuration, "motor torque") == "34HS46"
    assert catalogue.part_for_term(configuration, "rope tension") == "rope-4mm"
    assert catalogue.part_for_term(configuration, "spool rope tension") == "rope-4mm"
    assert catalogue.part_for_term({**configuration, "spool_rope": "rope-5mm"},
                                   "spool rope tension") == "rope-5mm"
    assert catalogue.part_for_term(configuration, "sheave") is None
    assert catalogue.part_for_term(configuration, "deviation") == "shape"
    assert catalogue.part_for_term(configuration, "anchor") is None
    assert catalogue.part_for_term(configuration, "none") is None


def test_the_load_factor_is_the_capacity_walk_over_the_scaled_fit():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    # the hook-and-hook turnbuckle's 1471 N against 500 N per unit skin:
    # 2.9 passes (1450), 3.0 breaches (1500), the anchor binds
    assert factor["limit_factor"] == pytest.approx(2.9)
    assert factor["breaching_factor"] == pytest.approx(3.0)
    assert factor["binding"] == "anchor"
    assert factor["binding_part"] == TURNBUCKLE
    assert round(factor["ceiling_newtons"]) == 1471
    assert factor["margin"] == pytest.approx(1471.0 / 500.0, rel=1e-3)
    assert factor["sufficient"] is True
    assert factor["skin_newtons"] == 66890.0 and factor["stage"] == "S7"
    assert factor["acceptance_mm"] == 2.18


def test_the_load_factor_judges_the_wires_at_no_less_than_the_entered_prestress():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    # as the engine writes it on the real study: the fit found 14.6 N in its worst
    # wire, the study entered 300 N, and the wires are judged at the larger
    demand = {"acceptance": 3.25, "prestress": 300.0,
              "sizing": {"stage": "S17", "worst_wire_tension_newtons": 300.0,
                         "fitted_wire_tension_newtons": 14.6, "prestress_newtons": 300.0,
                         "worst_actuator_newtons": 435.1, "worst_sag_mm": 1.0,
                         "load_newtons": 67459.0}}
    factor = catalogue.load_factor(parts, configuration, 10.0, demand)
    assert factor["worst_wire_tension_newtons"] == 300.0
    # the hook-and-hook turnbuckle's 1471 N against 300 N: 4.9 passes, 5.0 breaches
    assert factor["limit_factor"] == pytest.approx(4.9)
    assert factor["breaching_factor"] == pytest.approx(5.0)
    assert factor["margin"] == pytest.approx(1471.0 / 300.0, rel=1e-3)
    # a block written before the two figures carries the fit's alone, and is read by
    # the same rule against the prestress the document records
    older = {**demand, "sizing": {"stage": "S17", "worst_wire_tension_newtons": 14.6,
                                  "worst_actuator_newtons": 435.1, "worst_sag_mm": 1.0,
                                  "load_newtons": 67459.0}}
    assert catalogue.wire_floor(older) == {"newtons": 300.0, "fitted_newtons": 14.6,
                                           "prestress_newtons": 300.0}
    assert catalogue.load_factor(parts, configuration, 10.0, older)[
        "worst_wire_tension_newtons"] == 300.0
    # with no prestress recorded the fit's figure is all there is
    assert catalogue.load_factor(parts, configuration, 10.0, {**older, "prestress": None})[
        "worst_wire_tension_newtons"] == 14.6


def test_the_floor_reads_the_engines_figure_and_works_out_an_older_documents_by_its_rule():
    engine = {"prestress": 300.0, "sizing": {"worst_wire_tension_newtons": 900.0,
                                             "fitted_wire_tension_newtons": 900.0,
                                             "prestress_newtons": 300.0}}
    assert catalogue.wire_floor(engine) == {"newtons": 900.0, "fitted_newtons": 900.0,
                                            "prestress_newtons": 300.0}
    # the engine's three figures are read, never worked out again
    hand = {"prestress": 300.0, "sizing": {"worst_wire_tension_newtons": 50.0,
                                           "fitted_wire_tension_newtons": 900.0,
                                           "prestress_newtons": 300.0}}
    assert catalogue.wire_floor(hand)["newtons"] == 50.0
    # no block: the wires stage by stage, against the prestress where it is recorded
    stages = [{"wire_tensions": [100.0, 700.0]}, {"wire_tensions": [300.0, "x", None, True]}]
    assert catalogue.wire_floor({"stages": stages}) == {
        "newtons": 700.0, "fitted_newtons": 700.0, "prestress_newtons": None}
    assert catalogue.wire_floor({"prestress": 1000.0, "stages": stages})["newtons"] == 1000.0
    assert catalogue.wire_floor({"prestress": 1000.0, "stages": []}) == {
        "newtons": 1000.0, "fitted_newtons": None, "prestress_newtons": 1000.0}
    # a block with no figure for the wires falls to the stages
    assert catalogue.wire_floor({"sizing": {"worst_wire_tension_newtons": None},
                                 "stages": stages})["newtons"] == 700.0
    for nothing in (None, {}, {"stages": "x"}, {"prestress": "300", "stages": [5]}):
        assert catalogue.wire_floor(nothing)["newtons"] is None, nothing


def test_a_sag_past_the_line_binds_on_the_shape_at_the_first_rung():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(sag=10.0))
    assert factor["limit_factor"] == 0.0
    assert factor["binding"] == "deviation" and factor["binding_part"] == "shape"
    assert factor["sufficient"] is False


def test_no_acceptance_line_judges_the_parts_alone():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0,
                                   _demand(sag=10.0, acceptance=None))
    assert factor["binding"] == "anchor" and factor["acceptance_mm"] is None


def test_a_demand_without_sizing_gives_no_load_factor():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    assert catalogue.load_factor(parts, configuration, 10.0, {"stages": []}) is None
    assert catalogue.load_factor(parts, configuration, 10.0, None) is None
    assert catalogue.sizing_of({"sizing": None}) is None


def test_recommend_takes_the_largest_margin_then_the_fewest_parts_then_the_first_listed():
    parts = catalogue.load_parts()
    base = catalogue.configuration_of(parts, "stepper-seven-spool")
    # an identical rig with a named spool rope: the same ceiling, one more part
    parts["configurations"] = {
        "b-more-parts": {"name": "B", "for": "nine parts",
                         "parts": {**base, "spool_rope": "rope-4mm"}},
        "a-fewer-parts": {"name": "A", "for": "eight parts", "parts": dict(base)},
        "c-same-again": {"name": "C", "for": "eight parts too", "parts": dict(base)},
    }
    result = catalogue.recommend(parts, 10.0, _demand())
    assert result["key"] == "a-fewer-parts"
    assert result["sufficient"] is True
    assert "fewest parts" in result["rule"] and "the largest margin" in result["rule"]
    assert [row["key"] for row in result["rows"]] == ["b-more-parts", "a-fewer-parts", "c-same-again"]
    assert all(row["load_factor"]["limit_factor"] == pytest.approx(2.9) for row in result["rows"])


def test_recommend_says_plainly_when_nothing_carries_the_skin():
    parts = catalogue.load_parts()
    result = catalogue.recommend(parts, 10.0, _demand(t1=100000.0))
    assert result["sufficient"] is False
    assert "nothing in the catalogue carries" in result["rule"]
    best = max((r for r in result["rows"] if r.get("load_factor")),
               key=lambda r: r["load_factor"]["limit_factor"])
    assert result["key"] == best["key"]


def test_recommend_without_a_demand_ranks_by_ceiling_and_says_so():
    parts = catalogue.load_parts()
    result = catalogue.recommend(parts, 10.0, None)
    assert result["sufficient"] is None
    assert "ceiling" in result["rule"] and "run the cable net analysis" in result["rule"]
    best = max(result["rows"], key=lambda r: r["ceiling"])
    assert result["key"] == best["key"]
    stale = catalogue.recommend(parts, 10.0, {"schema": "bench.cablenet/1", "stages": []})
    assert stale["sufficient"] is None and "sizing" in stale["rule"]


def test_a_designed_rig_that_cannot_be_built_fails_at_load_naming_it_and_the_part(tmp_path):
    import json

    source = json.loads(catalogue.PARTS_PATH.read_text(encoding="utf-8"))

    def load_with(change):
        document = json.loads(json.dumps(source))
        change(document)
        path = tmp_path / "parts.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return catalogue.load_parts(path)

    def drawn_rig(document):
        return document["configurations"]["stepper-seven-spool"]["parts"]

    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*EG99"):
        load_with(lambda d: drawn_rig(d).update(gearbox="EG99"))
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*names no drum"):
        load_with(lambda d: drawn_rig(d).pop("drum"))
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*names no parts"):
        load_with(lambda d: d["configurations"]["stepper-seven-spool"].pop("parts"))
    # a motor whose drive is not in the catalogue is caught through the rig that uses it
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*34HS46.*no drive"):
        load_with(lambda d: d["motor"]["34HS46"].update(drive="CL99"))
    # a motor paired with a drive of another family cannot run it
    with pytest.raises(catalogue.CatalogueError, match="stepper-seven-spool.*different family"):
        load_with(lambda d: d["motor"]["34HS46"].update(drive="vfd-1ph-in"))
    # and a catalogue with no designed rigs still loads
    assert load_with(lambda d: d.pop("configurations"))["motor"]


def test_a_rig_is_sufficient_when_it_carries_exactly_the_sizing_stages_load():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    ceiling, _ = catalogue.ceiling_for(parts, configuration, 10.0)
    exact = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=ceiling))
    assert exact["limit_factor"] == pytest.approx(1.0) and exact["sufficient"] is True
    over = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=ceiling * 1.001))
    assert over["limit_factor"] == pytest.approx(0.9) and over["sufficient"] is False


def test_a_net_with_no_tension_at_the_sizing_stage_has_nothing_to_scale():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=0.0))
    assert factor["limit_factor"] is None and factor["sufficient"] is None
    assert factor["binding"] == "none" and factor["binding_part"] is None
    assert factor["margin"] is None and "nothing to scale" in factor["detail"]
    assert round(factor["ceiling_newtons"]) == 1471
    # no rig has a load factor, so Recommend falls back to the ceiling and says so
    result = catalogue.recommend(parts, 10.0, _demand(t1=0.0))
    assert result["sufficient"] is None and "ceiling" in result["rule"]


def test_a_sizing_that_is_not_a_block_is_no_sizing():
    for odd in (None, "S7", [], 0, 4.2):
        assert catalogue.sizing_of({"sizing": odd}) is None
    block = {"stage": "S7"}
    assert catalogue.sizing_of({"sizing": block}) is block


def test_when_two_terms_breach_on_one_rung_the_load_factor_names_the_ceilings_own_part():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-eye-eye")
    ceiling, named = catalogue.ceiling_for(parts, configuration, 10.0)
    # The motor allows 2350 N and the M12 eye bolt 2353.6 N. The walk's rungs are
    # 0.1 wide, so both are past their limit at 4.8 (2400 N), and checks() alone
    # names the eye bolt because it tests the anchor first. The ceiling line says
    # the motor, so the load factor says the motor too.
    assert round(ceiling, 1) == 2350.0 and named == "motor torque"
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    assert factor["limit_factor"] == pytest.approx(4.7)
    assert factor["breaching_factor"] == pytest.approx(4.8)
    assert factor["binding"] == "motor torque"
    assert factor["binding_part"] == "34HS46"
    # and the sentence beside it is the motor's, not the eye bolt's
    assert "N mm" in factor["detail"] and "working load" not in factor["detail"]


# a phrase that only each part term's own sentence carries (mechanism.checks words them)
_TERM_WORDS = {"rope tension": "net cable", "anchor": "N working load",
               "spool rope tension": "spool rope", "sheave": "moving block",
               "motor torque": "N mm"}


def test_the_load_factor_and_the_ceiling_line_never_name_different_parts():
    parts = catalogue.load_parts()
    seen = set()
    for key in catalogue.configurations(parts):
        configuration = catalogue.configuration_of(parts, key)
        ceiling, named = catalogue.ceiling_for(parts, configuration, 10.0)
        # from a skin far lighter than any rig's ceiling to one far past every rig's,
        # so the first rung to breach is cleared by one term, by several, by all
        for t1 in [5.0 * 1.25 ** step for step in range(50)]:
            factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=t1))
            if factor["binding"] in ("none", "deviation"):
                continue
            seen.add(factor["binding"])
            # ceiling_for names the chain part for the anchor and the term otherwise
            if factor["binding"] == "anchor":
                assert factor["binding_part"] == named, (key, t1)
            else:
                assert factor["binding"] == named, (key, t1)
                assert factor["binding_part"] == catalogue.part_for_term(
                    configuration, named), (key, t1)
            assert _TERM_WORDS[factor["binding"]] in factor["detail"], (key, t1)
            # the walk resolves a rung, so the true limit lies between the two it reports
            assert factor["limit_factor"] <= factor["margin"] * (1 + 1e-9), (key, t1)
            assert factor["breaching_factor"] >= factor["margin"] * (1 - 1e-9), (key, t1)
    assert {"anchor", "rope tension", "sheave", "motor torque"} <= seen


@pytest.mark.parametrize("disagreement", [{"binding": "anchor"}, {"breaching_factor": 99.0}],
                         ids=["another term", "another rung"])
def test_the_ceilings_term_is_named_even_when_its_own_wording_cannot_be_had(
        monkeypatch, disagreement):
    real = catalogue.capacity_from_curve

    def walk_with_the_earlier_terms_lifted_disagrees(mechanism, curve, acceptance):
        result = real(mechanism, curve, acceptance)
        if mechanism.anchor_wll > 1e100:
            return result._replace(**disagreement)
        return result

    monkeypatch.setattr(catalogue, "capacity_from_curve",
                        walk_with_the_earlier_terms_lifted_disagrees)
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-eye-eye")
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    # the part is the ceiling's whatever happens; the walk's own sentence stands
    assert factor["binding"] == "motor torque" and factor["binding_part"] == "34HS46"
    assert factor["limit_factor"] == pytest.approx(4.7)
    assert "N working load" in factor["detail"]


def test_lifting_a_term_moves_that_terms_limit_and_nothing_else():
    parts = catalogue.load_parts()
    configuration = catalogue.configuration_of(parts, "stepper-seven-spool-block")
    mechanism = catalogue.mechanism_for(parts, configuration, 10.0)
    for name, field in (("rope tension", "rope_mbl"), ("anchor", "anchor_wll"),
                        ("spool rope tension", "spool_rope_mbl"), ("sheave", "sheave_swl")):
        lifted = catalogue._with_terms_lifted(mechanism, [name])
        moved = {f for f in mechanism._fields if getattr(lifted, f) != getattr(mechanism, f)}
        assert moved == {field}, name
    # a spool rope that defaults to the net rope keeps the rope it was when the net rope is lifted
    defaulted = mechanism._replace(spool_rope_mbl=None)
    lifted = catalogue._with_terms_lifted(defaulted, ["rope tension"])
    assert lifted.rope_mbl > 1e100 and lifted.spool_rope_mbl == defaulted.rope_mbl


def test_recommend_says_why_there_is_no_demand_when_it_is_told():
    parts = catalogue.load_parts()
    reason = "There is no export named 'x', so no cable net demand has been written for it."
    told = catalogue.recommend(parts, 10.0, None, reason=reason)
    assert told["sufficient"] is None
    assert told["rule"].startswith("no demand document: There is no export named 'x'")
    assert "ceiling" in told["rule"] and "no sizing in the demand document" not in told["rule"]
    assert ".;" not in told["rule"]
    assert told["key"] == max(told["rows"], key=lambda r: r["ceiling"])["key"]
    # a document that exists without a sizing block keeps its own sentence, whatever
    # reason is passed with it
    stale = catalogue.recommend(parts, 10.0, {"stages": []}, reason=reason)
    assert stale["rule"].startswith("no sizing in the demand document")
    assert "run the cable net analysis" in stale["rule"]
    # and a block with no tension in it is neither of those
    quiet = catalogue.recommend(parts, 10.0, _demand(t1=0.0), reason=reason)
    assert "carries no wire tension" in quiet["rule"] and "ceiling" in quiet["rule"]
    assert "no sizing in" not in quiet["rule"] and "no demand document" not in quiet["rule"]


def test_recommend_blames_the_shape_and_ranks_by_the_parts_when_the_sag_is_past_the_line():
    parts = catalogue.load_parts()
    demand = _demand(sag=10.0)
    result = catalogue.recommend(parts, 10.0, demand)
    assert result["sufficient"] is False
    assert "shape" in result["rule"] and "acceptance line at the sizing stage" in result["rule"]
    assert "no part can change it" in result["rule"]
    assert "nothing in the catalogue carries" not in result["rule"]
    # judged on the shape every rig stops at the first rung; with the shape set aside
    # the parts alone tell them apart
    for row in result["rows"]:
        assert row["load_factor"]["binding"] == "deviation"
        assert row["load_factor"]["limit_factor"] == 0.0
        alone = catalogue.load_factor(parts, catalogue.configuration_of(parts, row["key"]),
                                      10.0, _demand(sag=10.0, acceptance=None))
        assert row["parts_factor"] == alone
    assert max(row["parts_factor"]["limit_factor"] for row in result["rows"]) > 0.0
    largest = max(row["parts_factor"]["margin"] for row in result["rows"])
    chosen = next(row for row in result["rows"] if row["key"] == result["key"])
    assert chosen["parts_factor"]["margin"] == largest
    assert "the largest margin" in result["rule"]
    # ties on what the parts carry go to the fewest parts, then the first listed
    tied = [row for row in result["rows"] if row["parts_factor"]["margin"] == largest]
    assert result["key"] == min(tied, key=lambda r: (r["parts"], r["position"]))["key"]


def test_recommend_decides_the_shape_from_the_document_not_from_how_the_rigs_bind():
    parts = catalogue.load_parts()
    # The sag is past the line and the skin is heavy enough that the lighter rigs
    # are stopped by their parts on the first rung as well. The shape is past the
    # line whatever the parts do, so the rule names it and the rigs are ranked by
    # what their parts alone carry.
    result = catalogue.recommend(parts, 10.0, _demand(t1=15000.0, sag=10.0))
    bindings = {row["key"]: row["load_factor"]["binding"] for row in result["rows"]}
    assert "deviation" in bindings.values() and set(bindings.values()) != {"deviation"}
    assert result["sufficient"] is False
    assert "shape" in result["rule"] and "no part can change it" in result["rule"]
    assert "nothing in the catalogue carries" not in result["rule"]
    # the heavy skin shows in the parts factors, which are low, and the best is chosen
    factors = {row["key"]: row["parts_factor"]["limit_factor"] for row in result["rows"]}
    assert all(0.0 <= value < 1.0 for value in factors.values())
    assert max(factors.values()) > 0.0
    margins = {row["key"]: row["parts_factor"]["margin"] for row in result["rows"]}
    largest = max(margins.values())
    assert margins[result["key"]] == largest
    tied = [row for row in result["rows"] if row["parts_factor"]["margin"] == largest]
    assert result["key"] == min(tied, key=lambda r: (r["parts"], r["position"]))["key"]


def _real_scale(sag):
    """The real study as the engine now sizes it: the wires judged at the 300 N
    entered (the fit found 14.6 N), the glulam rib's 3.25 mm line, a 67.5 kN skin."""

    return {"acceptance": 3.25, "prestress": 300.0,
            "sizing": {"stage": "S17", "worst_wire_tension_newtons": 300.0,
                       "fitted_wire_tension_newtons": 14.6, "prestress_newtons": 300.0,
                       "worst_actuator_newtons": 435.1, "worst_sag_mm": sag,
                       "load_newtons": 67459.0}}


def test_the_shipped_catalogue_recommends_its_largest_margin_at_real_scale():
    parts = catalogue.load_parts()
    # inside the line every rig carries the skin and is judged as it is; past the
    # line (the real study's 12.3 mm) the parts alone are ranked
    for sag, judged, sufficient in ((1.0, "load_factor", True), (12.3, "parts_factor", False)):
        result = catalogue.recommend(parts, 10.0, _real_scale(sag))
        assert result["sufficient"] is sufficient, sag
        assert "the largest margin, the ceiling over the tension the wires are judged at" in (
            result["rule"]), sag
        rows = [row for row in result["rows"] if not row.get("refused")]
        assert len(rows) == len(result["rows"]) >= 6
        margins = {row["key"]: row[judged]["margin"] for row in rows}
        for row in rows:
            assert row[judged]["worst_wire_tension_newtons"] == 300.0
            assert row[judged]["margin"] == pytest.approx(row["ceiling"] / 300.0)
        largest = max(margins.values())
        assert margins[result["key"]] == largest, sag
        # the largest is not shared with the weaker rigs, and among equals the rule's
        # own order decides
        assert sum(1 for value in margins.values() if value == largest) < len(margins)
        tied = [row for row in rows if margins[row["key"]] == largest]
        assert result["key"] == min(tied, key=lambda r: (r["parts"], r["position"]))["key"]


def test_rigs_that_all_reach_the_cap_are_still_ranked_by_their_margin():
    import exports
    parts = catalogue.load_parts()
    # the fit's own 14.6 N, which the real study was judged at before the floor rule:
    # every rig reaches the walk's cap of 20 and its load factor ties with the rest
    result = catalogue.recommend(parts, 10.0, _demand(t1=14.6, sag=1.0, acceptance=3.25))
    rows = {row["key"]: row for row in result["rows"]}
    assert {row["load_factor"]["limit_factor"] for row in rows.values()} == {20.0}
    assert all(row["load_factor"]["breaching_factor"] is None for row in rows.values())
    # the rigs that carry 7.5 times a 500 N wire no longer tie with those that carry 2.9
    at_500 = {key: catalogue.load_factor(parts, catalogue.configuration_of(parts, key), 10.0,
                                         _demand())["limit_factor"] for key in rows}
    strong = [key for key, value in at_500.items() if value == pytest.approx(7.5)]
    weak = [key for key, value in at_500.items() if value == pytest.approx(2.9)]
    assert len(strong) == 2 and len(weak) == 2
    assert (min(rows[key]["load_factor"]["margin"] for key in strong)
            > max(rows[key]["load_factor"]["margin"] for key in weak))
    assert result["key"] in strong
    # the factor keeps its cap, and the sentence says it is a floor
    chosen = rows[result["key"]]["load_factor"]
    assert exports.load_factor_sentence({"capacity": chosen}) == (
        "Carries at least 20.0 times the 66.9 kN skin: nothing binds up to that load.")


def test_the_shape_rule_needs_a_line_and_a_sag_past_it():
    parts = catalogue.load_parts()
    line = 2.18
    # a sag exactly on the line is inside it, as checks() has it, and a hair over is not
    on = catalogue.recommend(parts, 10.0, _demand(sag=line, acceptance=line))
    assert on["sufficient"] is True and "shape" not in on["rule"]
    over = catalogue.recommend(parts, 10.0, _demand(sag=line + 0.01, acceptance=line))
    assert over["sufficient"] is False and "shape is past the acceptance line" in over["rule"]
    # with no line there is nothing for the shape to be past: the parts are judged alone
    unlined = catalogue.recommend(parts, 10.0, _demand(sag=10.0, acceptance=None))
    assert unlined["sufficient"] is True and "shape" not in unlined["rule"]
    assert all("parts_factor" not in row for row in unlined["rows"])
    # inside the line and no rig carries the load: it is the parts that fall short
    heavy = catalogue.recommend(parts, 10.0, _demand(t1=100000.0, sag=1.0))
    assert heavy["sufficient"] is False and "nothing in the catalogue carries" in heavy["rule"]
    assert "shape" not in heavy["rule"]
    assert all("parts_factor" not in row for row in heavy["rows"])


def test_the_pairing_block_is_the_catalogue_functions_precomputed():
    parts = catalogue.load_parts()
    pairing = parts["pairing"]
    for key in parts["motor"]:
        assert pairing["drive_for"][key] == catalogue.drive_for(parts, key)
    assert pairing["gearboxes_for"]["34HS46"] == catalogue.gearboxes_for(parts, "34HS46")
    assert pairing["gearboxes_for"]["ac-1r1-3ph"] == catalogue.gearboxes_for(parts, "ac-1r1-3ph")
    assert pairing["gearboxes_for"]["boatlift-1hp"] == []
