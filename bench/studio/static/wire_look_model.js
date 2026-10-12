// The wires drawn as the rope chosen (Param, 2026-10-12: "make the wires we
// render in vaulted the actual wires selected for the mechanism size and
// colour"). Pure values, so they are tested under node: the rope's own radius
// and colour at 1x, a viewing multiplier from 1 to 10 for views where a real
// rope is a hairline, and the nodes drawn as a clamp following the rope.

// Before any rope is known the net keeps the sizes it always had.
export const FALLBACK = Object.freeze({
  wireRadius: 0.02, nodeRadius: 0.03, colour: null, metalness: null, roughness: null,
});

// A node is drawn as a clamp this many rope diameters across.
export const NODE_ACROSS = 2.5;

export const SCALE_MIN = 1;
export const SCALE_MAX = 10;

export function clampScale(value) {
  if (value === null || value === undefined || value === "") return SCALE_MIN;
  const n = Number(value);
  if (!Number.isFinite(n)) return SCALE_MIN;
  return Math.min(SCALE_MAX, Math.max(SCALE_MIN, n));
}

// The look of one rope at a viewing multiplier: radii in metres, the colour
// as #rrggbb, metalness and roughness as the catalogue gives them.
export function wireLook(rope, scale = 1) {
  const diameter = rope ? Number(rope.diameter_mm) / 1000 : NaN;
  if (!(diameter > 0)) return { ...FALLBACK };
  const s = clampScale(scale);
  const render = rope.render || {};
  return {
    wireRadius: (diameter / 2) * s,
    nodeRadius: ((diameter * NODE_ACROSS) / 2) * s,
    colour: typeof render.colour === "string" ? render.colour : null,
    metalness: Number.isFinite(Number(render.metalness)) ? Number(render.metalness) : null,
    roughness: Number.isFinite(Number(render.roughness)) ? Number(render.roughness) : null,
  };
}

// The rope a study wears: its own pick while the catalogue still holds it,
// else the default, else the first rope listed; null with no ropes at all.
export function ropeFor(ropes, picked, fallbackKey) {
  const keys = ropes.map((rope) => rope.key);
  if (picked && keys.includes(picked)) return picked;
  if (fallbackKey && keys.includes(fallbackKey)) return fallbackKey;
  return keys.length ? keys[0] : null;
}

function escapeHtml(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function ropeOptionsHtml(ropes, selected) {
  return ropes.map((rope) => `<option value="${escapeHtml(rope.key)}"`
    + `${rope.key === selected ? " selected" : ""}>${escapeHtml(rope.label)}</option>`).join("");
}
