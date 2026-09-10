// Split a prop that is a ROW OF VARIANTS into one prop per variant.
//
// A Poly Haven grass, flower or weed download is usually six or eight
// tufts laid side by side in a line, and the fetch brought each one in as
// a single model: grass_medium_01 is 5.6 m wide and 0.34 m tall, dandelion
// _01 is 4.2 m wide. Scattered as-is, every placement drops the whole line
// and claims a keep-out disc the width of the line, which is why a field
// of grass came out sparse and why every clump was the same clump (Param:
// "many of the objects are imported as a line of different variants of the
// prop, not just one item ... making sure that each type is one object we
// can make many variants of").
//
// The variants are NOT separate nodes. Every one of these files is one
// mesh, one primitive, one material: the tufts are fused into a single
// index buffer. So a variant has to be found the way a solid is found in
// a soup of triangles -- connected components over shared vertices, then
// components gathered into clusters by the gaps between them along the
// row -- and each cluster rebuilt as its own primitive with only the
// vertices it uses, recentred on its own footprint, in a copy of the
// document that keeps the material and the textures.
//
//     node tools/props/split.mjs                # report every candidate
//     node tools/props/split.mjs grass_medium_01 # split one, write files
//     node tools/props/split.mjs --all           # split every row found
//
// What it writes, for a slug with K variants:
//     <slug>__v1.glb ... <slug>__vK.glb   beside the original
//     props.json entries for each, with family: <slug>
//     the original moved to props-hd/rows/<slug>.glb, out of the folder
//     the studio scans (the FOLDER is the authority; a row left in place
//     would go on being offered as a prop)
//
// Textures are duplicated into each variant. A .glb is self-contained and
// cannot share a buffer with a sibling file; the cost is a few megabytes
// per species and the client loads a template once, so it is paid once.

import { existsSync } from "node:fs";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Document, NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { cloneDocument, dedup, dequantize, getBounds, prune, quantize } from "@gltf-transform/functions";

import { noticeFor } from "./notice.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const OUT = path.join(REPO, "bench", "studio", "props-hd");
const ROWS = path.join(OUT, "rows");

// A row is wide and flat. Anything taller than it is wide is a plant, not
// a line of plants, whatever its node count says.
const ROW_ASPECT = 2.5;
// Components closer than this fraction of the row's length are the same
// tuft: a blade of grass does not share a vertex with the blade beside it,
// so connectivity alone would split every tuft into its blades.
const GAP_FRACTION = 0.03;
// Fewer than this and it is one plant with a stray leaf, not a row.
const MIN_VARIANTS = 2;
// A cluster carrying less than this share of the triangles is a stray
// blade, not a plant, and is folded into its neighbour.
const FRAGMENT_FRACTION = 0.01;

function boundsOf(primitive) {
  const position = primitive.getAttribute("POSITION");
  return { min: position.getMin([]), max: position.getMax([]) };
}

// Disjoint set over vertex indices: two vertices are one component when a
// triangle joins them.
class Union {
  constructor(n) {
    this.parent = new Int32Array(n);
    for (let i = 0; i < n; i += 1) this.parent[i] = i;
  }
  find(i) {
    while (this.parent[i] !== i) {
      this.parent[i] = this.parent[this.parent[i]];
      i = this.parent[i];
    }
    return i;
  }
  join(a, b) {
    const ra = this.find(a), rb = this.find(b);
    if (ra !== rb) this.parent[ra] = rb;
  }
}

// The triangles of a primitive, as flat index triples, whether or not it
// is indexed.
function trianglesOf(primitive) {
  const indices = primitive.getIndices();
  const count = primitive.getAttribute("POSITION").getCount();
  if (indices) return indices.getArray();
  const flat = new Uint32Array(count);
  for (let i = 0; i < count; i += 1) flat[i] = i;
  return flat;
}

// Which variant each triangle belongs to, or null when the model is not
// a row. Returns { clusters: [[triangleIndex, ...], ...], axis, note }.
function findVariants(primitive) {
  const position = primitive.getAttribute("POSITION");
  const vertices = position.getCount();
  const tris = trianglesOf(primitive);
  const union = new Union(vertices);
  for (let t = 0; t < tris.length; t += 3) {
    union.join(tris[t], tris[t + 1]);
    union.join(tris[t], tris[t + 2]);
  }

  // Per component: an XZ bounding box, from its vertices.
  const boxes = new Map();
  const point = [0, 0, 0];
  for (let v = 0; v < vertices; v += 1) {
    const root = union.find(v);
    position.getElement(v, point);
    let box = boxes.get(root);
    if (!box) {
      box = { minX: point[0], maxX: point[0], minZ: point[2], maxZ: point[2], root };
      boxes.set(root, box);
    } else {
      if (point[0] < box.minX) box.minX = point[0];
      if (point[0] > box.maxX) box.maxX = point[0];
      if (point[2] < box.minZ) box.minZ = point[2];
      if (point[2] > box.maxZ) box.maxZ = point[2];
    }
  }

  const whole = boundsOf(primitive);
  const width = whole.max[0] - whole.min[0];
  const depth = whole.max[2] - whole.min[2];
  const height = whole.max[1] - whole.min[1];
  const along = width >= depth ? "x" : "z";
  const length = Math.max(width, depth);
  if (length < ROW_ASPECT * height) {
    return { clusters: null, note: "not a row: " + length.toFixed(2)
      + " m long against " + height.toFixed(2) + " m tall" };
  }

  // Sweep the components along the row. A component that starts before
  // the current cluster ends (plus the gap) joins it; otherwise it opens
  // the next one.
  const gap = length * GAP_FRACTION;
  const lo = along === "x" ? (b) => b.minX : (b) => b.minZ;
  const hi = along === "x" ? (b) => b.maxX : (b) => b.maxZ;
  const sorted = [...boxes.values()].sort((a, b) => lo(a) - lo(b));
  const clusters = [];
  let current = null, reach = -Infinity;
  for (const box of sorted) {
    if (!current || lo(box) > reach + gap) {
      current = { roots: new Set(), minX: box.minX, maxX: box.maxX,
        minZ: box.minZ, maxZ: box.maxZ };
      clusters.push(current);
    }
    current.roots.add(box.root);
    current.minX = Math.min(current.minX, box.minX);
    current.maxX = Math.max(current.maxX, box.maxX);
    current.minZ = Math.min(current.minZ, box.minZ);
    current.maxZ = Math.max(current.maxZ, box.maxZ);
    reach = Math.max(reach, hi(box));
  }
  // Assign triangles by their first vertex's component.
  const rootToCluster = new Map();
  clusters.forEach((c, i) => { for (const r of c.roots) rootToCluster.set(r, i); });
  const byCluster = clusters.map(() => []);
  for (let t = 0; t < tris.length; t += 3) {
    byCluster[rootToCluster.get(union.find(tris[t]))].push(t);
  }

  // A FRAGMENT IS NOT A VARIANT. grass_medium_01 produced an eleventh
  // "tuft" of forty triangles two centimetres across, a stray blade that
  // had drifted clear of its neighbours. Anything under a hundredth of
  // the geometry joins the nearest real cluster along the row rather
  // than becoming a species of its own.
  const total = tris.length / 3;
  const merged = [];
  for (let i = 0; i < clusters.length; i += 1) {
    const small = byCluster[i].length < total * FRAGMENT_FRACTION;
    if (small && merged.length) {
      const last = merged[merged.length - 1];
      last.tris.push(...byCluster[i]);
      last.box.minX = Math.min(last.box.minX, clusters[i].minX);
      last.box.maxX = Math.max(last.box.maxX, clusters[i].maxX);
      last.box.minZ = Math.min(last.box.minZ, clusters[i].minZ);
      last.box.maxZ = Math.max(last.box.maxZ, clusters[i].maxZ);
      continue;
    }
    if (small && i + 1 < clusters.length) {
      // The first cluster is a fragment: it joins the one that follows.
      byCluster[i + 1].push(...byCluster[i]);
      clusters[i + 1].minX = Math.min(clusters[i + 1].minX, clusters[i].minX);
      clusters[i + 1].minZ = Math.min(clusters[i + 1].minZ, clusters[i].minZ);
      continue;
    }
    merged.push({ tris: byCluster[i], box: clusters[i] });
  }
  if (merged.length < MIN_VARIANTS) {
    return { clusters: null, note: "one cluster: the components touch all "
      + "the way along, so this is a single plant" };
  }
  return { clusters: merged.map((m) => m.tris), boxes: merged.map((m) => m.box),
    along, length, note: merged.length + " variants along " + along
      + (merged.length < clusters.length
        ? " (" + (clusters.length - merged.length) + " fragments folded in)" : "") };
}

// One variant as its own document: a clone that keeps the material and
// the textures, with the mesh rebuilt from only the triangles and only
// the vertices this variant uses, recentred on its own footprint.
function variantDocument(source, primitiveIndex, triangleStarts, box) {
  const doc = cloneDocument(source);
  const root = doc.getRoot();
  const mesh = root.listMeshes()[0];
  const primitive = mesh.listPrimitives()[primitiveIndex];
  const tris = trianglesOf(primitive);

  // Remap the vertices this variant touches to a dense range.
  const remap = new Map();
  const order = [];
  for (const t of triangleStarts) {
    for (let k = 0; k < 3; k += 1) {
      const v = tris[t + k];
      if (!remap.has(v)) { remap.set(v, order.length); order.push(v); }
    }
  }
  const newIndices = new Uint32Array(triangleStarts.length * 3);
  let w = 0;
  for (const t of triangleStarts) {
    newIndices[w++] = remap.get(tris[t]);
    newIndices[w++] = remap.get(tris[t + 1]);
    newIndices[w++] = remap.get(tris[t + 2]);
  }

  const centreX = (box.minX + box.maxX) / 2;
  const centreZ = (box.minZ + box.maxZ) / 2;
  for (const semantic of primitive.listSemantics()) {
    const accessor = primitive.getAttribute(semantic);
    const size = accessor.getElementSize();
    const packed = new Float32Array(order.length * size);
    const element = new Array(size).fill(0);
    for (let i = 0; i < order.length; i += 1) {
      accessor.getElement(order[i], element);
      if (semantic === "POSITION") { element[0] -= centreX; element[2] -= centreZ; }
      for (let k = 0; k < size; k += 1) packed[i * size + k] = element[k];
    }
    const fresh = doc.createAccessor(semantic)
      .setType(accessor.getType())
      .setArray(packed)
      .setBuffer(root.listBuffers()[0]);
    primitive.setAttribute(semantic, fresh);
  }
  primitive.setIndices(doc.createAccessor("indices")
    .setType("SCALAR").setArray(newIndices).setBuffer(root.listBuffers()[0]));
  // Every other primitive of the mesh goes: a variant is one tuft.
  for (const other of mesh.listPrimitives()) {
    if (other !== primitive) other.dispose();
  }
  return doc;
}

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

async function splitOne(io, manifest, slug, write) {
  const entry = manifest.props.find((p) => p.key === slug);
  if (!entry) { console.log(`${slug}: not in the manifest`); return null; }
  const file = path.join(OUT, entry.file);
  if (!existsSync(file)) { console.log(`${slug}: no file`); return null; }

  const source = await io.read(file);
  // Everything below reasons in metres, so the quantised integers come
  // off first and go back on at the end, exactly as the fetch does.
  await source.transform(dequantize());
  const meshes = source.getRoot().listMeshes();
  if (meshes.length !== 1 || meshes[0].listPrimitives().length !== 1) {
    console.log(`${slug.padEnd(32)} skipped: ${meshes.length} meshes, `
      + `${meshes.reduce((n, m) => n + m.listPrimitives().length, 0)} primitives; `
      + "the splitter reads one fused primitive");
    return null;
  }
  const primitive = meshes[0].listPrimitives()[0];
  const found = findVariants(primitive);
  console.log(`${slug.padEnd(32)} ${found.note}`);
  if (!found.clusters) return null;
  if (!write) return found.clusters.length;

  const written = [];
  for (let i = 0; i < found.clusters.length; i += 1) {
    const doc = variantDocument(source, 0, found.clusters[i], found.boxes[i]);
    // The SCENE's bounds in world space, exactly as fetch.mjs measures.
    // dequantize turns the integers back into floats but leaves the
    // scale on the node above them, so reading POSITION directly
    // measures the quantisation cube: every variant came back with a
    // 2.0 in it, the same way every prop once did.
    const world = getBounds(doc.getRoot().listScenes()[0]);
    const b = { min: world.min, max: world.max };
    await doc.transform(
      quantize({ quantizePosition: 14, quantizeNormal: 10, quantizeTexcoord: 12 }),
      prune(), dedup());
    const key = `${slug}__v${i + 1}`;
    const packed = await io.writeBinary(doc);
    await writeFile(path.join(OUT, `${key}.glb`), packed);
    written.push({
      key, label: `${entry.label} ${i + 1}`, file: `${key}.glb`,
      group: entry.group, family: slug, variant: i + 1,
      sizeMetres: [b.max[0] - b.min[0], b.max[1] - b.min[1], b.max[2] - b.min[2]],
      triangles: triangleCount(doc), bytes: packed.byteLength,
      credit: entry.credit, licence: entry.licence, source: entry.source,
    });
    console.log(`    ${key.padEnd(36)} ${written[i].sizeMetres.map((n) => n.toFixed(2)).join(" x ")} m`
      + `  ${written[i].triangles} tris  ${(packed.byteLength / 1e6).toFixed(2)} MB`);
  }

  // The row leaves the folder the studio scans, and keeps its bytes.
  await mkdir(ROWS, { recursive: true });
  await rename(file, path.join(ROWS, entry.file));
  const thumb = file + ".thumb.png";
  if (existsSync(thumb)) await rename(thumb, path.join(ROWS, entry.file + ".thumb.png"));

  manifest.props = manifest.props.filter((p) => p.key !== slug).concat(written);
  return written.length;
}

async function main() {
  const args = process.argv.slice(2);
  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const manifestPath = path.join(OUT, "props.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));

  const all = args.includes("--all");
  const named = args.filter((a) => !a.startsWith("--"));
  const write = all || named.length > 0;
  // Candidates: every planting entry that is wide and flat, or whatever
  // was named.
  // A VARIANT IS NEVER A CANDIDATE. A flat tuft cut from a row is itself
  // wide and flat, and a second --all would have cut every tuft into its
  // blades: the dry run after the first split listed eighteen "rows",
  // all of them variants. Anything carrying a family has been split.
  const candidates = named.length ? named
    : manifest.props.filter((p) => !p.family && p.sizeMetres
        && Math.max(p.sizeMetres[0], p.sizeMetres[2]) >= ROW_ASPECT * p.sizeMetres[1]
        && (p.group === "planting" || all))
      .map((p) => p.key);

  let variants = 0, split = 0;
  for (const slug of candidates) {
    const n = await splitOne(io, manifest, slug, write);
    if (n) { variants += n; split += 1; }
  }
  if (write && split) {
    manifest.props.sort((a, b) => a.group.localeCompare(b.group) || a.key.localeCompare(b.key));
    await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
    await writeFile(path.join(OUT, "NOTICE.txt"), noticeFor(manifest));
  }
  console.log(`\n${split} rows ${write ? "split" : "found"} into ${variants} variants`
    + (write ? "" : "  (dry run: name a slug or pass --all to write)"));
}

await main();
