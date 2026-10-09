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

// The menu's three answers (spec 2026-10-09 Cable net display, section 3): the
// prestress the form needs (the run's floor until part 3 computes it), what the
// chosen machine gives its weakest wire, and the most any machine makes. Each
// null where nothing gives it.
export function menuAnswers(demand, row, strongest) {
  const floor = demand && !isStale(demand) ? wireFloor(demand).newtons : null;
  const worst = row && !row.refused && row.verdict ? row.verdict.worst : null;
  return {
    needed: floor,
    gives: worst ? { newtons: worst.ceiling, holds: !!row.verdict.holds, margin: worst.margin } : null,
    most: strongest ? { newtons: strongest.ceiling_newtons, described: strongest.described } : null,
  };
}

export function answersHtml(answers) {
  const gives = answers.gives;
  const rows = [
    ["Needed", answers.needed == null ? "not run" : newtons(answers.needed) + " N"],
    ["Gives", gives == null ? "no machine" : newtons(gives.newtons) + " N a wire " +
      mark(gives.holds) + (gives.margin == null ? "" : " " + factor(gives.margin) + "x")],
    ["Most", answers.most == null ? "none" : newtons(answers.most.newtons) + " N a wire, " +
      escapeHtml(answers.most.described)],
  ];
  return '<table class="cablenet-answers">' +
    rows.map(([name, value]) => `<tr><th>${name}</th><td>${value}</td></tr>`).join("") + "</table>";
}

// One line for each thing the run on screen differs from: the prestress dial,
// the tolerance dial, the chosen wire's stiffness. Plain text: the caller
// escapes it.
export function runWarnings(demand, dials, parts, rope) {
  if (!demand) return [];
  if (isStale(demand)) return ["Run again: older analysis, " + String(demand.schema || "unknown")];
  const out = [];
  const number = (value) => (value == null || value === "" ? NaN : Number(value));
  const usedPrestress = number(demand.prestress);
  const dialPrestress = number(dials && dials.prestress);
  if (Number.isFinite(usedPrestress) && Number.isFinite(dialPrestress) && usedPrestress !== dialPrestress) {
    out.push("Run again: dial " + newtons(dialPrestress) + " N, run " + newtons(usedPrestress) + " N");
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

export function machineHtml(row, parts) {
  if (!row) return "";
  if (row.refused) return `<p>${escapeHtml(row.refused)}</p>`;
  const c = row.configuration;
  const chain = (c.chain || []).map(escapeHtml).join(" + ");
  return `<p><b>${escapeHtml(row.described)}</b></p>` + table(["Part", "Value"], [
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
  const head = worst
    ? `<p><b>${mark(verdict.holds)} ${factor(worst.margin)}x</b> ${escapeHtml(worst.limit)}, ` +
      `${escapeHtml(worst.part)}, wire ${worst.wire}, pairing ${escapeHtml(verdict.pairing)}</p>`
    : `<p><b>${mark(verdict.holds)}</b> no tension</p>`;
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
  return `<p><b>${pounds(price.priced_gbp)}${floor ? " floor" : ""}</b>, ` +
    `${price.cabinets.cabinets.length} cabinets, exc VAT</p>` +
    table(["Part", "Count", "Unit", "Line"], study) +
    (first ? table(["Machine", "Motors", "Total", "Unpriced"], boxes) +
      `<p>Cabinet, machine 1: ${pounds(first.priced_gbp)}, ${first.unpriced} lines unpriced</p>` +
      table(["Part", "Count", "Rule", "Unit", "Line", "Supplier", "Quoted"], cabinet) : "");
}

export function recommendHtml(result) {
  if (!result) return "";
  if (result.holds) {
    return `<p><b>${escapeHtml(result.described)}</b>, ${pounds(result.priced_gbp)}, ` +
      `${escapeHtml(result.limit || "")} ${escapeHtml(result.part || "")} ` +
      `${result.margin == null ? "" : factor(result.margin) + "x"}` +
      `${result.confirm_run ? ", run to confirm" : ""}</p>`;
  }
  const c = result.closest;
  return `<p><b>none holds</b>${c ? `; closest ${escapeHtml(c.described)}, ` +
    `${escapeHtml(c.limit)} ${escapeHtml(c.part)} ${factor(c.margin)}x` : ""}</p>`;
}
