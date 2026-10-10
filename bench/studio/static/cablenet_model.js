// The cable net section's judgement and words, pure: plain data in, strings
// and small structures out, no DOM and no three.js, so every sentence the
// panel says runs under node (tests/studio/test_cablenet_model.py) the way
// data_analysis.js and live_graphs.js do. cablenet.js owns the wiring and
// studio.js owns the lenses; neither decides anything this file could.

// The one way the panel writes a force. It is exports._newtons in Python: one
// decimal, no grouping, so "1471.0 N" reads the same on screen and in all
// three documents. Never round a force to whole newtons here: a fractional
// ceiling just under the floor would then read "1471 N against 1471 N".
export function newtons(value) {
  return value == null ? "not recorded" : Number(value).toFixed(1);
}

export function millimetres(value) {
  return value == null ? "not recorded" : Number(value).toFixed(2);
}

export function kilonewtons(value) {
  return value == null ? "not recorded" : (Number(value) / 1000).toFixed(1);
}

export function factor(value) {
  return value == null ? "not established" : Number(value).toFixed(1);
}

export const SCHEMA = "bench.cablenet/2";

export function isStale(demand) {
  return !!demand && demand.schema !== SCHEMA;
}

export function sizingOf(demand) {
  return demand && demand.sizing && typeof demand.sizing === "object" ? demand.sizing : null;
}

// A frame of the raise: an instant with a machine time and no course. The net
// is slack by design while the formwork is raised, so a frame is shown by the
// lenses and judged by nothing. Everything else is a course, and that includes
// a stage with neither key, which comes from a document written before frames
// existed. A course is told by "is not null" and never by truth, because the
// first course is course 0. This is exports._is_frame_instant, read the same.
function isFrame(stage) {
  return stage.course == null && stage.time != null;
}

// Whether the net keeps its shape. Deviation is a property of the vault, the
// wires and the prestress; the chosen parts cannot move it. Three states, the
// same as the exported documents: it holds, it fails, or it is NOT
// ESTABLISHED. Absence of evidence is never a pass. Only the courses of the
// skin are judged: a frame of the raise enters neither the worst residual,
// nor the reachable test, nor the verdict (exports._shape_verdict).
export function shapeOf(demand) {
  const stages = (demand && demand.stages) || [];
  let worst = null;
  let allReachable = true;
  for (const stage of stages) {
    if (isFrame(stage)) continue;
    if (stage.reachable === false) allReachable = false;
    const residual = Number(stage.residual_after);
    if (stage.residual_after != null && Number.isFinite(residual) &&
        (worst === null || residual > worst.residual)) {
      worst = { residual, name: stage.name == null ? stage.stage : stage.name };
    }
  }
  const acceptance = !demand || demand.acceptance == null ? null : Number(demand.acceptance);
  let whyUnknown = null;
  if (!allReachable) {
    whyUnknown = null;
  } else if (stages.length === 0) {
    whyUnknown = "the demand has no stages, so no residual was measured";
  } else if (worst === null) {
    whyUnknown = "no stage records a residual after correction, so nothing was measured";
  } else if (acceptance === null) {
    whyUnknown = "no acceptance line is set, so the residual has nothing to be judged against";
  }
  const known = whyUnknown === null;
  const withinLine = worst !== null && acceptance !== null && worst.residual <= acceptance;
  // A version 2 residual is the sag with the grabbed nodes held, and a stage
  // is unreachable when that sag stays past the line; the first version's was
  // what its wires could not correct (exports._shape_verdict).
  const grabbed = !!demand && demand.schema === SCHEMA;
  return { known, whyUnknown, worst, allReachable, acceptance, grabbed,
           holds: known && allReachable && withinLine };
}

// A finite number, else null: a boolean, a string, a null and a NaN are not a
// force to any reader of the floor (catalogue._force).
function force(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function listed(value) {
  return Array.isArray(value) ? value : [];
}

// The tension every wire is judged at, and the two figures it is the larger
// of: { newtons, fitted, prestress }, each null when the document does not
// give it. This is catalogue.wire_floor, read the same way, and the server's
// row, the load factor and the three documents all read that. The engine's
// sizing block carries all three: worst_wire_tension_newtons is the larger of
// the entered prestress and the greatest tension the fit found in any wire,
// and the two are beside it. A document written before the block carried the
// two is read by the same rule from what it does carry (the block's one figure
// is the fit's, or the wires stage by stage when there is no block), with the
// prestress it records. Wires only: the force a grabbed node's actuator
// supplies is another figure, shown on its own; folded in here it would be a
// number on the panel that no document agrees with, and a verdict that
// disagrees with the server's.
export function wireFloor(demand) {
  const sizing = sizingOf(demand);
  const judged = sizing ? force(sizing.worst_wire_tension_newtons) : null;
  if (judged !== null && Object.prototype.hasOwnProperty.call(sizing, "fitted_wire_tension_newtons")) {
    return { newtons: judged, fitted: force(sizing.fitted_wire_tension_newtons),
             prestress: force(sizing.prestress_newtons) };
  }
  let fitted = judged;
  if (fitted === null) {
    for (const stage of listed(demand && demand.stages)) {
      if (!stage || typeof stage !== "object") continue;
      for (const tension of listed(stage.wire_tensions)) {
        const value = force(tension);
        if (value !== null && (fitted === null || value > fitted)) fitted = value;
      }
    }
  }
  const prestress = force(demand && typeof demand === "object" ? demand.prestress : null);
  const known = [prestress, fitted].filter((value) => value !== null);
  return { newtons: known.length ? Math.max(...known) : null, fitted, prestress };
}

// The floor as one figure for the verdict: 0 when the document gives none.
export function prestressFloor(demand) {
  const floor = wireFloor(demand).newtons;
  return floor === null ? 0 : floor;
}

// Total rope one wire winds over the whole build, taken at the worst wire.
export function ropeWound(demand) {
  const totals = [];
  for (const stage of (demand && demand.stages) || []) {
    (stage.wire_reel_commands || []).forEach((command, wire) => {
      totals[wire] = (totals[wire] || 0) + Math.abs(Number(command) || 0);
    });
  }
  return totals.length ? Math.max(...totals) : null;
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// The wire the analysis ran for, against the wire chosen here, by stiffness: the
// test is exports._rope_mismatch's (both numbers, differing by more than a
// millionth of the larger), so the panel and the documents warn in the same
// cases. Null when there is nothing to compare.
const EA_TOLERANCE = 1e-6;

export function eaMismatch(parts, demand, rope) {
  const chosen = (((parts && parts.rope) || {})[rope] || {}).ea_newtons;
  const analysed = demand && demand.ea_newtons;
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  if (!number(chosen) || !number(analysed)) return null;
  const larger = Math.max(Math.abs(chosen), Math.abs(analysed));
  if (Math.abs(chosen - analysed) <= EA_TOLERANCE * larger) return null;
  return { analysed, chosen };
}

// The prestress the form needs (spec 2026-10-10 prestress and holds) -------

// The needs table of a current document, or null.
function needsOf(demand) {
  const needs = demand && !isStale(demand) ? demand.needs : null;
  return needs && Array.isArray(needs.steps) && needs.steps.length ? needs : null;
}

// The nodes a machine of this ceiling needs held: the fewest steps of the walk
// whose prestress the ceiling covers, every node those steps added, and the
// prestress it is then set to. A ceiling no step meets holds the whole walk
// at the ceiling, not covered. Null with no table or no ceiling.
export function holdsFor(demand, ceiling) {
  const needs = needsOf(demand);
  if (!needs || ceiling == null || !Number.isFinite(Number(ceiling))) return null;
  const c = Number(ceiling);
  const steps = needs.steps;
  const at = steps.findIndex((s) => s.prestress_newtons != null && s.prestress_newtons <= c);
  const step = at < 0 ? steps.length - 1 : at;
  const nodes = steps.slice(1, step + 1).flatMap((s) => s.added || []);
  return { step, count: nodes.length, nodes, covered: at >= 0,
           prestress: at < 0 ? c : steps[at].prestress_newtons };
}

// A figure of the ladder at a prestress: straight across between two rungs in
// the logarithm of the prestress, the end's own figure beyond either end.
function ladderAt(demand, prestress, key) {
  const needs = needsOf(demand);
  const ladder = needs && Array.isArray(needs.ladder) ? needs.ladder : [];
  if (!ladder.length || prestress == null || !(Number(prestress) > 0)) return null;
  const p = Number(prestress);
  const first = ladder[0], last = ladder[ladder.length - 1];
  if (p <= first.prestress_newtons) return first[key];
  if (p >= last.prestress_newtons) return last[key];
  const i = ladder.findIndex((r, k) => k + 1 < ladder.length && ladder[k + 1].prestress_newtons > p);
  const a = ladder[i], b = ladder[i + 1];
  const t = Math.log(p / a.prestress_newtons) / Math.log(b.prestress_newtons / a.prestress_newtons);
  return a[key] + t * (b[key] - a[key]);
}

// The worst sag, mm, with the column heads alone at this prestress.
export function sagAt(demand, prestress) {
  return ladderAt(demand, prestress, "worst_sag_mm");
}

// The factor on the load that keeps the net within the line at this prestress.
export function roofAt(demand, prestress) {
  return ladderAt(demand, prestress, "roof");
}

// The menu's answers (spec 2026-10-10 prestress and holds, section 5): the
// prestress the form needs with its column heads alone, what the chosen
// machine gives a wire and the most any machine makes, each marked against it,
// the nodes the chosen machine needs held and why, and the roof its ceiling
// gives. Each null where nothing gives it.
export function menuAnswers(demand, row, strongest) {
  const needs = needsOf(demand);
  const worst = row && !row.refused && row.verdict ? row.verdict.worst : null;
  const needed = needs ? needs.steps[0].prestress_newtons : null;
  const known = needed != null;
  const most = strongest ? { newtons: strongest.ceiling_newtons, described: strongest.described,
                             holds: known ? strongest.ceiling_newtons >= needed : null } : null;
  const gives = worst ? { newtons: worst.ceiling, holds: known ? worst.ceiling >= needed : null,
                          margin: known ? worst.ceiling / needed : null } : null;
  const held = gives && needs ? holdsFor(demand, worst.ceiling) : null;
  return {
    needed: needs ? { newtons: needed } : null,
    gives,
    most,
    holds: held ? { count: held.count, covered: held.covered,
                    reason: held.count === 0 ? null : most && most.holds ? "machine" : "every machine" }
      : null,
    roof: gives && needs ? roofAt(demand, worst.ceiling) : null,
  };
}

export function answersHtml(answers) {
  const gives = answers.gives;
  const marked = (answer) => (answer.holds == null ? "" : " " + mark(answer.holds));
  const holds = answers.holds;
  const missing = answers.needed == null ? "not run" : "no machine";
  const rows = [
    ["Needed", answers.needed == null ? "not run"
      : answers.needed.newtons == null ? "more than 1 MN" : newtons(answers.needed.newtons) + " N"],
    ["Gives", gives == null ? "no machine" : newtons(gives.newtons) + " N a wire" + marked(gives) +
      (gives.margin == null ? "" : " " + factor(gives.margin) + "x")],
    ["Most", answers.most == null ? "none" : newtons(answers.most.newtons) + " N a wire" +
      marked(answers.most) + ", " + escapeHtml(answers.most.described)],
    ["Holds", holds == null ? missing : holds.count === 0 && holds.covered ? "none"
      : (holds.covered ? "" : "more than ") + holds.count + " nodes, " +
        (holds.reason === "machine" ? "this machine short" : "every machine short")],
    ["Roof", answers.roof == null ? missing : factor(answers.roof) + "x the skin"],
  ];
  return '<table class="cablenet-answers">' +
    rows.map(([name, value]) => `<tr><th>${name}</th><td>${value}</td></tr>`).join("") + "</table>";
}

// One line for each thing the run on screen differs from: the machine it was
// designed for, the tolerance dial, the chosen wire's stiffness. Plain text:
// the caller escapes it.
export function runWarnings(demand, dials, parts, rope) {
  if (!demand) return [];
  if (isStale(demand)) return ["Run again: older analysis, " + String(demand.schema || "unknown")];
  if (!needsOf(demand)) return ["Run again: older analysis, no prestress table"];
  const out = [];
  const number = (value) => (value == null || value === "" ? NaN : Number(value));
  const chosen = number(dials && dials.ceiling);
  const designed = number(demand.needs.ceiling_newtons);
  if (Number.isFinite(chosen) && (!Number.isFinite(designed) ||
      Math.abs(chosen - designed) > 0.01 * Math.max(chosen, designed))) {
    out.push("Run again: machine " + newtons(chosen) + " N, run " +
      (Number.isFinite(designed) ? newtons(designed) + " N" : "no machine"));
  }
  const usedTolerance = number(demand.tolerance_mm);
  const dialTolerance = number(dials && dials.tolerance);
  if (Number.isFinite(usedTolerance) && Number.isFinite(dialTolerance) && usedTolerance !== dialTolerance) {
    out.push("Run again: tolerance " + millimetres(dialTolerance) + " mm, run " +
      millimetres(usedTolerance) + " mm");
  }
  const ea = eaMismatch(parts, demand, rope);
  if (ea) out.push("Run again: wire EA " + newtons(ea.chosen) + " N, run " + newtons(ea.analysed) + " N");
  return out;
}

// The instant on screen as data: "F60 finish, t 60", "S2 tile, course 2, 12.0 kN".
export function stageCaption(stage) {
  if (!stage) return "";
  const name = String(stage.name == null ? stage.stage : stage.name) +
    (stage.kind ? " " + String(stage.kind) : "");
  if (isFrame(stage)) return name + ", t " + Number(stage.time);
  const placed = kilonewtons(stage.skin_load_sum_newtons) + " kN";
  // an older document carries no course number to count, and none is invented
  if (stage.course == null) return name + ", " + placed;
  return name + ", course " + (Number(stage.course) + 1) + ", " + placed;
}

export function nearestInstant(stages, machineTime) {
  let best = null;
  for (const stage of stages || []) {
    if (!isFrame(stage)) continue;
    if (best === null || Math.abs(stage.time - machineTime) < Math.abs(best.time - machineTime)) {
      best = stage;
    }
  }
  return best;
}

export function courseInstant(stages, index) {
  const courses = (stages || []).filter((s) => !isFrame(s));
  if (!courses.length) return null;
  if (index == null) return courses[courses.length - 1];
  const at = Math.max(0, Math.min(courses.length - 1, index));
  return courses[at];
}

// Which computed instant the timeline is at: the nearest frame during the
// formwork act, the course during the build, clamped at both ends; the
// other kind when the document has only one; null for an empty document.
export function instantAt(stages, { duringFormwork, machineTime, courseIndex }) {
  if (!stages || !stages.length) return null;
  if (duringFormwork) {
    return nearestInstant(stages, machineTime) || courseInstant(stages, 0);
  }
  return courseInstant(stages, courseIndex) || nearestInstant(stages, 100);
}

export function sagBand(mm, acceptance) {
  if (mm == null || acceptance == null) return "unknown";
  if (mm > acceptance) return "over";
  if (mm > 0.5 * acceptance) return "near";
  return "inside";
}

// The walk as inline SVG: grabbed nodes along the bottom, worst sag up the
// side on a log scale (a 2 m sag and a 2 mm line on one axis), the line dashed.
export function curveSvg(points, acceptance, width = 240, height = 72) {
  const rows = (points || []).filter((p) => p && Number.isFinite(p.worst_sag_mm));
  if (!rows.length) return "";
  const pad = { left: 28, right: 6, top: 6, bottom: 14 };
  const xs = rows.map((p) => Number(p.count));
  const ys = rows.map((p) => Math.max(0.01, Number(p.worst_sag_mm)));
  const xMax = Math.max(1, ...xs);
  let yMin = Math.min(...ys), yMax = Math.max(...ys);
  if (acceptance != null) { yMin = Math.min(yMin, acceptance); yMax = Math.max(yMax, acceptance); }
  if (yMax <= yMin) yMax = yMin * 10;
  const lx = (x) => pad.left + (x / xMax) * (width - pad.left - pad.right);
  const ly = (y) => pad.top + (1 - (Math.log10(y) - Math.log10(yMin)) /
    (Math.log10(yMax) - Math.log10(yMin))) * (height - pad.top - pad.bottom);
  const path = rows.map((p, i) => (i ? "L" : "M") + lx(Number(p.count)).toFixed(1) + " " +
    ly(Math.max(0.01, Number(p.worst_sag_mm))).toFixed(1)).join(" ");
  const line = acceptance == null ? "" :
    '<line class="line" x1="' + pad.left + '" y1="' + ly(acceptance).toFixed(1) +
    '" x2="' + (width - pad.right) + '" y2="' + ly(acceptance).toFixed(1) + '"/>';
  return '<svg class="cablenet-curve" viewBox="0 0 ' + width + " " + height +
    '" role="img" aria-label="worst sag against nodes grabbed">' +
    '<line class="axis" x1="' + pad.left + '" y1="' + (height - pad.bottom) + '" x2="' +
    (width - pad.right) + '" y2="' + (height - pad.bottom) + '"/>' +
    '<path class="walk" d="' + path + '"/>' + line +
    '<text x="' + pad.left + '" y="' + (height - 3) + '">0</text>' +
    '<text x="' + (width - pad.right) + '" y="' + (height - 3) + '" text-anchor="end">' +
    esc(xMax) + " nodes</text>" +
    '<text x="2" y="' + (pad.top + 8) + '">' + esc(millimetres(yMax)) + "</text>" +
    '<text x="2" y="' + (height - pad.bottom) + '">' + esc(millimetres(yMin)) + "</text>" +
    "</svg>";
}

// The lenses (spec 2026-10-09 Cable net display, section 5) ----------------

// A force as a label on the model: short, with its unit.
export function forceLabel(value) {
  if (value == null || !Number.isFinite(Number(value))) return "";
  const n = Number(value);
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + " kN";
  return (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1)) + " N";
}

// A wire's tension against the chosen machine's ceiling: within up to 0.6 of
// it, near below it, over above it; plain with no ceiling or no tension.
export function prestressBand(tension, ceiling) {
  if (tension == null || ceiling == null) return "plain";
  if (tension > ceiling) return "over";
  if (tension > 0.6 * ceiling) return "near";
  return "within";
}

// Each wire's reel commands summed from the first stage to the instant on
// screen, mm: negative reeled in, positive paid out. Zeros with no instant.
export function reelSoFar(stages, stage) {
  const list = stages || [];
  const width = Math.max(0, ...list.map((s) => (s.wire_reel_commands || []).length));
  const sums = new Array(width).fill(0);
  const at = stage ? list.indexOf(stage) : -1;
  for (let i = 0; i <= at; i += 1) {
    (list[i].wire_reel_commands || []).forEach((command, w) => {
      const value = Number(command);
      if (Number.isFinite(value)) sums[w] += value;
    });
  }
  return sums.map((value) => Math.round(value * 1e9) / 1e9);
}

// One decimal, and never a signed zero: -0.04 reads 0.0, not -0.0.
function oneDecimal(value) {
  const rounded = Math.round(Number(value) * 10) / 10;
  return (rounded === 0 ? 0 : rounded).toFixed(1);
}

export function reelSide(mm) {
  if (mm == null || !(Number(mm) !== 0)) return "still";
  return Number(mm) < 0 ? "in" : "out";
}

function largest(values, count) {
  return values.map((value, index) => ({ value, index }))
    .filter((item) => item.value != null && item.value > 0)
    .sort((a, b) => b.value - a.value || a.index - b.index)
    .slice(0, count);
}

// The points a lens labels, with their text: every machine wire at its rim node
// under Prestress and Reel, the largest node forces under Node force, the
// largest member tensions under Wire tension. Sag labels nothing.
// The largest first: where the wires crowd together, spreadLabels keeps the
// first of a crowd, so the one shown is the largest.
function largestFirst(rows) {
  return rows.map((row, at) => ({ row, at }))
    .sort((a, b) => Math.abs(b.row.value) - Math.abs(a.row.value) || a.at - b.at)
    .map(({ row }) => row.target);
}

export function labelTargets(lens, demand, stage, ceiling, count = 20) {
  if (!stage || !demand) return [];
  const wires = demand.wires || [];
  if (lens === "prestress") {
    const rows = [];
    (stage.wire_tensions || []).forEach((tension, index) => {
      if (tension == null || !wires[index]) return;
      rows.push({ value: Number(tension), target: { kind: "wire", index, node: wires[index].net_vertex,
        text: forceLabel(tension), band: prestressBand(tension, ceiling) } });
    });
    return largestFirst(rows);
  }
  if (lens === "reel") {
    // the side read from the figure shown, so a wire that reads 0.0 is still
    return largestFirst(reelSoFar(demand.stages, stage).map((mm, index) => (!wires[index] ? null : {
      value: mm, target: { kind: "wire", index, node: wires[index].net_vertex,
        text: oneDecimal(mm) + " mm", side: reelSide(Number(oneDecimal(mm))) } })).filter(Boolean));
  }
  if (lens === "nodeforce") {
    return largest((stage.node_residual || []).map(magnitude), count)
      .map(({ value, index }) => ({ kind: "node", index, text: forceLabel(value) }));
  }
  if (lens === "tension") {
    return largest((stage.member_tensions || []).map((v) => (v == null ? null : Number(v))), count)
      .map(({ value, index }) => ({ kind: "member", index, text: forceLabel(value) }));
  }
  return [];
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

// The colours the banded lenses draw their arrows in (studio.js
// updateCableNetVectors), which their legends key: within, near and over the
// machine's ceiling, none scored; rope taken in and paid out.
const BAND_COLOURS = { within: "#3f9e57", near: "#c99a2e", over: "#c24936", plain: "#9aa4b2",
                       in: "#66aaff", out: "#c99a2e" };

// The legend a lens draws: its quantity and unit, and its range at the
// instant. Wire tension and Sag keep the legends they draw today: null.
export function lensLegend(lens, demand, stage, ceiling) {
  if (!stage) return null;
  if (lens === "nodeforce") {
    const top = finiteMax((stage.node_residual || []).map(magnitude));
    return { title: "node force, N", min: "0", max: top == null ? "0" : newtons(top) };
  }
  if (lens === "prestress") {
    const top = finiteMax(stage.wire_tensions);
    return { title: "wire tension, N" + (ceiling == null ? "" : ": within / near / over " + newtons(ceiling)),
             min: "0", max: top == null ? "0" : newtons(top),
             bands: ceiling == null ? [{ name: "no machine", colour: BAND_COLOURS.plain }]
               : ["within", "near", "over"].map((name) => ({ name, colour: BAND_COLOURS[name] })) };
  }
  if (lens === "reel") {
    const sums = reelSoFar(demand && demand.stages, stage);
    return { title: "reel, mm: in / out", min: oneDecimal(Math.min(0, ...sums)),
             max: oneDecimal(Math.max(0, ...sums)),
             bands: [{ name: "in", colour: BAND_COLOURS.in }, { name: "out", colour: BAND_COLOURS.out }] };
  }
  return null;
}

// The card a click on a node opens (spec section 5.3): the node, its force and
// its sag, held or grabbed; for a wire's rim node also the wire, its tension,
// its own ceiling and margin from the scored row, and its reel so far.
export function pickHtml(demand, stage, node, verdict) {
  if (!demand || !stage || node == null) return "";
  const residual = (stage.node_residual || [])[node];
  const sag = (stage.node_sag_mm || [])[node];
  // a held node (a wire's or a column's) has no sag of its own; its force is
  // the support's, not an unbalanced one
  const held = Array.isArray(stage.node_sag_mm) ? sag == null : residual == null;
  const rows = [
    ["Node", String(node)],
    ["Force", held ? "held" : newtons(magnitude(residual || [0, 0, 0])) + " N"],
    ["Sag", held || sag == null ? "held" : millimetres(sag) + " mm"],
  ];
  if (((demand.held || {}).actuators || []).includes(node)) rows.push(["Grabbed", "yes"]);
  const wire = (demand.wires || []).findIndex((item) => item && item.net_vertex === node);
  if (wire >= 0) {
    const tension = (stage.wire_tensions || [])[wire];
    rows.push(["Wire", String(demand.wires[wire].name)],
              ["Tension", tension == null ? "not recorded" : newtons(tension) + " N"]);
    const own = verdict && verdict.wires ? verdict.wires[wire] : null;
    if (own) {
      rows.push(["Ceiling", newtons(own.ceiling) + " N"],
                ["Margin", own.margin == null ? "" : factor(own.margin) + "x"]);
    }
    rows.push(["Reel", (reelSoFar(demand.stages, stage)[wire] || 0).toFixed(1) + " mm"]);
  }
  return "<table>" + rows.map(([name, value]) =>
    `<tr><th>${name}</th><td>${escapeHtml(value)}</td></tr>`).join("") + "</table>";
}

// The Graphs tab (spec 2026-10-09 Cable net display, section 4.3) ---------

function finiteMax(values) {
  let top = null;
  for (const value of values || []) {
    if (typeof value === "number" && Number.isFinite(value) && (top === null || value > top)) top = value;
  }
  return top;
}

function magnitude(vector) {
  if (!Array.isArray(vector) || vector.length !== 3) return null;
  const parts = vector.map(Number);
  return parts.every(Number.isFinite) ? Math.hypot(...parts) : null;
}

// Each stage's worst wire tension (N), worst sag (mm) and worst node force
// (N, the size of a node's unbalanced force), in the run's order; null where a
// stage records none.
export function stageSeries(demand) {
  const stages = (demand && !isStale(demand) && demand.stages) || [];
  return stages.map((stage) => ({
    name: String(stage.name == null ? stage.stage : stage.name),
    tension: finiteMax(stage.wire_tensions),
    sag: finiteMax(stage.node_sag_mm),
    force: finiteMax((stage.node_residual || []).map(magnitude)),
  }));
}

// One series as inline SVG: the stages along the bottom, the value up the side
// from zero, the line (a ceiling or the tolerance) dashed. Empty when the
// series has no value at all.
export function stageSvg(series, key, line, width = 240, height = 72) {
  const values = (series || []).map((point) => point[key]);
  const known = values.filter((value) => value != null);
  if (!known.length) return "";
  const text = key === "sag" ? millimetres : newtons;
  const pad = { left: 40, right: 6, top: 6, bottom: 14 };
  let top = Math.max(...known);
  if (line != null && Number.isFinite(Number(line))) top = Math.max(top, Number(line));
  if (!(top > 0)) top = 1;
  const span = Math.max(1, values.length - 1);
  const lx = (i) => pad.left + (i / span) * (width - pad.left - pad.right);
  const ly = (y) => pad.top + (1 - y / top) * (height - pad.top - pad.bottom);
  let path = "";
  values.forEach((value, i) => {
    if (value == null) return;
    path += (path ? "L" : "M") + lx(i).toFixed(1) + " " + ly(value).toFixed(1) + " ";
  });
  const dashed = line == null || !Number.isFinite(Number(line)) ? "" :
    '<line class="line" x1="' + pad.left + '" y1="' + ly(Number(line)).toFixed(1) +
    '" x2="' + (width - pad.right) + '" y2="' + ly(Number(line)).toFixed(1) + '"/>';
  const first = series[0].name;
  const last = series[series.length - 1].name;
  return '<svg class="cablenet-graph-svg" viewBox="0 0 ' + width + " " + height +
    '" role="img">' +
    '<line class="axis" x1="' + pad.left + '" y1="' + (height - pad.bottom) + '" x2="' +
    (width - pad.right) + '" y2="' + (height - pad.bottom) + '"/>' +
    '<path class="series" d="' + path.trim() + '"/>' + dashed +
    '<text x="2" y="' + (pad.top + 8) + '">' + esc(text(top)) + "</text>" +
    '<text x="2" y="' + (height - pad.bottom) + '">0</text>' +
    '<text x="' + pad.left + '" y="' + (height - 3) + '">' + esc(first) + "</text>" +
    '<text x="' + (width - pad.right) + '" y="' + (height - 3) + '" text-anchor="end">' +
    esc(last) + "</text></svg>";
}

// The net in numbers, as rows of [name, value].
export function netRows(demand) {
  const sizing = sizingOf(demand) || {};
  const held = (demand && demand.held) || {};
  const courses = ((demand && demand.stages) || []).filter((s) => !isFrame(s));
  // the last course that records the figure: a course with none hides nothing
  const lastOf = (key) => [...courses].reverse().find((s) => s[key] != null) || {};
  const last = { skin_load_sum_newtons: lastOf("skin_load_sum_newtons").skin_load_sum_newtons,
                 net_weight_newtons: lastOf("net_weight_newtons").net_weight_newtons };
  const tolerance = demand && (demand.tolerance_mm != null ? demand.tolerance_mm : demand.acceptance);
  const count = (list) => String((list || []).length);
  const stage = sizing.stage || (demand && demand.sizing_stage);
  return [
    ["Floor", newtons(wireFloor(demand).newtons) + (wireFloor(demand).newtons == null ? "" : " N")],
    ["Tolerance", tolerance == null ? "not recorded" : millimetres(tolerance) + " mm"],
    ["Skin", last.skin_load_sum_newtons == null ? "not recorded" : kilonewtons(last.skin_load_sum_newtons) + " kN"],
    ["Net", last.net_weight_newtons == null ? "not recorded" : kilonewtons(last.net_weight_newtons) + " kN"],
    ["Wires", count(held.wire_nodes)],
    ["Column heads", count(held.column_heads)],
    ["Grabbed nodes", count(held.actuators)],
    ["Largest grabbed pull", sizing.worst_actuator_newtons == null ? "not recorded"
      : newtons(sizing.worst_actuator_newtons) + " N"],
    ["Worst sag", sizing.worst_sag_mm == null ? "not recorded" : millimetres(sizing.worst_sag_mm) + " mm"],
    ["Sizing stage", stage == null ? "not recorded" : String(stage)],
  ];
}

export function netHtml(demand) {
  return '<table class="cablenet-net">' + netRows(demand).map(([name, value]) =>
    `<tr><th>${name}</th><td>${esc(value)}</td></tr>`).join("") + "</table>";
}

// The whole tab: three graphs stage by stage, the walk, and the net.
export function graphsHtml(demand, ceiling) {
  if (!demand || isStale(demand)) return "";
  const series = stageSeries(demand);
  const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
  const graphs = [
    ["Worst wire tension, N", stageSvg(series, "tension", ceiling)],
    ["Worst sag, mm", stageSvg(series, "sag", acceptance)],
    ["Worst node force, N", stageSvg(series, "force", null)],
    ["Sag against nodes grabbed, mm", demand.placement ? curveSvg(demand.placement.curve, acceptance) : ""],
    ["Prestress needed against nodes held, N", needsOf(demand) ? stageSvg(
      needsOf(demand).steps.map((s) => ({ name: String(s.count), prestress: s.prestress_newtons })),
      "prestress", ceiling) : ""],
  ];
  return graphs.filter(([, svg]) => svg).map(([title, svg]) =>
    `<div class="cablenet-graph"><div class="cablenet-graph-title">${title}</div>${svg}</div>`).join("") +
    netHtml(demand);
}

// Annotation only: a number and its unit, never a comparison.
export function rpmText(speed, row) {
  const rpm = row && !row.refused ? row.motor_rpm_for_wanted_speed : null;
  return rpm == null ? speed + " mm/s" : speed + " mm/s, " + rpm.toFixed(0) + " rpm at the motor";
}

// ---------------------------------------------------------------------------
// The five choices (spec 2026-10-09 mechanism choices, sections 2 and 7.3).
// The panel is a tool, not a text: numbers with their units, marks, tables and
// part names; no sentence says why.
// ---------------------------------------------------------------------------

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

export function pounds(value) {
  return value == null ? "no price" : "£" + Number(value).toFixed(2);
}

export function mark(holds) {
  return holds ? "✓" : "✗";
}

function ratioLabel(ratio) {
  return ratio == null ? "none" : Number(ratio).toFixed(0) + ":1";
}

// What each select offers, from the server's choices block (GET /api/catalogue):
// a ratio only if the motor's frame offers it, a pulley only if it takes the wire.
export function choiceOptions(options, parts, choices) {
  const motors = options.motors.map((m) => ({
    value: m.key, label: `${m.key}, ${Number(m.torque_nm)} N m ${m.torque_basis}` }));
  const ratios = (options.ratios[choices.motor] || []).map((r) => ({
    value: r.ratio, label: ratioLabel(r.ratio) }));
  const ropes = options.ropes.map((r) => ({
    value: r.key, label: `${Number(r.diameter_mm)} mm ${r.construction || ""} ${r.material || ""}`.trim() }));
  const pulleys = [{ value: null, label: "none" }].concat(
    (options.pulleys[choices.rope] || []).map((key) => ({
      value: key, label: (parts.sheave[key] && (parts.sheave[key].name || parts.sheave[key].model)) || key })));
  const wires = options.wires_per_motor.map((n) => ({ value: n, label: String(n) }));
  return { motor: motors, ratio: ratios, rope: ropes, pulley: pulleys, wires_per_motor: wires };
}

// Choices the catalogue can build: each kept where it is still offered, else
// the first that is (a rated ratio before none, the export's reeving before
// none, one wire a motor).
export function validChoices(options, choices) {
  const c = { ...(choices || {}) };
  const motors = options.motors.map((m) => m.key);
  if (!motors.includes(c.motor)) c.motor = motors[0];
  const ratios = (options.ratios[c.motor] || []).map((r) => r.ratio);
  if (!ratios.some((r) => r === c.ratio)) {
    c.ratio = ratios.find((r) => r != null) ?? null;
  }
  const ropes = options.ropes.map((r) => r.key);
  if (!ropes.includes(c.rope)) c.rope = ropes.includes("rope-4mm") ? "rope-4mm" : ropes[0];
  const pulleys = options.pulleys[c.rope] || [];
  if (c.pulley !== null && !pulleys.includes(c.pulley)) c.pulley = pulleys[0] ?? null;
  if (!options.wires_per_motor.includes(c.wires_per_motor)) c.wires_per_motor = 1;
  return c;
}

function table(head, rows) {
  return "<table><tr>" + head.map((h) => `<th>${escapeHtml(h)}</th>`).join("") + "</tr>" +
    rows.map((r) => "<tr>" + r.map((cell) => `<td>${cell}</td>`).join("") + "</tr>").join("") +
    "</table>";
}

// A readout of named values, one row each: the pop-up's headline figures
// (spec 2026-10-09 Cable net display, section 8: tables, never a paragraph).
// Each value comes escaped by its caller.
function keyed(rows) {
  return "<table>" + rows.map(([name, value]) =>
    `<tr><th>${escapeHtml(name)}</th><td>${value}</td></tr>`).join("") + "</table>";
}

// The chosen machine's limits a wire, N, each with its part; the one that
// binds is marked (spec 2026-10-09 Cable net display, section 4.1).
const TERM_NAMES = { "rope tension": "Wire", anchor: "Anchor chain", "spool rope tension": "Spool rope",
                     sheave: "Pulleys", "gearbox torque": "Gearbox", "motor torque": "Motor" };

export function limitsHtml(terms) {
  if (!terms || !terms.length) return "";
  return table(["Limit", "N a wire", "Part", ""], terms.map((term) => [
    escapeHtml(TERM_NAMES[term.name] || term.name), newtons(term.newtons),
    escapeHtml(term.part == null ? "" : term.part), term.binds ? "binds" : ""]));
}

// Every motor at the other choices: one row each, the chosen one marked, a row
// a click chooses.
export function motorsHtml(rows, chosen, demand) {
  const head = ["Motor", "Ratio", "N a wire", "Margin", "", "Price", "Holds", "Sag, mm"];
  const body = (rows || []).map((row) => {
    const choice = row.choices || {};
    const motor = escapeHtml(choice.motor);
    const open = `<tr data-motor="${motor}"${choice.motor === chosen ? ' class="chosen"' : ""}>`;
    if (row.refused) return open + `<td>${motor}</td><td colspan="7">${escapeHtml(row.refused)}</td></tr>`;
    const worst = row.verdict && row.verdict.worst;
    // what this motor's ceiling needs held, and the sag it leaves with the
    // column heads alone: what a change of motor does to the accuracy
    const held = worst ? holdsFor(demand, worst.ceiling) : null;
    const sag = worst ? sagAt(demand, worst.ceiling) : null;
    const cells = [motor, ratioLabel(choice.ratio), worst ? newtons(worst.ceiling) : "",
                   worst && worst.margin != null ? factor(worst.margin) + "x" : "",
                   mark(row.verdict && row.verdict.holds),
                   row.price ? pounds(row.price.priced_gbp) : "",
                   held == null ? "" : held.count === 0 && held.covered ? "none"
                     : (held.covered ? "" : "more than ") + held.count,
                   sag == null ? "" : millimetres(sag)];
    return open + cells.map((cell) => `<td>${cell}</td>`).join("") + "</tr>";
  });
  return "<table><tr>" + head.map((h) => `<th>${h}</th>`).join("") + "</tr>" + body.join("") + "</table>";
}

export function eyeBoltHtml(angle) {
  return `<table><tr><th>Eye bolt angle</th><td>${Number(angle).toFixed(0)}°, assumed</td></tr></table>`;
}

export function machineHtml(row, parts) {
  if (!row) return "";
  if (row.refused) return `<div class="cablenet-warning">${escapeHtml(row.refused)}</div>`;
  const c = row.configuration;
  const chain = (c.chain || []).map(escapeHtml).join(" + ");
  return table(["Part", "Value"], [
    ["Machine", escapeHtml(row.described)],
    ["Driver", escapeHtml(c.drive)],
    ["Gearbox", escapeHtml(c.gearbox)],
    ["Pulleys", c.sheave == null ? "none, 1 fall" : `${escapeHtml(c.sheave)}, ${c.reeve_factor} falls`],
    ["Anchor chain", chain],
    ["Winding radius", `${millimetres(c.winding_radius_mm)} mm`],
    ["Groove pitch", `${millimetres(c.groove_pitch_mm)} mm`],
    ["Wires a motor", String(c.wires_per_motor)],
  ]);
}

export function verdictHtml(verdict) {
  if (!verdict) return "";
  const worst = verdict.worst;
  const head = keyed(worst
    ? [["Holds", mark(verdict.holds)], ["Margin", factor(worst.margin) + "x"],
       ["Limit", escapeHtml(worst.limit)], ["Part", escapeHtml(worst.part)],
       ["Worst wire", String(worst.wire)], ["Pairing", escapeHtml(verdict.pairing)]]
    : [["Holds", mark(verdict.holds)], ["Tension", "none"]]);
  const rows = verdict.machines.map((m) => {
    const w = verdict.wires[m.worst_wire];
    return [String(m.machine + 1), String(m.worst_wire), newtons(w.tension),
            m.margin == null ? "" : factor(m.margin), escapeHtml(m.limit), escapeHtml(m.part),
            mark(m.holds)];
  });
  return head + table(["Machine", "Worst wire", "Tension, N", "Margin", "Limit", "Part", ""], rows);
}

export function travelHtml(travel) {
  if (!travel) return "";
  const drum = travel.worst_drum;
  const carriage = travel.worst_carriage;
  const most = Math.max(0, ...travel.wires.map((w) => w.in_and_out_mm));
  return table(["Check", "Value", "Limit", ""], [
    ["Rope on drum, mm", millimetres(drum && drum.drum_rope_mm), millimetres(drum && drum.drum_capacity_mm),
     mark(!drum || drum.drum_fits)],
    ["Carriage, mm", millimetres(carriage && carriage.carriage_mm), millimetres(carriage && carriage.stroke_mm),
     mark(!carriage || carriage.rail_fits)],
    ["In and out, mm", millimetres(most), "", ""],
    ["Drum D/d", factor(travel.drum_over_rope), "", ""],
    ["Pulley D/d", travel.pulley_over_rope == null ? "" : factor(travel.pulley_over_rope), "", ""],
  ]);
}

export function buyHtml(price, cuts) {
  if (!price || !price.rope) return "";
  const lengths = (cuts || []).map((c) => c.length_mm / 1000);
  const floor = (cuts || []).some((c) => c.is_floor) || price.rope.is_floor;
  const best = price.rope.best;
  const bought = best == null ? "no price"
    : `${escapeHtml(best.buy)}${best.reels ? `, ${best.reels} reels` : ""}, ${pounds(best.cost_gbp)}`;
  return table(["Wire", "Value"], [
    ["Total, m", millimetres(price.rope.total_m) + (floor ? " (floor)" : "")],
    ["Cut lengths, m", lengths.length ? `${millimetres(Math.min(...lengths))} to ${millimetres(Math.max(...lengths))}` : ""],
    ["Bought", bought],
  ]);
}

// Who quoted a line, linked to its page when the source is one, else with the
// source as the cell's title (spec section 5.5).
function sourced(line) {
  const who = escapeHtml(line.supplier || "");
  const source = line.source ? String(line.source) : "";
  if (/^https?:\/\//.test(source)) {
    return `<a href="${escapeHtml(source)}" target="_blank" rel="noopener">${who || "source"}</a>`;
  }
  return source ? `<span title="${escapeHtml(source)}">${who}</span>` : who;
}

export function priceHtml(price) {
  if (!price) return "";
  const floor = price.unpriced.length > 0 || price.cabinet_unpriced > 0;
  const study = price.lines.map((l) => [escapeHtml(l.part), String(l.count), pounds(l.unit_gbp),
                                       pounds(l.line_gbp)]);
  const first = price.cabinets.cabinets[0];
  const cabinet = first ? first.lines.map((l) => [escapeHtml(l.model), String(l.count),
    escapeHtml(l.rule), pounds(l.unit_gbp), l.in_total ? pounds(l.line_gbp) : "not in total",
    sourced(l), escapeHtml(l.quoted || "")]) : [];
  const boxes = price.cabinets.cabinets.map((c, i) => [String(i + 1), String(c.motors),
    pounds(c.priced_gbp), String(c.unpriced)]);
  return keyed([["Study total", pounds(price.priced_gbp) + (floor ? " floor" : "")],
                 ["Cabinets", String(price.cabinets.cabinets.length)], ["VAT", "excluded"]]) +
    table(["Part", "Count", "Unit", "Line"], study) +
    (first ? table(["Machine", "Motors", "Total", "Unpriced"], boxes) +
      keyed([["Cabinet, machine 1", pounds(first.priced_gbp)],
             ["Unpriced lines", String(first.unpriced)]]) +
      table(["Part", "Count", "Rule", "Unit", "Line", "Supplier", "Quoted"], cabinet) : "");
}

export function recommendHtml(result) {
  if (!result) return "";
  const binds = (pick) => escapeHtml([pick.limit, pick.part].filter(Boolean).join(", "));
  if (result.holds) {
    return keyed([["Pick", escapeHtml(result.described)], ["Price", pounds(result.priced_gbp)],
                  ["Binds", binds(result)],
                  ["Margin", result.margin == null ? "" : factor(result.margin) + "x"],
                  ...(result.confirm_run ? [["Run to confirm", "yes"]] : [])]);
  }
  const c = result.closest;
  return keyed([["Pick", "none holds"], ...(c ? [["Closest", escapeHtml(c.described)],
    ["Binds", binds(c)], ["Margin", factor(c.margin) + "x"]] : [])]);
}
