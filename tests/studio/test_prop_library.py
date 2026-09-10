"""The prop library, and the two rules that keep it affordable.

A photoscanned tree is 17 million triangles behind a gigabyte of source
files. Everything here exists because that number has to come down before
the browser ever sees it, and because the studio has to be honest about
which of its props are worth a shadow pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "bench" / "studio"
STATIC = STUDIO / "static"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import app as studio_app  # noqa: E402


@pytest.fixture()
def props(tmp_path, monkeypatch):
    folder = tmp_path / "props"
    folder.mkdir()
    (folder / "described.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    (folder / "undescribed.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    (folder / "props.json").write_text(json.dumps({
        "library": "a test",
        "props": [{
            "key": "described", "label": "Described", "file": "described.glb",
            "group": "site", "sizeMetres": [1.2, 0.8, 1.2],
            "credit": "nobody", "licence": "CC0 1.0",
        }, {
            "key": "gone", "label": "Gone", "file": "gone.glb", "group": "site",
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(studio_app, "PROPS_DIR", folder)
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", tmp_path / "settings.json")
    return folder, TestClient(studio_app.create_app())


def test_a_model_the_manifest_does_not_mention_is_still_offered(props):
    """The manifest used to be the authority on what exists, which was right
    while the props shipped with the studio. Now that the folder is Param's,
    a model he drops into it should appear without his having to write about
    it first. What the manifest still carries is what a file cannot: the
    credit, and the real-world size."""

    _folder, client = props
    payload = client.get("/api/props").json()
    keys = {entry["key"]: entry for entry in payload["props"]}
    assert "described" in keys and "undescribed" in keys
    assert keys["undescribed"]["undescribed"] is True
    assert keys["described"]["sizeMetres"] == [1.2, 0.8, 1.2]


def test_a_manifest_entry_with_no_file_is_not_offered(props):
    """It would 404 the moment anybody clicked it."""

    _folder, client = props
    keys = [entry["key"] for entry in client.get("/api/props").json()["props"]]
    assert "gone" not in keys


def test_the_prop_folder_row_counts_models(props):
    folder, client = props
    row = client.get("/api/props/folder").json()
    assert row["exists"] is True and row["count"] == 2
    assert row["path"] == str(folder)


def test_a_prop_is_scaled_only_when_the_manifest_says_how_tall_it_is():
    """Poly Haven models are authored in metres and correct as they come.
    Scaling one to a guessed height is how a fire hydrant ends up the size
    of a house, so the rule is: scale on an explicit heightMetres, and
    otherwise trust the file."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = js[js.index("async function loadPropTemplate"):]
    body = body[:body.index("\n}\n")]
    # The fallback and the guard, exactly. An earlier version of this test
    # accepted "wanted" and "heightMetres" appearing anywhere in the
    # function, which the OLD code satisfied perfectly while making every
    # prop one metre tall: a photoscanned pine tree arrived in the scene the
    # size of a fire hydrant. Measured in a live browser before it was found.
    assert "+entry.heightMetres > 0 ? +entry.heightMetres : null;" in body, (
        "an absent height means trust the file, not scale it to one metre"
    )
    assert "if (wanted && height > 0.0001)" in body, (
        "the scale is conditional on the manifest declaring a height"
    )


def test_not_everything_casts_a_shadow_and_size_decides_not_group_alone():
    """Draw calls become the bottleneck before triangles do, and a shadow
    pass over a hundred tufts of grass costs what one over a hundred
    buildings costs. But a tree is planting too, and its shadow is half the
    reason to place it, so the height decides."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'const SHADOWLESS = new Set(["planting"]);' in js
    assert "function castsShadow(entry)" in js
    assert "return height === null || height > 1.2;" in js
    # The line that decides, not the line that assigns. An earlier version of
    # this test asserted only "child.castShadow = casts", which survives
    # `const casts = true` untouched: the mutation was proved to slip past it.
    body = js[js.index("async function loadPropTemplate"):]
    body = body[:body.index("\n}\n")]
    assert "const casts = castsShadow(entry);" in body
    assert "child.castShadow = casts;" in body


def test_the_grid_uses_the_group_the_manifest_has_always_carried():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = js[js.index("function buildPropTiles"):]
    body = body[:body.index("\n}\n")]
    # The lines that do the work. Asserting only that the WORDS "entry.group"
    # and "tile-family" appear passes a grid that computes a heading and then
    # prints nothing in it, which is a mutation this test was caught missing.
    assert 'group = entry.group || "other";' in body
    assert "heading.textContent = group;" in body
    assert 'heading.className = "tile-family";' in body
    assert "sizeMetres" in body, (
        "scale is communicated as text, which is Blender's own advice and the "
        "only method in the survey that does not put a stock human being in "
        "the picture"
    )


def test_the_fetch_script_never_builds_a_download_url_by_substitution():
    """Poly Haven's shared geometry .bin is served from the 8k path inside
    the 1k, 2k and 4k entries alike, because the geometry does not change
    with the texture resolution. A URL built by swapping "8k" for "1k"
    fetches a file that does not exist."""

    source = (REPO / "tools" / "props" / "fetch.mjs").read_text(encoding="utf-8")
    assert "entry.url" in source and "bundle.url" in source
    assert "dl.polyhaven.org" not in source, (
        "no download URL is written down here; every one comes from the API"
    )


def test_the_fetch_script_pins_one_sharp():
    """@gltf-transform/functions pulls ndarray-pixels, which depends on its
    OWN sharp at a different version. Two native libvips builds in one
    process do not fail loudly: the second .node fails to load and every
    resize on the first then throws "colourspace: parameter space not set"
    while metadata() goes on working. Without the override, every texture in
    the library silently keeps its full size."""

    manifest = json.loads(
        (REPO / "tools" / "props" / "package.json").read_text(encoding="utf-8"))
    assert manifest["overrides"]["sharp"] == manifest["dependencies"]["sharp"]
    assert not manifest["dependencies"]["sharp"].startswith("^"), (
        "a range would let npm resolve two versions again"
    )


def test_the_notice_names_every_library_actually_in_the_folder():
    """A licence claim nobody checks is exactly the kind that gets
    believed, so this one is checked.

    NOTICE.txt used to open with the hard-coded sentence "Every model in
    this folder is from Poly Haven and is CC0 1.0". fetch.mjs rewrites
    the file on any run, so fetching five grasses restated that over a
    library holding twenty Quixel Megascans assets under the Fab
    Standard License. The per-model ENTRIES were right the whole time --
    they come from the merged manifest -- but the sentence above them
    was false, which is the worse half to get wrong.
    """

    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "bench" / "studio" / "props-hd"
    manifest = json.loads((root / "props.json").read_text(encoding="utf-8"))
    notice = (root / "NOTICE.txt").read_text(encoding="utf-8")

    wanted = set()
    for prop in manifest["props"]:
        source = prop.get("source") or ""
        if "polyhaven" in source:
            wanted.add("Poly Haven")
        elif "ambientcg" in source.lower():
            wanted.add("ambientCG")
        elif "fab.com" in source:
            wanted.add("Quixel Megascans, via Fab")
    assert wanted, "the manifest names no sources at all"
    for library in wanted:
        assert library in notice, (
            "{} is in the folder and not in the notice".format(library))

    # And the false claim cannot come back.
    assert "Every model in this folder is from Poly Haven" not in notice

    # Every model is credited by name, not merely counted.
    for prop in manifest["props"]:
        assert prop["key"] in notice, prop["key"]


# What Param retired on 2026-09-10: "i think we can remove some assets
# too, the hydrants, the long planter, barrel, utility box, barrier,
# chainlink fence, coastline, rockface, cliff wall, powerpole,
# mountainside, costal cliff, 1 and 2, cliff outcrop, wet floor sign,
# cement bag, rock, all moon rocks. This is in props and scatter."
# Numbered variants of a thing he named go with it -- rock face 1 and 2,
# coastal cliff 1 and 2, road barrier and road barrier low, utility box
# and cabinet, Rock and Rock small, moon rocks 1 to 7. Loose name
# matches he did NOT name stay, because small site rocks are good
# scatter fodder: rock_moss_set_01/02, planter_box_01, potted_plant_02,
# sand_rocks_small_01, ms_forest_rocks_small, namaqualand_rocks_01.
RETIRED = {
    "props": ["barrel", "barrier", "rock"],
    "props-hd": [
        "Barrel_02", "WetFloorSign_01", "cement_bag", "coast_line_01",
        "coast_line_02", "coastal_cliff_01", "coastal_cliff_02",
        "concrete_road_barrier", "concrete_road_barrier_02", "fire_hydrant",
        "modular_chainlink_fence", "modular_electricity_poles",
        "moon_rock_01", "moon_rock_02", "moon_rock_03", "moon_rock_04",
        "moon_rock_05", "moon_rock_06", "moon_rock_07", "mountainside",
        "namaqualand_cliff_01", "namaqualand_cliff_02", "planter_box_03",
        "rock_07", "rock_09", "rock_face_01", "rock_face_02",
        "utility_box_01", "utility_box_02",
    ],
}


def test_a_retired_prop_is_gone_from_the_folder_and_not_merely_the_manifest():
    """The folder is the authority, not the manifest -- see
    test_a_model_the_manifest_does_not_mention_is_still_offered. So
    deleting a manifest entry does not retire a prop: it strips the prop
    of its credit and its real size and goes on offering it as an
    undescribed model, which is worse than leaving it alone. The MODEL
    has to go. This test is what stops a future tidy-up from doing only
    the bookkeeping half."""

    for library, keys in RETIRED.items():
        root = REPO / "bench" / "studio" / library
        manifest = json.loads((root / "props.json").read_text(encoding="utf-8"))
        described = {prop["key"] for prop in manifest["props"]}
        on_disk = {path.stem for path in root.glob("*.glb")}
        for key in keys:
            assert key not in described, (
                "{}/{} is back in the manifest".format(library, key))
            assert key not in on_disk, (
                "{}/{}.glb is still in the folder, so the studio still "
                "offers it -- as an undescribed prop now, with no credit "
                "and no size".format(library, key))


def test_no_model_in_either_library_is_a_stranger_to_its_manifest():
    """Three ways a library drifts, all of them silent. A model with no
    entry loses its credit and its size. An entry with no model is a tile
    that 404s the moment anybody clicks it. A thumbnail with no model is
    dead weight that still gets served."""

    for library in ("props", "props-hd"):
        root = REPO / "bench" / "studio" / library
        manifest = json.loads((root / "props.json").read_text(encoding="utf-8"))
        named = {prop["file"] for prop in manifest["props"]}
        on_disk = {path.name for path in root.glob("*.glb")}
        assert named == on_disk, (
            "{}: entries with no model {}, models with no entry {}".format(
                library, sorted(named - on_disk), sorted(on_disk - named)))
        for thumb in root.glob("*.glb.thumb.png"):
            model = thumb.name[: -len(".thumb.png")]
            assert model in on_disk, (
                "{}/{} is a thumbnail of nothing".format(library, thumb.name))


def test_a_retired_slug_can_still_be_fetched_back_by_name():
    """props-hd is gitignored, so git cannot undo a delete. Cutting the
    catalogue line as well would have made 37 MB of retired models
    unrecoverable by any route at all. They are MARKED instead: a bare
    run skips them, and naming one still fetches it."""

    source = (REPO / "tools" / "props" / "fetch.mjs").read_text(encoding="utf-8")
    for key in RETIRED["props-hd"]:
        line = [row for row in source.split("\n")
                if 'slug: "{}"'.format(key) in row]
        assert len(line) == 1, "{}: {} catalogue lines".format(key, len(line))
        assert "retired: true" in line[0], (
            "{} is not marked retired, so a bare fetch downloads it "
            "again".format(key))

    assert "? LIST.filter((item) => wanted.includes(item.slug))" in source, (
        "the named path must search the WHOLE list, retired included, or "
        "nothing ever comes back"
    )
    assert ": LIST.filter((item) => !item.retired);" in source, (
        "a bare run must skip the retired entries"
    )


def test_every_notice_writer_derives_its_libraries_from_the_manifest():
    """Three tools write NOTICE.txt and any of them can run last, so the
    rule has to hold in all three. fetch.mjs claimed everything was Poly
    Haven CC0 over twenty Fab assets; ingest.mjs claimed "two libraries"
    over a folder that had held three since the decals arrived. Both were
    hand-written sentences above correctly derived entries, which is the
    worse half to get wrong."""

    # THE JAVASCRIPT WRITERS SHARE ONE DERIVATION, notice.mjs, because a
    # third copy for split.mjs is where a rule stops being a habit and
    # becomes a module. Each of them must import it; the derivation is
    # checked once, there. The Python writer keeps its own, and is
    # checked in full.
    shared = (REPO / "tools" / "props" / "notice.mjs").read_text(encoding="utf-8")
    for name in ("fetch.mjs", "ingest.mjs", "split.mjs"):
        source = (REPO / "tools" / "props" / name).read_text(encoding="utf-8")
        assert 'import { noticeFor } from "./notice.mjs";' in source, (
            name + " must credit through the shared writer")
        assert "noticeFor(" in source, name + " imports it and never calls it"
        assert "NOTICE.txt" in source
    writers = {
        "notice.mjs": (REPO / "tools" / "props" / "notice.mjs"),
        "fetch_decals.py": (REPO / "tools" / "props" / "fetch_decals.py"),
    }
    false_claims = (
        "Every model in this folder is from Poly Haven",
        "come from two libraries",
    )
    for name, path in writers.items():
        source = path.read_text(encoding="utf-8")
        if name == "fetch_decals.py":
            assert "NOTICE.txt" in source, "{} no longer writes it".format(name)

        # A hard-coded notice line is a bare string literal in the list
        # being joined. Prose ABOUT the old bug is not, and all three of
        # these files carry that prose deliberately -- searching the
        # whole source would ban the explanation along with the defect.
        for line in source.split("\n"):
            stripped = line.strip()
            if not stripped.startswith(('"', "'")):
                continue
            for claim in false_claims:
                assert claim not in stripped, (
                    "{} hard-codes a library claim again: {}".format(
                        name, stripped))

        # And the positive half, which is what actually keeps it true: the
        # header is a count per library, taken from the props themselves.
        counted = ("  {}  ({})" in source              # python
                   or "  ${line}  (${count})" in source)  # javascript
        assert counted, (
            "{} must emit one counted line per library found in the "
            "manifest, not a sentence somebody typed".format(name))
        assert "polyhaven" in source and "ambientcg" in source.lower(), (
            "{} must sort each source into its library to count them, and "
            "a writer that knows only some of the libraries will drop the "
            "rest from the header".format(name)
        )
        assert "licence unstated" in source, (
            "{} must have something to say about a prop whose licence is "
            "missing; falling back to a named licence is how a wrong one "
            "gets asserted".format(name)
        )


def test_a_row_of_variants_is_split_into_a_family_and_the_row_leaves_the_folder():
    """Poly Haven ships a grass as a row of tufts fused into one mesh, and
    the fetch brought each one in as a single model 5.6 m wide. Scattered
    as-is every placement dropped the whole line and claimed a keep-out
    disc the width of the line: a 3 m brush fitted about one. After the
    split the same brush fits 357, in 13 shapes.

    The row itself has to LEAVE the folder, because the folder is the
    authority and a row left in place goes on being offered."""

    import re

    root = REPO / "bench" / "studio" / "props-hd"
    manifest = json.loads((root / "props.json").read_text(encoding="utf-8"))
    families = {}
    for prop in manifest["props"]:
        if prop.get("family"):
            families.setdefault(prop["family"], []).append(prop)
    assert len(families) >= 20, "the split has been run"
    keys = {p["key"] for p in manifest["props"]}
    for family, members in families.items():
        assert family not in keys, (
            "{}: the row is still in the manifest beside its variants".format(family))
        assert not (root / (family + ".glb")).exists(), (
            "{}: the row is still in the folder, so it is still offered".format(family))
        assert (root / "rows" / (family + ".glb")).exists(), (
            "{}: the row's bytes are kept, out of the scanned folder".format(family))
        assert len(members) >= 2, family
        for member in members:
            # __v3 from the sweep, __tiny_a from a named node.
            assert re.fullmatch(family + r"__[a-z0-9_+]+", member["key"]), member["key"]
            assert member["familyLabel"] == members[0]["familyLabel"], member["key"]
            assert (root / member["file"]).exists(), member["file"]
            assert member["variant"] >= 1
            # Sized in metres, not in quantisation units: every variant
            # first came back "65534 across", and then "2.0 across", for
            # the reasons fetch.mjs's boundsOf spells out.
            assert max(member["sizeMetres"]) < 40, member["key"]
            assert min(member["sizeMetres"]) > 0.001, member["key"]
            # Credited under the family's own source: the split is ours,
            # the model is theirs.
            assert member["source"] == members[0]["source"]

    tool = (REPO / "tools" / "props" / "split.mjs").read_text(encoding="utf-8")
    assert "const GAP_FRACTION = 0.03;" in tool
    # A fragment is not a variant: grass_medium_01 produced an eleventh
    # tuft of forty triangles two centimetres across, a stray blade. A
    # threshold of zero would make it a species again.
    assert "const FRAGMENT_FRACTION = 0.01;" in tool
    assert "byCluster[i].length < total * FRAGMENT_FRACTION" in tool
    assert "getBounds(doc.getRoot().listScenes()[0])" in tool, (
        "world-space bounds, or the size is the quantisation cube")
    assert "cloneDocument(source)" in tool
    assert 'import { noticeFor } from "./notice.mjs";' in tool


def test_a_row_of_named_nodes_is_split_by_name_and_parts_fold_into_one_plant():
    """Poly Haven never fused the variants: grass_medium_01 arrives as
    SEVENTEEN named nodes, tiny_a to large_c. It was fetch.mjs's own
    join(), with its default keepNamed false, that welded them into one
    primitive, and the connected-component sweep then reverse-engineered
    boundaries the file already had, finding eight of seventeen.

    So the fetch keeps named nodes, and the split cuts on them first. A
    node is a PART, not a variant, when its footprint sits inside
    another's: pachira_aquatica_01 is bark_a..d and leaves_a..d, four
    trees, and a trunk stands inside its own canopy."""

    fetch = (REPO / "tools" / "props" / "fetch.mjs").read_text(encoding="utf-8")
    assert "join({ keepNamed: true })," in fetch
    tool = (REPO / "tools" / "props" / "split.mjs").read_text(encoding="utf-8")
    assert "if (topMeshNodes(source).length >= MIN_VARIANTS) {" in tool
    assert "return splitByNodes(io, manifest, slug, entry, source, write);" in tool
    assert "const PART_OVERLAP = 0.8;" in tool
    assert "return ix * iz >= PART_OVERLAP * Math.min(areaA, areaB);" in tool

    root = REPO / "bench" / "studio" / "props-hd"
    manifest = json.loads((root / "props.json").read_text(encoding="utf-8"))
    by_family = {}
    for prop in manifest["props"]:
        if prop.get("family"):
            by_family.setdefault(prop["family"], []).append(prop["key"])
    grass = sorted(by_family["grass_medium_01"])
    assert len(grass) == 17, grass
    assert "grass_medium_01__tiny_a" in grass and "grass_medium_01__large_c" in grass
    pachira = sorted(by_family["pachira_aquatica_01"])
    assert pachira == ["pachira_aquatica_01__" + n for n in "abcd"], (
        "bark and leaves are parts of one tree, not two variants")

    # The drawer names the tile after the family, which the split now
    # writes on every variant; "Grass medium tiny a" has no number to strip.
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "if (entry.familyLabel) return entry.familyLabel;" in js


def test_a_species_is_a_family_and_every_placement_is_a_variant():
    """The drawers show a family once and every placement draws one of
    its variants, so a field of one species is a field of eight shapes.
    Param: "each type is one object we can make many variants of"."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "function familyOf(entry) { return entry.family || entry.key; }" in js
    assert "function familyEntries(entries)" in js
    assert "function pickVariant(type, random)" in js

    props = js[js.index("function buildPropTiles"):]
    props = props[:props.index("\n}\n")]
    assert "familyEntries(state.propLibrary)" in props
    assert "const variant = pickVariant(entry.key);" in props
    assert "carryNewProp(variant);" in props

    scatter = js[js.index("function renderShelfScatter"):]
    scatter = scatter[:scatter.index("\n}\n")]
    assert "familyEntries(state.propLibrary)" in scatter
    # The height ceiling is gone: it hid the five beech forest trees and
    # the study tree, which was the first thing Param noticed missing.
    assert "sizeMetres[1] <= 12" not in js, (
        "spacing is a multiple of each item's own width, so a 30 m tree "
        "keeps its own clearance and needs no fence")

    solve = js[js.index("function scatterSolve(region, salt)"):]
    solve = solve[:solve.index("\n}\n")]
    assert "const type = pickVariant(pick(), random);" in solve, (
        "the VARIANT is drawn from the same seeded stream, before its "
        "footprint is measured, so a replay deals the same shapes")
    assert "familyMembers(s.type).length" in solve

    run = js[js.index("async function runScatter(region, options)"):]
    run = run[:run.index("\n}\n")]
    assert "for (const member of familyMembers(s.type)) await ensurePropTemplate(member.key);" in run, (
        "every variant's template in hand before placing, or placeProp "
        "plants a primitive")
