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

  const floor = demand ? prestressFloor(demand) : 0;
  renderDemand(demandBox, demand, floor, demandNote);
  const rpmReadout = renderSpeed(speedBox, state, annotateSpeed);
  renderParts(partsBox, parts, state, refresh);

  let ticket = 0;
  async function score() {
    const body = {
      configurations: [configurationOf(state), ...ladder(state)],
      angle_degrees: 10.0,
      prestress_floor: floor,
      rope_speed_mm_s: state.speed,
    };
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
      renderVerdict(verdictBox, scored.rows[0], floor, parts);
      renderTable(tableBox, scored.rows, parts);
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

// the upgrade ladder, so the panel always shows what the next change would buy
function ladder(state) {
  const rungs = [
    { chain: ["eye-M12", "turnbuckle-eye-eye-M10"] },
    { chain: ["eye-M12", "turnbuckle-eye-eye-M10"], rope: "rope-5mm" },
    { chain: ["eye-M16", "turnbuckle-eye-eye-M10"], rope: "rope-6mm" },
    { chain: ["eye-M20", "turnbuckle-eye-eye-M12"], rope: "rope-8mm" },
  ];
  return rungs.map((rung) => ({ ...configurationOf(state), ...rung }));
}

// the configuration first, then the thread, then the load: the configuration
// is where the six-fold difference lives
function turnbuckleLabel(parts, key) {
  const entry = parts.turnbuckle[key];
  if (!entry) return key;
  return `${entry.configuration.toUpperCase()} ${entry.thread}, ` +
    `${entry.working_load_kg} kg working load`;
}

function renderDemand(box, demand, floor, note) {
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
    `it does not move when parts change.</p><p>${acceptance}</p>`;
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

function renderVerdict(box, row, floor, parts) {
  if (!row || row.refused) {
    box.innerHTML =
      `<h3>The verdict</h3><p>${row ? esc(row.refused) : "No answer."}</p>`;
    return;
  }
  const verdict = floor > 0
    ? (row.passes ? "It holds." : "It does not hold.")
    : "No demand to compare against yet.";
  const bound = parts.turnbuckle[row.binding]
    ? turnbuckleLabel(parts, row.binding) : row.binding;
  box.innerHTML =
    `<h3>The verdict</h3>` +
    `<p><strong>${verdict}</strong> The ceiling is ` +
    `${row.ceiling.toFixed(0)} N, set by ${esc(bound)}.` +
    (row.margin == null ? "" : ` That is ${row.margin.toFixed(2)} times the demand.`) +
    `</p>` +
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

function renderTable(box, rows, parts) {
  box.innerHTML = "<h3>What the next change would buy</h3>";
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
