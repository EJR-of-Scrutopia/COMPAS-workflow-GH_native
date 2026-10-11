// The mechanism pop-up's controller (spec 2026-10-11 one Cable net tab,
// section 8.1): it fetches the study's whole spooling mechanisms at the tab's
// wires a motor, remembers the one chosen for each study in this browser, and
// tells the tab when the choice changes. Every line comes from
// mechanism_pick_model.js. A tool, not a text: one dropdown and three lines.

import { mechanismHtml, optionsHtml, pickIndex } from "./mechanism_pick_model.js";

const REMEMBERED_PREFIX = "vaulted-mechanism:";

function byId(id) {
  return typeof document === "undefined" ? null : document.getElementById(id);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let detail = `${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* keep status */ }
    throw new Error(detail);
  }
  return response.json();
}

// onChange(choices, byHand): the five choices of the mechanism now chosen, or
// null, and whether his hand chose it (a list read again did not).
// onPopup(): the pop-up has opened, so the others on the left close.
export function mountMechanism({ studyName, onChange, onPopup = () => {} }) {
  const el = {
    popup: byId("mechanism-popup"), close: byId("mechanism-popup-close"),
    select: byId("mechanism-preset"), have: byId("mechanism-have"),
  };
  const missing = Object.keys(el).filter((name) => !el[name]);
  if (missing.length) {
    if (typeof console !== "undefined" && typeof document !== "undefined") {
      console.warn(`the mechanism pop-up is not on this page: no element for ${missing.join(", ")}`);
    }
    return { reload: async () => {}, clear: () => {}, chosen: () => null, entry: () => null,
             setWires: () => {}, setChecks: () => {}, toggle: () => {}, closePopup: () => {},
             adopt: async () => {} };
  }

  const state = { list: [], index: -1, wires: 1, checks: null, ticket: 0 };

  function entry() {
    return state.index >= 0 ? state.list[state.index] : null;
  }

  function chosen() {
    const e = entry();
    return e ? e.choices : null;
  }

  function remembered() {
    try { return localStorage.getItem(REMEMBERED_PREFIX + studyName()) || null; } catch (_) { return null; }
  }

  function remember() {
    const e = entry();
    if (!e) return;
    try { localStorage.setItem(REMEMBERED_PREFIX + studyName(), e.choices.motor); } catch (_) { /* private */ }
  }

  function render() {
    el.select.innerHTML = optionsHtml(state.list, state.index);
    el.have.innerHTML = mechanismHtml(entry(), state.checks);
  }

  // The study's mechanisms at the wires a motor, read again: the choice kept
  // by its motor, else the strongest. A late answer never paints over a newer.
  async function reload() {
    const mine = ++state.ticket;
    const name = studyName();
    if (!name) { clear(); return; }
    let list = [];
    let note = null;
    try {
      list = (await getJson(`/api/studies/${encodeURIComponent(name)}/mechanisms?wires_per_motor=${state.wires}`))
        .mechanisms || [];
    } catch (error) {
      note = error.message;
    }
    if (mine !== state.ticket) return;
    const before = JSON.stringify(chosen());
    state.list = list;
    state.index = pickIndex(list, remembered());
    render();
    if (note) el.have.innerHTML = `<div class="cablenet-warning">${note.replace(/[<>&]/g, "")}</div>`;
    if (JSON.stringify(chosen()) !== before) onChange(chosen(), false);
  }

  function clear() {
    state.ticket += 1;
    state.list = [];
    state.index = -1;
    state.checks = null;
    render();
  }

  el.select.addEventListener("change", () => {
    state.index = Number(el.select.value);
    remember();
    render();
    onChange(chosen(), true);
  });

  function setPopup(open) {
    el.popup.classList.toggle("hidden", !open);
    if (open) onPopup();
  }
  el.close.addEventListener("click", () => setPopup(false));

  // the pop-up's tabs: Mechanism, Cost and Graphs (sections 8.1 to 8.3)
  function showTab(id) {
    for (const button of el.popup.querySelectorAll("[data-mech-tab]")) {
      button.classList.toggle("active", button.dataset.mechTab === id);
    }
    for (const pane of el.popup.querySelectorAll(".mech-tab")) pane.classList.toggle("hidden", pane.id !== id);
  }
  for (const button of el.popup.querySelectorAll("[data-mech-tab]")) {
    button.addEventListener("click", () => showTab(button.dataset.mechTab));
  }

  return {
    reload, clear, chosen, entry,
    // the wires a motor changes every mechanism's pull: read them again
    setWires(n) {
      if (Number(n) === state.wires) return;
      state.wires = Number(n);
      reload();
    },
    // a study's run read first: its wires a motor and its motor become the
    // choice, so the run on screen is not out of date when nothing changed
    adopt(choices) {
      if (!choices || !choices.motor) return Promise.resolve();
      try { localStorage.setItem(REMEMBERED_PREFIX + studyName(), choices.motor); } catch (_) { /* private */ }
      state.wires = Number(choices.wires_per_motor) || state.wires;
      return reload();
    },
    // the run's drum and carriage, for the Checks line
    setChecks(checks) {
      state.checks = checks || null;
      el.have.innerHTML = mechanismHtml(entry(), state.checks);
    },
    toggle: () => setPopup(el.popup.classList.contains("hidden")),
    closePopup: () => setPopup(false),
  };
}
