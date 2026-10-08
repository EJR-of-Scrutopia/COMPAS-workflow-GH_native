"""A scatter is the thing he placed, and it keeps its name.

Param, 2026-09-13, over a hover box round one beech of a wood he had
scattered: "It also should have been that these trees should be one
scatter".

A planting used to be worked out from what was on a layer: every type
there sixty-four times or more. His beeches came to 50, 36, 26 and 15 of
four kinds, so none of them was bulk and every tree boxed alone. A count
cannot tell a sparse scatter from props placed by hand; the scatter that
placed them can, so each scattered prop now carries its scatter's number,
and the layout keeps it.

The functions themselves run under node here, over a field shaped like
his own: the same beech counts, ground cover interleaved with them in row
order, and a few props placed by hand.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STUDIO_JS = REPO / "bench" / "studio" / "static" / "studio.js"


def _whole(source, header):
    """One column-0 function of several lines, header to closing brace."""

    start = source.index(header)
    return source[start:source.index("\n}", start) + 2]


def _line(source, head):
    """The one line that starts with head: a constant, or a one-line
    function, which _whole would run on past."""

    start = source.index(head)
    return source[start:source.index("\n", start)]


HARNESS = r"""
class Vector3 { constructor(x, y, z) { this.x = x; this.y = y; this.z = z; } }
class Box3 { constructor(min, max) { this.min = min; this.max = max; } }
const THREE = { Vector3, Box3 };

const SIZES = {
  beech_european_beech_forest_04: [15.6, 31.6, 14.4],
  beech_european_beech_forest_05: [11.7, 25.3, 9.4],
  beech_european_beech_forest_06: [6.2, 15.3, 6.9],
  beech_european_beech_forest_07: [7.0, 13.5, 7.8],
  beech_european_beech_forest_01: [30.2, 48.4, 31.8],
  beech_european_beech_sapling_02: [2.8, 3.0, 3.5],
  grass_medium_01__tiny_c: [0.06, 0.06, 0.05],
  grass_medium_01__tall_a: [0.3, 0.32, 0.3],
  flower_heliophila__large: [1.66, 0.4, 1.2],
  fern_02__b: [0.99, 0.43, 0.9],
  bollard: [0.3, 1.0, 0.3],
};
function propEntry(type) { return SIZES[type] ? { sizeMetres: SIZES[type] } : null; }
const FAMILIES = {
  grass_medium_01: [{ key: "grass_medium_01__tiny_c" }, { key: "grass_medium_01__tall_a" }],
  fern_02: [{ key: "fern_02__b" }],
};
function familyMembers(family) { return FAMILIES[family] || []; }

const state = { props: [], scatter: { species: [] } };

__FUNCTIONS__

// A repeatable random, so the field is the same every run.
let seed = 7;
function random() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
function put(type, layer, scale) {
  const record = { type, layer, scale, x: random() * 40, y: random() * 40, z: 0,
    rotation: random() * 6.28, rotX: 0, rotY: 0 };
  state.props.push(record);
  return record;
}
const scattered = () => 0.8 + random() * 0.5;

// HIS FIELD, in miniature and in the order his rows came in: beeches and
// ground cover interleaved, the way a layout of his holds them.
const trees = { beech_european_beech_forest_04: 15, beech_european_beech_forest_05: 26,
  beech_european_beech_forest_06: 50, beech_european_beech_forest_07: 36,
  beech_european_beech_sapling_02: 319 };
const cover = { grass_medium_01__tiny_c: 2000, grass_medium_01__tall_a: 70,
  flower_heliophila__large: 5 };
const bag = [];
for (const [type, n] of Object.entries(trees)) for (let i = 0; i < n; i++) bag.push(type);
for (const [type, n] of Object.entries(cover)) for (let i = 0; i < n; i++) bag.push(type);
for (let i = bag.length - 1; i > 0; i--) {
  const j = Math.floor(random() * (i + 1));
  [bag[i], bag[j]] = [bag[j], bag[i]];
}
for (const type of bag) put(type, 1, scattered());
// Placed by hand: three bollards and one big beech, all at exactly 1.
const bollards = [put("bollard", 1, 1), put("bollard", 1, 1), put("bollard", 1, 1)];
const loneBeech = put("beech_european_beech_forest_01", 1, 1);
// And a little grass on a second layer of its own.
for (let i = 0; i < 10; i++) put("grass_medium_01__tiny_c", 2, scattered());

const out = {};
const idsOf = (pick) => [...new Set(state.props.filter(pick).map((r) => r.scatter || 0))];

// 1. A LAYOUT FROM BEFORE, restored: names worked out.
settleRestoredScatters(false);
out.legacy = {
  trees: idsOf((r) => r.layer === 1 && r.type in trees),
  cover: idsOf((r) => r.layer === 1 && r.type in cover),
  byHand: idsOf((r) => r.type === "bollard").concat(loneBeech.scatter ? [loneBeech.scatter] : [0]),
  secondLayer: idsOf((r) => r.layer === 2),
  ceiling: scatterIdCeiling,
};

// 2. THE LAYOUT CARRIES THEM: round trip, and a short list of runs.
const block = encodeProps(state.props);
const back = decodeProps(JSON.parse(JSON.stringify(block)));
out.roundTrip = {
  same: back.every((entry, i) => (entry.scatter || 0) === (state.props[i].scatter || 0)),
  runs: block.scatter.length / 2,
  rows: state.props.length,
  knows: layoutKnowsScatters(block),
};
const old = JSON.parse(JSON.stringify(block));
delete old.scatter;
out.oldLayout = { knows: layoutKnowsScatters(old), knowsBareArray: layoutKnowsScatters([]),
  anyNamed: decodeProps(old).some((entry) => entry.scatter) };

// 3. A NAMED LAYOUT IS NEVER GUESSED AT AGAIN, and its ceiling is its own.
// Tried on a copy whose layer-2 grass carries no name, as copies placed by
// hand at scattered sizes would: a guess would sweep them into a scatter.
const field = state.props;
state.props = field.map((r) => Object.assign({}, r));
const copies = state.props.filter((r) => r.layer === 2);
for (const r of copies) r.scatter = undefined;
const before = state.props.map((r) => r.scatter || 0);
settleRestoredScatters(true);
out.named = { unchanged: state.props.every((r, i) => (r.scatter || 0) === before[i]),
  copiesStillByHand: copies.every((r) => !r.scatter), ceiling: scatterIdCeiling };
state.props = field;
settleRestoredScatters(true);

// 4. A NEW STROKE JOINS THE SCATTER ITS MIX COULD HAVE MADE.
state.scatter.species = Object.keys(trees).map((type) => ({ type, weight: 1 }));
out.moreBeeches = scatterIdFor(1);
state.scatter.species = [{ type: "grass_medium_01", weight: 9 }];
out.moreGrassWithoutTheFlower = scatterIdFor(1);
state.scatter.species = [{ type: "grass_medium_01", weight: 9 },
  { type: "flower_heliophila__large", weight: 1 }];
out.theWholeCoverMix = scatterIdFor(1);
state.scatter.species = [{ type: "fern_02", weight: 1 }];
out.ferns = scatterIdFor(1);
state.scatter.species = [{ type: "grass_medium_01", weight: 9 }];
out.grassOnLayerTwo = scatterIdFor(2);

// 5. ONE PLANTING PER SCATTER PER LAYER, and a name that says how many.
const beech = state.props.find((r) => r.type === "beech_european_beech_forest_06");
const planting = plantingOf(beech);
const members = plantingRecords(planting);
const box = plantingBounds(planting);
out.planting = { members: members.length, name: plantingName(planting),
  sameObject: plantingOf(state.props.find((r) => r.type === "beech_european_beech_forest_04")) === planting,
  byHand: plantingOf(loneBeech), boxTop: +box.max.z.toFixed(1) };
// Grouped onto another layer, a tree keeps its number and stands apart.
beech.layer = 3;
clearPlantings();
out.moved = { own: plantingRecords(plantingOf(beech)).length,
  left: plantingRecords(plantingOf(state.props.find((r) => r.type === "beech_european_beech_forest_04"))).length };

console.log(JSON.stringify(out));
"""


def _run_harness(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    js = STUDIO_JS.read_text(encoding="utf-8")
    pieces = [
        _line(js, "const LAYOUT_STRIDE = "),
        _line(js, "function roundMm(value)"),
        _line(js, "function roundTurn(value)"),
        _whole(js, "function encodeProps(props)"),
        _whole(js, "function layoutKnowsScatters(block)"),
        _whole(js, "function decodeProps(block)"),
        _line(js, "const plantings = new Map();"),
        _line(js, "let scatterIdCeiling = "),
        _line(js, "function clearPlantings()"),
        _whole(js, "function plantingOf(record)"),
        _whole(js, "function inPlanting(record, planting)"),
        _whole(js, "function plantingName(planting)"),
        _whole(js, "function plantingBounds(planting)"),
        _whole(js, "function plantingRecords(planting)"),
        _whole(js, "function scatterIdFor(layerId)"),
        _line(js, "const LEGACY_BULK = "),
        _line(js, "const LEGACY_SIZE_SPREAD = "),
        _line(js, "const LEGACY_TALL_METRES = "),
        _whole(js, "function adoptLegacyScatters()"),
        _whole(js, "function settleRestoredScatters(knowsScatters)"),
        _whole(js, "function propFootprint(type)"),
        _whole(js, "function propStature(type)"),
    ]
    script = tmp_path / "scatters.mjs"
    script.write_text(HARNESS.replace("__FUNCTIONS__", "\n\n".join(pieces)),
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_his_beeches_are_one_scatter_when_an_old_layout_is_opened(tmp_path):
    """A layout written before scatters were named -- his own -- has its
    plantings worked out once on the way in. His rows interleave beeches
    with ground cover, so the order they were placed in is no guide; what
    is, is that a scattered kind stands at many sizes while a prop placed
    by hand arrives at exactly 1, and that trees stand above a person."""

    out = _run_harness(tmp_path)
    legacy = out["legacy"]
    assert len(legacy["trees"]) == 1 and legacy["trees"][0] > 0, (
        "every beech of every kind in one scatter, the sparse ones "
        "included: {}".format(legacy["trees"]))
    assert len(legacy["cover"]) == 1 and legacy["cover"][0] > 0, legacy["cover"]
    assert legacy["cover"] != legacy["trees"], (
        "the ground cover is a scatter of its own, or hovering a tree "
        "would box and Delete would take the whole field under it")
    assert legacy["byHand"] == [0, 0], (
        "bollards and a beech placed by hand at size 1 keep their own "
        "boxes: {}".format(legacy["byHand"]))
    assert len(legacy["secondLayer"]) == 1
    assert legacy["secondLayer"][0] not in (legacy["trees"][0], legacy["cover"][0])
    # Named in a fixed order, so the same layout says the same names every
    # time it is opened until they are saved.
    assert legacy["cover"][0] == 1 and legacy["trees"][0] == 2
    assert legacy["secondLayer"][0] == 3 and legacy["ceiling"] == 3


def test_the_layout_keeps_the_names_as_runs(tmp_path):
    out = _run_harness(tmp_path)
    trip = out["roundTrip"]
    assert trip["same"], "every row comes back in the scatter it left in"
    assert trip["knows"]
    assert trip["runs"] < trip["rows"] / 2, (
        "runs of [id, count], not a number per row: {} runs for {} "
        "rows".format(trip["runs"], trip["rows"]))
    old = out["oldLayout"]
    assert old["knows"] is False and old["knowsBareArray"] is False
    assert old["anyNamed"] is False

    named = out["named"]
    assert named["unchanged"], "a named layout is never guessed at again"
    assert named["copiesStillByHand"], (
        "not even the props a guess would have swept in")
    assert named["ceiling"] == 2, (
        "the ceiling is the highest name the field came back with")


def test_a_new_stroke_joins_the_scatter_its_mix_could_have_made(tmp_path):
    """One scatter is one mix on one layer, however many strokes painted
    it: painting more beeches joins the beeches, and switching to grass
    starts on the grass."""

    out = _run_harness(tmp_path)
    assert out["moreBeeches"] == 2, "the beech mix joins the beeches"
    # The cover scatter holds a flower as well as grass, and a grass-only
    # mix could not have made the flower: it starts afresh rather than
    # swelling a scatter it is not.
    assert out["moreGrassWithoutTheFlower"] == 4
    assert out["theWholeCoverMix"] == 1, "the whole cover mix joins the cover"
    assert out["ferns"] == 5, "a mix nothing on the layer came from is new"
    assert out["grassOnLayerTwo"] == 3, "and the grass on layer 2 is its own"


def test_one_planting_per_scatter_per_layer(tmp_path):
    out = _run_harness(tmp_path)
    planting = out["planting"]
    assert planting["members"] == 15 + 26 + 50 + 36 + 319
    assert planting["name"] == "Scatter #2 of 446 props"
    assert planting["sameObject"], "every beech answers with the same planting"
    assert planting["byHand"] is None
    # The box reaches the top of the tallest tree, not twice its crown.
    assert planting["boxTop"] > 31.6 * 0.8, planting["boxTop"]

    moved = out["moved"]
    assert moved["own"] == 1 and moved["left"] == 445, (
        "a tree grouped onto another layer keeps its number and is a "
        "planting there, apart from the ones it left")


def test_everything_that_places_or_restores_a_prop_keeps_its_scatter():
    js = STUDIO_JS.read_text(encoding="utf-8")

    # A SCATTER NAMES WHAT IT PLACES, once per stroke.
    run = _whole(js, "async function runScatter(region, options)")
    assert "if (stroke && !stroke.scatterId) stroke.scatterId = settings.scatterId || scatterIdFor(home.id);" in run
    assert "record.scatter = scatterId;" in run
    assert "{ intoLayer: home.id, owns, scatterId }" in run, (
        "a redone fill paints back into the scatter it painted before")
    end = _whole(js, "function endBrushStroke(stroke)")
    assert "scatterId: records[0].scatter || 0" in end, (
        "and so does a redone stroke")

    # BOTH RESTORES, the study's layout and a scene.
    restore = _whole(js, "function restoreProps(given)")
    assert "if (entry.scatter) record.scatter = +entry.scatter;" in restore
    assert "settleRestoredScatters(knowsScatters);" in restore
    assert "layoutKnowsScatters(layout.props)" in restore
    assert js.count("if (entry.scatter) record.scatter = +entry.scatter;") == 2
    assert "settleRestoredScatters(layoutKnowsScatters(scene_.props));" in js

    # A DELETE UNDONE puts it back into its scatter, one prop or many.
    many = _whole(js, "function deletePropsWithUndo(records)")
    assert "scatter: record.scatter }));" in many
    assert "if (one.scatter) again.scatter = one.scatter;" in many
    one = _whole(js, "function deletePropWithUndo(record)")
    assert "scatter: record.scatter };" in one
    assert "if (gone.scatter) again.scatter = gone.scatter;" in one

    # THE HOVER AND ITS DELETE ask the scatter, in the drawer's words.
    hover = _whole(js, "function setHoveredProp(record)")
    assert "plantingBounds(planting)" in hover
    assert "plantingName(planting)" in hover
    assert "plantingRecords(planting)" in js

    # And the count that guessed is gone, not merely unused.
    assert "BULK_ON_A_LAYER" not in js
    assert "function plantingFor(" not in js
