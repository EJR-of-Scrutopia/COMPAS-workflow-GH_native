// Pure geometry and field helpers for the studio scene. No three.js and no
// DOM: everything is plain arrays so tests/studio/test_fields.py can run
// this module in node against hand-computed values.

export function vertexNormals(vertices, faces) {
  const accumulator = vertices.map(() => [0, 0, 0]);
  for (const face of faces) {
    for (const [a, b, c] of [[face[0], face[1], face[2]], [face[0], face[2], face[3]]]) {
      const pa = vertices[a], pb = vertices[b], pc = vertices[c];
      const u = [pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]];
      const v = [pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]];
      // The raw cross product is twice the triangle area, so summing the
      // unnormalised crosses is exactly area weighting.
      const n = [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
      ];
      for (const index of [a, b, c]) {
        accumulator[index][0] += n[0];
        accumulator[index][1] += n[1];
        accumulator[index][2] += n[2];
      }
    }
  }
  return accumulator.map((n) => {
    const length = Math.hypot(n[0], n[1], n[2]);
    return length > 1e-12 ? [n[0] / length, n[1] / length, n[2] / length] : [0, 0, 1];
  });
}

export function segmentBoundaryEdges(faces, faceIndices) {
  const keyOf = (a, b) => (a < b ? a + "_" + b : b + "_" + a);
  const counts = new Map();
  for (const faceIndex of faceIndices) {
    const face = faces[faceIndex];
    for (let i = 0; i < face.length; i++) {
      const key = keyOf(face[i], face[(i + 1) % face.length]);
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  const boundary = [];
  for (const faceIndex of faceIndices) {
    const face = faces[faceIndex];
    for (let i = 0; i < face.length; i++) {
      const a = face[i], b = face[(i + 1) % face.length];
      if (counts.get(keyOf(a, b)) === 1) boundary.push({ a, b, face: faceIndex });
    }
  }
  return boundary;
}

export function extrudeSegment(vertices, faces, faceIndices, normals, thickness) {
  const half = thickness / 2;
  const offset = (i, sign) => [
    vertices[i][0] + normals[i][0] * half * sign,
    vertices[i][1] + normals[i][1] * half * sign,
    vertices[i][2] + normals[i][2] * half * sign,
  ];
  const positions = [];
  const corners = [];
  const push = (point, v, surface, face) => {
    positions.push(point[0], point[1], point[2]);
    corners.push({ v, surface, face });
  };
  for (const faceIndex of faceIndices) {
    const face = faces[faceIndex];
    for (const corner of [0, 1, 2, 0, 2, 3]) {
      push(offset(face[corner], 1), face[corner], "top", faceIndex);
    }
    for (const corner of [0, 2, 1, 0, 3, 2]) {
      push(offset(face[corner], -1), face[corner], "bottom", faceIndex);
    }
  }
  for (const { a, b, face } of segmentBoundaryEdges(faces, faceIndices)) {
    const ta = offset(a, 1), tb = offset(b, 1);
    const ba = offset(a, -1), bb = offset(b, -1);
    push(ta, a, "wall", face); push(tb, b, "wall", face); push(bb, b, "wall", face);
    push(ta, a, "wall", face); push(bb, b, "wall", face); push(ba, a, "wall", face);
  }
  return { positions, corners };
}

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
