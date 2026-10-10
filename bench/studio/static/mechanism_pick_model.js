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

// The entry chosen: the motor this browser last chose for the study, else the
// strongest, which is the first; -1 for an empty list.
export function pickIndex(list, motor) {
  if (!Array.isArray(list) || !list.length) return -1;
  const found = motor ? list.findIndex((entry) => entry.choices.motor === motor) : -1;
  return found >= 0 ? found : 0;
}

export function optionsHtml(list, chosen) {
  return (list || []).map((entry, i) =>
    `<option value="${i}"${i === chosen ? " selected" : ""}>${esc(entry.label)}</option>`).join("");
}

// Checks: the run's drum and carriage (formwork_sim.travel_checks), all
// passing in one line, else only what fails, a line each; before a run there
// is nothing yet to check.
function checkLines(checks) {
  if (!checks) return ["after a run"];
  const failing = [];
  if (checks.drum && !checks.drum.fits) {
    failing.push("rope on drum " + Math.round(checks.drum.value_mm).toLocaleString("en-GB") + " of "
      + millimetres(checks.drum.limit_mm) + " ✗");
  }
  if (checks.carriage && !checks.carriage.fits) {
    failing.push("carriage " + Math.round(checks.carriage.value_mm).toLocaleString("en-GB") + " of "
      + millimetres(checks.carriage.limit_mm) + " ✗");
  }
  return failing.length ? failing : ["all pass ✓"];
}

// The three lines under the dropdown: Have, Limited by, Checks.
export function mechanismHtml(entry, checks) {
  if (!entry) return "";
  const rows = [["Have", newtons(entry.have_newtons) + " a spool"],
                ["Limited by", esc(entry.part) + ", " + esc(LIMIT_NAMES[entry.limit] || entry.limit)]];
  checkLines(checks).forEach((line, i) => rows.push([i === 0 ? "Checks" : "", esc(line)]));
  return "<table>" + rows.map(([name, value]) => `<tr><th>${name}</th><td>${value}</td></tr>`).join("")
    + "</table>";
}
