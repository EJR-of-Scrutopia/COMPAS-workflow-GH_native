"""The atmosphere: an exponential height fog (bench/studio/static/atmosphere.js).

atmosphere.js imports nothing, so node runs its arithmetic here against the
integral's own limits and against brute-force quadrature. The shader carries
the same functions in GLSL; the pins below hold how that GLSL reaches every
fogged material and the Sky, how the one fog object is kept, and how a scene
carries the atmosphere in and out."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "bench" / "studio" / "static"
ATMOSPHERE = STATIC / "atmosphere.js"
FIELDS = STATIC / "fields.js"
STUDIO_JS = STATIC / "studio.js"
INDEX = STATIC / "index.html"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run_node(tmp_path, source):
    script = tmp_path / "check.mjs"
    script.write_text(
        source.replace("%ATMOSPHERE%", json.dumps(ATMOSPHERE.as_uri()))
        .replace("%FIELDS%", json.dumps(FIELDS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


def _body(js, signature):
    """The text of a function from its signature to its matching brace."""
    start = js.index(signature)
    opening = js.index("{", start + len(signature) - 1)
    depth = 0
    for at in range(opening, len(js)):
        if js[at] == "{":
            depth += 1
        elif js[at] == "}":
            depth -= 1
            if depth == 0:
                return js[start:at + 1]
    raise AssertionError("unbalanced braces after " + signature)


INTEGRAL_CHECK = textwrap.dedent("""
    import {
      layerOpticalDepth, atmosphereOpticalDepth, atmosphereAmounts,
    } from %ATMOSPHERE%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b, rel) { return Math.abs(a - b) <= rel * Math.max(1e-12, Math.abs(b)); }

    // Brute force: the midpoint rule over the density along the ray.
    function quadrature(k, f, h0, dz, d, steps = 200000) {
      let sum = 0;
      const ds = d / steps;
      for (let i = 0; i < steps; i++) sum += k * Math.exp(-f * (h0 + dz * (i + 0.5) * ds));
      return sum * ds;
    }

    // Zero density gives zero, whatever the ray.
    for (const dz of [-0.9, -0.1, 0, 0.1, 0.9]) {
      expect(layerOpticalDepth(0, 0.5, 3, dz, 400) === 0, "no density, no fog");
    }
    // Zero falloff is plain exponential distance fog: k times the length.
    for (const dz of [-0.9, -0.3, 0, 0.3, 0.9]) {
      expect(near(layerOpticalDepth(0.02, 0, 7, dz, 250), 0.02 * 250, 1e-12),
        "zero falloff reduces to exponential distance fog (dz " + dz + ")");
    }
    // A horizontal ray sees the density of its own height, all the way.
    expect(near(layerOpticalDepth(0.01, 0.2, 5, 0, 300), 0.01 * Math.exp(-1) * 300, 1e-12),
      "a level ray sees its height's density");
    // The closed form agrees with brute force, up, down, shallow and steep,
    // across both branches (|f dz d| either side of 1e-3).
    const rays = [
      [0.05, 1 / 1.7, 1.7, -0.02, 80], [0.05, 1 / 1.7, 1.7, 0.3, 80],
      [0.003, 1 / 30, 14, -0.45, 40], [0.003, 1 / 30, 14, 0.9, 900],
      [0.02, 1 / 60, 0.5, 1e-7, 500], [0.02, 1 / 25, 30, -0.99, 29],
    ];
    for (const [k, f, h0, dz, d] of rays) {
      const exact = layerOpticalDepth(k, f, h0, dz, d);
      const brute = quadrature(k, f, h0, dz, d);
      expect(near(exact, brute, 1e-6),
        "closed form " + exact + " against quadrature " + brute + " for " + [k, f, h0, dz, d]);
    }
    // Two layers add, and nothing lies before the start distance.
    const layers = {
      density: [0.004, 0.03], falloff: [1 / 40, 1 / 1.5], base: 0, start: 20,
      maxOpacity: 0.9, sunStart: 0, sunExponent: 8, sunGlow: 1,
    };
    const both = atmosphereOpticalDepth(layers, 1.7, -0.02, 70, 20);
    const h0 = 1.7 - 0.02 * 20;
    const parts = layerOpticalDepth(0.004, 1 / 40, h0, -0.02, 50)
      + layerOpticalDepth(0.03, 1 / 1.5, h0, -0.02, 50);
    expect(near(both, parts, 1e-12), "the two layers add");
    expect(atmosphereOpticalDepth(layers, 1.7, 0, 15, 20) === 0, "nothing before the start");
    // Height: at the same distance, a ray from lower down sees more fog.
    expect(atmosphereOpticalDepth(layers, 0.5, 0, 60, 0)
      > atmosphereOpticalDepth(layers, 8, 0, 60, 0), "the fog thickens toward the ground");
    // The cap holds, and the sun's glow has its own start.
    const [veil, glow] = atmosphereAmounts({ ...layers, density: [5, 5] }, 1, 0, 1000);
    expect(veil === 0.9 && glow === 0.9, "max opacity caps both amounts");
    const [nearVeil, nearGlow] = atmosphereAmounts(layers, 1.7, 0, 20);
    expect(nearVeil === 0 && nearGlow > 0, "the glow starts where its own start says");
    // Deep in the fog the overflow guard keeps every answer finite.
    expect(Number.isFinite(layerOpticalDepth(0.05, 2, -60, -0.5, 400)), "finite deep in the fog");
    // Deep under the base the exponent caps must never cancel. The case
    // that found it: Valley fog's mist, the base 20 m up, a 0.4 m mist
    // height, the eye at 1.7 m (18.3 m under the base). Every ray there is
    // in a whiteout, and a ray falling toward the floor passes through
    // more mist than a level one of the same length, never less.
    for (const dz of [-0.001, -0.01, -0.05, -0.2, -0.5, -0.99]) {
      const d = Math.min(2000, 1.7 / -dz);
      const steep = layerOpticalDepth(0.05, 2.5, -18.3, dz, d);
      const level = layerOpticalDepth(0.05, 2.5, -18.3, 0, d);
      expect(steep >= level && steep > 50,
        "a falling ray from under the base is in the whiteout too (dz " + dz + ": " + steep + ")");
    }
    // Rising from lower down never sees less fog: the depth never increases
    // with the start height, across the cap and on either side of it, and
    // no answer overflows a 32-bit float (the shader's).
    for (const f of [2.5, 1 / 1.5, 1 / 30, 5]) {
      for (const dz of [-0.9, -0.2, -1e-4, 0, 1e-4, 0.2, 0.9]) {
        for (const d of [0.5, 40, 2000]) {
          let above = layerOpticalDepth(0.05, f, -120, dz, d);
          for (let h0 = -119.75; h0 <= 10; h0 += 0.25) {
            const here = layerOpticalDepth(0.05, f, h0, dz, d);
            expect(here <= above * (1 + 1e-9) && here < 3.4e38,
              "depth " + here + " after " + above + " at h0 " + h0 + " (f " + f + ", dz " + dz + ", d " + d + ")");
            above = here;
          }
        }
      }
    }
    console.log("ok");
""")


@needs_node
def test_the_height_fog_integral_meets_its_limits_and_brute_force(tmp_path):
    assert "ok" in _run_node(tmp_path, INTEGRAL_CHECK)


# The GLSL is what renders, and the JS twin is what the tests above hold to
# the integral's limits. This translates the module's own GLSL into JS (the
# functions are scalar but for dir, which stays an {x, y, z}, and the three
# colours, which are run one channel at a time) and runs it against the twin
# over seeded random rays, so the two cannot quietly drift apart.
GLSL_TWIN_CHECK = textwrap.dedent(r"""
    import {
      ATMOSPHERE_SKY_GLSL, layerOpticalDepth, atmosphereOpticalDepth, atmosphereAmounts,
    } from %ATMOSPHERE%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) <= 1e-9 * Math.max(1e-12, Math.abs(a), Math.abs(b)); }

    function translate(glsl) {
      let js = glsl.split("\n").filter((line) => !/^\s*uniform\s/.test(line)).join("\n");
      js = js.replace(/^(?:float|vec2|vec3)\s+(\w+)\(([^)]*)\)\s*\{/gm, (whole, name, params) =>
        "function " + name + "(" + params.split(",").map((p) => p.trim().split(/\s+/).pop())
          .filter(Boolean).join(", ") + ") {");
      js = js.replace(/\b(?:float|vec2|vec3)\s+(\w+)\s*=/g, "let $1 =");
      js = js.replace(/(?<![\w.])(exp|min|max|abs|pow)\s*\(/g, "Math.$1(");
      js = js.replace(/(?<![\w.])vec2\s*\(/g, "glslVec2(");
      js = js.replace(/(?<![\w.])dot\s*\(/g, "glslDot(");
      const left = js.match(/\b(float|vec2|vec3|vec4|uniform|mix|clamp)\b/);
      expect(!left, "the translation left GLSL behind: " + (left && left[0]));
      return js;
    }
    const UNIFORMS = ["atmoDensity", "atmoFalloff", "atmoBase", "atmoStart", "atmoMaxOpacity",
      "atmoSunStart", "atmoSunExponent", "atmoSunColour", "atmoSunDir", "atmoSkyColour",
      "atmoSkyDistance", "cameraPosition"];
    const source = translate(ATMOSPHERE_SKY_GLSL);
    const build = new Function(...UNIFORMS, "glslVec2", "glslDot", source
      + "\nreturn { atmosphereLayer, atmosphereDepth, atmosphereAmounts, atmosphereApply, atmosphereSky };");
    const glslVec2 = (x, y) => ({ x, y });
    const glslDot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;

    let seed = 20260911;
    function random() {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    const between = (low, high) => low + (high - low) * random();
    function unit(x, y, z) { const n = Math.hypot(x, y, z); return { x: x / n, y: y / n, z: z / n }; }

    let taylor = 0, pastEnd = 0, capped = 0;
    for (let n = 0; n < 600; n++) {
      const layers = {
        density: [random() < 0.1 ? 0 : between(0, 0.05), random() < 0.3 ? 0 : between(0, 0.1)],
        falloff: [1 / between(0.5, 200), 1 / between(0.2, 20)],
        base: between(-5, 50), start: between(0, 100), maxOpacity: between(0, 1),
        sunStart: between(0, 200), sunExponent: between(1, 64),
      };
      const cameraZ = between(-2, 60);
      // Every fifth ray starts deep under the base in thin layers, where
      // both exponents meet the cap. Written as a difference those two
      // capped terms cancelled, so a whiteout read as clear air; left to
      // chance the rays reached that branch once in six hundred.
      if (n % 5 === 4) {
        layers.base = cameraZ + between(60, 200);
        layers.falloff = [1 / between(0.2, 1), 1 / between(0.2, 1)];
      }
      const kind = n % 4;
      const dz = kind === 0 ? 0 : kind === 1 ? between(-1e-5, 1e-5) : between(-1, 1);
      const dir = unit(between(-1, 1), between(-1, 1), 0);
      const lift = Math.sqrt(1 - dz * dz);
      dir.x *= lift; dir.y *= lift; dir.z = dz;
      const L = random() < 0.25 ? between(0.01, 20) : between(0.01, 2000);
      const sunDir = unit(between(-1, 1), between(-1, 1), between(-0.3, 1));
      const sunColour = [between(0, 3), between(0, 3), between(0, 3)];
      const skyColour = [between(0, 1), between(0, 1), between(0, 1)];
      const colour = [between(0, 2), between(0, 2), between(0, 2)];
      const ambient = [between(0, 1), between(0, 1), between(0, 1)];
      const glsl = (channel) => build(
        { x: layers.density[0], y: layers.density[1] }, { x: layers.falloff[0], y: layers.falloff[1] },
        layers.base, layers.start, layers.maxOpacity, layers.sunStart, layers.sunExponent,
        sunColour[channel], sunDir, skyColour[channel], 2000, { z: cameraZ }, glslVec2, glslDot);
      const shader = glsl(0);
      const where = "case " + n + " " + JSON.stringify({ layers, cameraZ, dir, L });

      // One layer, over segments that start anywhere, including far under the base.
      const h0 = cameraZ - layers.base;
      for (const [k, f] of [[layers.density[0], layers.falloff[0]], [layers.density[1], layers.falloff[1]]]) {
        const fall = Math.abs(f * dz * L);
        if (fall > 0 && fall <= 1e-3 && k > 0) taylor += 1;
        if (-f * h0 > 40) capped += 1;
        expect(near(shader.atmosphereLayer(k, f, h0, dz, L), layerOpticalDepth(k, f, h0, dz, L)),
          "atmosphereLayer is layerOpticalDepth, " + where);
      }
      // Both layers from the eye, for each start (the veil's and the glow's).
      for (const start of [layers.start, layers.sunStart]) {
        if (start > L && dz !== 0) pastEnd += 1;
        expect(near(shader.atmosphereDepth(dir, L, start),
          atmosphereOpticalDepth(layers, cameraZ, dz, L, start)),
          "atmosphereDepth is atmosphereOpticalDepth, " + where);
      }
      const amounts = shader.atmosphereAmounts(dir, L);
      const [veil, glow] = atmosphereAmounts(layers, cameraZ, dz, L);
      expect(near(amounts.x, veil) && near(amounts.y, glow), "atmosphereAmounts, " + where);
      // What reaches the pixel, channel by channel: the veil over the colour
      // toward the ambient, and the sun's lobe carried by the glow.
      const lobe = Math.pow(Math.max(glslDot(dir, sunDir), 0), layers.sunExponent);
      const skyAmounts = atmosphereAmounts(layers, cameraZ, dz, 2000);
      for (let channel = 0; channel < 3; channel++) {
        const run = glsl(channel);
        const pixel = colour[channel] * (1 - veil) + ambient[channel] * veil + sunColour[channel] * lobe * glow;
        expect(near(run.atmosphereApply(colour[channel], ambient[channel], dir, L), pixel),
          "atmosphereApply, channel " + channel + ", " + where);
        const skyPixel = colour[channel] * (1 - skyAmounts[0]) + skyColour[channel] * skyAmounts[0]
          + sunColour[channel] * lobe * skyAmounts[1];
        expect(near(run.atmosphereSky(colour[channel], dir), skyPixel),
          "atmosphereSky, channel " + channel + ", " + where);
      }
    }
    // The rays reached every branch the functions have.
    expect(taylor >= 20, "the Taylor branch was reached " + taylor + " times");
    expect(pastEnd >= 20, "a start past the ray's end was reached " + pastEnd + " times");
    expect(capped >= 20, "the exponent cap was reached " + capped + " times");
    console.log("ok " + JSON.stringify({ taylor, pastEnd, capped }));
""")


@needs_node
def test_the_shader_s_fog_is_its_tested_js_twin(tmp_path):
    assert "ok" in _run_node(tmp_path, GLSL_TWIN_CHECK)


PRESET_CHECK = textwrap.dedent("""
    import {
      ATMOSPHERE_PRESETS, ATMOSPHERE_RANGES, ATMOSPHERE_KEYS, atmosphereFromPreset,
      adoptAtmosphere, atmosphereIsOn, atmosphereLayers, atmospherePreviewPixels,
    } from %ATMOSPHERE%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    expect(Object.keys(ATMOSPHERE_PRESETS)[0] === "none", "None comes first");
    const labels = new Set();
    for (const [key, preset] of Object.entries(ATMOSPHERE_PRESETS)) {
      expect(!labels.has(preset.label), "labels are unique");
      labels.add(preset.label);
      if (key === "none") continue;
      for (const name of ATMOSPHERE_KEYS) {
        const [low, high] = ATMOSPHERE_RANGES[name];
        expect(typeof preset[name] === "number" && preset[name] >= low && preset[name] <= high,
          key + "." + name + " is a number inside its dial's range");
      }
      const layers = atmosphereLayers(atmosphereFromPreset(key), 0);
      expect(layers.density[0] + layers.density[1] > 0, key + " has some fog in it");
      expect(layers.maxOpacity > 0 && layers.maxOpacity <= 1, key + " caps as a fraction");
    }
    expect(!atmosphereIsOn(atmosphereFromPreset("none")), "None is off");
    expect(atmosphereFromPreset("not-a-preset").preset === "none", "an unknown key is None");
    // A scene from before the atmosphere carries none, and loads as None.
    expect(adoptAtmosphere(undefined).preset === "none", "an old scene is None");
    expect(adoptAtmosphere({ preset: "bogus", density: 9 }).preset === "none", "a bad preset is None");
    const kept = adoptAtmosphere({ preset: "haze", density: 999, height: -4, start: "x" });
    expect(kept.preset === "haze" && kept.density === 50 && kept.height === 0.5
      && kept.start === ATMOSPHERE_PRESETS.haze.start, "a saved scene is clamped, not trusted");
    // The tiles tell the presets apart: Valley fog veils the far arch far
    // more than None, where it stands in clear air.
    const w = 128, h = 64;
    const clear = atmospherePreviewPixels(w, h, atmosphereFromPreset("none"));
    const valley = atmospherePreviewPixels(w, h, atmosphereFromPreset("valley-fog"));
    let differ = 0;
    for (let i = 0; i < clear.length; i += 4) differ += Math.abs(clear[i] - valley[i]);
    expect(differ / (w * h) > 10, "a fogged tile is not the clear one");
    console.log(JSON.stringify({ ranges: ATMOSPHERE_RANGES,
      labels: Object.fromEntries(Object.entries(ATMOSPHERE_PRESETS).map(([k, v]) => [k, v.label])) }));
""")


@needs_node
def test_the_presets_are_sane_and_the_page_offers_exactly_them(tmp_path):
    table = json.loads(_run_node(tmp_path, PRESET_CHECK).strip().splitlines()[-1])
    html = INDEX.read_text(encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")
    select = html[html.index('<select id="atmosphere-preset">'):]
    select = select[:select.index("</select>")]
    options = re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', select)
    assert options == list(table["labels"].items()), "the picker offers every preset, in order"
    assert '<option value="none" selected>None</option>' in select, "None until he picks one"
    # Each dial's range is the module's, so a clamped scene and a dragged
    # dial agree about what is allowed.
    dials = re.findall(r'\["(atmosphere-[a-z-]+)", "([A-Za-z]+)", \d\]', js)
    assert len(dials) == 9
    for ident, key in dials:
        tag = re.search(r'<input id="' + ident + r'" type="range"([^>]*)>', html)
        assert tag, ident + " is a range on the page"
        low = float(re.search(r'min="([^"]+)"', tag.group(1)).group(1))
        high = float(re.search(r'max="([^"]+)"', tag.group(1)).group(1))
        assert [low, high] == table["ranges"][key], ident + " spans its key's range"


HORIZON_CHECK = textwrap.dedent("""
    import { equirectHorizonColour } from %FIELDS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b) { return Math.abs(a - b) < 1e-12; }
    // 64 by 32, four channels. Only row 15's centre (2.8 degrees up) lies
    // in the default 0 to 8 degree band.
    const width = 64, height = 32;
    const data = new Float32Array(width * height * 4).fill(100);
    for (let x = 0; x < width; x++) {
      const i = (15 * width + x) * 4;
      data[i] = 0.5; data[i + 1] = 0.25; data[i + 2] = 1.0;
    }
    const raw = equirectHorizonColour(data, width, height, 4);
    expect(near(raw[0], 0.5) && near(raw[1], 0.25) && near(raw[2], 1.0),
      "the band's mean, and nothing from outside it");
    // Through the backdrop's Reinhard, pixel by pixel.
    const toned = equirectHorizonColour(data, width, height, 4, { exposure: 3.2 });
    const map = (v) => (v * 3.2) / (1 + v * 3.2);
    expect(near(toned[0], map(0.5)) && near(toned[2], map(1.0)), "the Reinhard the backdrop wears");
    // A sun in the band tints the answer and cannot take it over.
    const sunny = Float32Array.from(data);
    sunny[(15 * width + 7) * 4] = 50000;
    const withSun = equirectHorizonColour(sunny, width, height, 4, { exposure: 3.2 });
    expect(withSun[0] < map(0.5) + 1 / width + 1e-9, "the sun is one pixel's worth");
    // Other strides, and a band with nothing in it.
    const rgb = new Float32Array(width * height * 3).fill(0.3);
    expect(near(equirectHorizonColour(rgb, width, height, 3)[1], Math.fround(0.3)), "stride three");
    expect(equirectHorizonColour(data, width, height, 4, { fromDeg: 88.6, toDeg: 88.7 }) === null,
      "an empty band is null");
    console.log("ok");
""")


@needs_node
def test_a_photograph_s_horizon_colour_is_the_mean_of_its_horizon_band(tmp_path):
    assert "ok" in _run_node(tmp_path, HORIZON_CHECK)


def test_the_fog_chunks_are_replaced_before_anything_renders():
    module = ATMOSPHERE.read_text(encoding="utf-8")
    js = STUDIO_JS.read_text(encoding="utf-8")
    for chunk in ("fog_pars_vertex:", "fog_vertex:", "fog_pars_fragment:", "fog_fragment:"):
        assert chunk in module
    install = _body(module, "export function installAtmosphere(THREE, inject)")
    assert "for (const [name, source] of Object.entries(FOG_CHUNKS)) chunks[name] = source;" in install
    assert "THREE.Material.prototype.onBeforeCompile = function atmosphereUniforms(shader) {" in install
    # Three's own fog uniforms stay declared, and its linear term stays:
    # refreshFogUniforms writes them, and Sky mode at None must not change.
    for kept in ("uniform vec3 fogColor;", "uniform float fogNear;", "uniform float fogFar;",
                 "smoothstep( fogNear, fogFar, vFogDepth )",
                 "gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );"):
        assert kept in module, kept
    assert "( vec4( vFogView, 0.0 ) * viewMatrix ).xyz" in module, "the world-space ray"
    assert "vFogView = mvPosition.xyz;" in module
    # Installed in the page before the first program can be built.
    where = js.index("if (!installAtmosphere(THREE, atmosphere.inject)) {")
    assert where < js.index("const pmrem = new THREE.PMREMGenerator(renderer);")
    assert where < js.index("previewRig = buildPreviewRig();")
    assert where < js.index("function renderView()")


def test_every_own_onbeforecompile_chains_the_atmosphere():
    js = STUDIO_JS.read_text(encoding="utf-8")
    hooks = js.count(".onBeforeCompile = ")
    assert hooks >= 1
    assert js.count("atmosphere.inject(shader);") == hooks, (
        "a material with its own onBeforeCompile shadows the prototype's "
        "and must hand the atmosphere its uniforms itself")
    outline = js[js.index("outlineMaterial.onBeforeCompile = (shader) => {"):]
    assert outline.index("atmosphere.inject(shader);") < outline.index("};")


def test_the_one_fog_object_is_made_once_and_kept():
    js = STUDIO_JS.read_text(encoding="utf-8")
    body = _body(js, "function applyEnvironment()")
    assert js.count("new THREE.Fog(") == 1, "one fog object for the life of the page"
    assert "atmosphereFog = atmosphereFog || new THREE.Fog(" in body
    assert "scene.fog = atmosphereFog;" in body
    assert "scene.fog = null;" in body
    assert 'if (state.environmentMode === "sky" || atmosphereIsOn(state.atmosphere)) {' in body
    assert body.count("scene.fog =") == 2, "set in one place, cleared in one"
    # Sky mode at None keeps the weather's own linear haze, exactly.
    apply = _body(js, "function applyAtmosphere()")
    assert 'const linear = state.environmentMode === "sky" && !on;' in apply
    assert "atmosphereFog.near = linear ? preset.fogNear : ATMOSPHERE_LINEAR_OFF;" in apply
    assert "atmosphereFog.far = linear ? preset.fogFar : 2 * ATMOSPHERE_LINEAR_OFF;" in apply
    # A plan or an elevation stays clean.
    assert "on && !camera.isOrthographicCamera" in apply
    assert "applyAtmosphere();" in _body(js, "function setProjection(kind)")


def test_the_sky_takes_the_same_fog_after_its_daylight():
    js = STUDIO_JS.read_text(encoding="utf-8")
    pinned = '"gl_FragColor = vec4( texColor * daylight, 1.0 );");'
    chained = ('.replace("gl_FragColor = vec4( texColor * daylight, 1.0 );",\n'
               '      "gl_FragColor = vec4( atmosphereSky( texColor * daylight, direction ), 1.0 );");')
    assert pinned in js and chained in js
    assert js.index(pinned) < js.index(chained), "chained after the pinned daylight patch"
    assert '.replace("uniform float daylight;", "uniform float daylight;\\n" + ATMOSPHERE_SKY_GLSL)' in js
    assert "Object.assign(shader.uniforms, atmosphere.uniforms);" in js
    # The horizon is measured in the one PMREM site, bare of the dial.
    regenerate = _body(js, "function regenerateEnvironment()")
    assert "skyDaylight.value = 1;\n    const measured = readSkyHorizon(holder);" in regenerate
    assert "const keptAtmosphere = holdAtmosphereForCapture();" in regenerate
    assert regenerate.index("holdAtmosphereForCapture()") < regenerate.index("pmrem.fromScene(")
    # The photograph's horizon, measured on load the way the backdrop shows it.
    assert "equirectHorizonColour(image.data, image.width, image.height, 4," in _body(
        js, "async function loadHdri(name)")
    # The daylight chain ends in the atmosphere's light.
    brightness = _body(js, "function applySkyBrightness()")
    assert brightness.rstrip("}").rstrip().endswith("stars.visible = state.environmentMode === \"sky\" && stars.material.opacity > 0.01;")
    assert "paintAtmosphereLight(dial, night);" in brightness
    light = _body(js, "function paintAtmosphereLight(dial, night)")
    assert "uniforms.atmoSunDir.value.copy(sun.position).normalize();" in light
    assert "ATMOSPHERE_NIGHT_FLOOR * dial * (1 - night)" in light


def test_the_fog_colour_follows_the_sky_whenever_the_sun_moves():
    # The day cycle and the recorder move the sun every frame but capture
    # the environment only every 30; a fog colour measured only at the
    # capture held for 30 frames and then jumped, a strobe through dawn.
    js = STUDIO_JS.read_text(encoding="utf-8")
    sun = _body(js, "function applySunFromTime()")
    assert "followSkyHorizon();\n  applySkyBrightness();" in sun, (
        "measured after the sky has its new sun and before the fog is painted")
    assert "applySunFromTime();" in _body(js, "function applyDayCycle(u)")
    follow = _body(js, "function followSkyHorizon()")
    assert 'if (state.environmentMode !== "sky" || !atmosphereIsOn(state.atmosphere)) return;' in follow
    assert "skyDaylight.value = 1;\n  const measured = readSkyHorizon(horizonHolder);" in follow
    assert "if (skyHorizon) lightBase.fog = skyHorizon.clone();" in follow
    # One read of the strip per measurement: four quarters drawn side by
    # side into one target, not four stalls a frame.
    horizon = _body(js, "function readSkyHorizon(holder)")
    assert horizon.count("renderer.readRenderTargetPixels(") == 1
    loop = horizon[horizon.index("for (let quarter = 0; quarter < 4; quarter++) {"):]
    assert loop.index("horizonTarget.viewport.set(") < loop.index("renderer.readRenderTargetPixels(")
    assert "}\n    renderer.readRenderTargetPixels(" in loop, "read once, after the loop"


def test_nothing_drawn_over_everything_is_veiled():
    js = STUDIO_JS.read_text(encoding="utf-8")
    lines = js.splitlines()
    for number, line in enumerate(lines):
        if "depthTest: false" in line:
            assert "fog: false" in line, "line {} is drawn over everything and fogged".format(number + 1)
        if re.search(r"\.material\.depthTest = false;", line):
            assert ".material.fog = false;" in lines[number + 1], (
                "line {} is drawn over everything and fogged".format(number + 1))


def test_a_scene_carries_its_atmosphere_and_an_old_one_loads_as_none():
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "atmosphere: { ...state.atmosphere }," in _body(js, "function collectScene(options)")
    restore = _body(js, "async function applyScene(record)")
    adopt = restore.index("state.atmosphere = adoptAtmosphere(scene_.atmosphere);")
    assert adopt < restore.index("applyEnvironment();"), "adopted before the environment is applied"
    assert 'control("atmosphere-preset").value = state.atmosphere.preset;' in restore
    assert 'atmosphere: atmosphereFromPreset("none"),' in js, "None when the page opens"
    module = ATMOSPHERE.read_text(encoding="utf-8")
    adopt_body = _body(module, "export function adoptAtmosphere(saved)")
    assert 'return atmosphereFromPreset("none");' in adopt_body


def test_the_atmosphere_lives_in_the_skies_drawer():
    html = INDEX.read_text(encoding="utf-8")
    modes = html[html.index('<div id="shelf-sky-modes"'):html.index('<div id="shelf-sky-settings"')]
    for ident in ('id="atmosphere-picker"', 'id="atmosphere-tiles"', 'id="atmosphere-preset"'):
        assert ident in modes
    settings = html[html.index('<div id="shelf-sky-settings"'):]
    settings = settings[:settings.index('<div id="prop-tiles"')]
    assert settings.count('class="atmosphere-dial hidden"') == 9, "hidden until a preset is chosen"
    js = STUDIO_JS.read_text(encoding="utf-8")
    sync = _body(js, "function syncAtmosphereControls()")
    assert 'label.classList.toggle("hidden", !on);' in sync
    assert 'document.getElementById(id + "-value").textContent' in sync
