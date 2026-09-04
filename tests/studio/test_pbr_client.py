"""The client half of the material library.

These are text pins on the shipped modules, which is what this suite can do
without a browser. They exist for the mistakes that are silent: a colour
space set on the wrong map corrupts it in hardware and still renders; a
scalar left at its default zeroes the map it was meant to multiply; a repeat
set on the albedo alone leaves the relief at 1:1 and only shows under a
light that moves.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def pbr() -> str:
    return (STATIC / "pbr.js").read_text(encoding="utf-8")


def studio() -> str:
    return (STATIC / "studio.js").read_text(encoding="utf-8")


def test_only_the_colour_map_is_colour():
    """Setting sRGB on a normal map does not merely look wrong. The internal
    format becomes SRGB8_ALPHA8 and the GPU decodes every texel through a
    transfer function before the shader sees the vector it was meant to be,
    so the corruption is in hardware and cannot be undone downstream."""

    source = pbr()
    assert 'COLOUR_DATA = new Set(["colour"])' in source
    assert "THREE.SRGBColorSpace" in source
    assert "THREE.NoColorSpace" in source
    # And nothing else is listed as colour data.
    listed = re.search(r"COLOUR_DATA = new Set\(\[([^\]]*)\]\)", source)
    assert listed and listed.group(1).count(",") == 0


def test_the_scalars_that_multiply_their_maps_are_set_to_one():
    """roughness and metalness MULTIPLY their maps rather than replacing
    them. Leaving metalness at its default 0 zeroes a metalness map
    entirely, which is the commonest silent fault in physically based
    rendering, and any roughness but 1 rescales every value in the library
    at once."""

    source = pbr()
    assert "roughness: 1.0," in source
    assert "metalness: metalnessFor(entry.family)," in source
    assert 'return family === "metal" ? 1.0 : 0.0;' in source


def test_repeat_is_set_on_every_map_and_wrapping_is_asked_for():
    """Each map slot carries its own transform uniform, so a repeat on the
    albedo alone leaves the relief and the roughness at 1:1. And
    RepeatWrapping is not the default: ClampToEdgeWrapping smears the edge
    pixel across the whole surface instead of tiling."""

    source = pbr()
    assert "for (const texture of set.textures) texture.repeat.set(u, v);" in source
    assert "texture.wrapS = THREE.RepeatWrapping;" in source
    assert "texture.wrapT = THREE.RepeatWrapping;" in source


def test_disposal_frees_the_maps_and_not_only_the_material():
    """Material.dispose() does not touch textures, and a texture is where
    the video memory is: four maps at 1024 square with mipmaps is about
    21 MB that stays allocated for the life of the page."""

    source = pbr()
    body = source[source.index("export function disposeLibraryMaterial"):]
    assert "for (const texture of set.textures) texture.dispose();" in body
    assert "set.material.dispose();" in body


def test_the_height_map_is_not_loaded_into_the_viewport():
    """Every material in the library has one and the viewport samples none
    of them: it normal-maps rather than displacing. A map nothing reads is a
    megabyte of video memory spent on nothing."""

    source = pbr()
    slots = source[source.index("const SLOTS = {"):source.index("};", source.index("const SLOTS = {"))]
    assert "colour:" in slots and "normal:" in slots
    assert "roughness:" in slots and "ao:" in slots
    assert "height:" not in slots


def test_a_piece_is_laid_out_in_metres_when_the_material_knows_its_size():
    """boxUVs takes UV units per metre. The hard-coded 0.15 it used to carry
    is one repeat per 6.67 m, a number chosen by eye for a procedural noise
    that had no real size; a library material has one."""

    fields = (STATIC / "fields.js").read_text(encoding="utf-8")
    assert "export function boxUVs(positions, centroid, offset, scaleU = 0.15, scaleV = scaleU)" in fields
    assert "* scaleU + offset[0]" in fields and "* scaleV + offset[1]" in fields
    source = studio()
    assert "boxUVs(positions, centre, segmentUVOffset(piece.key), 1 / tile[0], 1 / tile[1])" in source


def test_the_library_is_the_render_skin_and_stays_render_only():
    """A hundred and fifty-eight photographs of brick have nothing to say
    about density, so they belong in the skin and not beside the seven
    analysis materials the server knows. This is also what keeps the
    render-only separation, and its test, untouched."""

    source = studio()
    assert "async function refreshMaterialLibrary()" in source
    assert 'fetchJson("/api/materials")' in source
    assert "isLibraryKey(skin) && libraryCache.has(skin)" in source
    # The analysis material never learns about any of it.
    assert "state.bundle.material = " not in source


def test_the_loaded_set_cache_is_bounded_and_evicts_by_disposing():
    """A WebGL texture is not reclaimed by dropping a reference the way a
    GDI+ bitmap is, so eviction here has to dispose, unlike the plugin's own
    caches. The one exception is the material currently being worn."""

    source = studio()
    assert "const LIBRARY_CACHE_LIMIT = 6;" in source
    assert "while (libraryCache.size > LIBRARY_CACHE_LIMIT)" in source
    assert "disposeLibraryMaterial(libraryCache.get(oldest));" in source
    assert "if (oldest === key || oldest === state.appearance.skin) break;" in source


def test_a_double_click_does_not_fetch_the_same_set_twice():
    source = studio()
    assert "libraryLoads" in source
    assert "if (libraryLoads.has(key)) return libraryLoads.get(key);" in source


def test_tiles_are_pictures_from_the_backend_not_renders():
    """A hundred and fifty-eight rendered swatches would be a hundred and
    fifty-eight passes through the preview rig. The library's own 256 pixel
    crop is a file, costs no video memory, and is the most legible thing
    that could go in a tile because it is one unit of the substance."""

    source = pbr()
    assert "export const TILE_PX = 256;" in source
    assert "export function tileUrl(entry)" in source
    studio_source = studio()
    assert 'image.loading = "lazy";' in studio_source
    assert "imageTile(entry.key, entry.label, tileUrl(entry))" in studio_source
