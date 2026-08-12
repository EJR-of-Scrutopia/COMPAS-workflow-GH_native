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
export function sampleScalar(field, weights) {
  let total = 0;
  for (const [index, weight] of weights) {
    const value = field[index];
    if (value === null || value === undefined) return null;
    total += value * weight;
  }
  return total;
}

export function sampleVector(field, weights, fallback) {
  const out = [0, 0, 0];
  for (const [index, weight] of weights) {
    const value = field[index];
    if (!value) return fallback;
    out[0] += value[0] * weight;
    out[1] += value[1] * weight;
    out[2] += value[2] * weight;
  }
  return out;
}
