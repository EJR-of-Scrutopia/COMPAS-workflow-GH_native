// Ingest locally exported GLBs into the studio's prop library.
//
// fetch.mjs owns the Poly Haven pipeline; this is the same finishing line
// for models that arrive as files instead of URLs -- tonight, the Quixel
// Megascans trees exported from Unreal via the glTF exporter (the packs
// ship as Unreal assets only; the Fab Standard License permits use with
// any compatible tool, and the export is that use).
//
//     node tools/props/ingest.mjs <config.json>
//
// The config names the input folder and the provenance every entry
// carries:
//   { "dir": "path with .glb files", "group": "planting",
//     "credit": "...", "licence": "Fab Standard License", "source": "url",
//     "keyPrefix": "beech", "sizes": [{ "match": "regex", "size": "canopy" }],
//     "skip": ["regex", ...] }
//
// Differences from the fetch pipeline, both deliberate:
//   - Variant folding: SM_X and SM_X_PP are the same tree with different
//     wind rigs; the plain one wins and the _PP twin is dropped.
//   - Alpha-aware texture shrink: Unreal bakes leaf masks into PNG alpha,
//     and flattening those to JPEG would defoliate every canopy. Alpha
//     stays PNG; everything else becomes JPEG exactly as fetch.mjs does.

import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
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

// The same price lists as fetch.mjs, restated rather than imported: that
// file is a script with side effects, not a library.
const PLANTING = {
  canopy:  { triangles: 200000, bytes: 14.0e6, texture: 1024 },
  mid:     { triangles: 150000, bytes: 10.0e6, texture: 1024 },
  clutter: { triangles:  24000, bytes: 2.0e6, texture: 512 },
};
const CLASS = {
  hero:    { triangles:  90000, bytes: 3.0e6, texture: 1024 },
  mid:     { triangles:  30000, bytes: 1.2e6, texture: 512 },
  clutter: { triangles:   6000, bytes: 0.35e6, texture: 256 },
};

function triangleCount(document) {
  let total = 0;
  for (const mesh of document.getRoot().listMeshes()) {
    for (const primitive of mesh.listPrimitives()) {
      const indices = primitive.getIndices();
      const position = primitive.getAttribute("POSITION");
      const count = indices ? indices.getCount()
        : (position ? position.getCount() : 0);
      total += Math.floor(count / 3);
    }
  }
  return total;
}

function boundsOf(document) {
  const scene = document.getRoot().getDefaultScene()
    || document.getRoot().listScenes()[0];
  if (!scene) return null;
  const box = getBounds(scene);
  if (!box || !Number.isFinite(box.min[0])) return null;
  return {
    width: +(box.max[0] - box.min[0]).toFixed(3),
    height: +(box.max[1] - box.min[1]).toFixed(3),
    depth: +(box.max[2] - box.min[2]).toFixed(3),
  };
}

// Fill the RGB under transparent texels with the nearest leaf colour
// (pull-push inpainting). Unreal's bake leaves BLACK there, and mipmaps
// average those texels into every leaf: the canopy renders near-black at
// any distance, greener only at the rims -- exactly the screenshot that
// found this. Alpha is untouched; only hidden RGB changes.
async function bleedBaseColour(buffer, longest) {
  const meta = await sharp(buffer).metadata();
  let image = sharp(buffer).ensureAlpha();
  const biggest = Math.max(meta.width || 0, meta.height || 0);
  if (biggest > longest) {
    image = image.resize({ width: longest, height: longest, fit: "inside" });
  }
  const { data, info } = await image.raw()
    .toBuffer({ resolveWithObject: true });
  const { width, height } = info;
  const levels = [];
  let cw = width, ch = height;
  let cur = new Float32Array(cw * ch * 4);
  for (let i = 0, p = 0; i < data.length; i += 4, p += 4) {
    const solid = data[i + 3] > 40 ? 1 : 0;
    cur[p] = data[i] * solid;
    cur[p + 1] = data[i + 1] * solid;
    cur[p + 2] = data[i + 2] * solid;
    cur[p + 3] = solid;
  }
  levels.push({ data: cur, w: cw, h: ch });
  while (cw > 1 || ch > 1) {
    const nw = Math.max(1, cw >> 1);
    const nh = Math.max(1, ch >> 1);
    const next = new Float32Array(nw * nh * 4);
    for (let y = 0; y < nh; y++) {
      for (let x = 0; x < nw; x++) {
        let r = 0, g = 0, b = 0, weight = 0;
        for (let dy = 0; dy < 2; dy++) {
          for (let dx = 0; dx < 2; dx++) {
            const sx = Math.min(cw - 1, x * 2 + dx);
            const sy = Math.min(ch - 1, y * 2 + dy);
            const s = (sy * cw + sx) * 4;
            r += cur[s]; g += cur[s + 1]; b += cur[s + 2];
            weight += cur[s + 3];
          }
        }
        const d = (y * nw + x) * 4;
        next[d] = r; next[d + 1] = g; next[d + 2] = b; next[d + 3] = weight;
      }
    }
    levels.push({ data: next, w: nw, h: nh });
    cur = next; cw = nw; ch = nh;
  }
  for (let k = levels.length - 2; k >= 0; k--) {
    const fine = levels[k];
    const coarse = levels[k + 1];
    for (let y = 0; y < fine.h; y++) {
      for (let x = 0; x < fine.w; x++) {
        const f = (y * fine.w + x) * 4;
        if (fine.data[f + 3] > 0) continue;
        const c = (Math.min(coarse.h - 1, y >> 1) * coarse.w
          + Math.min(coarse.w - 1, x >> 1)) * 4;
        const weight = coarse.data[c + 3] || 1;
        fine.data[f] = coarse.data[c] / weight;
        fine.data[f + 1] = coarse.data[c + 1] / weight;
        fine.data[f + 2] = coarse.data[c + 2] / weight;
        fine.data[f + 3] = 1;
      }
    }
  }
  const filled = Buffer.from(data);
  const base = levels[0].data;
  for (let i = 0, p = 0; i < filled.length; i += 4, p += 4) {
    if (data[i + 3] > 40) continue;
    filled[i] = Math.max(0, Math.min(255, Math.round(base[p])));
    filled[i + 1] = Math.max(0, Math.min(255, Math.round(base[p + 1])));
    filled[i + 2] = Math.max(0, Math.min(255, Math.round(base[p + 2])));
  }
  return sharp(filled, { raw: { width, height, channels: 4 } })
    .png({ palette: true, colors: 256, dither: 0.5,
      compressionLevel: 9, effort: 7 }).toBuffer();
}

async function shrinkTextures(document, longest) {
  // Which textures are pictures (base colour) and which are data: a leaf
  // mask lives in a base colour's alpha and palette-quantising it is
  // invisible, where the same 256 colours would band a normal map into
  // corduroy. Data maps go JPEG whatever channels they arrived with.
  const baseColour = new Set();
  for (const material of document.getRoot().listMaterials()) {
    const texture = material.getBaseColorTexture();
    if (texture) baseColour.add(texture);
  }
  for (const texture of document.getRoot().listTextures()) {
    const image = texture.getImage();
    if (!image) continue;
    const buffer = Buffer.from(image);
    const meta = await sharp(buffer).metadata();
    const biggest = Math.max(meta.width || 0, meta.height || 0);
    if (!biggest) continue;
    // Unlike the fetch pipeline, size alone is not the gate: an Unreal
    // bake at 1024 is ALREADY within budget yet arrives as raw RGBA PNG,
    // megabytes a map. Anything not yet a JPEG is re-encoded even at its
    // present size; only a small JPEG passes untouched.
    if (biggest <= longest && meta.format === "jpeg") continue;
    const base = biggest > longest
      ? sharp(buffer).resize({ width: longest, height: longest, fit: "inside" })
      : sharp(buffer);
    let carriesAlpha = false;
    if ((meta.channels || 3) >= 4 && baseColour.has(texture)) {
      const stats = await sharp(buffer).stats();
      const alpha = stats.channels[3];
      carriesAlpha = !!alpha && alpha.min < 250;
    }
    if (carriesAlpha) {
      // Bleed first (mipmaps must never taste the black under the
      // holes), then the palette: 256 dithered colours read identically
      // on foliage at a quarter of the bytes.
      texture.setImage(new Uint8Array(await bleedBaseColour(buffer, longest)));
      texture.setMimeType("image/png");
    } else {
      texture.setImage(new Uint8Array(
        await base.flatten({ background: "#000" })
          .jpeg({ quality: 86, mozjpeg: true }).toBuffer()));
      texture.setMimeType("image/jpeg");
    }
  }
}

function labelFrom(name) {
  return name
    .replace(/^SM_/, "")
    .replace(/_PP$/, "")
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim();
}

function keyFrom(name, prefix) {
  const bare = name.replace(/^SM_/, "").replace(/_PP$/, "")
    .replace(/([a-z])([A-Z])/g, "$1_$2").toLowerCase();
  return (prefix && !bare.startsWith(prefix) ? prefix + "_" : "") + bare;
}

async function buildOne(io, file, config) {
  const name = path.basename(file, ".glb");
  let size = "mid";
  for (const rule of config.sizes || []) {
    if (new RegExp(rule.match, "i").test(name)) { size = rule.size; break; }
  }
  const group = ((config.renames || {})[name] || {}).group || config.group;
  const budget = (group === "planting" ? PLANTING : CLASS)[size];

  const document = await io.read(file);
  const before = triangleCount(document);
  // Unreal bake hygiene, both measured on the beech forest canopies:
  // - The IMPOSTOR billboard (the far-distance card the pack carries)
  //   arrives textureless with a magenta fallback and drew itself as a
  //   black mass over the real canopy. The real leaves are all there;
  //   the impostor goes.
  // - Baked materials ship metallicFactor 1 with no metallic texture,
  //   which dims every leaf under image lighting. A tree is not chrome.
  for (const material of document.getRoot().listMaterials()) {
    if (/impostor/i.test(material.getName() || "")) {
      for (const mesh of document.getRoot().listMeshes()) {
        for (const primitive of mesh.listPrimitives()) {
          if (primitive.getMaterial() === material) primitive.dispose();
        }
      }
      material.dispose();
      continue;
    }
    if (!material.getMetallicRoughnessTexture()
        && material.getMetallicFactor() === 1) {
      material.setMetallicFactor(0);
    }
  }
  // A Megaplant tree arrives SKINNED (Unreal assembles its branches on a
  // skeleton for wind). The bind pose is the tree; dropping the skin
  // keeps that shape and lets prune sweep the joints, weights and
  // inverse bind matrices away.
  for (const node of document.getRoot().listNodes()) {
    if (node.getSkin()) node.setSkin(null);
  }
  for (const skin of document.getRoot().listSkins()) skin.dispose();
  for (const mesh of document.getRoot().listMeshes()) {
    for (const primitive of mesh.listPrimitives()) {
      for (const name of primitive.listSemantics()) {
        if (name.startsWith("JOINTS_") || name.startsWith("WEIGHTS_")) {
          primitive.setAttribute(name, null);
        }
      }
    }
  }
  await document.transform(
    dedup(), flatten(), join(), weld(), resample(),
    prune({ keepAttributes: false, keepLeaves: false }),
  );
  const now = triangleCount(document);
  if (now > budget.triangles) {
    // An assertion out of meshopt on an Unreal-baked mesh abandons the
    // simplification, not the tree: over-budget is a report, an absent
    // prop is a hole.
    try {
      await document.transform(simplify({
        simplifier: MeshoptSimplifier,
        ratio: Math.max(0.02, budget.triangles / now),
        error: 0.004, lockBorder: true,
      }));
      let after = triangleCount(document);
      if (after > budget.triangles * 1.15) {
        await document.transform(simplify({
          simplifier: MeshoptSimplifier,
          ratio: Math.max(0.02, budget.triangles / after),
          error: 0.02, lockBorder: false,
        }));
        after = triangleCount(document);
      }
      if (after > budget.triangles * 1.15) {
        await document.transform(simplify({
          simplifier: MeshoptSimplifier,
          ratio: Math.max(0.02, budget.triangles / after),
          error: 0.08, lockBorder: false,
        }));
      }
    } catch (error) {
      process.stdout.write(`(simplify refused: ${error.message}) `);
    }
  }
  const bounds = boundsOf(document);
  await shrinkTextures(document, budget.texture);
  await document.transform(
    quantize({ quantizePosition: 14, quantizeNormal: 10,
      quantizeTexcoord: 12 }),
    prune(), dedup(),
  );
  const packed = await io.writeBinary(document);
  // Megascans exports carry scan codes for names (uldubik_tier_0); the
  // config's rename table restores the words a person would search for.
  const renamed = (config.renames || {})[name];
  const key = renamed ? renamed.key : keyFrom(name, config.keyPrefix);
  await writeFile(path.join(OUT, `${key}.glb`), packed);
  return {
    key,
    label: renamed ? renamed.label
      : config.labelPrefix
        ? `${config.labelPrefix} ${labelFrom(name)}`.replace(/\s+/g, " ").trim()
        : labelFrom(name),
    file: `${key}.glb`,
    group,
    sizeMetres: bounds ? [bounds.width, bounds.height, bounds.depth] : null,
    triangles: triangleCount(document),
    bytes: packed.byteLength,
    credit: config.credit,
    licence: config.licence,
    source: config.source,
    before,
    budget,
  };
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) {
    console.log("usage: node tools/props/ingest.mjs <config.json>");
    return;
  }
  const config = JSON.parse(await readFile(configPath, "utf8"));
  const files = (await readdir(config.dir))
    .filter((f) => f.toLowerCase().endsWith(".glb"));
  const bases = new Set(files.map((f) => path.basename(f, ".glb")));
  const chosen = files.filter((f) => {
    const name = path.basename(f, ".glb");
    if ((config.skip || []).some((s) => new RegExp(s, "i").test(name))) {
      return false;
    }
    // Variant folding: the plain wind variant wins over its _PP twin.
    if (/_PP$/.test(name) && bases.has(name.replace(/_PP$/, ""))) return false;
    return true;
  });
  if (!chosen.length) { console.log("nothing to ingest"); return; }

  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const built = [];
  const failed = [];
  for (const file of chosen) {
    process.stdout.write(path.basename(file, ".glb").padEnd(36));
    try {
      const result = await buildOne(io, path.join(config.dir, file), config);
      built.push(result);
      const over = result.triangles > result.budget.triangles
        || result.bytes > result.budget.bytes;
      console.log(`${String(result.before).padStart(9)} tri`
        + ` -> ${String(result.triangles).padStart(7)}`
        + `  -> ${(result.bytes / 1e6).toFixed(2).padStart(6)} MB`
        + (over ? "   OVER BUDGET" : ""));
    } catch (error) {
      failed.push({ file, why: error.message });
      console.log(`FAILED: ${error.message}`);
    }
  }

  const manifestPath = path.join(OUT, "props.json");
  let existing = { props: [] };
  if (existsSync(manifestPath)) {
    try {
      existing = JSON.parse(await readFile(manifestPath, "utf8"));
    } catch { /* a damaged manifest is replaced, not repaired */ }
  }
  const byKey = new Map((existing.props || []).map((p) => [p.key, p]));
  for (const prop of built) {
    const { before, budget, ...keep } = prop;
    byKey.set(keep.key, keep);
  }
  const props = [...byKey.values()].sort(
    (a, b) => a.group.localeCompare(b.group) || a.key.localeCompare(b.key));
  await writeFile(manifestPath, JSON.stringify({
    library: existing.library
      || "Poly Haven (CC0) and Quixel Megascans via Fab (Fab Standard License).",
    props,
  }, null, 2) + "\n");

  // THE CREDITS COME FROM THE MANIFEST, exactly as they do in fetch.mjs,
  // and for the same reason: a header written by hand is a licence claim
  // that nobody re-checks when the folder grows. This one said "two
  // libraries" over a folder that had held three since the decals
  // arrived, so an ingest run would have quietly deleted ambientCG's
  // line from a file whose whole job is to name who made what.
  const libraries = new Map();
  for (const prop of props) {
    const source = prop.source || "";
    const where = /polyhaven/.test(source) ? "Poly Haven"
      : /ambientcg/i.test(source) ? "ambientCG"
        : /fab\.com/.test(source) ? "Quixel Megascans, via Fab"
          : "other";
    const line = `${where} -- ${prop.licence || "licence unstated"}`;
    libraries.set(line, (libraries.get(line) || 0) + 1);
  }
  const notice = [
    "Models in this folder come from more than one library. Each is",
    "credited below; the licences they arrived under are:",
    ...[...libraries.entries()].sort()
      .map(([line, count]) => `  ${line}  (${count})`),
    "",
    "Poly Haven and ambientCG ask for no credit and this file is offered",
    "anyway. The Fab Standard License needs a free Epic account and",
    "permits use with any compatible tool, which the glTF export is.",
    "",
    ...props.map((p) => `${p.key}\n  ${p.label}\n  ${p.source}`),
  ].join("\n");
  await writeFile(path.join(OUT, "NOTICE.txt"), notice + "\n");

  console.log(`\n${built.length} ingested, ${failed.length} failed, into ${OUT}`);
  for (const f of failed) console.log(`  ${f.file}: ${f.why}`);
}

await main();
