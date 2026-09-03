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

export function boxUVs(positions, centroid, offset) {
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
        (point[uAxis] - centroid[uAxis]) * 0.15 + offset[0],
        (point[vAxis] - centroid[vAxis]) * 0.15 + offset[1],
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
//   1. The columns are structure, not falsework. The machine raises them
//      and they STAND for the rest of the build, through the strike that
//      takes the net away. Nothing here reads the strike.
//   2. Exactly one drawing of the columns is ever on screen. The animated
//      members and the exported solids are the same tubes at the same
//      radius, so drawn together they z-fight; the members carry the
//      timeline, the solids carry every other mode.
//
// The net is the third actor: it follows the frames until the act ends and
// then yields to the finished instanced wires, whose pose at that instant
// is identical by the writer's time-100 guarantee.
export function formworkVisibility({ t, seconds, showMode, hasMembers, hasColumnMesh }) {
  const act = seconds > 0 && showMode === "timeline";
  if (!act) {
    return { group: false, net: false, members: false, columnMesh: !!hasColumnMesh };
  }
  const net = t < seconds;
  const members = !!hasMembers;
  return {
    group: net || members,
    net,
    members,
    columnMesh: !!hasColumnMesh && !members,
  };
}
