from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bench" / "studio"))

import catalogue

TURNBUCKLE = "turnbuckle-hook-hook-M10"

# The closed-loop NEMA 34 on its 20:1 planetary, the workshop drum and rail, a
# 4 mm rope and the M12 eye with the M10 hook-and-hook: a machine the five
# choices can make, with the chain held as the anchor tests need it.
SEVEN_SPOOL = dict(motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
                   drum="drum-72", rope="rope-4mm", rail="MGN15H-300", sheave=None,
                   reeve_factor=1, chain=["eye-M12", TURNBUCKLE])
# the same on two falls through a 120 mm GPS block
BLOCK = dict(SEVEN_SPOOL, sheave="GPS-WZ11K", reeve_factor=2)
# a 5 mm rope with the eye-and-eye turnbuckle: the motor binds
EYE_EYE = dict(SEVEN_SPOOL, rope="rope-5mm", chain=["eye-M12", "turnbuckle-eye-eye-M10"])
# a 12 N m motor on a 50:1 planetary: the gearbox binds
HEAVY = dict(SEVEN_SPOOL, motor="34HS59-6004D-E1000", gearbox="EG34-G50", rope="rope-6mm",
             chain=["eye-M16", "turnbuckle-eye-eye-M12"])


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
    catalogue.mechanism_for(parts, SEVEN_SPOOL, angle_degrees=10.0)
    bad = dict(SEVEN_SPOOL, drive="A6-400RS")
    with pytest.raises(catalogue.CatalogueError, match="family") as raised:
        catalogue.mechanism_for(parts, bad, angle_degrees=10.0)
    assert "family A" in str(raised.value) and "family S" in str(raised.value)






def test_the_worked_ceiling_rows_come_out_as_the_spec_says():
    parts = catalogue.load_parts()
    base = dict(drum="drum-72", rope="rope-4mm", rail="MGN15H-300",
                chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    # the block: 125 kg x 9.80665 x (1 + 0.95) / 2 = 1195.2 N; the 23HS45:
    # 3000 N mm x 20 x 0.94 x 0.5 / 36 mm = 783.3 N, under its gearbox's 833.3 N
    rows = [
        (dict(base, motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
              sheave=None, reeve_factor=1), 1471, TURNBUCKLE),
        (dict(base, motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
              sheave="GPS-WZ11K", reeve_factor=2), 1195, "sheave"),
        (dict(base, motor="34HS31-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
              sheave=None, reeve_factor=1), 1123, "motor torque"),
        (dict(base, motor="23HS45-4204D-E1000", drive="CL57T-V41", gearbox="EG23-G20-D8",
              sheave=None, reeve_factor=1), 783, "motor torque"),
    ]
    for configuration, expected, binding in rows:
        ceiling, part = catalogue.ceiling_for(parts, configuration, angle_degrees=2.0)
        assert round(ceiling) == expected, configuration["motor"]
        assert part == binding


def test_the_upgrade_ladder_reaches_the_spec_figures():
    parts = catalogue.load_parts()
    base = dict(motor="34HS46-6004D-E1000", drive="CL86T-V41", gearbox="EG34-G20",
                drum="drum-72", rail="MGN15H-300", sheave=None, reeve_factor=1)
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
    base = dict(BLOCK)
    for rope, chain in (
        ("rope-4mm", ["eye-M12", "turnbuckle-hook-hook-M10"]),
        ("rope-5mm", ["eye-M12", "turnbuckle-eye-eye-M10"]),
        ("rope-8mm", ["eye-M20", "turnbuckle-eye-eye-M12"]),
    ):
        ceiling, part = catalogue.ceiling_for(
            parts, dict(base, rope=rope, chain=chain), angle_degrees=2.0)
        assert round(ceiling) == 1195
        assert part == "sheave"


def test_an_unpriced_line_keeps_the_total_a_floor():
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL, chain=["eye-M12", "turnbuckle-hook-hook-M10"])
    total = catalogue.price_of(parts, configuration)
    assert total["is_floor"] is True
    assert total["unpriced"] == ["drum-72"]          # the workshop drum carries no price
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
    motor="23HS45-4204D-E1000", drive="CL57T-V41", gearbox="EG23-G20-D8", drum="drum-72",
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
        parts, dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K"), angle_degrees=2.0)
    assert round(named) == 1195 and binding == "sheave"


def test_the_briefed_drum_holds_37_wraps_which_is_8369_mm():
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K", rope="rope-4mm")
    fits = catalogue.drum_and_travel(parts, configuration, 8000.0)
    assert fits["drum_capacity_wraps"] == 37
    assert round(fits["drum_capacity_mm"]) == 8369
    assert fits["drum_fits"] is True
    assert fits["carriage_travel_mm"] == 4000.0 and fits["rail_fits"] is False
    over = catalogue.drum_and_travel(parts, configuration, 8400.0)
    assert over["drum_fits"] is False


def test_the_carriage_travel_is_checked_against_the_stroke():
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K", rope="rope-4mm")
    ok = catalogue.drum_and_travel(parts, configuration, 600.0)
    assert ok["carriage_travel_mm"] == 300.0 and ok["rail_fits"] is True
    no = catalogue.drum_and_travel(parts, configuration, 601.0)
    assert no["rail_fits"] is False


def test_the_sheave_to_rope_ratio_is_a_number_with_no_verdict():
    parts = catalogue.load_parts()
    configuration = dict(REEVED_NO_SHEAVE, sheave="GPS-WZ11K", rope="rope-4mm")
    result = catalogue.drum_and_travel(parts, configuration, 100.0)
    assert result["sheave_over_rope_diameter"] == 30.0
    assert not any("verdict" in k or "ok" == k for k in result)


def _demand(t1=500.0, sag=1.0, acceptance=2.18, load=66890.0):
    return {"acceptance": acceptance,
            "sizing": {"stage": "S7", "worst_wire_tension_newtons": t1,
                       "worst_actuator_newtons": 0.0, "worst_sag_mm": sag,
                       "load_newtons": load}}




def test_the_drive_follows_the_motor_by_family():
    parts = catalogue.load_parts()
    for key, motor in parts["motor"].items():
        drive = catalogue.drive_for(parts, key)
        assert parts["drive"][drive]["family"] == motor["family"], key
    assert catalogue.drive_for(parts, "23HS45-4204D-E1000") == "CL57T-V41"
    assert catalogue.drive_for(parts, "34HS46-6004D-E1000") == "CL86T-V41"
    assert catalogue.drive_for(parts, "A6-RS400H2A1-M17") == "A6-400RS"
    with pytest.raises(catalogue.CatalogueError):
        catalogue.drive_for(parts, "not-a-motor")




def test_part_for_term_names_the_part_each_term_belongs_to():
    configuration = dict(SEVEN_SPOOL)
    assert catalogue.part_for_term(configuration, "motor torque") == "34HS46-6004D-E1000"
    assert catalogue.part_for_term(configuration, "gearbox torque") == "EG34-G20"
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
    configuration = dict(SEVEN_SPOOL)
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
    configuration = dict(SEVEN_SPOOL)
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
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(sag=10.0))
    assert factor["limit_factor"] == 0.0
    assert factor["binding"] == "deviation" and factor["binding_part"] == "shape"
    assert factor["sufficient"] is False


def test_no_acceptance_line_judges_the_parts_alone():
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0,
                                   _demand(sag=10.0, acceptance=None))
    assert factor["binding"] == "anchor" and factor["acceptance_mm"] is None


def test_a_demand_without_sizing_gives_no_load_factor():
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    assert catalogue.load_factor(parts, configuration, 10.0, {"stages": []}) is None
    assert catalogue.load_factor(parts, configuration, 10.0, None) is None
    assert catalogue.sizing_of({"sizing": None}) is None










def test_a_rig_is_sufficient_when_it_carries_exactly_the_sizing_stages_load():
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    ceiling, _ = catalogue.ceiling_for(parts, configuration, 10.0)
    exact = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=ceiling))
    assert exact["limit_factor"] == pytest.approx(1.0) and exact["sufficient"] is True
    over = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=ceiling * 1.001))
    assert over["limit_factor"] == pytest.approx(0.9) and over["sufficient"] is False


def test_a_net_with_no_tension_at_the_sizing_stage_has_nothing_to_scale():
    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=0.0))
    assert factor["limit_factor"] is None and factor["sufficient"] is None
    assert factor["binding"] == "none" and factor["binding_part"] is None
    assert factor["margin"] is None and "nothing to scale" in factor["detail"]
    assert round(factor["ceiling_newtons"]) == 1471


def test_a_sizing_that_is_not_a_block_is_no_sizing():
    for odd in (None, "S7", [], 0, 4.2):
        assert catalogue.sizing_of({"sizing": odd}) is None
    block = {"stage": "S7"}
    assert catalogue.sizing_of({"sizing": block}) is block


def test_when_two_terms_breach_on_one_rung_the_load_factor_names_the_ceilings_own_part():
    parts = catalogue.load_parts()
    configuration = dict(EYE_EYE)
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
    assert factor["binding_part"] == "34HS46-6004D-E1000"
    # and the sentence beside it is the motor's, not the eye bolt's
    assert "N mm" in factor["detail"] and "working load" not in factor["detail"]


# a phrase that only each part term's own sentence carries (mechanism.checks words them)
_TERM_WORDS = {"rope tension": "net cable", "anchor": "N working load",
               "spool rope tension": "spool rope", "sheave": "moving block",
               "gearbox torque": "at the output", "motor torque": "needed against"}


def test_the_load_factor_and_the_ceiling_line_never_name_different_parts():
    parts = catalogue.load_parts()
    seen = set()
    machines = {"seven-spool": SEVEN_SPOOL, "block": BLOCK, "eye-eye": EYE_EYE,
                "heavy": HEAVY,
                "rope": dict(SEVEN_SPOOL, chain=["eye-M12", "turnbuckle-eye-eye-M10"])}
    for key, configuration in machines.items():
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
    assert {"anchor", "rope tension", "sheave", "gearbox torque", "motor torque"} <= seen


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
    configuration = dict(EYE_EYE)
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand())
    # the part is the ceiling's whatever happens; the walk's own sentence stands
    assert factor["binding"] == "motor torque" and factor["binding_part"] == "34HS46-6004D-E1000"
    assert factor["limit_factor"] == pytest.approx(4.7)
    assert "N working load" in factor["detail"]


def test_lifting_a_term_moves_that_terms_limit_and_nothing_else():
    parts = catalogue.load_parts()
    configuration = dict(BLOCK)
    mechanism = catalogue.mechanism_for(parts, configuration, 10.0)
    for name, field in (("rope tension", "rope_mbl"), ("anchor", "anchor_wll"),
                        ("spool rope tension", "spool_rope_mbl"), ("sheave", "sheave_swl"),
                        ("gearbox torque", "gearbox_torque")):
        lifted = catalogue._with_terms_lifted(mechanism, [name])
        moved = {f for f in mechanism._fields if getattr(lifted, f) != getattr(mechanism, f)}
        assert moved == {field}, name
    # a spool rope that defaults to the net rope keeps the rope it was when the net rope is lifted
    defaulted = mechanism._replace(spool_rope_mbl=None)
    lifted = catalogue._with_terms_lifted(defaulted, ["rope tension"])
    assert lifted.rope_mbl > 1e100 and lifted.spool_rope_mbl == defaulted.rope_mbl


def test_a_gearbox_past_its_limit_on_the_motors_rung_is_worded_as_the_motor():
    """The motor allows 2350 N and its 90 N m gearbox 2500 N. Rungs of 1300 N
    put the second, 2600 N, past both; checks() tests the gearbox first, so the
    walk's own sentence is the gearbox's. The ceiling's term is the motor, and
    its sentence is the motor's."""

    parts = catalogue.load_parts()
    configuration = dict(SEVEN_SPOOL, rope="rope-6mm", chain=["eye-M16", "turnbuckle-eye-eye-M12"])
    factor = catalogue.load_factor(parts, configuration, 10.0, _demand(t1=13000.0))
    assert factor["breaching_factor"] == pytest.approx(0.2)
    assert factor["binding"] == "motor torque"
    assert factor["binding_part"] == "34HS46-6004D-E1000"
    assert "needed against" in factor["detail"] and "at the output" not in factor["detail"]


def test_a_gearbox_that_binds_is_named_by_its_part():
    parts = catalogue.load_parts()
    ceiling, named = catalogue.ceiling_for(parts, HEAVY, 10.0)
    # 100 N m at the output over the 36 mm drum: 2777.8 N
    assert round(ceiling, 1) == 2777.8 and named == "gearbox torque"
    factor = catalogue.load_factor(parts, HEAVY, 10.0, _demand())
    assert factor["binding"] == "gearbox torque" and factor["binding_part"] == "EG34-G50"
