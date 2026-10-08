"""The bit depths in the ground-texture importer, which were wrong once.

Poly Haven ships displacement and ao as 16-bit PNGs. PIL's convert("L")
from I;16 CLIPS at 255 rather than scaling, so the first import wrote a
height map and an ao map whose every pixel was 255: 7 kB files that
loaded without complaint and carried no information at all. A flat map
does not fail, it just quietly stops doing anything.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "fetch_ground_textures.py"

pytest.importorskip("PIL")
pytest.importorskip("numpy")


def tool():
    spec = importlib.util.spec_from_file_location("fetch_ground_textures", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sixteen_bit(values):
    """A 2x2 16-bit greyscale PNG carrying exactly these values."""

    import numpy as np
    from PIL import Image

    array = np.array(values, dtype=np.uint16).reshape(2, 2)
    image = Image.frombytes("I;16", (2, 2), array.tobytes())
    blob = io.BytesIO()
    image.save(blob, "PNG")
    return Image.open(io.BytesIO(blob.getvalue()))


def test_sixteen_bits_come_down_to_eight_by_scaling_not_clipping():
    """The whole bug in one assertion. Clipping sends everything above
    255 to 255, so a map whose values run to 65535 arrives white."""

    import numpy as np

    module = tool()
    image = sixteen_bit([0, 32768, 65535, 16384])
    got = module._to_mode(image, "L")
    assert got.mode == "L"
    assert got.getextrema() == (0, 255), (
        "a 16-bit range must map onto the whole 8-bit range")
    assert sorted(np.asarray(got).ravel().tolist()) == [0, 64, 128, 255]


def test_a_height_map_keeps_all_sixteen_of_its_bits():
    """The library stores height as I;16 (measured on every existing
    material), because a displacement quantised to 256 steps terraces."""

    import numpy as np

    module = tool()
    image = sixteen_bit([0, 32768, 65535, 16384])
    got = module._to_mode(image, "I;16")
    assert got.mode == "I;16"
    assert got.getextrema() == (0, 65535)
    assert sorted(np.asarray(got).ravel().tolist()) == [0, 16384, 32768, 65535]


def test_eight_bits_widen_so_white_stays_white():
    """255 must become 65535, not 65280. Multiplying by 257 does that;
    shifting left by 8 leaves a dark seam at the top of the range."""

    module = tool()
    from PIL import Image

    got = module._to_mode(Image.new("L", (2, 2), 255), "I;16")
    assert got.mode == "I;16"
    assert got.getextrema() == (65535, 65535)


def test_a_flat_map_is_refused_rather_than_written(tmp_path):
    """The guard that would have caught it. A map whose every pixel is
    the same value is indistinguishable from a working one at load
    time, so it is refused where it is cheap to notice."""

    import numpy as np
    from PIL import Image

    module = tool()
    flat = Image.frombytes(
        "I;16", (4, 4), np.full((4, 4), 40000, dtype=np.uint16).tobytes())
    blob = io.BytesIO()
    flat.save(blob, "PNG")

    with pytest.raises(ValueError, match="came out flat"):
        module.write_image(blob.getvalue(), tmp_path / "ao.png", 4, "png", "L")
    assert not (tmp_path / "ao.png").exists(), (
        "and nothing is written, so half a material cannot be left behind")


def test_a_real_map_is_written_in_the_mode_the_library_uses(tmp_path):
    import numpy as np
    from PIL import Image

    module = tool()
    ramp = np.linspace(0, 65535, 16, dtype=np.uint16).reshape(4, 4)
    source = Image.frombytes("I;16", (4, 4), ramp.tobytes())
    blob = io.BytesIO()
    source.save(blob, "PNG")

    size, span = module.write_image(
        blob.getvalue(), tmp_path / "height.png", 4, "png", "I;16")
    assert size == [4, 4]
    assert span[1] > span[0]
    with Image.open(tmp_path / "height.png") as written:
        assert written.mode == "I;16"


def test_the_directx_normal_is_never_the_one_taken():
    """nor_dx has an inverted green channel. Read under the OpenGL
    convention three.js uses, it lights a surface from the wrong side
    and never fails."""

    module = tool()
    sources = [entry[1] for entry in module.MAPS]
    assert "nor_gl" in sources
    assert "nor_dx" not in sources
