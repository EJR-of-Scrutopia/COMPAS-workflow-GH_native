import struct, zlib
from pathlib import Path

W = H = 24
FILL = (78, 89, 104, 255)   # the slate the mould family uses
WHITE = (255, 255, 255, 255)
GLYPHS = {
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
}
px = [[FILL] * W for _ in range(H)]

def blit(ch, x0, y0):
    for r, row in enumerate(GLYPHS[ch]):
        for c, bit in enumerate(row):
            if bit == "1":
                px[y0 + r][x0 + c] = WHITE

blit("S", 5, 8)
blit("K", 13, 8)
raw = b"".join(b"\x00" + bytes(v for p in row for v in p) for row in px)

def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9))
       + chunk(b"IEND", b""))
out = Path("plugin/icons/skin.png")
out.write_bytes(png)
print(out, len(png), "bytes")
