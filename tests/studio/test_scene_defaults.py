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


# ---------- a new scene ----------
# Param, 2026-09-15: "can we add a new scene button to scene tile, where it
# just gives us a blank scene to start from, not deleting any other saved
# scenes". The blank goes through the same completion as every scene, so
# the tests below hold it to the defaults above, run the real startNewScene
# against stubs to prove its order, and pin the button.

def _new_scene_source(js):
    start = js.index("function blankScene()")
    end = js.index("async function startNewScene()", start)
    end = js.index(chr(10) + "}" + chr(10), end) + 2
    return js[start:end]


BLANK_CHECK = textwrap.dedent("""
    import { completeScene, SCENE_DEFAULTS, SCENE_LEFT_AS_THEY_ARE } from %DEFAULTS%;
    const blankScene = new Function(%SOURCE% + "; return blankScene;")();
    const blank = completeScene(blankScene());
    const out = { mismatched: [], kept: [], props: blank.props, propLayers: blank.propLayers };
    for (const [key, value] of Object.entries(SCENE_DEFAULTS)) {
      if (JSON.stringify(blank[key]) !== JSON.stringify(value)) out.mismatched.push(key);
    }
    for (const key of SCENE_LEFT_AS_THEY_ARE) {
      if (key !== "props" && key !== "propLayers" && blank[key] !== undefined) out.kept.push(key);
    }
    console.log(JSON.stringify(out));
""")


@needs_node
def test_a_new_scene_is_the_defaults_around_the_same_vault(tmp_path):
    """Every default setting, nothing placed, and nothing said about what a
    scene may leave as it is (the vault's cut and skin, the camera, the
    sun), so those stay as they are on screen."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    script = tmp_path / "blank.mjs"
    script.write_text(BLANK_CHECK.replace("%DEFAULTS%", json.dumps(DEFAULTS.as_uri()))
                      .replace("%SOURCE%", json.dumps(_new_scene_source(js))), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["mismatched"] == [], "every setting is the studio's default"
    assert out["props"] == [] and out["propLayers"] == [], "nothing placed, one fresh layer"
    assert out["kept"] == [], "the camera, the sun and the vault are left as they are"


ORDER_CHECK = textwrap.dedent("""
    const calls = [];
    let pushed = null;
    let applyResult = true;
    let release = null;
    let holdApply = false;
    const state = { bundle: null };
    const document = { getElementById(id) {
      return id === "study-select" ? { value: "Trial 2" } : null; } };
    const stubs = {
      showBanner: (message) => calls.push("banner"),
      collectScene: () => { calls.push("collect"); return { marker: "before" }; },
      applyScene: async (record) => {
        calls.push("apply " + (record.state.marker || JSON.stringify(record.state)) + " " + record.study);
        if (holdApply) await new Promise((resolve) => { release = resolve; });
        return applyResult;
      },
      saveProps: () => calls.push("save"),
      refreshLayersShelf: () => calls.push("layers"),
      pushUndo: (label, undo, redo) => { calls.push("undo " + label); pushed = { undo, redo }; },
      logStudio: () => calls.push("log"),
      fetch: () => calls.push("FETCH"),
    };
    const made = new Function(...Object.keys(stubs), "state", "document",
      %SOURCE% + "; return { startNewScene, blankScene };")(...Object.values(stubs), state, document);
    const report = {};

    report.noStudy = [await made.startNewScene(), calls.splice(0)];

    state.bundle = {};
    report.started = [await made.startNewScene(), calls.splice(0)];

    await pushed.undo();
    report.undone = calls.splice(0);
    report.redoIsTheSame = pushed.redo === made.startNewScene;

    applyResult = false;
    pushed = null;
    report.refused = [await made.startNewScene(), calls.splice(0), pushed === null];
    applyResult = true;

    holdApply = true;
    const first = made.startNewScene();
    const second = await made.startNewScene();
    release();
    report.twice = [await first, second, calls.filter((c) => c.startsWith("apply")).length];
    console.log(JSON.stringify(report));
""")


@needs_node
def test_a_new_scene_restores_the_blank_then_offers_the_old_one_back(tmp_path):
    """Run, not read. The picture on screen is taken BEFORE the blank goes
    on, the empty layout is written only once the blank is on, and the undo
    entry is pushed after the apply because loadStudy clears the history on
    its way in. Nothing it does reaches the network, so no saved scene can
    be touched."""

    js = STUDIO_JS.read_text(encoding="utf-8")
    source = _new_scene_source(js)
    assert "fetch(" not in source and "/api/scenes" not in source
    script = tmp_path / "order.mjs"
    script.write_text(ORDER_CHECK.replace("%SOURCE%", json.dumps(source)), encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout.strip().splitlines()[-1])

    assert report["noStudy"] == [False, ["banner"]], "no study, nothing to start around"
    blank = 'apply {"props":[],"propLayers":[]} Trial 2'
    assert report["started"] == [True, ["collect", blank, "save", "layers", "undo new scene", "log"]]
    assert report["undone"] == ["apply before Trial 2", "save", "layers"], (
        "Ctrl+Z puts back the picture taken before, and its layout")
    assert report["redoIsTheSame"] is True
    assert report["refused"] == [False, ["collect", blank], True], (
        "a blank that did not go on writes no layout and offers no undo")
    assert report["twice"] == [True, False, 1], "a second press while the first rebuilds is ignored"


def test_the_new_scene_button_sits_beside_save_in_the_scenes_drawer():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    actions = page[page.index('<div id="shelf-actions">'):]
    actions = actions[:actions.index('<button id="shelf-close"')]
    tag = actions[actions.index('<button id="scene-new"'):]
    tag = tag[:tag.index(">")]
    assert 'class="hidden"' in tag, "shown only in the Scenes drawer"
    assert "No saved scene is touched" in tag and "Ctrl+Z" in tag, "the title says both"
    assert actions.index('id="scene-new"') < actions.index('id="scene-save"')
    assert page.count('id="scene-new"') == 1
    js = STUDIO_JS.read_text(encoding="utf-8")
    shelf = _body(js, "function renderShelf()")
    assert ('document.getElementById("scene-new").classList' + chr(10)
            + '    .toggle("hidden", shelfKind !== "scenes");') in shelf
    assert 'document.getElementById("scene-new").addEventListener("click", startNewScene);' in js
