"""Add a Poly Haven texture to the studio's ground library, in Param's format.

The library was curated by hand and by QS Intelligence's own stack, and
this writes into it in exactly the shape those materials already have:

    <root>/<family>/<name>/colour.jpg
                          /normal.png
                          /height.png
                          /roughness.png
                          /ao.png
                          /lod/<map>-1024.<ext>
                          /lod/<map>-256.<ext>
                          /material.json

Only the file names are ours. Which map goes where is Poly Haven's:

    Diffuse       -> colour      the albedo, stored as JPEG like its siblings
    nor_gl        -> normal      OpenGL convention, which is three.js's
    Displacement  -> height
    Rough         -> roughness   stored at half size, as the library does
    AO            -> ao          likewise

nor_dx is deliberately NOT used. It is the DirectX convention, whose green
channel is inverted, and a normal map read under the wrong convention lights
a surface from the wrong side without ever failing.

WHY POLY HAVEN AND NOT AMBIENTCG for grass. Both libraries are CC0 and both
are already represented here (100 and 132 materials). But the studio has to
know how much world one picture shows, or a vault ends up standing on blades
of grass the size of doors, and ambientCG answers 0 x 0 cm for every one of
its eight Grass assets. Poly Haven publishes real dimensions in millimetres
for all 21 of its grass textures, so the scale is fetched rather than
guessed. tools/fetch_tile_sizes.py picks that up afterwards.

    python tools/fetch_ground_textures.py <library root> --asset leafy_grass
        --family vegetation --name grass-lawn

Nothing existing is overwritten: a name that is already there is refused
unless --replace is given.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com"
AGENT = {"User-Agent": "vaulted-studio-ground-import/1.0"}

# Our name, their map, the file format, the side we store it at, and the
# PIXEL MODE, which is read off the library rather than chosen: colour and
# normal are RGB, roughness and ao are 8-bit grey, and HEIGHT IS 16-BIT.
#
# The mode is load-bearing and was got wrong once here. Poly Haven ships
# displacement and ao as 16-bit PNGs, and PIL's convert("L") from I;16
# CLIPS at 255 rather than scaling, so nearly every pixel saturates. The
# first import wrote a height map and an ao map whose every pixel was 255:
# 7 kB files that loaded without complaint and carried no information at
# all. A flat ao and a flat height do not fail, they just quietly stop
# doing anything, which is why the modes are stated here and asserted
# after writing.
#
# roughness and ao at half size, which is what the library already does
# and what those two can afford: neither carries an edge a viewer can see
# at 4K that it loses at 2K.
MAPS = (
    ("colour", "Diffuse", "jpg", 4096, "RGB"),
    ("normal", "nor_gl", "png", 4096, "RGB"),
    ("height", "Displacement", "png", 4096, "I;16"),
    ("roughness", "Rough", "png", 2048, "L"),
    ("ao", "AO", "png", 2048, "L"),
)

TIERS = (1024, 256)


def get_json(url: str):
    request = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, say) -> bytes:
    request = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(request, timeout=900) as response:
        total = int(response.headers.get("content-length") or 0)
        chunks = []
        read = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
            read += len(chunk)
            if total:
                say("      {:>5.1f} MB of {:>5.1f} MB\r".format(
                    read / 1048576, total / 1048576), end="")
        say(" " * 34 + "\r", end="")
        return b"".join(chunks)


def pick_source(node, wanted_format: str):
    """The 4K entry for a map, preferring the format we mean to store.

    JPEG is taken for the colour because that is how the library stores
    it, and PNG for everything else because a normal or a height map
    carries gradients that JPEG rings on.
    """

    at_4k = (node or {}).get("4k") or {}
    for candidate in (wanted_format, "png", "jpg"):
        entry = at_4k.get(candidate)
        if isinstance(entry, dict) and entry.get("url"):
            return entry["url"], candidate
    return None, None


def _is_wide(mode: str) -> bool:
    return mode in ("I;16", "I;16B", "I;16L", "I", "I;16N")


def _to_mode(image, mode: str):
    """The image in the mode the library stores this map in.

    Sixteen bits come down to eight by a SHIFT, never by PIL's own
    convert, which clips. Eight bits go up by multiplying by 257, which
    maps 255 exactly onto 65535 rather than leaving a dark seam at the
    top of the range.
    """

    import numpy as np
    from PIL import Image

    wide = _is_wide(image.mode)
    if mode == "I;16":
        if wide:
            array = np.asarray(image).astype(np.uint16)
        else:
            array = np.asarray(image.convert("L")).astype(np.uint16) * 257
        return Image.frombytes("I;16", (array.shape[1], array.shape[0]),
                               array.tobytes())
    if wide:
        array = (np.asarray(image).astype(np.uint32) >> 8).astype(np.uint8)
        grey = Image.frombytes("L", (array.shape[1], array.shape[0]),
                               array.tobytes())
        return grey.convert("RGB") if mode == "RGB" else grey
    return image.convert(mode)


def _resize(image, side: int):
    """LANCZOS, and through 32 bits for a 16-bit map.

    PIL will not resample I;16 directly. Going via I keeps the full range,
    where going via L would throw away the low byte before the filter ever
    ran, which is the same loss this module exists to avoid.
    """

    import numpy as np
    from PIL import Image

    if image.width == side:
        return image
    if image.mode == "I;16":
        wide = image.convert("I").resize((side, side), Image.LANCZOS)
        array = np.clip(np.asarray(wide), 0, 65535).astype(np.uint16)
        return Image.frombytes("I;16", (side, side), array.tobytes())
    return image.resize((side, side), Image.LANCZOS)


def _save(image, path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jpg":
        image.save(path, "JPEG", quality=92, optimize=True)
    else:
        image.save(path, "PNG", optimize=True)


def write_image(data: bytes, path: Path, side: int, fmt: str, mode: str):
    """Store one map, and REFUSE a flat one.

    A map whose every pixel is the same value is the signature of a
    botched bit-depth conversion, and it is indistinguishable from a
    working file at load time. Checked here, once, where it is cheap.
    """

    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    image = _resize(_to_mode(Image.open(io.BytesIO(data)), mode), side)
    low, high = _extremes(image)
    if low == high:
        raise ValueError(
            "{} came out flat at {} everywhere, which means the bit depth "
            "was lost rather than converted".format(path.name, low))
    _save(image, path, fmt)
    return list(image.size), (low, high)


def _extremes(image):
    band = image.getextrema()
    if isinstance(band[0], tuple):          # RGB gives one pair per channel
        return min(p[0] for p in band), max(p[1] for p in band)
    return band


def build_lods(path: Path, folder: Path, key: str, fmt: str, say) -> None:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    with Image.open(path) as image:
        image.load()
        for tier in TIERS:
            out = folder / "lod" / "{}-{}.{}".format(key, tier, fmt)
            _save(_resize(image, tier), out, fmt)
    say("      lod {} and {} written".format(*TIERS))


def fetch(asset: str, family: str, name: str, root: Path, replace: bool,
          say) -> int:
    folder = root / family / name
    if folder.exists() and not replace:
        say("  {} already exists; --replace to overwrite".format(folder))
        return 1

    say("  asking Poly Haven about {}".format(asset))
    try:
        info = get_json("{}/info/{}".format(API, asset))
        files = get_json("{}/files/{}".format(API, asset))
    except urllib.error.HTTPError as error:
        say("  {} is not a Poly Haven asset ({})".format(asset, error.code))
        return 1

    dimensions = info.get("dimensions") or []
    written = {}
    for key, source_key, fmt, side, mode in MAPS:
        url, got = pick_source(files.get(source_key), fmt)
        if url is None:
            say("  {} has no {} map; refusing to write half a "
                "material".format(asset, source_key))
            return 1
        say("    {:<10} <- {} ({})".format(key, source_key, got))
        data = download(url, say)
        path = folder / "{}.{}".format(key, fmt)
        try:
            size, span = write_image(data, path, side, fmt, mode)
        except ValueError as error:
            say("  {}".format(error))
            return 1
        written[key] = size
        say("      {} {} {}, values {} to {}".format(
            "x".join(str(n) for n in size), mode, fmt, span[0], span[1]))
        build_lods(path, folder, key, fmt, say)

    document = {
        "family": family,
        "assetId": asset,
        "source": "https://polyhaven.com/a/{}".format(asset),
        "licence": "CC0",
        "site": "Poly Haven",
        "maps": written,
        "sourceRes": "4K",
        "written": "{}x{}".format(*written["colour"]),
        "sourceName": asset,
        "name": name,
        "tiers": list(TIERS),
    }
    for key, fmt in (("colour", "jpg"), ("normal", "png")):
        blob = (folder / "{}.{}".format(key, fmt)).read_bytes()
        document["{}Md5".format(key)] = hashlib.md5(blob).hexdigest()
    if len(dimensions) >= 2:
        # Recorded for the human reading the folder. The studio takes its
        # own copy through tools/fetch_tile_sizes.py, into its sidecar,
        # so the library stays exactly as it was curated.
        document["dimensionsMm"] = [round(float(d), 1) for d in dimensions[:2]]
    (folder / "material.json").write_text(
        json.dumps(document, indent=1), encoding="utf-8")
    metres = (dimensions[0] / 1000.0) if dimensions else 0.0
    say("  written {}/{}  ({:.2f} m across)".format(family, name, metres))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="the ground library folder")
    parser.add_argument("--asset", required=True, help="Poly Haven asset id")
    parser.add_argument("--family", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print("no library at {}".format(args.root))
        return 1

    def say(text, end="\n"):
        print(text, end=end, flush=True)

    return fetch(args.asset, args.family, args.name, args.root,
                 args.replace, say)


if __name__ == "__main__":
    raise SystemExit(main())
