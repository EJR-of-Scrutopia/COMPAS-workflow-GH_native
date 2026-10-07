// The chooser: what the build demands, what a set of named parts can give, and
// which part stops it. Its own module because studio.js is 18,597 lines and
// must not grow; fields.js and live_graphs.js set the precedent.
//
// Two rules live here. The slider annotates and never judges: no prototype has
// been built to say what rope speed the net wants, and finding that out is the
// machine's whole purpose, so nothing in this file compares a speed with a
// limit. And a turnbuckle is named by its configuration before its thread,
// because hook/hook M10 is 150 kg and eye/eye M10 is 900 kg.

const FAMILY_NAMES = { A: "closed loop stepper", B: "three phase with inverter",
                       C: "single phase, fixed speed" };

// studyName is a string, or a function returning the current one. The panel
// also re-reads it when the study select changes and when its tab is opened,
// so studio.js needs only the one call.
export function mountCableNet(root, studyName) {
  if (!root) return;
  const currentName = typeof studyName === "function" ? studyName : () => studyName;
  let shownFor = null;
  const show = () => {
    const name = currentName();
    if (name === shownFor) return;
    shownFor = name;
    build(root, name).catch((error) => {
      root.textContent = `The cable net panel could not load: ${error.message}`;
    });
  };
  const select = document.getElementById("study-select");
  if (select) select.addEventListener("change", show);
  for (const tab of document.querySelectorAll('[data-tab="cablenet-panel"]')) {
    tab.addEventListener("click", show);
  }
  show();
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

async function build(root, studyName) {
  root.innerHTML = "";
  if (!studyName) {
    root.textContent = "Open a study to see what its cable net demands.";
    return;
  }
  const parts = await getJson("/api/catalogue");
  let demand = null;
  let demandNote = null;
  try {
    demand = await getJson(`/api/studies/${encodeURIComponent(studyName)}/cablenet`);
  } catch (error) {
    if (error.status !== 404) demandNote = error.message;
  }

  const state = {
    motor: "34HS46", drive: "CL86Y", gearbox: "EG23-G20", drum: "drum-72",
    rope: "rope-4mm", rail: "MGN15H-300", sheave: null, reeve_factor: 1,
    chain: ["eye-M12", "turnbuckle-hook-hook-M10"], speed: 50,
  };

  const demandBox = add(root, "section", "cablenet-demand");
  const partsBox = add(root, "section", "cablenet-parts");
  const speedBox = add(root, "section", "cablenet-speed");
  const verdictBox = add(root, "section", "cablenet-verdict");
  const tableBox = add(root, "section", "cablenet-table");
  const exportBox = add(root, "section", "cablenet-export");

  const floor = demand ? prestressFloor(demand) : 0;
  const shape = demand ? shapeOf(demand) : null;
  const wound = demand ? ropeWound(demand) : null;
  renderDemand(demandBox, demand, floor, demandNote, shape, wound);
  renderExport(exportBox, studyName, demand, () => ({
    // No material, pattern or size is sent: the panel's own demand fetch above
    // uses the same defaults, so the two agree. The day the panel learns to
    // pass them, this export must pass them too.
    configuration: configurationOf(state),
    angle_degrees: ASSUMED_ANGLE_DEGREES,
    ...(wound != null ? { rope_wound_mm: wound } : {}),
  }));
  const rpmReadout = renderSpeed(speedBox, state, annotateSpeed);
  renderParts(partsBox, parts, state, refresh);

  let ticket = 0;
  // The rungs come from the server (one definition, shared with the exports).
  // Fetched once per configuration change; null means unavailable, and there
  // is deliberately no hardcoded fallback, which would restore the drift.
  let rungs = null;
  let rungsFor = null;
  async function loadRungs() {
    const key = JSON.stringify(configurationOf(state));
    if (key === rungsFor) return;
    rungsFor = null;
    rungs = null;
    try {
      const got = await getJson("/api/cablenet/ladder", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ configuration: configurationOf(state) }) });
      rungs = got.rungs;
      rungsFor = key;
    } catch (error) {
      rungs = null;
    }
  }

  async function score() {
    await loadRungs();
    const body = {
      configurations: [configurationOf(state), ...(rungs || [])],
      angle_degrees: ASSUMED_ANGLE_DEGREES,
      prestress_floor: floor,
      rope_speed_mm_s: state.speed,
    };
    // The drum and rail checks only run when the server is told how much rope
    // the build winds. Without a demand document there is nothing to send.
    if (wound != null) body.rope_wound_mm = wound;
    return getJson(
      `/api/studies/${encodeURIComponent(studyName)}/cablenet/configurations`,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) });
  }

  // The parts changed: the verdict and the table are redrawn.
  async function refresh() {
    const mine = ++ticket;
    try {
      const scored = await score();
      if (mine !== ticket) return;
      renderVerdict(verdictBox, scored.rows[0], floor, parts, shape, demand);
      renderTable(tableBox, scored.rows, parts, rungs !== null);
      showRpm(rpmReadout, state.speed, scored.rows[0]);
    } catch (error) {
      verdictBox.textContent = `The numbers could not be fetched: ${error.message}`;
    }
  }

  // The slider moved: only the rpm readout is touched. The verdict and the
  // table are not redrawn, so the slider cannot change either.
  async function annotateSpeed() {
    const mine = ++ticket;
    try {
      const scored = await score();
      if (mine !== ticket) return;
      showRpm(rpmReadout, state.speed, scored.rows[0]);
    } catch (error) {
      rpmReadout.textContent = `${state.speed} mm/s (no rpm: ${error.message})`;
    }
  }

  await refresh();
}

function add(parent, tag, className) {
  const node = document.createElement(tag);
  node.className = className;
  parent.appendChild(node);
  return node;
}

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function money(value) {
  return `£${Number(value).toFixed(2)}`;
}

// The wire's angle to its eye bolt's axis is not recorded in the export, so
// this is an assumption, not a computed figure. It selects the bolt's off-axis
// rating, which is the conservative direction.
const ASSUMED_ANGLE_DEGREES = 10.0;

// Whether the net keeps its shape. Deviation is a property of the vault, the
// wires and the prestress; the chosen parts cannot move it.
function shapeOf(demand) {
  const stages = demand.stages || [];
  let worst = null;
  let allReachable = true;
  for (const stage of stages) {
    if (stage.reachable !== true) allReachable = false;
    const residual = Number(stage.residual_after);
    if (Number.isFinite(residual) && (worst === null || residual > worst.residual)) {
      worst = { residual, name: stage.name == null ? stage.stage : stage.name };
    }
  }
  const acceptance = demand.acceptance == null ? null : Number(demand.acceptance);
  const known = stages.length > 0 && worst !== null;
  const withinLine = acceptance == null || (worst !== null && worst.residual <= acceptance);
  return {
    known, worst, allReachable, acceptance,
    holds: known && allReachable && withinLine,
  };
}

// Total rope one wire winds over the whole build, taken at the worst wire.
function ropeWound(demand) {
  const totals = [];
  for (const stage of demand.stages || []) {
    (stage.wire_reel_commands || []).forEach((command, wire) => {
      totals[wire] = (totals[wire] || 0) + Math.abs(Number(command) || 0);
    });
  }
  return totals.length ? Math.max(...totals) : null;
}

function prestressFloor(demand) {
  let worst = 0;
  for (const stage of demand.stages || []) {
    for (const tension of stage.wire_tensions || []) worst = Math.max(worst, tension);
  }
  return worst;
}

function configurationOf(state) {
  const { speed, ...configuration } = state;
  return { ...configuration, chain: [...configuration.chain] };
}

// the configuration first, then the thread, then the load: the configuration
// is where the six-fold difference lives
function turnbuckleLabel(parts, key) {
  const entry = parts.turnbuckle[key];
  if (!entry) return key;
  return `${entry.configuration.toUpperCase()} ${entry.thread}, ` +
    `${entry.working_load_kg} kg working load`;
}

function renderDemand(box, demand, floor, note, shape, wound) {
  if (!demand) {
    box.textContent = note
      ? `The cable net demand could not be read: ${note}`
      : "This study has no cable net demand yet. Run it with the cable net " +
        "phase enabled and the numbers below will have something to answer.";
    return;
  }
  const acceptance = demand.acceptance == null
    ? "The acceptance line is not set for this run."
    : `The acceptance line is ${Number(demand.acceptance).toFixed(2)} mm` +
      (demand.acceptance_source ? `, from ${esc(demand.acceptance_source)}.` : ".");
  box.innerHTML =
    `<h3>What the build demands</h3>` +
    `<p>The greatest tension any wire must carry is ` +
    `<strong>${floor.toFixed(0)} N</strong>, at stage ` +
    `${esc(demand.sizing_stage)}. That is a property of the vault and the skin, so ` +
    `it does not move when parts change.</p><p>${acceptance}</p>` +
    (shape && shape.known
      ? `<p>The worst the net misses its shape after correction is ` +
        `<strong>${shape.worst.residual.toFixed(2)} mm</strong>, at stage ` +
        `${esc(shape.worst.name)}` +
        `${shape.allReachable ? "" : ", and at least one stage cannot be corrected at all"}. ` +
        `That is a property of the vault, the wires and the prestress, so ` +
        `it does not move when parts change.</p>`
      : "") +
    (wound == null ? "" :
      `<p>The worst wire winds ${wound.toFixed(0)} mm of rope in total. ` +
      `That too comes from the vault and not the parts.</p>`);
}

function renderParts(box, parts, state, refresh) {
  box.innerHTML = "<h3>The parts</h3>";
  const kinds = [
    ["motor", "Motor"], ["drive", "Drive"], ["gearbox", "Gearbox"],
    ["drum", "Drum"], ["rope", "Rope"], ["rail", "Rail"],
  ];
  for (const [kind, label] of kinds) {
    const select = document.createElement("select");
    for (const [key, entry] of Object.entries(parts[kind])) {
      const option = document.createElement("option");
      option.value = key;
      const family = entry.family ? ` (${FAMILY_NAMES[entry.family]})` : "";
      const price = entry.unit_price == null
        ? "no price yet" : money(entry.unit_price);
      option.textContent = `${entry.model || key}${family}, ${price}, ` +
        `${entry.confidence}`;
      option.selected = state[kind] === key;
      select.appendChild(option);
    }
    select.onchange = () => { state[kind] = select.value; refresh(); };
    const row = add(box, "label", "cablenet-field");
    row.textContent = label + " ";
    row.appendChild(select);
  }

  const turnbuckle = document.createElement("select");
  for (const key of Object.keys(parts.turnbuckle)) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = turnbuckleLabel(parts, key);
    option.selected = state.chain[1] === key;
    turnbuckle.appendChild(option);
  }
  turnbuckle.onchange = () => {
    state.chain = [state.chain[0], turnbuckle.value];
    refresh();
  };
  const turnRow = add(box, "label", "cablenet-field");
  turnRow.textContent = "Turnbuckle ";
  turnRow.appendChild(turnbuckle);

  const eye = document.createElement("select");
  for (const [key, entry] of Object.entries(parts.eye_bolt)) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = `${entry.thread} eye bolt, ${entry.angled_kg} kg at an angle`;
    option.selected = state.chain[0] === key;
    eye.appendChild(option);
  }
  eye.onchange = () => {
    state.chain = [eye.value, state.chain[1]];
    refresh();
  };
  const eyeRow = add(box, "label", "cablenet-field");
  eyeRow.textContent = "Eye bolt ";
  eyeRow.appendChild(eye);

  const pulley = document.createElement("input");
  pulley.type = "checkbox";
  pulley.checked = state.reeve_factor > 1;
  pulley.onchange = () => {
    state.reeve_factor = pulley.checked ? 2 : 1;
    state.sheave = pulley.checked ? Object.keys(parts.sheave)[0] : null;
    refresh();
  };
  const pulleyRow = add(box, "label", "cablenet-field");
  pulleyRow.textContent =
    "Moving block: halves the force at the drum and doubles it through the sheave ";
  pulleyRow.appendChild(pulley);
}

// Returns the element the rpm annotation is written into.
function renderSpeed(box, state, annotate) {
  box.innerHTML = "<h3>Rope speed</h3>";
  const slider = add(box, "input", "cablenet-slider");
  slider.type = "range";
  slider.min = "1";
  slider.max = "400";
  slider.value = String(state.speed);
  const readout = add(box, "span", "cablenet-rpm");
  readout.textContent = ` ${state.speed} mm/s`;
  let timer = null;
  slider.oninput = () => {
    state.speed = Number(slider.value);
    readout.textContent = ` ${state.speed} mm/s`;
    clearTimeout(timer);
    timer = setTimeout(annotate, 120);
  };
  const note = add(box, "p", "cablenet-note");
  note.textContent =
    "Nothing here passes or fails. No prototype has been built to say what " +
    "rate the net wants, and finding that out is what the machine is for.";
  return readout;
}

// Annotation only: a number and its unit, never a comparison.
function showRpm(readout, speed, row) {
  const rpm = row && !row.refused ? row.motor_rpm_for_wanted_speed : null;
  readout.textContent = rpm == null
    ? ` ${speed} mm/s`
    : ` ${speed} mm/s is ${rpm.toFixed(0)} rpm at the motor with this gearbox and drum`;
}

function renderVerdict(box, row, floor, parts, shape, demand) {
  if (!row || row.refused) {
    box.innerHTML =
      `<h3>The verdict</h3><p>${row ? esc(row.refused) : "No answer."}</p>`;
    return;
  }
  const bound = parts.turnbuckle[row.binding]
    ? turnbuckleLabel(parts, row.binding) : row.binding;
  const path = row.rope_path || null;

  // Holding is two questions: can the parts carry the tension, and does the
  // net stay within the acceptance line. Say which half failed. Every entry
  // in reasons is HTML; only numbers and escaped names go into it.
  let verdict;
  const reasons = [];
  if (!(floor > 0)) {
    verdict = "No demand to compare against yet.";
  } else {
    // not row.passes: the server folds the drum and rail checks into it
    const carries = row.ceiling >= floor;
    const pathOk = !path || (path.drum_fits && path.rail_fits);
    const shapeOk = !shape || !shape.known || shape.holds;
    verdict = carries && pathOk && shapeOk ? "It holds." : "It does not hold.";
    if (carries) {
      reasons.push("The parts can carry the tension.");
    } else {
      reasons.push(`The parts cannot carry the tension: the ceiling is ` +
        `${row.ceiling.toFixed(0)} N against ${floor.toFixed(0)} N demanded.`);
    }
    if (path && !path.drum_fits) {
      reasons.push(`The rope does not fit the drum in one layer (` +
        `${path.rope_wound_mm.toFixed(0)} mm against ` +
        `${path.drum_capacity_mm.toFixed(0)} mm). A second layer changes the ` +
        `effective radius, so every torque figure here would be wrong.`);
    }
    if (path && !path.rail_fits) {
      reasons.push(`The carriage would travel ${path.carriage_travel_mm.toFixed(0)} mm ` +
        `but the rail's stroke is ${path.rail_stroke_mm.toFixed(0)} mm.`);
    }
    if (shape && shape.known) {
      const line = shape.acceptance == null ? "no acceptance line set"
        : `${shape.acceptance.toFixed(2)} mm acceptance line`;
      if (!shape.holds) {
        const how = shape.allReachable ? "" :
          " and at least one stage cannot be corrected at all";
        reasons.push(`The net misses the shape by ${shape.worst.residual.toFixed(2)} mm ` +
          `at stage ${esc(shape.worst.name)} against a ${line}${how}. ` +
          `This comes from the vault, the wires and the prestress, so no ` +
          `change of parts here will cure it.`);
      } else {
        reasons.push(`The net stays within the shape: the worst miss is ` +
          `${shape.worst.residual.toFixed(2)} mm against a ${line}.`);
      }
    } else if (!demand || !shape || !shape.known) {
      reasons.push("The shape of the net could not be checked.");
    }
  }
  box.innerHTML =
    `<h3>The verdict</h3>` +
    `<p><strong>${verdict}</strong> ${reasons.join(" ")}</p>` +
    `<p>The ceiling is ` +
    `${row.ceiling.toFixed(0)} N, set by ${esc(bound)}.` +
    (row.margin == null ? "" : ` That is ${row.margin.toFixed(2)} times the demand.`) +
    `</p>` +
    `<p class="cablenet-note">The eye bolt is rated at its off-axis figure ` +
    `(${ASSUMED_ANGLE_DEGREES.toFixed(0)} degrees) because the wire's angle to the ` +
    `bolt is not recorded in the export. This is an assumption. A bolt genuinely ` +
    `loaded along its axis would be stronger.</p>` +
    ropeHtml(path) +
    (row.rope_speed_mm_s
      ? `<p>This drive runs the rope at ${row.rope_speed_mm_s.toFixed(0)} mm/s.</p>`
      : `<p>A stepper is commanded as fast or as slow as wanted. Check the ` +
        `rpm beside the slider against the motor's torque curve: the derate ` +
        `used here is a flat one.</p>`) +
    `<p>${row.price.is_floor
      ? `At least ${money(row.price.pounds)}; ` +
        `${row.price.unpriced.length === 1 ? "one part has" :
          `${row.price.unpriced.length} parts have`} no price yet ` +
        `(${esc(row.price.unpriced.join(", "))}).`
      : `${money(row.price.pounds)}.`}</p>`;
}

function ropeHtml(path) {
  if (!path) return "";
  const mark = (ok) => (ok ? "PASS" : "FAIL");
  const ratio = path.sheave_over_rope_diameter;
  return `<h4>Rope</h4><ul>` +
    `<li><strong>${mark(path.drum_fits)}</strong> Rope on the drum: ` +
    `${path.rope_wound_mm.toFixed(0)} mm wound against ` +
    `${path.drum_capacity_mm.toFixed(0)} mm of single-layer capacity ` +
    `(${path.drum_capacity_wraps} wraps).` +
    (path.drum_fits ? "" :
      " Past this a second layer starts and the torque figures are invalid.") +
    `</li>` +
    `<li><strong>${mark(path.rail_fits)}</strong> Carriage travel: ` +
    `${path.carriage_travel_mm.toFixed(0)} mm against a rail stroke of ` +
    `${path.rail_stroke_mm.toFixed(0)} mm.</li>` +
    `<li>Sheave to rope diameter ratio: ` +
    `${ratio == null ? "no sheave chosen" : ratio.toFixed(1)}. ` +
    `This is a bare number and carries no verdict, because the minimum it ` +
    `should meet is not confirmed.</li></ul>`;
}

function renderTable(box, rows, parts, ladderKnown) {
  box.innerHTML = "<h3>What the next change would buy</h3>";
  if (!ladderKnown) {
    const missing = add(box, "p", "cablenet-error");
    missing.textContent = "The upgrade ladder is unavailable: the server did not " +
      "return the rungs, so only the chosen set is shown.";
  }
  const table = document.createElement("table");
  table.innerHTML =
    "<tr><th>Turnbuckle</th><th>Rope</th><th>Ceiling</th>" +
    "<th>Bound by</th><th>Price</th></tr>";
  // row 0 is the chosen set; the rest are the ladder
  rows.forEach((row, index) => {
    const cells = document.createElement("tr");
    if (row.refused) {
      cells.innerHTML = `<td colspan="5">${esc(row.refused)}</td>`;
    } else {
      const configuration = row.configuration;
      cells.innerHTML =
        `<td>${index === 0 ? "chosen: " : ""}` +
        `${esc(turnbuckleLabel(parts, configuration.chain[1]))}</td>` +
        `<td>${esc(configuration.rope)}</td>` +
        `<td>${row.ceiling.toFixed(0)} N</td><td>${esc(row.binding)}</td>` +
        `<td>${row.price.is_floor ? "from " : ""}${money(row.price.pounds)}</td>`;
    }
    table.appendChild(cells);
  });
  box.appendChild(table);
}

// The export section: where the three documents go, and the button that
// writes them. Every string from the server goes through esc().
function renderExport(box, studyName, demand, bodyOf) {
  box.innerHTML = "<h3>Export</h3>";
  const folderLine = add(box, "p", "cablenet-export-folder");
  const choose = add(box, "button", "cablenet-export-choose");
  choose.type = "button";
  choose.textContent = "Choose folder";
  const exportButton = add(box, "button", "cablenet-export-run");
  exportButton.type = "button";
  exportButton.textContent = "Export";
  const reason = add(box, "span", "cablenet-note");
  const result = add(box, "div", "cablenet-export-result");

  const showFolder = (row) => {
    folderLine.innerHTML = row && row.path
      ? `Exports are saved to <strong>${esc(row.path)}</strong>` +
        `${row.exists ? "" : " (this folder is not there)"}.`
      : "No export folder is set.";
  };
  const showError = (error) => {
    result.innerHTML = `<p class="cablenet-error">${esc(error.message)}</p>`;
  };
  const loadFolder = async () => {
    try {
      showFolder(await getJson("/api/cablenet/exports/folder"));
    } catch (error) {
      folderLine.textContent = `The export folder could not be read: ${error.message}`;
    }
  };

  if (!demand) {
    exportButton.disabled = true;
    reason.textContent = " This study has no cable net demand, so there is " +
      "nothing to describe.";
  }

  choose.onclick = async () => {
    choose.disabled = true;
    try {
      const browsed = await getJson("/api/cablenet/exports/folder/browse",
        { method: "POST" });
      // A cancelled dialog returns no path and must change nothing.
      if (browsed && browsed.path) {
        const row = await getJson("/api/cablenet/exports/folder", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: browsed.path }) });
        showFolder(row);
        result.innerHTML = "";
      }
    } catch (error) {
      showError(error);
    } finally {
      choose.disabled = false;
    }
  };

  exportButton.onclick = async () => {
    exportButton.disabled = true;
    result.textContent = "Writing the documents...";
    try {
      const done = await getJson(
        `/api/studies/${encodeURIComponent(studyName)}/cablenet/exports`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(bodyOf()) });
      const files = (done.paths || []).map((path) => `<li>${esc(path)}</li>`).join("");
      result.innerHTML =
        `<p>Written to ${esc(done.folder)}:</p><ul>${files}</ul>` +
        (done.note ? `<p class="cablenet-note">${esc(done.note)}</p>` : "");
      loadFolder();
    } catch (error) {
      showError(error);
    } finally {
      exportButton.disabled = !demand;
    }
  };

  loadFolder();
}
