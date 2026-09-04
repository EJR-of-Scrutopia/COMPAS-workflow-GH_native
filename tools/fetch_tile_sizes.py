"""Give every material in the library its real-world size, in metres.

QS Intelligence never needed this and its material.json does not carry it.
It did not need it because of the one unit rule: the image IS one unit's
face, and a Grasshopper element carries its own length, width and height in
millimetres, so one repeat per face is the right physical scale whatever
size the element happens to be.

A three.js ground has no element. To lay a gravel texture over a sixty
metre disc the studio has to know how much gravel one picture shows, and
guessing is how a vault ends up standing on cobbles the size of cars.

Both libraries the stack was built from publish the figure, and both
material.json files record which library and which asset they came from,
so the number can be fetched rather than typed 158 times:

    Poly Haven   `dimensions` on /assets and /info, in MILLIMETRES,
                 two elements, with float noise from a unit conversion.
    ambientCG    `dimensions` on /api/v3/assets, in CENTIMETRES, an object
                 of width/height/depth, and 0 where it does not know, which
                 older and procedural assets frequently are.

Nothing is written into the library. The result lands in the studio's own
sidecar, bench/studio/materials.json, keyed by "family/name", so Param's
library stays exactly as he curated it and the studio's notes survive it
being moved or regenerated.

    python tools/fetch_tile_sizes.py <library folder>
    python tools/fetch_tile_sizes.py <library folder> --cache <folder>

The second form reads catalogues already downloaded into a folder, as
ph_textures.json and acg_*.json, for a machine whose shell has no network.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIDECAR = HERE.parent / "bench" / "studio" / "materials.json"

POLY_HAVEN = "https://api.polyhaven.com/assets?t=textures"
AMBIENTCG = ("https://ambientcg.com/api/v3/assets"
             "?type=Material&include=dimensions&limit=1000&offset={}")

# Poly Haven's terms ask for this, and it costs one header.
AGENT = "Bench Studio material library (Ananke Eidos)"


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def poly_haven_sizes(cache: Path | None) -> dict:
    """slug -> [width_m, height_m]. One request returns the whole catalogue,
    so per-asset /info calls are never needed."""

    if cache:
        catalogue = json.loads(
            (cache / "ph_textures.json").read_text(encoding="utf-8"))
    else:
        catalogue = get_json(POLY_HAVEN)
    sizes = {}
    for slug, entry in (catalogue or {}).items():
        dimensions = entry.get("dimensions")
        if not isinstance(dimensions, (list, tuple)) or len(dimensions) < 2:
            continue
        pair = [round(float(dimensions[0]) / 1000.0, 4),
                round(float(dimensions[1]) / 1000.0, 4)]
        if pair[0] > 0 and pair[1] > 0:
            sizes[slug.lower()] = pair
    return sizes


def ambientcg_sizes(cache: Path | None) -> dict:
    """id -> [width_m, height_m], skipping the zeros, which mean unknown."""

    sizes = {}
    pages = []
    if cache:
        pages = [json.loads(path.read_text(encoding="utf-8"))
                 for path in sorted(cache.glob("acg_*.json"))
                 if "probe" not in path.name]
    else:
        # Follow the API's own next-page link rather than counting offsets.
        # ambientCG silently caps `limit` at 500 however much you ask for, so
        # walking in strides of the number you REQUESTED skips half the
        # catalogue without any error to notice: asking for 1000 and stepping
        # 1000 reads assets 0-499, 1000-1499, 2000-2008 and quietly loses the
        # rest. nextPageHttp is computed from what was actually served.
        url = AMBIENTCG.format(0)
        seen = set()
        while url and url not in seen:
            seen.add(url)
            page = get_json(url)
            pages.append(page)
            url = page.get("nextPageHttp")
    for page in pages:
        for entry in page.get("assets") or []:
            dimensions = entry.get("dimensions") or {}
            try:
                pair = [round(float(dimensions.get("width", 0)) / 100.0, 4),
                        round(float(dimensions.get("height", 0)) / 100.0, 4)]
            except (TypeError, ValueError):
                continue
            # A zero is ambientCG saying it does not know. Read as a size it
            # would make the repeat count infinite.
            if pair[0] > 0 and pair[1] > 0:
                sizes[str(entry.get("id", "")).lower()] = pair
    return sizes


# A published size is the size of the WHOLE source photograph, and the
# picture in the library is a crop out of it: QS cuts one brick, one plank,
# one tile out of a wall before it enters the stack, and records what
# fraction of the source it took. Multiplying the two is what turns "this
# photograph covers two metres of wall" into "this picture is one 223 by 63
# millimetre brick", which is the number the studio actually needs.
def apply_crop(size, provenance):
    fractions = provenance.get("crop_fractions")
    if not isinstance(fractions, (list, tuple)) or len(fractions) < 4:
        return size          # no crop recorded: the picture IS the source
    try:
        width, height = float(fractions[2]), float(fractions[3])
    except (TypeError, ValueError):
        return size
    if not (0 < width <= 1 and 0 < height <= 1):
        return size
    return [round(size[0] * width, 4), round(size[1] * height, 4)]


# Where ambientCG recorded nothing -- and it recorded nothing for most
# assets published before it started measuring -- the family says what a
# sensible unit is. These are assumptions, not measurements, and they are
# written down as such so the panel can mark them and Param can correct any
# one of them in a single field. For the families whose pictures are a patch
# of a continuous surface rather than a unit, the number is arbitrary
# anyway, and a metre and a half of fair-faced concrete is what a
# photographer stands back to frame.
FAMILY_DEFAULTS = {
    "brick": [0.215, 0.065],      # a stock brick's stretcher face
    "clay": [0.15, 0.15],         # a glazed wall tile
    "slate": [0.5, 0.25],         # a roofing slate
    "stone": [0.6, 0.3],          # an ashlar block
    "timber": [1.2, 0.15],        # a board
    "concrete": [1.5, 1.5],       # a patch
    "plaster": [1.5, 1.5],        # a patch
    "aggregate": [1.0, 1.0],      # a patch
    "paint": [1.0, 1.0],          # a patch
    "metal": [1.0, 1.0],          # a patch of mill sheet
    "plastic": [0.6, 0.6],        # a board
    "mortar": [1.0, 1.0],
    "glass": [1.0, 1.0],
    "mineral-wool": [1.2, 0.6],
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path,
                        help="the materials folder of the library")
    parser.add_argument("--cache", type=Path, default=None,
                        help="read catalogues already downloaded here")
    parser.add_argument("--sidecar", type=Path, default=SIDECAR)
    arguments = parser.parse_args(argv)

    if not arguments.library.is_dir():
        print("no such folder: {}".format(arguments.library))
        return 1

    print("reading the catalogues...")
    haven = poly_haven_sizes(arguments.cache)
    ambient = ambientcg_sizes(arguments.cache)
    print("  Poly Haven {} sizes, ambientCG {} sizes".format(
        len(haven), len(ambient)))

    try:
        stored = json.loads(arguments.sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    tiles = stored.setdefault("tileMetres", {})
    provenances = stored.setdefault("tileSource", {})

    found = measured = assumed = 0
    assumptions = []
    for family in sorted(p for p in arguments.library.iterdir() if p.is_dir()):
        for folder in sorted(p for p in family.iterdir() if p.is_dir()):
            if not (folder / "colour.jpg").is_file():
                continue
            found += 1
            key = "{}/{}".format(family.name, folder.name)
            try:
                provenance = json.loads(
                    (folder / "material.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                provenance = {}
            asset = str(provenance.get("assetId")
                        or provenance.get("sourceName") or "").lower()
            site = (provenance.get("site") or "").lower()
            # The site is checked first but both are searched, because a
            # material whose site went unrecorded is still worth finding and
            # the two libraries' asset ids do not collide in practice.
            size = (ambient.get(asset) if "ambientcg" in site
                    else haven.get(asset) if "poly" in site else None)
            if size is None:
                size = ambient.get(asset) or haven.get(asset)
            if size is not None:
                cropped = apply_crop(size, provenance)
                tiles[key] = cropped
                provenances[key] = "{} {}{}".format(
                    provenance.get("site") or "published", asset,
                    ", cropped" if cropped != size else "")
                measured += 1
                continue
            fallback = FAMILY_DEFAULTS.get(family.name)
            if fallback is None:
                continue
            # An existing measurement, or something Param typed himself, is
            # never overwritten by an assumption.
            if provenances.get(key, "").startswith("assumed") or key not in tiles:
                tiles[key] = list(fallback)
                provenances[key] = "assumed ({})".format(family.name)
                assumed += 1
                assumptions.append("{} <- {} x {} m ({} {})".format(
                    key, fallback[0], fallback[1],
                    provenance.get("site") or "?", asset or "?"))

    arguments.sidecar.parent.mkdir(parents=True, exist_ok=True)
    arguments.sidecar.write_text(
        json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("{} materials: {} measured from the publisher, {} assumed from "
          "the family".format(found, measured, assumed))
    if assumptions:
        print("\nassumed, because the publisher records no size for these.\n"
              "Correct any of them in the studio's material panel:")
        for line in assumptions:
            print("  " + line)
    print("\nwritten to {}".format(arguments.sidecar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
