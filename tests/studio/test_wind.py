"""The wind through what is placed (bench/studio/static/wind.js).

Param, 2026-09-13: "add in wind and movement of the objects ... getting
shadows right with that is the key to sell it."

wind.js imports nothing, so node runs its arithmetic here, and splices it
into the vendored three's own vertex chunks to show where it lands. The
studio's wiring -- the prop's materials and its shadow's wearing the same
sway, the clock, the cull and the dials -- is pinned against the page.

Measured in the browser on his wood with the ground cover cleared: a patch
of ground in the beeches' shade changed between two instants of the wind's
clock by 0.276 of a level on average with the wind at full strength; by 0
with no wind; and by 0 with the wind on but the shadow materials taken away,
which is the fake wind this is built not to be. The canopy moved and the
trunks stood.
"""

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
WIND = STATIC / "wind.js"
STUDIO_JS = STATIC / "studio.js"
INDEX = STATIC / "index.html"
THREE_JS = STATIC / "vendor" / "three.module.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run_node(tmp_path, source):
    script = tmp_path / "check.mjs"
    script.write_text(
        source.replace("%WIND%", json.dumps(WIND.as_uri()))
        .replace("%THREE%", json.dumps(THREE_JS.as_uri())),
        encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


def _body(js, signature):
    start = js.index(signature)
    return js[start:js.index("\n}", start)]


MOTION_CHECK = textwrap.dedent("""
    import {
      windOffset, windParameters, windUniformsFrom, adoptWind, WIND_DEFAULTS,
      WIND_ACROSS, WIND_FLUTTER_METRES, WIND_FLUTTER_SHARE,
    } from %WIND%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    const near = (a, b, tol = 1e-9) => Math.abs(a - b) < tol;
    const len = (v) => Math.hypot(v[0], v[1], v[2]);

    const beech = windParameters(25);
    const grass = windParameters(0.3);
    const air = (time, extra = {}) => ({ time, strength: 1, gusts: 0.5, direction: [1, 0], ...extra });

    // THE MODEL'S OWN WIND: a tall tree leans a smaller share of itself and
    // sways more slowly than a blade of grass.
    expect(beech.bend < grass.bend, "a beech is stiffer than grass");
    expect(beech.frequency < grass.frequency, "and slower");
    expect(beech.bend * beech.height > grass.bend * grass.height, "but its tip still travels further");

    // CALM IS STILL, and the feet are planted whatever the wind.
    expect(len(windOffset([1, 2, 20], [5, 5, 0], 1, beech, air(3, { strength: 0 }), true)) === 0,
      "no wind, no movement");
    for (let t = 0; t < 20; t += 0.37) {
      const foot = windOffset([0.3, -0.2, 0], [5, 5, 0], 1.1, beech, air(t), true);
      expect(len(foot) < 1e-12, "the feet never move (t " + t + ")");
    }

    // BOUNDED: the tip never leans further than the bend allows, plus the
    // side wobble and the flutter.
    let furthest = 0;
    for (let t = 0; t < 60; t += 0.05) {
      const tip = windOffset([0, 0, 25], [13, -7, 0], 1, beech, air(t), true);
      furthest = Math.max(furthest, Math.hypot(tip[0], tip[1]));
      // A bent stem is no longer: the tip comes down, never up, from the lean.
      const bare = windOffset([0, 0, 25], [13, -7, 0], 1, beech, air(t), false);
      expect(bare[2] <= 1e-12, "the tip drops as it leans");
    }
    const limit = beech.bend * beech.height * Math.hypot(1, WIND_ACROSS)
      + Math.min(WIND_FLUTTER_METRES, WIND_FLUTTER_SHARE * beech.height) * Math.SQRT2;
    expect(furthest <= limit + 1e-9, "never past the bend: " + furthest + " of " + limit);
    expect(furthest > 0.5 * beech.bend * beech.height, "and it does lean: " + furthest);

    // DOWNWIND ON AVERAGE: over time the tip leans the way the air moves.
    let along = 0, across = 0, samples = 0;
    for (let t = 0; t < 120; t += 0.1) {
      const tip = windOffset([0, 0, 25], [3, 4, 0], 1, beech, air(t, { direction: [0, 1] }), false);
      along += tip[1]; across += tip[0]; samples += 1;
    }
    expect(along / samples > 5 * Math.abs(across / samples), "the lean is downwind");

    // CONTINUOUS in time, so a take has no jumps between frames.
    for (let t = 0; t < 10; t += 0.5) {
      const a = windOffset([0.2, 0.1, 0.25], [2, 2, 0], 1, grass, air(t), true);
      const b = windOffset([0.2, 0.1, 0.25], [2, 2, 0], 1, grass, air(t + 1 / 240), true);
      expect(len([a[0] - b[0], a[1] - b[1], a[2] - b[2]]) < 0.02, "a 240th of a second moves little");
    }

    // OUT OF STEP: two neighbours do not sway in unison.
    let apart = 0;
    for (let t = 0; t < 10; t += 0.25) {
      const a = windOffset([0, 0, 0.3], [0, 0, 0], 1, grass, air(t, { gusts: 0 }), false);
      const b = windOffset([0, 0, 0.3], [0.7, 0.3, 0], 1, grass, air(t, { gusts: 0 }), false);
      apart += Math.abs(a[0] - b[0]);
    }
    expect(apart > 0.01, "neighbours are out of step");

    // GUSTS come and go across the site; with none, the air is steady.
    const swayOnly = (t) => windOffset([0, 0, 25], [40, 0, 0], 1, beech, air(t, { gusts: 0 }), false);
    const gusting = (t) => windOffset([0, 0, 25], [40, 0, 0], 1, beech, air(t, { gusts: 1 }), false);
    let lo = Infinity, hi = -Infinity, loG = Infinity, hiG = -Infinity;
    for (let t = 0; t < 40; t += 0.1) {
      lo = Math.min(lo, swayOnly(t)[0]); hi = Math.max(hi, swayOnly(t)[0]);
      loG = Math.min(loG, gusting(t)[0]); hiG = Math.max(hiG, gusting(t)[0]);
    }
    expect(hi - lo < hiG - loG, "gusts widen how much it moves");

    // FLUTTER is the cards' alone.
    let flutters = 0;
    for (let t = 0; t < 5; t += 0.1) {
      const leaf = windOffset([0.4, 0.2, 20], [1, 1, 0], 1, beech, air(t), true);
      const bark = windOffset([0.4, 0.2, 20], [1, 1, 0], 1, beech, air(t), false);
      flutters += len([leaf[0] - bark[0], leaf[1] - bark[1], leaf[2] - bark[2]]);
    }
    expect(flutters > 0, "a leaf flutters where bark does not");

    // THE DIALS. The wind comes FROM the dial's direction, measured as the
    // sun's azimuth is, and moves the other way.
    const from0 = windUniformsFrom({ strength: 100, from: 0, gusts: 50 });
    expect(near(from0.direction[0], -1) && near(from0.direction[1], 0), "from +x blows toward -x");
    const from90 = windUniformsFrom({ strength: 50, from: 90, gusts: 0 });
    expect(near(from90.direction[1], -1, 1e-9) && from90.strength === 0.5 && from90.gusts === 0, "fractions");
    // A light breeze by default (Param, 2026-09-14: "have the wind on as
    // default set to like 10%"), and an old scene comes back in it.
    expect(WIND_DEFAULTS.strength === 10, "a tenth by default");
    expect(adoptWind(null).strength === 10 && adoptWind({}).from === WIND_DEFAULTS.from, "an old scene is the default breeze");
    expect(adoptWind({ strength: 400, from: -20, gusts: 30 }).strength === 100, "clamped high");
    expect(adoptWind({ strength: 400, from: -20, gusts: 30 }).from === 0, "clamped low");
    expect(adoptWind({ strength: 40, from: 90, gusts: 30 }).gusts === 30, "kept");
    console.log("ok");
""")


@needs_node
def test_the_wind_leans_sways_gusts_and_flutters_with_the_feet_planted(tmp_path):
    assert "ok" in _run_node(tmp_path, MOTION_CHECK)


SPLICE_CHECK = textwrap.dedent("""
    import * as THREE from %THREE%;
    import { applyWind } from %WIND%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    const air = { windTime: { value: 3 } };
    const model = { windHeight: { value: 25 } };

    // A lit material's vertex stage: both places a vertex is moved by its
    // instance get the offset, inside the instancing block.
    const lit = { uniforms: {}, alphaTest: false, vertexShader: THREE.ShaderLib.standard.vertexShader };
    expect(applyWind(lit, THREE.ShaderChunk, { ...air, ...model }) === 2, "both chunks reached");
    const v = lit.vertexShader;
    expect(v.includes("mvPosition = instanceMatrix * mvPosition;\\n\\tmvPosition.xyz += windOffset( transformed, instanceMatrix );"),
      "drawn where it sways");
    expect(v.includes("worldPosition = instanceMatrix * worldPosition;\\n\\tworldPosition.xyz += windOffset( transformed, instanceMatrix );"),
      "and shadowed and reflected from where it sways");
    const instancing = v.indexOf("#ifdef USE_INSTANCING", v.indexOf("void main() {"));
    expect(instancing > 0 && v.indexOf("mvPosition.xyz += windOffset") > instancing, "only for instances");
    expect(v.indexOf("vec3 windOffset(") < v.indexOf("void main() {"), "the function before main");
    expect(!v.includes("#define WIND_FLUTTER\\n"), "bark does not flutter");
    expect(!v.includes("#include <project_vertex>") && !v.includes("#include <worldpos_vertex>"), "no include left behind");
    expect(lit.uniforms.windTime === air.windTime, "the air is held by reference, so one write moves all");
    expect(lit.uniforms.windHeight === model.windHeight, "and the model's own numbers");

    // THE SHADOW'S vertex stage: the depth material has project_vertex alone.
    const depth = { uniforms: {}, alphaTest: true, vertexShader: THREE.ShaderLib.depth.vertexShader };
    expect(applyWind(depth, THREE.ShaderChunk, { ...air, ...model }) === 1, "the shadow sways the same way");
    expect(depth.vertexShader.includes("#define WIND_FLUTTER\\n"), "and a leaf card's shadow flutters with it");

    // A three that has moved the line is loud, not quietly still.
    const moved = { ...THREE.ShaderChunk,
      project_vertex: THREE.ShaderChunk.project_vertex.replace("mvPosition = instanceMatrix * mvPosition;", "mvPosition = mvPosition;") };
    const lost = { uniforms: {}, alphaTest: false, vertexShader: THREE.ShaderLib.depth.vertexShader };
    expect(applyWind(lost, moved, air) === 0, "nothing reached is answered as nothing");
    console.log("ok");
""")


@needs_node
def test_the_sway_is_spliced_where_three_moves_an_instance(tmp_path):
    assert "ok" in _run_node(tmp_path, SPLICE_CHECK)


def test_the_glsl_is_the_js_twin():
    """The shader and the tested arithmetic are the same formula: the terms
    that decide how far and which way are pinned in both."""

    module = WIND.read_text(encoding="utf-8")
    js_part = module[module.index("export function windOffset("):module.index("export const WIND_GLSL")]
    glsl = module[module.index("export const WIND_GLSL"):module.index("const PROJECT_AT")]
    for js_term, glsl_term in (
        ("const weight = above * above;", "float weight = above * above;"),
        ("air.gusts * (0.5 - 0.5 * Math.sin(front * 0.09 - air.time * 1.3",
         "windGusts * ( 0.5 - 0.5 * sin( front * 0.09 - windTime * 1.3"),
        ("0.7 + 0.3 * Math.sin(air.time * model.frequency * 2 * Math.PI + seed)",
         "0.7 + 0.3 * sin( windTime * windFrequency * 6.283185307 + seed )"),
        ("const reach = air.strength * model.bend * height * weight;",
         "float reach = windStrength * windBend * height * weight;"),
        ("Math.sin(air.time * model.frequency * 4.7 + seed * 1.7)",
         "sin( windTime * windFrequency * 4.7 + seed * 1.7 )"),
        ("-Math.min((out[0] * out[0] + out[1] * out[1]) / (2 * up), 0.5 * up)",
         "- min( dot( offset.xy, offset.xy ) / ( 2.0 * up ), 0.5 * up )"),
        ("Math.min(WIND_FLUTTER_METRES * scale, WIND_FLUTTER_SHARE * height)",
         "min( WIND_FLUTTER_METRES * scale, WIND_FLUTTER_SHARE * height )"),
    ):
        assert js_term in js_part, js_term
        assert glsl_term in glsl, glsl_term


def test_a_prop_and_its_shadow_wear_the_same_wind():
    js = STUDIO_JS.read_text(encoding="utf-8")

    compile_ = _body(js, "function windCompile(shader)")
    assert "atmosphere.inject(shader);" in compile_
    assert "applyWind(shader, THREE.ShaderChunk," in compile_
    assert "Object.assign({}, windAir, this.userData.windModel)" in compile_
    assert "reportProblem(" in compile_, "a three that moved the chunks is loud"

    wear = _body(js, "function wearWind(material, windModel)")
    assert "material.onBeforeCompile = windCompile;" in wear
    assert "material.needsUpdate = true;" in wear
    assert js.count(".onBeforeCompile = windCompile;") == 1

    batch = _body(js, "function propBatch(type, template)")
    assert "const model = windParameters(box.max.z - box.min.z);" in batch
    assert "wearWind(material, windModel);" in batch
    assert "windDepth: shadowOf(new THREE.MeshDepthMaterial())," in batch
    assert "windDistance: shadowOf(new THREE.MeshDistanceMaterial())," in batch
    size = _body(js, "function sizeCluster(batch, cluster)")
    assert "mesh.customDepthMaterial = batch.windDepth;" in size
    assert "mesh.customDistanceMaterial = batch.windDistance;" in size

    # A leaning tree does not pop out of view at the frame's edge.
    settle = _body(js, "function settleClusters(batch, reach, height)")
    assert "propCullSphere.radius = cluster.radius + batch.windReach * windAir.windStrength.value;" in settle


def test_the_wind_keeps_its_own_clock():
    js = STUDIO_JS.read_text(encoding="utf-8")

    # Live: in the frame loop, only while there is wind, never in a still.
    loop = _body(js, "function frame(now)")
    assert "if (!state.recording && windAir.windStrength.value > 0) windAir.windTime.value += delta;" in loop
    assert "windAir" not in _body(js, "function renderView()"), "renderView reads no clock"

    # A take: the take's own clock, frame by frame, and the live one back after.
    take = _body(js, "async function recordAnimation()")
    assert "windAir.windTime.value = frameIndex / fps;" in take
    assert take.index("windAir.windTime.value = frameIndex / fps;") < take.index("applyTimeline(frameIndex * speed / fps);")
    assert "const windWas = windAir.windTime.value;" in take
    assert "windAir.windTime.value = windWas;" in take[take.index("} finally {"):]

    # The rays re-march while the trees move.
    changed = _body(js, "function shaftsChanged()")
    assert "put(windAir.windTime.value);" in changed
    assert "put(windAir.windStrength.value);" in changed


def test_the_wind_dials_and_the_scene():
    js = STUDIO_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    settings = html[html.index('<div id="shelf-sky-settings"'):]
    settings = settings[:settings.index('<div id="prop-tiles"')]
    for ident, unit, rest in (("wind-strength", "%", "10"), ("wind-from", "&deg;", "225"),
                              ("wind-gusts", "%", "50")):
        tag = re.search(r'<input id="' + ident + r'" type="range"([^>]*)>', settings)
        assert tag, ident
        assert 'value="' + rest + '"' in tag.group(1), ident
        assert '<b id="' + ident + '-value">' + rest + "</b><em>" + unit + "</em>" in settings, ident
    # None rests at nought, so none declares its unit (section 3).
    for ident in ("wind-strength", "wind-from", "wind-gusts"):
        assert 'id="' + ident + '" type="range" data-unit' not in settings, ident

    assert '["wind-strength", "strength", 0],' in js
    apply_ = _body(js, "function applyWindState()")
    assert "windAir.windDirection.value.set(air.direction[0], air.direction[1]);" in apply_
    assert "wind: { ...state.wind }," in js, "a scene carries its wind"
    assert "state.wind = adoptWind(scene_.wind);" in js
    assert "wind: { ...WIND_DEFAULTS }," in js, "and the studio starts in the default breeze"
    boot = js[js.index("applyWindState();", js.index("function syncWindControls()")):]
    assert boot.index("applyWindState();") < boot.index("for (const [id, key, digits] of WIND_DIALS)"), (
        "with the air set before the first frame")
