// The Formwork tab's model (spec 2026-10-10 formwork tab): the capture
// document the formwork engine writes, read into typed arrays, and the
// player's clock over it. Pure: no page and no three.js, so it runs under node
// in the tests. formwork.js wires it to the page, formwork_view.js draws it.

import { escapeHtml, forceLabel } from "./labels.js";

export const SCHEMA = "bench.formwork-sim/1";
// The studio plays machine time 0 to 100 in its 12 s formwork act; the raise,
// finish and hold go at that rate, and each tiling quarter takes TILING_BEAT
// (the owner's answer of 10 October 2026).
export const ACT_SECONDS = 12;
export const TILING_BEAT = 0.5;
// The jacking of the holds in a run made before they went (11 October 2026),
// at machine time 100 like the hold before it, takes this long, so the player
// reaches both (found by the final review: the hold
// could not be reached and Back stuck at the jacking).
export const JACK_SECONDS = 2;

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

// The 95th percentile of some values, nought for none.
export function percentile95(values) {
  if (!values || !values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(0.95 * sorted.length) - 1)];
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
    treeAxial: decodeF32(c.tree_axial) || new Float32Array(0),
    ground: Array.isArray(c.ground) ? c.ground : null,
    addedFaces: Array.isArray(c.added_faces) ? c.added_faces : null,
    tendonTension: decodeF32(c.tendon_tension) || new Float32Array(0),
  }));
  // a capture with no positions cannot be drawn: the document is not read
  // (final review 9)
  if (captures.some((c) => !c.x || !c.treeX)) return null;
  const scale = (field) => Math.max(0, ...captures.map((c) => largestOf(c[field])));
  // the heads' pushes, which the drawing scales by their 95th percentile, so
  // one spike does not shrink every other push to nothing (final review 4)
  const pushes = [];
  for (const c of captures) {
    const p = c.headPush;
    for (let i = 0; p && i + 2 < p.length; i += 3) {
      const size = Math.hypot(p[i], p[i + 1], p[i + 2]);
      if (size > 0) pushes.push(size);
    }
  }
  const push = percentile95(pushes);
  // the across tendons (spec 2026-10-11 across tendons, sections 4 and 6):
  // each edge's family, the pull and each tendon's line, and the tendon whose
  // path runs along each edge, and through each node past its head (-1 for
  // none)
  const edges = net.edges || [];
  const families = Array.isArray(net.families) ? net.families : null;
  const tendons = doc.tendons && Array.isArray(doc.tendons.lines)
    ? { pull: Number(doc.tendons.pull_n) || 0, lines: doc.tendons.lines } : null;
  const edgeTendon = new Int32Array(edges.length).fill(-1);
  const nodeTendon = new Int32Array(Number(net.nodes) || 0).fill(-1);
  if (tendons) {
    const pair = (a, b) => Math.min(a, b) + "," + Math.max(a, b);
    const index = new Map(edges.map(([a, b], e) => [pair(a, b), e]));
    tendons.lines.forEach((line, t) => {
      const path = line.path || [];
      for (let k = 1; k < path.length; k++) {
        const e = index.get(pair(path[k - 1], path[k]));
        if (e != null) edgeTendon[e] = t;
        if (path[k] >= 0 && path[k] < nodeTendon.length) nodeTendon[path[k]] = t;
      }
    });
  }
  // each family's largest over the run: along, its ropes alone; across, each
  // rope with its tendon; both, every member so
  let along = 0;
  let across = 0;
  let both = 0;
  for (const c of captures) {
    for (let e = 0; c.tension && e < edges.length; e++) {
      const whole = memberForce({ edgeTendon }, c, e);
      if (whole > both) both = whole;
      const family = families && families[e];
      if (family === "along" && c.tension[e] > along) along = c.tension[e];
      if (family === "across" && whole > across) across = whole;
    }
  }
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
    // a run made with holds, which went on 11 October 2026 (his word: "it
    // doesnt work for what i am thinking"): its rods are not shown, and it is
    // to be run again
    held: Array.isArray(net.holds) && net.holds.length > 0,
    // each node's side (spec 2026-10-11 one Cable net tab, section 6), and the
    // mechanism's drum and carriage judged on the run's own reels (8.1)
    sides: Array.isArray(net.sides) ? net.sides : null,
    checks: doc.checks || null,
    families, tendons, edgeTendon, nodeTendon, tendonsReason: doc.tendons_reason || null,
    scales: { tension: scale("tension"), wire: scale("wireTension"),
              deviation: scale("deviation"), utilisation: scale("treeUtilisation"), push,
              along, across, both },
    // a run from before the families were written cannot tell Along from
    // Across (spec 2026-10-11 across tendons, section 7)
    older: !Array.isArray(net.faces) || doc.captures.some((c) => !Array.isArray(c.ground))
      || !("families" in net),
  };
}

// A member's whole force at a capture, N: its rope's tension and, on an across
// line, the pull of the tendon beside it (spec 2026-10-11 across tendons,
// section 6).
export function memberForce(sim, c, e) {
  const t = sim.edgeTendon ? sim.edgeTendon[e] : -1;
  return c.tension[e] + (t >= 0 ? c.tendonTension[t] || 0 : 0);
}

// The capture's label: its machine time and phase during the raise, its row
// and quarter while tiling.
export function captureLabel(capture) {
  if (!capture) return "";
  if (capture.phase === "tiling") return capture.row + " q" + capture.quarter;
  return "t " + Number(Number(capture.time).toFixed(1)) + " " + capture.phase;
}

// The first capture of the scene after the one capture index is in, or the
// last capture from the last scene (his ask of 11 October 2026: the player
// steps on a scene, not a capture). A scene is a phase (the raise, the
// finish, the hold, the jacking), and in the tiling each row of tiles.
export function nextScene(captures, index) {
  const list = captures || [];
  if (!list.length) return 0;
  const scene = (c) => (c.phase === "tiling" ? "tiling " + c.row : c.phase);
  const here = scene(list[Math.min(Math.max(index, 0), list.length - 1)]);
  for (let i = Math.max(index, 0) + 1; i < list.length; i++) {
    if (scene(list[i]) !== here) return i;
  }
  return list.length - 1;
}

// When the player reaches each capture, in seconds at 1x: the raise, finish
// and hold at the act's rate from the first capture's machine time, the
// capture after the jacking JACK_SECONDS after the hold, each tiling quarter
// TILING_BEAT after the capture before it.
export function captureTimes(captures) {
  const at = [];
  let t = 0;
  let machine = null;
  (captures || []).forEach((c, i) => {
    if (i > 0) {
      if (c.phase === "holds") t += JACK_SECONDS;
      else {
        t += c.phase !== "tiling" && c.time != null && machine != null
          ? (Number(c.time) - machine) * ACT_SECONDS / 100 : TILING_BEAT;
      }
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

// ---------- what the tab shows of a capture ----------

export function kilonewtons(n) {
  return (Number(n) / 1000).toFixed(1) + " kN";
}

export function newtons(n) {
  return Number(n).toFixed(0) + " N";
}

export function millimetres(mm) {
  const v = Number(mm);
  return (v >= 10 ? v.toFixed(0) : v.toFixed(1)) + " mm";
}

function keyed(rows) {
  return "<table>" + rows.map(([name, value]) =>
    `<tr><th>${escapeHtml(name)}</th><td>${value}</td></tr>`).join("") + "</table>";
}

function pushOf(capture, head) {
  const p = capture.headPush;
  return p ? Math.hypot(p[3 * head], p[3 * head + 1], p[3 * head + 2]) : 0;
}

// Two neighbouring rings of a tendon at most this far apart are at their stop
// (net_engine.TENDON_STOP_MM, 20 mm), to within half a millimetre.
export const RING_STOP_M = 0.0205;

// The frame line (spec section 9): the largest rope, wire, tree and deviation
// at the capture, and how many heads touch their nodes; and with tendons, how
// many pull and how many rings are at their stop (spec 2026-10-11 across
// tendons, section 6).
export function frameLine(sim, index) {
  const c = sim && sim.captures[index];
  if (!c) return null;
  const heads = sim.trees.heads.length;
  let touching = 0;
  for (let h = 0; h < heads; h++) if (pushOf(c, h) > 0) touching += 1;
  const lines = sim.tendons ? sim.tendons.lines : [];
  let pulling = 0;
  let atStop = 0;
  lines.forEach((line, t) => {
    if ((c.tendonTension[t] || 0) > 0) pulling += 1;
    const path = line.path || [];
    for (let k = 1; k < path.length; k++) {
      const a = 3 * path[k - 1];
      const b = 3 * path[k];
      if (Math.hypot(c.x[b] - c.x[a], c.x[b + 1] - c.x[a + 1], c.x[b + 2] - c.x[a + 2]) < RING_STOP_M) {
        atStop += 1;
      }
    }
  });
  return { rope: largestOf(c.tension), wire: largestOf(c.wireTension),
           trees: largestOf(c.treeUtilisation), deviation: largestOf(c.deviation), touching, heads,
           pulling, tendons: lines.length, atStop };
}

export function frameLineHtml(line) {
  if (!line) return "";
  return keyed([["Rope max", kilonewtons(line.rope)], ["Wire max", newtons(line.wire)],
    ["Trees", line.trees.toFixed(2)], ["Deviation max", millimetres(line.deviation)],
    ["Heads touching", line.touching + "/" + line.heads],
    ...(line.tendons ? [["Pulling", line.pulling + "/" + line.tendons], ["At the stop", String(line.atStop)]]
      : [])]);
}

// Colour by (spec 2026-10-11 one Cable net tab, section 5.1), one at a time;
// Along, Across and Both in place of Ropes (spec 2026-10-11 across tendons,
// section 6).
export const COLOUR_BY = [["wire", "Wires"], ["along", "Along"], ["across", "Across"],
  ["both", "Both"], ["deviation", "Offset"], ["utilisation", "Trees"], ["off", "Off"]];

// The full ramp every Colour by is drawn on, from a cool blue that shows on the
// net (so the whole object reads, not only its hotspots) through to red; and
// the tolerance's bands, which Compare's offset lines wear.
export const RAMP_STOPS = ["#3a6fc4", "#3fa6a0", "#e8c547", "#cc2211"];
const DEVIATION_COLOURS = { within: "#3f9e57", near: "#c99a2e", over: "#c24936" };

function hexRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export function ramp(fraction) {
  const f = Math.min(1, Math.max(0, Number(fraction) || 0)) * (RAMP_STOPS.length - 1);
  const i = Math.min(RAMP_STOPS.length - 2, Math.floor(f));
  const a = hexRgb(RAMP_STOPS[i]);
  const b = hexRgb(RAMP_STOPS[i + 1]);
  return a.map((v, k) => v + (b[k] - v) * (f - i));
}

export function bandColour(mm, tolerance) {
  return hexRgb(DEVIATION_COLOURS[deviationBand(mm, tolerance)]);
}

// A deviation's band against the tolerance, as the Sag lens bands a sag: over
// it, near it (over half of it), or within it.
export function deviationBand(mm, tolerance) {
  if (Number(mm) > tolerance) return "over";
  if (Number(mm) > 0.5 * tolerance) return "near";
  return "within";
}

// The scale of each Colour by: the run's largest, so a colour is the same
// value in every capture.
const SCALE = { wire: "wire", tension: "tension", deviation: "deviation", utilisation: "utilisation",
                along: "along", across: "across", both: "both" };

// The colour a value is drawn in under a Colour by choice, [r, g, b] from 0 to
// 1, on the full ramp over the run (spec 2026-10-11 section 5.1); null where
// the choice colours nothing (Off). Whether a part is over its limit is
// Weakest's to show, not the colour's.
export function colourOf(by, value, sim) {
  if (!sim || value == null || !SCALE[by]) return null;
  const top = sim.scales[SCALE[by]];
  return ramp(top > 0 ? value / top : 0);
}

function kilo(n) {
  return (Number(n) / 1000).toFixed(1) + " kN";
}

// The other family's members under Along or Across, drawn in a quiet grey
// (spec 2026-10-11 across tendons, section 6): a mid grey, so it stays under
// the family coloured on a dark viewport and shows on a light one (found on
// screen: a light grey read near white, louder than the family coloured).
export const OTHER_FAMILY = hexRgb("#7d828a");

// The colour a net member is drawn in under a Colour by choice: its rope's
// tension under the old Ropes, its family's force under Along and Across (the
// other family grey), its whole force under Both; null where the choice does
// not colour members.
export function memberColour(by, sim, c, e) {
  if (by === "tension") return colourOf("tension", c.tension[e], sim);
  if (by === "both") return colourOf("both", memberForce(sim, c, e), sim);
  if (by === "along" || by === "across") {
    if (!sim.families || sim.families[e] !== by) return OTHER_FAMILY;
    return colourOf(by, by === "along" ? c.tension[e] : memberForce(sim, c, e), sim);
  }
  return null;
}

// The key a Colour by choice draws: a real scale from nought to the run's
// largest, and the limit named, with its place on the bar (fraction) when it
// is on it; null for Off. limits: { have, rope, tolerance } (a bare number is
// the tolerance, as the tab's older calls give it).
export function colourKey(by, sim, limits) {
  if (!sim || !SCALE[by]) return null;
  const given = typeof limits === "number" ? { tolerance: limits } : (limits || {});
  const top = sim.scales[SCALE[by]];
  const keyed = {
    wire: ["wire tension, N", grouped(top), given.have, (v) => "one spool " + grouped(v)],
    tension: ["rope tension, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    along: ["along, rope tension, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    across: ["across, rope and tendon, kN", kilo(top), null, null],
    both: ["rope and tendon, kN", kilo(top), given.rope, (v) => "working load " + kilo(v)],
    deviation: ["offset, mm", millimetres(top), given.tolerance, (v) => "tolerance " + Number(v) + " mm"],
    utilisation: ["tree utilisation", top.toFixed(2), 1.0, (v) => "capacity " + Number(v).toFixed(1)],
  }[by];
  const [title, max, limit, named] = keyed;
  const known = limit != null && Number.isFinite(Number(limit));
  const fraction = known && top > 0 && Number(limit) <= top ? Number(limit) / top : null;
  return { title, min: "0", max, limitText: known ? named(limit) : null, fraction };
}

// The parts a Colour by puts its values on, and which Show tick they need.
const LABEL_PART = { wire: "wires", tension: "net", deviation: "net", utilisation: "trees", off: "heads",
                     along: "net", across: "net", both: "net" };

export function labelsShown(by, show) {
  return !!(show || {})[LABEL_PART[by]];
}

// Each value a capture has for a Colour by: [target, value, side], the side
// the part is on (null where the run has none, and for the trees).
function valuesFor(sim, c, by) {
  const side = (node) => (sim.sides && node != null ? sim.sides[node] ?? null : null);
  const out = [];
  if (by === "wire") {
    sim.rim.nodes.forEach((node, w) => out.push([{ kind: "wire", index: w }, c.wireTension[w], side(node)]));
  } else if (by === "tension") {
    sim.edges.forEach(([u], e) => out.push([{ kind: "member", index: e }, c.tension[e], side(u)]));
  } else if (by === "along" || by === "across" || by === "both") {
    sim.edges.forEach(([u], e) => {
      if (by !== "both" && (!sim.families || sim.families[e] !== by)) return;
      out.push([{ kind: "member", index: e }, by === "along" ? c.tension[e] : memberForce(sim, c, e),
                side(u)]);
    });
  } else if (by === "deviation") {
    for (let i = 0; i < sim.nodes; i++) out.push([{ kind: "node", index: i }, c.deviation[i], side(i)]);
  } else if (by === "utilisation") {
    sim.trees.members.forEach((_, k) => out.push([{ kind: "tree", index: k }, c.treeUtilisation[k], null]));
  } else if (by === "off") {
    sim.trees.heads.forEach(([node], h) => out.push([{ kind: "node", index: node }, pushOf(c, h), side(node)]));
  }
  return out;
}

function textFor(by, value) {
  if (by === "wire" || by === "off") return grouped(value);
  if (by === "tension" || by === "along" || by === "across" || by === "both") return kilo(value);
  if (by === "deviation") return millimetres(value);
  return Number(value).toFixed(2);
}

// The values a capture puts on the model (spec 2026-10-11 section 5.2): for
// the Colour by shown, its count largest, then the largest of each side not
// yet among them; with Colour by off, the heads' pushes. Largest first, so
// where they crowd the largest is the one kept.
export function colourLabels(sim, index, by, count = 5) {
  const c = sim && sim.captures[index];
  if (!c || !LABEL_PART[by]) return [];
  const values = valuesFor(sim, c, by).filter(([, value]) => value > 0);
  values.sort((a, b) => b[1] - a[1] || a[0].index - b[0].index);
  const picked = values.slice(0, count);
  const sides = new Set(picked.map(([, , side]) => side));
  for (const entry of values) {
    if (entry[2] != null && !sides.has(entry[2])) {
      picked.push(entry);
      sides.add(entry[2]);
    }
  }
  return picked.map(([target, value]) => ({ ...target, value, text: textFor(by, value) }));
}

// The values on the model (spec 2026-10-11 sections 5.2 to 5.4): the Colour
// by's (by, or null with the values off), then each weakest part's value, or
// with none over what it has to spare, then with Compare the largest offsets
// in mm. One label a part, the first kept; largest first within each.
const KIND_BY = { wire: "wire", member: "tension", tree: "utilisation", node: "deviation" };

export function modelLabels(sim, index, { by = null, weakest = [], compare = false } = {}) {
  const out = [];
  const seen = new Set();
  const add = (label) => {
    const key = label.kind + ":" + label.index;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(label);
    }
  };
  if (!sim) return out;
  if (by != null) colourLabels(sim, index, by).forEach(add);
  for (const item of weakest || []) {
    add({ kind: item.kind, index: item.index, value: item.value,
          text: item.over ? item.text : textFor(KIND_BY[item.kind], item.limit - item.value) + " spare" });
  }
  if (compare) colourLabels(sim, index, "deviation").forEach(add);
  return out;
}

// The weakest parts at a capture (spec 2026-10-11 section 5.3): every part
// over its limit, the furthest over first (a wire over one spool's pull, a
// rope over its working load, a tree member over 1.0, a node outside the
// tolerance); with none over, the five closest to their limits. A kind with
// no limit is not judged. limits: { have, rope, tolerance }.
export function weakestAt(sim, index, limits) {
  const c = sim && sim.captures[index];
  if (!c) return [];
  const given = limits || {};
  const kinds = [["wire", "wire", given.have], ["tension", "member", given.rope],
                 ["utilisation", "tree", 1.0], ["deviation", "node", given.tolerance]];
  const all = [];
  for (const [by, kind, limit] of kinds) {
    if (limit == null || !(Number(limit) > 0)) continue;
    for (const [target, value] of valuesFor(sim, c, by)) {
      if (value == null || !Number.isFinite(value)) continue;
      all.push({ kind, index: target.index, value, limit: Number(limit), ratio: value / Number(limit),
                 over: value > Number(limit), text: textFor(by, value) });
    }
  }
  all.sort((a, b) => b.ratio - a.ratio);
  const over = all.filter((item) => item.over);
  return over.length ? over : all.slice(0, 5);
}

// Where a part is at a capture, in metres: a member's midpoint, a node, a
// wire's rim node, a tree member's midpoint, the centre of a machine's rim
// nodes. The labels stand there and the worst tables turn the camera there.
export function targetPoint(sim, index, target) {
  const c = sim && sim.captures[index];
  if (!c || !target) return null;
  const at = (array, i) => (array && i != null && 3 * i + 2 < array.length
    ? [array[3 * i], array[3 * i + 1], array[3 * i + 2]] : null);
  const mid = (a, b) => (a && b ? a.map((v, k) => (v + b[k]) / 2) : null);
  if (target.kind === "node") return at(c.x, target.index);
  if (target.kind === "member") {
    const edge = sim.edges[target.index];
    return edge ? mid(at(c.x, edge[0]), at(c.x, edge[1])) : null;
  }
  if (target.kind === "wire") return at(c.x, sim.rim.nodes[target.index]);
  if (target.kind === "tree") {
    const member = sim.trees.members[target.index];
    return member ? mid(at(c.treeX, member[0]), at(c.treeX, member[1])) : null;
  }
  if (target.kind === "machine") {
    const points = (sim.rim.machines[target.index] || []).map((node) => at(c.x, node)).filter(Boolean);
    if (!points.length) return null;
    return [0, 1, 2].map((k) => points.reduce((sum, p) => sum + p[k], 0) / points.length);
  }
  return null;
}

// The card a click on a node opens (spec section 9): where it is, how far from
// where it should be, on the ground or not, a head's push, a rim node's wire,
// then each member at the node with its tension.
export function formworkPickHtml(sim, index, node) {
  const c = sim && sim.captures[index];
  if (!c || node == null || node < 0 || node >= sim.nodes) return "";
  const p = [c.x[3 * node], c.x[3 * node + 1], c.x[3 * node + 2]];
  const rows = [["Node", String(node)], ["At", p.map((v) => v.toFixed(3)).join(", ") + " m"],
                ["Deviation", millimetres(c.deviation[node])]];
  if (c.ground) rows.push(["Ground", c.ground.includes(node) ? "yes" : "no"]);
  const head = sim.trees.heads.findIndex(([net]) => net === node);
  if (head >= 0) rows.push(["Head push", newtons(pushOf(c, head))]);
  const wire = sim.rim.nodes.indexOf(node);
  if (wire >= 0) {
    rows.push(["Wire", escapeHtml(sim.rim.names[wire] || "#" + wire)],
              ["Wire tension", newtons(c.wireTension[wire])]);
  }
  // a ring or free end's tendon (spec 2026-10-11 across tendons, section 6);
  // a head's push already carries its tendons' pull
  const tendon = sim.nodeTendon ? sim.nodeTendon[node] : -1;
  if (tendon >= 0) rows.push(["Tendon", newtons(c.tendonTension[tendon] || 0)]);
  const members = [];
  sim.edges.forEach(([u, v], e) => {
    if (u === node || v === node) {
      members.push(`<tr><td>${u === node ? v : u}</td><td>${forceLabel(c.tension[e])}</td></tr>`);
    }
  });
  return keyed(rows) + (members.length
    ? "<table><tr><th>To node</th><th>Tension</th></tr>" + members.join("") + "</table>" : "");
}

const MECHANISM_KEYS = ["motor", "ratio", "pulley", "rope", "wires_per_motor"];

// One line each (spec 2026-10-11 one Cable net tab, section 4.4): no run yet,
// an older run, and a run not made with the mechanism chosen (its five
// choices, wires a motor among them). A wall is judged again without a run
// (withWall), so it never makes a run out of date. chosen: { mechanism }, the
// pop-up's five choices, null while they load.
export function formworkWarnings(sim, chosen) {
  if (!sim) return ["No run yet: Run"];
  const out = [];
  if (sim.older) out.push("Run again: older run");
  const mine = chosen && chosen.mechanism;
  const ran = (sim.options || {}).mechanism;
  if (mine && (!ran || MECHANISM_KEYS.some((key) => (ran[key] ?? null) !== (mine[key] ?? null)))) {
    out.push("Run again: mechanism changed");
  }
  if (sim.held) out.push("Run again: made with holds");
  // the pull a tendon (spec 2026-10-11 across tendons, section 7), and why a
  // pulled run has none (section 2)
  const pull = chosen && chosen.pullIn;
  if (pull != null && Number(pull) !== Number((sim.options || {}).pull_in || 0)) {
    out.push("Run again: pull changed");
  }
  if (sim.tendonsReason) out.push(sim.tendonsReason);
  return out;
}

// A whole number of newtons with its thousands marked: "57,476 N".
export function grouped(n) {
  return Math.round(Number(n)).toLocaleString("en-GB") + " N";
}

// The answer, from the run alone (spec 2026-10-11 one Cable net tab, section
// 4.3): the largest wire tension anywhere in the run, its wire and capture;
// one spool's pull of the run's mechanism; how much is missing or to spare;
// the form, the worst offset and the mean at the run's last capture, against
// the tolerance; and the trees' load, the member the run judges worst, its
// force and what its tube takes (his ask of 11 October 2026). have and gap
// are null for a run cut for a named prestress.
export function answer(sim, tolerance) {
  if (!sim) return null;
  let needed = null;
  sim.captures.forEach((c, k) => {
    const t = c.wireTension;
    for (let w = 0; t && w < t.length; w++) {
      if (!needed || t[w] > needed.newtons) needed = { newtons: t[w], wire: w, capture: k };
    }
  });
  if (needed) {
    needed.name = sim.rim.names[needed.wire] || "#" + needed.wire;
    needed.label = captureLabel(sim.captures[needed.capture]);
  }
  const o = sim.options || {};
  const have = o.have_newtons == null ? null
    : { newtons: Number(o.have_newtons), limit: o.have_limit || null, part: o.have_part || null,
        mechanism: o.mechanism || null };
  const gap = needed && have
    ? { newtons: Math.abs(needed.newtons - have.newtons), missing: needed.newtons > have.newtons }
    : null;
  const last = sim.captures[sim.captures.length - 1];
  const worst = largestOf(last.deviation);
  const form = { mm: worst, tolerance: Number(tolerance), within: worst <= Number(tolerance) };
  const offsets = last.deviation || [];
  let sum = 0;
  for (let i = 0; i < offsets.length; i++) sum += offsets[i];
  const meanMm = offsets.length ? sum / offsets.length : 0;
  const mean = { mm: meanMm, within: meanMm <= Number(tolerance) };
  // the pull a tendon, the tendons and what they put into the column heads in
  // all (spec 2026-10-11 across tendons, section 5)
  const lines = sim.tendons ? sim.tendons.lines.length : 0;
  const pull = lines ? { newtons: sim.tendons.pull, tendons: lines, total: sim.tendons.pull * lines } : null;
  return { needed, have, gap, form, mean, trees: treesLoad(sim), pull };
}

// The tree member the run judges worst, at the capture it is worst: its
// force, N, what its tube takes there and the ratio; null with no trees.
function treesLoad(sim) {
  let worst = null;
  sim.captures.forEach((c, k) => {
    const u = c.treeUtilisation;
    for (let m = 0; u && m < u.length; m++) {
      if (!worst || u[m] > worst.utilisation) worst = { utilisation: u[m], member: m, capture: k };
    }
  });
  if (!worst) return null;
  const c = sim.captures[worst.capture];
  const [p, q] = sim.trees.members[worst.member];
  const length = Math.hypot(c.treeX[3 * q] - c.treeX[3 * p], c.treeX[3 * q + 1] - c.treeX[3 * p + 1],
                            c.treeX[3 * q + 2] - c.treeX[3 * p + 2]) * 1000;
  const n = c.treeAxial[worst.member] || 0;
  const wall = Number(sim.trees.wall);
  const capacity = length < FOLDED_MM || !(wall > 0) ? null
    : resistance(sim.trees.diameter, wall, length, n < 0);
  return { ...worst, newtons: Math.abs(n), capacity, label: captureLabel(c) };
}

// The mechanism as the answer names it: "23HS45-4204D-E1000 20:1".
function shortMechanism(mechanism) {
  if (!mechanism) return "";
  return mechanism.motor + (mechanism.ratio == null ? " direct" : " " + mechanism.ratio + ":1");
}

// The answer block (spec section 4.3): a row each, value then what it is;
// Needed's row carries its capture and wire, so a click goes there. Greyed
// (stale) while the run is out of date.
export function answerHtml(a, { stale = false } = {}) {
  if (!a) return "";
  // what falls short in deep red (his ask of 11 October 2026: no cross)
  const short = (text, bad) => (bad ? `<span class="over">${text}</span>` : text);
  const row = (name, value, note = "", attrs = "") =>
    `<tr${attrs}><th>${escapeHtml(name)}</th><td>${value}</td><td>${escapeHtml(note)}</td></tr>`;
  const rows = [];
  if (a.needed) {
    rows.push(row("Needed", grouped(a.needed.newtons),
                  "worst wire " + a.needed.name + ", at " + a.needed.label,
                  ` data-capture="${a.needed.capture}" data-wire="${a.needed.wire}"`));
  }
  rows.push(a.have ? row("Have", grouped(a.have.newtons), "one spool, " + shortMechanism(a.have.mechanism))
    : row("Have", "none"));
  if (a.gap) rows.push(row(a.gap.missing ? "Missing" : "Spare", short(grouped(a.gap.newtons), a.gap.missing)));
  rows.push(row("Worst offset", short(millimetres(a.form.mm), !a.form.within),
                "at the end, tolerance " + Number(a.form.tolerance) + " mm"));
  if (a.mean) rows.push(row("Mean offset", short(millimetres(a.mean.mm), !a.mean.within), "at the end"));
  if (a.trees) {
    rows.push(row("Trees load", short(grouped(a.trees.newtons), a.trees.utilisation > 1),
                  a.trees.capacity == null ? "worst member"
                    : "worst member, its tube takes " + grouped(a.trees.capacity)));
  }
  if (a.pull) {
    rows.push(row("Pull in", grouped(a.pull.newtons) + " a tendon",
                  a.pull.tendons + (a.pull.tendons === 1 ? " tendon, " : " tendons, ")
                  + grouped(a.pull.total) + " in all"));
  }
  return `<table class="answer${stale ? " stale" : ""}">` + rows.join("") + "</table>";
}

// ---------- the trees judged again for a new wall ----------
// trees.resistance, ported (spec 2026-10-11 section 7: a new wall is judged
// again from the run's own member forces, without a run): EN 1993-1-1 6.3.1,
// buckling curve a, S355, the member's own length as its buckling length.
const E_STEEL = 210000.0;
const FY_S355 = 355.0;
const ALPHA_CURVE_A = 0.21;
const FOLDED_MM = 1.0e-6;

function resistance(diameter, wall, length, compression) {
  const inner = diameter - 2 * wall;
  const area = Math.PI / 4 * (diameter ** 2 - inner ** 2);
  const plastic = area * FY_S355;
  if (!compression) return plastic;
  const inertia = Math.PI / 64 * (diameter ** 4 - inner ** 4);
  const critical = Math.PI ** 2 * E_STEEL * inertia / length ** 2;
  const slenderness = Math.sqrt(plastic / critical);
  const phi = 0.5 * (1 + ALPHA_CURVE_A * (slenderness - 0.2) + slenderness ** 2);
  return Math.min(1, 1 / (phi + Math.sqrt(phi ** 2 - slenderness ** 2))) * plastic;
}

// The run with its trees judged in a tube of this wall: each capture's
// utilisation from its members' forces and lengths, and the scale with them.
// The run read is left as it is.
export function withWall(sim, wall) {
  if (!sim) return sim;
  const diameter = sim.trees.diameter;
  const captures = sim.captures.map((c) => {
    const utilisation = new Float32Array(sim.trees.members.length);
    sim.trees.members.forEach(([p, q], k) => {
      const length = Math.hypot(c.treeX[3 * q] - c.treeX[3 * p], c.treeX[3 * q + 1] - c.treeX[3 * p + 1],
                                c.treeX[3 * q + 2] - c.treeX[3 * p + 2]) * 1000;
      const n = c.treeAxial[k] || 0;
      utilisation[k] = length < FOLDED_MM ? 0 : Math.abs(n) / resistance(diameter, wall, length, n < 0);
    });
    return { ...c, treeUtilisation: utilisation };
  });
  const scale = Math.max(0, ...captures.map((c) => largestOf(c.treeUtilisation)));
  return { ...sim, captures, trees: { ...sim.trees, wall }, scales: { ...sim.scales, utilisation: scale } };
}

// ---------- what a recorded frame carries ----------
// The Formwork tab's recording (the owner's choice of 10 October 2026): the
// page's labels, key and frame line are HTML, which never reach the canvas
// the recorder reads, so each frame is copied into a 2D canvas and these are
// drawn over it.

// The frame line on one line, the capture first.
export function recordingCaption(sim, index) {
  const line = frameLine(sim, index);
  if (!line) return "";
  return [captureLabel(sim.captures[index]), "Rope max " + kilonewtons(line.rope),
    "Wire max " + newtons(line.wire), "Trees " + line.trees.toFixed(2),
    "Deviation max " + millimetres(line.deviation),
    "Heads touching " + line.touching + "/" + line.heads,
    ...(line.tendons ? ["Pulling " + line.pulling + "/" + line.tendons, "At the stop " + line.atStop]
      : [])].join("   ");
}

const OVERLAY_INK = "#f2efe8";
const OVERLAY_GROUND = "rgba(20, 22, 26, 0.72)";

// Draw the caption along the top, each label standing on its point (x, y in
// the frame's pixels), and the key at the bottom right, sized from the page's
// own at 900 pixels high.
export function paintOverlay(ctx, { width, height, caption, labels, key }) {
  const s = height / 900;
  const px = (n) => Math.round(n * s);
  ctx.save();
  ctx.textBaseline = "middle";
  if (caption) {
    ctx.font = px(14) + "px sans-serif";
    const w = ctx.measureText(caption).width + 2 * px(8);
    ctx.fillStyle = OVERLAY_GROUND;
    ctx.fillRect(px(16), px(16), w, px(28));
    ctx.fillStyle = OVERLAY_INK;
    ctx.fillText(caption, px(24), px(30));
  }
  ctx.font = px(11) + "px sans-serif";
  for (const label of labels || []) {
    const w = ctx.measureText(label.text).width + 2 * px(4);
    const h = px(16);
    const x = label.x - w / 2;
    const y = label.y - h - px(6);
    ctx.fillStyle = OVERLAY_GROUND;
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = OVERLAY_INK;
    ctx.fillText(label.text, x + px(4), y + h / 2);
  }
  if (key) {
    const bw = px(220);
    const bh = px(74);
    const x0 = width - bw - px(16);
    const y0 = height - bh - px(16);
    const barX = x0 + px(10);
    const barW = bw - px(20);
    const barY = y0 + px(24);
    const barH = px(14);
    ctx.fillStyle = OVERLAY_GROUND;
    ctx.fillRect(x0, y0, bw, bh);
    ctx.fillStyle = OVERLAY_INK;
    ctx.font = px(12) + "px sans-serif";
    ctx.fillText(key.title, barX, y0 + px(14));
    const gradient = ctx.createLinearGradient(barX, 0, barX + barW, 0);
    RAMP_STOPS.forEach((stop, i) => gradient.addColorStop(i / (RAMP_STOPS.length - 1), stop));
    ctx.fillStyle = gradient;
    ctx.fillRect(barX, barY, barW, barH);
    // the limit marked at its place on the bar, when it is within the run
    if (key.limitText && key.fraction != null) {
      ctx.fillStyle = OVERLAY_INK;
      ctx.fillRect(barX + key.fraction * barW - px(1), barY - px(3), px(2), barH + px(6));
    }
    ctx.fillStyle = OVERLAY_INK;
    ctx.font = px(11) + "px sans-serif";
    ctx.fillText(key.min, barX, barY + barH + px(12));
    ctx.fillText(key.max, barX + barW - ctx.measureText(key.max).width, barY + barH + px(12));
    // and named on a line of its own under the ends, as the page's legend
    if (key.limitText) ctx.fillText(key.limitText, barX, barY + barH + px(27));
  }
  ctx.restore();
}

// The faces the skin has on it at a capture: every tiling quarter's up to it
// (spec section 8). An older run names none.
export function placedFaces(sim, index) {
  const out = [];
  if (!sim) return out;
  for (let k = 0; k <= index && k < sim.captures.length; k++) {
    for (const face of sim.captures[k].addedFaces || []) out.push(face);
  }
  return out;
}
