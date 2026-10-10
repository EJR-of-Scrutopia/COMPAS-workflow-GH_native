// The Formwork tab's model (spec 2026-10-10 formwork tab): the capture
// document the formwork engine writes, read into typed arrays, and the
// player's clock over it. Pure: no page and no three.js, so it runs under node
// in the tests. formwork.js wires it to the page, formwork_view.js draws it.

export const SCHEMA = "bench.formwork-sim/1";
// The studio plays machine time 0 to 100 in its 12 s formwork act; the raise,
// finish and hold go at that rate, and each tiling quarter takes TILING_BEAT
// (the owner's answer of 10 October 2026).
export const ACT_SECONDS = 12;
export const TILING_BEAT = 0.5;

// One packed array (solve_formwork.pack): base64 of little-endian float32,
// read through a DataView so the byte order is the document's on any machine.
export function decodeF32(entry) {
  if (!entry || typeof entry.f32 !== "string") return null;
  const binary = atob(entry.f32);
  const view = new DataView(new ArrayBuffer(binary.length));
  for (let i = 0; i < binary.length; i++) view.setUint8(i, binary.charCodeAt(i));
  const out = new Float32Array(binary.length >> 2);
  for (let i = 0; i < out.length; i++) out[i] = view.getFloat32(i * 4, true);
  return out;
}

function metres(values) {
  if (!values) return null;
  const out = new Float32Array(values.length);
  for (let i = 0; i < values.length; i++) out[i] = values[i] / 1000;
  return out;
}

function largestOf(values) {
  let top = 0;
  if (!values) return top;
  for (let i = 0; i < values.length; i++) if (values[i] > top) top = values[i];
  return top;
}

// The document read once: every position in metres, every force in newtons,
// every deviation in millimetres. Each scale is the largest over the whole
// run, so a colour is the same newtons in every capture (spec section 9). A
// document from before the skin and the ground were written is older. Not a
// capture document: null.
export function readSim(doc) {
  if (!doc || doc.schema !== SCHEMA || !Array.isArray(doc.captures) || !doc.captures.length) {
    return null;
  }
  const net = doc.net || {};
  const rim = doc.rim || {};
  const trees = doc.trees || {};
  const captures = doc.captures.map((c) => ({
    phase: c.phase, time: c.time, row: c.row, quarter: c.quarter,
    x: metres(decodeF32(c.x)),
    tension: decodeF32(c.tension),
    deviation: decodeF32(c.deviation),
    headPush: decodeF32(c.head_push),
    wireTension: decodeF32(c.wire_tension),
    letOut: decodeF32(c.let_out),
    treeX: metres(decodeF32(c.tree_x)),
    treeUtilisation: decodeF32(c.tree_utilisation),
    ground: Array.isArray(c.ground) ? c.ground : null,
    addedFaces: Array.isArray(c.added_faces) ? c.added_faces : null,
  }));
  const scale = (field) => Math.max(0, ...captures.map((c) => largestOf(c[field])));
  return {
    study: doc.study, options: doc.options || {},
    nodes: Number(net.nodes) || 0, edges: net.edges || [],
    faces: Array.isArray(net.faces) ? net.faces : null,
    design: metres(decodeF32(net.design)),
    rim: { nodes: rim.nodes || [], names: rim.names || [], anchors: metres(decodeF32(rim.anchors)),
           into: decodeF32(rim.into), machines: rim.machines || [] },
    trees: { members: trees.members || [], heads: trees.heads || [], feet: trees.feet || [],
             diameter: Number(trees.diameter) || 60.3, wall: trees.wall },
    captures,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
              deviation: scale("deviation"), utilisation: scale("treeUtilisation") },
    older: !Array.isArray(net.faces) || doc.captures.some((c) => !Array.isArray(c.ground)),
  };
}

// The capture's label: its machine time and phase during the raise, its row
// and quarter while tiling.
export function captureLabel(capture) {
  if (!capture) return "";
  if (capture.phase === "tiling") return capture.row + " q" + capture.quarter;
  return "t " + Number(Number(capture.time).toFixed(1)) + " " + capture.phase;
}

// When the player reaches each capture, in seconds at 1x: the raise, finish
// and hold at the act's rate from the first capture's machine time, each
// tiling quarter TILING_BEAT after the capture before it.
export function captureTimes(captures) {
  const at = [];
  let t = 0;
  let machine = null;
  (captures || []).forEach((c, i) => {
    if (i > 0) {
      t += c.phase !== "tiling" && c.time != null && machine != null
        ? (Number(c.time) - machine) * ACT_SECONDS / 100 : TILING_BEAT;
    }
    at.push(t);
    if (c.time != null) machine = Number(c.time);
  });
  return at;
}

// Where the player is at second s: the captures either side and how far
// between them (0 to 1), which the drawing blends, and the nearer one, whose
// numbers are shown (spec section 7: every number is a capture's, never a
// blend).
export function playhead(times, s) {
  const n = (times || []).length;
  if (!n) return null;
  const t = Math.min(Math.max(Number(s) || 0, 0), times[n - 1]);
  let i = 0;
  while (i < n - 1 && times[i + 1] <= t) i++;
  if (i >= n - 1) return { from: n - 1, to: n - 1, blend: 0, nearer: n - 1 };
  const span = times[i + 1] - times[i];
  const blend = span > 0 ? (t - times[i]) / span : 0;
  return { from: i, to: i + 1, blend, nearer: blend < 0.5 ? i : i + 1 };
}
