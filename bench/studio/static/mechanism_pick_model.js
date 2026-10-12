// The mechanism pop-up's model (spec 2026-10-11 one Cable net tab, section
// 8.1): which whole mechanism is chosen, the dropdown's options, and the three
// lines under it. Pure: no page, so it runs under node in the tests.
// mechanism_pick.js wires it to the page.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function newtons(n) {
  return Math.round(Number(n)).toLocaleString("en-GB") + " N";
}

function millimetres(n) {
  return Math.round(Number(n)).toLocaleString("en-GB") + " mm";
}

// The part's kind, as Limited by names it after the part.
const LIMIT_NAMES = {
  "rope tension": "rope", "anchor": "anchor chain", "spool rope tension": "spool rope",
  "sheave": "pulleys", "gearbox torque": "gearbox", "motor torque": "motor",
};

// Where the study's mechanisms are read: at its wires a motor, and held to the
// rope it wears when one is named (Param, 2026-10-12: the wire on screen is
// the wire the run is made with).
export function mechanismsUrl(study, wiresPerMotor, rope) {
  const base = `/api/studies/${encodeURIComponent(study)}/mechanisms?wires_per_motor=${wiresPerMotor}`;
  return rope ? `${base}&rope=${encodeURIComponent(rope)}` : base;
}

// ---------- the mechanism built by hand ----------
// Param, 2026-10-12: "this mechanisms tab i also want to be able to create my
// own mechanism, choose whether there is pulley or not should just be a toggle
// on this pop up too". options: every mechanism the machine can be built as
// for the wire chosen (machine.options), each motor, ratio and pulley or none.

// The stronger of two: the more pull, and among equals the stronger drive.
function stronger(a, b) {
  return a.have_newtons > b.have_newtons
    || (a.have_newtons === b.have_newtons && (a.drive_newtons || 0) > (b.drive_newtons || 0));
}

// A ratio as a dropdown value and back: direct drive has none.
export function ratioKey(ratio) {
  return ratio === null || ratio === undefined ? "direct" : String(ratio);
}

export function ratioFromKey(key) {
  return key === "direct" ? null : Number(key);
}

// The option built: wanted is { motor, ratio, pulley } (pulley null with
// Pulleys off), or a study's motor alone as it was remembered before he could
// build his own. What the motor cannot make falls to its strongest: a ratio it
// has not, its strongest ratio; a pulley no longer offered with Pulleys on,
// the strongest pulley there. Nothing wanted: the strongest of all. -1 for
// none.
export function builderPick(options, wanted) {
  if (!Array.isArray(options) || !options.length) return -1;
  const want = typeof wanted === "string" ? { motor: wanted } : (wanted || {});
  const best = (indices) => indices.reduce(
    (found, i) => (found < 0 || stronger(options[i], options[found]) ? i : found), -1);
  const all = options.map((_, i) => i);
  const mine = all.filter((i) => options[i].choices.motor === want.motor);
  if (!mine.length) return best(all);
  const geared = "ratio" in want ? mine.filter((i) => options[i].choices.ratio === want.ratio) : [];
  if (!geared.length) return best(mine);
  if (want.pulley === null) {
    const off = geared.find((i) => options[i].choices.pulley === null);
    return off !== undefined ? off : best(geared);
  }
  const exact = geared.find((i) => options[i].choices.pulley === want.pulley);
  if (exact !== undefined) return exact;
  const on = geared.filter((i) => options[i].choices.pulley !== null);
  return best(on.length ? on : geared);
}

function unique(values) {
  return values.filter((value, i) => values.indexOf(value) === i);
}

function option(value, label, selected) {
  return `<option value="${esc(value)}"${selected ? " selected" : ""}>${esc(label)}</option>`;
}

export function motorOptionsHtml(options, motor) {
  return unique(options.map((entry) => entry.choices.motor))
    .map((key) => option(key, key, key === motor)).join("");
}

export function ratioOptionsHtml(options, motor, ratio) {
  const mine = options.filter((entry) => entry.choices.motor === motor);
  const keys = unique(mine.map((entry) => ratioKey(entry.choices.ratio)));
  return keys.map((key) => {
    const entry = mine.find((one) => ratioKey(one.choices.ratio) === key);
    return option(key, entry.ratio_label, key === ratioKey(ratio));
  }).join("");
}

function geared(options, motor, ratio) {
  return options.filter((entry) => entry.choices.motor === motor
    && ratioKey(entry.choices.ratio) === ratioKey(ratio) && entry.choices.pulley !== null);
}

export function pulleyOptionsHtml(options, motor, ratio, pulley) {
  return geared(options, motor, ratio)
    .map((entry) => option(entry.choices.pulley, entry.pulley_label, entry.choices.pulley === pulley))
    .join("");
}

// Whether the motor at this ratio can take a pulley for the wire at all.
export function hasPulleys(options, motor, ratio) {
  return geared(options, motor, ratio).length > 0;
}

// Checks: the run's drum and carriage (formwork_sim.travel_checks), only what
// fails, a line each, in deep red (his ask of 11 October 2026: no cross);
// nothing when all pass or before a run (his ruling of the same day: no
// descriptive text). Each line as HTML.
function checkLines(checks) {
  if (!checks) return [];
  const failing = [];
  const fails = (text) => `<span class="over">${esc(text)}</span>`;
  if (checks.drum && !checks.drum.fits) {
    failing.push(fails("rope on drum " + Math.round(checks.drum.value_mm).toLocaleString("en-GB") + " of "
      + millimetres(checks.drum.limit_mm)));
  }
  if (checks.carriage && !checks.carriage.fits) {
    failing.push(fails("carriage " + Math.round(checks.carriage.value_mm).toLocaleString("en-GB") + " of "
      + millimetres(checks.carriage.limit_mm)));
  }
  return failing;
}

// The lines under the dropdowns: Have, Limited by, Checks when one fails, and
// at the end the most its drive pulls ("we should at the end of that also
// have it show the newtons max the mechanisms can produce").
export function mechanismHtml(entry, checks) {
  if (!entry) return "";
  const rows = [["Have", newtons(entry.have_newtons)],
                ["Limited by", esc(LIMIT_NAMES[entry.limit] || entry.limit) + ", "
                  + esc(entry.part_name || entry.part)]];
  checkLines(checks).forEach((line, i) => rows.push([i === 0 ? "Checks" : "", line]));
  if (Number.isFinite(entry.drive_newtons)) rows.push(["Max", newtons(entry.drive_newtons)]);
  return "<table>" + rows.map(([name, value]) => `<tr><th>${name}</th><td>${value}</td></tr>`).join("")
    + "</table>";
}
