// The Cable net tab on screen (spec 2026-10-09 Cable net display, section 8):
// drives a studio in headless Chromium and photographs the menu, each pop-up
// tab, each lens with its labels and legend, and the card a click on a node
// opens. Writes the pictures and a report of what each one carries.
// Needs puppeteer-core next to studio_probe.mjs (bench/scripts/probe-env).
// Run against a studio on a spare port, never Param's 8600:
//   cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601
//   node bench/scripts/cablenet_screens.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8601), BROWSER_EXE (the
// Playwright Chromium), SCREENS_OUT, STUDY (default the 5 sided form), CUT
// (JSON, default its tile cut: a demand keyed with no density, which a fresh
// browser reads; the timber demand is keyed by the owner's skin's density),
// RUN=1 to press Run cable net analysis first and look at what it writes.
// A run rewrites the cut's demand under bench/studies: copy it aside first.

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
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-10-10-cablenet-display", "screens");
const STUDY = process.env.STUDY || "5 sided form";
const CUT = JSON.parse(process.env.CUT ||
  '{"material": "tile", "pattern": "bonded-courses", "source": "authored", "size": 1.0, "thickness": 0.02}');
const LENSES = [["tension", "Wire tension"], ["nodeforce", "Node force"], ["sag", "Sag"],
                ["prestress", "Prestress"], ["reel", "Reel"], ["holds", "Holds"]];
const RUN = process.env.RUN === "1";

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

// Under SwiftShader a frame of the real study takes the best part of a
// minute: a picture is taken only after the studio's own render has run twice
// since the change, and one taken without is said so in the report.
async function settle(page) {
  const seen = await page.evaluate(() => window.__renders);
  return page.waitForFunction((n) => window.__renders >= n + 2, { timeout: 300000 }, seen)
    .then(() => true, () => false);
}

async function shot(page, name, lens = null) {
  const settled = await settle(page);
  if (!settled) report.errors.push(name + ": taken with no render after the change");
  const file = path.join(OUT, name + ".png");
  await page.screenshot({ path: file });
  const seen = await page.evaluate(() => {
    // fixed elements have no offsetParent: read what the page computed
    const visible = (el) => el && !el.classList.contains("hidden") && getComputedStyle(el).display !== "none";
    const labels = [...document.querySelectorAll("#model-labels .model-label")]
      .filter((el) => el.style.display !== "none");
    const legend = document.getElementById("legend");
    const card = document.getElementById("cablenet-pick");
    return {
      labels: labels.length,
      someLabels: labels.slice(0, 5).map((el) => el.textContent),
      legend: visible(legend) ? legend.innerText.replace(/\s+/g, " ").trim() : "",
      menu: (document.getElementById("cablenet-demand") || {}).innerText || "",
      card: visible(card) ? card.innerText.replace(/\s+/g, " ").trim() : "",
      paragraphs: document.querySelectorAll("#cablenet-section p, #cablenet-popup p").length,
      stage: (document.getElementById("cablenet-stage") || {}).textContent || "",
    };
  });
  seen.settled = settled;
  // a lens is looked at on the loaded net: a course, not a frame of the raise
  if (lens && !/^S/.test(seen.stage)) report.errors.push(name + ": at " + (seen.stage || "no instant"));
  report.shots.push({ name, file, ...seen });
  note(name + " " + JSON.stringify(seen));
}

const browser = await puppeteer.launch({
  executablePath: BROWSER_EXE,
  headless: true,
  protocolTimeout: 900000,
  args: ["--no-sandbox", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
  defaultViewport: { width: 1600, height: 900 },
});
try {
  const page = await browser.newPage();
  page.on("console", (msg) => { if (msg.type() === "error") report.errors.push(msg.text()); });
  page.on("pageerror", (error) => report.errors.push("pageerror: " + error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) report.requests.push(response.status() + " " + response.url());
  });
  await page.goto(STUDIO_URL, { waitUntil: "networkidle0", timeout: 300000 });
  note("page loaded");
  if (!await waitFor(page, () => !!window.__studio)) throw new Error("the studio never booted");
  await page.evaluate(() => {
    window.__renders = 0;
    const composer = window.__studio.composer;
    const render = composer.render.bind(composer);
    composer.render = (...args) => { window.__renders += 1; return render(...args); };
  });
  await page.evaluate((study, cut) => window.__studio.applyScene({ study, state: { cut } }), STUDY, CUT);
  note("scene applied");
  if (!await waitFor(page, () => !!window.__studio.state.cablenet, 180000)) {
    report.errors.push("no cable net demand for this cut");
    throw new Error("no cable net demand for this cut: " + JSON.stringify(CUT));
  }
  // the scored row, which Gives, Most, the limits and the motors read
  await waitFor(page, () => (document.getElementById("cablenet-holds") || {}).innerHTML, 120000);
  if (RUN) {
    // the analysis as the panel runs it, designed for the machine chosen; done
    // when the demand on screen carries its prestress table
    const before = Date.now();
    await clickOn(page, "#cablenet-run");
    const done = await waitFor(page, () => {
      const demand = window.__studio.state.cablenet;
      const status = (document.getElementById("cablenet-run-status") || {}).textContent || "";
      return !!(demand && demand.needs) || /failed|refused|error/i.test(status);
    }, 1800000);
    report.run = {
      seconds: Math.round((Date.now() - before) / 1000),
      status: await page.evaluate(() => document.getElementById("cablenet-run-status").textContent),
      needs: await page.evaluate(() => {
        const needs = (window.__studio.state.cablenet || {}).needs;
        return needs ? { ceiling: needs.ceiling_newtons, steps: needs.steps.length,
                         needed: needs.steps[0].prestress_newtons } : null;
      }),
    };
    if (!done || !report.run.needs) report.errors.push("the run gave no prestress table: " + report.run.status);
    note("run " + JSON.stringify(report.run));
    await waitFor(page, () => (document.getElementById("cablenet-holds") || {}).innerHTML, 120000);
  }
  // The net in clear view: the study's props (its trees) put away, and the
  // camera three-quarter on to the net from its own extent.
  report.view = await page.evaluate(() => {
    const s = window.__studio;
    const groups = s.scene.children.filter((c) => c.isGroup);
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
  await clickOn(page, '#tab-rail button[data-section="cablenet-section"]');
  await shot(page, "01-menu");

  await clickOn(page, "#cablenet-popup-toggle");
  for (const [tab, name] of [["cn-mechanism", "02-popup-mechanism"], ["cn-cost", "03-popup-cost"],
                             ["cn-graphs", "04-popup-graphs"]]) {
    await clickOn(page, `#cablenet-tabs button[data-cn-tab="${tab}"]`);
    if (tab === "cn-mechanism") {
      await waitFor(page, () => document.querySelectorAll("#cablenet-motors tr[data-motor]").length > 0, 120000);
    }
    await shot(page, name);
  }
  await clickOn(page, "#cablenet-popup-close");

  // The lenses at the end of the timeline, the net carrying the whole skin.
  await page.evaluate(() => {
    const scrubber = document.getElementById("timeline-scrubber");
    scrubber.value = scrubber.max;
    scrubber.dispatchEvent(new Event("input", { bubbles: true }));
  });
  note("timeline at the end: " + await page.evaluate(() =>
    (document.getElementById("cablenet-stage") || {}).textContent));

  let index = 5;
  for (const [lens, label] of LENSES) {
    const pressed = await page.evaluate((text) => {
      const button = [...document.querySelectorAll("#cablenet-lenses button.layer-btn")]
        .find((b) => b.textContent === text);
      if (!button || button.disabled) return button ? "disabled: " + button.title : "missing";
      button.click();
      return "on";
    }, label);
    if (pressed !== "on") report.errors.push(label + " lens " + pressed);
    await shot(page, String(index++).padStart(2, "0") + "-lens-" + lens, lens);
    if (lens === "nodeforce") {
      // the card: a click on the node with the largest unbalanced force
      const at = await page.evaluate(() => {
        const s = window.__studio;
        const stage = s.state.cablenet.stages.find((x) => x.node_residual) || null;
        if (!stage) return null;
        const sizes = stage.node_residual.map((v) => (v ? Math.hypot(v[0], v[1], v[2]) : 0));
        const i = sizes.indexOf(Math.max(...sizes));
        const v = s.state.bundle.analysis_mesh.vertices[i];
        const lift = s.state.objects.nodes ? s.state.objects.nodes.position.z : 0;
        const p = new s.camera.position.constructor(v[0], v[1], v[2] + lift).project(s.camera);
        const rect = document.getElementById("view").getBoundingClientRect();
        return { x: rect.left + (p.x * 0.5 + 0.5) * rect.width, y: rect.top + (-p.y * 0.5 + 0.5) * rect.height };
      });
      if (at) {
        await page.mouse.click(at.x, at.y);
        await shot(page, String(index++).padStart(2, "0") + "-card", lens);
        // close the card with a click on the empty sky, then rest the
        // pointer over the panel, where it hovers nothing on the model
        await page.mouse.click(700, 60);
        await page.mouse.move(1450, 760);
      } else report.errors.push("no node force to click");
    }
    if (pressed === "on") {
      await page.evaluate((text) => [...document.querySelectorAll("#cablenet-lenses button.layer-btn")]
        .find((b) => b.textContent === text).click(), label);
    }
  }
} finally {
  writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log("errors:", JSON.stringify(report.errors));
  console.log("failed requests:", JSON.stringify(report.requests));
  await browser.close();
}
