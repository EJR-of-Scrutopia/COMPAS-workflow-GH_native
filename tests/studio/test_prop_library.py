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
