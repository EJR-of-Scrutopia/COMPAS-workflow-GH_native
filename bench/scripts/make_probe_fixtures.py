"""Writes probe fixtures into a target directory: two tiny valid Radiance
.hdr files with different dominant colours (width 4 keeps scanlines
uncompressed, which HDRLoader accepts), plus the Tiny contract pair the
studio tests already use."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "tests" / "studio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "studio"))
from conftest_data import tiny_contract  # noqa: E402


def write_hdr(path: Path, rgbe_pixel: bytes) -> None:
    header = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 2 +X 4\n"
    path.write_bytes(header + rgbe_pixel * 8)


def main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    # (r, g, b, e): e = 129 puts values around 2.0, comfortably HDR.
    write_hdr(target / "probe-warm.hdr", struct.pack("BBBB", 255, 128, 32, 129))
    write_hdr(target / "probe-cool.hdr", struct.pack("BBBB", 32, 128, 255, 129))
    (target / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8")
    # app.py's upload_export 400s a compas file with no "thrustMesh" key
    # (bare "{}" fails that check), and bundle.py never reads the compas
    # file's contents at all -- geometry.available_exports only checks it
    # exists on disk to call the pair complete. An empty thrustMesh clears
    # the upload gate without needing real compas geometry.
    (target / "Tiny-compas.json").write_text(
        json.dumps({"thrustMesh": {}}), encoding="utf-8")
    print("fixtures written to {}".format(target))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
