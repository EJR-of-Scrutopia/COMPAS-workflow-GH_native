"""Turn ambientCG's CC0 decals into props the studio already knows how to place.

Param: "Can we include some decals too in the props".

A DECAL IS A PROP WHOSE GEOMETRY IS A PLANE. That one decision removes
almost all of the work. Arriving as an ordinary GLB -- two triangles and
an alpha-mapped texture -- a decal goes through placeProp like anything
else, and inherits the gumball, the layers, rotation, scale, undo, the
scene round trip AND the scatter brush without a line of new client code.
It also gets the right shadow behaviour for nothing: castsShadow keys on
a prop's height and a decal is two millimetres tall.

There is no DecalGeometry here and there should not be. That class
projects onto arbitrary meshes and pays for it; the studio's floor is a
flat disc (relief is bumpScale, never displacement -- see pbr.py), so a
plane laid on it is not an approximation, it is the exact answer.

TWO THINGS THIS GETS RIGHT AND A NAIVE VERSION WOULD NOT.

The plane is LIFTED two millimetres. glTF has no polygon offset, and a
decal exactly coplanar with the floor z-fights into stripes from every
camera -- the same fault the HDRI dome's ground hit at 40 mm (HDRI_DROP
in studio.js). Two millimetres is invisible at any angle that can see the
vault and settles the depth test outright.

And the alpha comes from ambientCG's OPACITY map composited into the
colour image, not from an alphaMap: glTF has no alpha channel slot, so a
separate opacity texture has nowhere to go in a GLB at all.

    python tools/props/fetch_decals.py            # the curated set
    python tools/props/fetch_decals.py ManholeCover011 TireTracks001

Merges into props.json by key, the way fetch.mjs does, so a later prop
run adds to these rather than replacing them.
"""

from __future__ import annotations

import io
import json
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "bench" / "studio" / "props-hd"
API = "https://ambientcg.com/api/v2/full_json"
AGENT = {"User-Agent": "vaulted-studio-decals/1.0"}

# Two millimetres above the floor. See the module docstring.
LIFT = 0.002
SIDE = 1024          # the stored texture, one tier below the 2K source

# The curated set, for a vault under construction on a site. ambientCG
# publishes no dimensions for decals, so the real-world size is stated
# here: a manhole cover is 800 mm because manhole covers are, and a tyre
# track is as wide as a wheel.
CURATED = [
    ("ManholeCover011", "decal-manhole", "Manhole cover", 0.80),
    ("ManholeCover004", "decal-manhole-square", "Square cover", 0.70),
    ("AsphaltDamage001", "decal-cracks", "Cracked ground", 1.60),
    ("PavingEdge001", "decal-paving-edge", "Paving edge", 2.00),
    ("PavingEdge002", "decal-paving-edge-2", "Paving edge 2", 2.00),
    ("RoadLines022A", "decal-line-worn", "Worn line", 2.00),
    ("ManholeCover001", "decal-drain", "Drain cover", 0.60),
    ("ManholeCover008", "decal-inspection", "Inspection cover", 0.75),
    # TireTracks001 and the whole Leaking family are NOT here, and cannot
    # be: they ship no opacity map, so they are surface textures rather
    # than cutouts and arrive as opaque squares. rgba_from refuses them.
    ("RoadLines019A", "decal-line-white", "Painted line", 2.00),
    ("ChewingGum001", "decal-gum", "Ground litter", 0.35),
]


def get_json(url: str):
    request = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, say) -> bytes:
    request = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(request, timeout=900) as response:
        total = int(response.headers.get("content-length") or 0)
        chunks, read = [], 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
            read += len(chunk)
            if total:
                say("      {:>5.1f} of {:>5.1f} MB\r".format(
                    read / 1048576, total / 1048576), end="")
        say(" " * 30 + "\r", end="")
        return b"".join(chunks)


def archive_url(asset: str) -> str:
    """The 1K JPEG zip. A ground decal is never read close enough to want
    more, and the 8K is a quarter of a gigabyte."""

    body = get_json("{}?id={}&include=downloadData".format(API, asset))
    found = body.get("foundAssets") or []
    if not found:
        return ""
    for folder in (found[0].get("downloadFolders") or {}).values():
        for group in (folder.get("downloadFiletypeCategories") or {}).values():
            for item in group.get("downloads", []):
                if item.get("fileName", "").endswith("_1K-JPG.zip"):
                    return item.get("fullDownloadPath") or item.get("downloadLink") or ""
    return ""


def rgba_from(archive: bytes):
    """Colour with the opacity map as its alpha channel.

    glTF has no slot for a separate opacity texture, so the two have to
    become one image here or the decal arrives as an opaque rectangle.
    """

    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        names = zipped.namelist()

        def find(*words):
            for name in names:
                low = name.lower()
                if any(word in low for word in words) and low.endswith(
                        (".jpg", ".jpeg", ".png")):
                    return name
            return None

        colour_name = find("_color", "_col")
        alpha_name = find("_opacity", "_alpha")
        if not colour_name:
            raise ValueError("no colour map in the archive")
        colour = Image.open(io.BytesIO(zipped.read(colour_name))).convert("RGB")
        colour = colour.resize((SIDE, SIDE), Image.LANCZOS)
        # NO OPACITY MAP MEANS NO DECAL. Not every ambientCG asset filed
        # under Decal is a cutout: the whole Leaking family is a surface
        # texture, colour and normal and roughness with nothing to say
        # which parts are stain and which are background. Composited with
        # a white alpha it lays an OPAQUE GREY SQUARE on his floor, which
        # loads without complaint and looks like a bug in the studio.
        # Four of the first ten came out that way. Refused here instead.
        if not alpha_name:
            raise ValueError(
                "no opacity map: this is a surface texture, not a decal")
        alpha = Image.open(io.BytesIO(zipped.read(alpha_name))).convert("L")
        alpha = alpha.resize((SIDE, SIDE), Image.LANCZOS)
        low, high = alpha.getextrema()
        if low == high:
            raise ValueError(
                "the opacity map is flat at {}, so there is no cutout in "
                "it".format(low))
        colour.putalpha(alpha)
    blob = io.BytesIO()
    colour.save(blob, "PNG", optimize=True)
    return blob.getvalue(), True


def pad(data: bytes, to: int = 4, filler: bytes = b"\x00") -> bytes:
    over = len(data) % to
    return data if not over else data + filler * (to - over)


def build_glb(png: bytes, metres: float, name: str) -> bytes:
    """A GLB holding one lifted, alpha-mapped plane, `metres` across.

    glTF is Y-up and the studio is Z-up; the loader rotates on the way
    in, so the plane is authored in XZ with the lift on Y and arrives
    flat on the floor.
    """

    half = metres / 2.0
    positions = [(-half, LIFT, -half), (half, LIFT, -half),
                 (half, LIFT, half), (-half, LIFT, half)]
    normals = [(0.0, 1.0, 0.0)] * 4
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    indices = [0, 1, 2, 0, 2, 3]

    position_bytes = b"".join(struct.pack("<3f", *p) for p in positions)
    normal_bytes = b"".join(struct.pack("<3f", *n) for n in normals)
    uv_bytes = b"".join(struct.pack("<2f", *t) for t in uvs)
    index_bytes = b"".join(struct.pack("<H", i) for i in indices)

    parts, views, offset = [], [], 0
    for blob, target in ((position_bytes, 34962), (normal_bytes, 34962),
                         (uv_bytes, 34962), (index_bytes, 34963),
                         (png, None)):
        padded = pad(blob)
        views.append({"buffer": 0, "byteOffset": offset,
                      "byteLength": len(blob)}
                     | ({"target": target} if target else {}))
        parts.append(padded)
        offset += len(padded)
    buffer = b"".join(parts)

    document = {
        "asset": {"version": "2.0",
                  "generator": "vaulted tools/props/fetch_decals.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": [{
            "attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
            "indices": 3, "material": 0}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3",
             "min": [-half, LIFT, -half], "max": [half, LIFT, half]},
            {"bufferView": 1, "componentType": 5126, "count": 4, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": 4, "type": "VEC2"},
            {"bufferView": 3, "componentType": 5123, "count": 6, "type": "SCALAR"},
        ],
        "bufferViews": views,
        "buffers": [{"byteLength": len(buffer)}],
        "images": [{"bufferView": 4, "mimeType": "image/png"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987,
                      "wrapS": 33071, "wrapT": 33071}],
        "textures": [{"sampler": 0, "source": 0}],
        "materials": [{
            "name": name,
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0.0, "roughnessFactor": 0.9},
            # BLEND rather than MASK: a stain's edge is a gradient, and a
            # cutout would give it a hard sawn edge.
            "alphaMode": "BLEND",
            "doubleSided": True,
        }],
    }
    json_chunk = pad(json.dumps(document, separators=(",", ":")).encode("utf-8"),
                     filler=b" ")
    bin_chunk = pad(buffer)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    out = [struct.pack("<4sII", b"glTF", 2, total),
           struct.pack("<II", len(json_chunk), 0x4E4F534A), json_chunk,
           struct.pack("<II", len(bin_chunk), 0x004E4942), bin_chunk]
    return b"".join(out)


def merge(entries, say):
    """Into props.json BY KEY, the way fetch.mjs merges, so a later prop
    run adds to these rather than replacing them."""

    path = OUT / "props.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    by_key = {p["key"]: p for p in manifest.get("props", [])}
    for entry in entries:
        by_key[entry["key"]] = entry
    manifest["props"] = sorted(
        by_key.values(), key=lambda p: (p.get("group", ""), p["key"]))
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_notice(manifest)
    say("  props.json now holds {} props".format(len(manifest["props"])))


def write_notice(manifest) -> None:
    """The credits, FROM THE MANIFEST, the same way fetch.mjs writes them.

    Deliberately duplicated across the two tools rather than shared: they
    are a Python script and a Node one, and this repo's own convention is
    that a duplicated piece is pinned by its own test.

    The header must describe what is ACTUALLY in the folder. It used to
    be a hard-coded "Every model in this folder is from Poly Haven and is
    CC0 1.0", which a five-grass run restated over twenty Quixel
    Megascans assets under the Fab Standard License. The entries were
    right; the sentence above them was false, which is the worse half to
    get wrong.
    """

    props = manifest.get("props", [])
    libraries = {}
    for prop in props:
        source = prop.get("source") or ""
        if "polyhaven" in source:
            where = "Poly Haven"
        elif "ambientcg" in source.lower():
            where = "ambientCG"
        elif "fab.com" in source:
            where = "Quixel Megascans, via Fab"
        else:
            where = "other"
        line = "{} -- {}".format(where, prop.get("licence") or "licence unstated")
        libraries[line] = libraries.get(line, 0) + 1

    lines = ["Models in this folder come from more than one library. Each is",
             "credited below; the licences they arrived under are:"]
    for line in sorted(libraries):
        lines.append("  {}  ({})".format(line, libraries[line]))
    lines += ["",
              "Poly Haven and ambientCG ask for no credit and this file is offered",
              "anyway. The Fab Standard License needs a free Epic account and",
              "permits use with any compatible tool, which the glTF export is.",
              ""]
    for prop in props:
        lines.append("{}\n  {}\n  {}".format(
            prop["key"], prop.get("label", prop["key"]), prop.get("source", "")))
    (OUT / "NOTICE.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    wanted = CURATED if not argv else [
        row for row in CURATED if row[0] in argv]
    if argv and not wanted:
        wanted = [(name, "decal-" + name.lower(), name, 1.5) for name in argv]

    def say(text, end="\n"):
        print(text, end=end, flush=True)

    built = []
    for asset, key, label, metres in wanted:
        say("{}  ({:.2f} m)".format(asset, metres))
        url = archive_url(asset)
        if not url:
            say("  no 1K JPG archive; skipped")
            continue
        try:
            png, had_alpha = rgba_from(download(url, say))
        except Exception as error:
            say("  {}: {}".format(type(error).__name__, error))
            continue
        glb = build_glb(png, metres, label)
        (OUT / (key + ".glb")).write_bytes(glb)
        built.append({
            "key": key, "label": label, "file": key + ".glb",
            "group": "decals",
            "sizeMetres": [metres, LIFT, metres],
            "triangles": 2, "bytes": len(glb),
            "credit": "{} by ambientCG".format(label),
            "licence": "CC0 1.0",
            "source": "https://ambientcg.com/view?id={}".format(asset),
        })
        say("  {:<22} {:>6.2f} MB{}".format(
            key, len(glb) / 1048576, "" if had_alpha else "  (no opacity map)"))
    if built:
        merge(built, say)
    say("\n{} decals built".format(len(built)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
