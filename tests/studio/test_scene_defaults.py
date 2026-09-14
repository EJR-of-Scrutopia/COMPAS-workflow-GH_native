"""What a scene is when it does not say (bench/studio/static/scene_defaults.js).

Param, 2026-09-14: "when i save a scene it saves all these settings? make
sure that if the other ones dont have all these updates on them that we
save a set of defaults always so things dont break."

applyScene used to write a setting only when the scene carried it, so a
scene from before a setting existed came back in the previous picture's
value. Every scene is now completed against one set of defaults before it
is read. The completion runs under node here; the census holds the saver,
the defaults and the reader to one another.
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
DEFAULTS = STATIC / "scene_defaults.js"
STUDIO_JS = STATIC / "studio.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _body(js, signature):
    start = js.index(signature)
    return js[start:js.index("\n}", start)]


COMPLETE_CHECK = textwrap.dedent("""
    import { completeScene, SCENE_DEFAULTS, SCENE_LEFT_AS_THEY_ARE, SCENE_VERSION } from %DEFAULTS%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

    // NOTHING AT ALL is the defaults, whole.
    for (const nothing of [undefined, null, {}, "junk", 7, []]) {
      const scene = completeScene(nothing);
      for (const [key, value] of Object.entries(SCENE_DEFAULTS)) {
        expect(same(scene[key], value), "an empty scene has the default " + key);
      }
    }

    // A SCENE FROM BEFORE: what it carries stays, what it lacks is filled.
    const old = completeScene({
      camera: { position: [1, 2, 3], target: [0, 0, 0], fov: 40 },
      brightness: 1.4,
      ground: { preset: "brick/paver", radius: 24 },
      lamp: { lumens: 900, spot: { aperture: 20 } },
      hdri: { name: "meadow.hdr", scale: 90 },
      sun: { azimuth: 200 },
    });
    expect(old.brightness === 1.4, "a saved value is kept");
    expect(old.skyBrightness === 1 && old.relief === 1, "a setting it never had is the default");
    expect(old.ground.preset === "brick/paver" && old.ground.radius === 24, "a group keeps what it carries");
    expect(old.ground.breakup === false && same(old.ground.seed, [0, 0]), "and fills what it lacks");
    expect(old.lamp.lumens === 900 && old.lamp.kelvin === 3000, "the lamp too");
    expect(old.lamp.spot.aperture === 20 && old.lamp.spot.shadow === true, "and one level deeper");
    expect(old.hdri.name === "meadow.hdr", "what the defaults do not name is kept");
    expect(old.hdri.projection === "projected" && old.hdri.scale === 90, "beside what they fill");
    expect(same(old.section, SCENE_DEFAULTS.section), "no section is the section off");
    // Left as the scene has it, whether it has it or not.
    expect(same(old.camera, { position: [1, 2, 3], target: [0, 0, 0], fov: 40 }), "the camera is its own");
    expect(same(old.sun, { azimuth: 200 }), "the sun is not filled");
    expect(completeScene({}).camera === undefined && completeScene({}).props === undefined,
      "an absent camera or props stay absent: the scene has nothing to say about them");

    // THE WRONG KIND OF THING is as good as missing.
    const odd = completeScene({ brightness: "1.4", ground: { seed: [1], offset: [0, "x"] },
      section: "off", cameraView: "top" });
    expect(odd.brightness === 1, "a number saved as a string is the default");
    expect(same(odd.ground.seed, [0, 0]) && same(odd.ground.offset, [0, 0]), "a malformed pair is the default");
    expect(same(odd.section, SCENE_DEFAULTS.section), "a group saved as something else is the default");
    expect(odd.cameraView === "top", "a default of nothing takes whatever the scene says");

    // A COPY: completing never hands out the defaults' own objects.
    const a = completeScene({});
    a.ground.seed[0] = 99; a.lamp.spot.aperture = 1;
    const b = completeScene({});
    expect(b.ground.seed[0] === 0 && b.lamp.spot.aperture === 45, "the defaults cannot be written through");
    expect(SCENE_DEFAULTS.ground.seed[0] === 0, "and are untouched");

    // The two lists do not overlap.
    for (const key of SCENE_LEFT_AS_THEY_ARE) {
      expect(!(key in SCENE_DEFAULTS), key + " is either defaulted or left, not both");
    }
    expect(SCENE_VERSION >= 2, "scenes carry a version");
    console.log(JSON.stringify({ defaults: Object.keys(SCENE_DEFAULTS), left: SCENE_LEFT_AS_THEY_ARE }));
""")


def _run(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = tmp_path / "check.mjs"
    script.write_text(COMPLETE_CHECK.replace("%DEFAULTS%", json.dumps(DEFAULTS.as_uri())),
                      encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout.strip().splitlines()[-1])


@needs_node
def test_a_scene_is_completed_against_the_defaults(tmp_path):
    _run(tmp_path)


@needs_node
def test_every_setting_the_saver_writes_is_defaulted_or_deliberately_left(tmp_path):
    """The census. A setting added to collectScene without a default (or a
    reason to have none) is exactly how the last picture's value leaks into
    the next scene, so the two lists must account for every key it writes,
    and every default must be something the saver actually writes."""

    lists = _run(tmp_path)
    js = STUDIO_JS.read_text(encoding="utf-8")
    body = _body(js, "function collectScene(options)")
    body = body[body.index("  return {"):]
    written = set(re.findall(r"^    ([A-Za-z]+):", body, re.M))
    # Written for the reader's sake, not a setting: the layout's own props
    # travel as rows beside their layers.
    written.discard("sceneVersion")
    accounted = set(lists["defaults"]) | set(lists["left"])
    assert written - accounted == set(), (
        "written but neither defaulted nor left: {}".format(sorted(written - accounted)))
    assert set(lists["defaults"]) - written == set(), (
        "defaulted but never written: {}".format(sorted(set(lists["defaults"]) - written)))


def test_the_reader_completes_first_and_restores_what_was_never_saved():
    js = STUDIO_JS.read_text(encoding="utf-8")
    apply_ = _body(js, "async function applyScene(record)")
    assert apply_.index("const scene_ = completeScene(record.state);") < apply_.index("scene_.cut"), (
        "completed before a single setting is read")
    save = _body(js, "function collectScene(options)")
    for field in ("sceneVersion: SCENE_VERSION,", "skyBrightness: state.skyBrightness,",
                  "relief: state.relief,", "occlusion: state.occlusion,",
                  "showMachine: state.showMachine !== false,"):
        assert field in save, field
    for restore in ("state.skyBrightness = scene_.skyBrightness;",
                    "state.relief = scene_.relief;", "state.occlusion = scene_.occlusion;",
                    "applySurfaceControls();", "state.showMachine = scene_.showMachine;",
                    "state.dayCycle.seconds = scene_.dayCycle.seconds;",
                    "state.dayCycle.record = scene_.dayCycle.record;"):
        assert restore in apply_, restore
    # The sky brightness is applied by the sun's own step, after it is set.
    assert apply_.index("state.skyBrightness = scene_.skyBrightness;") < apply_.index("applySkyBrightness();")
