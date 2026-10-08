// The Cable net section's controller: it fetches, fills the skeleton in
// index.html, runs the analysis and writes the exports. Every judgement and
// every sentence comes from cablenet_model.js, which runs under node; this
// file only wires them to the page. studio.js owns the lenses and is told
// through onDemand when a demand document arrives.
//
// Two rules live here. The speed dial annotates and never judges: no
// prototype has said what rope speed the net wants, and finding that out is
// the machine's whole purpose. And price never reaches the panel: it stays in
// the exported documents, where a supplier or a supervisor needs it.

import {
  curveSvg, demandSentences, fallbackKey, grabText, isStale, modifiedFrom, newtons,
  prestressFloor, ropeWound, rpmText, settledText, shapeOf, verdictOf,
} from "./cablenet_model.js";

// The wire's angle to its eye bolt's axis is not recorded in the export, so
// this is an assumption, not a computed figure. It selects the bolt's off-axis
// rating, which is the conservative direction.
const ASSUMED_ANGLE_DEGREES = 10.0;
const REMEMBERED_KEY = "vaulted-cablenet-configuration";

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

function configurationOf(parts, key) {
  const entry = parts.configurations[key];
  const configuration = { ...entry.parts, chain: [...(entry.parts.chain || [])] };
  if (configuration.sheave === undefined) configuration.sheave = null;
  if (configuration.reeve_factor === undefined) configuration.reeve_factor = 1;
  return configuration;
}

export function mountCableNet({ studyName, studyOptions, onDemand, onCeiling }) {
  const el = {
    run: byId("cablenet-run"), runStatus: byId("cablenet-run-status"),
    prestress: byId("cablenet-prestress"), prestressValue: byId("cablenet-prestress-value"),
    speed: byId("cablenet-speed"), speedValue: byId("cablenet-speed-value"),
    speedNote: byId("cablenet-speed-note"), demand: byId("cablenet-demand"),
    select: byId("cablenet-configuration"), selectNote: byId("cablenet-configuration-note"),
    recommend: byId("cablenet-recommend"), recommendNote: byId("cablenet-recommend-note"),
    varyToggle: byId("cablenet-vary-toggle"), parts: byId("cablenet-parts"),
    settled: byId("cablenet-settled"), holds: byId("cablenet-holds"), grab: byId("cablenet-grab"),
    exportButton: byId("cablenet-export"), choose: byId("cablenet-export-choose"),
    path: byId("cablenet-export-path"), result: byId("cablenet-export-result"),
  };
  // A page without the section is not the page this serves: mount nothing, and
  // say so, since a throw here would stop the studio's own script before it boots.
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    console.warn(`the cable net section is not on this page: no element for ${missing.join(", ")}`);
    return { reload: async () => {} };
  }

  // Two tickets keep a late answer from overwriting a newer one: the verdict's,
  // which the parts and the demand move, and the speed note's.
  const panel = {
    parts: null, key: null, configuration: null, modified: false,
    demand: null, demandNote: null, row: null,
    ticket: 0, speedTicket: 0, speed: Number(el.speed.value),
  };

  let remembered = null;
  try { remembered = localStorage.getItem(REMEMBERED_KEY); } catch (_) { remembered = null; }

  async function loadParts() {
    if (panel.parts) return panel.parts;
    panel.parts = await getJson("/api/catalogue");
    const fallback = fallbackKey(remembered, panel.parts.configurations);
    panel.key = fallback.key;
    panel.configuration = panel.key ? configurationOf(panel.parts, panel.key) : null;
    panel.modified = false;
    renderSelect(fallback.note);
    renderParts();
    return panel.parts;
  }

  function renderSelect(note) {
    el.select.innerHTML = "";
    for (const [key, entry] of Object.entries(panel.parts.configurations)) {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = entry.name;
      option.title = entry.for;
      option.selected = key === panel.key;
      el.select.appendChild(option);
    }
    const entry = panel.key ? panel.parts.configurations[panel.key] : null;
    el.selectNote.innerHTML = (note ? `<p>${esc(note)}</p>` : "") +
      (entry ? `<p>${esc(entry.for)}</p>` : "") +
      (panel.modified ? `<p><b>Modified from ${esc(entry ? entry.name : panel.key)}.</b> ` +
        `<button type="button" id="cablenet-reset" title="Return to the configuration as designed">Reset</button></p>` : "");
    const reset = byId("cablenet-reset");
    if (reset) reset.onclick = () => choose(panel.key);
    el.settled.textContent = settledText(panel.configuration ? panel.configuration.drive : null);
  }

  function choose(key) {
    panel.key = key;
    panel.configuration = configurationOf(panel.parts, key);
    panel.modified = false;
    try { localStorage.setItem(REMEMBERED_KEY, key); } catch (_) { /* a private window */ }
    renderSelect(null);
    renderParts();
    refresh();
  }

  el.select.addEventListener("change", () => choose(el.select.value));

  // Vary parts: the individual selects, collapsed until wanted. The drive is
  // shown and never chosen; the gearbox list follows the motor's family.
  // Both pairings come precomputed from the catalogue (parts.pairing).
  el.varyToggle.addEventListener("click", () => {
    el.parts.classList.toggle("hidden");
    el.varyToggle.classList.toggle("active", !el.parts.classList.contains("hidden"));
  });

  function renderParts() {
    const parts = panel.parts;
    const current = panel.configuration;
    el.parts.innerHTML = "";
    if (!parts || !current) return;
    const pairing = parts.pairing || { drive_for: {}, gearboxes_for: {} };
    const row = (label, control) => {
      const holder = document.createElement("div");
      holder.className = "named";
      const name = document.createElement("span");
      name.textContent = label;
      holder.appendChild(name);
      holder.appendChild(control);
      el.parts.appendChild(holder);
    };
    const select = (entries, chosen, labelOf, onChange) => {
      const control = document.createElement("select");
      for (const [key, entry] of entries) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = labelOf(key, entry);
        option.selected = key === chosen;
        control.appendChild(option);
      }
      control.onchange = () => { onChange(control.value); varied(); };
      return control;
    };
    const kinds = [["motor", "Motor"], ["gearbox", "Gearbox"], ["drum", "Drum"],
                   ["rope", "Rope"], ["rail", "Rail"]];
    for (const [kind, label] of kinds) {
      let entries = Object.entries(parts[kind]);
      if (kind === "gearbox") {
        const allowed = pairing.gearboxes_for[current.motor] || [];
        entries = entries.filter(([key]) => allowed.includes(key));
      }
      row(label, select(entries, current[kind],
        (key, entry) => `${entry.model || key}${entry.confidence ? `, ${entry.confidence}` : ""}`,
        (value) => {
          current[kind] = value;
          if (kind === "motor") {
            current.drive = pairing.drive_for[value] || current.drive;
            const allowed = pairing.gearboxes_for[value] || [];
            if (!allowed.includes(current.gearbox)) current.gearbox = allowed[0] || current.gearbox;
          }
        }));
    }
    const drive = document.createElement("span");
    drive.textContent = `${current.drive} (follows the motor)`;
    row("Drive", drive);
    row("Turnbuckle", select(Object.entries(parts.turnbuckle), current.chain[1],
      (key, entry) => `${String(entry.configuration).toUpperCase()} ${entry.thread}, ${entry.working_load_kg} kg working load`,
      (value) => { current.chain = [current.chain[0], value]; }));
    row("Eye bolt", select(Object.entries(parts.eye_bolt), current.chain[0],
      (key, entry) => `${entry.thread} eye bolt, ${entry.angled_kg} kg at an angle`,
      (value) => { current.chain = [value, current.chain[1]]; }));
    const block = document.createElement("input");
    block.type = "checkbox";
    block.checked = Number(current.reeve_factor) > 1;
    block.title = "Halves the force at the drum and doubles it through the sheave";
    block.onchange = () => {
      current.reeve_factor = block.checked ? 2 : 1;
      current.sheave = block.checked ? Object.keys(parts.sheave)[0] : null;
      varied();
    };
    row("Moving block", block);
  }

  function varied() {
    panel.modified = modifiedFrom(panel.key, panel.configuration, panel.parts.configurations);
    renderSelect(null);
    renderParts();
    refresh();
  }

  function renderDemand() {
    const demand = panel.demand;
    let html = panel.demandNote
      ? `<p>The cable net demand could not be read: ${esc(String(panel.demandNote).replace(/\.+$/, ""))}.</p>`
      : demandSentences(demand).map((s) => `<p>${s.replace(/<(?!\/?b>)/g, "&lt;")}</p>`).join("");
    if (demand && demand.prestress != null &&
        Number(demand.prestress) !== Number(el.prestress.value)) {
      html += `<p>The analysis on screen used a prestress of ` +
        `<b>${newtons(demand.prestress)} N</b>; the dial reads ${esc(el.prestress.value)} N. ` +
        `Run again to use the dial's value.</p>`;
    }
    el.demand.innerHTML = html;
    el.exportButton.disabled = !demand;
    el.exportButton.title = demand
      ? "Write the configuration with its data: the spreadsheet, the diagram and the data sheet"
      : "Nothing to export: this study has no cable net demand yet";
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
      configurations: [panel.configuration], angle_degrees: ASSUMED_ANGLE_DEGREES,
      rope_speed_mm_s: speed,
    };
    if (options) {
      body.options = sentOptions(options);
    } else {
      // No study options: the server has no demand to read, so the panel's own
      // figures stand (the route takes the caller's when it reads none).
      body.prestress_floor = panel.demand ? prestressFloor(panel.demand) : 0;
      const wound = panel.demand ? ropeWound(panel.demand) : null;
      if (wound != null) body.rope_wound_mm = wound;
    }
    const scored = await postJson(
      `/api/studies/${encodeURIComponent(studyName())}/cablenet/configurations`, body);
    return scored.rows[0];
  }

  function renderHolds() {
    const row = panel.row;
    const floor = panel.demand ? prestressFloor(panel.demand) : 0;
    const shape = panel.demand ? shapeOf(panel.demand) : null;
    // With no load factor the route says why in load_factor_note. That reason
    // goes to the model as the capacity's own detail, so the first line says
    // what is true (no demand at all, or an old one) and says it once.
    const capacity = !row ? null : (row.load_factor || (row.load_factor_note
      ? { limit_factor: null, detail: row.load_factor_note } : null));
    const verdict = verdictOf({ row, floor, shape, capacity });
    el.holds.innerHTML = `<p><b>${esc(verdict.headline)}</b></p>` +
      verdict.reasons.map((r) => `<p>${esc(r)}</p>`).join("") +
      `<p>The eye bolt is rated at its off-axis figure (${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees) ` +
      `because the wire's angle to the bolt is not recorded in the export. This is an assumption.</p>`;
    onCeiling(row && !row.refused ? row.ceiling : null);
  }

  // The parts changed, or the demand did: the verdict is redrawn.
  async function refresh() {
    if (!panel.configuration) return;
    const mine = ++panel.ticket;
    panel.speedTicket += 1;           // this answer writes the speed note too
    const speed = panel.speed;
    if (!studyName()) {
      // nothing to score against until a study is open
      panel.row = null;
      el.holds.innerHTML = "";
      el.speedNote.textContent = rpmText(speed, null);
      onCeiling(null);
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
      el.holds.innerHTML = `<p>The numbers could not be fetched: ${esc(error.message)}</p>`;
      onCeiling(null);
    }
  }

  // The slider moved: only the rpm note is touched, never the verdict.
  async function annotateSpeed() {
    if (!panel.configuration) return;
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
  // prestress dial also re-says whether it still matches the analysis on screen.
  function showDials() {
    el.prestressValue.textContent = el.prestress.value;
    el.speedValue.textContent = el.speed.value;
  }
  showDials();

  el.prestress.addEventListener("input", () => {
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
      const request = { angle_degrees: ASSUMED_ANGLE_DEGREES };
      if (options) request.options = sentOptions(options);
      const body = await postJson(
        `/api/studies/${encodeURIComponent(studyName())}/cablenet/recommend`, request);
      panel.key = body.key;
      panel.configuration = { ...body.configuration, chain: [...body.configuration.chain] };
      panel.modified = false;
      try { localStorage.setItem(REMEMBERED_KEY, body.key); } catch (_) { /* a private window */ }
      el.recommendNote.innerHTML = `<p><b>${esc(body.name)}</b>: ${esc(body.rule)}.</p>` +
        (body.demand_note ? `<p>${esc(body.demand_note)}</p>` : "");
      renderSelect(null);
      renderParts();
      await refresh();
    } catch (error) {
      el.recommendNote.innerHTML = `<p>No recommendation: ${esc(error.message)}</p>`;
    } finally {
      el.recommend.disabled = false;
    }
  }
  el.recommend.addEventListener("click", recommend);

  async function loadDemand() {
    const options = studyOptions();
    panel.demand = null;
    panel.demandNote = null;
    if (!options || !studyName()) {
      renderDemand();
      renderGrab();
      onDemand(null);
      return;
    }
    try {
      panel.demand = await getJson(demandUrl(studyName(), options));
    } catch (error) {
      if (error.status !== 404) panel.demandNote = error.message;
    }
    renderDemand();
    renderGrab();
    onDemand(panel.demand);
  }

  function watch(runId) {
    const poll = setInterval(async () => {
      try {
        const run = await getJson(`/api/runs/${encodeURIComponent(runId)}`);
        el.runStatus.textContent = `${run.state} (${run.phase}) ${run.message || ""}`;
        if (run.state === "done") {
          clearInterval(poll);
          el.run.disabled = false;
          el.runStatus.textContent = "the cable net analysis is in";
          await loadDemand();
          await refresh();
        }
        if (run.state === "failed") {
          clearInterval(poll);
          el.run.disabled = false;
        }
      } catch (error) {
        clearInterval(poll);
        el.run.disabled = false;
        el.runStatus.textContent = `lost contact with the server: ${error.message}`;
      }
    }, 1000);
  }

  async function startRun() {
    const options = studyOptions();
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    el.run.disabled = true;
    el.runStatus.textContent = "starting";
    try {
      const body = { ...sentOptions(options), prestress: Number(el.prestress.value),
                     rope: panel.configuration ? panel.configuration.rope : undefined };
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
      const done = await postJson(`/api/studies/${encodeURIComponent(studyName())}/cablenet/exports`, {
        ...sentOptions(options), configuration: panel.configuration, angle_degrees: ASSUMED_ANGLE_DEGREES,
        ...(wound != null ? { rope_wound_mm: wound } : {}),
      });
      el.result.innerHTML = `<p>Written to ${esc(done.folder)}:</p><ul>` +
        (done.paths || []).map((p) => `<li>${esc(p)}</li>`).join("") + "</ul>" +
        (done.note ? `<p>${esc(done.note)}</p>` : "");
      loadFolder();
    } catch (error) {
      el.result.innerHTML = `<p>${esc(error.message)}</p>`;
    } finally {
      el.exportButton.disabled = !panel.demand;
    }
  }
  el.exportButton.addEventListener("click", runExport);

  async function reload() {
    try {
      await loadParts();
      await loadDemand();
      await refresh();
    } catch (error) {
      el.holds.innerHTML = `<p>The cable net section could not load: ${esc(error.message)}</p>`;
    }
  }

  loadFolder();
  reload();
  return { reload };
}
