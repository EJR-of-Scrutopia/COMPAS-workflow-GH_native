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
