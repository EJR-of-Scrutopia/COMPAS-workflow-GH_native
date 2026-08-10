// The JS mirror of bench/studio/segmentation.py. The rule (canonical copy
// in docs/superpowers/plans/2026-08-09-bench-studio.md Task 3):
// 1. axis = mean (x, y) of face centroids.
// 2. rho = hypot from axis, theta = atan2 folded to [0, 2pi).
// 3. rings equal-width bins over [min rho, max rho], ring 0 = rim:
//    t = (hi - rho) / (hi - lo), ring = min(rings - 1, floor(t * rings)).
// 4. rho_mid(r) = hi - (r + 0.5) * (hi - lo) / rings.
// 5. wedges[r] = max(1, floor(12 * rho_mid(r) / rho_mid(0) + 0.5)).
// 6. offset(r) = (r % 2) * pi / wedges[r].
// 7. wedge = floor(((theta + offset) % 2pi) / (2pi / wedges[r])), clamped.
// 8. order: rings outward in, wedges ascending, occupied cells only.
// Use halfUp (floor x + 0.5) for rounding; the two languages disagree at .5 boundaries
// and the parity check would trip if we used the native round function.

const TWO_PI = 2 * Math.PI;
export const WEDGES_AT_RIM = 12;

function halfUp(value) {
  return Math.floor(value + 0.5);
}

export function segmentKey(ring, wedge) {
  return "r" + ring + "w" + wedge;
}

export function segmentFaces(centroids, rings) {
  const n = centroids.length;
  let ax = 0, ay = 0;
  for (const p of centroids) { ax += p[0]; ay += p[1]; }
  ax /= n; ay /= n;

  const rhos = centroids.map((p) => Math.hypot(p[0] - ax, p[1] - ay));
  const lo = Math.min(...rhos), hi = Math.max(...rhos);
  const spread = hi - lo;

  const rhoMid = (r) => hi - (r + 0.5) * spread / rings;
  const rimMid = rhoMid(0);
  const wedgeCounts = [];
  for (let r = 0; r < rings; r++) {
    wedgeCounts.push(rimMid > 0 ? Math.max(1, halfUp(WEDGES_AT_RIM * rhoMid(r) / rimMid)) : 1);
  }

  const assignment = [];
  for (let i = 0; i < n; i++) {
    const rho = rhos[i];
    const ring = spread <= 0 ? 0 : Math.min(rings - 1, Math.floor((hi - rho) / spread * rings));
    const count = wedgeCounts[ring];
    let theta = Math.atan2(centroids[i][1] - ay, centroids[i][0] - ax) % TWO_PI;
    if (theta < 0) theta += TWO_PI;
    const offset = (ring % 2) * Math.PI / count;
    const wedge = Math.min(count - 1, Math.floor(((theta + offset) % TWO_PI) / (TWO_PI / count)));
    assignment.push([ring, wedge]);
  }

  const occupied = new Set(assignment.map(([r, w]) => r + ":" + w));
  const order = [];
  for (let r = 0; r < rings; r++) {
    for (let w = 0; w < wedgeCounts[r]; w++) {
      if (occupied.has(r + ":" + w)) order.push([r, w]);
    }
  }
  return { axis: [ax, ay], rings, wedge_counts: wedgeCounts, assignment, order };
}
