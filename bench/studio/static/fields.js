// Pure geometry and field helpers for the studio scene. No three.js and no
// DOM: everything is plain arrays so tests/studio/test_fields.py can run
// this module in node against hand-computed values.
//
// This module used to also carry vertexNormals, segmentBoundaryEdges and
// extrudeSegment, a JS mirror of the offset maths in bench/studio/pieces.py
// and bench/studio/blocks.py. The viewer no longer extrudes anything
// itself: pieces.py ships mid-surface points and normals per piece in the
// bundle, and studio.js's buildPieceMeshes just offsets those by half the
// thickness. Python is now the only implementation of that maths, which is
// the point: one fewer mirror to keep in step.

export function segmentUVOffset(key) {
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash ^ key.charCodeAt(i)) * 16777619) >>> 0;
  }
  return [(hash % 97) / 9.7, ((hash >>> 8) % 97) / 9.7];
}

// A quarter-turn per piece, from the same FNV hash family as the offset:
// deterministic for a given key, so the same study always looks the same,
// and re-seeded wholesale by the Randomise button (the key carries the
// seed). Four turns are enough to break the alignment the eye finds when
// every voussoir wears the crop the same way up.
export function uvQuarterTurn(key) {
  return Math.floor(segmentUVOffset(key)[1] * 9.7) % 4;
}

// The window a piece samples from the sheet (see sheetUVs): two fractions
// in [0, 1] of the FREE margin, from the same FNV hash family as the
// offset, so the same study always deals the same windows and the
// Randomise button re-deals them wholesale through the key's seed.
export function segmentWindow(key) {
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash ^ key.charCodeAt(i)) * 16777619) >>> 0;
  }
  return [(hash % 97) / 96, ((hash >>> 8) % 97) / 96];
}

// The piece's best-fit plane frame, then an in-plane [e1, e2] pair for
// u and v. Two flavours:
//
//   grain=false  e1 is world X projected into the plane (world Y when the
//                plane is nearly vertical-X): the stable default.
//   grain=true   e2 is world +Z projected into the plane -- the uphill
//                direction -- so v runs up the slope of the voussoir and a
//                picture whose grain is vertical flows up each leg of the
//                vault (Param: "use the direction of the voussoir... so
//                that each leg has the right direction"). A face lying
//                flat has no uphill and keeps the stable default.
//
// The plane itself comes from the ORIENTATION TENSOR -- the area-weighted
// sum of nn^T over every triangle -- never from a Newell sum: a voussoir
// is a CLOSED solid (top face, bottom face, joint walls), and over any
// closed surface the signed face-area vectors cancel to zero, so Newell
// handed every piece floating-point noise -- and handed a symmetric piece
// an exact zero, whose degenerate e2 collapsed v to a constant and
// smeared the picture into streaks. The tensor is sign-blind: the top and
// bottom faces ADD, and its dominant eigenvector is the direction most of
// the surface faces, which is the projection plane that foreshortens
// least -- on a flat slab it is exact, and on a wrapping band it is the
// best single plane there is.
function pieceFrame(positions, grain) {
  let qxx = 0, qxy = 0, qxz = 0, qyy = 0, qyz = 0, qzz = 0;
  for (let i = 0; i < positions.length; i += 9) {
    const ux = positions[i + 3] - positions[i];
    const uy = positions[i + 4] - positions[i + 1];
    const uz = positions[i + 5] - positions[i + 2];
    const vx = positions[i + 6] - positions[i];
    const vy = positions[i + 7] - positions[i + 1];
    const vz = positions[i + 8] - positions[i + 2];
    const wx = uy * vz - uz * vy;
    const wy = uz * vx - ux * vz;
    const wz = ux * vy - uy * vx;
    const twice = Math.hypot(wx, wy, wz);
    if (twice < 1e-12) continue;
    // area * n n^T, with w = 2 * area * n, is w w^T / (2 |w|).
    const weight = 1 / (2 * twice);
    qxx += wx * wx * weight; qxy += wx * wy * weight; qxz += wx * wz * weight;
    qyy += wy * wy * weight; qyz += wy * wz * weight; qzz += wz * wz * weight;
  }
  const q = [qxx, qxy, qxz, qyy, qyz, qzz];
  const apply = (v) => [
    q[0] * v[0] + q[1] * v[1] + q[2] * v[2],
    q[1] * v[0] + q[3] * v[1] + q[4] * v[2],
    q[2] * v[0] + q[4] * v[1] + q[5] * v[2]];
  // Power iteration for the dominant eigenvector, seeded on the axis the
  // tensor already leans to, so it cannot start orthogonal to the answer
  // on an axis-aligned piece.
  let v = qxx >= qyy && qxx >= qzz ? [1, 0, 0]
    : (qyy >= qzz ? [0, 1, 0] : [0, 0, 1]);
  for (let k = 0; k < 48; k++) {
    const w = apply(v);
    const len = Math.hypot(w[0], w[1], w[2]);
    if (len < 1e-12) break;
    v = [w[0] / len, w[1] / len, w[2] / len];
  }
  const nx = v[0], ny = v[1], nz = v[2];
  if (grain) {
    const ux = -nz * nx, uy = -nz * ny, uz = 1 - nz * nz;
    const ulen = Math.hypot(ux, uy, uz);
    if (ulen > 1e-6) {
      const e2x = ux / ulen, e2y = uy / ulen, e2z = uz / ulen;
      // e1 = e2 x n keeps the frame right-handed with n.
      return [e2y * nz - e2z * ny, e2z * nx - e2x * nz, e2x * ny - e2y * nx,
              e2x, e2y, e2z];
    }
  }
  let e1x = 1 - nx * nx, e1y = -nx * ny, e1z = -nx * nz;
  let e1len = Math.hypot(e1x, e1y, e1z);
  if (e1len < 1e-6) {
    e1x = -ny * nx; e1y = 1 - ny * ny; e1z = -ny * nz;
    e1len = Math.hypot(e1x, e1y, e1z) || 1;
  }
  e1x /= e1len; e1y /= e1len; e1z /= e1len;
  return [e1x, e1y, e1z,
          ny * e1z - nz * e1y, nz * e1x - nx * e1z, nx * e1y - ny * e1x];
}

function projectedBounds(positions, frame) {
  const [e1x, e1y, e1z, e2x, e2y, e2z] = frame;
  let minU = Infinity, maxU = -Infinity, minV = Infinity, maxV = -Infinity;
  const flat = new Array((positions.length / 3) * 2);
  for (let i = 0, j = 0; i < positions.length; i += 3, j += 2) {
    const u = positions[i] * e1x + positions[i + 1] * e1y + positions[i + 2] * e1z;
    const v = positions[i] * e2x + positions[i + 1] * e2y + positions[i + 2] * e2z;
    flat[j] = u; flat[j + 1] = v;
    if (u < minU) minU = u;
    if (u > maxU) maxU = u;
    if (v < minV) minV = v;
    if (v > maxV) maxV = v;
  }
  return { flat, minU, minV, spanU: maxU - minU, spanV: maxV - minV };
}

// A flat piece projects onto its plane at true size, but a CURVED one
// foreshortens: the projected footprint is smaller than the surface, so
// dividing by the sheet alone would magnify its picture against its flat
// neighbours -- the very "different scale between objects" Param saw. The
// gain is how much surface each projected metre really carries,
// sqrt(true area / projected area), measured over the faces the eye sees:
// a triangle standing nearly edge-on to the plane (a joint wall) holds
// real area but projects to nothing, and it is hidden inside the joint,
// so it must not pollute the average.
function projectionGain(positions, frame) {
  const [e1x, e1y, e1z, e2x, e2y, e2z] = frame;
  let surface = 0, projected = 0;
  for (let i = 0; i < positions.length; i += 9) {
    const ux = positions[i + 3] - positions[i];
    const uy = positions[i + 4] - positions[i + 1];
    const uz = positions[i + 5] - positions[i + 2];
    const vx = positions[i + 6] - positions[i];
    const vy = positions[i + 7] - positions[i + 1];
    const vz = positions[i + 8] - positions[i + 2];
    const wx = uy * vz - uz * vy;
    const wy = uz * vx - ux * vz;
    const wz = ux * vy - uy * vx;
    const area = 0.5 * Math.hypot(wx, wy, wz);
    const u1 = ux * e1x + uy * e1y + uz * e1z;
    const v1 = ux * e2x + uy * e2y + uz * e2z;
    const u2 = vx * e1x + vy * e1y + vz * e1z;
    const v2 = vx * e2x + vy * e2y + vz * e2z;
    const flat = 0.5 * Math.abs(u1 * v2 - u2 * v1);
    if (flat > 0.3 * area) {
      surface += area;
      projected += flat;
    }
  }
  if (surface < 1e-12 || projected < 1e-12) return 1;
  return Math.sqrt(surface / projected);
}

// How much sheet one piece needs: its footprint's larger in-plane span
// times its projection gain, in metres, measured in the same frame
// sheetUVs will project with. The caller takes the max over every piece
// to size the sheet.
//
// frameSource: the triangles the frame and gain are measured over, when
// they should not be the whole soup. A vault piece is 200 mm thick with
// a small face, so over the WHOLE solid the joint walls out-weigh the
// faces and the tensor tips edge-on (measured live: median piece 3x
// compressed, worst 73x). The caller passes the TOP SURFACE alone -- it
// knows which triangles those are -- and the walls merely project along.
export function footprintSpan(positions, grain = false, frameSource = null) {
  const source = frameSource && frameSource.length ? frameSource : positions;
  const frame = pieceFrame(source, grain);
  const bounds = projectedBounds(positions, frame);
  return Math.max(bounds.spanU, bounds.spanV) * projectionGain(source, frame);
}

// ONE sheet of material for the whole vault, cut into voussoirs. The crop
// is mapped at one UNIFORM scale -- the same in u and v, and the same on
// every piece (Param: "we should keep it always uniform... the texture
// scale on the skin always needs to be the same between objects") -- with
// the sheet sized by the largest voussoir footprint, so no face ever
// repeats. Each piece samples its own window of the sheet, placed by
// windowU/windowV as fractions of the free margin: voussoirs sawn from
// one slab, no two from quite the same patch.
//
// The whole piece -- top face, bottom face and its thin joint walls -- is
// projected onto the piece's own best-fit plane; the joint walls inherit
// the rim of the window, which keeps edges continuous and is invisible
// inside a closed joint. rotation is 0..3 quarter turns within the unit
// square, so the window never leaves the sheet.
export function sheetUVs(positions, sheet, options = {}) {
  const { grain = false, windowU = 0, windowV = 0, rotation = 0,
    frameSource = null } = options;
  const source = frameSource && frameSource.length ? frameSource : positions;
  const frame = pieceFrame(source, grain);
  const bounds = projectedBounds(positions, frame);
  // The gain stretches the projection back to true surface size, so a
  // curved piece wears its picture at the same density as a flat one.
  const gain = projectionGain(source, frame);
  // A sheet smaller than the piece would spill past the picture's edge;
  // never let it (the caller's max-over-pieces makes this a no-op).
  const metres = Math.max(sheet, bounds.spanU * gain, bounds.spanV * gain) || 1;
  const fitU = bounds.spanU * gain / metres;
  const fitV = bounds.spanV * gain / metres;
  const baseU = windowU * (1 - fitU);
  const baseV = windowV * (1 - fitV);
  const flat = bounds.flat;
  const uvs = new Array(flat.length);
  for (let j = 0; j < flat.length; j += 2) {
    let u = baseU + (flat[j] - bounds.minU) * gain / metres;
    let v = baseV + (flat[j + 1] - bounds.minV) * gain / metres;
    for (let turn = 0; turn < (rotation & 3); turn++) {
      const kept = u;
      u = v;
      v = 1 - kept;
    }
    uvs[j] = u;
    uvs[j + 1] = v;
  }
  return uvs;
}

// Box projection: each triangle is laid flat against whichever of the three
// planes its own normal leans on most, and the two remaining world axes
// become u and v. That is what makes a texture sit on a doubly curved shell
// without a seam anybody can find.
//
// scaleU and scaleV are UV UNITS PER METRE, which is to say the reciprocal
// of how many metres one repeat of the picture covers. They used to be a
// single hard-coded 0.15 -- one repeat per 6.67 m, a number chosen by eye
// for a procedural noise that had no real size. A library material does
// have one: a brick photographed at 230 by 61 millimetres wants 1/0.230 and
// 1/0.061, and passing anything else lays bricks the size of doors.
//
// The default keeps every existing caller and every existing test on the
// number they were written against.
export function boxUVs(positions, centroid, offset, scaleU = 0.15, scaleV = scaleU) {
  const uvs = [];
  for (let i = 0; i < positions.length; i += 9) {
    const u = [
      positions[i + 3] - positions[i],
      positions[i + 4] - positions[i + 1],
      positions[i + 5] - positions[i + 2],
    ];
    const v = [
      positions[i + 6] - positions[i],
      positions[i + 7] - positions[i + 1],
      positions[i + 8] - positions[i + 2],
    ];
    const n = [
      Math.abs(u[1] * v[2] - u[2] * v[1]),
      Math.abs(u[2] * v[0] - u[0] * v[2]),
      Math.abs(u[0] * v[1] - u[1] * v[0]),
    ];
    const axis = n[2] >= n[0] && n[2] >= n[1] ? 2 : (n[1] >= n[0] ? 1 : 0);
    const uAxis = axis === 0 ? 1 : 0;
    const vAxis = axis === 2 ? 1 : 2;
    for (let corner = 0; corner < 3; corner++) {
      const point = [
        positions[i + 3 * corner],
        positions[i + 3 * corner + 1],
        positions[i + 3 * corner + 2],
      ];
      uvs.push(
        (point[uAxis] - centroid[uAxis]) * scaleU + offset[0],
        (point[vAxis] - centroid[vAxis]) * scaleV + offset[1],
      );
    }
  }
  return uvs;
}

export function stressValueOf(pair, surface) {
  if (surface === "top" || surface === "bottom") {
    const p = pair[surface];
    return Math.abs(p[1]) > p[0] ? p[1] : p[0];
  }
  const worstTension = Math.max(pair.top[0], pair.bottom[0]);
  const worstCompression = Math.min(pair.top[1], pair.bottom[1]);
  return Math.abs(worstCompression) > worstTension ? worstCompression : worstTension;
}

export function smoothStressField(faces, vertexCount, stresses, surface) {
  const sum = new Array(vertexCount).fill(0);
  const count = new Array(vertexCount).fill(0);
  faces.forEach((face, faceIndex) => {
    const pair = stresses[String(faceIndex)];
    if (!pair) return;
    const value = stressValueOf(pair, surface);
    for (const vertex of face) {
      sum[vertex] += value;
      count[vertex] += 1;
    }
  });
  return sum.map((total, i) => (count[i] ? total / count[i] : null));
}

export function interpolateScalarField(field, vertexSources) {
  return vertexSources.map((sources) => {
    let total = 0, found = 0;
    for (const source of sources) {
      const value = field[source];
      if (value !== null && value !== undefined) {
        total += value;
        found += 1;
      }
    }
    return found ? total / found : null;
  });
}

// A cut piece vertex is not a mesh vertex, so every solved field is read
// through the barycentric weights the cut recorded for it. A vertex that
// happens to land on a mesh vertex has a single weight of one, which is
// exactly the lookup this replaces.
//
// Empty weights cannot happen today (the lift that produces them always
// returns three), but zero is the wrong answer for "no information": it is
// exactly the shape of a silently shifted heatmap value or a vertex dragged
// to the origin, so both functions treat it the same as a null entry.
//
// A single missing corner used to forfeit the whole sample: one hole in
// coverage turned the render vertex null even though its other corners had
// real data. Both functions instead sum only the corners that DO have data
// and renormalise over their weight, so a vertex with partial coverage
// reads as that partial data (weight-corrected) rather than nothing. Only
// when every weighted corner is missing does the sample fall back, because
// then there is truly nothing to renormalise over.
export function sampleScalar(field, weights) {
  if (!weights.length) return null;
  let total = 0, foundWeight = 0;
  for (const [index, weight] of weights) {
    const value = field[index];
    if (value === null || value === undefined) continue;
    total += value * weight;
    foundWeight += weight;
  }
  return foundWeight > 0 ? total / foundWeight : null;
}

export function sampleVector(field, weights, fallback) {
  if (!weights.length) return fallback;
  const out = [0, 0, 0];
  let foundWeight = 0;
  for (const [index, weight] of weights) {
    const value = field[index];
    if (!value) continue;
    out[0] += value[0] * weight;
    out[1] += value[1] * weight;
    out[2] += value[2] * weight;
    foundWeight += weight;
  }
  if (foundWeight <= 0) return fallback;
  return [out[0] / foundWeight, out[1] / foundWeight, out[2] / foundWeight];
}

// Crease-angle vertex normals for an unindexed triangle soup, 9 floats
// per triangle. The piece builder guarantees that shared points are
// bit-identical across facets (the cut welds them), so grouping corners
// by exact position key is safe. Each corner's normal averages the facet
// normals at its position whose angle to the corner's own facet normal
// is inside the crease threshold: gently curved caps smooth, the roughly
// 90 degree cap-to-side edges stay hard, so silhouettes keep corners.
export function creaseNormals(positions, creaseDegrees = 40) {
  const cosCrease = Math.cos((creaseDegrees * Math.PI) / 180);
  const facetCount = positions.length / 9;
  const facetNormals = new Array(facetCount);
  const byPosition = new Map();
  for (let f = 0; f < facetCount; f++) {
    const i = 9 * f;
    const ux = positions[i + 3] - positions[i];
    const uy = positions[i + 4] - positions[i + 1];
    const uz = positions[i + 5] - positions[i + 2];
    const vx = positions[i + 6] - positions[i];
    const vy = positions[i + 7] - positions[i + 1];
    const vz = positions[i + 8] - positions[i + 2];
    const nx = uy * vz - uz * vy;
    const ny = uz * vx - ux * vz;
    const nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz);
    if (length < 1e-12) {
      // A zero-area facet has no direction to contribute; it is left out
      // of the position index entirely so it cannot poison a neighbour.
      facetNormals[f] = null;
      continue;
    }
    facetNormals[f] = [nx / length, ny / length, nz / length];
    for (let corner = 0; corner < 3; corner++) {
      const key = positions[i + 3 * corner] + ","
        + positions[i + 3 * corner + 1] + ","
        + positions[i + 3 * corner + 2];
      let list = byPosition.get(key);
      if (!list) { list = []; byPosition.set(key, list); }
      list.push(f);
    }
  }
  const normals = new Float32Array(positions.length);
  for (let f = 0; f < facetCount; f++) {
    const own = facetNormals[f];
    for (let corner = 0; corner < 3; corner++) {
      const at = 9 * f + 3 * corner;
      if (!own) {
        // A corner of a degenerate facet spans no area, so any unit
        // vector is as honest; +z never produces a NaN downstream.
        normals[at + 2] = 1;
        continue;
      }
      const key = positions[at] + "," + positions[at + 1] + ","
        + positions[at + 2];
      let x = 0, y = 0, z = 0;
      for (const other of byPosition.get(key)) {
        const n = facetNormals[other];
        if (n[0] * own[0] + n[1] * own[1] + n[2] * own[2] < cosCrease) continue;
        x += n[0]; y += n[1]; z += n[2];
      }
      const length = Math.hypot(x, y, z);
      if (length < 1e-12) {
        // Unreachable while the facet's own normal is in its own list
        // (dot 1 with itself), kept so a cancelling sum can never emit
        // a zero normal.
        normals[at] = own[0]; normals[at + 1] = own[1]; normals[at + 2] = own[2];
      } else {
        normals[at] = x / length;
        normals[at + 1] = y / length;
        normals[at + 2] = z / length;
      }
    }
  }
  return normals;
}

// E3: find the sun in an equirectangular HDR so shadows agree with the
// picture by default. Pure array maths: pixel data in, angles and an
// intensity out, no three.js, no DOM, so node can pin it. Convention:
// u spans azimuth 0..360, v spans elevation with row 0 at the zenith
// (RGBELoader keeps Radiance file order, whose scanlines run top first).
export function estimateSunFromEquirect(data, width, height, stride = 4) {
  const step = Math.max(1, Math.floor(width / 256));
  let total = 0;
  let count = 0;
  let best = -1;
  let bestX = 0;
  let bestY = 0;
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * stride;
      const lum = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      total += lum;
      count += 1;
      if (lum > best) { best = lum; bestX = x; bestY = y; }
    }
  }
  const mean = total / Math.max(1, count);
  const peak = mean > 0 ? best / mean : 1;
  // A clear sky peaks thousands of times over its mean; an overcast map
  // barely rises above it. Log-map that ratio into a usable lamp range
  // with a soft floor so a sunless map still grounds the vault.
  const intensity = Math.min(4, Math.max(0.6, 0.6 + 0.35 * Math.log2(Math.max(1, peak))));
  return {
    azimuthDeg: (bestX / width) * 360,
    elevationDeg: 90 - (bestY / height) * 180,
    intensity,
  };
}

// The colour of a photograph's horizon: the mean of the band of sky just
// above it, all the way round. The atmosphere's fog fades toward this in
// HDRI mode, so a fogged floor dissolves into the photograph's own air
// rather than into a grey somebody picked.
//
// exposure, when given, puts each pixel through the same Reinhard map the
// server bakes the backdrop with (hdri_preview._tone: v * e / (1 + v * e)),
// so the answer is the linear colour the eye is actually shown; that also
// keeps a sun in the band from outvoting the sky around it. Without it the
// raw radiance is averaged. null when the band holds no pixel.
export function equirectHorizonColour(data, width, height, stride = 4, options = {}) {
  const fromDeg = options.fromDeg ?? 0;
  const toDeg = options.toDeg ?? 8;
  const exposure = options.exposure ?? null;
  const step = Math.max(1, Math.floor(width / 512));
  const sum = [0, 0, 0];
  let count = 0;
  for (let y = 0; y < height; y++) {
    // Row y covers elevation 90 - 180 (y + 0.5) / height at its centre.
    const elevation = 90 - ((y + 0.5) / height) * 180;
    if (elevation < fromDeg || elevation > toDeg) continue;
    for (let x = 0; x < width; x += step) {
      const i = (y * width + x) * stride;
      for (let c = 0; c < 3; c++) {
        const value = Math.max(0, data[i + c]);
        sum[c] += exposure === null ? value : (value * exposure) / (1 + value * exposure);
      }
      count += 1;
    }
  }
  if (!count) return null;
  return sum.map((total) => total / count);
}

// The formwork build playback's whole algorithm. The frames come from the
// exporter's bench.frames/1 document (FRAMES-WRITER-SPEC-2026-09-03.md):
// the writer samples the engine's own motion, so the reader NEVER
// reconstructs it, it lerps between the samples it was given, clamped at
// both ends. The spec's section 9 is explicit that easing belongs on the
// playback clock, never here: positions between samples are linear.
// frames must be non-empty with strictly ascending times, which the
// server-side validator (bench/studio/frames.py) has already enforced
// before any document reaches this function.
export function interpolateFormworkFrame(frames, time) {
  const lerpTriples = (a, b, u) => a.map((p, i) => [
    p[0] + (b[i][0] - p[0]) * u,
    p[1] + (b[i][1] - p[1]) * u,
    p[2] + (b[i][2] - p[2]) * u,
  ]);
  const first = frames[0];
  const last = frames[frames.length - 1];
  if (time <= first.time) {
    return { vertices: first.vertices, columnNodes: first.columnNodes, phase: first.phase };
  }
  if (time >= last.time) {
    return { vertices: last.vertices, columnNodes: last.columnNodes, phase: last.phase };
  }
  let lo = 0;
  let hi = frames.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (frames[mid].time <= time) lo = mid; else hi = mid;
  }
  const a = frames[lo];
  const b = frames[hi];
  if (a.time === time) {
    return { vertices: a.vertices, columnNodes: a.columnNodes, phase: a.phase };
  }
  const u = (time - a.time) / (b.time - a.time);
  return {
    vertices: lerpTriples(a.vertices, b.vertices, u),
    columnNodes: lerpTriples(a.columnNodes, b.columnNodes, u),
    phase: a.phase,
  };
}

// The machine's own clock, 0 to 100, read off the timeline clock. The
// writer stamps frames on a 0-100 scale that is deliberately not seconds
// (FRAMES-WRITER-SPEC section 1): the writer owns the motion, the reader
// owns how fast it plays. Clamped at both ends, so a timeline scrubbed
// past the act holds the finished pose rather than running off the frames.
export function machineTime(t, seconds) {
  if (!(seconds > 0)) return 100;
  return Math.min(100, Math.max(0, (t / seconds) * 100));
}

// What is on screen during and after the raise. Pure, and kept away from
// three.js, because it carries two rules that are easy to break by
// accident while editing scene code:
//
//   1. The columns are part of the machine. They are raised with the net,
//      they stand through the build while the vault is cast on it, and
//      they go with the formwork on the strike -- the whole machine
//      leaves together and the vault is left standing on its own.
//   2. Exactly one drawing of the columns is ever on screen. The animated
//      members and the exported solids are the same tubes at the same
//      radius, so drawn together they z-fight; the members carry the
//      timeline, the solids carry every other mode.
//
// The net is the third actor: it follows the frames until the act ends and
// then yields to the finished instanced wires, whose pose at that instant
// is identical by the writer's time-100 guarantee.
// THE TAKE ENDS WHERE IT BEGAN (Param, 2026-09-15): "the rotations around
// should always end on the position which the animation started. It must
// only max out at 1 full rotation after the formwork is removed and
// therefore will stop at some point on that last rotation when it meets
// that point."
//
// spin is the orbit in radians per second; turning is how many seconds the
// camera has already turned for when the formwork has gone. The answer is
// the last turn, in radians: whatever brings the whole sweep to a whole
// number of revolutions, more than nothing and never more than one. A
// strike that ends exactly on the start bearing takes the full revolution,
// so the vault is still seen once on its own. A still camera has nothing
// to finish.
export function finalOrbitTurn(spin, turning) {
  if (!(spin > 0) || !(turning >= 0)) return 0;
  const revolution = 2 * Math.PI;
  const left = revolution - ((spin * turning) % revolution);
  return left > 1e-9 ? left : revolution;
}

export function formworkVisibility({
  t, seconds, showMode, strikeU, hasMembers, hasColumnMesh,
}) {
  const act = seconds > 0 && showMode === "timeline";
  if (!act) {
    // Rule 1 cuts both ways: the columns are the MACHINE'S, and Shell is
    // the vault ALONE -- the one rest mode that shows no machine shows no
    // columns either (Param: "it should just show shell but it shows the
    // columns too").
    return { group: false, net: false, members: false,
             columnMesh: !!hasColumnMesh && showMode !== "shell" };
  }
  const standing = !(strikeU >= 1);
  const net = t < seconds;
  const members = !!hasMembers && standing;
  return {
    group: net || members,
    net,
    members,
    // hasMembers, not members: once the strike has taken the animated
    // columns away the exported solids must not walk back on in their
    // place. They are the same columns, and the machine has left.
    columnMesh: !!hasColumnMesh && !hasMembers && standing,
  };
}

// How many times a joint texture repeats across the ground disc. The
// textures are drawn with a fixed number of pavers or tiles per image, so
// the repeat has to follow the disc's own size: a 0.6 m tile stays 0.6 m
// at any radius, which is the difference between resizing a floor and
// zooming a photograph of one. tileMetres is the physical size of ONE
// image, not of one paver.
// Which way each machine reverses out when the formwork is struck.
// Param, watching the strike: "you can see in the animation the machine
// is moving sideways. I would prefer that the machines all move backwards
// on both sides and fade away."
//
// Sideways is what an outward direction taken per MACHINE gives: measured
// from the middle of everything, the machine at the end of a row points
// along its own row, so a row fans apart instead of backing off. So the
// direction is taken per SIDE. Each row leaves along one direction, the
// row's own mean measured against the middle of the rows, which mirrors
// the two sides without either having to declare which it is. Horizontal
// only: the plant drives off across the floor, never into it.
//
// places: [{ side, x, y }], one per machine. centre: [x, y] of the work
// itself, used only where there is a single row and the rows' own middle
// can say nothing.
export function machineRetreats(places, centre) {
  const unit = (dx, dy) => {
    const d = Math.hypot(dx, dy);
    return d > 1e-6 ? [dx / d, dy / d] : null;
  };
  const rows = new Map();
  for (const place of places) {
    const key = Number.isFinite(place.side) ? place.side : 0;
    const row = rows.get(key) || { x: 0, y: 0, n: 0 };
    row.x += place.x;
    row.y += place.y;
    row.n += 1;
    rows.set(key, row);
  }
  for (const row of rows.values()) {
    row.x /= row.n;
    row.y /= row.n;
  }
  // The middle of the ROWS, not of the machines: a row of six and a row
  // of two still face each other squarely.
  const middle = { x: 0, y: 0 };
  for (const row of rows.values()) {
    middle.x += row.x / rows.size;
    middle.y += row.y / rows.size;
  }
  const away = new Map();
  for (const [key, row] of rows) {
    away.set(key, unit(row.x - middle.x, row.y - middle.y)
      // One row has no facing row to be measured against, so it backs
      // away from the work it stands around.
      || (centre ? unit(row.x - centre[0], row.y - centre[1]) : null));
  }
  return places.map((place) => {
    const key = Number.isFinite(place.side) ? place.side : 0;
    // A machine with nowhere to go fades where it stands rather than
    // being sent off in a direction nothing chose.
    return away.get(key) || unit(place.x - middle.x, place.y - middle.y) || [0, 0];
  });
}

export function groundRepeat(radius, tileMetres) {
  const extent = Math.max(0, radius) * 2;
  return [extent / tileMetres[0], extent / tileMetres[1]];
}

// ---------- where the sun actually is ----------
// The NOAA solar calculator's formulation, which is Meeus's low precision
// solar coordinates (Astronomical Algorithms ch. 25) with his equation of
// time (ch. 28) and the Saemundsson and Bennett refraction NOAA uses. Sixty
// lines, no tables, well under a microsecond, so a day cycle can call it
// every frame.
//
// Checked against an independent PSA implementation over 200,000 samples
// from 2020 to 2050, all latitudes: median difference 0.003 degrees, 99th
// percentile 0.022, worst case 0.13 at 85 degrees elevation where azimuth
// is geometrically ill conditioned and the shadow is a point anyway. The
// sun's disc is 0.53 degrees across, so the error is a twenty-fifth of the
// thing being placed, and a shadow cast 10 m lands within 4 mm. The real
// error in a studio is the timezone and the north offset, which is the
// argument for keeping both in the interface.
//
// Azimuth is degrees clockwise from north (0 N, 90 E, 180 S, 270 W).
// elevation includes refraction, which is what matches a photograph;
// elevationGeometric excludes it, and is what preset times are solved
// against so sunrise agrees with published tables.
const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

export function refraction(h) {
  if (h > 85) return 0;
  const t = Math.tan(h * D2R);
  const r = h > 5 ? 58.1 / t - 0.07 / t ** 3 + 0.000086 / t ** 5
    : h > -0.575 ? 1735 + h * (-518.2 + h * (103.4 + h * (-12.79 + h * 0.711)))
    : -20.772 / t;
  return r / 3600;
}

export function sunPosition(when, latitude, longitude, northOffset = 0) {
  const jd = when.getTime() / 86400000 + 2440587.5;
  const T = (jd - 2451545) / 36525;
  const L0 = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360;
  const M = 357.52911 + T * (35999.05029 - 0.0001537 * T);
  const e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T);
  const Mr = M * D2R;
  const C = Math.sin(Mr) * (1.914602 - T * (0.004817 + 0.000014 * T))
    + Math.sin(2 * Mr) * (0.019993 - 0.000101 * T)
    + Math.sin(3 * Mr) * 0.000289;
  const om = (125.04 - 1934.136 * T) * D2R;
  const lambda = (L0 + C - 0.00569 - 0.00478 * Math.sin(om)) * D2R;
  const eps0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60;
  const eps = (eps0 + 0.00256 * Math.cos(om)) * D2R;
  const decl = Math.asin(Math.sin(eps) * Math.sin(lambda));
  const y = Math.tan(eps / 2) ** 2;
  const L0r = L0 * D2R;
  const eot = 4 * R2D * (y * Math.sin(2 * L0r) - 2 * e * Math.sin(Mr)
    + 4 * e * y * Math.sin(Mr) * Math.cos(2 * L0r)
    - 0.5 * y * y * Math.sin(4 * L0r) - 1.25 * e * e * Math.sin(2 * Mr));
  const utMin = when.getUTCHours() * 60 + when.getUTCMinutes()
    + when.getUTCSeconds() / 60 + when.getUTCMilliseconds() / 60000;
  let ha = (utMin + eot + 4 * longitude) / 4 - 180;
  ha = ((ha + 180) % 360 + 360) % 360 - 180;
  const H = ha * D2R;
  const phi = latitude * D2R;
  const sinAlt = Math.sin(phi) * Math.sin(decl)
    + Math.cos(phi) * Math.cos(decl) * Math.cos(H);
  const alt = Math.asin(Math.max(-1, Math.min(1, sinAlt))) * R2D;
  let az = Math.atan2(-Math.sin(H),
    Math.tan(decl) * Math.cos(phi) - Math.sin(phi) * Math.cos(H)) * R2D;
  az = ((az - northOffset) % 360 + 360) % 360;
  return {
    azimuth: az, elevation: alt + refraction(alt), elevationGeometric: alt,
    declination: decl * R2D, equationOfTime: eot, hourAngle: ha,
  };
}

// THE SITE'S OWN CLOCK, from its longitude and nothing else.
//
// The studio's hour used to mean UTC. Nobody could see that while the
// site was fixed at London, where 12:00 UTC is solar noon to within two
// minutes, so the two agreed by coincidence. The moment the place became
// a control the coincidence broke: Sydney at "noon" was 23:00 and the
// sun sat 27 degrees below the horizon, so choosing a place put the
// lights out.
//
// Derived, not looked up. A zone database is a large dependency and it
// answers a POLITICAL question -- which is why Spain, on Madrid's
// meridian, keeps Berlin's clock -- where the one a shadow cares about
// is astronomical. So this is local MEAN time: within half an hour of
// the civil clock nearly everywhere, exactly the quantity a sun study
// wants, and carrying no daylight saving for the same reason.
export function utcOffsetMinutes(longitude) {
  return Math.round(longitude / 15) * 60;
}

// A UTC instant read off that clock. Only the reading is wanted, never
// the calendar day it belongs to, which is why this wraps instead of
// carrying a date: a Sydney sunrise is 07:00 there whichever UTC day the
// solver happened to find it on.
export function localClockMinutes(when, longitude) {
  const utc = when.getUTCHours() * 60 + when.getUTCMinutes();
  return ((utc + utcOffsetMinutes(longitude)) % 1440 + 1440) % 1440;
}

// Solar noon for a UTC day, iterated because the equation of time depends
// on the instant it is being solved for.
export function solarNoonUTC(dayStartMs, longitude) {
  let t = dayStartMs + 12 * 3600e3;
  for (let i = 0; i < 4; i += 1) {
    const eot = sunPosition(new Date(t), 0, longitude).equationOfTime;
    t = dayStartMs + (720 - 4 * longitude - eot) * 60000;
  }
  return t;
}

// When the sun reaches a given GEOMETRIC elevation, morning or evening.
// Null when it never gets that high or never gets that low on that day,
// which is a real answer in December at this latitude and is why the
// presets can grey out rather than lie.
export function timeAtElevation(dayUTC, latitude, longitude, targetDegrees, evening) {
  const start = Date.UTC(dayUTC.getUTCFullYear(), dayUTC.getUTCMonth(), dayUTC.getUTCDate());
  const noon = solarNoonUTC(start, longitude);
  let a = evening ? noon : noon - 12 * 3600e3;
  let b = evening ? noon + 12 * 3600e3 : noon;
  const f = (t) => sunPosition(new Date(t), latitude, longitude).elevationGeometric - targetDegrees;
  if (f(noon) < 0) return null;
  if (f(evening ? b : a) > 0) return null;
  for (let i = 0; i < 60; i += 1) {
    const m = (a + b) / 2;
    if ((f(m) > 0) === evening) a = m; else b = m;
  }
  return new Date((a + b) / 2);
}

// ---------- what colour the sun is at that height ----------
// Not taste, and not a control. What reddens a low sun is optical path
// length: at the zenith the beam crosses one air mass, at the horizon about
// thirty eight, and Rayleigh scattering strips blue as the fourth power of
// frequency. Dimming and reddening are therefore the same variable, which
// is why elevation drives both and the colour picker can go.
//
// The ramp below was derived by attenuating a 5778 K source through Rayleigh
// optical depth at the Kasten-Young air mass, an Angstrom aerosol term and
// the Chappuis ozone band, integrating against the CIE 1931 observer and
// finding the nearest point on the Planckian locus. It gives 5.6 magnitudes
// of extinction from zenith to horizon, which is the accepted astronomical
// figure, so it is calibrated rather than invented.
//
// The clamp at 1800 K is deliberate: the physics runs on to about 1400 K at
// the true horizon, but below 1800 K the beam is too weak to light anything
// and only stains the sky.
const SUN_RAMP = [
  { elevation: 60, colour: 0xffe7d1, lux: 100000 },
  { elevation: 45, colour: 0xffe5cd, lux: 92000 },
  { elevation: 30, colour: 0xffe0c2, lux: 78000 },
  { elevation: 20, colour: 0xffd9b3, lux: 62000 },
  { elevation: 15, colour: 0xffd3a5, lux: 50000 },
  { elevation: 10, colour: 0xffc88d, lux: 35000 },
  { elevation: 7, colour: 0xffbd76, lux: 23000 },
  { elevation: 5, colour: 0xffb05f, lux: 15000 },
  { elevation: 3, colour: 0xff9c3b, lux: 7300 },
  { elevation: 2, colour: 0xff8d1d, lux: 4100 },
  { elevation: 1, colour: 0xff7e00, lux: 1500 },
  { elevation: 0, colour: 0xff7e00, lux: 140 },
];

function mixChannels(a, b, u) {
  const channel = (shift) => {
    const from = (a >> shift) & 255;
    const to = (b >> shift) & 255;
    return Math.round(from + (to - from) * u);
  };
  return (channel(16) << 16) | (channel(8) << 8) | channel(0);
}

// The sun's colour and strength at an elevation, interpolated along the
// ramp. Strength is returned relative to the 60 degree figure, so it is a
// multiplier a renderer can apply to whatever it calls full sun, and it
// fades to nothing across the last degree and a half rather than switching
// off at the horizon.
export function sunLight(elevation) {
  if (elevation <= -0.833) return { colour: 0xff7e00, strength: 0 };
  let above = SUN_RAMP[0];
  let below = SUN_RAMP[SUN_RAMP.length - 1];
  for (let i = 0; i < SUN_RAMP.length - 1; i += 1) {
    if (elevation <= SUN_RAMP[i].elevation && elevation >= SUN_RAMP[i + 1].elevation) {
      above = SUN_RAMP[i];
      below = SUN_RAMP[i + 1];
      break;
    }
  }
  // Clamped at both ends rather than extrapolated. Above 60 degrees the
  // beam has stopped changing; below 0 the ramp has run out and the last
  // degree is the fade's business, not the interpolation's. Extrapolating
  // there ran u negative and pushed the colour back off the end of the
  // ramp, which is a bluer sun the further it sets.
  if (elevation >= SUN_RAMP[0].elevation) {
    above = below = SUN_RAMP[0];
  } else if (elevation <= 0) {
    above = below = SUN_RAMP[SUN_RAMP.length - 1];
  }
  const span = above.elevation - below.elevation;
  const u = span > 0 ? (elevation - below.elevation) / span : 0;
  const colour = mixChannels(below.colour, above.colour, u);
  let strength = (below.lux + (above.lux - below.lux) * u) / SUN_RAMP[0].lux;
  if (elevation < 1.5) {
    // Smoothstep out across the last degree and a half: the beam is gone
    // before the geometric horizon and the sky carries the scene, which is
    // the correct physics and the reason a naive sunset looks wrong.
    const t = Math.max(0, Math.min(1, (elevation + 0.833) / 2.333));
    strength *= t * t * (3 - 2 * t);
  }
  return { colour, strength };
}

// Where each emitting face of a box fixture sits and how big it is, for
// the strip and cube lights (studio.js, layFixtureEmitters). half is the
// box's half size in its own unscaled frame, centre its centre there,
// scale the fixture's scale on each axis, and faces a list such as
// ["+y", "-z"]. Each face comes back with:
//   position  the face's centre in the fixture's own unscaled frame,
//             which the fixture's scale then carries to the right place;
//   axes      the light's own X, Y and Z in that frame. X runs along its
//             width and Y along its height, and Z points INTO the
//             fixture, because a three.js RectAreaLight shines down its
//             -Z. X cross Y is Z, so the three make a true rotation;
//   width, height  the face's size in metres in the WORLD, because a rect
//             light is shaded from its rotation alone and never picks up
//             its parent's scale;
//   share     its part of the fixture's output, by area. They sum to 1.
export function fixtureFaces(half, centre, scale, faces) {
  const extent = [0, 1, 2].map((i) => 2 * half[i] * Math.abs(scale[i]));
  const unit = (i, sign) => {
    const axis = [0, 0, 0];
    axis[i] = sign;
    return axis;
  };
  const laid = faces.map((face) => {
    const sign = face[0] === "-" ? -1 : 1;
    const a = "xyz".indexOf(face[1]);
    if (a < 0) throw new Error("not a face of a box: " + face);
    const b = (a + 1) % 3;
    const c = (a + 2) % 3;
    // Width and height are the face's other two axes, taken in the order
    // that makes width cross height point into the fixture.
    const [ui, vi] = sign > 0 ? [c, b] : [b, c];
    const position = centre.slice();
    position[a] += sign * half[a];
    return { position, axes: [unit(ui, 1), unit(vi, 1), unit(a, -sign)],
      width: extent[ui], height: extent[vi], area: extent[ui] * extent[vi] };
  });
  const total = laid.reduce((sum, face) => sum + face.area, 0);
  for (const face of laid) face.share = total > 0 ? face.area / total : 0;
  return laid;
}

// ---------- which spots may cast a shadow ----------
// Every shadow-casting light costs ONE fragment texture unit, and a
// WebGL2 fragment shader is promised only sixteen of them. The
// material's own maps, the sun's shadow and the two tables an area
// light needs are all spending from that same purse, so the spots get
// what is left and no more.
//
// Measured on the studio's own scene rather than guessed: the TENTH
// shadow-casting spot makes every physical material fail to link
// ("FRAGMENT shader texture image units count exceeds
// MAX_TEXTURE_IMAGE_UNITS(16)"), and a material that will not link
// draws BLACK. Param photographed the result -- seventeen spots in one
// scene, and nothing on the screen but the sky.
//
// `wishes` is one entry per spot in PLACEMENT order, true where that
// spot asks for a shadow and is on screen to need one. The first
// `budget` wishes are granted and the rest are lit but cast nothing.
// Placement order, never distance: a shadow that appeared and vanished
// as the camera moved would be a worse fault than the one this fixes.
export function spotShadowGrants(wishes, budget) {
  const room = Math.max(0, Math.floor(budget) || 0);
  const grants = [];
  let given = 0;
  for (const wish of wishes) {
    const allow = !!wish && given < room;
    if (allow) given += 1;
    grants.push(allow);
  }
  return grants;
}

// ---------- which way the arrow keys point ----------
// Param: "the arrow keys to move it say 0.2m each time". An arrow key
// means a direction on the SCREEN -- press right, the thing goes right
// -- so the step is taken in the camera's own frame, flattened onto the
// floor. World axes would mean the same key moved a prop a different
// way depending on where the eye happened to be standing, which is the
// very thing arrow keys exist to avoid.
//
// `forward`, `right` and `up` are the camera's three axes in world
// space. Both answers come back as unit vectors in the XY plane.
//
// UP THE SCREEN IS THE CAMERA'S OWN UP, flattened -- not its forward.
// For every ordinary pose the two agree, because an unrolled camera's
// up and forward lean the same way over the floor; they part company
// in the two cases that matter. Looking straight down, forward is
// vertical and flattens to nothing, and up is the only one of them
// that still says which way the screen is pointing. Looking level, it
// is the other way about: up is vertical, and forward is what is left.
// Taking up first and falling back to forward answers both, and
// answers a rolled camera correctly into the bargain -- which forward
// first does not, since a camera banked on its side still has north up
// its screen only if you ignore the bank.
export function screenGroundAxes(forward, right, up) {
  const flat = (v) => {
    if (!v) return null;
    const length = Math.hypot(v[0], v[1]);
    return length > 1e-6 ? [v[0] / length, v[1] / length] : null;
  };
  const across = flat(right) || [1, 0];
  const along = flat(up) || flat(forward) || [0, 1];
  return { right: across, up: along };
}

// One arrow key, as a step in metres on the floor. Null for any other
// key, so the caller can let it through to whatever else wants it.
export function arrowStep(key, axes, step) {
  const table = {
    ArrowRight: [axes.right, 1], ArrowLeft: [axes.right, -1],
    ArrowUp: [axes.up, 1], ArrowDown: [axes.up, -1],
  };
  const chosen = table[key];
  if (!chosen) return null;
  const [axis, sign] = chosen;
  return [axis[0] * step * sign, axis[1] * step * sign];
}

// ---------- flying the camera with the keys ----------
// Param, 2026-09-13: "can we add movement with wsad and 1-4 for moevement
// speeds". Unreal's viewport keys: W and S along the way the camera looks,
// A and D across it, and the number row choosing how fast.
//
// Metres a second. 1 walks round the vault, 2 looks along a row, 3 crosses
// the site in a couple of seconds, 4 covers a whole scattered field.
export const FLY_SPEEDS = { 1: 1.5, 2: 5, 3: 15, 4: 45 };
// And Q and E, straight up and straight down. Param: "add q and e as raise
// and lower camera z with the wasd too" -- Q raises, E lowers, in the order
// he named them, and along the WORLD's z rather than the camera's own up,
// so a camera looking down still rises rather than backing away.
export const FLY_KEYS = ["w", "a", "s", "d", "q", "e"];

// Param, 2026-09-15: "press space bar to run the animation and press again
// to pause. double pressing quickly, brings it back to the start on pause".
// A press within this many milliseconds of the one before is the second of
// a double press: about the gap an operating system allows a double click.
export const DOUBLE_PRESS_MS = 300;

// What a press of Space does, given when the last counted press was (null
// for none) and when this one is: "rewind" when it follows that press
// closely enough to be the second of a double press, else "toggle". The
// caller forgets the press that completed a double, so a third quick press
// starts a fresh pair rather than rewinding again.
export function spaceBarAction(previousPress, now, windowMs = DOUBLE_PRESS_MS) {
  return previousPress !== null && now - previousPress <= windowMs
    ? "rewind" : "toggle";
}

// One frame's move for the keys held, as [x, y, z] in metres, or null when
// nothing is held or the held keys cancel. `right` is the camera's OWN
// screen-right, taken from its matrix, not forward crossed with up: looking
// straight down those two are parallel and A and D would do nothing.
// Diagonals are normalised, or W and D together would go 41 per cent
// faster than either alone.
export function flyStep(held, forward, right, speed, seconds) {
  const along = (held.has("w") ? 1 : 0) - (held.has("s") ? 1 : 0);
  const across = (held.has("d") ? 1 : 0) - (held.has("a") ? 1 : 0);
  const rise = (held.has("q") ? 1 : 0) - (held.has("e") ? 1 : 0);
  if (!along && !across && !rise) return null;
  const unit = (v) => {
    const length = Math.hypot(v[0], v[1], v[2]);
    return length > 1e-9 ? [v[0] / length, v[1] / length, v[2] / length] : [0, 0, 0];
  };
  const f = unit(forward);
  const r = unit(right);
  const x = f[0] * along + r[0] * across;
  const y = f[1] * along + r[1] * across;
  const z = f[2] * along + r[2] * across + rise;
  const length = Math.hypot(x, y, z);
  if (length < 1e-9) return null;
  const distance = speed * Math.max(0, seconds) / length;
  return [x * distance, y * distance, z * distance];
}

// ---------- the lens under Ctrl and the wheel ----------
// Param, 2026-09-13: "ctrl + scroll should alter the camera lens length".
// One notch of the wheel (100 in deltaY) is a tenth longer or shorter a
// lens, in millimetres, so a notch feels the same at 18 mm as at 85 mm;
// rolling forward (deltaY below 0) is a longer lens. Answered as the
// vertical field of view three reads, and held inside the dial's range so
// the Field of view slider always tells the truth about it.
export const LENS_NOTCH = 1.1;

export function lensStep(fovDegrees, deltaY, minDegrees, maxDegrees) {
  const half = (fovDegrees * Math.PI / 180) / 2;
  const millimetres = 12 / Math.tan(half);
  const longer = millimetres * Math.pow(LENS_NOTCH, -deltaY / 100);
  const fov = 2 * Math.atan(12 / longer) * 180 / Math.PI;
  return Math.max(minDegrees, Math.min(maxDegrees, fov));
}

// ---------- looking round from where the camera stands ----------
// Param, 2026-09-13: "cntrl + right click should control where the camera
// is looking, while staying stationary in its poition, just rotates around
// the position." A drag turns the look: across about the world's up, and
// up and down about the camera's own right, stopping short of straight up
// or down, where "across" would stop meaning anything.
export const LOOK_RADIANS_PER_PIXEL = 0.004;
export const LOOK_PITCH_LIMIT = 85 * Math.PI / 180;

export function lookTurn(direction, dx, dy, radiansPerPixel = LOOK_RADIANS_PER_PIXEL) {
  const length = Math.hypot(direction[0], direction[1], direction[2]) || 1;
  const x = direction[0] / length, y = direction[1] / length, z = direction[2] / length;
  // Dragging right turns the view right, dragging up looks up.
  const yaw = Math.atan2(y, x) - dx * radiansPerPixel;
  const pitch = Math.max(-LOOK_PITCH_LIMIT, Math.min(LOOK_PITCH_LIMIT,
    Math.asin(Math.max(-1, Math.min(1, z))) - dy * radiansPerPixel));
  return [Math.cos(pitch) * Math.cos(yaw), Math.cos(pitch) * Math.sin(yaw), Math.sin(pitch)];
}
