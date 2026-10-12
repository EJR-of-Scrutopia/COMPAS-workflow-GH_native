// A round steel tube, one unit long up y from 0 to 1 (Param, 2026-10-12: the
// column "to have a thickness and shape to have what we have specced"): its
// outer face, its inner face, and the two rings of wall at its open ends,
// each with its own normals so the ends read as cut steel. An inner radius of
// nought or less is a solid bar with discs for ends. THREE is handed in, so
// the drawing runs under node in the tests as it does in the page.

export function tubeGeometry(THREE, outer, inner, segments = 24) {
  const positions = [];
  const normals = [];
  const index = [];
  const hollow = inner > 0;
  const ring = (radius, y, nx, ny, nz) => {
    const start = positions.length / 3;
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      const c = Math.cos(a), s = Math.sin(a);
      positions.push(radius * c, y, radius * s);
      if (ny !== 0) normals.push(0, ny, 0);
      else normals.push(nx * c, 0, nz * s);
    }
    return start;
  };
  // a band between two rings; flip turns its faces the other way round
  const band = (a, b, flip) => {
    for (let i = 0; i < segments; i++) {
      const p = a + i, q = a + i + 1, r = b + i, t = b + i + 1;
      if (flip) index.push(p, q, r, q, t, r);
      else index.push(p, r, q, q, r, t);
    }
  };
  // the outer face, looking out
  band(ring(outer, 0, 1, 0, 1), ring(outer, 1, 1, 0, 1), false);
  if (hollow) {
    // the inner face, looking in
    band(ring(inner, 0, -1, 0, -1), ring(inner, 1, -1, 0, -1), true);
    // the wall at each end: up at the top, down at the bottom
    band(ring(inner, 1, 0, 1, 0), ring(outer, 1, 0, 1, 0), true);
    band(ring(inner, 0, 0, -1, 0), ring(outer, 0, 0, -1, 0), false);
  } else {
    for (const [y, ny, flip] of [[1, 1, false], [0, -1, true]]) {
      const centre = positions.length / 3;
      positions.push(0, y, 0);
      normals.push(0, ny, 0);
      const rim = ring(outer, y, 0, ny, 0);
      for (let i = 0; i < segments; i++) {
        if (flip) index.push(centre, rim + i, rim + i + 1);
        else index.push(centre, rim + i + 1, rim + i);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setIndex(index);
  return geometry;
}
