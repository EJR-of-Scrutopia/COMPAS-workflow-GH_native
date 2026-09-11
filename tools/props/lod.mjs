// Distance tiers for the prop library, as sidecar files beside each LOD0.
//
// A scattered field of 25,375 props ran at 2 fps. Instancing takes care of
// the draw calls; what it cannot take care of is the 88.5 million
// triangles the field still asks the GPU to rasterise, most of them in
// tufts thirty metres from the camera that cover four pixels. Poly Haven
// ships no LODs (see the header of fetch.mjs), so the tiers are cut here,
// with the same meshopt simplifier the fetch already uses to bring a film
// asset under its triangle budget.
//
//     node tools/props/lod.mjs                       # what is missing or stale
//     node tools/props/lod.mjs grass_medium_01__tiny_a [more keys]
//     node tools/props/lod.mjs --force               # rebuild every entry
//
// What it writes, for a manifest entry whose file is <key>.glb:
//     <key>.lod1.glb   about a third of LOD0's triangles
//     <key>.lod2.glb   about an eighth
//     and on the entry: "lods": [{ "file", "triangles" }, ...], tier order
//
// A sidecar is GEOMETRY ONLY. Every texture is stripped before it is
// written, because the maps are most of a prop's bytes and the client
// already holds them: it reuses LOD0's materials, pairing by MESH NAME and
// primitive order. That pairing is the contract this tool has to keep, so
// nothing here joins, flattens or renames. Dedup and prune are fine;
// anything that would give a node or a mesh a different name is not.
//
// A tier that would come out under a dozen triangles is not written. A
// tuft of 80 triangles has no LOD2 worth the fetch, and a two-triangle
// decal has no tiers at all; the entry records only what exists.
//
// The folder the studio scans is the authority on what is a prop (see
// app.py's /api/props), so app.py has to know that <key>.lod1.glb is a
// part of <key> and not a prop of its own. It excludes the sidecar pattern
// from the offered list and still serves the file by name.

import { existsSync } from "node:fs";
import { readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Logger, NodeIO, PropertyType } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import {
  cloneDocument, dedup, dequantize, prune, quantize, simplify, weld,
} from "@gltf-transform/functions";
import { MeshoptSimplifier } from "meshoptimizer";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const OUT = path.join(REPO, "bench", "studio", "props-hd");

// The tiers, as a share of LOD0's triangles. Two of them: a third for the
// middle distance, where a silhouette still has to read, and an eighth for
// the far field, where a plant is a coloured blob a few pixels wide.
const LOD1_RATIO = 0.35;
const LOD2_RATIO = 0.12;
// The error bound is the fraction of the mesh's extent a vertex may move.
// The fetch holds LOD0 to 0.004 because it is what the camera lands on;
// a tier is only ever seen from far off, so its bound is looser, and the
// far tier's looser still or a canopy refuses to come down (fetch.mjs saw
// the same: leaves do not simplify until the bound is wide enough to let
// a leaf go).
const TIERS = [
  { suffix: "lod1", ratio: LOD1_RATIO, error: 0.01 },
  { suffix: "lod2", ratio: LOD2_RATIO, error: 0.03 },
];
// A canopy stops well short of any target at the tier's own bound: the
// first run left beech_european_beech_forest_01 at 63% of its triangles
// when 35% was asked for, because meshopt will not let a leaf go until
// the bound is wider than the leaf. So a tier that has not come within
// this margin of its target is simplified again at each wider bound in
// turn, as fetch.mjs does for LOD0. A tier is only ever seen from far
// off, which is what makes the widest bound affordable.
const TARGET_MARGIN = 1.15;
const WIDER_BOUNDS = [0.08, 0.2];
// Under this a tier is not a model, it is a fetch for nothing.
const MIN_TRIANGLES = 12;

// The wider passes also PRUNE. A canopy is thousands of leaves that share
// no vertex with each other, and an edge collapse can only ever shrink a
// leaf, never remove it: the beech's 124,072-triangle leaf primitive sat
// at 104,278 whatever the bound was. meshopt's Prune flag lets a
// component that is below the error bound go entirely, which took the
// same primitive to 11,641. @gltf-transform/functions passes no flag but
// LockBorder, so the flag rides in on a simplifier that wraps meshopt's.
const PruningSimplifier = {
  ready: MeshoptSimplifier.ready,
  compactMesh: (...args) => MeshoptSimplifier.compactMesh(...args),
  simplifyPoints: (...args) => MeshoptSimplifier.simplifyPoints(...args),
  simplify: (indices, positions, stride, target, error, flags = []) =>
    MeshoptSimplifier.simplify(indices, positions, stride, target, error,
      [...flags, "Prune"]),
};

function triangleCount(doc) {
  let n = 0;
  for (const mesh of doc.getRoot().listMeshes()) {
    for (const p of mesh.listPrimitives()) {
      const idx = p.getIndices();
      n += (idx ? idx.getCount() : p.getAttribute("POSITION").getCount()) / 3;
    }
  }
  return Math.round(n);
}

function primitiveCount(doc) {
  return doc.getRoot().listMeshes()
    .reduce((n, mesh) => n + mesh.listPrimitives().length, 0);
}

// Geometry only. The five core slots are cleared by name so the intent is
// on the page; then every texture still referenced is disposed, which
// catches the slots an extension adds (clearcoat, sheen, transmission,
// specular ...) without this file having to know the list. Materials
// themselves stay: a primitive keeps its material index so the client's
// pairing by primitive order is undisturbed.
function stripTextures(doc) {
  const root = doc.getRoot();
  for (const material of root.listMaterials()) {
    material.setBaseColorTexture(null);
    material.setMetallicRoughnessTexture(null);
    material.setNormalTexture(null);
    material.setOcclusionTexture(null);
    material.setEmissiveTexture(null);
  }
  for (const texture of root.listTextures()) texture.dispose();
}

// The sidecar name for a tier: grass_medium_01__tiny_a.glb -> .lod1.glb.
function sidecarName(file, suffix) {
  return file.replace(/\.glb$/i, "") + "." + suffix + ".glb";
}

// One tier of one prop, in a clone so LOD0 is untouched, or null when
// the tier is not worth writing.
async function buildTier(source, tier) {
  const target = triangleCount(source) * tier.ratio;
  // A tier whose own target is under the minimum is not cut at all. The
  // simplifier stops short of a target this small and hands back a dozen
  // triangles for an 80-triangle tuft, which is a file, a fetch and a
  // manifest line for nothing anybody could see.
  if (target < MIN_TRIANGLES) return null;
  let doc = source;
  let triangles = triangleCount(source);
  for (const error of [tier.error, ...WIDER_BOUNDS]) {
    if (triangles <= target * TARGET_MARGIN) break;
    // Each pass works on a clone of the best so far, because a pruning
    // pass can take everything: flower_gazania__e is 2,104 triangles of
    // petals that share no vertex, and at the 0.08 bound every one of
    // them was under the bound and went, leaving no far tier at all. A
    // pass that leaves less than a model is discarded, not written.
    const attempt = cloneDocument(doc).setLogger(source.getLogger());
    await attempt.transform(simplify({
      simplifier: error === tier.error ? MeshoptSimplifier : PruningSimplifier,
      ratio: Math.max(0.02, target / triangles),
      error,
      lockBorder: false,
    }));
    const left = triangleCount(attempt);
    if (primitiveCount(attempt) === 0 || left < MIN_TRIANGLES) break;
    doc = attempt;
    triangles = left;
  }
  if (doc === source || triangles < MIN_TRIANGLES) return null;
  stripTextures(doc);
  // keepLeaves, because a node that has lost its mesh to the simplifier
  // is still a name in LOD0's hierarchy, and dedup on accessors only:
  // deduping meshes would fold two identical tufts under one name and
  // break the pairing for the other.
  await doc.transform(
    prune({ keepLeaves: true }),
    quantize({ quantizePosition: 14, quantizeNormal: 10, quantizeTexcoord: 12 }),
    prune({ keepLeaves: true }),
    dedup({ propertyTypes: [PropertyType.ACCESSOR] }),
  );
  return { doc, triangles };
}

async function mtime(file) {
  try { return (await stat(file)).mtimeMs; } catch { return null; }
}

// An entry is due when it has never been tiered, when a sidecar it
// records has gone missing, or when the model is newer than any of its
// sidecars (a re-fetch or a re-split rewrote it).
async function isStale(entry) {
  if (!Array.isArray(entry.lods)) return true;
  const model = await mtime(path.join(OUT, entry.file));
  for (const lod of entry.lods) {
    const side = await mtime(path.join(OUT, lod.file));
    if (side === null || model > side) return true;
  }
  return false;
}

async function tierOne(io, entry) {
  const file = path.join(OUT, entry.file);
  if (!existsSync(file)) {
    console.log(`${entry.key.padEnd(44)} skipped: no file ${entry.file}`);
    return null;
  }
  const source = await io.read(file);
  // The simplifier reasons in floats. The integers come off first and go
  // back on at the end, exactly as split.mjs does. And WELD, even though
  // the fetch welded: quantising afterwards folded distinct floats onto
  // the same integer, so boulder_01 arrives with 55,793 vertices where
  // 31,609 are distinct, and simplify() will not re-weld a primitive that
  // is already indexed. Unwelded, every seam is a border and an edge
  // collapse has nowhere to go: the boulder came out at 97% of itself.
  await source.transform(dequantize(), weld());
  const lod0 = triangleCount(source);

  const lods = [];
  const counts = [lod0];
  let bytes = 0;
  for (const tier of TIERS) {
    const name = sidecarName(entry.file, tier.suffix);
    const built = await buildTier(source, tier);
    if (!built) {
      // A tier this run did not write must not survive from an earlier
      // run: the manifest would say one thing and the folder another.
      // This is the only .glb the tool ever deletes, and it is its own.
      await rm(path.join(OUT, name), { force: true });
      counts.push("-");
      continue;
    }
    const packed = await io.writeBinary(built.doc);
    await writeFile(path.join(OUT, name), packed);
    lods.push({ file: name, triangles: built.triangles });
    counts.push(built.triangles);
    bytes += packed.byteLength;
  }
  console.log(`${entry.key.padEnd(44)} ${counts.join(" -> ")} tris`
    + `  ${(bytes / 1e3).toFixed(1)} kB`);
  return { lods, bytes };
}

async function main() {
  const args = process.argv.slice(2);
  const force = args.includes("--force");
  const named = args.filter((a) => !a.startsWith("--"));

  // Warnings only: prune reports every accessor it drops at info level,
  // and over 270 props that buries the one line per prop this prints.
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
    .setLogger(new Logger(Logger.Verbosity.WARN));
  const manifestPath = path.join(OUT, "props.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));

  let entries;
  if (named.length) {
    entries = [];
    for (const key of named) {
      const entry = manifest.props.find((p) => p.key === key);
      if (entry) entries.push(entry);
      else console.log(`${key}: not in the manifest`);
    }
  } else {
    entries = [];
    for (const entry of manifest.props) {
      if (force || await isStale(entry)) entries.push(entry);
    }
  }

  let done = 0, sidecars = 0, bytes = 0;
  const perTier = TIERS.map(() => 0);
  let lod0 = 0;
  for (const entry of entries) {
    const result = await tierOne(io, entry);
    if (!result) continue;
    // Everything else on the entry stays as it was; only lods is replaced.
    entry.lods = result.lods;
    done += 1;
    sidecars += result.lods.length;
    bytes += result.bytes;
    lod0 += entry.triangles || 0;
    for (const lod of result.lods) {
      perTier[TIERS.findIndex((t) => lod.file.endsWith("." + t.suffix + ".glb"))] += lod.triangles;
    }
  }

  if (done) {
    manifest.props.sort((a, b) => a.group.localeCompare(b.group) || a.key.localeCompare(b.key));
    await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
  }
  console.log(`\n${done} props tiered, ${sidecars} sidecars, `
    + `${(bytes / 1e6).toFixed(2)} MB`);
  console.log(`triangles  LOD0 ${lod0}`
    + TIERS.map((t, i) => `  ${t.suffix} ${perTier[i]}`).join(""));
}

await main();
