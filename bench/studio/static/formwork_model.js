// The Formwork tab's model (spec 2026-10-10 formwork tab): the capture
// document the formwork engine writes, read into typed arrays, and the
// player's clock over it. Pure: no page and no three.js, so it runs under node
// in the tests. formwork.js wires it to the page, formwork_view.js draws it.

import { escapeHtml, forceLabel } from "./cablenet_model.js";

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

// The frame line (spec section 9): the largest rope, wire, tree and deviation
// at the capture, and how many heads touch their nodes.
export function frameLine(sim, index) {
  const c = sim && sim.captures[index];
  if (!c) return null;
  const heads = sim.trees.heads.length;
  let touching = 0;
  for (let h = 0; h < heads; h++) if (pushOf(c, h) > 0) touching += 1;
  return { rope: largestOf(c.tension), wire: largestOf(c.wireTension),
           trees: largestOf(c.treeUtilisation), deviation: largestOf(c.deviation), touching, heads };
}

export function frameLineHtml(line) {
  if (!line) return "";
  return keyed([["Rope max", kilonewtons(line.rope)], ["Wire max", newtons(line.wire)],
    ["Trees", line.trees.toFixed(2)], ["Deviation max", millimetres(line.deviation)],
    ["Heads touching", line.touching + "/" + line.heads]]);
}

export const COLOUR_BY = [["tension", "Rope tension"], ["deviation", "Deviation"],
  ["utilisation", "Tree utilisation"], ["wire", "Wire tension"], ["off", "Off"]];

// The two ends of the studio's one-sided ramp (#legend.deflection's bar), and
// the deviation bands in the colours the Sag lens draws them.
const RAMP_LOW = [0xf2, 0xef, 0xe8];
const RAMP_HIGH = [0xcc, 0x22, 0x11];
const DEVIATION_COLOURS = { within: "#f2efe8", near: "#c99a2e", over: "#c24936" };

function hexRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export function ramp(fraction) {
  const f = Math.min(1, Math.max(0, Number(fraction) || 0));
  return RAMP_LOW.map((low, i) => (low + (RAMP_HIGH[i] - low) * f) / 255);
}

// A deviation's band against the tolerance, as the Sag lens bands a sag: over
// it, near it (over half of it), or within it.
export function deviationBand(mm, tolerance) {
  if (Number(mm) > tolerance) return "over";
  if (Number(mm) > 0.5 * tolerance) return "near";
  return "within";
}

// The colour a value is drawn in under a Colour by choice, [r, g, b] from 0 to
// 1, on the run's own scale; null where the choice colours nothing (Off).
export function colourOf(by, value, sim, tolerance) {
  if (!sim || value == null) return null;
  if (by === "tension") return ramp(sim.scales.tension > 0 ? value / sim.scales.tension : 0);
  if (by === "wire") return ramp(sim.scales.wire > 0 ? value / sim.scales.wire : 0);
  // full red at the tube's capacity and over it
  if (by === "utilisation") return ramp(value);
  if (by === "deviation") return hexRgb(DEVIATION_COLOURS[deviationBand(value, tolerance)]);
  return null;
}

// The key a Colour by choice draws, in the legend's own shape (lensLegend's).
export function colourKey(by, sim, tolerance) {
  if (!sim) return null;
  if (by === "tension") {
    return { title: "rope tension, kN", min: "0", max: (sim.scales.tension / 1000).toFixed(1) };
  }
  if (by === "wire") return { title: "wire tension, N", min: "0", max: sim.scales.wire.toFixed(0) };
  if (by === "utilisation") return { title: "tree utilisation", min: "0", max: "1.0" };
  if (by === "deviation") {
    return { title: "deviation, mm: tolerance " + Number(tolerance), min: "0",
             max: sim.scales.deviation.toFixed(0),
             bands: ["within", "near", "over"].map((name) => ({ name, colour: DEVIATION_COLOURS[name] })) };
  }
  return null;
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

export const LABEL_KINDS = [["rope", "Rope"], ["deviation", "Deviation"], ["contact", "Contact"]];

function largestIndices(values, count) {
  const found = [];
  if (!values) return found;
  for (let i = 0; i < values.length; i++) if (values[i] > 0) found.push(i);
  found.sort((a, b) => values[b] - values[a] || a - b);
  return found.slice(0, count);
}

// The labels a capture puts on the model for the ticked kinds, each kind's
// largest first, so where they crowd the largest is the one kept: rope kN at a
// member, deviation mm at a node, the push of each head touching its node.
export function formworkLabels(sim, index, kinds, count = 20) {
  const c = sim && sim.captures[index];
  if (!c) return [];
  const out = [];
  if (kinds.includes("rope")) {
    for (const i of largestIndices(c.tension, count)) {
      out.push({ kind: "member", index: i, text: kilonewtons(c.tension[i]) });
    }
  }
  if (kinds.includes("deviation")) {
    for (const i of largestIndices(c.deviation, count)) {
      out.push({ kind: "node", index: i, text: millimetres(c.deviation[i]) });
    }
  }
  if (kinds.includes("contact")) {
    const push = sim.trees.heads.map((_, h) => pushOf(c, h));
    for (const h of largestIndices(push, count)) {
      out.push({ kind: "node", index: sim.trees.heads[h][0], text: newtons(push[h]) });
    }
  }
  return out;
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
  const members = [];
  sim.edges.forEach(([u, v], e) => {
    if (u === node || v === node) {
      members.push(`<tr><td>${u === node ? v : u}</td><td>${forceLabel(c.tension[e])}</td></tr>`);
    }
  });
  return keyed(rows) + (members.length
    ? "<table><tr><th>To node</th><th>Tension</th></tr>" + members.join("") + "</table>" : "");
}

// The machine as a warning names it: its wire, wires a motor and pulleys.
function machineName(options) {
  return (options.rope || "no wire") + ", " + (options.wires_per_motor || 1) + " a motor, "
    + (options.pulleys === false ? "no pulleys" : "pulleys");
}

// One line each (spec section 11): no run yet, an older run, and the run's
// machine, prestress or wall not the chosen ones. chosen: the Cable net tab's
// rope, wires_per_motor and pulleys, the Wall dial, and the cable net run's
// design prestress (null when there is none).
export function formworkWarnings(sim, chosen) {
  if (!sim) return ["No formwork run: Run formwork analysis"];
  const out = [];
  if (sim.older) out.push("Run again: older formwork run");
  const ran = sim.options || {};
  if (!chosen) return out;
  if (machineName(chosen) !== machineName(ran)) {
    out.push("Run again: machine " + machineName(chosen) + ", run " + machineName(ran));
  }
  if (chosen.prestress != null && ran.prestress != null
      && Math.abs(chosen.prestress - ran.prestress) > 0.01 * ran.prestress) {
    out.push("Run again: prestress " + Number(chosen.prestress).toFixed(1) + " N, run "
      + Number(ran.prestress).toFixed(1) + " N");
  }
  if (chosen.wall != null && ran.wall != null
      && Number(chosen.wall).toFixed(1) !== Number(ran.wall).toFixed(1)) {
    out.push("Run again: wall " + Number(chosen.wall).toFixed(1) + " mm, run "
      + Number(ran.wall).toFixed(1) + " mm");
  }
  return out;
}

// ---------- the worst tables ----------

export const WORST_PARTS = [["ropes", "Ropes"], ["wires", "Wires"], ["trees", "Trees"],
  ["nodes", "Nodes"], ["machines", "Machines"]];
export const WORST_ROWS = 50;

// Each element's largest value over every capture, and the first capture it
// reaches it at.
function worstOver(sim, field) {
  const best = [];
  sim.captures.forEach((c, k) => {
    const values = c[field];
    if (!values) return;
    for (let i = 0; i < values.length; i++) {
      if (best[i] == null || values[i] > best[i].value) best[i] = { index: i, value: values[i], capture: k };
    }
  });
  return best.filter(Boolean);
}

function worstFirst(rows) {
  return rows.sort((a, b) => b.value - a.value || a.index - b.index).slice(0, WORST_ROWS);
}

// The worst tables (spec section 10): each part's worst over the whole
// sequence with the capture it happens at, the WORST_ROWS worst of each. A
// machine's worst is its worst wire's.
export function worstTables(sim) {
  if (!sim) return null;
  const wires = worstOver(sim, "wireTension").map((row) => ({
    ...row, node: sim.rim.nodes[row.index], name: sim.rim.names[row.index] || "#" + row.index }));
  const machines = sim.rim.machines.map((nodes, m) => {
    let worst = null;
    for (const node of nodes) {
      const row = wires.find((r) => r.node === node);
      if (row && (!worst || row.value > worst.value)) {
        worst = { index: m, value: row.value, capture: row.capture, wire: row.name };
      }
    }
    return worst;
  }).filter(Boolean);
  return { ropes: worstFirst(worstOver(sim, "tension")), wires: worstFirst(wires),
           trees: worstFirst(worstOver(sim, "treeUtilisation")),
           nodes: worstFirst(worstOver(sim, "deviation")), machines: worstFirst(machines) };
}

export function sortRows(rows, key, descending) {
  const sign = descending ? -1 : 1;
  return [...rows].sort((a, b) => sign * (a[key] - b[key]) || a.index - b.index);
}

const WORST_COLUMNS = {
  ropes: [["index", "Member"], ["value", "kN"], ["capture", "Capture"]],
  wires: [["index", "Wire"], ["value", "N"], ["capture", "Capture"]],
  trees: [["index", "Member"], ["value", "Utilisation"], ["capture", "Capture"]],
  nodes: [["index", "Node"], ["value", "mm"], ["capture", "Capture"]],
  machines: [["index", "Machine"], ["value", "Worst wire, N"], ["capture", "Capture"]],
};
const WORST_KIND = { ropes: "member", wires: "wire", trees: "tree", nodes: "node", machines: "machine" };

function worstCell(part, key, row, sim) {
  if (key === "capture") return escapeHtml(captureLabel(sim.captures[row.capture]));
  if (key === "index") {
    if (part === "wires") return escapeHtml(row.name);
    if (part === "machines") return "M" + (row.index + 1);
    return String(row.index);
  }
  if (part === "ropes") return (row.value / 1000).toFixed(1);
  if (part === "trees") return row.value.toFixed(2);
  if (part === "nodes") return row.value >= 10 ? row.value.toFixed(0) : row.value.toFixed(1);
  return row.value.toFixed(0);
}

// A worst table: a header a column, which sorts (the sorted one marked); a row
// a part, carrying its capture and the part to turn the camera onto.
export function worstHtml(part, rows, sim, sort = { key: "value", descending: true }) {
  const columns = WORST_COLUMNS[part];
  if (!columns || !sim) return "";
  const head = columns.map(([key, name]) => `<th data-sort="${key}"`
    + (key === sort.key ? ` class="sorted ${sort.descending ? "down" : "up"}"` : "")
    + `>${escapeHtml(name)}</th>`).join("");
  const body = sortRows(rows || [], sort.key, sort.descending).map((row) =>
    `<tr data-capture="${row.capture}" data-kind="${WORST_KIND[part]}" data-index="${row.index}">`
    + columns.map(([key]) => `<td>${worstCell(part, key, row, sim)}</td>`).join("") + "</tr>").join("");
  return `<table class="worst"><tr>${head}</tr>${body}</table>`;
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
