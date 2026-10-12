"""The wires drawn as the rope chosen (Param, 2026-10-12): "we should actually
make the wires we render in vaulted the actual wires selected for the mechanism
size and colour. so we can set a default up and then if i chnage the wire type
then it changes the rendered wires". His answers: the machines' wires redrawn
at the rope's size, the wire size a viewing multiplier at 1x, the nodes
following the rope, and one default rope in Settings until a study picks
another in the Cable net tab."""

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


def _luminance(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_every_rope_carries_how_it_is_drawn():
    ropes = catalogue.load_parts()["rope"]
    assert ropes
    for key, rope in ropes.items():
        look = rope.get("render")
        assert isinstance(look, dict), key
        assert re.fullmatch(r"#[0-9a-f]{6}", look.get("colour", "")), key
        assert 0.0 <= float(look["metalness"]) <= 1.0, key
        assert 0.0 <= float(look["roughness"]) <= 1.0, key
    # stainless is the bright one, galvanised the dull grey
    stainless = ropes["rope-2mm-7x19-ss"]["render"]
    galvanised = ropes["rope-2mm-7x7"]["render"]
    assert _luminance(stainless["colour"]) > _luminance(galvanised["colour"])
    assert stainless["roughness"] < galvanised["roughness"]


def test_a_rope_without_a_look_is_refused_when_the_catalogue_is_read(tmp_path):
    parts = json.loads((STUDIO / "parts.json").read_text(encoding="utf-8"))
    del parts["rope"]["rope-3mm"]["render"]
    path = tmp_path / "parts.json"
    path.write_text(json.dumps(parts), encoding="utf-8")
    with pytest.raises(catalogue.CatalogueError, match="rope-3mm"):
        catalogue.load_parts(path)


def test_the_mechanisms_can_be_held_to_one_rope():
    parts = catalogue.load_parts()
    for rope in ("rope-2mm-7x7", "rope-3mm", "rope-8mm"):
        listed = machine.presets(parts, FACTS, ANGLE, 1, rope=rope)
        assert listed, rope
        assert all(entry["choices"]["rope"] == rope for entry in listed), rope
        pulls = [entry["have_newtons"] for entry in listed]
        assert pulls == sorted(pulls, reverse=True)
    # a light rope binds lower than the heavy one
    light = machine.presets(parts, FACTS, ANGLE, 1, rope="rope-2mm-7x7")[0]["have_newtons"]
    heavy = machine.presets(parts, FACTS, ANGLE, 1, rope="rope-8mm")[0]["have_newtons"]
    assert light < heavy
    with pytest.raises(machine.MachineError, match="no-such-rope"):
        machine.presets(parts, FACTS, ANGLE, 1, rope="no-such-rope")


pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402
from test_mechanisms import _plant  # noqa: E402


def test_the_route_lists_the_mechanisms_for_the_rope_asked(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    _plant(tmp_path)
    response = client.get("/api/studies/Tiny/mechanisms", params={"rope": "rope-3mm"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rope"] == "rope-3mm"
    assert body["mechanisms"]
    assert all(entry["choices"]["rope"] == "rope-3mm" for entry in body["mechanisms"])
    refused = client.get("/api/studies/Tiny/mechanisms", params={"rope": "no-such-rope"})
    assert refused.status_code == 400
    assert "no-such-rope" in refused.json()["detail"]


def test_the_ropes_route_lists_every_rope_with_its_look_and_the_default(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    body = client.get("/api/ropes").json()
    parts = catalogue.load_parts()
    assert [row["key"] for row in body["ropes"]] == list(parts["rope"])
    for row in body["ropes"]:
        rope = parts["rope"][row["key"]]
        assert row["diameter_mm"] == rope["diameter_mm"]
        assert row["render"] == rope["render"]
        # as it is bought: "8 mm 7x19 galvanised"
        assert row["label"] == "{} {}".format(machine.part_name(parts, row["key"]), rope["material"])
    # nothing saved yet: the heaviest rope, the one the mechanisms favour
    assert body["default"] == "rope-8mm"


def test_the_default_rope_is_saved_with_the_other_settings(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    saved = client.put("/api/ropes/default", json={"rope": "rope-2mm-7x7"})
    assert saved.status_code == 200, saved.text
    assert client.get("/api/ropes").json()["default"] == "rope-2mm-7x7"
    stored = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert stored["default_rope"] == "rope-2mm-7x7"
    refused = client.put("/api/ropes/default", json={"rope": "no-such-rope"})
    assert refused.status_code == 400
    assert "no-such-rope" in refused.json()["detail"]
    assert client.get("/api/ropes").json()["default"] == "rope-2mm-7x7"
