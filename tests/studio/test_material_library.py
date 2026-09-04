"""The material library: a folder of folders, read and never written.

The shape under test is Param's own, curated inside QS Intelligence across
158 materials, so these tests build a small tree in exactly that shape
rather than inventing a fixture format. The awkward cases are the ones that
occur in his real library: a material with no AO map (50 of the 158), a
material so small no lod tier was ever written for it, and family folders
holding things that are not materials.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import app as studio_app  # noqa: E402
import materials  # noqa: E402


def write(path: Path, body: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


@pytest.fixture()
def library(tmp_path):
    """A library in the QS stack shape, with the awkward cases in it."""

    root = tmp_path / "materials"

    # A complete material, with both lod tiers for colour and only the
    # smaller one for normal, which is what happens when a normal master is
    # between 256 and 1024 pixels on its long edge.
    full = root / "brick" / "stock-red"
    for name in ("colour.jpg", "normal.png", "height.png",
                 "roughness.png", "ao.png"):
        write(full / name)
    write(full / "lod" / "colour-1024.jpg")
    write(full / "lod" / "colour-256.jpg")
    write(full / "lod" / "normal-256.png")
    (full / "material.json").write_text(json.dumps({
        "family": "brick", "name": "stock-red", "site": "ambientCG",
        "source": "https://ambientcg.com/view?id=Bricks005", "licence": "CC0",
        "dimensions": {"width": 21.5, "height": 6.5, "depth": 0},
    }), encoding="utf-8")

    # No AO, which is the ordinary case for 50 of the 158, and no tiers at
    # all, which is the case for a master already smaller than 256.
    thin = root / "timber" / "oak-board"
    for name in ("colour.jpg", "normal.png", "height.png", "roughness.png"):
        write(thin / name)
    (thin / "material.json").write_text(json.dumps({
        "site": "Poly Haven", "source": "https://polyhaven.com/a/oak",
        "licence": "CC0", "dimensions": [2000, 2000],
    }), encoding="utf-8")

    # Things that are not materials and must not be counted as any.
    (root / "brick" / "not-a-material").mkdir(parents=True, exist_ok=True)
    write(root / "brick" / "not-a-material" / "normal.png")
    (root / "glass").mkdir(parents=True, exist_ok=True)   # a seeded, empty family
    write(root / "README.txt")

    return root


def test_a_material_is_a_folder_holding_a_colour_map(library):
    """The marker is colour.jpg and nothing else qualifies.

    This is the rule that lets the library have no index file to fall out of
    step with: a folder of normal maps with no colour is not a material, and
    an empty seeded family is not one either.
    """

    found = materials.scan(library)
    keys = [entry["key"] for entry in found]
    assert keys == ["brick/stock-red", "timber/oak-board"]
    assert "brick/not-a-material" not in keys


def test_the_maps_a_material_actually_has_are_reported(library):
    found = {entry["key"]: entry for entry in materials.scan(library)}
    assert found["brick/stock-red"]["maps"] == [
        "colour", "normal", "height", "roughness", "ao"]
    # Fifty of the 158 have no AO, and their absence is reported by the map
    # simply not being in the list, not by a flag.
    assert "ao" not in found["timber/oak-board"]["maps"]


def test_the_folder_name_is_the_identity_and_the_label_is_only_speech(library):
    found = {entry["key"]: entry for entry in materials.scan(library)}
    assert found["brick/stock-red"]["name"] == "stock-red"
    assert found["brick/stock-red"]["label"] == "Stock red"
    assert found["timber/oak-board"]["label"] == "Oak board"


def test_a_missing_tier_falls_through_to_the_master_not_to_a_smaller_tier(library):
    """The rule that makes the lod scheme safe to read without opening a file.

    A tier is written only when the master's long edge exceeds it, so the
    largest tier at or below the size asked for being absent means the
    master is ALREADY no larger than that and is the right answer. Handing
    back the next tier down instead would be blurrier than the file the
    caller could have had.
    """

    root = library
    # colour has both tiers, so each is served at its own size.
    assert materials.resolve(root, "brick", "stock-red", "colour", 1024).name \
        == "colour-1024.jpg"
    assert materials.resolve(root, "brick", "stock-red", "colour", 256).name \
        == "colour-256.jpg"
    # normal has only the 256 tier, so asking for 1024 gets the MASTER,
    # because the master must be 1024 or smaller for the 1024 tier to be
    # absent at all.
    assert materials.resolve(root, "brick", "stock-red", "normal", 1024).name \
        == "normal.png"
    assert materials.resolve(root, "brick", "stock-red", "normal", 256).name \
        == "normal-256.png"
    # No tiers at all, so every size is the master.
    assert materials.resolve(root, "timber", "oak-board", "colour", 256).name \
        == "colour.jpg"
    # No size asked for means the master, never a tier.
    assert materials.resolve(root, "brick", "stock-red", "colour", None).name \
        == "colour.jpg"


def test_a_map_the_material_does_not_have_resolves_to_nothing(library):
    assert materials.resolve(library, "timber", "oak-board", "ao", 256) is None
    assert materials.resolve(library, "brick", "stock-red", "specular", 256) is None


def test_physical_size_comes_out_of_both_libraries_in_metres(library):
    """The one field QS never needed, and the two sources that publish it.

    Poly Haven gives millimetres in a two-element list; ambientCG gives
    centimetres in an object. Both have to arrive in the studio as metres or
    the ground tiles at a thousand times the wrong scale.
    """

    found = {entry["key"]: entry for entry in materials.scan(library)}
    assert found["timber/oak-board"]["tileMetres"] == [2.0, 2.0]       # 2000 mm
    assert found["brick/stock-red"]["tileMetres"] == [0.215, 0.065]    # 21.5 cm


def test_an_ambientcg_zero_is_unknown_and_not_a_size():
    """ambientCG writes 0 where it does not know, which older and procedural
    assets frequently are. Read as a size that would make the repeat count
    infinite."""

    assert materials._tile_metres(
        {"site": "ambientCG", "dimensions": {"width": 0, "height": 0}}) is None
    assert materials._tile_metres({"site": "Poly Haven", "dimensions": [0, 0]}) is None
    assert materials._tile_metres({}) is None


def test_an_explicit_tile_size_beats_a_published_one():
    assert materials._tile_metres({
        "site": "ambientCG", "dimensions": {"width": 540, "height": 540},
        "tileMetres": [0.9, 0.6]}) == [0.9, 0.6]


def test_the_studio_records_its_own_tile_sizes_without_touching_the_library(library):
    """The sidecar is keyed by family/name so it survives the library moving."""

    found = materials.apply_sidecar(
        materials.scan(library),
        {"tileMetres": {"timber/oak-board": [0.15, 2.4]},
         "preview": {"timber/oak-board": "plank"}})
    entry = {row["key"]: row for row in found}["timber/oak-board"]
    assert entry["tileMetres"] == [0.15, 2.4]
    assert entry["preview"] == "plank"


def test_a_library_that_is_not_there_is_empty_and_not_an_error(tmp_path):
    assert materials.scan(None) == []
    assert materials.scan(tmp_path / "nowhere") == []


# ---------------------------------------------------------------- routes


@pytest.fixture()
def client(library, tmp_path, monkeypatch):
    monkeypatch.setattr(studio_app, "MATERIALS_DIR", library)
    monkeypatch.setattr(studio_app, "MATERIALS_SIDECAR", tmp_path / "notes.json")
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(studio_app.create_app())


def test_the_index_names_the_families_and_the_materials(client, library):
    payload = client.get("/api/materials").json()
    assert payload["exists"] is True
    assert payload["root"] == str(library)
    # An empty seeded family is still a family: the taxonomy has fourteen
    # names and three of them hold nothing yet, which is a visible slot
    # rather than an omission.
    assert payload["families"] == ["brick", "timber"]
    assert [row["key"] for row in payload["materials"]] == [
        "brick/stock-red", "timber/oak-board"]


def test_a_map_is_served_at_the_size_asked_for(client):
    assert client.get("/api/materials/brick/stock-red/colour?px=256").status_code == 200
    assert client.get("/api/materials/brick/stock-red/colour").status_code == 200
    assert client.get("/api/materials/timber/oak-board/ao?px=256").status_code == 404


def test_a_material_route_refuses_to_walk_out_of_the_library(client):
    for family, name in (("..", "stock-red"), ("brick", ".."),
                         ("brick/..", "stock-red")):
        response = client.get(
            "/api/materials/{}/{}/colour".format(family, name))
        assert response.status_code in (400, 404), (family, name)


def test_the_tile_size_is_written_to_the_studio_and_never_to_the_library(
        client, library, tmp_path):
    response = client.post("/api/materials/brick/stock-red/tile",
                           json={"tileMetres": [0.44, 0.22]})
    assert response.status_code == 200
    assert response.json()["tileMetres"] == [0.44, 0.22]
    # It landed in the studio's sidecar, and the library folder is untouched.
    stored = json.loads((tmp_path / "notes.json").read_text(encoding="utf-8"))
    assert stored["tileMetres"]["brick/stock-red"] == [0.44, 0.22]
    assert sorted(p.name for p in (library / "brick" / "stock-red").iterdir()) == [
        "ao.png", "colour.jpg", "height.png", "lod", "material.json",
        "normal.png", "roughness.png"]
    # And the index now reports it in place of the published figure.
    index = client.get("/api/materials").json()
    entry = {row["key"]: row for row in index["materials"]}["brick/stock-red"]
    assert entry["tileMetres"] == [0.44, 0.22]


def test_a_tile_size_must_be_two_positive_numbers(client):
    for bad in ([0, 1], [-1, 2], ["wide", "tall"], [1]):
        assert client.post("/api/materials/brick/stock-red/tile",
                           json={"tileMetres": bad}).status_code == 400


def test_the_word_folder_is_not_swallowed_by_a_path_parameter(client):
    """FastAPI matches in declaration order, so /api/props/{name} declared
    first would answer a folder request with "no prop file folder". The
    three folder routes are declared above their libraries' parameterised
    routes and this is the test that keeps them there."""

    for kind in ("materials", "hdri", "props"):
        row = client.get("/api/{}/folder".format(kind))
        assert row.status_code == 200, kind
        assert set(row.json()) == {"path", "exists", "count"}, kind


def test_choosing_one_folder_does_not_forget_the_others(client, tmp_path):
    """settings.json used to be written as a fresh object with one key in it,
    which was correct while there was one setting and would have thrown away
    the vault folder the moment a sky folder was chosen."""

    settings = tmp_path / "settings.json"
    studio_app.remember_setting("upload_folder", "C:/vaults")
    studio_app.remember_setting("hdri_folder", "C:/skies")
    stored = json.loads(settings.read_text(encoding="utf-8"))
    assert stored == {"upload_folder": "C:/vaults", "hdri_folder": "C:/skies"}


def test_a_folder_that_is_not_a_folder_is_refused_by_name(client, tmp_path):
    response = client.post("/api/materials/folder",
                           json={"path": str(tmp_path / "nowhere")})
    assert response.status_code == 400
    assert "is not a folder on this machine" in response.json()["detail"]


def test_setting_a_material_folder_takes_effect_and_is_remembered(
        client, library, tmp_path):
    response = client.post("/api/materials/folder", json={"path": str(library)})
    assert response.status_code == 200
    assert response.json()["count"] == 2
    stored = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert stored["material_folder"] == str(library)
