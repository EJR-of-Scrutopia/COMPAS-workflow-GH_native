// The Cable net section's controller: it fetches, fills the skeleton in
// index.html, runs the analysis and writes the exports. Every judgement and
// every sentence comes from cablenet_model.js, which runs under node; this
// file only wires them to the page. studio.js owns the lenses and is told
// through onDemand when a demand document arrives.
//
// The speed dial annotates and never judges: no prototype has said what rope
// speed the net wants. The mechanism is five choices (spec 2026-10-09
// mechanism choices), remembered per study in this browser, and the panel
// shows prices (the owner's ruling of 9 October 2026). It is a tool, not a
// text: numbers, marks, tables and part names.

import {
  buyHtml, choiceOptions, curveSvg, demandSentences, grabText, isStale, machineHtml,
  prestressNote, priceHtml, recommendHtml, ropeMismatch, ropeWound, rpmText,
  toleranceNote, travelHtml, validChoices, verdictHtml,
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

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) {
  const el = {
    run: byId("cablenet-run"), runStatus: byId("cablenet-run-status"),
    prestress: byId("cablenet-prestress"), prestressValue: byId("cablenet-prestress-value"),
    tolerance: byId("cablenet-tolerance"), toleranceValue: byId("cablenet-tolerance-value"),
    speed: byId("cablenet-speed"), speedValue: byId("cablenet-speed-value"),
    speedNote: byId("cablenet-speed-note"), demand: byId("cablenet-demand"),
    motor: byId("cablenet-motor"), ratio: byId("cablenet-ratio"), pulley: byId("cablenet-pulley"),
    rope: byId("cablenet-rope"), wires: byId("cablenet-wires"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
    machine: byId("cablenet-machine"), holds: byId("cablenet-holds"),
    travel: byId("cablenet-travel"), buy: byId("cablenet-buy"), price: byId("cablenet-price"),
    grab: byId("cablenet-grab"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
    path: byId("cablenet-export-path"), result: byId("cablenet-export-result"),
  };
  // A page without the section is not the page this serves: mount nothing, and
  // say so, since a throw here would stop the studio's own script before it boots.
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    console.warn(`the cable net section is not on this page: no element for ${missing.join(", ")}`);
    return { reload: async () => {}, clear: () => {} };
  }

  // A ticket for each kind of answer keeps a late one from overwriting a newer:
  // the verdict's (which the parts and the demand move), the speed note's, and
  // the demand's own. watcher is the interval watching a run, if one is.
  const panel = {
    parts: null, options: null, choices: null,
    demand: null, demandNote: null, row: null, watcher: null,
    ticket: 0, speedTicket: 0, demandTicket: 0, speed: Number(el.speed.value),
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

  const SELECTS = [["motor", "motor"], ["ratio", "ratio"], ["pulley", "pulley"],
                   ["rope", "rope"], ["wires", "wires_per_motor"]];

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

  // Export is there while there is a demand to describe, and says why when not.
  function showExport() {
    el.exportButton.disabled = !panel.demand;
    el.exportButton.title = panel.demand
      ? "Spreadsheet, diagram and data sheet"
      : "No cable net demand";
  }

  // The demand in sentences, then what the chosen rope and the dial say about
  // the analysis on screen. All of it is the model's words, escaped there; the
  // rope note follows the system chosen, so every change of system redraws this.
  function renderDemand() {
    const demand = panel.demand;
    const sentences = panel.demandNote
      ? [`The cable net demand could not be read: ${esc(String(panel.demandNote).replace(/\.+$/, ""))}.`]
      : demandSentences(demand);
    for (const note of [ropeMismatch(panel.parts, demand, { rope: panel.choices && panel.choices.rope }),
                        prestressNote(demand, Number(el.prestress.value)),
                        toleranceNote(demand, Number(el.tolerance.value))]) {
      if (note) sentences.push(note);
    }
    el.demand.innerHTML = sentences.map((s) => `<p>${s.replace(/<(?!\/?b>)/g, "&lt;")}</p>`).join("");
    showExport();
  }

  function renderGrab() {
    const demand = panel.demand;
    if (!demand || isStale(demand)) { el.grab.innerHTML = ""; return; }
    const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
    el.grab.innerHTML = `<p>${esc(grabText(demand.placement, demand.held, acceptance))}</p>` +
      (demand.placement ? curveSvg(demand.placement.curve, acceptance) : "") +
      (demand.held && demand.held.actuators && demand.held.actuators.length
        ? `<p>The grabbed nodes light in the accent colour under the Sag and Node force lenses.</p>` : "");
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
    return scored.rows[0];
  }

  // The machine the choices make, each wire's verdict, the drum and carriage,
  // the wire to buy and the price: tables, from the model.
  function renderHolds() {
    const row = panel.row;
    const ok = row && !row.refused;
    el.machine.innerHTML = machineHtml(row, panel.parts);
    el.holds.innerHTML = ok ? verdictHtml(row.verdict) +
      `<p>Eye bolt at ${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees off its axis, assumed</p>` : "";
    el.travel.innerHTML = ok ? travelHtml(row.travel) : "";
    el.buy.innerHTML = ok ? buyHtml(row.price, row.cut_lengths) : "";
    el.price.innerHTML = ok ? priceHtml(row.price) : "";
    onCeiling(ok && row.verdict.worst ? row.verdict.worst.ceiling : null);
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
      el.holds.innerHTML = `<p>${esc(error.message)}</p>`;
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
  // prestress and tolerance dials also re-say whether they still match the
  // analysis on screen.
  function showDials() {
    el.prestressValue.textContent = el.prestress.value;
    el.toleranceValue.textContent = el.tolerance.value;
    el.speedValue.textContent = el.speed.value;
  }
  showDials();

  el.prestress.addEventListener("input", () => {
    showDials();
    renderDemand();
  });

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
      el.recommendNote.innerHTML = `<p>${esc(error.message)}</p>`;
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
    renderGrab();
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
    panel.demandNote = null;
    el.demand.innerHTML = "";
    el.machine.innerHTML = "";
    el.holds.innerHTML = "";
    el.travel.innerHTML = "";
    el.buy.innerHTML = "";
    el.price.innerHTML = "";
    el.grab.innerHTML = "";
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
      const body = { ...sentOptions(options), prestress: Number(el.prestress.value),
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
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
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
      });
      el.result.innerHTML = `<p>Written to ${esc(done.folder)}:</p><ul>` +
        (done.paths || []).map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>" +
        (done.note ? `<p>${esc(done.note)}</p>` : "");
      loadFolder();
    } catch (error) {
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
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
      el.holds.innerHTML = `<p>${esc(error.message)}</p>`;
    }
  }

  loadFolder();
  reload();
  return { reload, clear };
}
