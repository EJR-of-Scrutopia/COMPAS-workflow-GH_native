"""The whole spooling mechanisms the one Cable net tab chooses from, and one
spool's pull (spec 2026-10-11 one Cable net tab, sections 4.1 and 8.1)."""

import json
import re
import sys
from pathlib import Path

import pytest

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import catalogue  # noqa: E402
import machine  # noqa: E402

FACTS = {"winding_radius_mm": 33.9, "reeve_factor": 4, "spools": 7}
ANGLE = 10.0


def _every_combination(parts, motor, wires_per_motor):
    for option in machine.ratio_options(parts, motor):
        for rope in parts["rope"]:
            for pulley in [None] + machine.pulleys_for(parts, rope):
                choices = {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                           "rope": rope, "wires_per_motor": wires_per_motor}
                try:
                    built = machine.derive(parts, choices, FACTS, ANGLE)
                    yield built, machine.limit_terms(parts, built, ANGLE)
                except (machine.MachineError, catalogue.CatalogueError):
                    continue


def test_one_spools_pull_is_the_binding_limit_term_of_its_wire():
    parts = catalogue.load_parts()
    built = machine.derive(parts, {"motor": "23HS45-4204D-E1000", "ratio": 20,
                                   "pulley": "Pfaff-DSRB-90-4", "rope": "rope-4mm",
                                   "wires_per_motor": 2}, FACTS, ANGLE)
    terms = machine.limit_terms(parts, built, ANGLE)
    binding = next(term for term in terms if term["binds"])
    have = machine.have(parts, built, ANGLE)
    assert have == {"newtons": binding["newtons"], "limit": binding["name"],
                    "part": binding["part"]}
    # the lowest of the wire's own limits and its share of the motor
    assert have["newtons"] == min(term["newtons"] for term in terms)


def test_the_list_holds_one_whole_mechanism_a_buildable_motor_strongest_first():
    parts = catalogue.load_parts()
    listed = machine.presets(parts, FACTS, ANGLE, 1)
    buildable = [motor for motor in machine.offered_motors(parts)
                 if any(True for _ in _every_combination(parts, motor, 1))]
    assert sorted(entry["choices"]["motor"] for entry in listed) == sorted(buildable)
    pulls = [entry["have_newtons"] for entry in listed]
    assert pulls == sorted(pulls, reverse=True)
    for entry in listed:
        # the most that motor's ratios, ropes and pulleys give a spool
        best = max(min(term["newtons"] for term in terms)
                   for _, terms in _every_combination(parts, entry["choices"]["motor"], 1))
        assert entry["have_newtons"] == pytest.approx(best)
        assert entry["choices"]["wires_per_motor"] == 1
        built = machine.derive(parts, entry["choices"], FACTS, ANGLE)
        assert machine.have(parts, built, ANGLE)["newtons"] == pytest.approx(entry["have_newtons"])
        assert entry["described"] == machine.describe(parts, built)
        # by real names and its pull: motor, ratio, pulleys, rope, newtons a
        # spool and what limits it, and the drive's own pull when the drive is
        # not what limits it
        assert re.fullmatch(r"[\w-]+, (direct|\d+:1), (\d+ mm pulleys|no pulleys), "
                            r"\d+ mm [\w ]+: [\d,]+ N [a-z ]+(, [\d,]+ N drive)?",
                            entry["label"]), entry["label"]
    top = listed[0]
    assert top["label"].split(": ")[1].startswith("{:,.0f} N ".format(top["have_newtons"]))
    assert top["limit"] and top["part"]


def test_each_mechanism_says_what_limits_it_and_what_its_drive_pulls():
    # Param, 2026-10-12, on the 2 sided prototype's 8.8 mm drum: "the
    # mechanisms are all showing the same amount of newtons, they should be
    # different". Every motor there out-pulls a 6 mm rope, so the rope's working
    # load is every one's pull; what differs is the drive behind it, said
    small = {"winding_radius_mm": 8.8, "reeve_factor": 4, "spools": 7}
    parts = catalogue.load_parts()
    listed = machine.presets(parts, small, ANGLE, 1, rope="rope-6mm")
    assert all(abs(entry["have_newtons"] - 3760.0) < 1.0 for entry in listed)
    drives = []
    for entry in listed:
        built = machine.derive(parts, entry["choices"], small, ANGLE)
        terms = {term["name"]: term["newtons"] for term in machine.limit_terms(parts, built, ANGLE)}
        # a direct drive has no gearbox
        drive = min(value for name, value in terms.items() if name in ("motor torque", "gearbox torque"))
        assert entry["drive_newtons"] == pytest.approx(drive)
        assert entry["label"].endswith(": 3,760 N rope, {:,.0f} N drive".format(drive)), entry["label"]
        drives.append(round(drive))
    assert len(set(drives)) > 1, "the drives differ, and the list says so"
    # among ratios that pull alike, the one with the strongest drive is listed
    for entry in listed:
        motor = entry["choices"]["motor"]
        alike = [machine.derive(parts, {**entry["choices"], "ratio": option["ratio"]}, small, ANGLE)
                 for option in machine.ratio_options(parts, motor)]
        best = 0.0
        for built in alike:
            try:
                terms = {t["name"]: t["newtons"] for t in machine.limit_terms(parts, built, ANGLE)}
            except Exception:
                continue
            if min(terms.values()) >= entry["have_newtons"] - 1e-6:
                best = max(best, min(value for name, value in terms.items()
                                     if name in ("motor torque", "gearbox torque")))
        assert entry["drive_newtons"] == pytest.approx(best), motor
    # where the drive itself limits, it is said once
    plain = machine.presets(parts, FACTS, ANGLE, 1, rope="rope-6mm")
    weak = [entry for entry in plain if entry["limit"] in ("motor torque", "gearbox torque")]
    assert weak and all(entry["label"].endswith(" N drive") and ", " not in entry["label"].split(": ")[1]
                        for entry in weak)


def test_the_part_that_limits_a_spool_is_named_as_it_is_bought():
    parts = catalogue.load_parts()
    assert machine.part_name(parts, "rope-8mm") == "8 mm 7x19"
    assert machine.part_name(parts, "GPS-55-209464") == "GPS 55 mm polyamide"
    assert machine.part_name(parts, "23HS45-4204D-E1000") == "23HS45-4204D-E1000"
    assert machine.part_name(parts, "no-such-part") == "no-such-part"
    for entry in machine.presets(parts, FACTS, ANGLE, 1):
        assert entry["part_name"] == machine.part_name(parts, entry["part"])


def test_sharing_a_motor_never_raises_a_spools_pull():
    parts = catalogue.load_parts()
    alone = {entry["choices"]["motor"]: entry["have_newtons"]
             for entry in machine.presets(parts, FACTS, ANGLE, 1)}
    shared = machine.presets(parts, FACTS, ANGLE, 2)
    assert shared and all(entry["choices"]["wires_per_motor"] == 2 for entry in shared)
    for entry in shared:
        assert entry["have_newtons"] <= alone[entry["choices"]["motor"]] + 1e-9
    # a stepper's torque is halved between two wires
    assert any(entry["have_newtons"] < alone[entry["choices"]["motor"]] - 1.0 for entry in shared)


pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402
from test_formwork_sim import _route_mechanism  # noqa: E402


def _plant(tmp_path, document=None):
    document = document if document is not None else dict(
        _route_mechanism(), mechanism={"spoolRadius": 0.0339})
    (tmp_path / "upload" / "Tiny-mechanism.json").write_text(json.dumps(document),
                                                             encoding="utf-8")


def test_the_route_lists_the_mechanisms_at_the_wires_a_motor_asked(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.get("/api/studies/Tiny/mechanisms", params={"wires_per_motor": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["wires_per_motor"] == 2 and body["angle_degrees"] == ANGLE
    listed = body["mechanisms"]
    assert listed and all(entry["choices"]["wires_per_motor"] == 2 for entry in listed)
    pulls = [entry["have_newtons"] for entry in listed]
    assert pulls == sorted(pulls, reverse=True)
    # one wire a motor when none is asked
    assert all(entry["choices"]["wires_per_motor"] == 1 for entry in
               client.get("/api/studies/Tiny/mechanisms").json()["mechanisms"])


def test_every_mechanism_he_can_build_for_the_wire_is_offered(tmp_path, monkeypatch):
    # Param, 2026-10-12: "this mechanisms tab i also want to be able to create
    # my own mechanism, choose whether there is pulley or not should just be a
    # toggle"; asked, the pop-up becomes Motor, Ratio, Pulleys on or off and
    # Pulley. Every motor, each of its ratios, and no pulley or each pulley
    # that takes the rope, each with its pull, what limits it and the most its
    # drive pulls ("we should at the end of that also have it show the newtons
    # max the mechanisms can produce")
    parts = catalogue.load_parts()
    offered = machine.options(parts, FACTS, ANGLE, 1, "rope-6mm")
    expected = []
    for motor in machine.offered_motors(parts):
        for option in machine.ratio_options(parts, motor):
            for pulley in [None] + machine.pulleys_for(parts, "rope-6mm"):
                choices = {"motor": motor, "ratio": option["ratio"], "pulley": pulley,
                           "rope": "rope-6mm", "wires_per_motor": 1}
                try:
                    built = machine.derive(parts, choices, FACTS, ANGLE)
                    terms = machine.limit_terms(parts, built, ANGLE)
                except (machine.MachineError, catalogue.CatalogueError):
                    continue
                expected.append((choices, built, terms))
    assert [entry["choices"] for entry in offered] == [choices for choices, _, _ in expected]
    assert any(entry["choices"]["pulley"] is None for entry in offered)
    assert any(entry["choices"]["pulley"] is not None for entry in offered)
    for entry, (choices, built, terms) in zip(offered, expected):
        have = machine.have(parts, built, ANGLE)
        assert entry["have_newtons"] == pytest.approx(have["newtons"])
        assert entry["limit"] == have["limit"]
        assert entry["drive_newtons"] == pytest.approx(machine.drive_newtons(terms))
        assert entry["ratio_label"] == ("direct" if choices["ratio"] is None
                                        else "{:g}:1".format(choices["ratio"]))
        assert entry["pulley_label"] == (None if choices["pulley"] is None
                                         else machine.part_name(parts, choices["pulley"]))
        assert entry["described"] == machine.describe(parts, built)
    # each motor's strongest is the one the list of mechanisms leads with
    best = {entry["choices"]["motor"]: entry
            for entry in machine.presets(parts, FACTS, ANGLE, 1, rope="rope-6mm")}
    for motor, entry in best.items():
        mine = [option for option in offered if option["choices"]["motor"] == motor]
        assert max(option["have_newtons"] for option in mine) == pytest.approx(entry["have_newtons"])
    # and the route carries them beside the mechanisms
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    body = client.get("/api/studies/Tiny/mechanisms", params={"rope": "rope-6mm"}).json()
    assert body["options"] and all(option["choices"]["rope"] == "rope-6mm" for option in body["options"])


def test_the_route_says_in_one_line_why_it_lists_none(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    for bad in ("0", "8", "two"):
        response = client.get("/api/studies/Tiny/mechanisms", params={"wires_per_motor": bad})
        assert response.status_code in (400, 422), bad
    assert client.get("/api/studies/Nowhere/mechanisms").status_code == 404
    # a study with no mechanism document, then one whose machine gives no radius
    response = client.get("/api/studies/Tiny/mechanisms")
    assert response.status_code == 400 and response.json()["detail"] == "mechanism: none for this study"
    _plant(tmp_path, dict(_route_mechanism(), mechanism={}))
    response = client.get("/api/studies/Tiny/mechanisms")
    assert response.status_code == 400 and response.json()["detail"] == "machine: no winding radius"
