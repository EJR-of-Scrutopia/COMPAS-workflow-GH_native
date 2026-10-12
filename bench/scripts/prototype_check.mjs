// The 2 sided prototype on screen (Param, 2026-10-12): the principal lines as
// plain wires, the columns as their tube, Tube, Steel, Finish and Marks in the
// Cable net tab, the mechanism built by hand, and a pulled run's across wires
// as the tendons with no line drawn over them. Run against a studio on a spare
// port, never Param's 8600:
//   cd bench/studio && ../../.venv/Scripts/python.exe serve.py --port 8601
//   node bench/scripts/prototype_check.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8601), BROWSER_EXE, SCREENS_OUT,
// GPU=1 to draw on the graphics card, PULL=N to run with N newtons a tendon
// (it writes the prototype's run document under bench/studies).

import puppeteer from "./probe-env/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STUDIO_URL = process.env.STUDIO_URL || "http://127.0.0.1:8601";
const BROWSER_EXE = process.env.BROWSER_EXE || path.join(process.env.LOCALAPPDATA || "",
  "ms-playwright", "chromium-1237", "chrome-win64", "chrome.exe");
const OUT = process.env.SCREENS_OUT || path.join(HERE, "..", "..", ".superpowers", "prototype-check");
const STUDY = "2 sided prototype";
const CUT = { material: "brick", pattern: "bonded-courses", source: "authored", size: 0.5, thickness: 0.04 };
const PULL = process.env.PULL == null ? null : Number(process.env.PULL);

mkdirSync(OUT, { recursive: true });
const report = { shots: [], errors: [], requests: [] };
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const started = Date.now();
const note = (line) => console.log(((Date.now() - started) / 1000).toFixed(1) + "s " + line);

async function waitFor(page, fn, timeout = 60000) {
  const start = Date.now();
  for (;;) {
    if (await page.evaluate(fn)) return true;
    if (Date.now() - start > timeout) return false;
    await sleep(250);
  }
}

async function settle(page) {
  const seen = await page.evaluate(() => window.__renders);
  return page.waitForFunction((n) => window.__renders >= n + 2, { timeout: 300000 }, seen)
    .then(() => true, () => false);
}

async function shot(page, name, extra) {
  await settle(page);
  const file = path.join(OUT, name + ".png");
  await page.screenshot({ path: file });
  const seen = extra ? await page.evaluate(extra) : {};
  report.shots.push({ name, file, ...seen });
  note(name + " " + JSON.stringify(seen));
}

const browser = await puppeteer.launch({
  executablePath: BROWSER_EXE, headless: true, protocolTimeout: 900000,
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
  await page.goto(STUDIO_URL, { waitUntil: "domcontentloaded", timeout: 300000 });
  if (!await waitFor(page, () => !!window.__studio, 300000)) throw new Error("the studio never booted");
  await page.evaluate(() => {
    window.__renders = 0;
    const composer = window.__studio.composer;
    const render = composer.render.bind(composer);
    composer.render = (...args) => { window.__renders += 1; return render(...args); };
  });
  await page.evaluate((study, cut) => window.__studio.applyScene({ study, state: { cut } }), STUDY, CUT);
  if (!await waitFor(page, () => !!window.__studio.state.bundle, 180000)) report.errors.push("no bundle");
  await sleep(4000);
  // three quarters on, from the net's own extent; the props put away
  await page.evaluate(() => {
    const s = window.__studio;
    const groups = s.scene.children.filter((c) => c.isGroup && c.name !== "formwork");
    for (const g of groups) {
      if (g.children.some((m) => m.isInstancedMesh && m.userData.propType)) g.visible = false;
    }
    const v = s.state.bundle.analysis_mesh.vertices;
    const lo = [0, 1, 2].map((k) => Math.min(...v.map((p) => p[k])));
    const hi = [0, 1, 2].map((k) => Math.max(...v.map((p) => p[k])));
    const extent = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
    const target = s.controls.target;
    target.set((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 3);
    const dir = new target.constructor(0.55, -0.75, 0.45).normalize();
    s.camera.position.copy(target).add(dir.multiplyScalar(extent * 1.2));
    s.camera.up.set(0, 0, 1);
    s.controls.update();
  });
  const mainFacts = () => {
    const s = window.__studio;
    const columns = s.state.objects.columns;
    const instanced = columns ? columns.children.filter((c) => c.isInstancedMesh) : [];
    let outer = null, inner = null;
    if (instanced.length) {
      const pos = instanced[0].geometry.attributes.position;
      let lo = Infinity, hi = 0;
      for (let i = 0; i < pos.count; i++) {
        const r = Math.hypot(pos.getX(i), pos.getZ(i));
        lo = Math.min(lo, r); hi = Math.max(hi, r);
      }
      outer = hi; inner = lo;
    }
    return {
      principal: "principal" in s.state.objects && !!s.state.objects.principal,
      columnLook: s.state.columnLook,
      columnRadiusExported: s.state.columnRadius,
      columnMeshes: columns ? columns.children.length : 0, instancedColumns: instanced.length,
      tubeOuterM: outer, tubeInnerM: inner,
      wireRadius: s.state.wireRadius,
    };
  };
  await shot(page, "a-main", mainFacts);

  // the Cable net tab: Tube, Steel, Finish and Marks
  await page.evaluate(() => document.querySelector('#tab-rail button[data-section="formwork-section"]').click());
  await waitFor(page, () => !!document.getElementById("formwork-line").innerHTML
    || /No run yet|Run again/.test(document.getElementById("formwork-warnings").innerText), 180000);
  const tabFacts = () => {
    const value = (id) => { const el = document.getElementById(id); return el ? el.value : null; };
    const text = (id) => ((document.getElementById(id) || {}).innerText || "").replace(/\s+/g, " ").trim();
    const view = window.__studio.formworkView;
    const parts = view.parts();
    return {
      tube: value("column-tube"), grade: value("column-grade"), finish: value("column-finish"),
      finishDisabled: document.getElementById("column-finish").disabled,
      tubes: document.getElementById("column-tube").options.length,
      marks: value("formwork-marks"), wall: value("formwork-wall"),
      warnings: text("formwork-warnings"), answer: text("formwork-answer"),
      viewChildren: view.group.children.length, tendonLines: parts ? parts.tendons !== undefined : null,
      treeRadius: parts && parts.trees ? (() => {
        parts.trees.geometry.computeBoundingSphere();
        const pos = parts.trees.geometry.attributes.position;
        let hi = 0, lo = Infinity;
        for (let i = 0; i < pos.count; i++) { const r = Math.hypot(pos.getX(i), pos.getZ(i)); hi = Math.max(hi, r); lo = Math.min(lo, r); }
        return [lo, hi];
      })() : null,
    };
  };
  await shot(page, "b-tab", tabFacts);

  // the mechanism built by hand
  await page.evaluate(() => document.getElementById("mechanism-toggle").click());
  await waitFor(page, () => document.getElementById("mechanism-motor").options.length > 0, 60000);
  const mechFacts = () => {
    const value = (id) => document.getElementById(id).value;
    return {
      motor: value("mechanism-motor"), ratio: value("mechanism-ratio"),
      pulleys: document.getElementById("mechanism-pulleys").checked, pulley: value("mechanism-pulley"),
      motors: document.getElementById("mechanism-motor").options.length,
      ratios: [...document.getElementById("mechanism-ratio").options].map((o) => o.textContent),
      readout: document.getElementById("mechanism-have").innerText.replace(/\s+/g, " ").trim(),
      paragraphs: document.querySelectorAll("#mechanism-popup p").length,
    };
  };
  await shot(page, "c-mechanism", mechFacts);
  // Pulleys off: straight off the drum
  await page.evaluate(() => {
    const box = document.getElementById("mechanism-pulleys");
    box.checked = false;
    box.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await shot(page, "d-mechanism-no-pulleys", mechFacts);
  // another motor at another ratio
  await page.evaluate(() => {
    const motor = document.getElementById("mechanism-motor");
    motor.value = motor.options[motor.options.length - 1].value;
    motor.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await shot(page, "e-mechanism-servo", mechFacts);
  // back to the strongest with pulleys, for the run
  await page.evaluate(() => {
    const motor = document.getElementById("mechanism-motor");
    motor.value = motor.options[0].value;
    motor.dispatchEvent(new Event("change", { bubbles: true }));
    const box = document.getElementById("mechanism-pulleys");
    if (!box.disabled && !box.checked) { box.checked = true; box.dispatchEvent(new Event("change", { bubbles: true })); }
    document.getElementById("mechanism-popup-close").click();
  });

  // the Marks at a quarter
  await page.evaluate(() => {
    const marks = document.getElementById("formwork-marks");
    marks.value = "0.25";
    marks.dispatchEvent(new Event("input", { bubbles: true }));
  });

  if (PULL != null) {
    await page.evaluate((n) => {
      const slider = document.getElementById("formwork-pull");
      slider.value = String(n);
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    }, PULL);
    const before = Date.now();
    await page.evaluate(() => document.getElementById("formwork-run").click());
    await waitFor(page, () => /running|capture|starting|cutting/.test(
      document.getElementById("formwork-run-status").textContent), 30000);
    const done = await waitFor(page, () => !document.getElementById("formwork-run").disabled
      && !document.getElementById("formwork-run-status").textContent
      && !!document.getElementById("formwork-line").innerHTML, 1800000);
    report.run = { seconds: Math.round((Date.now() - before) / 1000), done,
      status: await page.evaluate(() => document.getElementById("formwork-run-status").textContent) };
    note("run " + JSON.stringify(report.run));
    // the hold, coloured Across, the Tendons chip on
    await page.evaluate(() => {
      const select = document.getElementById("formwork-colour");
      select.value = "across";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      const scrub = document.getElementById("formwork-scrub");
      scrub.value = scrub.max;
      scrub.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }
  await shot(page, "f-tab-after", tabFacts);
} catch (error) {
  report.errors.push("script: " + error.message);
} finally {
  writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 1));
  await browser.close();
}
