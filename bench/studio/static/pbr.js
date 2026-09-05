// Turning a folder of pictures into a material three.js can light.
//
// The library is Param's, curated inside QS Intelligence, and its
// conventions are inherited rather than reinvented: one folder per
// material, fixed file names, maps linked by living together. What is NOT
// inherited is its colour handling. The plugin runs every calculation on
// 8-bit sRGB bytes with Rec.601 luma weights, which is right for a GDI+
// preview and wrong in a physically based renderer, where exactly one map
// carries colour and the other four carry numbers.
//
// Everything in here is about that distinction and its consequences.

import * as THREE from "three";

// What the viewport asks for, and what a tile asks for. Both are real tiers
// in the library; the server snaps anything else down to one of them and
// falls through to the master when the tier was never written, which
// happens whenever the master was already smaller.
// 0 means the master: the largest the library holds for that map, which in
// this library is the one-unit crop at whatever size it was cut from a 4K or
// 8K source. There is no larger thing to ask for, and asking for a tier
// instead would be choosing to be blurrier than the files allow.
//
// Unless the device is the wrong size for the master. The studio travels
// over the tailnet now, and an iPad asked for five master-tier maps per
// material change spends seconds decoding and uploading them -- and under
// GPU memory pressure iOS starts dropping texture uploads, which is the
// silver-props face of the same problem. Touch is the tell: iPadOS
// masquerades as a Mac in its user agent, but a Mac has no touch points.
export const CONSTRAINED_DEVICE =
  typeof navigator !== "undefined" && navigator.maxTouchPoints > 1;
export const VIEWPORT_PX = CONSTRAINED_DEVICE ? 1024 : 0;
export const TILE_PX = 256;

// Which file goes in which slot.
const SLOTS = {
  colour: "map",
  normal: "normalMap",
  roughness: "roughnessMap",
  ao: "aoMap",
  // The height field, as the BUMP map. A height map can drive geometry or
  // it can drive shading, and the mesh decides which is possible:
  // displacementMap moves vertices, and a vault piece is an extruded
  // voussoir of a couple of dozen of them, so displacing it would do
  // nothing whatever. Bump perturbs the shading normal per fragment, needs
  // no vertices at all, and is what makes a mortar joint read as a recess
  // rather than as a dark line.
  height: "bumpMap",
};

// Only colour is colour. Setting sRGB on a normal map does not merely look
// wrong, it corrupts it in hardware: the internal format becomes
// SRGB8_ALPHA8 and the GPU decodes every pixel through a transfer function
// before the shader ever sees the vector it was meant to be.
const COLOUR_DATA = new Set(["colour"]);

// Two library roots serve the same folder shape: the vault's skin library
// at /api/materials and the ground's at /api/ground-materials. The base is
// a parameter so one loader serves both.
export const SKIN_BASE = "/api/materials";
export const GROUND_BASE = "/api/ground-materials";

export function mapUrl(family, name, kind, px, base = SKIN_BASE) {
  const url = base + "/" + encodeURIComponent(family)
    + "/" + encodeURIComponent(name) + "/" + encodeURIComponent(kind);
  return px ? url + "?px=" + px : url;
}

// The picture a tile shows: the flat colour crop, at the smallest tier.
// Served as an ordinary image and drawn by the browser, so a library of a
// hundred and fifty materials costs no video memory at all.
export function tileUrl(entry, base = SKIN_BASE) {
  return mapUrl(entry.family, entry.name, "colour", TILE_PX, base);
}

function loadTexture(loader, url, kind, anisotropy) {
  return loader.loadAsync(url).then((texture) => {
    texture.colorSpace = COLOUR_DATA.has(kind)
      ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    // RepeatWrapping is NOT the default. A repeat above 1 with the default
    // ClampToEdgeWrapping smears the edge pixel across the whole surface,
    // which is the classic "my repeat does nothing" afternoon.
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    // Anisotropy is silently ignored unless minFilter is a mipmap-linear
    // filter, which is the default and is left alone here on purpose. It
    // earns its cost on a ground plane seen at a grazing angle, which is
    // most of the time in this studio.
    texture.anisotropy = anisotropy;
    return texture;
  });
}

// The metal family is the only one whose pictures are of a conductor, and
// the difference is not a matter of degree: a dielectric reflects white and
// a conductor reflects its own colour. Everything else in the taxonomy --
// brick, clay, stone, slate, concrete, aggregate, mortar, timber, glass,
// plaster, plastic, mineral-wool, paint -- is a dielectric.
function metalnessFor(family) {
  return family === "metal" ? 1.0 : 0.0;
}

/**
 * One material from the library, with every map it has.
 *
 * Returns { material, textures, entry }. The textures are handed back
 * separately because disposing a material does NOT dispose its maps, and
 * something has to remember what to free.
 */
export async function loadLibraryMaterial(entry, options) {
  const settings = options || {};
  const px = settings.px || VIEWPORT_PX;
  const anisotropy = settings.anisotropy || 8;
  const loader = settings.loader || new THREE.TextureLoader();

  const base = settings.base || SKIN_BASE;
  const kinds = (entry.maps || []).filter((kind) => SLOTS[kind]);
  // Only the colour is load-bearing. A material whose relief or roughness
  // map fails arrives flatter, not absent: failing the WHOLE set over one
  // secondary map was how a clicked material silently kept the default
  // look while the tile claimed it was worn.
  const loaded = await Promise.all(kinds.map((kind) =>
    loadTexture(loader, mapUrl(entry.family, entry.name, kind, px, base),
      kind, anisotropy).catch((error) => {
        if (kind === "colour") throw error;
        console.warn("map failed, carrying on without it:",
          entry.family + "/" + entry.name + "/" + kind, error);
        return null;
      })));

  const material = new THREE.MeshPhysicalMaterial({
    // White, so the picture is the colour. A tint multiplies this, which is
    // how the appearance controls go on working without fighting the map.
    color: 0xffffff,
    side: THREE.DoubleSide,
    // These two scalars MULTIPLY their maps rather than replacing them, so
    // anything but 1 quietly rescales every value in the library at once.
    // Leaving metalness at its default 0 is the commonest silent fault in
    // physically based rendering: it zeroes a metalness map entirely.
    roughness: 1.0,
    metalness: metalnessFor(entry.family),
    envMapIntensity: 1.0,
  });

  const textures = [];
  kinds.forEach((kind, index) => {
    if (!loaded[index]) return;
    material[SLOTS[kind]] = loaded[index];
    textures.push(loaded[index]);
  });
  // aoMap reads channel 0, the plain `uv` attribute, in r185. The old rule
  // that it needs a second UV set is dead: aoMap.channel defaults to 0 and
  // only a non-zero channel defines USE_UV1. The jsdoc still says otherwise
  // and contradicts its own code.
  if (material.aoMap) material.aoMapIntensity = settings.occlusion ?? 1.0;
  // In METRES, because the height field is a real depth and the studio is a
  // real building. QS's own convention is that a relief of 1 means 10 mm,
  // measured about the field's mean rather than about mid-grey, and this is
  // that number in three's units.
  if (material.bumpMap) material.bumpScale = (settings.relief ?? 1.0) * 0.01;
  // A material with no roughness map keeps a sensible fixed roughness
  // instead of the 1.0 the scalar wants to be when a map is present.
  if (!material.roughnessMap) material.roughness = 0.85;

  return { material, textures, entry };
}

/**
 * How many times a picture repeats across a surface of a given size.
 *
 * tileMetres is the real-world size of the unit in the picture. A brick
 * photographed at 230 by 61 millimetres laid across an eight metre span
 * repeats 35 times, and that is a number, not a preference.
 */
export function repeatsFor(extentU, extentV, tileMetres) {
  const tile = tileMetres && tileMetres[0] > 0 && tileMetres[1] > 0
    ? tileMetres : [DEFAULT_TILE_METRES, DEFAULT_TILE_METRES];
  return [Math.max(0, extentU) / tile[0], Math.max(0, extentV) / tile[1]];
}

// Used only when a material has no recorded size, which after the fetch
// tool has run means one nobody has ever looked up. Six hundred millimetres
// is a paving slab: wrong for a brick and wrong for a field of gravel, but
// wrong by a factor of three rather than a factor of a thousand, and the
// panel says when it is being used.
export const DEFAULT_TILE_METRES = 0.6;

/**
 * Set the repeat on EVERY map in the set.
 *
 * Each slot carries its own transform uniform -- mapTransform,
 * normalMapTransform, roughnessMapTransform, aoMapTransform -- so setting
 * repeat on the albedo alone leaves the relief and the roughness at 1:1 and
 * the surface comes apart under any light that moves.
 *
 * No needsUpdate is required: repeat feeds texture.matrix, which is
 * recomputed every frame while matrixAutoUpdate is true.
 */
export function setRepeat(set, u, v) {
  for (const texture of set.textures) texture.repeat.set(u, v);
}

/**
 * The two dials over a loaded set: how deep its relief reads, and how much
 * of its own crevice shading it keeps.
 *
 * Both are per-material rather than per-map, so they change nothing on the
 * GPU: no texture is re-uploaded and no shader is recompiled.
 */
export function setSurface(set, relief, occlusion) {
  if (!set) return;
  if (set.material.bumpMap) set.material.bumpScale = relief * 0.01;
  if (set.material.aoMap) set.material.aoMapIntensity = occlusion;
  set.material.needsUpdate = false;
}

/**
 * Free a material and every map it holds.
 *
 * Material.dispose() does not touch textures, and a texture is where the
 * video memory is: four maps at 1024 square, with mipmaps, is about 21 MB
 * that stays allocated for the life of the page if nobody says otherwise.
 */
export function disposeLibraryMaterial(set) {
  if (!set) return;
  for (const texture of set.textures) texture.dispose();
  set.textures.length = 0;
  set.material.dispose();
}
