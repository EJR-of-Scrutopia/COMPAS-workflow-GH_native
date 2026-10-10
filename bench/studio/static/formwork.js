// The Formwork tab's controller (spec 2026-10-10 formwork tab): it runs the
// formwork engine, fetches its captures, plays them, and fills the section and
// the worst pop-up from formwork_model.js. studio.js hands it the study, the
// Cable net tab's machine, the drawing (formwork_view.js) and its own hooks;
// this file touches no three.js. A tool, not a text: numbers, marks, tables.

import {
  captureLabel, captureTimes, colourKey, formworkLabels, formworkPickHtml, formworkWarnings,
  frameLine, frameLineHtml, playhead, readSim, worstHtml, worstTables,
} from "./formwork_model.js";
import { spreadLabels } from "./cablenet_model.js";

// As the Cable net tab's labels and card (studio.js).
const LABEL_MAX = 125;
const LABEL_GAP_X = 44;
const LABEL_GAP_Y = 16;
const CARD_WIDTH = 220;
const CARD_CLEAR_BOTTOM = 70;

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

// The study's options as the cable net demand is keyed: a null or empty value
// is left out.
function sentOptions(options) {
  const sent = {};
  for (const [key, value] of Object.entries(options || {})) {
    if (value != null && value !== "") sent[key] = value;
  }
  return sent;
}

function simUrl(studyName, options) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(sentOptions(options))) query.set(key, String(value));
  return `/api/studies/${encodeURIComponent(studyName)}/formwork/sim?${query.toString()}`;
}

// hooks: enter() and leave() (the studio's timeline and objects), legend(key)
// (null hides it), showMachine(on), aim(point), camera(), canvasRect(),
// viewRight(), onPopup().
export function mountFormwork({ studyName, studyOptions, machine, designPrestress, tolerance, view,
                                hooks }) {
  const el = {
    run: byId("formwork-run"), runStatus: byId("formwork-run-status"),
    machine: byId("formwork-machine"), wall: byId("formwork-wall"),
    wallValue: byId("formwork-wall-value"), scrub: byId("formwork-scrub"),
    scrubValue: byId("formwork-scrub-value"), speed: byId("formwork-speed"),
    speedValue: byId("formwork-speed-value"), back: byId("formwork-back"),
    play: byId("formwork-play"), on: byId("formwork-on"), label: byId("formwork-label"),
    line: byId("formwork-line"), show: byId("formwork-show"), colour: byId("formwork-colour"),
    labelTicks: byId("formwork-label-ticks"), worstToggle: byId("formwork-worst-toggle"),
    warnings: byId("formwork-warnings"), popup: byId("formwork-popup"),
    popupClose: byId("formwork-popup-close"), worst: byId("formwork-worst"),
    labels: byId("formwork-labels"), pick: byId("formwork-pick"),
  };
  const api = { active: () => false, setActive: () => {}, tick: () => {}, place: () => {},
                pick: () => {}, clear: () => {}, reload: () => {}, refresh: () => {},
                closePopup: () => {} };
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    console.warn(`the formwork section is not on this page: no element for ${missing.join(", ")}`);
    return api;
  }
  const tabs = [...document.querySelectorAll("#formwork-tabs [data-fw-tab]")];

  // A ticket keeps a late document from overwriting a newer one, or the
  // emptiness of a study that has gone; watcher is the interval watching a run.
  const tab = {
    active: false, sim: null, times: [], at: 0, playing: false, speed: 1,
    worst: null, part: "ropes", sort: { key: "value", descending: true },
    ticket: 0, watcher: null, items: [], pickNode: null, shown: -1, settingsKey: "",
  };

  function settings() {
    const show = {};
    for (const box of el.show.querySelectorAll("input[data-show]")) show[box.dataset.show] = box.checked;
    const picked = el.colour.querySelector("input[name=formwork-colour]:checked");
    const labels = [...el.labelTicks.querySelectorAll("input[data-label]")]
      .filter((box) => box.checked).map((box) => box.dataset.label);
    return { show, colour: picked ? picked.value : "off", labels, tolerance: Number(tolerance()) };
  }

  // The machine the Cable net tab chose, one a study (the owner's answer of
  // 10 October 2026), with the Wall dial and the cable net run's prestress.
  function chosen() {
    const choices = machine();
    return { rope: choices ? choices.rope : null,
             wires_per_motor: choices ? choices.wires_per_motor : 1,
             pulleys: choices ? choices.pulley != null : true,
             wall: Number(el.wall.value), prestress: designPrestress() };
  }

  function renderMachine() {
    const c = chosen();
    const name = c.rope == null ? "none chosen"
      : `${esc(c.rope)}, ${c.wires_per_motor} a motor, ${c.pulleys ? "pulleys" : "no pulleys"}`;
    const prestress = c.prestress == null ? "Run cable net analysis" : `${Number(c.prestress).toFixed(1)} N`;
    el.machine.innerHTML = `<table class="cablenet-answers"><tr><th>Machine</th><td>${name}</td></tr>`
      + `<tr><th>Prestress</th><td>${prestress}</td></tr></table>`;
  }

  function renderWarnings() {
    el.warnings.innerHTML = formworkWarnings(tab.sim, chosen())
      .map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
  }

  function renderWorst() {
    if (el.popup.classList.contains("hidden")) return;
    for (const button of tabs) button.classList.toggle("active", button.dataset.fwTab === tab.part);
    el.worst.innerHTML = tab.sim && tab.worst
      ? worstHtml(tab.part, tab.worst[tab.part], tab.sim, tab.sort)
      : `<div class="cablenet-warning">No formwork run: Run formwork analysis</div>`;
  }

  // The labels for the capture shown, rebuilt when the capture or the ticks
  // change; placed every frame (place).
  function rebuildLabels(index, kinds) {
    el.labels.innerHTML = "";
    tab.items = [];
    if (!tab.sim || !tab.active) return;
    for (const target of formworkLabels(tab.sim, index, kinds).slice(0, LABEL_MAX)) {
      const label = document.createElement("div");
      label.className = "model-label";
      label.textContent = target.text;
      el.labels.appendChild(label);
      tab.items.push({ label, target });
    }
  }

  // The capture the player is at, drawn: the positions blended, every number
  // the nearer capture's.
  function draw(force = false) {
    if (!tab.sim || !tab.active) return;
    const head = playhead(tab.times, tab.at);
    if (!head) return;
    const now = settings();
    view.show(head, now);
    hooks.showMachine(!!now.show.wires);
    const key = JSON.stringify(now);
    const changed = force || key !== tab.settingsKey;
    if (changed) hooks.legend(colourKey(now.colour, tab.sim, now.tolerance));
    if (changed || head.nearer !== tab.shown) {
      const capture = tab.sim.captures[head.nearer];
      el.label.textContent = captureLabel(capture);
      el.scrubValue.textContent = String(head.nearer + 1);
      if (document.activeElement !== el.scrub) el.scrub.value = String(head.nearer + 1);
      el.line.innerHTML = frameLineHtml(frameLine(tab.sim, head.nearer));
      rebuildLabels(head.nearer, now.labels);
      if (tab.pickNode != null) el.pick.innerHTML = formworkPickHtml(tab.sim, head.nearer, tab.pickNode);
      tab.shown = head.nearer;
      tab.settingsKey = key;
    }
  }

  function end() {
    return tab.times.length ? tab.times[tab.times.length - 1] : 0;
  }

  function setPlaying(on) {
    tab.playing = !!on && !!tab.sim;
    el.play.textContent = tab.playing ? "Pause" : "Play";
  }

  function goTo(index) {
    if (!tab.sim) return;
    const i = Math.min(Math.max(index, 0), tab.times.length - 1);
    tab.at = tab.times[i];
    setPlaying(false);
    draw();
  }

  function step(by) {
    const head = playhead(tab.times, tab.at);
    if (head) goTo(head.nearer + by);
  }

  el.play.addEventListener("click", () => {
    if (!tab.sim) return;
    if (!tab.playing && tab.at >= end()) tab.at = 0;
    setPlaying(!tab.playing);
  });
  el.back.addEventListener("click", () => step(-1));
  el.on.addEventListener("click", () => step(1));
  el.scrub.addEventListener("input", () => goTo(Number(el.scrub.value) - 1));
  el.speed.addEventListener("input", () => {
    tab.speed = Number(el.speed.value);
    el.speedValue.textContent = tab.speed.toFixed(2);
  });
  el.wall.addEventListener("input", () => {
    el.wallValue.textContent = Number(el.wall.value).toFixed(1);
    renderWarnings();
  });
  for (const holder of [el.show, el.colour, el.labelTicks]) {
    holder.addEventListener("change", () => draw(true));
  }

  // The worst tables on the left (spec section 10), one tab a part.
  function setPopup(open) {
    el.popup.classList.toggle("hidden", !open);
    el.worstToggle.classList.toggle("active", open);
    if (open) hooks.onPopup();
    renderWorst();
  }

  el.worstToggle.addEventListener("click", () => setPopup(el.popup.classList.contains("hidden")));
  el.popupClose.addEventListener("click", () => setPopup(false));
  for (const button of tabs) {
    button.addEventListener("click", () => {
      tab.part = button.dataset.fwTab;
      tab.sort = { key: "value", descending: true };
      renderWorst();
    });
  }

  // A header sorts by its column, again the other way; a row moves the player
  // to its capture and turns the camera onto its part.
  el.worst.addEventListener("click", (event) => {
    const header = event.target.closest("th[data-sort]");
    if (header) {
      const key = header.dataset.sort;
      tab.sort = key === tab.sort.key ? { key, descending: !tab.sort.descending }
        : { key, descending: key !== "index" };
      renderWorst();
      return;
    }
    const row = event.target.closest("tr[data-capture]");
    if (!row || !tab.sim) return;
    goTo(Number(row.dataset.capture));
    hooks.aim(view.point({ kind: row.dataset.kind, index: Number(row.dataset.index) }));
  });

  // Every frame while the tab is open: the player's clock.
  function tick(seconds) {
    if (!tab.active || !tab.playing) return;
    tab.at = Math.min(tab.at + seconds * tab.speed, end());
    if (tab.at >= end()) setPlaying(false);
    draw();
  }

  function placeCard(x, y) {
    el.pick.style.left = Math.round(Math.min(hooks.viewRight() - CARD_WIDTH, x + 14)) + "px";
    el.pick.style.top = Math.round(Math.max(12,
      Math.min(innerHeight - el.pick.offsetHeight - CARD_CLEAR_BOTTOM, y - 20))) + "px";
  }

  // Every render: each label where its part is on screen, the largest of a
  // crowd kept; the card beside its node, shut when the node leaves the view.
  function place() {
    if (!tab.active) return;
    const camera = hooks.camera();
    const rect = hooks.canvasRect();
    const right = hooks.viewRight();
    if (tab.items.length) {
      const points = tab.items.map((item) => {
        const p = view.project(view.point(item.target), camera, rect);
        return p && p[0] < right ? p : null;
      });
      const shown = spreadLabels(points, LABEL_GAP_X, LABEL_GAP_Y);
      tab.items.forEach((item, i) => {
        item.label.style.display = shown[i] ? "" : "none";
        if (shown[i]) {
          item.label.style.left = points[i][0] + "px";
          item.label.style.top = points[i][1] + "px";
        }
      });
    }
    if (tab.pickNode != null) {
      const p = view.project(view.point({ kind: "node", index: tab.pickNode }), camera, rect);
      if (!p || p[0] >= right) {
        el.pick.classList.add("hidden");
        tab.pickNode = null;
      } else {
        placeCard(p[0], p[1]);
      }
    }
  }

  // A click on a node shows its numbers beside it; a click anywhere else
  // closes the card. studio.js hands over the clicks a drag, a stamp or a tool
  // has not taken.
  function pick(event) {
    el.pick.classList.add("hidden");
    tab.pickNode = null;
    if (!tab.active || !tab.sim) return;
    const node = view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY);
    if (node == null) return;
    const head = playhead(tab.times, tab.at);
    el.pick.innerHTML = formworkPickHtml(tab.sim, head.nearer, node);
    el.pick.classList.remove("hidden");
    tab.pickNode = node;
    place();
  }

  // The study's capture document, read once: none yet is said so.
  async function load() {
    const mine = ++tab.ticket;
    const options = studyOptions();
    let sim = null;
    if (options && studyName()) {
      try {
        sim = readSim(await getJson(simUrl(studyName(), options)));
      } catch (error) {
        if (error.status !== 404) el.runStatus.textContent = error.message;
      }
    }
    if (mine !== tab.ticket) return;
    tab.sim = sim;
    tab.times = sim ? captureTimes(sim.captures) : [];
    tab.worst = sim ? worstTables(sim) : null;
    tab.at = 0;
    tab.shown = -1;
    setPlaying(false);
    el.scrub.max = String(Math.max(1, tab.times.length));
    el.scrub.value = "1";
    el.scrubValue.textContent = "1";
    el.scrubValue.nextElementSibling.textContent = `of ${Math.max(1, tab.times.length)}`;
    view.build(sim);
    if (!sim) {
      el.label.textContent = "";
      el.line.innerHTML = "";
      el.labels.innerHTML = "";
      tab.items = [];
      hooks.legend(null);
    }
    renderWarnings();
    renderWorst();
    draw(true);
  }

  function stopWatching() {
    if (tab.watcher != null) clearInterval(tab.watcher);
    tab.watcher = null;
  }

  function watch(runId) {
    stopWatching();
    const poll = setInterval(async () => {
      try {
        const run = await getJson(`/api/runs/${encodeURIComponent(runId)}`);
        if (tab.watcher !== poll) return;
        el.runStatus.textContent = run.of > 0 ? `capture ${run.stage} of ${run.of}`
          : `${run.state} (${run.phase})`;
        if (run.state === "done") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = "";
          await load();
        }
        if (run.state === "failed") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = run.message;
        }
      } catch (error) {
        if (tab.watcher !== poll) return;
        stopWatching();
        el.run.disabled = false;
        el.runStatus.textContent = error.message;
      }
    }, 1000);
    tab.watcher = poll;
  }

  // The run takes the cable net run's prestress at the server; the tab sends
  // the cut, the machine and the wall, and never a prestress.
  async function startRun() {
    const options = studyOptions();
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    const c = chosen();
    el.run.disabled = true;
    el.runStatus.textContent = "starting: about two minutes";
    try {
      const body = { ...sentOptions(options), wires_per_motor: c.wires_per_motor,
                     pulleys: c.pulleys, wall: c.wall };
      if (c.rope != null) body.rope = c.rope;
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      let started = null;
      try { started = await response.json(); } catch (_) { started = null; }
      if (response.status === 409) {
        const live = await getJson(`/api/runs/${encodeURIComponent(started.run)}`);
        if (live.kind === "formwork") {
          watch(started.run);
        } else {
          el.runStatus.textContent = `a ${live.kind} run is live on this study`;
          el.run.disabled = false;
        }
        return;
      }
      if (!response.ok) {
        el.runStatus.textContent = started && started.detail ? started.detail : `HTTP ${response.status}`;
        el.run.disabled = false;
        return;
      }
      watch(started.run);
    } catch (error) {
      el.runStatus.textContent = error.message;
      el.run.disabled = false;
    }
  }
  el.run.addEventListener("click", startRun);

  // The tab opened or left (studio.js activateTab).
  function setActive(on) {
    if (on === tab.active) return;
    tab.active = on;
    document.body.classList.toggle("formwork-open", on);
    if (on) {
      hooks.enter();
      renderMachine();
      if (!tab.sim) load();
      else draw(true);
      renderWarnings();
      return;
    }
    setPlaying(false);
    setPopup(false);
    el.labels.innerHTML = "";
    tab.items = [];
    el.pick.classList.add("hidden");
    tab.pickNode = null;
    tab.shown = -1;
    hooks.legend(null);
    hooks.leave();
  }

  // The study on screen is going: nothing the tab holds describes it.
  function clear() {
    tab.ticket += 1;
    stopWatching();
    tab.sim = null;
    tab.times = [];
    tab.worst = null;
    tab.pickNode = null;
    tab.items = [];
    setPlaying(false);
    view.build(null);
    el.labels.innerHTML = "";
    el.pick.classList.add("hidden");
    el.line.innerHTML = "";
    el.label.textContent = "";
    el.runStatus.textContent = "";
    el.run.disabled = false;
    renderWorst();
  }

  function reload() {
    clear();
    renderMachine();
    renderWarnings();
    if (tab.active) load();
  }

  function refresh() {
    renderMachine();
    renderWarnings();
  }

  return { active: () => tab.active, setActive, tick, place, pick, clear, reload, refresh,
           closePopup: () => setPopup(false) };
}
