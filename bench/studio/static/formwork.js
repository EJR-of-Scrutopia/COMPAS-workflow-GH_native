// The one Cable net tab's controller (spec 2026-10-11 one Cable net tab): it
// runs the physics engine with the mechanism chosen in the pop-up
// (mechanism_pick.js), fetches the run's captures, plays them, gives the
// answer, and fills the section from formwork_model.js. studio.js hands it the
// study, the mechanism pop-up, the drawing (formwork_view.js) and its own
// hooks; this file touches no three.js. A tool, not a text: numbers, marks,
// tables.

import {
  answer, answerHtml, captureLabel, captureTimes, colourKey, colourLabels, formworkPickHtml,
  formworkWarnings, frameLine, frameLineHtml, labelsShown, paintOverlay, playhead, readSim,
  recordingCaption, weakestAt, withWall,
} from "./formwork_model.js";
import { spreadLabels } from "./labels.js";

// As the studio's labels and card.
const LABEL_MAX = 125;
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
    const picked = el.colour.querySelector("input[name=formwork-colour]:checked");
    return { show, colour: picked ? picked.value : "off", values: el.values.checked,
             tolerance: Number(el.tolerance.value), compare: tab.compare, weakestOn: tab.weakest,
             skinOpacity: Number(el.skin.value) / 100 };
  }

  function renderMechanism() {
    const entry = mechanism.entry();
    el.mechanismName.textContent = entry ? entry.label : "none chosen";
  }

  function outOfDate() {
    return formworkWarnings(tab.sim, { mechanism: mechanism.chosen() });
  }

  // The answer (spec section 4.3), greyed while the run is out of date.
  function renderAnswer() {
    if (tab.loading) { el.answer.innerHTML = ""; return; }
    const stale = outOfDate().some((line) => line.startsWith("Run again"));
    el.answer.innerHTML = answerHtml(answer(tab.judged, Number(el.tolerance.value)), { stale });
  }

  // Nothing is said while the document is being looked for: "No run yet"
  // only once it is known there is none (found on screen: it showed while
  // the 6 MB document loaded).
  function renderWarnings() {
    if (tab.loading) { el.warnings.innerHTML = ""; return; }
    el.warnings.innerHTML = outOfDate()
      .map((line) => `<div class="cablenet-warning">${esc(line)}</div>`).join("");
  }

  // The values for the capture shown, rebuilt when the capture or the
  // settings change; placed every frame (place).
  function rebuildLabels(index, by) {
    el.labels.innerHTML = "";
    tab.items = [];
    if (!tab.judged || !tab.active || by == null) return;
    for (const target of colourLabels(tab.judged, index, by).slice(0, LABEL_MAX)) {
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
      rebuildLabels(head.nearer, labelled(now));
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

  function step(by) {
    const head = playhead(tab.times, tab.at);
    if (head) goTo(head.nearer + by);
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
  el.back.addEventListener("click", () => step(-1));
  el.on.addEventListener("click", () => step(1));
  el.scrub.addEventListener("input", () => goTo(Number(el.scrub.value) - 1));
  el.speed.addEventListener("input", () => {
    tab.speed = Number(el.speed.value);
    el.speedValue.textContent = tab.speed.toFixed(2);
  });
  el.wall.addEventListener("input", () => {
    el.wallValue.textContent = Number(el.wall.value).toFixed(1);
    judge();
    renderAnswer();
    draw(true);
  });
  el.tolerance.addEventListener("input", () => {
    el.toleranceValue.textContent = el.tolerance.value;
    renderAnswer();
    draw(true);
  });
  el.skin.addEventListener("input", () => {
    el.skinValue.textContent = el.skin.value;
    draw(true);
  });
  // wires a motor changes every mechanism's pull: the pop-up reads them
  // again, and its answer starts the run (mechanismChanged)
  el.wires.addEventListener("input", () => { el.wiresValue.textContent = el.wires.value; });
  el.wires.addEventListener("change", () => {
    tab.again = true;
    mechanism.setWires(Number(el.wires.value));
  });
  for (const holder of [el.show, el.colour]) holder.addEventListener("change", () => draw(true));
  el.values.addEventListener("change", () => draw(true));
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
    tab.sim = sim;
    judge();
    mechanism.setChecks(sim ? sim.checks : null);
    tab.times = sim ? captureTimes(sim.captures) : [];
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
    renderAnswer();
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
          // a change made while this run went on: run again for it
          if (outOfDate().includes("Run again: mechanism changed")) scheduleRerun();
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

  // The run takes the mechanism chosen in the pop-up; the server cuts the net
  // for one spool's pull of it. The tab never sends a prestress.
  async function startRun() {
    const options = studyOptions();
    if (!options || !studyName()) { el.runStatus.textContent = "open a study first"; return; }
    const choices = mechanism.chosen();
    if (!choices) { el.runStatus.textContent = "Choose a mechanism"; return; }
    el.run.disabled = true;
    el.runStatus.textContent = "starting: about two minutes";
    try {
      const body = { ...sentOptions(options), mechanism: choices, wall: Number(el.wall.value),
                     tolerance_mm: Number(el.tolerance.value) };
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
  el.record.addEventListener("click", () => hooks.record());

  // A change that needs a run (the mechanism, wires a motor) starts it once
  // the changes settle; one already running is followed by another.
  function scheduleRerun() {
    clearTimeout(tab.rerun);
    tab.rerun = setTimeout(() => {
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
      const by = labelled(now);
      const targets = by == null ? [] : colourLabels(tab.judged, head.nearer, by).slice(0, LABEL_MAX);
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
