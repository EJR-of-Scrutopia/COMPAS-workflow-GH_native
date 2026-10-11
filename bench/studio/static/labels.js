// What the one Cable net tab's labels share (spec 2026-10-11 one Cable net
// tab, section 9): escaping text for the page, a force as a short label,
// and which labels to draw where they crowd. Pure, so it runs under node.

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

// A force as a label on the model: short, with its unit.
export function forceLabel(value) {
  if (value == null || !Number.isFinite(Number(value))) return "";
  const n = Number(value);
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + " kN";
  return (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1)) + " N";
}

// Which labels to draw where they would print over one another: each screen
// point ([x, y], or null for one off the view) in the order given; one that
// falls within gapX across and gapY down of a label already kept is not drawn.
export function spreadLabels(points, gapX, gapY) {
  const kept = [];
  return (points || []).map((point) => {
    if (!point) return false;
    if (kept.some((k) => Math.abs(k[0] - point[0]) < gapX && Math.abs(k[1] - point[1]) < gapY)) return false;
    kept.push(point);
    return true;
  });
}
