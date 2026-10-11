// The one Cable net tab's controller (spec 2026-10-11 one Cable net tab): it
// runs the physics engine with the mechanism chosen in the pop-up
// (mechanism_pick.js), fetches the run's captures, plays them, gives the
// answer, and fills the section from formwork_model.js. studio.js hands it the
// study, the mechanism pop-up, the drawing (formwork_view.js) and its own
// hooks; this file touches no three.js. A tool, not a text: numbers, marks,
// tables.

import {
  answer, answerHtml, captureLabel, captureTimes, colourKey, formworkPickHtml, modelLabels,
  formworkWarnings, frameLine, frameLineHtml, labelsShown, liveAnswer, nextScene, paintOverlay,
  playhead, readSim, recordingCaption, weakestAt, withWall,
} from "./formwork_model.js";
import { spreadLabels } from "./labels.js";
import { costHtml, graphsHtml } from "./run_popup_model.js";

// As the studio's labels and card.
const LABEL_MAX = 250;
const LABEL_GAP_X = 44;
const LABEL_GAP_Y = 16;
const CARD_WIDTH = 220;
const CARD_CLEAR_BOTTOM = 70;
// A change that needs a run starts it once nothing has changed for this long
// (spec 2026-10-11 section 7).
const RERUN_SETTLE_MS = 1000;
// The studio's own play and pause symbols (paintPlayButtons).
const PLAY = "▶";
const PAUSE = "❚❚";

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function byId(id) {
  return typeof document === "undefined" ? null : document.getElementById(id);
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

// The study's options as a run is keyed: a null or empty value is left out.
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

// mechanism: the pop-up's controller (mechanism_pick.js). hooks: enter() and
// leave() (the studio's timeline and objects), legend(key) (null hides it),
// aim(point), camera(), canvasRect(), viewRight(), record() (the studio's
// recorder: start, or stop).
export function mountFormwork({ studyName, studyOptions, mechanism, view, hooks }) {
  const el = {
    run: byId("formwork-run"), runStatus: byId("formwork-run-status"),
    answer: byId("formwork-answer"), mechanismToggle: byId("mechanism-toggle"),
    mechanismName: byId("formwork-mechanism-name"),
    tolerance: byId("formwork-tolerance"), toleranceValue: byId("formwork-tolerance-value"),
    wires: byId("formwork-wires"), wiresValue: byId("formwork-wires-value"),
    pull: byId("formwork-pull"), pullValue: byId("formwork-pull-value"),
    wall: byId("formwork-wall"), wallValue: byId("formwork-wall-value"),
    skin: byId("formwork-skin"), skinValue: byId("formwork-skin-value"),
    scrub: byId("formwork-scrub"), scrubValue: byId("formwork-scrub-value"),
    speed: byId("formwork-speed"), speedValue: byId("formwork-speed-value"),
    back: byId("formwork-back"), play: byId("formwork-play"), on: byId("formwork-on"),
    label: byId("formwork-label"), line: byId("formwork-line"), show: byId("formwork-show"),
    compare: byId("formwork-compare"), weakest: byId("formwork-weakest"),
    colour: byId("formwork-colour"), values: byId("formwork-values"),
    warnings: byId("formwork-warnings"), labels: byId("formwork-labels"),
    pick: byId("formwork-pick"), record: byId("formwork-record"),
    costBody: byId("cost-body"), costExport: byId("cost-export"),
    costStatus: byId("cost-export-status"), graphs: byId("graphs-body"),
    costFolderChoose: byId("cost-folder-choose"), costFolderPath: byId("cost-folder-path"),
  };
  const api = { active: () => false, setActive: () => {}, tick: () => {}, place: () => {},
                pick: () => {}, clear: () => {}, reload: () => {}, refresh: () => {},
                closePopup: () => {}, mechanismChanged: () => {} };
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    if (typeof document !== "undefined") {
      console.warn(`the Cable net section is not on this page: no element for ${missing.join(", ")}`);
    }
    return api;
  }

  // A ticket keeps a late document from overwriting a newer one, or the
  // emptiness of a study that has gone; watcher is the interval watching a
  // run. judged is the run with its trees judged for the Wall dial.
  const tab = {
    active: false, sim: null, judged: null, times: [], at: 0, playing: false, speed: 1,
    ticket: 0, watcher: null, items: [], pickNode: null, shown: -1, settingsKey: "",
    loading: false, compare: false, weakest: false, rerun: null, again: false,
  };

  // What one spool pulls, the rope's working load and the tolerance: the
  // limits the key, the answer and the weakest are judged against.
  function limits() {
    const o = (tab.sim && tab.sim.options) || {};
    return { have: o.have_newtons ?? null, rope: o.rope_working_newtons ?? null,
             tolerance: Number(el.tolerance.value) };
  }

  function settings() {
    const show = {};
    for (const box of el.show.querySelectorAll("input[data-show]")) show[box.dataset.show] = box.checked;
    return { show, colour: el.colour.value || "off", values: el.values.classList.contains("active"),
             tolerance: Number(el.tolerance.value), compare: tab.compare, weakestOn: tab.weakest,
             skinOpacity: Number(el.skin.value) / 100 };
  }

  function renderMechanism() {
    const entry = mechanism.entry();
    el.mechanismName.textContent = entry ? entry.label : "none chosen";
  }

  function outOfDate() {
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen(), pullIn: Number(el.pull.value) });
  }

  // one spool's pull of the mechanism chosen, which a run going is made with
  function liveHave() {
    const entry = mechanism.entry();
    return entry ? entry.have_newtons : null;
  }

  // The answer (spec section 4.3), greyed while the run is out of date.
  function renderAnswer() {
    if (tab.loading) { el.answer.innerHTML = ""; return; }
    // while a run goes: its figures so far, never the run before it (his
    // choice of 11 October 2026)
    if (tab.watcher != null) {
      const live = liveAnswer(tab.live, liveHave(), Number(el.tolerance.value), Number(el.pull.value));
      el.answer.innerHTML = answerHtml(live);
      return;
    }
    const stale = outOfDate().some((line) => line.startsWith("Run again"));
    el.answer.innerHTML = answerHtml(answer(tab.judged, Number(el.tolerance.value)), { stale });
  }

  // Nothing is said while the document is being looked for: "No run yet"
  // only once it is known there is none (found on screen: it showed while
  // the 6 MB document loaded).
  function renderWarnings() {
    if (tab.loading) { el.warnings.innerHTML = ""; return; }
    // no "Run again" over the run that is going
    const lines = tab.watcher != null
      ? outOfDate().filter((line) => !line.startsWith("Run again")) : outOfDate();
    el.warnings.innerHTML = lines
      .map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
  }

  // The values for the capture shown, rebuilt when the capture or the
  // settings change; placed every frame (place).
  function rebuildLabels(index, now) {
    el.labels.innerHTML = "";
    tab.items = [];
    if (!tab.judged || !tab.active) return;
    for (const target of modelLabels(tab.judged, index, onModel(now, index)).slice(0, LABEL_MAX)) {
      const label = document.createElement("div");
      label.className = "model-label";
      label.textContent = target.text;
      el.labels.appendChild(label);
      tab.items.push({ label, target });
    }
  }

  // The Colour by whose values go on the model, or null.
  function labelled(now) {
    return now.values && labelsShown(now.colour, now.show) ? now.colour : null;
  }

  // What goes on the model at a capture: the Colour by's values, the weakest
  // parts' and, with Compare on, the largest offsets (spec sections 5.2 to 5.4).
  function onModel(now, index) {
    return { by: labelled(now), compare: now.compare,
             weakest: now.weakestOn ? weakestAt(tab.judged, index, limits()) : [] };
  }

  // The capture the player is at, drawn: the positions blended, every number
  // the nearer capture's.
  function draw(force = false) {
    if (!tab.judged || !tab.active) return;
    const head = playhead(tab.times, tab.at);
    if (!head) return;
    const now = settings();
    const weakest = now.weakestOn ? weakestAt(tab.judged, head.nearer, limits()) : [];
    view.show(head, { ...now, weakest });
    const key = JSON.stringify(now);
    const changed = force || key !== tab.settingsKey;
    if (changed) hooks.legend(colourKey(now.colour, tab.judged, limits()));
    if (changed || head.nearer !== tab.shown) {
      const capture = tab.judged.captures[head.nearer];
      el.label.textContent = captureLabel(capture);
      el.scrubValue.textContent = String(head.nearer + 1);
      if (document.activeElement !== el.scrub) el.scrub.value = String(head.nearer + 1);
      el.line.innerHTML = frameLineHtml(frameLine(tab.judged, head.nearer));
      rebuildLabels(head.nearer, now);
      if (tab.pickNode != null) el.pick.innerHTML = formworkPickHtml(tab.judged, head.nearer, tab.pickNode);
      tab.shown = head.nearer;
      tab.settingsKey = key;
    }
  }

  function end() {
    return tab.times.length ? tab.times[tab.times.length - 1] : 0;
  }

  function setPlaying(on) {
    tab.playing = !!on && !!tab.judged;
    el.play.textContent = tab.playing ? PAUSE : PLAY;
    el.play.title = tab.playing ? "Pause" : "Play";
  }

  function goTo(index) {
    if (!tab.judged) return;
    const i = Math.min(Math.max(index, 0), tab.times.length - 1);
    tab.at = tab.times[i];
    setPlaying(false);
    draw();
  }


  // The run with its trees judged in the Wall dial's tube (spec section 7: a
  // new wall is judged again from the run's own forces, without a run).
  function judge() {
    const wall = Number(el.wall.value);
    tab.judged = tab.sim && tab.sim.trees.wall !== wall ? withWall(tab.sim, wall) : tab.sim;
  }

  el.play.addEventListener("click", () => {
    if (!tab.judged) return;
    if (!tab.playing && tab.at >= end()) tab.at = 0;
    setPlaying(!tab.playing);
  });
  // back to the start; on to the next scene (his ask of 11 October 2026)
  el.back.addEventListener("click", () => goTo(0));
  el.on.addEventListener("click", () => {
    const head = playhead(tab.times, tab.at);
    if (head && tab.judged) goTo(nextScene(tab.judged.captures, head.nearer));
  });
  el.scrub.addEventListener("input", () => goTo(Number(el.scrub.value) - 1));
  el.speed.addEventListener("input", () => {
    tab.speed = Number(el.speed.value);
    el.speedValue.textContent = tab.speed.toFixed(2);
  });
  el.wall.addEventListener("input", () => {
    el.wallValue.textContent = Number(el.wall.value).toFixed(1);
    judge();
    view.rejudge(tab.judged);
    renderAnswer();
    renderGraphs();
    draw(true);
  });
  el.tolerance.addEventListener("input", () => {
    el.toleranceValue.textContent = el.tolerance.value;
    renderAnswer();
    renderGraphs();
    draw(true);
  });
  el.skin.addEventListener("input", () => {
    el.skinValue.textContent = el.skin.value;
    draw(true);
  });
  // wires a motor changes every mechanism's pull: the pop-up reads them
  // again, and its answer starts the run (mechanismChanged)
  el.wires.addEventListener("input", () => { el.wiresValue.textContent = el.wires.value; });
  // Pull in, N a tendon (spec 2026-10-11 across tendons, section 7): a
  // change is a full run once it settles, as a mechanism change is
  function setPull(value) {
    el.pull.value = String(value);
    el.pullValue.textContent = el.pull.value;
  }
  el.pull.addEventListener("input", () => { el.pullValue.textContent = el.pull.value; });
  el.pull.addEventListener("change", () => {
    renderWarnings();
    renderAnswer();
    if (tab.sim && outOfDate().includes("Run again: pull changed")) scheduleRerun();
  });
  el.wires.addEventListener("change", () => {
    tab.again = true;
    mechanism.setWires(Number(el.wires.value));
  });
  for (const holder of [el.show, el.colour]) holder.addEventListener("change", () => draw(true));
  el.values.addEventListener("click", () => {
    el.values.classList.toggle("active");
    draw(true);
  });
  el.compare.addEventListener("click", () => {
    tab.compare = !tab.compare;
    el.compare.classList.toggle("active", tab.compare);
    draw(true);
  });
  el.weakest.addEventListener("click", () => {
    tab.weakest = !tab.weakest;
    el.weakest.classList.toggle("active", tab.weakest);
    draw(true);
  });
  el.mechanismToggle.addEventListener("click", () => mechanism.toggle());

  // Needed's row goes to its capture and turns the camera onto its wire.
  el.answer.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-capture]");
    if (!row || !tab.judged) return;
    goTo(Number(row.dataset.capture));
    hooks.aim(view.point({ kind: "wire", index: Number(row.dataset.wire) }));
  });

  // Every frame while the tab is open: the player's clock.
  // A throw here would end the studio's render loop, which reschedules itself
  // only on a normal exit: the player stops and says why.
  function tick(seconds) {
    if (!tab.active || !tab.playing) return;
    try {
      tab.at = Math.min(tab.at + seconds * tab.speed, end());
      if (tab.at >= end()) setPlaying(false);
      draw();
    } catch (error) {
      setPlaying(false);
      el.runStatus.textContent = error.message;
    }
  }

  function placeCard(x, y) {
    el.pick.style.left = Math.round(Math.min(hooks.viewRight() - CARD_WIDTH, x + 14)) + "px";
    el.pick.style.top = Math.round(Math.max(12,
      Math.min(innerHeight - el.pick.offsetHeight - CARD_CLEAR_BOTTOM, y - 20))) + "px";
  }

  // Every render: each value where its part is on screen, the largest of a
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
    if (!tab.active || !tab.judged) return;
    const node = view.nearestNode(hooks.camera(), hooks.canvasRect(), event.clientX, event.clientY);
    if (node == null) return;
    const head = playhead(tab.times, tab.at);
    el.pick.innerHTML = formworkPickHtml(tab.judged, head.nearer, node);
    el.pick.classList.remove("hidden");
    tab.pickNode = node;
    place();
  }

  // The study's run, read once: none yet is said so.
  async function load() {
    const mine = ++tab.ticket;
    const options = studyOptions();
    let sim = null;
    tab.loading = true;
    renderWarnings();
    renderAnswer();
    if (options && studyName()) {
      try {
        sim = readSim(await getJson(simUrl(studyName(), options)));
      } catch (error) {
        if (error.status !== 404) el.runStatus.textContent = error.message;
      }
    }
    if (mine !== tab.ticket) return;
    tab.loading = false;
    const first = !tab.sim;
    tab.sim = sim;
    if (sim && first) {
      adoptMechanism(sim);
      setPull(sim.options.pull_in ?? 0);
    }
    judge();
    mechanism.setChecks(sim ? sim.checks : null);
    tab.times = sim ? captureTimes(sim.captures) : [];
    // a rerun keeps the player where it was, within the new run; a study's
    // first run starts at the raise
    tab.at = first ? 0 : Math.min(tab.at, end());
    tab.shown = -1;
    setPlaying(false);
    el.scrub.max = String(Math.max(1, tab.times.length));
    el.scrub.value = "1";
    el.scrubValue.textContent = "1";
    el.scrubValue.nextElementSibling.textContent = `of ${Math.max(1, tab.times.length)}`;
    view.build(tab.judged);
    if (!sim) {
      el.label.textContent = "";
      el.line.innerHTML = "";
      el.labels.innerHTML = "";
      tab.items = [];
      hooks.legend(null);
    }
    renderWarnings();
    renderAnswer();
    renderGraphs();
    loadCost();
    draw(true);
  }

  // A study's run read first: the slider and the pop-up take its wires a
  // motor and its motor, so a current run does not open out of date (found by
  // the final review). Not his hand, so no run follows.
  function adoptMechanism(sim) {
    const ran = (sim.options || {}).mechanism;
    if (!ran) return;
    el.wires.value = String(ran.wires_per_motor);
    el.wiresValue.textContent = el.wires.value;
    mechanism.adopt(ran);
  }

  // The pop-up's Graphs (spec section 8.3), from the run shown: judged again
  // for a new tolerance without a run.
  function renderGraphs() {
    const have = tab.sim ? (tab.sim.options || {}).have_newtons : null;
    el.graphs.innerHTML = graphsHtml(tab.judged, have == null ? null : Number(have), Number(el.tolerance.value));
  }

  // The pop-up's Cost (section 8.2): the run's mechanism priced on the study.
  async function loadCost() {
    const mine = tab.ticket;
    const options = studyOptions();
    el.costStatus.textContent = "";
    if (!tab.sim || !options || !studyName()) { el.costBody.innerHTML = ""; return; }
    // a run with no mechanism has no cost to ask for (found on screen: an
    // older run's refusal reached the console)
    if (!(tab.sim.options || {}).mechanism) {
      el.costBody.innerHTML = '<div class="cablenet-warning">Run again: no mechanism</div>';
      return;
    }
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(sentOptions(options))) query.set(key, String(value));
    try {
      const cost = await getJson(
        `/api/studies/${encodeURIComponent(studyName())}/formwork/cost?${query.toString()}`);
      if (mine !== tab.ticket) return;
      el.costBody.innerHTML = costHtml(cost);
    } catch (error) {
      if (mine !== tab.ticket) return;
      el.costBody.innerHTML = `<div class="cablenet-warning">${esc(error.message)}</div>`;
    }
  }

  // Export BOM: the run's bill of materials, written to the export folder.
  async function exportBom() {
    const options = studyOptions();
    if (!tab.sim || !options || !studyName()) { el.costStatus.textContent = "No run yet: Run"; return; }
    el.costExport.disabled = true;
    el.costStatus.textContent = "writing";
    try {
      const written = await getJson(`/api/studies/${encodeURIComponent(studyName())}/formwork/bom`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sentOptions(options)) });
      el.costStatus.textContent = "saved: " + written.path;
    } catch (error) {
      el.costStatus.textContent = error.message;
    } finally {
      el.costExport.disabled = false;
    }
  }
  el.costExport.addEventListener("click", exportBom);

  // Where Export BOM writes, and the choice of it (the export folder routes).
  function showFolder(row) {
    el.costFolderPath.textContent = row && row.path ? row.path : "no folder chosen";
    el.costFolderPath.title = row && row.path
      ? (row.exists ? row.path : `${row.path} (missing)`) : "";
  }
  async function loadFolder() {
    try { showFolder(await getJson("/api/cablenet/exports/folder")); }
    catch (error) { el.costFolderPath.textContent = error.message; }
  }
  el.costFolderChoose.addEventListener("click", async () => {
    el.costFolderChoose.disabled = true;
    try {
      const browsed = await getJson("/api/cablenet/exports/folder/browse", { method: "POST" });
      if (browsed && browsed.path) {
        showFolder(await getJson("/api/cablenet/exports/folder", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: browsed.path }) }));
      }
    } catch (error) {
      el.costStatus.textContent = error.message;
    } finally {
      el.costFolderChoose.disabled = false;
    }
  });
  loadFolder();

  function stopWatching() {
    if (tab.watcher != null) clearInterval(tab.watcher);
    tab.watcher = null;
    tab.live = null;
  }

  function watch(runId) {
    stopWatching();
    const poll = setInterval(async () => {
      try {
        const run = await getJson(`/api/runs/${encodeURIComponent(runId)}`);
        if (tab.watcher !== poll) return;
        el.runStatus.textContent = run.of > 0 ? `capture ${run.stage} of ${run.of}`
          : run.state;
        tab.live = run.figures || [];
        renderAnswer();
        if (run.state === "done") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = "";
          await load();
          // a change made while this run went on: run again for it
          const lines = outOfDate();
          if (lines.includes("Run again: mechanism changed")
              || lines.includes("Run again: pull changed")) scheduleRerun();
        }
        if (run.state === "failed") {
          stopWatching();
          el.run.disabled = false;
          el.runStatus.textContent = run.message;
          renderWarnings();
          renderAnswer();
        }
      } catch (error) {
        if (tab.watcher !== poll) return;
        stopWatching();
        el.run.disabled = false;
        el.runStatus.textContent = error.message;
        renderWarnings();
        renderAnswer();
      }
    }, 1000);
    tab.watcher = poll;
    // the run before it goes from the answer the moment this one starts
    renderWarnings();
    renderAnswer();
  }

  // The run takes the mechanism chosen in the pop-up; the server cuts the net
  // for one spool's pull of it. The tab never sends a prestress. Every run is
  // a full run (the holds, and the run from the hold for them, went on 11
  // October 2026).
  async function startRun() {
    const options = studyOptions();
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    const choices = mechanism.chosen();
    if (!choices) { el.runStatus.textContent = "Choose a mechanism"; return; }
    el.run.disabled = true;
    el.runStatus.textContent = "starting";
    try {
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     pull_in: Number(el.pull.value) };
      const response = await fetch(`/api/studies/${encodeURIComponent(studyName())}/formwork/run`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      let started = null;
      try { started = await response.json(); } catch (_) { started = null; }
      if (response.status === 409) {
        const live = await getJson(`/api/runs/${encodeURIComponent(started.run)}`);
        if (live.kind === "formwork") {
          watch(started.run);
        } else {
          el.runStatus.textContent = `${live.kind} run live`;
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
  el.run.addEventListener("click", () => startRun());
  el.record.addEventListener("click", () => hooks.record());

  // A change that needs a run (the mechanism, wires a motor, the pull)
  // starts it once the changes settle; one already running is followed by
  // another.
  function scheduleRerun() {
    clearTimeout(tab.rerun);
    tab.rerun = setTimeout(() => {
      tab.rerun = null;
      if (!tab.active) return;
      if (tab.watcher != null) return;     // the watch runs again when it ends
      startRun();
    }, RERUN_SETTLE_MS);
  }

  // The pop-up's choice changed (by his hand, or by wires a motor): the
  // answer greys, the line says so, and the run starts on its own.
  function mechanismChanged(choices, byHand) {
    renderMechanism();
    renderWarnings();
    renderAnswer();
    const wanted = byHand || tab.again;
    tab.again = false;
    if (wanted && choices && outOfDate().includes("Run again: mechanism changed")) scheduleRerun();
  }

  // The recording of the raise (studio.js recordAnimation): the player's
  // length and speed, a seek that draws the capture at a second, and what
  // each frame carries over the picture, projected on the frame's own pixels.
  const recording = {
    duration: () => end(),
    speed: () => tab.speed,
    seek(seconds) {
      tab.at = Math.min(Math.max(seconds, 0), end());
      setPlaying(false);
      draw();
    },
    overlay(ctx, width, height) {
      const head = playhead(tab.times, tab.at);
      if (!tab.judged || !head) return;
      const now = settings();
      const rect = { left: 0, top: 0, width, height };
      const scale = height / 900;
      const targets = modelLabels(tab.judged, head.nearer, onModel(now, head.nearer)).slice(0, LABEL_MAX);
      const points = targets.map((target) => view.project(view.point(target), hooks.camera(), rect));
      const shown = spreadLabels(points, LABEL_GAP_X * scale, LABEL_GAP_Y * scale);
      const labels = targets.map((target, i) => (shown[i]
        ? { text: target.text, x: points[i][0], y: points[i][1] } : null)).filter(Boolean);
      paintOverlay(ctx, { width, height, caption: recordingCaption(tab.judged, head.nearer),
                          labels, key: colourKey(now.colour, tab.judged, limits()) });
    },
  };

  // The tab opened or left (studio.js activateTab).
  function setActive(on) {
    if (on === tab.active) return;
    tab.active = on;
    document.body.classList.toggle("formwork-open", on);
    if (on) {
      hooks.enter();
      renderMechanism();
      if (!tab.sim) load();
      else draw(true);
      renderWarnings();
      renderAnswer();
      return;
    }
    setPlaying(false);
    mechanism.closePopup();
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
    clearTimeout(tab.rerun);
    tab.rerun = null;
    tab.sim = null;
    tab.judged = null;
    tab.times = [];
    tab.pickNode = null;
    tab.items = [];
    setPlaying(false);
    view.build(null);
    mechanism.clear();
    el.labels.innerHTML = "";
    el.pick.classList.add("hidden");
    el.line.innerHTML = "";
    el.answer.innerHTML = "";
    el.costBody.innerHTML = "";
    el.graphs.innerHTML = "";
    setPull(0);
    el.label.textContent = "";
    el.runStatus.textContent = "";
    el.run.disabled = false;
  }

  function reload() {
    clear();
    mechanism.reload();
    renderMechanism();
    renderWarnings();
    if (tab.active) load();
  }

  function refresh() {
    renderMechanism();
    renderWarnings();
    renderAnswer();
  }

  return { active: () => tab.active, setActive, tick, place, pick, clear, reload, refresh,
           closePopup: () => mechanism.closePopup(), recording, mechanismChanged };
}
