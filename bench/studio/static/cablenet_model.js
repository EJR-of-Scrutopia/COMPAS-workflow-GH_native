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
  return { known, whyUnknown, worst, allReachable, acceptance,
           holds: known && allReachable && withinLine };
}

// The greatest tension any wire carries: the sizing block's figure when the
// document has one, else the worst wire over the stages. Wires only, as the
// server reads the demand (_demand_floor in app.py, which decides whether a
// row passes) and as the exports do (_prestress_floor). The force a grabbed
// node's actuator supplies is another figure, said in a sentence of its own
// by demandSentences; folded in here it would be a number on the panel that
// no document agrees with, and a verdict that disagrees with the server's.
export function prestressFloor(demand) {
  const sizing = sizingOf(demand);
  if (sizing && sizing.worst_wire_tension_newtons != null) {
    return Number(sizing.worst_wire_tension_newtons);
  }
  let worst = 0;
  for (const stage of (demand && demand.stages) || []) {
    for (const tension of stage.wire_tensions || []) worst = Math.max(worst, tension);
  }
  return worst;
}

// Where the floor occurs: the first stage, in the document's order, whose own
// greatest wire tension is the floor, with whether it is a frame of the raise.
// It is not the sizing stage, which is chosen among the courses; the floor is
// the greatest over every instant, the raise included. Null when no stage
// carries it (a hand-edited document whose sizing block and stages disagree)
// or the stage has no name: an instant is named only when the document says
// which it is.
function floorInstant(demand, floor) {
  if (!(floor > 0)) return null;
  for (const stage of (demand && demand.stages) || []) {
    let top = null;
    for (const tension of stage.wire_tensions || []) {
      const value = Number(tension);
      if (Number.isFinite(value) && (top === null || value > top)) top = value;
    }
    if (top !== null && top === floor) {
      const name = stage.name == null ? stage.stage : stage.name;
      return name == null ? null : { name, frame: isFrame(stage) };
    }
  }
  return null;
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

// "1 wire", "2 wires", "2 batches": the noun agrees with the count
// (exports._count).
function counted(number, noun) {
  const plural = noun + (/(ch|sh|s|x|z)$/.test(noun) ? "es" : "s");
  return number + " " + (number === 1 ? noun : plural);
}

// A sentence of the server's own, as the exports write one: ended with a full
// stop when it has none (exports._sentence).
function sentenceOf(text) {
  const plain = String(text).trim();
  return /[.!?]$/.test(plain) ? plain : plain + ".";
}

// The demand, in sentences. They carry <b> tags the model writes itself, so
// every string the server supplied (the stage names, the acceptance source,
// the run's note, the schema) is escaped here, and the caller sets the result
// as markup without escaping it a second time.
export function demandSentences(demand) {
  if (!demand) {
    return ["This study has no cable net demand yet. Run the cable net analysis " +
            "and the figures below will have something to answer."];
  }
  if (isStale(demand)) {
    return ["This demand document is from an earlier analysis (" +
            esc(demand.schema || "unknown schema") + "). Run the cable net " +
            "analysis again for the lenses, the load factor and the grab count."];
  }
  const out = [];
  const sizing = sizingOf(demand);
  // the document names the stage twice, in the sizing block and at the top level
  const sizingStage = (sizing && sizing.stage) || demand.sizing_stage;
  const floor = prestressFloor(demand);
  const instant = floorInstant(demand, floor);
  const reached = !instant ? "" : (instant.frame
    ? ", reached at the raise's instant " : ", reached at stage ") + esc(instant.name);
  out.push("The greatest tension any wire carries is <b>" + newtons(floor) + " N</b>" +
    reached + ". That is a property of the vault and the skin, so it does not move " +
    "when parts change." +
    (sizingStage ? " The stage that sizes the parts is " + esc(sizingStage) + "." : ""));
  out.push(demand.acceptance == null
    ? "No acceptance line is set for this run, so sag has nothing to be judged against."
    : "The acceptance line is " + millimetres(demand.acceptance) + " mm" +
      (demand.acceptance_source ? ", from " + esc(demand.acceptance_source) : "") + ".");
  const courses = (demand.stages || []).filter((s) => !isFrame(s));
  const last = courses[courses.length - 1];
  if (last) {
    out.push("The skin weighs <b>" + kilonewtons(last.skin_load_sum_newtons) + " kN</b> placed" +
      (demand.thickness != null && demand.density != null
        ? ", " + Math.round(Number(demand.thickness) * 1000) + " mm at " +
          Math.round(Number(demand.density)) + " kg/m3" : "") +
      "; the net itself weighs " + kilonewtons(last.net_weight_newtons) + " kN.");
  }
  const held = demand.held || {};
  out.push("Held by " + counted((held.wire_nodes || []).length, "wire") + " and " +
    counted((held.column_heads || []).length, "column head") + ".");
  // The grabbed nodes' own figure, apart from the wires' floor above: it is
  // said when the document carries one above zero (exports._grab_section).
  const pull = sizing && sizing.worst_actuator_newtons != null
    ? Number(sizing.worst_actuator_newtons) : 0;
  if (Number.isFinite(pull) && pull > 0) {
    out.push("The grabbed nodes need up to " + newtons(pull) + " N each, " +
      "which a wire there would have to carry.");
  }
  const note = demand.note == null ? "" : String(demand.note).trim();
  if (note) out.push(esc(sentenceOf(note)));
  return out;
}

// The rope the analysis ran for, against the rope chosen here. The rope sets the
// stiffness the net was solved and cut for, so another rope leaves the ceiling
// (parts arithmetic) valid and quietly invalidates the prestress floor, the
// residuals and the cut lengths. It is said and not refused: trying another rope
// is how the choice is made. The test is exports._rope_mismatch's (both
// stiffnesses numbers, differing by more than a millionth of the larger), so the
// panel and the three documents warn in the same cases; the words are the
// panel's own. The sentence carries a <b> the model wrote, and the rope's key, a
// server string, is escaped. Empty when there is nothing to compare: no demand,
// no stiffness in it, a rope the catalogue does not have.
const EA_TOLERANCE = 1e-6;

export function ropeMismatch(parts, demand, configuration) {
  const key = configuration && configuration.rope;
  const chosen = (((parts && parts.rope) || {})[key] || {}).ea_newtons;
  const analysed = demand && demand.ea_newtons;
  const number = (value) => typeof value === "number" && Number.isFinite(value);
  if (!number(chosen) || !number(analysed)) return "";
  const larger = Math.max(Math.abs(chosen), Math.abs(analysed));
  if (Math.abs(chosen - analysed) <= EA_TOLERANCE * larger) return "";
  return "<b>The chosen rope is not the rope that was analysed.</b> The analysis used EA " +
    newtons(analysed) + " N; " + esc(key) + " is EA " + newtons(chosen) + " N. " +
    "The ceiling below is for the chosen rope. The prestress floor, the residuals and " +
    "the cut lengths are for the analysed rope and do not describe this one.";
}

// Whether the prestress dial still matches the analysis on screen. The document
// records the prestress it was run with; the dial is only the next run's, so
// when they differ the panel says which of the two the figures came from.
export function prestressNote(demand, dialNewtons) {
  if (!demand || demand.prestress == null) return "";
  const used = Number(demand.prestress);
  const dial = Number(dialNewtons);
  if (!Number.isFinite(used) || !Number.isFinite(dial) || used === dial) return "";
  return "The analysis on screen used a prestress of <b>" + newtons(used) + " N</b>; the dial reads " +
    newtons(dial) + " N. Run again to use the dial's value.";
}

// The skin, with its weight in kilonewtons when the sizing block gave one:
// an unknown weight is left out of the sentence, never written as zero
// (exports._skin_words).
function skinWords(capacity) {
  const weight = capacity.skin_newtons;
  if (typeof weight !== "number" || !Number.isFinite(weight)) return "skin";
  return kilonewtons(weight) + " kN skin";
}

// What stops the factor rising, as a clause that follows "before"
// (exports._binder).
function binder(capacity) {
  const part = capacity.binding_part || capacity.binding;
  if (part === "shape") {
    return "the shape binds, because the net sags past the acceptance line at any load";
  }
  return String(part) + " binds";
}

// The same sentence exports.load_factor_sentence renders, word for word, so the
// panel and the documents agree in words as well as numbers. The two share no
// code; test_cablenet_model.py puts them side by side.
export function loadFactorText(capacity) {
  if (!capacity || capacity.limit_factor == null) {
    const why = (capacity && capacity.detail) ||
      "the demand document has no sizing block; run the cable net analysis again";
    return "Whether it carries the skin is not established: " +
      String(why).replace(/\.+$/, "") + ".";
  }
  const skin = skinWords(capacity);
  const times = factor(capacity.limit_factor);
  if (capacity.binding === "none") {
    // the walk ran to its end with nothing past a limit: a floor, not a ceiling
    return "Carries at least " + times + " times the " + skin +
      ": nothing binds up to that load.";
  }
  if (capacity.sufficient) {
    return "Carries " + times + " times the " + skin + " before " + binder(capacity) + ".";
  }
  return "Carries only " + times + " times the " + skin +
    ", so it does not hold the skin: " + binder(capacity) + ".";
}

// Holding is three questions now: does the system carry the skin, can the
// parts carry the tension, and does the net keep its shape. The weight leads.
export function verdictOf({ row, floor, shape, capacity }) {
  if (!row || row.refused) {
    return { headline: row ? String(row.refused) : "No answer.", reasons: [] };
  }
  const reasons = [loadFactorText(capacity)];
  const path = row.rope_path || null;
  if (!(floor > 0)) {
    return { headline: "No demand to compare against yet.", reasons };
  }
  const carries = row.ceiling >= floor;
  const pathOk = !path || (path.drum_fits && path.rail_fits);
  const weightFails = !!capacity && capacity.sufficient === false;
  const shapeFails = !!shape && shape.known && !shape.holds;
  const shapeUnknown = !shape || !shape.known;
  const weightUnknown = !capacity || capacity.limit_factor == null;
  let headline;
  if (!carries || !pathOk || shapeFails || weightFails) headline = "It does not hold.";
  else if (shapeUnknown || weightUnknown) headline = "Whether it holds has not been established.";
  else headline = "It holds.";
  reasons.push(carries
    ? "The parts can carry the tension: the ceiling is " + newtons(row.ceiling) +
      " N, set by " + String(row.binding) + (row.margin == null ? "" :
      ", " + Number(row.margin).toFixed(2) + " times the demand") + "."
    : "The parts cannot carry the tension: the ceiling is " + newtons(row.ceiling) +
      " N against " + newtons(floor) + " N demanded.");
  if (path && !path.drum_fits) {
    reasons.push("The rope does not fit the drum in one layer (" +
      path.rope_wound_mm.toFixed(0) + " mm against " + path.drum_capacity_mm.toFixed(0) +
      " mm). A second layer changes the effective radius, so every torque figure here would be wrong.");
  }
  if (path && !path.rail_fits) {
    reasons.push("The carriage would travel " + path.carriage_travel_mm.toFixed(0) +
      " mm but the rail's stroke is " + path.rail_stroke_mm.toFixed(0) + " mm.");
  }
  if (shape && shape.known && shape.worst) {
    const line = shape.acceptance == null ? "no acceptance line set"
      : millimetres(shape.acceptance) + " mm acceptance line";
    if (!shape.holds) {
      reasons.push("The net misses the shape by " + millimetres(shape.worst.residual) +
        " mm at stage " + String(shape.worst.name) + " against a " + line +
        (shape.allReachable ? "" : " and at least one stage cannot be corrected at all") +
        ". This comes from the vault, the wires and the prestress, so no change of parts here will cure it.");
    } else {
      reasons.push("The net stays within the shape: the worst miss is " +
        millimetres(shape.worst.residual) + " mm against a " + line + ".");
    }
  } else if (shape && !shape.known) {
    reasons.push("Whether the net keeps its shape has not been established, because " +
      String(shape.whyUnknown) + ".");
  } else {
    reasons.push("Whether the net keeps its shape has not been established.");
  }
  return { headline, reasons };
}

export function configurationLabel(entry) {
  return entry && entry.name ? String(entry.name) : "unnamed configuration";
}

function sameValue(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    return Array.isArray(a) && Array.isArray(b) && a.length === b.length &&
      a.every((v, i) => v === b[i]);
  }
  return (a == null ? null : a) === (b == null ? null : b);
}

// Whether the current parts differ from the named configuration's. Every key
// the configuration carries is compared, the chain as a list.
export function modifiedFrom(key, current, configurations) {
  const entry = configurations && configurations[key];
  if (!entry || !current) return false;
  const parts = entry.parts || {};
  const keys = new Set([...Object.keys(parts), ...Object.keys(current)]);
  for (const k of keys) {
    if (!sameValue(parts[k], current[k])) return true;
  }
  return false;
}

export function fallbackKey(remembered, configurations) {
  const keys = Object.keys(configurations || {});
  if (!keys.length) return { key: null, note: "The catalogue has no configurations." };
  if (remembered && configurations[remembered]) return { key: remembered, note: null };
  const first = keys[0];
  return {
    key: first,
    note: remembered
      ? "The remembered system \"" + String(remembered) + "\" is no longer in the " +
        "catalogue; showing " + configurationLabel(configurations[first]) + "."
      : null,
  };
}

export function stageCaption(stage) {
  if (!stage) return "";
  if (isFrame(stage)) {
    return "Frame at machine time " + Number(stage.time) + " (" + String(stage.kind) +
      "): the net's own weight only.";
  }
  const placed = kilonewtons(stage.skin_load_sum_newtons) + " kN placed.";
  // an older document carries no course number to count, and none is invented
  if (stage.course == null) return "Stage " + String(stage.name) + ": " + placed;
  return "Course " + (Number(stage.course) + 1) + " of the skin (" + String(stage.name) +
    "): " + placed;
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

// A sag with its unit, or the words that say it is missing: never "not
// recorded mm" (exports._mm_text).
function sagText(value) {
  return value == null ? "not recorded" : millimetres(value) + " mm";
}

// The same sentence exports.grab_sentence renders, word for word: how many
// nodes to grab, in how many batches (the last may be short), and whether
// grabbing them brings the net inside the line. A document that names no held
// set has not said that none are held, so it is not read as an empty one.
export function grabText(placement, held, acceptance) {
  if (!placement) {
    return "Where to grab the net is not established: the demand document has no " +
      "placement; run the cable net analysis again.";
  }
  const nodes = held && Array.isArray(held.actuators) ? held.actuators : null;
  if (nodes === null) {
    return "Where to grab the net is not established: the demand document has no " +
      "held set; run the cable net analysis again.";
  }
  const count = nodes.length;
  const batch = Math.max(1, Math.trunc(Number(placement.batch)) || 1);
  const batches = count ? Math.ceil(count / batch) : 0;
  // the last batch is short when the count is not a multiple of the size
  const how = counted(batches, "batch") + " of " + (count % batch ? "up to " : "") + batch;
  const line = acceptance == null ? "a line nobody set" : "the " + millimetres(acceptance) + " mm line";
  const curve = placement.curve || [];
  const none = curve.length ? sagText(curve[0].worst_sag_mm) : "not recorded";
  const last = curve.length ? sagText(curve[curve.length - 1].worst_sag_mm) : "not recorded";
  const method = "The placement is greedy by unbalanced force, a heuristic and not an optimum.";
  if (placement.reached) {
    if (!count) {
      return "No node needs grabbing: with none grabbed the worst sag is " + none +
        ", already inside " + line + ".";
    }
    return "Grab " + counted(count, "node") + " (" + how + ") to bring the net inside " +
      line + "; the worst sag with none grabbed is " + none + ". " + method;
  }
  return "Grabbing " + counted(count, "node") + " (" + how + ") did not reach the line: " +
    "the worst sag is still " + last + " against " + line + ", from " + none +
    " with none grabbed. " + method;
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

// What is settled is said, not offered.
export function settledText(drive) {
  return "Settled: the drive is " + String(drive || "the motor's own") +
    ", which follows the motor; the drum is the workshop's 72 mm grooved drum and the " +
    "rail the MGN15H-300. The controller, the single board computer, the power " +
    "supply, the amplifiers and the terminals carry no mechanical load and change no " +
    "number on this panel.";
}

// Annotation only: a number and its unit, never a comparison.
export function rpmText(speed, row) {
  const rpm = row && !row.refused ? row.motor_rpm_for_wanted_speed : null;
  return rpm == null ? speed + " mm/s"
    : speed + " mm/s is " + rpm.toFixed(0) + " rpm at the motor with this gearbox and drum";
}
