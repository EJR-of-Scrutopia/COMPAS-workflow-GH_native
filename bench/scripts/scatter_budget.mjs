// Slice zero of the scatter tool: measure the ceiling instead of arguing it.
//
// The design proposes a triangle budget per scatter rather than an instance
// count, because props-hd spans 94 to 219,430 triangles and an instance
// count means nothing across that range. This places real props through the
// real placeProp and reads what the renderer actually submits.
//
// DRAW CALLS AND TRIANGLES ARE EXACT and do not depend on the GPU, so they
// are the numbers the budget is set from. Frame time is reported too, but
// it is only worth reading if the GL renderer string below says a real
// adapter: a headless SwiftShader run rasterises on the CPU and its
// milliseconds say nothing about Param's 4090.
//
//   node bench/scripts/scatter_budget.mjs
//
// MEASURED AND REJECTED, 2026-09-10: gating renderer.shadowMap.autoUpdate.
//
// The scatter design named it "the highest-leverage change available in
// this file" and expected it to roughly halve the per-frame cost, on the
// reasoning that a 2048 square map is rebuilt every frame even on a still
// camera and every caster is therefore drawn twice. The reasoning is
// correct and the conclusion is not. Measured on the 4090 at 1080p, with
// shrub_02 as the caster:
//
//     props   autoUpdate ON    OFF      saved
//         0        5.2 ms      5.2       0%
//       200        5.3         5.4      -2%   (noise)
//       500        5.5         5.3       4%   (0.2 ms)
//
// Nothing worth having, against a change to shared render state that the
// recorder, the timeline and the formwork act all sit on, and that needs
// an invalidation call at every point anything casting moves.
//
// The number underneath is the one worth keeping: an EMPTY scene costs
// 5.2 ms and 500 shadow-casting shrubs cost 5.5. The frame is dominated
// by the composer's own passes at 1080p, not by the scene, which is why
// a scattered field feels free and why the triangle budget binds long
// before the frame does.
//
// Leaves the scene as it found it: every prop it places is removed again.
import { pathToFileURL } from "node:url";

const REPO = "C:/Users/Param/OneDrive - Ananke-eidos/Documents/Ananke Eidos Studio"
  + "/VS code/COMPAS-Workflow-bench";
const PUP = REPO + "/bench/scripts/probe-env/node_modules/puppeteer-core"
  + "/lib/puppeteer/puppeteer-core.js";
const EXE = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe";

const COUNTS = [100, 250, 500, 1000];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function until(page, fn, ms = 240000) {
  const start = Date.now();
  for (;;) {
    let ok = false;
    try { ok = await page.evaluate(fn); } catch { ok = false; }
    if (ok) return true;
    if (Date.now() - start > ms) return false;
    await sleep(500);
  }
}

const puppeteer = (await import(pathToFileURL(PUP).href)).default;
const browser = await puppeteer.launch({
  executablePath: EXE, headless: true,
  args: ["--use-angle=default", "--enable-gpu", "--ignore-gpu-blocklist"],
  defaultViewport: { width: 1920, height: 1080 },
});
const page = await browser.newPage();
page.on("pageerror", (e) => console.log("  page error:", String(e).slice(0, 160)));
await page.goto("http://127.0.0.1:8600", { waitUntil: "domcontentloaded" });

if (!await until(page, () => !!window.__studioReady)) {
  console.log("the studio never finished booting"); await browser.close();
  process.exit(1);
}
await until(page, () => document.getElementById("study-select").options.length > 0);
await page.evaluate(() => {
  const s = document.getElementById("study-select");
  s.value = s.options[0].value;
  s.dispatchEvent(new Event("change"));
});
if (!await until(page, () => !!(window.__studio.state.bundle
    && window.__studio.state.objects.shell))) {
  console.log("no study loaded"); await browser.close(); process.exit(1);
}
await sleep(3000);

const facts = await page.evaluate(() => {
  const gl = window.__studio.composer.renderer.getContext();
  const ext = gl.getExtension("WEBGL_debug_renderer_info");
  return {
    renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "unknown",
    study: document.getElementById("study-select").value,
    baseCalls: window.__studio.composer.renderer.info.render.calls,
    baseTriangles: window.__studio.composer.renderer.info.render.triangles,
  };
});
console.log("GL renderer :", facts.renderer);
console.log("study       :", facts.study);
console.log("scene alone : " + facts.baseCalls + " draw calls, "
  + facts.baseTriangles.toLocaleString() + " triangles");
console.log();

// The two ends of the range the tool must serve: the library's median
// prop, and a real standing tree of the size he would actually plant.
const picks = await page.evaluate(async () => {
  const library = window.__studio.state.propLibrary || [];
  const withTris = library.filter((e) => e.triangles > 0);
  const sorted = [...withTris].sort((a, b) => a.triangles - b.triangles);
  const median = sorted[Math.floor(sorted.length / 2)];
  // A believable standing tree: 2 to 10 m tall, heaviest of those.
  const trees = withTris
    .filter((e) => e.sizeMetres && e.sizeMetres[1] >= 2 && e.sizeMetres[1] <= 10)
    .sort((a, b) => b.triangles - a.triangles);
  return { median: { key: median.key, triangles: median.triangles },
    tree: trees[0] ? { key: trees[0].key, triangles: trees[0].triangles,
      height: trees[0].sizeMetres[1] } : null };
});
console.log("median prop :", picks.median.key, picks.median.triangles.toLocaleString(), "triangles");
if (picks.tree) console.log("tallest tree:", picks.tree.key,
  picks.tree.triangles.toLocaleString(), "triangles,", picks.tree.height.toFixed(1), "m");
console.log();

const rows = [];
for (const pick of [picks.median, picks.tree].filter(Boolean)) {
  for (const count of COUNTS) {
    const row = await page.evaluate(async (key, count) => {
      const S = window.__studio;
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      await S.ensurePropTemplate(key);
      const before = S.state.props.length;
      // CENTRED ON THE VAULT AND IN SHOT. The first attempt put the grid
      // at x=40, y=-40, outside the camera's view of the vault, so every
      // prop was frustum-culled and 1,000 of them cost the same as 100.
      const side = Math.ceil(Math.sqrt(count));
      const gap = 3;
      const half = (side - 1) * gap / 2;
      for (let i = 0; i < count; i++) {
        S.placeProp(key, (i % side) * gap - half,
          Math.floor(i / side) * gap - half, (i * 0.7) % 6.28, false, 1);
      }
      // Frame the whole grid, or the cull does the measuring for us.
      const reach = half * 1.9 + 20;
      S.controls.target.set(0, 0, 0);
      S.camera.position.set(reach, -reach, reach * 0.7);
      S.camera.lookAt(0, 0, 0);
      S.camera.far = reach * 6;
      S.camera.updateProjectionMatrix();
      S.controls.update();
      await sleep(700);

      // info.autoReset clears the counters on EVERY render call, and the
      // composer ends each frame with a fullscreen copy pass, so reading
      // it afterwards reported that pass alone: one call, one triangle,
      // identical at every count. Held across a whole frame instead.
      const info = S.composer.renderer.info;
      info.autoReset = false;
      const marks = [];
      let calls = 0, triangles = 0;
      for (let f = 0; f < 30; f++) {
        info.reset();
        const t = performance.now();
        await new Promise((r) => requestAnimationFrame(r));
        marks.push(performance.now() - t);
        calls = Math.max(calls, info.render.calls);
        triangles = Math.max(triangles, info.render.triangles);
      }
      info.autoReset = true;
      marks.sort((a, b) => a - b);
      const out = { key, count, calls, triangles,
        median: marks[Math.floor(marks.length / 2)] };
      // Put the scene back exactly as it was.
      const placed = S.state.props.splice(before);
      for (const record of placed) record.object.parent.remove(record.object);
      await sleep(300);
      return out;
    }, pick.key, count);
    rows.push(row);
    console.log("  {} x {}".replace("{}", row.key).replace("{}", String(row.count))
      + "  ->  " + row.calls + " calls, "
      + row.triangles.toLocaleString() + " triangles, "
      + row.median.toFixed(1) + " ms/frame");
  }
  console.log();
}

console.log("Per prop, derived:");
for (const pick of [picks.median, picks.tree].filter(Boolean)) {
  const mine = rows.filter((r) => r.key === pick.key);
  if (mine.length < 2) continue;
  const a = mine[0], b = mine[mine.length - 1];
  const callsEach = (b.calls - a.calls) / (b.count - a.count);
  const trisEach = (b.triangles - a.triangles) / (b.count - a.count);
  console.log("  " + pick.key + ": " + callsEach.toFixed(2) + " draw calls and "
    + Math.round(trisEach).toLocaleString() + " triangles each");
  console.log("    25 M triangle budget allows about "
    + Math.floor(25e6 / trisEach).toLocaleString() + " of them");
}
await browser.close();
