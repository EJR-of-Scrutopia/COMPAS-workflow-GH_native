// The Cable net section's controller: it fetches, fills the skeleton in
// index.html, runs the analysis and writes the exports. Every figure and table
// comes from cablenet_model.js, which runs under node; this file only wires
// them to the page. studio.js owns the lenses and is told
// through onDemand when a demand document arrives.
//
// The speed dial annotates and never judges: no prototype has said what rope
// speed the net wants. The mechanism is five choices (spec 2026-10-09
// mechanism choices), remembered per study in this browser, and the panel
// shows prices (the owner's ruling of 9 October 2026). It is a tool, not a
// text: numbers, marks, tables and part names.

import {
  answersHtml, buyHtml, choiceOptions, eyeBoltHtml, graphsHtml, limitsHtml, machineHtml,
  menuAnswers, motorsHtml, priceHtml, recommendHtml, ropeWound, rpmText, runWarnings,
  travelHtml, validChoices, verdictHtml,
} from "./cablenet_model.js";

// The wire's angle to its eye bolt's axis is not recorded in the export, so
// this is an assumption, not a computed figure. It selects the bolt's off-axis
// rating, which is the conservative direction.
const ASSUMED_ANGLE_DEGREES = 10.0;
const REMEMBERED_PREFIX = "vaulted-cablenet-choices:";

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function byId(id) {
  return document.getElementById(id);
}

async function getJson(url, init) {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* keep status */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function postJson(url, body) {
  return getJson(url, { method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(body) });
}

// The demand is keyed exactly as the bundle on screen was fetched, so the
// panel reads the document the run wrote and never a neighbour of it. A value
// the study does not have (a null source) is not put in the query.
function demandUrl(studyName, options) {
  const query = new URLSearchParams();
  for (const key of ["material", "pattern", "size", "thickness", "density", "source"]) {
    if (options[key] != null && options[key] !== "") query.set(key, String(options[key]));
  }
  return `/api/studies/${encodeURIComponent(studyName)}/cablenet?${query.toString()}`;
}

// The study's options as a request body carries them, on the same rule as the
// query above: a null or empty value is left out. The server reads a null
// material or size as the text "None" or refuses it, so it must not arrive.
function sentOptions(options) {
  const sent = {};
  for (const [key, value] of Object.entries(options || {})) {
    if (value != null && value !== "") sent[key] = value;
  }
  return sent;
}

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling, onPopup = () => {} }) {
  const el = {
    run: byId("cablenet-run"), runStatus: byId("cablenet-run-status"),
    tolerance: byId("cablenet-tolerance"), toleranceValue: byId("cablenet-tolerance-value"),
    speed: byId("cablenet-speed"), speedValue: byId("cablenet-speed-value"),
    speedNote: byId("cablenet-speed-note"), demand: byId("cablenet-demand"),
    motor: byId("cablenet-motor"), ratio: byId("cablenet-ratio"), pulley: byId("cablenet-pulley"),
    rope: byId("cablenet-rope"), wires: byId("cablenet-wires"),
    wiresValue: byId("cablenet-wires-value"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
    machine: byId("cablenet-machine"), holds: byId("cablenet-holds"),
    travel: byId("cablenet-travel"), buy: byId("cablenet-buy"), price: byId("cablenet-price"),
    graphs: byId("cablenet-graphs"), limits: byId("cablenet-limits"), motors: byId("cablenet-motors"),
    popup: byId("cablenet-popup"), popupToggle: byId("cablenet-popup-toggle"),
    popupClose: byId("cablenet-popup-close"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
    path: byId("cablenet-export-path"), result: byId("cablenet-export-result"),
  };
  // A page without the section is not the page this serves: mount nothing, and
  // say so, since a throw here would stop the studio's own script before it boots.
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    console.warn(`the cable net section is not on this page: no element for ${missing.join(", ")}`);
    return { reload: async () => {}, clear: () => {}, closePopup: () => {} };
  }
  const tabs = [...document.querySelectorAll("#cablenet-tabs [data-cn-tab]")];
  const panes = [...document.querySelectorAll("#cablenet-popup .cn-tab")];

  // A ticket for each kind of answer keeps a late one from overwriting a newer:
  // the verdict's (which the parts and the demand move), the speed note's, and
  // the demand's own. watcher is the interval watching a run, if one is.
  const panel = {
    parts: null, options: null, choices: null,
    demand: null, demandNote: null, row: null, strongest: null, watcher: null,
    ticket: 0, speedTicket: 0, demandTicket: 0, motorsTicket: 0, speed: Number(el.speed.value),
    tab: "cn-mechanism",
  };

  async function loadParts() {
    if (panel.parts) return panel.parts;
    panel.parts = await getJson("/api/catalogue");
    panel.options = panel.parts.choices;
    return panel.parts;
  }

  // The study's own choices, as this browser last left them, else the first
  // the catalogue can build.
  function restoreChoices() {
    let remembered = null;
    try {
      remembered = JSON.parse(localStorage.getItem(REMEMBERED_PREFIX + studyName()) || "null");
    } catch (_) { remembered = null; }
    panel.choices = validChoices(panel.options, remembered);
    renderChoices();
  }

  function saveChoices() {
    try {
      localStorage.setItem(REMEMBERED_PREFIX + studyName(), JSON.stringify(panel.choices));
    } catch (_) { /* a private window */ }
  }

  // the four choices in the pop-up; wires a motor is the menu's slider
  const SELECTS = [["motor", "motor"], ["ratio", "ratio"], ["pulley", "pulley"],
                   ["rope", "rope"]];

  function renderChoices() {
    const offered = choiceOptions(panel.options, panel.parts, panel.choices);
    for (const [name, key] of SELECTS) {
      const control = el[name];
      control.innerHTML = "";
      for (const item of offered[key]) {
        const option = document.createElement("option");
        option.value = item.value == null ? "" : String(item.value);
        option.textContent = item.label;
        option.selected = item.value === panel.choices[key];
        control.appendChild(option);
      }
    }
    el.wires.value = String(panel.choices.wires_per_motor);
    el.wiresValue.textContent = el.wires.value;
  }

  function readChoice(key, value) {
    if (key === "motor" || key === "rope") return value;
    if (key === "pulley") return value === "" ? null : value;
    if (key === "ratio") return value === "" ? null : Number(value);
    return Number(value);
  }

  for (const [name, key] of SELECTS) {
    el[name].addEventListener("change", () => {
      panel.choices = validChoices(panel.options,
                                   { ...panel.choices, [key]: readChoice(key, el[name].value) });
      saveChoices();
      renderChoices();
      refresh();
    });
  }

  el.wires.addEventListener("input", () => {
    showDials();
  });
  el.wires.addEventListener("change", () => {
    if (!panel.choices) return;
    panel.choices = validChoices(panel.options,
                                 { ...panel.choices, wires_per_motor: Number(el.wires.value) });
    saveChoices();
    renderChoices();
    refresh();
  });

  // The pop-up on the left (spec 2026-10-09 Cable net display, section 4), open
  // or shut and on the tab this browser last left it. Opening it takes the
  // left from the data sheet and the live graphs (onPopup).
  const POPUP_KEY = "vaulted-cablenet-popup";

  function savePopup() {
    try {
      localStorage.setItem(POPUP_KEY, JSON.stringify(
        { open: !el.popup.classList.contains("hidden"), tab: panel.tab }));
    } catch (_) { /* a private window */ }
  }

  function showTab(id) {
    panel.tab = id;
    for (const button of tabs) button.classList.toggle("active", button.dataset.cnTab === id);
    for (const pane of panes) pane.classList.toggle("hidden", pane.id !== id);
    savePopup();
    renderMotors();
  }

  function setPopup(open) {
    el.popup.classList.toggle("hidden", !open);
    el.popupToggle.classList.toggle("active", open);
    if (open) onPopup();
    savePopup();
    renderMotors();
  }

  for (const button of tabs) button.addEventListener("click", () => showTab(button.dataset.cnTab));
  el.popupToggle.addEventListener("click", () => setPopup(el.popup.classList.contains("hidden")));
  el.popupClose.addEventListener("click", () => setPopup(false));

  // Every motor at the other choices, scored only while the Mechanism tab is in
  // view; a click on a row chooses its motor.
  async function renderMotors() {
    if (el.popup.classList.contains("hidden") || panel.tab !== "cn-mechanism") return;
    if (!panel.choices || !panel.options || !studyName()) { el.motors.innerHTML = ""; return; }
    const mine = ++panel.motorsTicket;
    const choices = panel.options.motors.map((motor) =>
      validChoices(panel.options, { ...panel.choices, motor: motor.key }));
    const options = studyOptions();
    const body = { choices, angle_degrees: ASSUMED_ANGLE_DEGREES };
    if (options) body.options = sentOptions(options);
    // scored once for what the rows depend on (the study, its options, every
    // choice but the motor, the demand): opening the tab again or choosing a
    // motor redraws them from what was scored
    const key = JSON.stringify([studyName(), body, panel.demandTicket]);
    if (key === panel.motorsKey && panel.motorsRows) {
      el.motors.innerHTML = motorsHtml(panel.motorsRows, panel.choices.motor, panel.demand);
      return;
    }
    try {
      const scored = await postJson(
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
      if (mine !== panel.motorsTicket) return;
      panel.motorsKey = key;
      panel.motorsRows = scored.rows;
      el.motors.innerHTML = motorsHtml(scored.rows, panel.choices.motor, panel.demand);
    } catch (error) {
      if (mine !== panel.motorsTicket) return;
      el.motors.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
  }

  el.motors.addEventListener("click", (event) => {
    const line = event.target.closest("tr[data-motor]");
    if (!line || !panel.choices) return;
    panel.choices = validChoices(panel.options, { ...panel.choices, motor: line.dataset.motor });
    saveChoices();
    renderChoices();
    refresh();
  });

  // Export is there while there is a demand to describe, and says why when not.
  function showExport() {
    el.exportButton.disabled = !panel.demand;
    el.exportButton.title = panel.demand
      ? "Spreadsheet, diagram and data sheet"
      : "No cable net demand";
  }

  // The ceiling a run is designed for (spec 2026-10-10 prestress and holds,
  // section 4): the chosen machine's worst wire, or the strongest machine's
  // while none is scored, or none.
  function chosenCeiling() {
    if (panel.row && !panel.row.refused && panel.row.verdict && panel.row.verdict.worst) {
      return panel.row.verdict.worst.ceiling;
    }
    return panel.strongest ? panel.strongest.ceiling_newtons : null;
  }

  // The menu's answers (Needed, Gives, Most, Holds, Roof), then one line for
  // each thing the run on screen differs from. Values only: the model writes them.
  function renderDemand() {
    const demand = panel.demand;
    const warnings = panel.demandNote
      ? ["Cable net demand: " + String(panel.demandNote).replace(/\.+$/, "")]
      : runWarnings(demand, { ceiling: chosenCeiling(), tolerance: Number(el.tolerance.value) }, panel.parts, panel.choices && panel.choices.rope);
    el.demand.innerHTML = answersHtml(menuAnswers(demand, panel.row, panel.strongest)) +
      warnings.map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
    showExport();
  }

  // The Graphs tab: the run's stages, the walk and the net, against the chosen
  // machine's ceiling.
  function renderGraphs() {
    const row = panel.row;
    const ceiling = row && !row.refused && row.verdict && row.verdict.worst
      ? row.verdict.worst.ceiling : null;
    el.graphs.innerHTML = graphsHtml(panel.demand, ceiling);
  }

  async function score(speed) {
    const options = studyOptions();
    const body = {
      choices: [panel.choices], angle_degrees: ASSUMED_ANGLE_DEGREES,
      rope_speed_mm_s: speed,
    };
    if (options) body.options = sentOptions(options);
    const scored = await postJson(
      `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
    panel.strongest = scored.strongest || null;
    return scored.rows[0];
  }

  // The machine the choices make, each wire's verdict, the drum and carriage,
  // the wire to buy and the price: tables, from the model.
  function renderHolds() {
    const row = panel.row;
    const ok = row && !row.refused;
    el.machine.innerHTML = machineHtml(row, panel.parts);
    el.limits.innerHTML = ok ? limitsHtml(row.terms) : "";
    el.holds.innerHTML = ok ? verdictHtml(row.verdict) + eyeBoltHtml(ASSUMED_ANGLE_DEGREES) : "";
    el.travel.innerHTML = ok ? travelHtml(row.travel) : "";
    el.buy.innerHTML = ok ? buyHtml(row.price, row.cut_lengths) : "";
    el.price.innerHTML = ok ? priceHtml(row.price) : "";
    renderDemand();
    renderGraphs();
    renderMotors();
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null, ok ? row.verdict : null, panel.strongest ? panel.strongest.ceiling_newtons : null);
  }

  // The parts changed, or the demand did: the verdict is redrawn, and the demand
  // readout with it, because its rope note follows the chosen rope.
  async function refresh() {
    if (!panel.choices) return;
    const mine = ++panel.ticket;
    panel.speedTicket += 1;           // this answer writes the speed note too
    const speed = panel.speed;
    renderDemand();
    if (!studyName()) {
      // nothing to score against until a study is open
      panel.row = null;
      renderHolds();
      el.speedNote.textContent = rpmText(speed, null);
      return;
    }
    try {
      const row = await score(speed);
      if (mine !== panel.ticket) return;
      panel.row = row;
      renderHolds();
      if (speed === panel.speed) el.speedNote.textContent = rpmText(speed, row);
    } catch (error) {
      if (mine !== panel.ticket) return;
      panel.row = null;
      renderHolds();
      el.holds.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
  }

  // The slider moved: only the rpm note is touched, never the verdict.
  async function annotateSpeed() {
    if (!panel.choices) return;
    const mine = ++panel.speedTicket;
    const speed = panel.speed;
    if (!studyName()) {
      byId("cablenet-speed-note").textContent = rpmText(speed, null);
      return;
    }
    try {
      const row = await score(speed);
      if (mine !== panel.speedTicket) return;
      byId("cablenet-speed-note").textContent = rpmText(speed, row);
    } catch (error) {
      if (mine !== panel.speedTicket) return;
      byId("cablenet-speed-note").textContent = `${speed} mm/s (no rpm: ${error.message})`;
    }
  }

  // Each dial states the value it has: its reading follows the track, and the
  // tolerance dial also re-says whether it still matches the analysis on screen.
  function showDials() {
    el.toleranceValue.textContent = el.tolerance.value;
    el.speedValue.textContent = el.speed.value;
    el.wiresValue.textContent = el.wires.value;
  }
  showDials();

  el.tolerance.addEventListener("input", () => {
    showDials();
    renderDemand();
  });

  let speedTimer = null;
  el.speed.addEventListener("input", () => {
    panel.speed = Number(el.speed.value);
    showDials();
    clearTimeout(speedTimer);
    speedTimer = setTimeout(annotateSpeed, 150);
  });

  async function recommend() {
    el.recommend.disabled = true;
    try {
      const options = studyOptions();
      if (!studyName()) throw new Error("open a study first");
      const request = { search: "choices", angle_degrees: ASSUMED_ANGLE_DEGREES };
      if (options) request.options = sentOptions(options);
      const body = await postJson(
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/recommend`, request);
      el.recommendNote.innerHTML = recommendHtml(body);
      if (body.choices) {
        panel.choices = validChoices(panel.options, body.choices);
        saveChoices();
        renderChoices();
        await refresh();
      }
    } catch (error) {
      el.recommendNote.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    } finally {
      el.recommend.disabled = false;
    }
  }
  el.recommend.addEventListener("click", recommend);

  // The newest answer is the one on screen: a reload begun while an older one
  // was still reading is not undone when the older one comes back. The state is
  // replaced after the wait, so what is shown and what is judged stay one thing.
  // False says a newer load, or a clear, owns the panel now: the caller leaves
  // the rescoring to it.
  async function loadDemand() {
    const mine = ++panel.demandTicket;
    const options = studyOptions();
    let demand = null;
    let note = null;
    if (options && studyName()) {
      try {
        demand = await getJson(demandUrl(studyName(), options));
      } catch (error) {
        if (error.status !== 404) note = error.message;
      }
      if (mine !== panel.demandTicket) return false;
    }
    panel.demand = demand;
    panel.demandNote = note;
    renderDemand();
    renderGraphs();
    onDemand(panel.demand);
    return true;
  }

  function stopWatching() {
    if (panel.watcher != null) clearInterval(panel.watcher);
    panel.watcher = null;
  }

  function watch(runId) {
    stopWatching();
    const poll = setInterval(async () => {
      try {
        const run = await getJson(`/api/runs/${encodeURIComponent(runId)}`);
        if (panel.watcher !== poll) return;       // let go while the answer was on its way
        el.runStatus.textContent = `${run.state} (${run.phase}) ${run.message || ""}`;
        if (run.state === "done") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = "the cable net analysis is in";
          if (await loadDemand()) await refresh();
        }
        if (run.state === "failed") {
          stopWatching();
          el.run.disabled = false;
        }
      } catch (error) {
        if (panel.watcher !== poll) return;
        stopWatching();
        el.run.disabled = false;
        el.runStatus.textContent = `lost contact with the server: ${error.message}`;
      }
    }, 1000);
    panel.watcher = poll;
  }

  // The study on screen is going, or a new one is loading: nothing the panel
  // holds describes it any more. An answer still on its way cannot paint over
  // the emptiness (the tickets), and a run being watched is let go of: it goes on
  // at the server, and pressing Run for that study picks it up again (the 409).
  // The caller reloads once the new study is in.
  function clear() {
    panel.ticket += 1;
    panel.speedTicket += 1;
    panel.demandTicket += 1;
    stopWatching();
    panel.demand = null;
    panel.row = null;
    panel.strongest = null;
    panel.motorsKey = null;
    panel.motorsRows = null;
    panel.demandNote = null;
    el.demand.innerHTML = "";
    el.limits.innerHTML = "";
    el.motors.innerHTML = "";
    el.machine.innerHTML = "";
    el.holds.innerHTML = "";
    el.travel.innerHTML = "";
    el.buy.innerHTML = "";
    el.price.innerHTML = "";
    el.graphs.innerHTML = "";
    el.runStatus.textContent = "";
    el.recommendNote.innerHTML = "";
    el.result.innerHTML = "";
    el.run.disabled = false;
    showExport();
    onDemand(null);
    onCeiling(null);
  }

  async function startRun() {
    const options = studyOptions();
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    el.run.disabled = true;
    el.runStatus.textContent = "starting";
    try {
      // the engine works the prestress out from the load, under the
      // ceiling of the machine chosen
      const body = { ...sentOptions(options),
                     ceiling_newtons: chosenCeiling() == null ? undefined : chosenCeiling(),
                     tolerance_mm: Number(el.tolerance.value),
                     rope: panel.choices ? panel.choices.rope : undefined };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/cablenet/run`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      let started = null;
      try { started = await response.json(); } catch (_) { started = null; }
      if (response.status === 409) {
        // A run is already live on this study. A cable net run is watched from
        // here; a staged one belongs to the Analysis section, whose own watcher
        // would reload the study when it ends and call it an analysis.
        const live = await getJson(`/api/runs/${encodeURIComponent(started.run)}`);
        if (live.kind === "cable net") {
          el.runStatus.textContent = "watching the live run";
          watch(started.run);
        } else {
          el.runStatus.textContent = "a staged analysis is live on this study; " +
            "the cable net run can start when it finishes";
          el.run.disabled = false;
        }
        return;
      }
      if (!response.ok) {
        el.runStatus.textContent = `run refused: ${started && started.detail ? started.detail : `HTTP ${response.status}`}`;
        el.run.disabled = false;
        return;
      }
      watch(started.run);
    } catch (error) {
      el.runStatus.textContent = `run failed to start: ${error.message}`;
      el.run.disabled = false;
    }
  }
  el.run.addEventListener("click", startRun);

  const showFolder = (row) => {
    el.path.textContent = row && row.path ? row.path : "no folder chosen";
    el.path.title = row && row.path ? (row.exists ? row.path : `${row.path} (this folder is not there)`) : "";
  };
  async function loadFolder() {
    try { showFolder(await getJson("/api/cablenet/exports/folder")); }
    catch (error) { el.path.textContent = `the export folder could not be read: ${error.message}`; }
  }
  el.choose.addEventListener("click", async () => {
    el.choose.disabled = true;
    try {
      const browsed = await getJson("/api/cablenet/exports/folder/browse", { method: "POST" });
      if (browsed && browsed.path) {
        showFolder(await postJson("/api/cablenet/exports/folder", { path: browsed.path }));
        el.result.innerHTML = "";
      }
    } catch (error) {
      el.result.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    } finally {
      el.choose.disabled = false;
    }
  });

  async function runExport() {
    const options = studyOptions();
    el.exportButton.disabled = true;
    el.result.textContent = "writing the documents";
    try {
      const wound = panel.demand ? ropeWound(panel.demand) : null;
      if (!panel.row || panel.row.refused) throw new Error("no machine to export");
      const done = await postJson(`/api/studies/${encodeURIComponent(studyName())}/cablenet/exports`, {
        ...sentOptions(options), configuration: panel.row.configuration, angle_degrees: ASSUMED_ANGLE_DEGREES,
        ...(wound != null ? { rope_wound_mm: wound } : {}),
        // the holds file is for the machine chosen (spec 2026-10-10, section 8)
        ceiling_newtons: chosenCeiling(),
        most_newtons: panel.strongest ? panel.strongest.ceiling_newtons : null,
      });
      el.result.innerHTML = `<div>Written to ${esc(done.folder)}:</div><ul>` +
        (done.paths || []).map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>" +
        (done.note ? `<div class="cablenet-warning">${esc(done.note)}</div>` : "");
      loadFolder();
    } catch (error) {
      el.result.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    } finally {
      showExport();
    }
  }
  el.exportButton.addEventListener("click", runExport);

  async function reload() {
    try {
      await loadParts();
      restoreChoices();
      if (await loadDemand()) await refresh();
    } catch (error) {
      el.holds.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
  }

  let remembered = {};
  try { remembered = JSON.parse(localStorage.getItem(POPUP_KEY) || "{}") || {}; } catch (_) { remembered = {}; }
  showTab(panes.some((pane) => pane.id === remembered.tab) ? remembered.tab : "cn-mechanism");
  if (remembered.open) setPopup(true);
  loadFolder();
  reload();
  return { reload, clear, closePopup: () => setPopup(false) };
}
