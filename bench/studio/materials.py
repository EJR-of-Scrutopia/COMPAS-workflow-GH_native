"""The material library: a folder of folders, read and never written.

The shape is Param's own, already curated inside QS Intelligence across 158
materials, and it is inherited here verbatim rather than reinvented:

    <root>/<family>/<material>/colour.jpg
                              /normal.png
                              /height.png
                              /roughness.png
                              /ao.png
                              /material.json
                              /lod/colour-1024.jpg
                              /lod/colour-256.jpg
                              /lod/normal-1024.png
                              ...

Two of its rules do all the work. The maps are linked by living in the same
folder and never by their names, so renaming a material is renaming its
folder and nothing else needs telling. And a material IS a folder holding a
colour.jpg, so the library has no index file to fall out of step with the
files: this module walks the tree and that is the truth.

A tier under lod/ exists only when the master's long edge exceeds it, and
nothing was ever upscaled, so a missing tier is not an error, it means the
master was already smaller and the master is what you get.

Nothing in here writes. Param's library is his, and the studio's own facts
about a material -- the real-world size of the unit the picture shows,
which QS never needed because a Grasshopper element carries its own
millimetres -- live in a sidecar beside the studio instead, keyed by
"family/name" so they survive the library being moved or regenerated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

# The five maps, in the order a person reads them: what colour is it, what
# shape is its surface, how deep, how shiny, how shaded in its own crevices.
MAP_FILES = {
    "colour": "colour.jpg",
    "normal": "normal.png",
    "height": "height.png",
    "roughness": "roughness.png",
    "ao": "ao.png",
}

# Colour is JPEG and everything else is PNG, and the asymmetry is deliberate
# rather than historical: a JPEG artefact is invisible in a colour map and
# becomes false relief in a normal map.
MAP_SUFFIX = {kind: Path(name).suffix for kind, name in MAP_FILES.items()}

# Largest first, because resolution walks down from what was asked for.
TIERS = (1024, 256)

LOD_DIR = "lod"

# A material is a folder with this in it. Nothing else qualifies, which is
# how a family folder, a lod folder and a stray archive all fail to be
# mistaken for materials.
MARKER = MAP_FILES["colour"]


def _label(name: str) -> str:
    """"stock-red" reads as "Stock red". The folder name is the identity and
    this is only how it is spoken."""

    words = name.replace("_", "-").split("-")
    if not words:
        return name
    return " ".join([words[0].capitalize()] + words[1:])


def tier_file(kind: str, px: int) -> str:
    """The name a tier goes by: lod/colour-256.jpg, lod/normal-1024.png."""

    return "{}-{}{}".format(kind, px, MAP_SUFFIX[kind])


def resolve(root: Path, family: str, name: str, kind: str,
            px: Optional[int] = None) -> Optional[Path]:
    """The best file for this map at or below the size asked for.

    px is snapped DOWN to a real tier, and then it is that tier or the
    master, with nothing in between. That is not a shortcut, it follows from
    the library's own rule: a tier is written only when the master's long
    edge exceeds it, so the largest tier at or below px being absent means
    the master is already no larger than px and the master is therefore the
    right answer. Taking a smaller tier instead would hand back a blurrier
    picture than the file the reader could have had.

    px below the smallest tier, or above the largest, is not an error. It
    snaps to the nearest tier that exists in the scheme, and a px of zero or
    None means the master and nothing else.
    """

    if kind not in MAP_FILES:
        return None
    folder = root / family / name
    master = folder / MAP_FILES[kind]
    if px:
        wanted = next((tier for tier in TIERS if tier <= px), None)
        if wanted:
            candidate = folder / LOD_DIR / tier_file(kind, wanted)
            if candidate.is_file():
                return candidate
    return master if master.is_file() else None


def _read_provenance(folder: Path) -> Dict:
    """material.json, or an empty dict. It is provenance, not instruction:
    where the picture came from, under what licence, cropped out of what.
    The plugin never reads it and neither does the viewport. It is read here
    only for the two facts a reader can use, `site` and `source`, so a
    credit line can be shown, and for `dimensions` if a fetch script wrote
    one."""

    try:
        loaded = json.loads((folder / "material.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def scan(root: Optional[Path]) -> List[Dict]:
    """Every material under root, sorted by family then name.

    Two levels of directory and one existence test per map. No image is
    opened and no header is parsed: asking a 4096 pixel PNG how big it is
    costs a file open, and asking 158 of them five times over costs a
    noticeable pause on a folder that lives in OneDrive.
    """

    if not root:
        return []
    try:
        families = sorted(entry for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return []

    found: List[Dict] = []
    for family in families:
        try:
            children = sorted(entry for entry in family.iterdir() if entry.is_dir())
        except OSError:
            continue
        for folder in children:
            if not (folder / MARKER).is_file():
                continue
            maps = [kind for kind, filename in MAP_FILES.items()
                    if (folder / filename).is_file()]
            provenance = _read_provenance(folder)
            found.append({
                "key": "{}/{}".format(family.name, folder.name),
                "family": family.name,
                "name": folder.name,
                "label": _label(folder.name),
                "maps": maps,
                "site": provenance.get("site"),
                "source": provenance.get("source"),
                "licence": provenance.get("licence"),
                "tileMetres": _tile_metres(provenance),
            })
    return found


def _tile_metres(provenance: Dict) -> Optional[List[float]]:
    """The real-world size of the unit the picture shows, in metres.

    QS records no such thing and did not need to: its images are one unit's
    face and a Grasshopper element carries its own millimetres, so one
    repeat per face is right at any size. A three.js ground has no element,
    so the number has to come from somewhere, and the two libraries worth
    fetching from both publish it. Poly Haven gives millimetres in
    `dimensions`; ambientCG gives centimetres in a `dimensions` object and
    writes 0 where it does not know, which is not a size and must not be
    read as one.
    """

    raw = provenance.get("tileMetres")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            pair = [float(raw[0]), float(raw[1])]
        except (TypeError, ValueError):
            return None
        return pair if pair[0] > 0 and pair[1] > 0 else None

    dimensions = provenance.get("dimensions")
    site = (provenance.get("site") or "").lower()
    divisor = 100.0 if "ambientcg" in site else 1000.0
    if isinstance(dimensions, dict):
        width, height = dimensions.get("width"), dimensions.get("height")
    elif isinstance(dimensions, (list, tuple)) and len(dimensions) >= 2:
        width, height = dimensions[0], dimensions[1]
    else:
        return None
    try:
        pair = [float(width) / divisor, float(height) / divisor]
    except (TypeError, ValueError):
        return None
    return pair if pair[0] > 0 and pair[1] > 0 else None


def apply_sidecar(found: List[Dict], sidecar: Dict) -> List[Dict]:
    """Overlay the studio's own facts about materials it does not own.

    The library belongs to QS and is never written to, so a tile size typed
    into the studio has to live somewhere else. It lives here, keyed by
    "family/name", which survives the library being moved, regenerated or
    renamed, and loses only the materials that were themselves renamed.
    """

    tiles = (sidecar or {}).get("tileMetres") or {}
    previews = (sidecar or {}).get("preview") or {}
    for entry in found:
        override = tiles.get(entry["key"])
        if isinstance(override, (list, tuple)) and len(override) == 2:
            try:
                pair = [float(override[0]), float(override[1])]
            except (TypeError, ValueError):
                pair = None
            if pair and pair[0] > 0 and pair[1] > 0:
                entry["tileMetres"] = pair
        if entry["key"] in previews:
            entry["preview"] = previews[entry["key"]]
    return found
