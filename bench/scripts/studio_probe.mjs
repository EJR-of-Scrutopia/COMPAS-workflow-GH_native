// Studio probe: drives a live studio in headless Brave and writes a
// defect-table draft. Needs puppeteer-core installed next to it:
//   cd bench/scripts/probe-env && npm init -y && npm i puppeteer-core
// Run: node bench/scripts/studio_probe.mjs
// Env: STUDIO_URL (default http://127.0.0.1:8600),
//      BROWSER_EXE (default Brave's standard install path),
//      PROBE_OUT (default .superpowers/sdd/2026-08-15-studio-repairs)

import puppeteer from "./probe-env/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..", "..");

const STUDIO_URL = process.env.STUDIO_URL || "http://127.0.0.1:8600";
const BROWSER_EXE = process.env.BROWSER_EXE ||
  "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe";
const PROBE_OUT = process.env.PROBE_OUT ||
  path.join(REPO_ROOT, ".superpowers", "sdd", "2026-08-15-studio-repairs");
const FIXTURE_DIR = PROBE_OUT; // make_probe_fixtures.py writes fixtures here too

mkdirSync(PROBE_OUT, { recursive: true });

const reportLines = [];
const consoleErrors = []; // { check, text }
let currentCheck = "boot";

function log(line) {
  console.log(line);
  reportLines.push(line);
}

function heading(text) {
  log("");
  log("## " + text);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(page, fn, { timeout = 15000, interval = 200 } = {}) {
  const start = Date.now();
  for (;;) {
    const ok = await page.evaluate(fn);
    if (ok) return true;
    if (Date.now() - start > timeout) return false;
    await sleep(interval);
  }
}

// ---------- PUT helpers, direct HTTP, not through the page ----------
async function putFile(urlPath, filePath) {
  const body = readFileSync(filePath);
  const response = await fetch(STUDIO_URL + urlPath, { method: "PUT", body });
  const text = await response.text();
  return { ok: response.ok, status: response.status, text };
}

// ---------- pixel helpers ----------
function countDistinctHues(png, region) {
  // png: { width, height, data: Uint8ClampedArray RGBA }. Buckets hue into
  // 24 slices (15 degrees each) plus a "greyscale" bucket for low-saturation
  // pixels (white/black/grey read as no colour, which is the point).
  const buckets = new Set();
  const { x0, y0, x1, y1 } = region;
  for (let y = y0; y < y1; y += 2) {
    for (let x = x0; x < x1; x += 2) {
      const i = (y * png.width + x) * 4;
      const r = png.data[i], g = png.data[i + 1], b = png.data[i + 2];
      const max = Math.max(r, g, b), min = Math.min(r, g, b);
      const delta = max - min;
      if (delta < 12) { buckets.add("grey"); continue; }
      let hue;
      if (max === r) hue = ((g - b) / delta) % 6;
      else if (max === g) hue = (b - r) / delta + 2;
      else hue = (r - g) / delta + 4;
      hue = Math.round(hue * 60);
      if (hue < 0) hue += 360;
      buckets.add(Math.floor(hue / 15));
    }
  }
  return buckets;
}

function fractionWhite(png, region) {
  const { x0, y0, x1, y1 } = region;
  let white = 0, total = 0;
  for (let y = y0; y < y1; y += 2) {
    for (let x = x0; x < x1; x += 2) {
      const i = (y * png.width + x) * 4;
      total += 1;
      if (png.data[i] >= 250 && png.data[i + 1] >= 250 && png.data[i + 2] >= 250) white += 1;
    }
  }
  return total ? white / total : 0;
}

// Minimal PNG decoder is not worth writing here: puppeteer screenshots can
// be taken straight to disk, but pixel inspection needs raw RGBA. We ask
// the PAGE itself to read the canvas back (readPixels through a 2D copy),
// which sidesteps needing a PNG decoder in node entirely.
async function readCanvasRegion(page, region) {
  // Crop to the requested region in-page before serialising: the full
  // 1600x900 canvas is 5.76M bytes, and shipping that over CDP as a JSON
  // array is the slow way to do this.
  const cropped = await page.evaluate((r) => {
    const source = document.getElementById("view");
    const canvas = document.createElement("canvas");
    canvas.width = source.width;
    canvas.height = source.height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(source, 0, 0);
    const w = r.x1 - r.x0, h = r.y1 - r.y0;
    const image = ctx.getImageData(r.x0, r.y0, w, h);
    return { width: w, height: h, data: Array.from(image.data) };
  }, region);
  // The caller's `region` was in full-canvas coordinates; the cropped data
  // is now local to (0, 0), so return a local region alongside it.
  return { width: cropped.width, height: cropped.height, data: cropped.data,
    localRegion: { x0: 0, y0: 0, x1: cropped.width, y1: cropped.height } };
}

async function main() {
  log("# Studio probe raw report");
  log("");
  log("STUDIO_URL: " + STUDIO_URL);
  log("BROWSER_EXE: " + BROWSER_EXE);
  log("PROBE_OUT: " + PROBE_OUT);
  log("timestamp: " + new Date().toISOString());

  let browser;
  let headlessMode = "headless: true (new)";
  try {
    browser = await puppeteer.launch({
      executablePath: BROWSER_EXE,
      headless: true,
      args: ["--use-angle=default"],
      defaultViewport: { width: 1600, height: 900 },
    });
  } catch (error) {
    log("headless launch failed: " + error.message + "; falling back to headed");
    headlessMode = "headless: false (fallback)";
    browser = await puppeteer.launch({
      executablePath: BROWSER_EXE,
      headless: false,
      args: ["--use-angle=default"],
      defaultViewport: { width: 1600, height: 900 },
    });
  }

  const page = await browser.newPage();
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push({ check: currentCheck, text: msg.text() });
    }
  });
  page.on("pageerror", (error) => {
    consoleErrors.push({ check: currentCheck, text: "pageerror: " + error.message });
  });

  try {
    // ---------- 1. Boot and WebGL sanity ----------
    currentCheck = "boot";
    heading("1. Boot and WebGL sanity (" + headlessMode + ")");
    await page.goto(STUDIO_URL, { waitUntil: "networkidle0" });
    const hasHook = await waitFor(page, () => !!window.__studio, { timeout: 10000 });
    log("window.__studio present: " + hasHook);
    if (!hasHook) throw new Error("window.__studio never appeared; boot failed");
    const glInfo = await page.evaluate(() => {
      const canvas = document.getElementById("view");
      const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
      if (!gl) return { ok: false, reason: "no webgl context" };
      return { ok: true, renderer: gl.getParameter(gl.RENDERER) || "", vendor: gl.getParameter(gl.VENDOR) || "" };
    });
    log("WebGL: " + JSON.stringify(glInfo));
    if (!glInfo.ok) throw new Error("WebGL did not start: " + glInfo.reason);

    // ---------- 2. Upload the Tiny pair, reload, select it ----------
    currentCheck = "upload-tiny";
    heading("2. Upload the Tiny pair and select it");
    const contractPut = await putFile(
      "/api/uploads/exports/Tiny/contract", path.join(FIXTURE_DIR, "Tiny-contract.json"));
    const compasPut = await putFile(
      "/api/uploads/exports/Tiny/compas", path.join(FIXTURE_DIR, "Tiny-compas.json"));
    log("PUT contract: " + contractPut.status + " " + contractPut.text);
    log("PUT compas: " + compasPut.status + " " + compasPut.text);

    await page.reload({ waitUntil: "networkidle0" });
    await waitFor(page, () => !!window.__studio, { timeout: 10000 });
    await page.evaluate(() => {
      const select = document.getElementById("study-select");
      select.value = "Tiny";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    // The page may already have booted onto a real study before the select
    // and change event above land (boot() runs on load and picks
    // studies[0]), so "some bundle exists" is trivially true immediately.
    // Wait for the specific export, or every later check risks racing an
    // in-flight loadStudy("Tiny") that swaps state.bundle out from under it.
    const bundleLoaded = await waitFor(page, () =>
      window.__studio.state.bundle !== null &&
      window.__studio.state.bundle.export === "Tiny" &&
      window.__studio.state.objects.shell &&
      window.__studio.state.objects.shell.children.length > 0,
      { timeout: 15000 });
    log("Tiny bundle loaded, shell has children: " + bundleLoaded);
    if (!bundleLoaded) throw new Error("Tiny study never produced a bundle with a populated shell");
    const bundleExport = await page.evaluate(() => window.__studio.state.bundle.export);
    log("loaded bundle export: " + bundleExport);

    // ---------- 3. Drive the timeline to its end ----------
    currentCheck = "timeline-end";
    heading("3. Drive the timeline to its end");
    // rebuildTimeline (inside buildScene) only just replaced state.timeline
    // for the Tiny bundle above; give the DOM a beat before scrubbing it,
    // or the scrub can land between the swap and the first render() pass.
    await sleep(200);
    await page.evaluate(() => {
      const scrubber = document.getElementById("timeline-scrubber");
      scrubber.value = 1000;
      scrubber.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await sleep(300);
    const timelineT = await page.evaluate(() => window.__studio.state.timeline
      ? window.__studio.state.timeline.t : null);
    log("timeline.t after scrub to 1000: " + timelineT);

    // ---------- 4. Layer checks ----------
    const LABEL_MATCH = {
      shell: "finished shell", wires: "thrust wires", stress: "stress heatmap",
      deflection: "deflection heatmap", loads: "load vectors", reactions: "reaction vectors",
      overlays: "text overlays", pulse: "integrity pulse", forces: "wire forces",
    };
    async function readLayerState(name) {
      return page.evaluate((n) => {
        const s = window.__studio.state;
        const shellChildren = s.objects.shell ? s.objects.shell.children : [];
        return {
          checked: s.layers[n],
          shellVisibleCount: shellChildren.filter((c) => c.visible).length,
          shellChildCount: shellChildren.length,
          shellMaterialType: shellChildren[0] ? shellChildren[0].material.type : null,
          loadArrowsVisible: s.objects.loadArrows ? s.objects.loadArrows.visible : null,
          reactionArrowsVisible: s.objects.reactionArrows ? s.objects.reactionArrows.visible : null,
          wiresVisible: s.objects.wires ? s.objects.wires.visible : null,
          nodesVisible: s.objects.nodes ? s.objects.nodes.visible : null,
        };
      }, name);
    }
    async function readDisabled(name) {
      return page.evaluate((n, matchText) => {
        const boxes = Array.from(document.querySelectorAll('#layer-toggles input[type="checkbox"]'));
        const labels = Array.from(document.querySelectorAll("#layer-toggles label"));
        const idx = labels.findIndex((l) => l.textContent.toLowerCase().includes(matchText));
        if (idx < 0) return { found: false };
        const box = boxes[idx];
        return { found: true, disabled: box.disabled, title: labels[idx].title || "" };
      }, name, LABEL_MATCH[name]);
    }
    async function toggleLayer(name, checked) {
      return page.evaluate((n, v, matchText) => {
        const labels = Array.from(document.querySelectorAll("#layer-toggles label"));
        const boxes = Array.from(document.querySelectorAll('#layer-toggles input[type="checkbox"]'));
        const idx = labels.findIndex((l) => l.textContent.toLowerCase().includes(matchText));
        if (idx < 0) return false;
        boxes[idx].checked = v;
        boxes[idx].dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }, name, checked, LABEL_MATCH[name]);
    }
    async function runLayerPass(passLabel) {
      const results = {};
      for (const name of Object.keys(LABEL_MATCH)) {
        currentCheck = "layer-" + name + "-" + passLabel;
        const before = await readLayerState(name);
        const disabled = await readDisabled(name);
        // shell, wires and overlays default checked=true, so always toggling
        // to true first is a no-op transition for them and would misreport
        // "no observable effect" on a control that never actually moved.
        // Flip relative to the CURRENT checked state instead, then flip
        // back, so every layer gets a real state transition to observe.
        const target = !before.checked;
        await toggleLayer(name, target);
        await sleep(150);
        const on = await readLayerState(name);
        await toggleLayer(name, before.checked);
        await sleep(150);
        const changed = JSON.stringify(before) !== JSON.stringify(on);
        results[name] = { before, on, disabled, changed, toggledTo: target };
        log("[" + passLabel + "] " + name + ": disabled=" + JSON.stringify(disabled) + " toggledTo=" + target +
          " effect=" + (changed ? "OBSERVABLE" : "no observable effect") + " on=" + JSON.stringify(on));
      }
      return results;
    }

    currentCheck = "layer-checks-end";
    heading("4a. Layer checks at the end of the timeline (scrubber 1000, post-strike)");
    const layerResultsEnd = await runLayerPass("end");

    currentCheck = "layer-checks-midbuild";
    heading("4b. Layer checks mid-build (scrubber 500, pre-strike) -- same toggles, to tell a real "
      + "no-effect bug apart from the strike deliberately taking wires/nodes/falsework with it");
    await page.evaluate(() => {
      const scrubber = document.getElementById("timeline-scrubber");
      scrubber.value = 500;
      scrubber.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await sleep(200);
    const layerResultsMid = await runLayerPass("midbuild");
    await page.evaluate(() => {
      const scrubber = document.getElementById("timeline-scrubber");
      scrubber.value = 1000;
      scrubber.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await sleep(200);

    writeFileSync(path.join(PROBE_OUT, "probe-layer-results.json"),
      JSON.stringify({ end: layerResultsEnd, midbuild: layerResultsMid }, null, 2));

    // ---------- 5. Heatmap pixels ----------
    currentCheck = "heatmap-pixels";
    heading("5. Heatmap pixels (stress on)");
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("#layer-toggles label"));
      const boxes = Array.from(document.querySelectorAll('#layer-toggles input[type="checkbox"]'));
      const idx = labels.findIndex((l) => l.textContent.toLowerCase().includes("stress heatmap"));
      boxes[idx].checked = true;
      boxes[idx].dispatchEvent(new Event("change", { bubbles: true }));
    });
    await sleep(300);
    await page.screenshot({ path: path.join(PROBE_OUT, "heatmap-stress.png") });
    const region = { x0: 500, y0: 250, x1: 1100, y1: 650 };
    const canvasRead = await readCanvasRegion(page, region);
    const pngLike = { width: canvasRead.width, height: canvasRead.height, data: canvasRead.data };
    const hueBuckets = countDistinctHues(pngLike, canvasRead.localRegion);
    log("distinct hue buckets in central region: " + hueBuckets.size +
      " (" + Array.from(hueBuckets).join(",") + ")");
    log("white-wash defect confirmed (< 3 hues): " + (hueBuckets.size < 3));
    log("screenshot: heatmap-stress.png");
    const stressDisabledInfo = await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("#layer-toggles label"));
      const boxes = Array.from(document.querySelectorAll('#layer-toggles input[type="checkbox"]'));
      const idx = labels.findIndex((l) => l.textContent.toLowerCase().includes("stress heatmap"));
      return { disabled: boxes[idx].disabled, title: labels[idx].title,
        hasStage: !!(window.__studio.state.bundle && window.__studio.state.bundle.staging),
        hasVerification: !!(window.__studio.state.bundle && window.__studio.state.bundle.verification) };
    });
    log("stress checkbox state: " + JSON.stringify(stressDisabledInfo));
    // turn stress back off
    await page.evaluate(() => {
      const labels = Array.from(document.querySelectorAll("#layer-toggles label"));
      const boxes = Array.from(document.querySelectorAll('#layer-toggles input[type="checkbox"]'));
      const idx = labels.findIndex((l) => l.textContent.toLowerCase().includes("stress heatmap"));
      boxes[idx].checked = false;
      boxes[idx].dispatchEvent(new Event("change", { bubbles: true }));
    });

    // ---------- 6. Formwork ----------
    currentCheck = "formwork";
    heading("6. Formwork modes (rest and mid-build)");
    const formworkResults = {};
    for (const mode of ["animation", "always", "hidden"]) {
      currentCheck = "formwork-" + mode;
      await page.evaluate((m) => {
        const scrubber = document.getElementById("timeline-scrubber");
        scrubber.value = 1000;
        scrubber.dispatchEvent(new Event("input", { bubbles: true }));
        const select = document.getElementById("formwork-mode");
        select.value = m;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }, mode);
      await sleep(150);
      const atRest = await page.evaluate(() => {
        const f = window.__studio.state.objects.falsework;
        return f ? { visible: f.visible, opacity: f.material.opacity, z: f.position.z } : null;
      });
      await page.evaluate((m) => {
        const scrubber = document.getElementById("timeline-scrubber");
        scrubber.value = 500;
        scrubber.dispatchEvent(new Event("input", { bubbles: true }));
      }, mode);
      await sleep(150);
      const midBuild = await page.evaluate(() => {
        const f = window.__studio.state.objects.falsework;
        return f ? { visible: f.visible, opacity: f.material.opacity, z: f.position.z } : null;
      });
      // The state reading says whether falsework.visible is true, but the
      // owner's report is about what actually reaches the screen -- a
      // translucent mesh sitting almost exactly where the opaque finished
      // shell already stands can be geometrically hidden even at
      // visible: true. Screenshot both timeline positions for each mode so
      // that question has a picture to answer it, not just a boolean.
      await page.evaluate(() => {
        const scrubber = document.getElementById("timeline-scrubber");
        scrubber.value = 1000;
        scrubber.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await sleep(150);
      await page.screenshot({ path: path.join(PROBE_OUT, "formwork-" + mode + "-rest.png") });
      await page.evaluate(() => {
        const scrubber = document.getElementById("timeline-scrubber");
        scrubber.value = 500;
        scrubber.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await sleep(150);
      await page.screenshot({ path: path.join(PROBE_OUT, "formwork-" + mode + "-midbuild.png") });
      formworkResults[mode] = { atRest, midBuild };
      log("formwork " + mode + ": atRest=" + JSON.stringify(atRest) + " midBuild=" + JSON.stringify(midBuild) +
        " screenshots=formwork-" + mode + "-rest.png,formwork-" + mode + "-midbuild.png");
    }
    writeFileSync(path.join(PROBE_OUT, "probe-formwork-results.json"), JSON.stringify(formworkResults, null, 2));
    await page.evaluate(() => {
      const select = document.getElementById("formwork-mode");
      select.value = "animation";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      const scrubber = document.getElementById("timeline-scrubber");
      scrubber.value = 1000;
      scrubber.dispatchEvent(new Event("input", { bubbles: true }));
    });

    // ---------- 7. Environment wash ----------
    currentCheck = "environment-wash";
    heading("7. Environment wash (weather presets at elevation 40)");
    await page.evaluate(() => {
      const select = document.getElementById("environment-mode");
      select.value = "sky";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await sleep(200);
    const washResults = {};
    for (const preset of ["clear", "hazy", "overcast", "golden-hour", "night"]) {
      currentCheck = "wash-" + preset;
      await page.evaluate((p) => {
        const elevation = document.getElementById("sun-elevation");
        elevation.value = 40;
        elevation.dispatchEvent(new Event("input", { bubbles: true }));
        elevation.dispatchEvent(new Event("change", { bubbles: true }));
        const select = document.getElementById("weather-preset");
        select.value = p;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }, preset);
      await sleep(250);
      const shotPath = path.join(PROBE_OUT, "wash-" + preset + ".png");
      await page.screenshot({ path: shotPath });
      const upperRegion = { x0: 0, y0: 0, x1: 1600, y1: 450 };
      const canvasRead2 = await readCanvasRegion(page, upperRegion);
      const frac = fractionWhite(
        { width: canvasRead2.width, height: canvasRead2.height, data: canvasRead2.data },
        canvasRead2.localRegion);
      washResults[preset] = frac;
      log("weather=" + preset + " elevation=40 pure-white fraction (upper half): " +
        frac.toFixed(3) + " screenshot=" + path.basename(shotPath));
    }
    writeFileSync(path.join(PROBE_OUT, "probe-wash-results.json"), JSON.stringify(washResults, null, 2));
    await page.evaluate(() => {
      const select = document.getElementById("environment-mode");
      select.value = "studio";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });

    // ---------- 8. HDRI replace ----------
    currentCheck = "hdri-replace";
    heading("8. HDRI replace (the reported bug)");
    await page.evaluate(() => {
      const select = document.getElementById("environment-mode");
      select.value = "hdri";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await sleep(300);

    async function uploadHdri(name) {
      const input = await page.$("#hdri-upload");
      await input.uploadFile(path.join(FIXTURE_DIR, name));
      await sleep(600);
      return page.evaluate(() => ({
        hdriName: window.__studio.state.hdriName,
        hasBackground: !!window.__studio.scene.background,
        statusText: document.getElementById("hdri-status").textContent,
      }));
    }

    currentCheck = "hdri-warm";
    const warmResult = await uploadHdri("probe-warm.hdr");
    log("after probe-warm.hdr: " + JSON.stringify(warmResult));

    currentCheck = "hdri-cool";
    const coolResult = await uploadHdri("probe-cool.hdr");
    log("after probe-cool.hdr: " + JSON.stringify(coolResult));

    log("HDRI name changed warm->cool: " + (warmResult.hdriName !== coolResult.hdriName));
    log("HDRI replace summary: warm=" + JSON.stringify(warmResult) + " cool=" + JSON.stringify(coolResult));

    // Back to the studio environment: the synthetic probe HDRIs are single
    // flat-colour images, near black once PMREM'd, and every screenshot
    // taken from here on (export replace, rim captures) would otherwise be
    // lit by that degenerate environment rather than anything representative.
    await page.evaluate(() => {
      const select = document.getElementById("environment-mode");
      select.value = "studio";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await sleep(300);

    // ---------- 9. Export replace ----------
    currentCheck = "export-replace";
    heading("9. Export replace (re-import after a contract change)");
    const beforeChecksum = await page.evaluate(() => {
      const b = window.__studio.state.bundle;
      if (!b || !b.render_mesh) return null;
      const positions = b.render_mesh.positions || b.render_mesh.vertices;
      return JSON.stringify(positions).length;
    });
    log("bundle checksum (positions JSON length) before re-import: " + beforeChecksum);

    const rawContract = JSON.parse(readFileSync(path.join(FIXTURE_DIR, "Tiny-contract.json"), "utf-8"));
    for (const v of rawContract.equilibrium.vertices) v.z = v.z * 1.2;
    const modifiedPath = path.join(PROBE_OUT, "Tiny-contract-modified.json");
    writeFileSync(modifiedPath, JSON.stringify(rawContract));
    const reupload = await putFile("/api/uploads/exports/Tiny/contract", modifiedPath);
    log("PUT modified contract: " + reupload.status + " " + reupload.text);

    await page.evaluate(() => {
      const select = document.getElementById("study-select");
      select.value = "Tiny";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await sleep(1000);
    const afterChecksum = await page.evaluate(() => {
      const b = window.__studio.state.bundle;
      if (!b || !b.render_mesh) return null;
      const positions = b.render_mesh.positions || b.render_mesh.vertices;
      return JSON.stringify(positions).length;
    });
    log("bundle checksum (positions JSON length) after re-import: " + afterChecksum);
    const geometryChanged = await page.evaluate(() => {
      const b = window.__studio.state.bundle;
      const positions = b.render_mesh.positions || b.render_mesh.vertices;
      // Compare max z against the pre-modification value: the tiny
      // contract's centre vertex lifts to 1.0 * 1.2 = 1.2 after scaling.
      let maxZ = -Infinity;
      for (const p of positions) maxZ = Math.max(maxZ, Array.isArray(p) ? p[2] : p.z);
      return maxZ;
    });
    log("max z in render mesh after re-import (expect ~1.2 if geometry updated): " + geometryChanged);

    // ---------- 10. Rim captures ----------
    currentCheck = "rim-captures";
    heading("10. Rim captures at two piece sizes");
    const cameraReachable = await page.evaluate(() => !!(window.__studio.scene && window.__studio.scene.children));
    log("scene reachable via __studio.scene: " + cameraReachable + " (camera object itself is not exported)");
    for (const size of [0.9, 0.3]) {
      currentCheck = "rim-" + size;
      await page.evaluate((s) => {
        const slider = document.getElementById("size-slider");
        slider.value = s;
        slider.dispatchEvent(new Event("input", { bubbles: true }));
        slider.dispatchEvent(new Event("change", { bubbles: true }));
      }, size);
      // The commit waits out RELOAD_SETTLE_MS (1500ms) before it even issues
      // the cut request, then the server re-cuts and re-renders. Poll the
      // loaded bundle's own size rather than sleeping a guessed duration.
      const landed = await page.waitForFunction(
        (s) => window.__studio.state.bundle && window.__studio.state.bundle.size === s,
        { timeout: 20000 }, size).then(() => true).catch(() => false);
      await sleep(300);
      const shotPath = path.join(PROBE_OUT, "rim-" + String(size).replace(".", "").padEnd(3, "0") + ".png");
      await page.screenshot({ path: shotPath });
      log("size=" + size + " landed=" + landed + " screenshot=" + path.basename(shotPath) +
        " state.bundle.size=" + (await page.evaluate(() => window.__studio.state.bundle && window.__studio.state.bundle.size)));
    }

  } catch (error) {
    log("");
    log("## PROBE ERROR");
    log(String(error && error.stack ? error.stack : error));
  } finally {
    heading("Console errors captured, by check");
    if (consoleErrors.length === 0) {
      log("(none)");
    } else {
      for (const entry of consoleErrors) {
        log("[" + entry.check + "] " + entry.text);
      }
    }
    await browser.close();
    writeFileSync(path.join(PROBE_OUT, "probe-raw-report.md"), reportLines.join("\n") + "\n");
    console.log("");
    console.log("Raw report written to " + path.join(PROBE_OUT, "probe-raw-report.md"));
  }
}

main();
