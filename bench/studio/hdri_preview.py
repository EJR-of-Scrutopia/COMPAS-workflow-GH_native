"""A small preview of a Radiance .hdr, with nothing but the standard library.

The studio's HDRI list is filenames, which asks the user to remember what a
sky looks like. A thumbnail answers that, but the files are enormous: the
sunset in Param's folder is 343 MB and the meadow 111 MB, so nothing can
decode them in the browser and nothing should decode them whole here either.

So this reads the header for the dimensions, then decodes only the scanlines
it needs, sampling across each one, and tone maps the result to a small PNG.
An 8k by 4k sky costs about 128 scanlines rather than 4096.

Standard library only, on purpose: geometry.py opens with the same rule and
the studio has stayed free of numpy and PIL, which is what lets it run under
any interpreter that can serve HTTP. A PNG writer is thirty lines of zlib,
and an RGBE decoder is not much more; a dependency is forever.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import List, Tuple

PREVIEW_WIDTH = 256

# What the browser is given, and why these two numbers.
#
# LIGHTING_WIDTH is what three.js asks for in as many words: "The ideal input
# image size is 1k (1024 x 512), as this matches best with the 256 x 256
# cubemap output." Everything above it is paid for twice, once in the source
# texture and again in a prefilter whose cost grows with the square of the
# width, and then thrown away by the blur.
#
# BACKGROUND_WIDTH is the sky the eye looks at rather than the light it
# casts, so it is tone-mapped to an ordinary 8-bit PNG. A background does not
# need float: it is behind the tone mapper anyway. It DOES need its pixels:
# 2048 across an equirect was about 340 pixels over a sixty degree view, and
# Param's 8k skies came out as soup ("they are all so blurry... i would like
# them at maximum quality please"). The width is now the common GPU texture
# ceiling; the samplers clamp to the source, so an 8k sky serves at its own
# native 8192 and only a 24k monster is trimmed to what a texture unit can
# hold. First derivation of a big sky costs real time in this stdlib-only
# decoder and is then cached beside the skies for good.
LIGHTING_WIDTH = 1024
BACKGROUND_WIDTH = 16384

# Reinhard leaves a value in 0..1 and the gamma is the expensive half, so it
# is a table rather than six million calls to pow. 4096 steps is finer than
# an 8-bit output can show.
_GAMMA_STEPS = 4096
_GAMMA = [max(0, min(255, int(round(255.0 * ((step / (_GAMMA_STEPS - 1.0))
                                             ** (1.0 / 2.2))))))
          for step in range(_GAMMA_STEPS)]


def _read_header(handle) -> Tuple[int, int]:
    """Consume the header and return (width, height).

    Radiance writes free-form lines, a blank line, then a resolution line
    like "-Y 4096 +X 8192". Only the standard orientation is handled; a
    rotated or flipped file raises rather than being drawn sideways.
    """

    magic = handle.readline()
    if not magic.startswith(b"#?"):
        raise ValueError("not a Radiance file: no #? signature")
    while True:
        line = handle.readline()
        if line in (b"\n", b"\r\n", b""):
            break
    resolution = handle.readline().decode("ascii", "replace").strip()
    parts = resolution.split()
    if len(parts) != 4 or parts[0] != "-Y" or parts[2] != "+X":
        raise ValueError("unsupported scanline order {!r}".format(resolution))
    return int(parts[3]), int(parts[1])


def _decode_scanline(handle, width: int) -> bytes:
    """One scanline as RGBE bytes, flat or adaptively run-length encoded."""

    head = handle.read(4)
    if len(head) < 4:
        raise ValueError("the file ends inside a scanline")
    if head[0] != 2 or head[1] != 2 or ((head[2] << 8) | head[3]) != width:
        # Old-style flat RGBE: the four bytes already read are the first
        # pixel, and the rest of the line follows.
        rest = handle.read(4 * (width - 1))
        return head + rest
    channels = []
    for _ in range(4):
        out = bytearray()
        while len(out) < width:
            count = handle.read(1)
            if not count:
                raise ValueError("the file ends inside a run")
            run = count[0]
            if run > 128:
                out.extend(handle.read(1) * (run - 128))
            else:
                out.extend(handle.read(run))
        channels.append(bytes(out[:width]))
    interleaved = bytearray(width * 4)
    for channel in range(4):
        interleaved[channel::4] = channels[channel]
    return bytes(interleaved)


def _tone(value: float, exposure: float) -> int:
    """Reinhard, then gamma. Enough for a thumbnail and defensible.

    A sky's dynamic range is the whole point of the format, so a linear
    clip would show a white disc on a white field. Reinhard keeps the sun
    from taking the frame while leaving the horizon readable.
    """

    lit = value * exposure
    mapped = lit / (1.0 + lit)
    return _GAMMA[int(mapped * (_GAMMA_STEPS - 1))]


def preview_rows(path, width: int = PREVIEW_WIDTH) -> Tuple[int, int, List[bytes]]:
    """Sampled, tone-mapped RGB rows for a small preview of the sky."""

    path = Path(path)
    with path.open("rb") as handle:
        full_width, full_height = _read_header(handle)
        if full_width <= 0 or full_height <= 0:
            raise ValueError("the header declares no image")
        width = min(width, full_width)
        height = max(1, int(round(width * full_height / full_width)))
        wanted = [min(full_height - 1, int(row * full_height / height))
                  for row in range(height)]
        columns = [min(full_width - 1, int(column * full_width / width))
                   for column in range(width)]
        rows: List[bytes] = []
        next_wanted = 0
        for line in range(full_height):
            if next_wanted >= len(wanted):
                break
            scan = _decode_scanline(handle, full_width)
            while next_wanted < len(wanted) and wanted[next_wanted] == line:
                out = bytearray()
                for column in columns:
                    base = column * 4
                    exponent = scan[base + 3]
                    if exponent == 0:
                        out.extend(b"\x00\x00\x00")
                        continue
                    scale = math.ldexp(1.0, exponent - 136)  # 2^(e-128) / 256
                    for channel in range(3):
                        out.append(_tone(scan[base + channel] * scale, 3.2))
                rows.append(bytes(out))
                next_wanted += 1
    return width, len(rows), rows


def write_png(destination, width: int, height: int, rows: List[bytes]) -> Path:
    """A plain 8-bit RGB PNG. Thirty lines, and no dependency."""

    raw = b"".join(b"\x00" + row for row in rows)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def build_preview(source, destination, width: int = PREVIEW_WIDTH) -> Path:
    """Decode a sky and write its thumbnail, once."""

    image_width, image_height, rows = preview_rows(source, width)
    return write_png(destination, image_width, image_height, rows)


def sample_rgbe(path, width: int = LIGHTING_WIDTH):
    """A smaller sky, still in RGBE, still with its full dynamic range.

    The same walk as preview_rows and the same nearest-neighbour sampling,
    but the four bytes are carried through untouched rather than tone
    mapped, because this file is going to be light and not a picture.

    Nearest neighbour, and it is worth saying what that costs. A proper box
    filter would preserve energy exactly; sampling one pixel in eight can
    miss a sun disc or over-count it. Two things make it acceptable here.
    The sky itself is smooth, so everything except the sun is unaffected;
    and the studio lights with an explicit directional sun whose direction
    and strength are estimated from THIS file, so the estimate and the
    environment agree with each other whatever the sampling did. A true box
    average over an 8192 pixel scanline in pure Python is tens of millions
    of operations per sky, and the standard-library-only rule is worth more
    than the last few per cent of a sun's energy.
    """

    path = Path(path)
    with path.open("rb") as handle:
        full_width, full_height = _read_header(handle)
        if full_width <= 0 or full_height <= 0:
            raise ValueError("the header declares no image")
        width = min(width, full_width)
        height = max(1, int(round(width * full_height / full_width)))
        wanted = [min(full_height - 1, int(row * full_height / height))
                  for row in range(height)]
        columns = [min(full_width - 1, int(column * full_width / width))
                   for column in range(width)]
        rows = []
        next_wanted = 0
        for line in range(full_height):
            if next_wanted >= len(wanted):
                break
            scan = _decode_scanline(handle, full_width)
            while next_wanted < len(wanted) and wanted[next_wanted] == line:
                out = bytearray()
                for column in columns:
                    base = column * 4
                    out += scan[base:base + 4]
                rows.append(bytes(out))
                next_wanted += 1
    return width, len(rows), rows


def write_hdr(destination, width: int, height: int, rows) -> Path:
    """A flat, uncompressed Radiance file.

    Flat rather than run-length encoded on purpose: at 1024 by 512 the whole
    thing is 2 MB, an encoder is a page of code that can be wrong in ways a
    decoder will not report, and every reader handles the flat form. three's
    own HDRLoader tries the RLE marker first and falls through to this.
    """

    header = (b"#?RADIANCE\n"
              b"FORMAT=32-bit_rle_rgbe\n"
              b"SOFTWARE=Bench Studio\n"
              b"\n"
              + "-Y {} +X {}\n".format(height, width).encode("ascii"))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + b"".join(rows))
    return destination


def build_lighting(source, destination, width: int = LIGHTING_WIDTH) -> Path:
    """The sky the renderer lights with: small, and still high dynamic range."""

    image_width, image_height, rows = sample_rgbe(source, width)
    return write_hdr(destination, image_width, image_height, rows)


def build_background(source, destination, width: int = BACKGROUND_WIDTH) -> Path:
    """The sky the eye looks at: bigger, and only eight bits deep."""

    image_width, image_height, rows = preview_rows(source, width)
    return write_png(destination, image_width, image_height, rows)
