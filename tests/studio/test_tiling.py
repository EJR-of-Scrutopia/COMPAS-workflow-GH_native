"""Breaking the floor's repeat (bench/studio/static/tiling.js).

Param, 2026-09-12: "at the moment randomise uv just rotates all uv to a
random orientation. but what it should mean is every instance randomises,
so that the repeating is different throughout and it helps to hide some
of the errors where repetition is too noticable on surfaces."

tiling.js imports nothing, so node runs its arithmetic here: the lattice
is a partition of unity, the blend is continuous, the hash scatters, and
the blend keeps the picture's contrast. The shader carries the same
functions in GLSL, and the pins below hold the two together and hold how
the GLSL reaches the floor.
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
TILING = STATIC / "tiling.js"
STUDIO_JS = STATIC / "studio.js"
INDEX = STATIC / "index.html"

needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")


def _run_node(tmp_path, source):
    script = tmp_path / "check.mjs"
    script.write_text(source.replace("%TILING%", json.dumps(TILING.as_uri())),
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


def _body(js, header):
    start = js.index(header)
    return js[start:js.index("\n}", start)]


LATTICE_CHECK = textwrap.dedent(r"""
    import { hexWeights, tileOffset, sharpenWeights, blendAt, LATTICE_SCALE,
      BLEND_SHARPNESS } from %TILING%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }

    // 1. A PARTITION OF UNITY, everywhere and without negatives. If the
    // three weights did not sum to one the floor would change brightness
    // from triangle to triangle, which is a worse artefact than the one
    // being fixed.
    let worstSum = 0, worstNegative = 0;
    for (let i = 0; i < 40000; i++) {
      const u = (Math.random() - 0.5) * 60;
      const v = (Math.random() - 0.5) * 60;
      const { cells, weights } = hexWeights(u, v);
      expect(cells.length === 3 && weights.length === 3, "three of each");
      for (const c of cells) {
        expect(Number.isInteger(c[0]) && Number.isInteger(c[1]),
          "a lattice vertex is a whole cell, or the hash is fed a fraction "
          + "and every point gets its own offset");
      }
      worstSum = Math.max(worstSum, Math.abs(weights[0] + weights[1] + weights[2] - 1));
      worstNegative = Math.min(worstNegative, Math.min(...weights));
    }
    expect(worstSum < 1e-9, "the weights sum to one (worst " + worstSum + ")");
    expect(worstNegative >= -1e-12, "no weight is negative");

    // 2. CONTINUOUS, including across the diagonal that splits each cell
    // into its two triangles. A discontinuity there is a seam, which is
    // the whole thing this technique exists to avoid.
    const picture = (u, v) => Math.sin(u * 12.9898 + v * 78.233) * 0.5 + 0.5;
    let worstJump = 0;
    for (let i = 0; i < 40000; i++) {
      const u = (Math.random() - 0.5) * 20;
      const v = (Math.random() - 0.5) * 20;
      const e = 1e-5;
      const a = blendAt(u, v, picture, 0.5);
      worstJump = Math.max(worstJump,
        Math.abs(a - blendAt(u + e, v, picture, 0.5)),
        Math.abs(a - blendAt(u, v + e, picture, 0.5)));
    }
    // The picture itself moves by about 1e-4 over that step, so anything
    // of that order is the picture, not a seam.
    expect(worstJump < 5e-3, "the blend is continuous (worst " + worstJump + ")");

    // 3. THE HASH SCATTERS. Neighbouring cells have to read from
    // unrelated parts of the picture or the exercise buys nothing, and
    // no two cells in a floor-sized patch may land in the same place.
    const seen = new Set();
    let collisions = 0, nearest = 9;
    for (let i = -40; i <= 40; i++) {
      for (let j = -40; j <= 40; j++) {
        const o = tileOffset(i, j);
        expect(o[0] >= 0 && o[0] < 1 && o[1] >= 0 && o[1] < 1,
          "an offset is a fraction of one repeat");
        const key = o[0].toFixed(4) + "," + o[1].toFixed(4);
        if (seen.has(key)) collisions += 1;
        seen.add(key);
        for (const [di, dj] of [[1, 0], [0, 1], [1, 1], [1, -1]]) {
          const p = tileOffset(i + di, j + dj);
          nearest = Math.min(nearest, Math.hypot(o[0] - p[0], o[1] - p[1]));
        }
      }
    }
    expect(collisions === 0, "6561 cells, no two reading the same place "
      + "(" + collisions + " collisions)");
    expect(nearest > 0.002, "no two neighbouring cells read from within a "
      + "five hundredth of a repeat of one another (nearest " + nearest + ")");

    // 4. DETERMINISTIC, and the seed actually changes the arrangement --
    // which is what Randomise is for.
    const twice = [tileOffset(3, 7), tileOffset(3, 7)];
    expect(twice[0][0] === twice[1][0] && twice[0][1] === twice[1][1],
      "the same cell always reads from the same place");
    const seeded = tileOffset(3, 7, 11.5, 4.25);
    expect(Math.hypot(twice[0][0] - seeded[0], twice[0][1] - seeded[1]) > 0.01,
      "a fresh seed is a fresh arrangement");

    // 5. SHARPENING leaves the ends alone: a point standing on a lattice
    // vertex still shows that vertex and nothing else.
    const corner = sharpenWeights([1, 0, 0]);
    expect(Math.abs(corner[0] - 1) < 1e-12, "a vertex shows itself alone");
    const even = sharpenWeights([0.5, 0.5, 0]);
    expect(Math.abs(even[0] - 0.5) < 1e-12, "an even edge stays even");
    const near = sharpenWeights([0.7, 0.2, 0.1]);
    expect(near[0] > 0.7 && near[0] < 0.99,
      "sharpening favours the nearest vertex without becoming a hard cut, "
      + "which would put a ribbon along every lattice edge (got " + near[0] + ")");

    // 6. THE CONTRAST SURVIVES. Three pictures averaged together have
    // less variance than one, and that softening is the standard
    // complaint about this technique. Blending each tap's distance from
    // the MEAN and dividing by the weight vector's length restores it.
    function spreadOf(f) {
      let n = 0, sum = 0, sumSq = 0;
      for (let i = 0; i < 30000; i++) {
        const u = (Math.random() - 0.5) * 30, v = (Math.random() - 0.5) * 30;
        const x = f(u, v);
        n += 1; sum += x; sumSq += x * x;
      }
      return Math.sqrt(sumSq / n - (sum / n) ** 2);
    }
    const plain = spreadOf(picture);
    const kept = spreadOf((u, v) => blendAt(u, v, picture, 0.5));
    const averaged = spreadOf((u, v) => {
      const { cells, weights } = hexWeights(u, v);
      const w = sharpenWeights(weights);
      let t = 0;
      for (let i = 0; i < 3; i++) {
        const [du, dv] = tileOffset(cells[i][0], cells[i][1]);
        t += w[i] * picture(u + du, v + dv);
      }
      return t;
    });
    expect(kept / plain > 0.9, "the blend keeps the picture's contrast "
      + "(kept " + (kept / plain) + ")");
    expect(kept > averaged, "and keeps more of it than a plain average "
      + "does (" + kept + " against " + averaged + ")");

    console.log("ok " + JSON.stringify({
      contrastKept: +(kept / plain).toFixed(3),
      contrastAveraged: +(averaged / plain).toFixed(3),
      nearestNeighbour: +nearest.toFixed(4) }));
""")


@needs_node
def test_the_lattice_is_sound_and_the_blend_keeps_the_contrast(tmp_path):
    """The arithmetic under the floor, run by node.

    Two of these were live faults caught here before the shader was ever
    compiled. The sine-and-fract hash every shader reaches for first put
    adjacent cells within a hundredth of a repeat of one another, leaving
    the repetition visible in patches; and a first attempt at sharpening
    turned weights of 0.70/0.20/0.10 into 0.998/0.002/0.000, which is a
    hard cut wearing a blend's clothes and would have drawn a ribbon
    along every lattice edge.
    """

    out = _run_node(tmp_path, LATTICE_CHECK)
    assert out.startswith("ok"), out
    # The numbers the docstring above is quoting, so a change that makes
    # them worse has to come and edit this line.
    measured = json.loads(out[3:])
    assert measured["contrastKept"] >= 0.95
    assert measured["contrastAveraged"] < measured["contrastKept"]


def test_the_shader_is_the_twin_of_the_tested_arithmetic():
    """The GLSL cannot be run here, so it is held against the JS that can
    be. Every constant and every branch has to be the same, or the tests
    above are testing something the floor does not do."""

    js = TILING.read_text(encoding="utf-8")
    glsl = js[js.index("export const TILING_GLSL"):js.index("export const TILED_CHUNKS")]

    # The same skew, to the digit.
    for number in ("0.5773502691896258", "1.1547005383792517"):
        assert js.count(number) >= 2, (
            "{} appears in the JS lattice and in the GLSL".format(number))

    # The same two branches, chosen the same way, with the same weights.
    assert "if ( f.x + f.y < 1.0 ) {" in glsl
    assert "w = vec3( 1.0 - f.x - f.y, f.y, f.x );" in glsl
    assert "w = vec3( f.x + f.y - 1.0, 1.0 - f.y, 1.0 - f.x );" in glsl
    lower = _body(js, "export function hexWeights(u, v)")
    assert "weights: [1.0 - fu - fv, fv, fu]" in lower
    assert "weights: [fu + fv - 1.0, 1.0 - fv, 1.0 - fu]" in lower

    # The same hash. Not the sine one: a GPU computes in 32 bit floats,
    # and sin() of a large argument there has lost most of its meaning.
    assert "sin(" not in glsl, "the sine hash is degenerate in 32 bit floats"
    for number in ("0.1031", "0.1030", "0.0973", "33.33"):
        assert number in glsl and number in js[:js.index("export const TILING_GLSL")], (
            "{} is in both halves of the hash".format(number))

    # The same blend: distance from the mean, divided by the weight
    # vector's LENGTH. Divided by its total instead, the variance is not
    # restored and the floor goes soft.
    assert "inversesqrt( max( dot( w, w ), 1e-6 ) )" in glsl
    blend = _body(js, "export function blendAt(u, v, sample, mean")
    assert "Math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])" in blend
    assert "sum / Math.max(length, 1e-6)" in blend

    # THE MEAN IS THE SMALLEST MIP. Sampling past the last level clamps
    # to it, and that one texel is the average of the whole picture.
    assert "texture2DLodEXT( picture, vec2( 0.5 ), 20.0 )" in glsl

    # THE GRADIENTS ARE THE SMOOTH COORDINATE'S. The sampled coordinate
    # jumps by a whole random offset at every triangle edge, so left to
    # itself the hardware would see an enormous rate of change there and
    # drop to the blurriest mip in a line along every edge.
    assert glsl.count("texture2DGradEXT( picture,") == 3
    assert "vec2 dx = dFdx( uv );" in glsl and "vec2 dy = dFdy( uv );" in glsl
    assert "texture2D( picture, uv" not in glsl, (
        "a plain sample would choose its own mip from the jumping "
        "coordinate")


def test_the_floor_reads_every_map_through_the_lattice():
    """One map rewritten and the others left alone would be worse than
    none: the colour would stop repeating while the roughness and the
    relief went on repeating in rows, and the grid would still be
    there in the light."""

    js = TILING.read_text(encoding="utf-8")
    table = js[js.index("export const TILED_CHUNKS"):js.index("export function applyTiling")]
    for chunk in ("map_fragment", "roughnessmap_fragment", "metalnessmap_fragment",
                  "aomap_fragment", "normal_fragment_maps"):
        assert chunk in table, chunk
    # bumpMap is deliberately absent, and the reason is written down.
    assert "bumpmap" not in table.lower().replace("bumpmap is deliberately", "")
    assert "dHdxy_fwd" in js, "why the height map is left alone is stated"

    # THE INCLUDES ARE UNRESOLVED at onBeforeCompile: three expands them
    # afterwards, so the chunk text is not in the string yet and editing
    # it in place would silently do nothing at all.
    apply = _body(js, "export function applyTiling(shader, chunks, uniforms)")
    assert 'const include = "#include <" + name + ">";' in apply
    assert "shader.fragmentShader.replace(\n      include, source.split(from).join(to))" in apply
    assert "source.split(from).join(to)" in apply, (
        "normal_fragment_maps samples the map twice, once per branch, and "
        "replace would take only the first")
    assert "return rewritten;" in apply, (
        "the count is how a caller notices three moving a chunk out from "
        "under this, rather than quietly going back to a repeating floor")


def test_randomise_now_randomises_every_tile():
    """Param: "at the moment randomise uv just rotates all uv to a random
    orientation. but what it should mean is every instance randomises".

    The button kept its old job -- turning and sliding the whole sheet --
    and gained the one he asked for. Measured on the rendered floor: the
    picture's correlation with itself one tile along was 0.82, and is
    -0.03 with this on."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    button = js[js.index('document.getElementById("ground-randomise")'):]
    button = button[:button.index("\n});")]
    assert "state.ground.seed = [Math.random() * 64, Math.random() * 64];" in button, (
        "a fresh arrangement, not merely a fresh lay angle")
    assert "setGroundBreakup(true);" in button, (
        "the button turns it on, because that is what he asked the "
        "button to mean")
    assert "state.ground.rotation = Math.random() * Math.PI * 2;" in button, (
        "and it still re-lays the sheet, which was never wrong, only "
        "insufficient")

    # A WAY BACK. A floor whose pattern is meant to read as a regular
    # grid wants this off, and a button with no opposite is a trap.
    assert 'id="ground-breakup"' in html
    box = html[html.index('<label title="Read every tile'):]
    box = box[:box.index("</label>")]
    assert 'id="ground-breakup" type="checkbox"' in box
    assert "regular grid" in box, "the caveat is on the control itself"

    setter = _body(js, "function setGroundBreakup(on)")
    assert "material.needsUpdate = true;" in setter, (
        "it is a different shader, so the old program has to go")
    assert 'document.getElementById("ground-breakup")' in setter, (
        "the checkbox follows the state, so a restored scene and the "
        "button both move it")

    # THE CACHE KEY. Without it three hands back the program it built the
    # first time and the toggle does nothing whatever.
    install = _body(js, "function installGroundTiling(material)")
    assert "material.customProgramCacheKey = () => (state.ground.breakup" in js
    assert "atmosphere.inject(shader);" in install, (
        "this hook shadows the prototype's, so the floor would be the one "
        "surface in the scene with no height fog on it")
    assert install.index("atmosphere.inject(shader);") < install.index(
        "if (!state.ground.breakup) return;"), (
        "the fog's uniforms go on whether the lattice does or not")

    # A scene carries both, or reopening one shows a different floor.
    assert "breakup: state.ground.breakup, seed: state.ground.seed.slice() }" in js
    assert "setGroundBreakup(!!scene_.ground.breakup);" in js
    assert "if (Array.isArray(scene_.ground.seed))" in js
