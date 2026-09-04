// Turn Poly Haven's models into props a browser can hold.
//
// Poly Haven has quietly become a photoscan house: 521 models, all CC0 with
// explicit permission to redistribute, and they are exactly the trees,
// rocks and street furniture an architectural scene needs. They are also
// film assets. tree_small_02 is 4.65 million polygons with a 95 MB buffer
// and there are no LODs, so nothing here can be dropped into a viewport as
// it comes.
//
// There is a second problem that decides the shape of this script. Poly
// Haven publishes no packed .glb: a model is a .gltf, a separate .bin and a
// folder of textures, and the studio's own prop route rejects any filename
// containing a path separator, so a sidecar cannot be served at all. Every
// prop has to be packed into one self-contained file here.
//
// And one trap worth naming, because it is silent. The .bin URL inside the
// 1k entry points at the 8k PATH -- geometry is shared across resolutions
// and only the textures differ -- so a URL built by substituting "1k" for
// "8k" fetches a file that does not exist, or worse, one that does. Always
// use the url the API returns.
//
//     node tools/props/fetch.mjs                 # the whole list
//     node tools/props/fetch.mjs fire_hydrant    # one, or a few
//
// Nothing here runs in the studio. It is a build step, and its output is a
// folder of .glb files the studio reads like any other library.

import { createHash } from "node:crypto";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import {
  dedup, prune, weld, simplify, resample, flatten, join, quantize,
  getBounds,
} from "@gltf-transform/functions";
import { MeshoptSimplifier } from "meshoptimizer";
import sharp from "sharp";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const OUT = path.join(REPO, "bench", "studio", "props-hd");
const WORK = path.join(HERE, ".work");
// Downloads are kept. pine_tree_01 is 958 MB of source and a ratio is not
// worth tuning at that price, nor is Poly Haven worth asking twice.
const CACHE = path.join(HERE, ".cache");

// Poly Haven's terms ask to be named in the User-Agent, and it costs a line.
const AGENT = "Bench Studio prop library (Ananke Eidos)";

// The budget, as policy rather than hope. A prop that misses it is reported
// rather than quietly bloating the scene, because draw calls and triangles
// are what decide whether a vault study can afford entourage at all.
const CLASS = {
  // A canopy is not a boulder. Its silhouette is a cloud of alpha-clipped
  // leaves that meshopt cannot weld across, so the target is lower and the
  // maps smaller, and the reason a tree still costs three megabytes is that
  // it is a photoscan of a tree.
  canopy:  { triangles:  60000, bytes: 4.0e6, texture: 512 },
  hero:    { triangles:  90000, bytes: 3.0e6, texture: 1024 },
  mid:     { triangles:  30000, bytes: 1.2e6, texture: 512 },
  clutter: { triangles:   6000, bytes: 0.35e6, texture: 256 },
};

// group is what the studio's grid sorts by and what decides whether a prop
// casts a shadow: nobody will miss the shadow of a tuft of grass, and a
// draw call for it costs the same as one for a building.
const LIST = [
  // Planting. These are the heavy ones and the reason for the simplifier,
  // and three of them are not here any more.
  //
  // fir_tree_01, pine_tree_01 and island_tree_02 were dropped on 2026-09-04
  // after being looked at. At the 60,000 triangle budget their canopies come
  // through as a haze of dark speckle: the leaves are alpha-cut cards, two
  // triangles each, and a simplifier asked to weld them has nothing to weld
  // that is not a leaf. pine_tree_01 alone is 17.2 million triangles behind
  // 958 MB of source. Raised to 400,000 they read properly and weigh 27 to
  // 36 MB each, which is not a browser asset at any budget worth defending.
  //
  // The three below survive because their canopies were built from fewer,
  // larger cards. The real fix for the others is to rebuild a canopy in
  // Blender as alpha-clipped cards over Poly Haven's own leaf textures,
  // which reaches a photoreal-reading tree at about 20,000 triangles.
  { slug: "tree_small_02",       label: "Broadleaf tree",   group: "planting", size: "canopy" },
  { slug: "searsia_lucida",      label: "Searsia",          group: "planting", size: "canopy" },
  { slug: "fir_sapling_medium",  label: "Fir sapling",      group: "planting", size: "mid" },
  { slug: "tree_stump_01",       label: "Tree stump",       group: "planting", size: "mid" },
  { slug: "dead_tree_trunk_02",  label: "Dead trunk",       group: "planting", size: "mid" },
  { slug: "fern_02",             label: "Fern",             group: "planting", size: "clutter" },
  { slug: "nettle_plant",        label: "Nettles",          group: "planting", size: "clutter" },
  { slug: "dandelion_01",        label: "Dandelion",        group: "planting", size: "clutter" },
  { slug: "flower_gazania",      label: "Gazania",          group: "planting", size: "clutter" },
  { slug: "potted_plant_01",     label: "Potted plant",     group: "planting", size: "mid" },
  // Rock. Photoscanned, and the most convincing thing in the catalogue.
  { slug: "namaqualand_boulder_02", label: "Boulder",       group: "site", size: "mid" },
  { slug: "namaqualand_boulders_01", label: "Boulders",     group: "site", size: "mid" },
  { slug: "namaqualand_stones_01", label: "Stones",         group: "site", size: "clutter" },
  { slug: "boulder_01",          label: "Small boulder",    group: "site", size: "mid" },
  { slug: "rock_moss_set_01",    label: "Mossy rocks",      group: "site", size: "mid" },
  { slug: "sand_rocks_small_01", label: "Sand rocks",       group: "site", size: "clutter" },
  // Street and site.
  { slug: "fire_hydrant",        label: "Fire hydrant",     group: "street", size: "mid" },
  { slug: "concrete_road_barrier", label: "Road barrier",   group: "street", size: "mid" },
  { slug: "utility_box_01",      label: "Utility box",      group: "street", size: "mid" },
  { slug: "water_manhole_cover", label: "Manhole cover",    group: "street", size: "clutter" },
  { slug: "modular_electricity_poles", label: "Power pole", group: "street", size: "mid" },
  { slug: "modular_chainlink_fence", label: "Chainlink fence", group: "street", size: "mid" },
  { slug: "WetFloorSign_01",     label: "Wet floor sign",   group: "site", size: "clutter" },
  { slug: "cement_bag",          label: "Cement bag",       group: "site", size: "clutter" },
  { slug: "Barrel_02",           label: "Barrel",           group: "site", size: "clutter" },
  // The 2026-09-04 vegetation expansion: every entry below was verified
  // against the API's own gltf .bin sizes (the honest number; polycount
  // lies for geonodes assets) and sits far under the canopy-failure class.
  // Poly Haven has no oak/maple/birch: what a CC0 catalogue holds is what
  // a CC0 library gets.
  { slug: "quiver_tree_01",      label: "Quiver tree",      group: "planting", size: "canopy" },
  { slug: "quiver_tree_02",      label: "Quiver tree small", group: "planting", size: "mid" },
  { slug: "othonna_cerarioides", label: "Othonna tree",     group: "planting", size: "canopy" },
  { slug: "pachira_aquatica_01", label: "Pachira",          group: "planting", size: "canopy" },
  { slug: "fir_sapling",         label: "Small fir",        group: "planting", size: "mid" },
  { slug: "pine_sapling_small",  label: "Small pine",       group: "planting", size: "mid" },
  { slug: "dead_quiver_trunk",   label: "Quiver trunk",     group: "planting", size: "clutter" },
  { slug: "tree_stump_02",       label: "Old stump",        group: "planting", size: "mid" },
  { slug: "didelta_spinosa",     label: "Didelta shrub",    group: "planting", size: "mid" },
  { slug: "shrub_01",            label: "Flowering shrub",  group: "planting", size: "mid" },
  { slug: "shrub_02",            label: "Hedge mass",       group: "planting", size: "mid" },
  { slug: "shrub_03",            label: "Meadow shrub",     group: "planting", size: "clutter" },
  { slug: "shrub_04",            label: "Undergrowth",      group: "planting", size: "clutter" },
  { slug: "wild_rooibos_bush",   label: "Rooibos bush",     group: "planting", size: "mid" },
  { slug: "weed_plant_02",       label: "Weeds",            group: "planting", size: "clutter" },
  { slug: "anthurium_botany_01", label: "Anthurium",        group: "planting", size: "mid" },
  { slug: "calathea_orbifolia_01", label: "Calathea",       group: "planting", size: "clutter" },
  { slug: "flower_ursinia",      label: "Ursinia",          group: "planting", size: "clutter" },
  { slug: "periwinkle_plant",    label: "Periwinkle",       group: "planting", size: "clutter" },
  { slug: "crystalline_iceplant", label: "Iceplant",        group: "planting", size: "clutter" },
  { slug: "cheiridopsis_succulent", label: "Cheiridopsis",  group: "planting", size: "clutter" },
  { slug: "celandine_01",        label: "Celandine",        group: "planting", size: "clutter" },
  { slug: "grass_medium_01",     label: "Grass clumps",     group: "planting", size: "clutter" },
  { slug: "grass_medium_02",     label: "Grass tufts",      group: "planting", size: "clutter" },
  { slug: "potted_plant_02",     label: "Planter plant",    group: "planting", size: "mid" },
  { slug: "potted_plant_04",     label: "Potted aloe",      group: "planting", size: "clutter" },
  { slug: "planter_box_01",      label: "Planter box",      group: "planting", size: "clutter" },
  { slug: "planter_box_03",      label: "Long planter",     group: "planting", size: "clutter" },
  // Buildings: DROPPED 2026-09-05 on Param's review. Poly Haven's
  // building assets are modular KITS -- disassembled facade panels,
  // fort wall segments, pier sections floating in a bounding box --
  // "obviously pieces of buildings that want combining", useless as
  // one-click props. Dropped: modular_urban_apartments_facade,
  // modular_factory_facade, modular_fort_01, modular_wooden_pier,
  // modular_fire_escape. Photoreal people likewise exist under no CC0
  // licence anywhere -- that hole is documented in the wave register
  // with the account-gated sources Param can pull himself.
  { slug: "utility_box_02",      label: "Utility cabinet",  group: "street", size: "mid" },
  { slug: "concrete_road_barrier_02", label: "Road barrier low", group: "street", size: "clutter" },
  // The 2026-09-04 tree-and-rock sweep: everything left in the catalogue
  // that is a tree, a trunk, a root or a rock, minus the three canopy
  // failures already dropped above (fir_tree_01, pine_tree_01,
  // island_tree_02 stay out; their verdict was rendered, not guessed).
  // Ten more were offered to the 30 MB pre-flight guard on 2026-09-04 and
  // refused on the API's own .bin sizes, so they are not listed either:
  // jacaranda_tree (214.6 MB), pine_sapling_medium (267.8 MB),
  // island_tree_01 (66.3), island_tree_03 (84.9), searsia_burchellii
  // (34.6), coast_land_rocks_02/03/04 (39.6/34.0/33.6), coast_rocks_02
  // (38.5) and coastal_cliff_04 (46.5). The catalogue holds no broadleaf
  // shade tree under the line; that hole stays a Blender job, not a fetch.
  { slug: "dead_tree_trunk",     label: "Fallen trunk",     group: "planting", size: "mid" },
  { slug: "root_cluster_01",     label: "Root cluster",     group: "planting", size: "mid" },
  { slug: "root_cluster_02",     label: "Root mat",         group: "planting", size: "clutter" },
  { slug: "single_root",         label: "Single root",      group: "planting", size: "clutter" },
  { slug: "pine_roots",          label: "Pine roots",       group: "planting", size: "clutter" },
  { slug: "bark_debris_01",      label: "Bark debris",      group: "planting", size: "clutter" },
  // Rock, the rest of it. Namaqualand first, then the verdant-trail and
  // smugglers-cove formations; the coast pieces are landscape-scale and
  // priced as heroes because their silhouettes are the whole point.
  { slug: "namaqualand_boulder_03", label: "Boulder large", group: "site", size: "mid" },
  { slug: "namaqualand_boulder_04", label: "Boulder round", group: "site", size: "mid" },
  { slug: "namaqualand_boulder_05", label: "Boulder low",   group: "site", size: "mid" },
  { slug: "namaqualand_boulder_06", label: "Boulder tall",  group: "site", size: "mid" },
  { slug: "namaqualand_rocks_01", label: "Quartz rocks",    group: "site", size: "clutter" },
  { slug: "namaqualand_cliff_01", label: "Cliff outcrop",   group: "site", size: "hero" },
  { slug: "namaqualand_cliff_02", label: "Cliff wall",      group: "site", size: "hero" },
  { slug: "mountainside",        label: "Mountainside",     group: "site", size: "hero" },
  { slug: "rock_face_01",        label: "Rock face",        group: "site", size: "mid" },
  { slug: "rock_face_02",        label: "Rock face small",  group: "site", size: "mid" },
  { slug: "rock_moss_set_02",    label: "Mossy rocks 2",    group: "site", size: "mid" },
  { slug: "rock_07",             label: "Rock",             group: "site", size: "clutter" },
  { slug: "rock_09",             label: "Rock small",       group: "site", size: "clutter" },
  { slug: "stone_01",            label: "Stone",            group: "site", size: "clutter" },
  { slug: "coast_rocks_01",      label: "Coast formation",  group: "site", size: "hero" },
  { slug: "coast_rocks_03",      label: "Coast formation 3", group: "site", size: "hero" },
  { slug: "coast_rocks_05",      label: "Reef rock",        group: "site", size: "mid" },
  { slug: "coast_line_01",       label: "Coastline",        group: "site", size: "hero" },
  { slug: "coast_line_02",       label: "Coastline 2",      group: "site", size: "hero" },
  { slug: "coastal_cliff_01",    label: "Coastal cliff",    group: "site", size: "hero" },
  { slug: "coastal_cliff_02",    label: "Coastal cliff 2",  group: "site", size: "hero" },
  { slug: "moon_rock_01",        label: "Moon rock 1",      group: "site", size: "clutter" },
  { slug: "moon_rock_02",        label: "Moon rock 2",      group: "site", size: "clutter" },
  { slug: "moon_rock_03",        label: "Moon rock 3",      group: "site", size: "clutter" },
  { slug: "moon_rock_04",        label: "Moon rock 4",      group: "site", size: "clutter" },
  { slug: "moon_rock_05",        label: "Moon rock 5",      group: "site", size: "clutter" },
  { slug: "moon_rock_06",        label: "Moon rock 6",      group: "site", size: "clutter" },
  { slug: "moon_rock_07",        label: "Moon rock 7",      group: "site", size: "clutter" },
];

// The pre-flight rule that would have caught every canopy failure before a
// byte was downloaded: the API's gltf .bin size at the chosen resolution is
// the honest measure of what the export really holds.
const MAX_SOURCE_BIN_BYTES = 30e6;

async function getJson(url) {
  const response = await fetch(url, { headers: { "User-Agent": AGENT } });
  if (!response.ok) throw new Error(`${response.status} for ${url}`);
  return response.json();
}

async function download(url, destination, md5) {
  await mkdir(path.dirname(destination), { recursive: true });
  // Keyed on the URL, so the shared .bin that every resolution points at is
  // fetched once however many times it is asked for.
  const key = createHash("sha1").update(url).digest("hex");
  const cached = path.join(CACHE, key);
  let bytes = null;
  if (existsSync(cached)) {
    bytes = await readFile(cached);
    if (md5 && createHash("md5").update(bytes).digest("hex") !== md5) {
      bytes = null;                 // a bad cache entry is not a cache entry
    }
  }
  if (!bytes) {
    const response = await fetch(url, { headers: { "User-Agent": AGENT } });
    if (!response.ok) throw new Error(`${response.status} for ${url}`);
    bytes = Buffer.from(await response.arrayBuffer());
    if (md5) {
      const got = createHash("md5").update(bytes).digest("hex");
      if (got !== md5) throw new Error(`md5 mismatch for ${url}`);
    }
    await mkdir(CACHE, { recursive: true });
    await writeFile(cached, bytes);
  }
  await writeFile(destination, bytes);
  return bytes.length;
}

// Textures are where a prop's bytes are, so this is the lever that matters,
// and it is done with sharp directly rather than through textureCompress.
// That transform asks libvips for a colourspace conversion the installed
// sharp refuses ("colourspace: parameter space not set"), and in any case
// there is nothing to convert: the sources are already JPEG and staying
// JPEG avoids needing EXT_texture_webp on the loader for no gain a
// photoscan can show.
//
// Never upscale. A 1k source asked for 2048 is a bigger file with no more
// information in it, which is the same rule the material library's own lod
// tiers follow.
async function shrinkTextures(document, longest) {
  for (const texture of document.getRoot().listTextures()) {
    const image = texture.getImage();
    if (!image) continue;
    const meta = await sharp(Buffer.from(image)).metadata();
    const biggest = Math.max(meta.width || 0, meta.height || 0);
    // Never upscale. A 1k source asked for 2048 is a bigger file with no
    // more in it, which is the rule the material library's lod tiers follow.
    if (!biggest || biggest <= longest) continue;
    const resized = await sharp(Buffer.from(image))
      .resize({ width: longest, height: longest, fit: "inside" })
      .jpeg({ quality: 86, mozjpeg: true })
      .toBuffer();
    texture.setImage(new Uint8Array(resized));
    texture.setMimeType("image/jpeg");
  }
}

function triangleCount(document) {
  let total = 0;
  for (const mesh of document.getRoot().listMeshes()) {
    for (const primitive of mesh.listPrimitives()) {
      const indices = primitive.getIndices();
      const position = primitive.getAttribute("POSITION");
      const count = indices ? indices.getCount() : (position ? position.getCount() : 0);
      total += Math.floor(count / 3);
    }
  }
  return total;
}

function boundsOf(document) {
  // The SCENE's bounds, not the accessors'. quantize maps positions into a
  // [-1, 1] cube and puts the real scale on the node above them, so reading
  // POSITION directly measures the cube: every prop came back with a 2.0 in
  // it, and a two metre wide fire hydrant is how that shows.
  const scene = document.getRoot().getDefaultScene()
    || document.getRoot().listScenes()[0];
  if (!scene) return null;
  const box = getBounds(scene);
  if (!box || !Number.isFinite(box.min[0])) return null;
  // glTF is Y-up, and the studio stands its props on the ground, so the
  // height a person cares about is the Y extent.
  return {
    width: +(box.max[0] - box.min[0]).toFixed(3),
    height: +(box.max[1] - box.min[1]).toFixed(3),
    depth: +(box.max[2] - box.min[2]).toFixed(3),
  };
}

async function buildOne(io, item) {
  const budget = CLASS[item.size];
  const files = await getJson(`https://api.polyhaven.com/files/${item.slug}`);
  const gltf = files.gltf && (files.gltf["1k"] || files.gltf["2k"]);
  if (!gltf || !gltf.gltf) throw new Error("no gltf bundle published");
  const bundle = gltf.gltf;

  // Refuse the canopy-failure class before a byte is downloaded: the
  // included .bin size is the honest measure of what the export holds
  // (polycount lies for geometry-nodes assets, in both directions). All
  // three known failures -- pine_tree_01, fir_tree_01, island_tree_02 --
  // and every flagged sibling would have been caught by this one rule.
  let sourceBytes = 0;
  for (const entry of Object.values(bundle.include || {})) {
    sourceBytes += entry.size || 0;
  }
  if (sourceBytes > MAX_SOURCE_BIN_BYTES) {
    throw new Error(`source geometry is ${(sourceBytes / 1e6).toFixed(1)} MB; `
      + `over the ${(MAX_SOURCE_BIN_BYTES / 1e6).toFixed(0)} MB line a dense `
      + `canopy cannot decimate across`);
  }

  const work = path.join(WORK, item.slug);
  await rm(work, { recursive: true, force: true });
  await mkdir(work, { recursive: true });

  const main = path.join(work, `${item.slug}.gltf`);
  let fetched = await download(bundle.url, main, bundle.md5);
  for (const [name, entry] of Object.entries(bundle.include || {})) {
    // The name is the path the .gltf refers to, relative to itself, and it
    // is the ONLY thing that decides where the file goes. The url is
    // whatever Poly Haven serves it from, which for the shared .bin is the
    // 8k folder whatever resolution was asked for.
    fetched += await download(entry.url, path.join(work, name), entry.md5);
  }

  const document = await io.read(main);
  const before = { triangles: triangleCount(document), bytes: fetched };

  await document.transform(
    dedup(),
    flatten(),
    join(),
    weld(),
    resample(),
    prune({ keepAttributes: false, keepLeaves: false }),
  );

  // Simplify only what is over budget, and only as far as it has to go.
  // A photoscanned boulder holds together at almost any ratio; a canopy of
  // geometry-node leaves does not, so the ratio is reported and the error
  // bound kept tight enough that a failure looks like a failure.
  const now = triangleCount(document);
  if (now > budget.triangles) {
    // Two passes, because meshopt will not cross a seam it has been told
    // to keep and a photoscan is mostly seams: the first pass tries to
    // preserve them, and if it has not come close the second lets them go.
    // A boulder has no silhouette anybody knows, which is exactly the case
    // where a looser bound costs nothing anyone can see.
    await document.transform(simplify({
      simplifier: MeshoptSimplifier,
      ratio: Math.max(0.02, budget.triangles / now),
      error: 0.004,
      lockBorder: true,
    }));
    let after = triangleCount(document);
    if (after > budget.triangles * 1.15) {
      await document.transform(simplify({
        simplifier: MeshoptSimplifier,
        ratio: Math.max(0.02, budget.triangles / after),
        error: 0.02,
        lockBorder: false,
      }));
      after = triangleCount(document);
    }
    // And once more for a canopy, which stops well short of any target it
    // is given until the error bound is wide enough to let a leaf go.
    if (after > budget.triangles * 1.15) {
      await document.transform(simplify({
        simplifier: MeshoptSimplifier,
        ratio: Math.max(0.02, budget.triangles / after),
        error: 0.08,
        lockBorder: false,
      }));
    }
  }

  const bounds = boundsOf(document);
  await shrinkTextures(document, budget.texture);
  // Positions, normals and UVs as integers rather than 32-bit floats.
  // KHR_mesh_quantization is understood by three's own GLTFLoader with
  // nothing vendored, and geometry is most of what is left once the maps
  // have shrunk: 14 bits of position over a prop's own bounding box is a
  // tenth of a millimetre on a two metre boulder, finer than the scan.
  await document.transform(
    quantize({
      quantizePosition: 14,
      quantizeNormal: 10,
      quantizeTexcoord: 12,
    }),
    prune(),
    dedup(),
  );

  const packed = await io.writeBinary(document);
  await mkdir(OUT, { recursive: true });
  const out = path.join(OUT, `${item.slug}.glb`);
  await writeFile(out, packed);
  await rm(work, { recursive: true, force: true });

  return {
    key: item.slug,
    label: item.label,
    file: `${item.slug}.glb`,
    group: item.group,
    sizeMetres: bounds ? [bounds.width, bounds.height, bounds.depth] : null,
    triangles: triangleCount(document),
    bytes: packed.byteLength,
    credit: `${item.label} by Poly Haven`,
    licence: "CC0 1.0",
    source: `https://polyhaven.com/a/${item.slug}`,
    before,
    budget,
  };
}

// Re-measure what is already on disk, without fetching a byte. The trees
// alone are a gigabyte and a half of source, which is not a price worth
// paying twice to correct a number.
async function remeasure(io) {
  const manifestPath = path.join(OUT, "props.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  for (const prop of manifest.props) {
    const file = path.join(OUT, prop.file);
    if (!existsSync(file)) continue;
    const document = await io.read(file);
    const bounds = boundsOf(document);
    prop.sizeMetres = bounds
      ? [bounds.width, bounds.height, bounds.depth] : null;
    console.log(`${prop.key.padEnd(28)}${prop.sizeMetres
      ? prop.sizeMetres.map((n) => n.toFixed(2)).join(" x ") + " m"
      : "unmeasurable"}`);
  }
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
  console.log(`\n${manifest.props.length} re-measured`);
}

async function main() {
  const wanted = process.argv.slice(2);
  if (wanted[0] === "--measure") {
    await remeasure(new NodeIO().registerExtensions(ALL_EXTENSIONS));
    return;
  }
  const list = wanted.length
    ? LIST.filter((item) => wanted.includes(item.slug))
    : LIST;
  if (!list.length) {
    console.log("nothing matched; known slugs:\n  "
      + LIST.map((i) => i.slug).join("\n  "));
    return;
  }

  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const built = [];
  const failed = [];
  for (const item of list) {
    process.stdout.write(`${item.slug.padEnd(32)}`);
    try {
      const result = await buildOne(io, item);
      built.push(result);
      const over = result.triangles > result.budget.triangles
        || result.bytes > result.budget.bytes;
      console.log(
        `${String(result.before.triangles).padStart(9)} tri`
        + ` -> ${String(result.triangles).padStart(7)}`
        + `  ${(result.before.bytes / 1e6).toFixed(1).padStart(6)} MB`
        + ` -> ${(result.bytes / 1e6).toFixed(2).padStart(6)}`
        + (over ? "   OVER BUDGET" : ""));
    } catch (error) {
      failed.push({ slug: item.slug, why: error.message });
      console.log(`FAILED: ${error.message}`);
    }
  }

  // The manifest the studio reads. Written whole, from what was actually
  // built, so a prop that failed cannot be offered and then 404.
  const manifest = {
    library: "Poly Haven, CC0. Decimated and packed by tools/props/fetch.mjs.",
    props: built.map(({ before, budget, ...keep }) => keep),
  };
  await mkdir(OUT, { recursive: true });
  const manifestPath = path.join(OUT, "props.json");
  let existing = { props: [] };
  if (existsSync(manifestPath)) {
    try {
      existing = JSON.parse(await readFile(manifestPath, "utf8"));
    } catch { /* a damaged manifest is replaced, not repaired */ }
  }
  // A partial run adds to what is there rather than replacing it.
  const byKey = new Map((existing.props || []).map((p) => [p.key, p]));
  for (const prop of manifest.props) byKey.set(prop.key, prop);
  manifest.props = [...byKey.values()].sort(
    (a, b) => a.group.localeCompare(b.group) || a.key.localeCompare(b.key));
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");

  const notice = [
    "Every model in this folder is from Poly Haven and is CC0 1.0.",
    "Poly Haven asks for no credit and this file is offered anyway.",
    "",
    ...manifest.props.map((p) => `${p.key}\n  ${p.label}\n  ${p.source}`),
  ].join("\n");
  await writeFile(path.join(OUT, "NOTICE.txt"), notice + "\n");

  console.log(`\n${built.length} built, ${failed.length} failed, into ${OUT}`);
  for (const f of failed) console.log(`  ${f.slug}: ${f.why}`);
}

await main();
