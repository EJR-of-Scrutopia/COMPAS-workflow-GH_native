// ---------- what a scene is, when it does not say ----------
// Param, 2026-09-14: "when i save a scene it saves all these settings? make
// sure that if the other ones dont have all these updates on them that we
// save a set of defaults always so things dont break."
//
// A scene is written by collectScene and read back by applyScene, and the
// reader used to write a setting only when the scene carried it. So a scene
// saved before a setting existed -- or saved by a build that did not know it
// -- came back wearing whatever the LAST picture on screen had: the last
// scene's sky brightness, its ground scale, its section, its fixtures. What
// a scene restores depended on what had been shown before it.
//
// Now every scene is completed against one set of defaults before it is
// read, group by group, so a missing setting is the studio's own default and
// never the previous picture's. The defaults are the values the studio
// starts with.
//
// SOME THINGS A SCENE MAY LEAVE UNSAID ON PURPOSE, and these are not given
// defaults (SCENE_LEFT_AS_THEY_ARE): where the camera stands and what the
// props are belong to a scene that carries them, a site and a sun whose
// absence means "keep the angles this scene was framed under", the cut and
// the skin that the study itself remembers, the timeline's instant, and the
// atmosphere and wind, whose own adopters (adoptAtmosphere, adoptWind) are
// the single place their defaults live.
//
// It imports nothing, so node tests it in tests/studio/test_scene_defaults.py.

// Written into every scene from this build on, so a later reader can tell
// what it is looking at.
export const SCENE_VERSION = 2;

export const SCENE_DEFAULTS = {
  showMode: "both",
  environmentMode: "studio",
  weatherPreset: "clear",
  backgroundTone: 85,
  brightness: 1,
  contrast: 0,
  outline: 0,
  skyBrightness: 1,
  relief: 1,
  occlusion: 1,
  showMachine: true,
  projection: "perspective",
  cameraView: null,
  layers: { overlays: true },
  lamp: {
    lumens: 4000, kelvin: 3000, tint: "#ffffff", invisible: false,
    spot: { aperture: 45, softness: 0.35, reach: 0, shadow: true },
  },
  hdri: { projection: "projected", scale: 60, height: 2, rotation: 0 },
  section: { mode: "off", axis: "y", offset: 0, cutMachine: false },
  ground: {
    preset: "dark-studio", radius: 60, scaleX: 1, scaleY: 1, relief: 1,
    offset: [0, 0], rotation: 0, breakup: false, seed: [0, 0],
  },
  dayCycle: { seconds: 30, peakElevation: 40, record: false },
};

export const SCENE_LEFT_AS_THEY_ARE = [
  "camera", "props", "propLayers", "site", "sun", "cut", "appearance",
  "timeline", "atmosphere", "wind", "orthoHeight", "orthoZoom",
];

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function copy(value) {
  if (Array.isArray(value)) return value.map(copy);
  if (isPlainObject(value)) {
    const out = {};
    for (const [key, inner] of Object.entries(value)) out[key] = copy(inner);
    return out;
  }
  return value;
}

// The saved value where it is the same KIND of thing as the default, and the
// default where it is missing or is not: a number saved as a string by some
// older writer, or an object where a number belongs, is as good as missing.
function complete(defaults, saved) {
  if (isPlainObject(defaults)) {
    const out = isPlainObject(saved) ? copy(saved) : {};
    for (const [key, fallback] of Object.entries(defaults)) {
      out[key] = complete(fallback, isPlainObject(saved) ? saved[key] : undefined);
    }
    return out;
  }
  if (saved === undefined) return copy(defaults);
  if (defaults === null) return saved;
  if (Array.isArray(defaults)) {
    return Array.isArray(saved) && saved.length === defaults.length
      && saved.every((item, i) => typeof item === typeof defaults[i])
      ? saved.slice() : defaults.slice();
  }
  return typeof saved === typeof defaults ? saved : defaults;
}

// A whole scene: every default filled in, and everything the scene carries
// beyond the defaults kept as it is.
export function completeScene(saved) {
  const scene = isPlainObject(saved) ? copy(saved) : {};
  for (const [key, fallback] of Object.entries(SCENE_DEFAULTS)) {
    scene[key] = complete(fallback, scene[key]);
  }
  return scene;
}
