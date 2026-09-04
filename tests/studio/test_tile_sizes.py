"""The arithmetic that gives a library picture its real-world size.

Two libraries publish the size of the whole photograph, in two different
units, and QS's library holds a CROP of that photograph, one brick or one
plank cut out of a wall. Getting either half wrong is not a small error: a
factor of ten in the unit, or forgetting the crop entirely, and a vault
stands on cobbles the size of cars.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

import fetch_tile_sizes as tool  # noqa: E402


def test_a_published_size_is_the_whole_photograph_and_the_library_holds_a_crop():
    """brick/stock-red's real numbers, from Param's own library.

    Bricks005 is a 4096 square photograph of a wall, and material.json
    records that 11.16 per cent of its width and 3.15 per cent of its height
    were cut out to make one brick. Multiply a two metre wall by those
    fractions and a brick comes out: 223 by 63 millimetres, which is a
    stock brick to within the mortar joint.
    """

    provenance = {"crop_fractions": [0.448486, 0.546631, 0.111572, 0.031494]}
    assert tool.apply_crop([2.0, 2.0], provenance) == [0.2231, 0.063]


def test_a_material_with_no_crop_recorded_is_the_whole_source():
    """A hundred of the 158 have no crop: the picture went in whole, because
    looking at it showed it already repeated."""

    assert tool.apply_crop([6.0, 6.0], {}) == [6.0, 6.0]
    assert tool.apply_crop([2.0, 2.0], {"crop_fractions": None}) == [2.0, 2.0]


def test_a_crop_that_makes_no_sense_is_ignored_rather_than_believed():
    """A fraction above one or at zero would give a tile larger than the
    photograph or of no size at all. Both mean the record is wrong, and a
    wrong record is better ignored than multiplied."""

    for bad in ([0, 0, 0, 0], [0, 0, 1.4, 0.5], [0, 0, 0.5, 0],
                [0, 0, "half", 0.5], [0, 0]):
        assert tool.apply_crop([2.0, 2.0], {"crop_fractions": bad}) == [2.0, 2.0]


def test_poly_haven_millimetres_become_metres(tmp_path):
    (tmp_path / "ph_textures.json").write_text(json.dumps({
        "gravel_floor_02": {"dimensions": [2000, 2000]},
        "noisy_float": {"dimensions": [2460.0000381469727, 1899.9998569488525]},
        "no_size": {"name": "an hdri has no dimensions"},
        "zero": {"dimensions": [0, 0]},
    }), encoding="utf-8")
    sizes = tool.poly_haven_sizes(tmp_path)
    assert sizes["gravel_floor_02"] == [2.0, 2.0]
    # The float noise is a unit conversion artefact on their side, rounded
    # off here rather than carried into a repeat count.
    assert sizes["noisy_float"] == [2.46, 1.9]
    assert "no_size" not in sizes and "zero" not in sizes


def test_ambientcg_centimetres_become_metres_and_zero_means_unknown(tmp_path):
    """ambientCG writes 0 for every asset published before it started
    measuring, which is most of them. Read as a size, a zero gives an
    infinite repeat count and a texture that never draws."""

    (tmp_path / "acg_p0.json").write_text(json.dumps({"assets": [
        {"id": "PavingStones151", "dimensions": {"width": 540, "height": 540}},
        {"id": "Bricks005", "dimensions": {"width": 0, "height": 0}},
    ]}), encoding="utf-8")
    sizes = tool.ambientcg_sizes(tmp_path)
    assert sizes["pavingstones151"] == [5.4, 5.4]
    assert "bricks005" not in sizes


def test_the_two_libraries_are_read_in_their_own_units_not_a_shared_one(tmp_path):
    """The same number, 540, is 54 centimetres to one library and 54
    centimetres to neither if the units are swapped. This is the test that
    fails if the divisors are ever made the same."""

    (tmp_path / "ph_textures.json").write_text(
        json.dumps({"a": {"dimensions": [540, 540]}}), encoding="utf-8")
    (tmp_path / "acg_p0.json").write_text(json.dumps({"assets": [
        {"id": "B", "dimensions": {"width": 540, "height": 540}}]}),
        encoding="utf-8")
    assert tool.poly_haven_sizes(tmp_path)["a"] == [0.54, 0.54]
    assert tool.ambientcg_sizes(tmp_path)["b"] == [5.4, 5.4]


def test_every_populated_family_has_a_fallback_size():
    """Where a publisher records nothing the family says what a sensible
    unit is, and every family on disk must have one or those materials come
    out with no scale at all."""

    populated = ("aggregate", "brick", "clay", "concrete", "metal", "paint",
                 "plaster", "plastic", "slate", "stone", "timber")
    for family in populated:
        size = tool.FAMILY_DEFAULTS[family]
        assert len(size) == 2 and size[0] > 0 and size[1] > 0, family
    # The three seeded but empty families are here too, so a material
    # arriving in one of them tomorrow is not the day this breaks.
    for family in ("glass", "mortar", "mineral-wool"):
        assert family in tool.FAMILY_DEFAULTS
