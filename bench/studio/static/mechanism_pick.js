// The mechanism pop-up's controller (spec 2026-10-11 one Cable net tab,
// section 8.1): it fetches every mechanism the study's machine can be built as
// for the wire chosen, at the tab's wires a motor; he builds his own from
// Motor, Ratio, Pulleys and Pulley (Param, 2026-10-12: "i also want to be able
// to create my own mechanism, choose whether there is pulley or not should
// just be a toggle"); the one built is remembered for each study in this
// browser, and the tab is told when it changes. Every line comes from
// mechanism_pick_model.js. A tool, not a text.

import {
  builderPick, hasPulleys, mechanismHtml, mechanismsUrl, motorOptionsHtml, pulleyOptionsHtml,
  ratioFromKey, ratioKey, ratioOptionsHtml,
} from "./mechanism_pick_model.js";

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
// rope(): the rope the study wears, which holds every mechanism listed.
export function mountMechanism({ studyName, onChange, onPopup = () => {}, rope = () => null }) {
  const el = {
    popup: byId("mechanism-popup"), close: byId("mechanism-popup-close"),
    motor: byId("mechanism-motor"), ratio: byId("mechanism-ratio"),
    pulleys: byId("mechanism-pulleys"), pulley: byId("mechanism-pulley"),
    have: byId("mechanism-have"),
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

  // the mechanism this browser built for the study: { motor, ratio, pulley },
  // or its motor alone as it was kept before he could build his own
  function remembered() {
    let kept = null;
    try { kept = localStorage.getItem(REMEMBERED_PREFIX + studyName()); } catch (_) { return null; }
    if (!kept) return null;
    try {
      const parsed = JSON.parse(kept);
      return parsed && typeof parsed === "object" ? parsed : kept;
    } catch (_) { return kept; }
  }

  function keep(wanted) {
    try { localStorage.setItem(REMEMBERED_PREFIX + studyName(), JSON.stringify(wanted)); } catch (_) { /* private */ }
  }

  function render() {
    const e = entry();
    const c = e ? e.choices : { motor: null, ratio: null, pulley: null };
    el.motor.innerHTML = motorOptionsHtml(state.list, c.motor);
    el.ratio.innerHTML = e ? ratioOptionsHtml(state.list, c.motor, c.ratio) : "";
    const can = e ? hasPulleys(state.list, c.motor, c.ratio) : false;
    el.pulleys.checked = c.pulley !== null;
    el.pulleys.disabled = !can;
    el.pulley.innerHTML = c.pulley !== null ? pulleyOptionsHtml(state.list, c.motor, c.ratio, c.pulley) : "";
    el.pulley.disabled = c.pulley === null;
    el.have.innerHTML = mechanismHtml(e, state.checks);
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
      list = (await getJson(mechanismsUrl(name, state.wires, rope()))).options || [];
    } catch (error) {
      note = error.message;
    }
    if (mine !== state.ticket) return;
    const before = JSON.stringify(chosen());
    state.list = list;
    state.index = builderPick(list, remembered());
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

  // His hand on any of the four: what he asked for, or the nearest the motor
  // can make; Pulleys on picks the strongest pulley, off takes none.
  function built(wanted) {
    state.index = builderPick(state.list, wanted);
    const e = entry();
    if (e) keep({ motor: e.choices.motor, ratio: e.choices.ratio, pulley: e.choices.pulley });
    render();
    onChange(chosen(), true);
  }
  el.motor.addEventListener("change", () => built({ motor: el.motor.value }));
  el.ratio.addEventListener("change", () => {
    const e = entry();
    built({ motor: e.choices.motor, ratio: ratioFromKey(el.ratio.value),
            pulley: e.choices.pulley === null ? null : e.choices.pulley });
  });
  el.pulleys.addEventListener("change", () => {
    const e = entry();
    built({ motor: e.choices.motor, ratio: e.choices.ratio,
            pulley: el.pulleys.checked ? "" : null });
  });
  el.pulley.addEventListener("change", () => {
    const e = entry();
    built({ motor: e.choices.motor, ratio: e.choices.ratio, pulley: el.pulley.value });
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
      keep({ motor: choices.motor, ratio: choices.ratio ?? null, pulley: choices.pulley ?? null });
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
