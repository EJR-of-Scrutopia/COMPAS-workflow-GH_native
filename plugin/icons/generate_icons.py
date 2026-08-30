"""Generate the Ananke Equilibrium Grasshopper component icons.

The generator intentionally uses only the Python standard library. Text is
drawn with a bundled 5 x 7 bitmap alphabet, so output does not depend on an
installed font, Pillow version, operating system, or display scaling.

Run from any working directory:

    python plugin/icons/generate_icons.py
    python plugin/icons/generate_icons.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


ICON_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = ICON_DIR.parent
MAP_PATH = ICON_DIR / "icon-map.json"
MANIFEST_PATH = PLUGIN_DIR / "components.toml"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

RGBA = Tuple[int, int, int, int]
RGB = Tuple[int, int, int]

# Only the glyphs used by icon-map.json are needed. Keeping the alphabet small
# makes unsupported labels fail loudly instead of silently rendering badly.
GLYPHS: Dict[str, Tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "11001", "10101", "10011", "10011", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
}


def parse_hex(value: str) -> RGB:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("Expected #RRGGBB colour, got {!r}".format(value))
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]


def blend(first: RGB, second: RGB, amount: float) -> RGB:
    return tuple(
        round(a * (1.0 - amount) + b * amount)
        for a, b in zip(first, second)
    )  # type: ignore[return-value]


def set_pixel(pixels: bytearray, width: int, x: int, y: int, colour: RGBA) -> None:
    if x < 0 or y < 0 or x >= width or y >= width:
        return
    index = (y * width + x) * 4
    pixels[index : index + 4] = bytes(colour)


def in_rounded_rectangle(
    x: int,
    y: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    radius: int,
) -> bool:
    """Return whether a pixel centre lies in an exclusive-bound rounded box."""
    px = x + 0.5
    py = y + 0.5
    nearest_x = min(max(px, left + radius), right - radius)
    nearest_y = min(max(py, top + radius), bottom - radius)
    dx = px - nearest_x
    dy = py - nearest_y
    return dx * dx + dy * dy <= radius * radius


def draw_glyph(
    pixels: bytearray,
    width: int,
    glyph: Sequence[str],
    x: int,
    y: int,
    scale: int,
    colour: RGBA,
) -> None:
    for row_index, row in enumerate(glyph):
        for column_index, bit in enumerate(row):
            if bit != "1":
                continue
            for offset_y in range(scale):
                for offset_x in range(scale):
                    set_pixel(
                        pixels,
                        width,
                        x + column_index * scale + offset_x,
                        y + row_index * scale + offset_y,
                        colour,
                    )


def draw_label(
    pixels: bytearray,
    size: int,
    label: str,
    scale: int = 2,
) -> None:
    spacing = scale
    glyph_width = 5 * scale
    text_width = len(label) * glyph_width + (len(label) - 1) * spacing
    text_height = 7 * scale
    x = (size - text_width) // 2
    y = (size - text_height) // 2

    for index, character in enumerate(label):
        glyph = GLYPHS[character]
        glyph_x = x + index * (glyph_width + spacing)
        draw_glyph(pixels, size, glyph, glyph_x + 1, y + 1, scale, (0, 0, 0, 125))
    for index, character in enumerate(label):
        glyph = GLYPHS[character]
        glyph_x = x + index * (glyph_width + spacing)
        draw_glyph(pixels, size, glyph, glyph_x, y, scale, (255, 255, 255, 255))


def make_icon(size: int, fill: RGB, label: str) -> bytes:
    pixels = bytearray(size * size * 4)
    border = (20, 31, 37, 255)
    highlight = blend(fill, (255, 255, 255), 0.16)

    for y in range(size):
        for x in range(size):
            if in_rounded_rectangle(x, y, 0, 0, size, size, 5):
                set_pixel(pixels, size, x, y, border)
            if in_rounded_rectangle(x, y, 1, 1, size - 1, size - 1, 4):
                colour = highlight if y < 4 else fill
                set_pixel(pixels, size, x, y, (*colour, 255))

    draw_label(pixels, size, label)
    return encode_png(size, size, pixels)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(data, checksum)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def encode_png(width: int, height: int, pixels: bytes) -> bytes:
    stride = width * 4
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)  # PNG filter type: None
        start = y * stride
        scanlines.extend(pixels[start : start + stride])

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9))
        + png_chunk(b"IEND", b"")
    )


def load_mapping() -> dict:
    with MAP_PATH.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def read_manifest_components() -> Dict[str, str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    blocks = text.split("[[components]]")[1:]
    result: Dict[str, str] = {}
    for block in blocks:
        key_match = re.search(r'(?m)^key\s*=\s*"([^"]+)"', block)
        category_match = re.search(r'(?m)^subcategory\s*=\s*"([^"]+)"', block)
        if not key_match or not category_match:
            raise ValueError("Malformed [[components]] block in {}".format(MANIFEST_PATH))
        result[key_match.group(1)] = category_match.group(1)
    return result


def validate_mapping(mapping: dict) -> None:
    size = mapping.get("size")
    if size != [24, 24]:
        raise ValueError("Grasshopper icon size must remain [24, 24]")

    categories = mapping.get("categories", {})
    components = mapping.get("components", [])
    native_components = mapping.get("native_components", [])
    manifest = read_manifest_components()

    # The LEGACY list answers to plugin/components.toml, the old
    # script-backed plugin's manifest: the same keys and the same
    # subcategory, exactly as before. The NATIVE list answers to the .gha's
    # own panels and is checked against nothing here, because the smoke
    # harness checks it against the components themselves, which is the only
    # thing that can say whether it is right.
    mapped_keys = [item.get("key") for item in components]
    if set(mapped_keys) != set(manifest):
        missing = sorted(set(manifest) - set(mapped_keys))
        extra = sorted(set(mapped_keys) - set(manifest))
        raise ValueError("Icon coverage mismatch: missing={}, extra={}".format(missing, extra))

    for name, entries in (
        ("components", components),
        ("native_components", native_components),
    ):
        keys = [item["key"] for item in entries]
        filenames = [item["filename"] for item in entries]
        if len(keys) != len(set(keys)):
            raise ValueError("{} contains duplicate component keys".format(name))
        if len(filenames) != len(set(filenames)):
            raise ValueError("{} contains duplicate filenames".format(name))

    # A key in BOTH lists is one PNG with two readers: four native
    # components (Loads, TNA Solve, FD Solve, Style) keep the keys the old
    # manifest gave them, and the .gha loads the file by that name. Allowed,
    # and the two entries must name the same file, or one list would
    # silently overwrite a file belonging to the other.
    native_by_key = {item["key"]: item for item in native_components}
    for item in components:
        twin = native_by_key.get(item["key"])
        if twin is not None and twin["filename"] != item["filename"]:
            raise ValueError(
                "{} is in both lists under two filenames: {!r} and {!r}".format(
                    item["key"], item["filename"], twin["filename"]
                )
            )

    for index, item in enumerate(components + native_components):
        legacy = index < len(components)
        key = item["key"]
        label = item["label"]
        category = item["category"]
        filename = item["filename"]

        if not re.fullmatch(r"[A-Z0-9]{2,3}", label):
            raise ValueError("{} label must be 2-3 uppercase characters".format(key))
        unsupported = sorted(set(label) - set(GLYPHS))
        if unsupported:
            raise ValueError("{} label uses unsupported glyphs: {}".format(key, unsupported))
        if category not in categories:
            raise ValueError("{} uses unknown category {!r}".format(key, category))
        if legacy and key in manifest and category != manifest[key]:
            raise ValueError(
                "{} category differs from components.toml: {!r} != {!r}".format(
                    key, category, manifest[key]
                )
            )
        if not re.fullmatch(r"[a-z0-9_]+\.png", filename):
            raise ValueError("{} has unsafe filename {!r}".format(key, filename))
        parse_hex(categories[category]["fill"])


def validate_png(path: Path, expected_size: int) -> str:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("{} is not a PNG".format(path))
    length = struct.unpack(">I", data[8:12])[0]
    kind = data[12:16]
    if kind != b"IHDR" or length != 13:
        raise ValueError("{} has an invalid IHDR chunk".format(path))
    width, height, depth, colour_type, _, _, _ = struct.unpack(">IIBBBBB", data[16:29])
    if (width, height, depth, colour_type) != (expected_size, expected_size, 8, 6):
        raise ValueError(
            "{} expected {}x{} RGBA8, got {}x{} depth={} type={}".format(
                path, expected_size, expected_size, width, height, depth, colour_type
            )
        )
    return hashlib.sha256(data).hexdigest()[:12]


def generate(mapping: dict) -> None:
    size = mapping["size"][0]
    categories = mapping["categories"]
    # Native LAST, deliberately: where a key is in both lists the native
    # entry owns the pixels, because the .gha is the plugin that is built
    # and its panel is the colour the badge has to carry.
    for item in mapping["components"] + mapping.get("native_components", []):
        fill = parse_hex(categories[item["category"]]["fill"])
        data = make_icon(size, fill, item["label"])
        (ICON_DIR / item["filename"]).write_bytes(data)


def check(mapping: dict) -> None:
    expected_size = mapping["size"][0]
    for item in mapping["components"] + mapping.get("native_components", []):
        path = ICON_DIR / item["filename"]
        if not path.is_file():
            raise FileNotFoundError("Missing icon: {}".format(path))
        digest = validate_png(path, expected_size)
        print("{:<22} {}x{} RGBA8 sha256:{}".format(
            item["filename"], expected_size, expected_size, digest
        ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate existing icons without regenerating them.",
    )
    arguments = parser.parse_args()

    mapping = load_mapping()
    validate_mapping(mapping)
    if not arguments.check:
        generate(mapping)
    check(mapping)
    count = len(mapping["components"]) + len(mapping.get("native_components", []))
    print("Validated {} component icons.".format(count))


if __name__ == "__main__":
    main()
