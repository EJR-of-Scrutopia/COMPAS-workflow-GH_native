// The one Cable net tab on screen (spec 2026-10-11 one Cable net tab,
// section 10): drives a studio in headless Chromium and photographs the tab
// at a raise capture, a finish capture, the hold, the jacking and a tiling
// quarter; each Colour by; each Show chip alone; the values; Compare;
// Weakest; the skin at nought and at half; the mechanism pop-up; the card.
// Writes the pictures and a report of what each one carries.
// Needs puppeteer-core next to studio_probe.mjs (bench/scripts/probe-env).
// Run against a studio on a spare port, never Param's 8600:
//   cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601
//   node bench/scripts/formwork_screens.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8601), BROWSER_EXE (the
// Playwright Chromium), SCREENS_OUT, STUDY (default the 5 sided form), CUT
// (JSON, default its tile cut), GPU=1 to draw on the graphics card, RUN=1 to
// press Run formwork analysis first:
// about two minutes on the real study, and it rewrites the cut's capture
// document under bench/studies, so copy that aside first.

import puppeteer from "./probe-env/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");
const STUDIO_URL = process.env.STUDIO_URL || "http://127.0.0.1:8601";
const BROWSER_EXE = process.env.BROWSER_EXE || path.join(process.env.LOCALAPPDATA || "",
  "ms-playwright", "chromium-1237", "chrome-win64", "chrome.exe");
const OUT = process.env.SCREENS_OUT ||
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-10-10-formwork-tab", "screens");
const STUDY = process.env.STUDY || "5 sided form";
const CUT = JSON.parse(process.env.CUT ||
  '{"material": "tile", "pattern": "bonded-courses", "source": "authored", "size": 1.0, "thickness": 0.02}');
const RUN = process.env.RUN === "1";
const TICKS = ["net", "trees", "heads", "wires", "anchors", "ground", "holds"];
const COLOURS = ["wire", "tension", "deviation", "utilisation", "off"];

mkdirSync(OUT, { recursive: true });
const report = { study: STUDY, cut: CUT, shots: [], errors: [], requests: [] };
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const note = (line) => console.log(((Date.now() - started) / 1000).toFixed(1) + "s " + line);

// A click the page itself makes: under SwiftShader a pointer click waits on
// layout and frames the software renderer is slow to give.
async function clickOn(page, selector) {
  const found = await page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return false;
    el.click();
    return true;
  }, selector);
  if (!found) report.errors.push("no " + selector);
  note("clicked " + selector);
}

async function waitFor(page, fn, timeout = 60000) {
  const start = Date.now();
  for (;;) {
    if (await page.evaluate(fn)) return true;
    if (Date.now() - start > timeout) return false;
    await sleep(250);
  }
}

// A picture only after the studio has rendered twice since the change.
async function settle(page) {
  const seen = await page.evaluate(() => window.__renders);
  return page.waitForFunction((n) => window.__renders >= n + 2, { timeout: 300000 }, seen)
    .then(() => true, () => false);
}

// The study's props (a forest, on the real study) stream in for many
// minutes and make each software-rendered frame take a quarter of an hour:
// their group is put out of view before every picture, directly, so the
// owner's saved layout is not written.
async function hideProps(page) {
  await page.evaluate(() => {
    const s = window.__studio;
    // the group every prop and every batch of them is drawn in
    s.propsGroup.visible = false;
  });
}

async function shot(page, name) {
  await hideProps(page);
  const settled = await settle(page);
  if (!settled) report.errors.push(name + ": taken with no render after the change");
  const file = path.join(OUT, name + ".png");
  await page.screenshot({ path: file });
  const seen = await page.evaluate(() => {
    const visible = (el) => el && !el.classList.contains("hidden") && getComputedStyle(el).display !== "none";
    const text = (id) => ((document.getElementById(id) || {}).innerText || "").replace(/\s+/g, " ").trim();
    const labels = [...document.querySelectorAll("#formwork-labels .model-label")]
      .filter((el) => el.style.display !== "none");
    const legend = document.getElementById("legend");
    const card = document.getElementById("formwork-pick");
    const popup = document.getElementById("mechanism-popup");
    const group = window.__studio.formworkView.group;
    return {
      label: text("formwork-label"), line: text("formwork-line"), answer: text("formwork-answer"),
      mechanism: text("formwork-mechanism-name"),
      warnings: text("formwork-warnings"), status: text("formwork-run-status"),
      labels: labels.length, someLabels: labels.slice(0, 5).map((el) => el.textContent),
      legend: visible(legend) ? legend.innerText.replace(/\s+/g, " ").trim() : "",
      card: visible(card) ? card.innerText.replace(/\s+/g, " ").trim() : "",
      popup: visible(popup) ? popup.innerText.replace(/\s+/g, " ").trim().slice(0, 300) : "",
      drawn: group.visible ? group.children.filter((c) => c.visible).map((c) => c.type) : [],
      paragraphs: document.querySelectorAll("#formwork-section p, #mechanism-popup p").length,
    };
  });
  seen.settled = settled;
  report.shots.push({ name, file, ...seen });
  note(name + " " + JSON.stringify(seen));
}

async function toCapture(page, index) {
  await page.evaluate((i) => {
    const scrub = document.getElementById("formwork-scrub");
    scrub.value = String(i + 1);
    scrub.dispatchEvent(new Event("input", { bubbles: true }));
  }, index);
}

async function setTicks(page, on) {
  await page.evaluate((wanted) => {
    for (const box of document.querySelectorAll("#formwork-show input[data-show]")) {
      box.checked = wanted.includes(box.dataset.show);
    }
    document.getElementById("formwork-show").dispatchEvent(new Event("change", { bubbles: true }));
  }, on);
}

async function setColour(page, value) {
  await page.evaluate((v) => {
    const radio = document.querySelector(`#formwork-colour input[value="${v}"]`);
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

async function setValues(page, on) {
  await page.evaluate((wanted) => {
    const box = document.getElementById("formwork-values");
    box.checked = wanted;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  }, on);
}

async function setSkin(page, value) {
  await page.evaluate((v) => {
    const slider = document.getElementById("formwork-skin");
    slider.value = String(v);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
}

const browser = await puppeteer.launch({
  executablePath: BROWSER_EXE,
  headless: true,
  protocolTimeout: 900000,
  // GPU=1 draws on the graphics card (a picture in seconds); otherwise SwiftShader
  args: process.env.GPU === "1"
    ? ["--no-sandbox", "--use-gl=angle", "--use-angle=d3d11", "--ignore-gpu-blocklist", "--enable-gpu"]
    : ["--no-sandbox", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
  defaultViewport: { width: 1600, height: 900 },
});
try {
  const page = await browser.newPage();
  page.on("console", (msg) => { if (msg.type() === "error") report.errors.push(msg.text()); });
  page.on("pageerror", (error) => report.errors.push("pageerror: " + error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) report.requests.push(response.status() + " " + response.url());
  });
  // the default scene streams some hundreds of prop models, so the network
  // never goes quiet in time: wait for the studio itself to boot instead
  await page.goto(STUDIO_URL, { waitUntil: "domcontentloaded", timeout: 300000 });
  note("page loaded");
  if (!await waitFor(page, () => !!window.__studio, 300000)) throw new Error("the studio never booted");
  await page.evaluate(() => {
    window.__renders = 0;
    const composer = window.__studio.composer;
    const render = composer.render.bind(composer);
    composer.render = (...args) => { window.__renders += 1; return render(...args); };
  });
  await page.evaluate((study, cut) => window.__studio.applyScene({ study, state: { cut } }), STUDY, CUT);
  note("scene applied");
  // the study's bundle first: the view is framed from its mesh
  if (!await waitFor(page, () => !!window.__studio.state.bundle, 180000)) {
    report.errors.push("the study's bundle did not load");
  }
  // The net in clear view: the study's props put away, the camera three
  // quarters on to the net from its own extent.
  report.view = await page.evaluate(() => {
    const s = window.__studio;
    const groups = s.scene.children.filter((c) => c.isGroup && c.name !== "formwork");
    const props = groups.map((g) => [g, g.children.filter((m) => m.isInstancedMesh || m.userData.propType).length])
      .sort((a, b) => b[1] - a[1])[0];
    if (props && props[1] > 0) props[0].visible = false;
    const v = s.state.bundle.analysis_mesh.vertices;
    const lo = [0, 1, 2].map((k) => Math.min(...v.map((p) => p[k])));
    const hi = [0, 1, 2].map((k) => Math.max(...v.map((p) => p[k])));
    const extent = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
    const target = s.controls.target;
    target.set((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 3);
    const dir = new target.constructor(0.55, -0.75, 0.6).normalize();
    s.camera.position.copy(target).add(dir.multiplyScalar(extent * 1.15));
    s.camera.up.set(0, 0, 1);
    s.controls.update();
    return { propsHidden: props ? props[1] : 0, extent };
  });
  note("view set " + JSON.stringify(report.view));

  await clickOn(page, '#tab-rail button[data-section="formwork-section"]');
  await waitFor(page, () => !!document.getElementById("formwork-line").innerHTML
    || /No run yet/.test(document.getElementById("formwork-warnings").innerText), 180000);
  await shot(page, "01-tab");
  const stale = await page.evaluate(() =>
    /No run yet|Run again/.test(document.getElementById("formwork-warnings").innerText));
  if (RUN || stale) {
    const before = Date.now();
    await clickOn(page, "#formwork-run");
    const done = await waitFor(page, () => {
      const status = document.getElementById("formwork-run-status").textContent;
      return !document.getElementById("formwork-run").disabled
        && (!!document.getElementById("formwork-line").innerHTML || !!status);
    }, 1800000);
    report.run = { seconds: Math.round((Date.now() - before) / 1000), done,
      status: await page.evaluate(() => document.getElementById("formwork-run-status").textContent),
      warnings: await page.evaluate(() => document.getElementById("formwork-warnings").innerText) };
    note("run " + JSON.stringify(report.run));
    await shot(page, "02-after-run");
  }
  report.holds = await page.evaluate(() => {
    const el = document.getElementById("formwork-holds");
    return el ? el.innerText : null;
  });
  note("holds " + JSON.stringify(report.holds));

  // Which capture is which, read off the document the tab plays.
  const captures = await page.evaluate(async (study, cut) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(cut)) if (value != null) query.set(key, String(value));
    const response = await fetch(`/api/studies/${encodeURIComponent(study)}/formwork/sim?${query}`);
    if (!response.ok) return [];
    const doc = await response.json();
    return doc.captures.map((c) => ({ phase: c.phase, time: c.time, row: c.row, quarter: c.quarter }));
  }, STUDY, CUT);
  report.captures = captures.length;
  if (!captures.length) throw new Error("no formwork run to look at");
  const first = (test) => Math.max(0, captures.findIndex(test));
  const tiling = captures.map((c, i) => [c, i]).filter(([c]) => c.phase === "tiling").map(([, i]) => i);
  const moments = [
    ["03-raise", first((c) => c.phase === "raise" && c.time >= 46)],
    ["04-finish", first((c) => c.phase === "finish" && c.time >= 76)],
    ["05-hold", captures.map((c) => c.phase).lastIndexOf("hold")],
    ...(captures.some((c) => c.phase === "holds")
      ? [["05b-jacked", captures.findIndex((c) => c.phase === "holds")]] : []),
    ["06-tiling", tiling[Math.floor(tiling.length / 2)] ?? captures.length - 1],
    ["07-end", captures.length - 1],
  ];
  for (const [name, index] of moments) {
    await toCapture(page, index);
    await shot(page, name);
  }

  let n = 8;
  for (const colour of COLOURS) {
    await setColour(page, colour);
    await shot(page, String(n++).padStart(2, "0") + "-colour-" + colour);
  }
  await setColour(page, "deviation");

  for (const tick of TICKS) {
    await setTicks(page, [tick]);
    await shot(page, String(n++).padStart(2, "0") + "-show-" + tick);
  }
  await setTicks(page, TICKS);

  // the values at the hold, then none
  await toCapture(page, moments[2][1]);
  await setValues(page, true);
  await shot(page, String(n++).padStart(2, "0") + "-values");
  await setValues(page, false);
  await shot(page, String(n++).padStart(2, "0") + "-values-off");
  await setValues(page, true);

  // Compare and Weakest at the end of the tiling, each alone
  await toCapture(page, captures.length - 1);
  await clickOn(page, "#formwork-compare");
  await shot(page, String(n++).padStart(2, "0") + "-compare");
  await clickOn(page, "#formwork-compare");
  await clickOn(page, "#formwork-weakest");
  await shot(page, String(n++).padStart(2, "0") + "-weakest");
  await clickOn(page, "#formwork-weakest");

  // the skin hidden, then half opaque
  for (const value of [0, 50]) {
    await setSkin(page, value);
    await shot(page, String(n++).padStart(2, "0") + "-skin-" + value);
  }
  await setSkin(page, 30);

  // the mechanism pop-up
  await clickOn(page, "#mechanism-toggle");
  await shot(page, String(n++).padStart(2, "0") + "-mechanism");
  await clickOn(page, "#mechanism-popup-close");

  // a click on the view opens the card of the node there
  const centre = await page.evaluate(() => {
    const rect = document.getElementById("view").getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  });
  await page.mouse.click(centre.x, centre.y);
  await shot(page, String(n++).padStart(2, "0") + "-card");
  await page.mouse.click(700, 60);
  await page.mouse.move(1450, 760);

  // and leaving gives the studio back
  await clickOn(page, '#tab-rail button[data-section="animation-section"]');
  await shot(page, String(n++).padStart(2, "0") + "-left");
} finally {
  writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log("errors:", JSON.stringify(report.errors));
  console.log("failed requests:", JSON.stringify(report.requests));
  await browser.close();
}
