import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Sky } from "three/addons/objects/Sky.js";
import { GroundedSkybox } from "three/addons/objects/GroundedSkybox.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import {
  upgradeSliders, paintScrub, repaintScrubs, buildSegmented, paintSegmented,
  buildGroups, paintGroupSummaries, setGroupSummaries,
} from "/static/panel.js";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { BrightnessContrastShader } from "three/addons/shaders/BrightnessContrastShader.js";
import {
  boxUVs, segmentUVOffset, segmentWindow, sheetUVs, footprintSpan, uvQuarterTurn,
  smoothStressField, interpolateScalarField,
  sampleScalar, sampleVector, creaseNormals, estimateSunFromEquirect,
  interpolateFormworkFrame, machineTime, formworkVisibility, groundRepeat,
  sunPosition, sunLight, timeAtElevation,
} from "/static/fields.js";
import {
  loadLibraryMaterial, disposeLibraryMaterial, tileUrl, setRepeat, setSurface,
  repeatsFor, DEFAULT_TILE_METRES, VIEWPORT_PX, GROUND_BASE,
  CONSTRAINED_DEVICE,
} from "/static/pbr.js";

// ---------- diagnosis ----------
// When something goes wrong on screen it writes itself down, with enough
// context to be acted on: what the studio was showing, what it was asked to
// do, and the stack. Param asked for this after a scene restore failed with
// a message that named a symptom and nothing else. The log is a file on the
// server (bench/studio/diagnostics.log), one JSON object per line.
let reportingProblem = false;

function reportProblem(message, detail) {
  // Never report a failure of the reporting itself, and never let a report
  // throw into the code that was already failing.
  if (reportingProblem) return;
  reportingProblem = true;
  try {
    const body = {
      message: String(message || "").slice(0, 2000),
      stack: detail && detail.stack ? String(detail.stack).slice(0, 4000) : null,
      page: location.pathname + location.search,
      when: new Date().toISOString(),
      context: null,
    };
    // The context is a bonus, never the message's ransom: an error thrown
    // DURING module evaluation reaches this function before `state` exists,
    // and on the iPad that turned the one report that mattered into
    // silence. The bare message still travels when the context cannot.
    try {
      body.context = {
        study: (document.getElementById("study-select") || {}).value || null,
        showMode: state.showMode,
        source: state.source,
        material: (document.getElementById("material-select") || {}).value || null,
        pattern: state.pattern,
        size: state.size,
        thickness: state.thickness,
        environment: state.environmentMode,
        hdri: state.hdriName,
        playing: !!(state.timeline && state.timeline.playing),
        t: state.timeline ? state.timeline.t : null,
        recent: recentLog.slice(-12),
      };
    } catch (error) { /* module still assembling itself */ }
    // Which machine, in numbers: a remote report from an iPad has to say
    // so itself, and the GPU ceilings are the facts that separate "bug"
    // from "this device ran out". Its own guard, because the renderer may
    // not exist yet when the report is about the boot itself.
    try {
      body.context.device = {
        touch: navigator.maxTouchPoints,
        dpr: window.devicePixelRatio,
        maxTexture: renderer.capabilities.maxTextureSize,
        ua: navigator.userAgent.slice(0, 120),
      };
    } catch (error) { /* before the renderer exists */ }
    const wire = JSON.stringify(body);
    // sendBeacon first: it is the transport built for pages that are dying,
    // which is exactly when this report is worth the most. A tab being
    // reclaimed for memory (the iPad's way of failing) drops in-flight
    // fetch() bodies; beacons are handed to the browser process and
    // survive. fetch stays as the fallback for anything without beacons.
    let sent = false;
    try {
      sent = !!(navigator.sendBeacon && navigator.sendBeacon(
        "/api/diagnostics", new Blob([wire], { type: "application/json" })));
    } catch (error) { sent = false; }
    if (!sent) {
      fetch("/api/diagnostics", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: wire,
      }).catch(() => { /* the studio is not worth breaking over a log line */ });
    }
  } catch (error) {
    /* the same */
  } finally {
    reportingProblem = false;
  }
}

// The last few log lines travel with a report: what the user did just
// before is usually the half of the story the message leaves out.
const recentLog = [];

window.addEventListener("error", (event) => {
  reportProblem(event.message, event.error);
});
window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  reportProblem(
    reason && reason.message ? reason.message : String(reason), reason);
});

// ---------- app state ----------
const state = {
  bundle: null,
  source: null,        // deliverable B: null = whatever the study has (Skin wins), else "authored" | "generated"
  formwork: null,      // bench.frames/1 payload for this study, or null: frames, edges, columns.members (see applyFormworkAct)
  columnRadius: null,  // bench.columns/1 "radius" from the loaded study's columns file: the width the exporter swept the column solids along, and the width the act's animated members take (see columnRadius())
  propLibrary: [],     // the manifest entries that loaded, from /api/props
  propCredits: null,   // what the library as a whole is, and where it came from
  scenes: [],          // saved scenes, newest first, from /api/scenes
  live: true,          // the Live button: while on, a Grasshopper push reloads the study on screen
  lastRefusal: null,   // the server's own words for the last refused load, shown under the cut source control
  studies: [],
  layers: { overlays: true }, // shell and wires are gone: the Show select owns both (applyShowMode)
  showMode: "both",    // "framework" | "shell" | "both" chosen by the three buttons; "timeline" is what playing switches to on its own (see setShowMode)
  // Fixed 2026-09-04 (Param: "remove the formwork dropdown all together...
  // it just plays animation as it should"). Hidden is the value the control
  // had defaulted to and the one every take has been watched at: the
  // machine itself is drawn by the formwork act, and this ghost was a
  // second, translucent copy of the same surface. The rules that read it
  // are untouched, so restoring the control is a control and a handler.
  formworkMode: "hidden",
  environmentMode: "studio", // E1: "studio" | "sky" | "hdri", each owns background, environment, fog, sun
  cameraAspect: "fill",  // the Camera menu's frame: "fill" or a ratio as a string
  weatherPreset: "clear",    // E2: a key of WEATHER
  groundPreset: "dark-studio", // E4: a key of GROUNDS, independent of the environment mode
  groundRadius: 60,     // the floor disc's radius in metres, the Ground size slider (rebuildGround)
  // The floor texture's own dials: per-axis scale multipliers over the
  // real-world repeat, its own relief depth, and a slid offset from the
  // Randomise button (rebuildGround applies all four).
  ground: { scaleX: 1, scaleY: 1, relief: 1, offset: [0, 0], rotation: 0 },
  props: [],            // E5: [{ type, x, y, rotation, object }], mirrored to localStorage
  carrying: null,      // { record, from } while a prop follows the cursor (see carryNewProp)
  armedPropType: null,  // kept for the older arming path used by nothing in the panel now
  selectedProp: null,   // the record whose object is highlighted and keyboard-driven
  propEdit: false,      // the Edit button: only then do clicks grab placed props
  // Layers group placed props (Param: "control, duplicate and place
  // groups of objects"). New props land on the ACTIVE layer.
  propLayers: [{ id: 1, name: "Layer 1", visible: true }],
  activeLayer: 1,
  nextLayerId: 2,
  propDrag: false,
  hdriTexture: null,         // E3: the decoded equirect, set by loadHdri (Task 4)
  hdriName: null,
  hdriProjection: "projected", // Task 2: "projected" builds a GroundedSkybox dome; "infinite" is the flat equirect background
  hdriScale: 60,       // GroundedSkybox radius, metres
  hdriHeight: 2,        // GroundedSkybox height (camera height above ground in the source photo), metres
  hdriRotation: 0,      // degrees, spins the dome/background about the world vertical
  hdriEstimateAzimuth: null, // raw pixel-estimated azimuth from the last loadHdri; lets the rotation slider re-aim the sun without re-scanning pixels
  sunColourOverride: null,   // S5: hex string once the sun-colour input is touched; null lets a preset choose the colour again
  sunIntensityOverride: null, // F4: sun.intensity captured once a day cycle finishes; null lets a preset choose the intensity again, exactly like sunColourOverride
  // The sun is a time and a place now, not two angles. The angles are
  // derived (see applySunFromTime) and the two hidden inputs keep them for
  // the code that still speaks in angles: the HDRI estimate and the sky.
  sunDay: new Date(),          // taken once at load, so a take is not interrupted by midnight
  sunMinutes: 13 * 60,         // early afternoon, a defensible default for a first look
  sunElevationSetting: 40,   // F1: the #sun-elevation slider's own value, written only by its own input handler; the day cycle reads its peak from here, never from the slider itself (applyDayCycle also writes that slider, clamped for display -- see applyDayCycle)
  dayCycle: { playing: false, t: 0, seconds: 30, peakElevation: 40, record: false }, // S5
  brightness: 1,     // R2: multiplier on the active mode's exposure base
  contrast: 0,       // R2: BrightnessContrastShader contrast, display space
  exposureBase: 0.85, // written by applyEnvironment per mode and preset
  objects: {},         // shell, wires, nodes, falsework, columns, ground, loadArrows, reactionArrows
  timeline: null,      // Task 13
  userDragging: false, // Task 13
  recording: false,    // Task 15: true while recordAnimation() drives the render loop
  centre: null,        // Task 13: cached orbit centroid, set in rebuildTimeline
  pattern: "bonded-courses",
  size: 0.9,
  thickness: 0.2,
  // Fixed 2026-09-04 (Param): a hairline joint, not a control. The cut
  // still opens the joint at the widest corner and closes it toward the
  // centre; this is the width it opens to.
  jointGap: 0.001,
  // The crown taper control is retired with the Skin panel rework: it thins
  // pieces toward the crown in the DRAWING only, while the analysis stays
  // uniform, so the picture and the numbers disagreed. Pinned at 0 (no
  // taper) until it can drive the thickness the analysis actually uses.
  taper: 0,
  segmentIndex: null,  // Task 11
  // Fixed 2026-09-04 with the View panel: 30 mm nodes and 20 mm wires are
  // the sizes Param settled on, so they are the sizes, not a control.
  nodeRadius: 0.03,
  wireRadius: 0.02,
  // Task 9: filled from /api/studies at boot, so the pattern control knows
  // which patterns are actually selectable and what each material's own
  // default and honesty note are.
  patterns: [],
  patternDefaults: {},
  patternNotes: {},
  patternChosen: false, // an explicit pattern choice survives material changes
  loadSequence: 0,      // bundle request token: only the newest response lands
  reloadTimer: null,    // the settle timer behind size and thickness commits
  // Task 5: render-only overrides, keyed to the loaded ANALYSIS material
  // and persisted per material under "bench-studio-appearance:" + material
  // (see restoreAppearance/persistAppearance). null means no override; the
  // registry material (or a skin) shows through untouched.
  appearance: { tint: null, finish: null, skin: "none",
    variation: 1, uvSeed: 0, grain: false },
  relief: 1,             // height-map depth, where 1 is QS's own 10 mm
  occlusion: 1,          // how much of a photoscan's own crevice shading is kept
  hdriBackdrop: null,    // the sharp visible sky, separate from the one that lights
  materialLibrary: [],   // the SKIN index from /api/materials, or empty
  materialRoot: "",      // where it is being read from, for the panel
  groundLibrary: [],     // the GROUND index from /api/ground-materials
  groundRoot: "",        // its folder, for the panel
};

const canvas = document.getElementById("view");
const scrubber = document.getElementById("timeline-scrubber");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
// Full native density on the desktop; a ceiling on touch devices. An iPad
// at DPR 2 is a 3200x2400 canvas, and shading it is half of why the studio
// felt slow there; 1.5 is the standard trade and still crisp at 264 ppi.
renderer.setPixelRatio(CONSTRAINED_DEVICE
  ? Math.min(window.devicePixelRatio, 1.5) : window.devicePixelRatio);
// When iOS reclaims graphics memory it takes the context with it, and every
// symptom downstream (silver props, missing textures, a frozen viewport)
// looks like a different bug. Written down with the device's numbers, so a
// remote report says which ceiling was hit.
canvas.addEventListener("webglcontextlost", () => {
  reportProblem("WebGL context lost", null);
  logStudio("the graphics context was lost; reload the page");
});
renderer.shadowMap.enabled = true;
// PCFSoftShadowMap is deprecated in r185 and silently downgraded to this
// with a console warning: PCF was rewritten to a hardware-comparison
// five-tap Vogel disk jittered by interleaved gradient noise, so softness
// now comes from light.shadow.radius rather than from the constant.
renderer.shadowMap.type = THREE.PCFShadowMap;
// Neutral, not ACESFilmic. ACES multiplies exposure by 1/0.6 inside its own
// shader without saying so, then applies a film-print curve that lifts
// midtone saturation and hue-shifts strong colours. A studio whose job is
// to show what a material looks like cannot use an operator that lies about
// albedo. Neutral is the Khronos 3D Commerce curve: a straight pass-through
// below a peak of 0.76, rolling off only the highlights above it.
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;

// Every exposure number in this file was tuned by eye against ACES, and so
// carries ACES's hidden 1/0.6 inside it. Neutral applies no such gain, so
// the factor is put back here once rather than rewritten into a dozen
// presets whose numbers would then mean nothing to anybody reading them.
const EXPOSURE_GAIN = 1 / 0.6;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
camera.position.set(24, -24, 14);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
const propRaycaster = new THREE.Raycaster();

const pmrem = new THREE.PMREMGenerator(renderer);
const studioEnvironment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environment = studioEnvironment;
let environmentTarget = null; // the disposable PMREM target behind sky/hdri modes
let hdriDome = null; // the disposable GroundedSkybox group, hdri mode + projected only (Task 2)

// R2: render, tone-map to display space, then grade. Contrast pivots
// around mid grey, which is only meaningful AFTER tone mapping, so the
// grade pass sits last, on the OutputPass's sRGB result. samples: 4
// keeps the antialiasing the direct canvas render had.
const composerTarget = new THREE.WebGLRenderTarget(1, 1, { samples: 4, type: THREE.HalfFloatType });
const composer = new EffectComposer(renderer, composerTarget);
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new OutputPass());
const gradePass = new ShaderPass(BrightnessContrastShader);
composer.addPass(gradePass);

function applyGrade() {
  renderer.toneMappingExposure = state.exposureBase * state.brightness * EXPOSURE_GAIN;
  gradePass.uniforms.brightness.value = 0;
  gradePass.uniforms.contrast.value = state.contrast;
}

// The eye never goes below the floor (Param: "i dont want the camera to be
// able to go below floor level"). The clamp lives HERE, the one choke
// point every camera writer passes through before a pixel is drawn:
// OrbitControls with damping, the take's own autoSpin (which bypasses the
// controls entirely), a restored scene's raw position, and the recording
// loop's renderView all funnel into this call. A controls limit alone
// cannot hold, because the orbit target sits at the vault's centroid, not
// on the floor. groundLevel needs a loaded bundle for the true floor;
// before one arrives the plain z = 0 plane stands in.
function clampCameraAboveFloor() {
  const floor = state.bundle ? groundLevel() : 0;
  const eye = floor + 0.2;
  if (camera.position.z < eye) camera.position.z = eye;
}

function renderView() {
  clampCameraAboveFloor();
  composer.render();
}

const sun = new THREE.DirectionalLight(0xffffff, 3.0);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -30; sun.shadow.camera.right = 30;
sun.shadow.camera.top = 30; sun.shadow.camera.bottom = -30;
scene.add(sun);
const hemi = new THREE.HemisphereLight(0xbfd4e6, 0x30271f, 0.5);
scene.add(hemi);

// E2: one physical sky shared by backdrop and lighting. The shader's up
// vector defaults to Y-up; this scene is Z-up.
const sky = new Sky();
sky.scale.setScalar(450);
sky.visible = false;
sky.material.uniforms.up.value.set(0, 0, 1);
sky.material.uniforms.cloudCoverage.value = 0; // the cloud block is hardcoded Y-up; scattering respects up, clouds do not
scene.add(sky);

// E2: weather presets are parameter bundles on that one shader. The
// numbers are starting values tuned by eye, not physics claims; elevation
// non-null moves the slider to a fitting default when the preset lands.
const WEATHER = {
  clear: {
    turbidity: 3, rayleigh: 1.2, mieCoefficient: 0.004, mieDirectionalG: 0.8,
    sunIntensity: 3.2, sunColor: 0xfff2e0, shadowRadius: 2, exposure: 0.55,
    hemisphere: 0.35, fogColor: 0xcfd8e0, fogNear: 120, fogFar: 400, elevation: null,
  },
  hazy: {
    turbidity: 10, rayleigh: 2.2, mieCoefficient: 0.02, mieDirectionalG: 0.75,
    sunIntensity: 2.2, sunColor: 0xffe8c8, shadowRadius: 6, exposure: 0.55,
    hemisphere: 0.45, fogColor: 0xd8d4c8, fogNear: 60, fogFar: 240, elevation: null,
  },
  overcast: {
    turbidity: 20, rayleigh: 3.5, mieCoefficient: 0.06, mieDirectionalG: 0.6,
    sunIntensity: 0.9, sunColor: 0xe8ecf0, shadowRadius: 12, exposure: 0.5,
    hemisphere: 0.7, fogColor: 0xc4c8cc, fogNear: 50, fogFar: 200, elevation: null,
  },
  "golden-hour": {
    turbidity: 6, rayleigh: 2.8, mieCoefficient: 0.012, mieDirectionalG: 0.85,
    sunIntensity: 2.6, sunColor: 0xffb36b, shadowRadius: 3, exposure: 0.7,
    hemisphere: 0.3, fogColor: 0xe0c0a0, fogNear: 80, fogFar: 300, elevation: 12,
  },
  night: {
    turbidity: 2, rayleigh: 0.4, mieCoefficient: 0.002, mieDirectionalG: 0.7,
    sunIntensity: 0.25, sunColor: 0xbcd0ff, shadowRadius: 4, exposure: 0.45,
    hemisphere: 0.15, fogColor: 0x10141c, fogNear: 60, fogFar: 250, elevation: 20,
  },
};

// F1: the shared position math, callable with an unclamped elevation so
// applyDayCycle can render a genuine sub-5-degree dawn (and a captured low
// peak) even though the slider it also writes for display cannot show a
// value under its own min="5" -- see applyDayCycle.
function applySunAt(azimuthDeg, elevationDeg) {
  const az = THREE.MathUtils.degToRad(azimuthDeg);
  const el = THREE.MathUtils.degToRad(elevationDeg);
  const r = 60;
  sun.position.set(r * Math.cos(el) * Math.cos(az), r * Math.cos(el) * Math.sin(az), r * Math.sin(el));
  sky.material.uniforms.sunPosition.value.copy(sun.position).normalize();
}

// Kept for the day cycle and the HDRI estimate, both of which speak in
// angles rather than in times.
function applySunFromSliders() {
  applySunAt(+document.getElementById("sun-azimuth").value, +document.getElementById("sun-elevation").value);
}

// S5: the day as a pure function of u in [0,1]. Azimuth sweeps west to
// east through south; elevation is a sine arc to the peak captured at
// start; colour and intensity ramp warm-dim, white-bright, warm-dim.
// Writes the sliders and the colour input so the UI tells the truth.
function applyDayCycle(u) {
  // The day cycle is the clock running, not an arc somebody drew. u sweeps
  // the hours from dawn to dusk on the real day at the real site, and the
  // solar model places, colours and dims the sun exactly as it does for a
  // time chosen by hand: the same code path, so the cycle cannot look
  // different from the still it passes through.
  //
  // This replaces a synthesised azimuth sweep and a sine elevation whose
  // peak came from a slider. The peak now comes from the date and the
  // latitude, which is where a peak comes from.
  const from = dayCycleStart();
  const to = dayCycleEnd();
  state.sunMinutes = from + (to - from) * Math.max(0, Math.min(1, u));
  applySunFromTime();
}

function dayCycleStart() {
  const dawn = timeAtElevation(sunDay(), SUN_SITE.latitude, SUN_SITE.longitude, -6, false);
  return dawn ? dawn.getUTCHours() * 60 + dawn.getUTCMinutes() : 5 * 60;
}

function dayCycleEnd() {
  const dusk = timeAtElevation(sunDay(), SUN_SITE.latitude, SUN_SITE.longitude, -6, true);
  return dusk ? dusk.getUTCHours() * 60 + dusk.getUTCMinutes() : 21 * 60;
}

function setEnvironmentTexture(texture, target) {
  // The studio texture is permanent; sky and hdri targets are disposable,
  // and leaking one per regeneration is a GPU leak the browser never
  // reports. Dispose the old target before adopting the new one.
  if (environmentTarget) environmentTarget.dispose();
  environmentTarget = target || null;
  scene.environment = texture;
}

function applyEnvironment() {
  // The cheap pass: lights, backdrop ownership, fog, row visibility.
  // PMREM lives in regenerateEnvironment only (E6).
  applySunFromSliders();
  document.getElementById("background-row").classList.toggle("hidden", state.environmentMode !== "studio");
  // The picker too, not only its grid: outside Sky mode the weather picker
  // did nothing but could still be opened, and the next pass through here
  // slammed the grid shut on whoever had just opened it. A mode-dependent
  // control shows only in its mode, exactly as the HDRI block already does.
  // (#weather-row, the legacy select, stays hidden for good: it is the
  // state holder behind the picker, not a control.)
  document.getElementById("weather-picker").classList.toggle("hidden", state.environmentMode !== "sky");
  // Hide-only for the grid: forcing it OPEN in sky mode fought the picker,
  // which owns opening -- every pass through here reopened a grid the user
  // had just closed. Leaving sky mode shuts it and resets the chevron.
  if (state.environmentMode !== "sky") {
    document.getElementById("weather-tiles").classList.add("hidden");
    document.getElementById("weather-picker").classList.remove("open");
  }
  document.getElementById("hdri-row").classList.toggle("hidden", state.environmentMode !== "hdri");
  if (state.environmentMode !== "hdri") disposeHdriDome();
  if (state.environmentMode === "sky") {
    const preset = WEATHER[state.weatherPreset];
    const uniforms = sky.material.uniforms;
    uniforms.turbidity.value = preset.turbidity;
    uniforms.rayleigh.value = preset.rayleigh;
    uniforms.mieCoefficient.value = preset.mieCoefficient;
    uniforms.mieDirectionalG.value = preset.mieDirectionalG;
    sky.visible = true;
    scene.background = null;
    scene.fog = new THREE.Fog(preset.fogColor, preset.fogNear, preset.fogFar);
    scene.backgroundRotation.set(0, 0, 0);
    scene.environmentRotation.set(0, 0, 0);
    // F4: a day cycle's captured intensity survives an environment redraw
    // the same way its captured colour already does, below.
    if (state.sunIntensityOverride === null) sun.intensity = preset.sunIntensity;
    // F3: the colour input must show the truth. A preset write bypasses the
    // input's own "input" handler (the only other place that sets
    // sun.color), so it has to sync #sun-colour itself or the swatch keeps
    // showing whatever an earlier override or preset left behind.
    if (state.sunColourOverride === null) {
      sun.color.set(preset.sunColor);
      document.getElementById("sun-colour").value = "#" + sun.color.getHexString();
    }
    sun.shadow.radius = preset.shadowRadius;
    hemi.intensity = preset.hemisphere;
    state.exposureBase = preset.exposure;
    scene.environmentIntensity = 0.6;
  } else if (state.environmentMode === "hdri") {
    sky.visible = false;
    scene.fog = null;
    applyHdriBackdrop();
    hemi.intensity = 0.25;
    state.exposureBase = 0.7;
    scene.environmentIntensity = 1.0;
  } else {
    sky.visible = false;
    scene.fog = null;
    const tone = +document.getElementById("background-tone").value / 100;
    scene.background = new THREE.Color().setHSL(0.6, 0.08, 0.06 + 0.5 * tone);
    scene.backgroundRotation.set(0, 0, 0);
    scene.environmentRotation.set(0, 0, 0);
    if (state.sunIntensityOverride === null) sun.intensity = 3.0;
    if (state.sunColourOverride === null) {
      sun.color.set(0xffffff);
      document.getElementById("sun-colour").value = "#" + sun.color.getHexString();
    }
    sun.shadow.radius = 1;
    hemi.intensity = 0.5;
    // Light concretes were clipping to white under the room environment plus
    // filmic tone mapping, which made three different presets look identical.
    state.exposureBase = 0.85;
    scene.environmentIntensity = 0.6;
  }
  applyGrade();
  // The environment's presets write the sun's colour and intensity as a
  // last resort, from a time when nothing else knew what colour a sun
  // should be. Something does now, and it is the instrument: whichever
  // preset has just been applied, the derived sun goes back on top of it,
  // or a mode change would silently flatten an evening back to white noon.
  if (sunInstrumentReady) applySunFromTime();
}

// False until the instrument has been placed once, so applyEnvironment can
// run during boot before the sun has a time to be at.
let sunInstrumentReady = false;

function regenerateEnvironment() {
  // The one PMREM site (E6): mode entry, weather change, sun slider
  // release in sky mode, and HDRI load all land here.
  if (state.environmentMode === "sky") {
    const holder = new THREE.Scene();
    holder.add(sky); // borrows the mesh; a mesh lives in one scene at a time
    const target = pmrem.fromScene(holder, 0.04);
    scene.add(sky);
    setEnvironmentTexture(target.texture, target);
  } else if (state.environmentMode === "hdri" && state.hdriTexture) {
    const target = pmrem.fromEquirectangular(state.hdriTexture);
    setEnvironmentTexture(target.texture, target);
  } else {
    setEnvironmentTexture(studioEnvironment, null);
  }
}

function disposeHdriDome() {
  // hdriDome is a Group (the Z-up quarter turn) wrapping the one
  // GroundedSkybox mesh (the Y-up dome); the mesh owns the disposable
  // geometry and material.
  if (!hdriDome) return;
  scene.remove(hdriDome);
  const dome = hdriDome.children[0];
  dome.geometry.dispose();
  dome.material.dispose();
  hdriDome = null;
}

function applyHdriBackdrop() {
  // Task 2: hdri mode's backdrop is either a ground-projected dome
  // (state.hdriProjection === "projected") or the flat infinite equirect
  // background used before this task. Both read state.hdriRotation, so a
  // full rebuild covers projection, scale, height and rotation changes
  // alike; the rotation slider's "input" handler moves the live dome/
  // background directly instead of paying for a rebuild every drag tick.
  disposeHdriDome();
  document.getElementById("hdri-scale-row").classList.toggle("hidden", state.hdriProjection !== "projected");
  document.getElementById("hdri-height-row").classList.toggle("hidden", state.hdriProjection !== "projected");
  const rotation = THREE.MathUtils.degToRad(state.hdriRotation);
  // Equirects are authored Y-up; the scene is Z-up, so the environment
  // sampler rotates a quarter turn about X, same as the old flat backdrop.
  scene.environmentRotation.set(Math.PI / 2, 0, rotation);
  if (state.hdriProjection === "projected" && backdropTexture()) {
    const dome = new GroundedSkybox(backdropTexture(), state.hdriHeight, state.hdriScale);
    // GroundedSkybox is centred on the camera by default; position.y lifts
    // its flattened ground disc up to the dome's own origin (three's own
    // documented usage), then the wrapping group's x = PI/2 stands the
    // whole thing up so that disc lands on the scene's z = 0 ground. The
    // user's rotation is about the world vertical, which -- before that
    // quarter turn is applied -- is the dome's own local Y axis, so it is
    // set on the dome (not the group).
    dome.position.y = state.hdriHeight;
    dome.rotation.y = rotation;
    const group = new THREE.Group();
    group.rotation.x = Math.PI / 2;
    // Under the studio's floor by HDRI_DROP, so the floor wins the depth
    // test everywhere it exists and the photograph carries on beyond it.
    group.position.z = groundLevel() - HDRI_DROP;
    group.add(dome);
    scene.add(group);
    hdriDome = group;
    scene.background = null;
  } else {
    scene.background = backdropTexture(); // null paints the clear colour until a file loads
    scene.backgroundRotation.set(Math.PI / 2, 0, rotation);
  }
}

async function refreshHdriList(selectName) {
  // null signals a failed fetch, already bannered here: callers must stop
  // rather than fall through to loadHdri, which would fail the same fetch
  // again and banner it a second time. [] is a real, successful answer
  // (no HDRIs installed) and callers may carry on past it.
  let files;
  try {
    ({ files } = await fetchJson("/api/hdri"));
  } catch (error) {
    showBanner("Failed to load the HDRI list: " + error.message, "error");
    return null;
  }
  const select = document.getElementById("hdri-select");
  select.innerHTML = "";
  if (!files.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "no HDRIs installed";
    select.appendChild(option);
    return [];
  }
  for (const name of files) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  const stored = selectName || localStorage.getItem("bench-studio-hdri");
  if (stored && files.includes(stored)) select.value = stored;
  // The tiles are built from the same list and read the same select, so
  // the picture and the choice cannot disagree. The picker face gets the
  // same courtesy: the value above was set without a change event.
  buildHdriTiles(files);
  repaintSettingControls();
  return files;
}

// ---------- the loading toast ----------
// Every asset fetch says so on the glass: a translucent card with a
// turning ring (Param: "lets have it say its loading in translucent pop
// up message with a loading animation"). Counted, not toggled, so
// overlapping loads keep one card up until the last of them lands; the
// label is last-writer-wins, which is the load the user just asked for.
let loadingHeld = 0;
function beginLoading(label) {
  loadingHeld += 1;
  const toast = document.getElementById("loading-toast");
  if (toast) {
    document.getElementById("loading-toast-text").textContent = label;
    toast.classList.remove("hidden");
  }
  let done = false;
  return () => {
    if (done) return;               // a catch and a finally may both call it
    done = true;
    loadingHeld = Math.max(0, loadingHeld - 1);
    if (!loadingHeld && toast) toast.classList.add("hidden");
  };
}

// The sharp visible sky, separate from the one that lights the scene.
// Two cheap textures doing one job each beat one expensive texture doing
// both badly: 2048 of 8-bit sRGB is 16 MB and looks right behind a vault,
// where 8192 of half-float is 256 MB and is then thrown away by the blur.
async function loadHdriBackdrop(name) {
  const wanted = name;
  const done = beginLoading("Preparing sky " + name + " at full quality");
  try {
    // Full resolution is for machines with the memory to hold it: a 16k
    // backdrop uploads as half a GIGABYTE of texture, and an iPad asked
    // to carry that sheds every other texture to fit it -- the lighting
    // environment included, which is where Param's "sun drop out while
    // changing hdris on other devices" came from. Touch devices get a 4k
    // sky: 32 MB, and the vault keeps its light.
    const texture = await new THREE.TextureLoader().loadAsync(
      "/api/hdri/" + encodeURIComponent(name) + "/background"
      + (CONSTRAINED_DEVICE ? "?px=4096" : ""));
    done();
    // A slower sky that lost the race must not replace a faster one that
    // won it: the user may have changed their mind while this was in flight.
    if (state.hdriName !== wanted) { texture.dispose(); return; }
    texture.mapping = THREE.EquirectangularReflectionMapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    if (state.hdriBackdrop) state.hdriBackdrop.dispose();
    state.hdriBackdrop = texture;
    applyHdriBackdrop();
    // A named milestone: when a device goes dark with no error (the iPad
    // has), the on-screen log says which stage still spoke.
    logStudio("sky backdrop ready: " + name + " at "
      + (texture.image ? texture.image.width : "?") + "px");
  } catch (error) {
    logStudio("the sharp sky for " + name + " did not arrive: " + error.message);
  } finally {
    done();
  }
}

function backdropTexture() {
  // The sharp one when it has arrived, the lighting one until then, so a
  // sky appears at once and gets better rather than appearing late.
  return state.hdriBackdrop || state.hdriTexture;
}

async function loadHdri(name) {
  const status = document.getElementById("hdri-status");
  status.textContent = "loading " + name;
  // The first ask for a big sky is a real wait: the server is deriving
  // the full-resolution backdrop from a 100-300 MB source, once.
  const done = beginLoading("Loading sky " + name);
  try {
    // The DERIVED lighting file, not the original. 1024 by 512 is what
    // three.js asks for in as many words, and the difference is not small:
    // an 8k source is 256 MB of half-float texture and about a gigabyte of
    // peak video memory to prefilter, for a picture the prefilter then
    // blurs into a 256 pixel cube.
    //
    // FloatType stays. It doubles the source texture, but at 1k that is
    // 4 MB rather than 512, and estimateSunFromEquirect below wants
    // Float32Array pixels to find the sun in.
    const loader = new HDRLoader().setDataType(THREE.FloatType);
    const texture = await loader.loadAsync(
      "/api/hdri/" + encodeURIComponent(name) + "/light");
    texture.mapping = THREE.EquirectangularReflectionMapping;
    if (state.hdriTexture) state.hdriTexture.dispose();
    state.hdriTexture = texture;
    // The other named milestone (see loadHdriBackdrop): if a device shows
    // this line but the scene stands dark, the failure is downstream of
    // the light's arrival -- in the prefilter or the upload.
    logStudio("sky light ready: " + name);
    // And the sharp one, for the sky the eye actually looks at. It is an
    // ordinary tone-mapped PNG: a background sits behind the tone mapper
    // anyway and has no use for the dynamic range. Loaded in parallel and
    // allowed to fail, because a soft sky is a disappointment and a missing
    // sky is a black frame.
    loadHdriBackdrop(name);
    state.hdriName = name;
    localStorage.setItem("bench-studio-hdri", name);
    const image = texture.image;
    const estimate = estimateSunFromEquirect(image.data, image.width, image.height);
    // The estimator speaks image space. Three's equirect shader samples
    // u = atan2(dir.z, dir.x) / (2 * pi) + 0.5, and the backgroundRotation
    // quarter-turn is uploaded transposed, so world azimuth = 180 - image
    // azimuth, not the negated image azimuth. state.hdriRotation spins the
    // dome/background on top of that, so it folds into the same sum; the
    // raw estimate is kept so the rotation slider can redo this without
    // re-scanning pixels (Task 2).
    state.hdriEstimateAzimuth = estimate.azimuthDeg;
    const azimuth = ((180 - estimate.azimuthDeg + state.hdriRotation) % 360 + 360) % 360;
    document.getElementById("sun-azimuth").value = Math.round(azimuth);
    document.getElementById("sun-elevation").value =
      Math.round(Math.min(85, Math.max(5, estimate.elevationDeg)));
    // applyEnvironment's hdri branch deliberately leaves sun.intensity and
    // sun.color alone (Task 3 sets only hemi, exposure and
    // environmentIntensity there), so the estimate survives the call below.
    sun.intensity = estimate.intensity;
    status.textContent = "";
    applyEnvironment();
    regenerateEnvironment();
    logStudio("loaded hdri " + name);
  } catch (error) {
    // #hdri-status keeps progress text only; the failure itself goes to
    // the banner, named, so it cannot be missed off-screen or overwritten
    // by the next progress message.
    status.textContent = "";
    showBanner("Could not load HDRI " + name + ": " + error.message, "error");
    regenerateEnvironment(); // keep the environment matching state.environmentMode even on failure
  } finally {
    done();
  }
}

// ---------- procedural textures: offline, no image assets ----------
function noiseTexture(size, base, variation) {
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasEl.height = size;
  const context = canvasEl.getContext("2d");
  const image = context.createImageData(size, size);
  let seed = 1234567;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < image.data.length; i += 4) {
    const v = base + (random() - 0.5) * 2 * variation;
    image.data[i] = image.data[i + 1] = image.data[i + 2] = Math.max(0, Math.min(255, v));
    image.data[i + 3] = 255;
  }
  context.putImageData(image, 0, 0);
  const texture = new THREE.CanvasTexture(canvasEl);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(6, 6);
  // Anisotropy 1 shimmers into moire bands at grazing angles, which is
  // most of a vault seen from eye height.
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return texture;
}

function grainTexture(size) {
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasEl.height = size;
  const context = canvasEl.getContext("2d");
  context.fillStyle = "#a9793f";
  context.fillRect(0, 0, size, size);
  let seed = 424242;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let y = 0; y < size; y += 3) {
    const tone = 0.75 + 0.25 * random();
    context.fillStyle = "rgba(" + Math.floor(140 * tone) + "," + Math.floor(96 * tone) + "," + Math.floor(48 * tone) + ",0.55)";
    context.fillRect(0, y + Math.floor(3 * random()), size, 1 + Math.floor(2 * random()));
  }
  const texture = new THREE.CanvasTexture(canvasEl);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3, 3);
  // Same grazing-angle moire fix as noiseTexture.
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return texture;
}

// E4: joints drawn into colour, roughness and bump so raking sun catches
// them. The disc's CircleGeometry UVs span its 120 m diameter once, so a
// repeat of n gives cells of 120 / n metres.
function groundJointTexture(cols, rows, staggered, baseTone) {
  const size = 512;
  const canvasEl = document.createElement("canvas");
  canvasEl.width = canvasEl.height = size;
  const context = canvasEl.getContext("2d");
  let seed = 987654;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  const cellW = size / cols;
  const cellH = size / rows;
  for (let row = 0; row < rows; row += 1) {
    const offset = staggered && row % 2 === 1 ? cellW / 2 : 0;
    for (let col = -1; col < cols; col += 1) {
      const tone = baseTone + Math.floor((random() - 0.5) * 22);
      context.fillStyle = "rgb(" + tone + "," + tone + "," + (tone - 4) + ")";
      context.fillRect(col * cellW + offset + 2, row * cellH + 2, cellW - 4, cellH - 4);
    }
  }
  const texture = new THREE.CanvasTexture(canvasEl);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return texture;
}

// One built-in floor: the neutral studio ground. The procedural slab,
// paver and tile stand-ins are gone on Param's word -- every real surface
// comes from the ground library folder now, and a scene saved with one of
// the old presets falls back to dark-studio via the guard below.
const GROUNDS = {
  "dark-studio": () => new THREE.MeshPhysicalMaterial({ color: 0x22242a, roughness: 0.95 }),
};

const groundMaterialCache = {};

// The ground's own loaded library material, separate from the vault's.
// Repeat lives on the texture, and two surfaces wearing one material want
// different repeats, so sharing one set would mean the floor's tiling and
// the vault's fighting over the same object.
let groundLibrarySet = null;

function groundMaterial(preset) {
  if (isLibraryKey(preset)) {
    // Until the maps arrive, the studio floor stands in. A frame of dark
    // grey beats a frame of white default material.
    return groundLibrarySet && groundLibrarySet.entry.key === preset
      ? groundLibrarySet.material : groundMaterial("dark-studio");
  }
  if (!GROUNDS[preset]) preset = "dark-studio";
  if (!groundMaterialCache[preset]) groundMaterialCache[preset] = GROUNDS[preset]();
  return groundMaterialCache[preset];
}

async function loadGroundMaterial(key) {
  if (!isLibraryKey(key)) {
    // Leaving the library frees what it was wearing: the floor is one
    // surface and there is no reason to keep a set nothing draws.
    if (groundLibrarySet) { disposeLibraryMaterial(groundLibrarySet); groundLibrarySet = null; }
    rebuildGround();
    return;
  }
  const entry = groundLibraryEntry(key);
  if (!entry) return;
  const done = beginLoading("Loading floor " + (entry.label || key));
  try {
    const set = await loadLibraryMaterial(entry, {
      px: VIEWPORT_PX,
      anisotropy: renderer.capabilities.getMaxAnisotropy(),
      relief: state.ground.relief,
      occlusion: state.occlusion,
      base: GROUND_BASE,
    });
    // A floor is seen from one side, so it costs nothing to say so, and
    // single-sided geometry is half the fragment work.
    set.material.side = THREE.FrontSide;
    if (groundLibrarySet) disposeLibraryMaterial(groundLibrarySet);
    groundLibrarySet = set;
    logStudio("floor: " + entry.label + (entry.tileMetres
      ? " at " + Math.round(entry.tileMetres[0] * 1000) + " x "
        + Math.round(entry.tileMetres[1] * 1000) + " mm"
      : " at an unknown size"));
  } catch (error) {
    logStudio("floor " + key + " would not load: " + error.message);
    return;
  } finally {
    done();
  }
  rebuildGround();
}

// The plane everything stands on, and the reason it is not zero.
//
// The analysis surface is the vault's MID-surface, so the built vault's
// underside at the springing sits half a thickness BELOW the support nodes,
// the drawn net hangs a wire radius below that again (netClearance), and the
// falsework ghost lower still. A floor at z = 0 therefore cuts through all
// three and the vault reads as sunk into its own site, which is exactly what
// it looked like: reported from the screen, 2026-09-04, "the vaults seems to
// be always lower than the floor". The floor goes under the lowest of them,
// with 40 mm of air so nothing z-fights it.
//
// The HDRI dome's photographic ground rides just BELOW this plane, not on
// it: coplanar surfaces z-fight, and two grounds at the same height tore
// into stripes of grass and paving across the whole floor (photographed
// 2026-09-04). A finger's width of separation is invisible from any camera
// that can see the vault and settles the depth test outright.
const HDRI_DROP = 0.05;

function groundLevel() {
  const thickness = state.bundle && state.bundle.provenance
    ? state.bundle.provenance.thickness : 0;
  return -(thickness / 2 + Math.max(state.wireRadius, state.nodeRadius) + 0.04);
}

// The floor is a disc, so "how much flooring there is" is one radius. The
// jointed presets carry the physical size of one texture image, so their
// repeat is recomputed from the disc every time it is resized; the plain
// and noise presets have no joint to keep honest and are left alone.
function rebuildGround() {
  const existing = state.objects.ground;
  if (existing) {
    scene.remove(existing);
    // The geometry is ours and is replaced on every resize. The material
    // is NOT: groundMaterialCache hands the same one back for a preset, so
    // disposing it here would take the texture with it.
    existing.geometry.dispose();
    state.objects.ground = null;
  }
  const material = groundMaterial(state.groundPreset);
  if (groundLibrarySet && material === groundLibrarySet.material) {
    // The library knows how much of the world one picture shows, so the
    // repeat is arithmetic rather than a number tuned by eye. Every map,
    // not the albedo alone: each slot carries its own transform uniform and
    // a mismatch shows the moment the sun moves. The scale dials multiply
    // that truth per axis (Param: "a scale x and y is preferable"), and
    // the randomised offset slides the whole pattern so two renders of the
    // same floor need not land the same grout line under the same pier.
    const tile = groundLibrarySet.entry.tileMetres
      || [DEFAULT_TILE_METRES, DEFAULT_TILE_METRES];
    const [u, v] = groundRepeat(state.groundRadius, tile);
    setRepeat(groundLibrarySet, u * state.ground.scaleX, v * state.ground.scaleY);
    for (const texture of groundLibrarySet.textures) {
      texture.offset.set(state.ground.offset[0], state.ground.offset[1]);
      // The rotation is what makes Randomise VISIBLE: sliding a periodic
      // pattern lands it back on itself, but a fresh lay angle cannot be
      // missed. About the disc centre, every map together. (With unequal
      // scale dials a rotation shears the pattern a little; the dials are
      // equal in every ordinary use.)
      texture.center.set(0.5, 0.5);
      texture.rotation = state.ground.rotation || 0;
    }
  } else {
    const tile = material.userData.groundTileMetres;
    if (tile && material.map) {
      const [u, v] = groundRepeat(state.groundRadius, tile);
      material.map.repeat.set(u * state.ground.scaleX, v * state.ground.scaleY);
      material.map.center.set(0.5, 0.5);
      material.map.rotation = state.ground.rotation || 0;
    }
  }
  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(state.groundRadius, 64), material);
  ground.receiveShadow = true;
  const level = groundLevel();
  ground.position.z = level;
  // The props stand on the floor, not on the analysis plane: their models
  // are built with their feet at z = 0, so the group carries the drop.
  propsGroup.position.z = level;
  // A dome already up when the study changed would keep the old thickness's
  // floor, so it is levelled here too rather than only where it is built.
  if (hdriDome) hdriDome.position.z = level - HDRI_DROP;
  state.objects.ground = ground;
  scene.add(ground);
}

// ---------- E5: placeable props ----------
// Procedural low-poly groups, origin on the ground plane, metres for
// units. They cast shadows, never join analysis picking or recolouring,
// and their layout is mirrored to localStorage per study.
const propsGroup = new THREE.Group();
scene.add(propsGroup);

function propMaterial(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.85 });
}

function propFigure() {
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.95, 4, 8), propMaterial(0x4a5560));
  body.rotation.x = Math.PI / 2;
  body.position.z = 0.78;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8), propMaterial(0xc8a288));
  head.position.z = 1.62;
  group.add(body, head);
  return group;
}

function propTree() {
  const group = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.14, 1.6, 8), propMaterial(0x6b4f35));
  trunk.rotation.x = Math.PI / 2;
  trunk.position.z = 0.8;
  const lower = new THREE.Mesh(new THREE.SphereGeometry(1.15, 10, 8), propMaterial(0x4d6b3a));
  lower.position.z = 2.3;
  const upper = new THREE.Mesh(new THREE.SphereGeometry(0.8, 10, 8), propMaterial(0x557a41));
  upper.position.z = 3.2;
  group.add(trunk, lower, upper);
  return group;
}

function propPallets() {
  const group = new THREE.Group();
  for (let level = 0; level < 3; level += 1) {
    const slab = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.8, 0.14), propMaterial(0xa08050));
    slab.position.z = 0.07 + level * 0.16;
    group.add(slab);
  }
  return group;
}

function propBarrier() {
  const group = new THREE.Group();
  const rail = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.06, 0.5), propMaterial(0xd8d8d8));
  rail.position.z = 0.7;
  group.add(rail);
  for (const x of [-0.9, 0.9]) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.5, 0.95), propMaterial(0xd8d8d8));
    leg.position.set(x, 0, 0.475);
    group.add(leg);
  }
  return group;
}

function propCone() {
  const group = new THREE.Group();
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.65, 12), propMaterial(0xd2622a));
  cone.rotation.x = Math.PI / 2;
  cone.position.z = 0.36;
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.42, 0.05), propMaterial(0x33363a));
  base.position.z = 0.025;
  group.add(cone, base);
  return group;
}

const PROP_BUILDERS = {
  figure: propFigure, tree: propTree, pallets: propPallets,
  barrier: propBarrier, cone: propCone,
};

function makeProp(type) {
  const group = PROP_BUILDERS[type]();
  group.traverse((child) => {
    if (child.isMesh) { child.castShadow = true; child.receiveShadow = true; }
  });
  group.userData.propType = type;
  return group;
}

function propsKey() {
  return "bench-studio-props:" + state.bundle.export;
}

// ---------- layers ----------
function layerById(id) {
  return state.propLayers.find((layer) => layer.id === id);
}

function layerVisible(id) {
  const layer = layerById(id);
  return !layer || layer.visible !== false;
}

// A hidden layer's props stay in the record and out of the scene AND out
// of picking: an invisible tree that still catches clicks would be a
// haunting.
function applyLayerVisibility() {
  for (const record of state.props) {
    record.object.visible = layerVisible(record.layer);
  }
  if (state.selectedProp && !layerVisible(state.selectedProp.layer)) {
    selectProp(null);
  }
}

function newLayer(name) {
  // The name reads the id BEFORE the increment, or "Layer 2" is born
  // calling itself Layer 3 (it was).
  const layer = { id: state.nextLayerId,
    name: name || ("Layer " + state.nextLayerId), visible: true };
  state.nextLayerId += 1;
  state.propLayers.push(layer);
  state.activeLayer = layer.id;
  return layer;
}

// Restore a saved layers list (from a layout or a scene), tolerating the
// older shapes that had none.
function adoptLayers(saved) {
  if (Array.isArray(saved) && saved.length) {
    state.propLayers = saved.map((layer) => ({
      id: +layer.id || 1,
      name: String(layer.name || "Layer"),
      visible: layer.visible !== false,
    }));
  } else {
    state.propLayers = [{ id: 1, name: "Layer 1", visible: true }];
  }
  state.nextLayerId = 1 + Math.max(...state.propLayers.map((l) => l.id));
  if (!layerById(state.activeLayer)) {
    state.activeLayer = state.propLayers[0].id;
  }
}

function saveProps() {
  if (!state.bundle) return;   // no study, nowhere to key the layout
  const layout = {
    layers: state.propLayers.map((layer) => ({
      id: layer.id, name: layer.name, visible: layer.visible })),
    props: state.props.map((p) => ({
      type: p.type, x: p.x, y: p.y, rotation: p.rotation,
      scale: p.scale || 1, layer: p.layer || 1 })),
  };
  localStorage.setItem(propsKey(), JSON.stringify(layout));
}

// Mirrors disposeShell's rule: whatever is replaced owns GPU buffers.
function disposeProp(object) {
  // Library props are clones sharing one template's geometry and materials,
  // so freeing them here would empty the template every other clone is
  // still drawing from. The template owns its resources for the session.
  if (object.userData.fromLibrary) return;
  object.traverse((child) => {
    if (child.isMesh) {
      child.geometry.dispose();
      child.material.dispose();
    }
  });
}

// Set when a restore met a prop whose model had not arrived yet. The prop
// library loads over the network and can finish AFTER the first restore,
// so without this a cold boot silently drops every library prop a study
// was saved with, and the loss looks like the study never had them.
let propsAwaitingLibrary = false;

function knownPropType(type) {
  return propTemplates.has(type) || !!PROP_BUILDERS[type];
}

function restoreProps() {
  for (const record of state.props) { disposeProp(record.object); propsGroup.remove(record.object); }
  state.props = [];
  // Through selectProp, never by assignment: the outline and the gumball
  // follow the selection, and a bare null leaves them orbiting a corpse.
  selectProp(null);
  let layout = [];
  try {
    layout = JSON.parse(localStorage.getItem(propsKey()) || "[]");
  } catch (error) {
    layout = [];
  }
  // Two shapes on disk: the old bare array of props, and the layered
  // {layers, props} that replaced it. Both restore.
  let entries = layout;
  if (!Array.isArray(layout) && layout && Array.isArray(layout.props)) {
    adoptLayers(layout.layers);
    entries = layout.props;
  } else {
    adoptLayers(null);
  }
  if (!Array.isArray(entries)) entries = [];
  propsAwaitingLibrary = false;
  for (const entry of entries) {
    if (!knownPropType(entry.type)) {
      // Either the manifest is still in flight, or this prop is gone from
      // it. Either way the entry stays in the saved layout untouched, so a
      // library that arrives late can put it back.
      propsAwaitingLibrary = true;
      // Known to the manifest but not loaded yet: ask for exactly this
      // model, and run the restore again when it lands. ensure dedupes,
      // and the re-run fires only from the call that CREATED the load, so
      // repeated restores cannot multiply into repeated fetches.
      if (propLibraryEntry(entry.type) && !propTemplatePromises.has(entry.type)) {
        ensurePropTemplate(entry.type).then((template) => {
          if (template && propsAwaitingLibrary) restoreProps();
        });
      }
      continue;
    }
    const record = placeProp(entry.type, +entry.x || 0, +entry.y || 0,
      +entry.rotation || 0, false, +entry.scale || 1);
    record.layer = +entry.layer || 1;
  }
  applyLayerVisibility();
}

// ---------- the prop library ----------
// Props are real models now: GLB files in bench/studio/props, listed by a
// manifest that says what each one is, how tall it stands in the world and
// who made it. The height matters more than it looks: a GLB carries
// whatever units its author worked in, so a figure is only a SCALE figure
// if the studio scales it to a stated height rather than trusting the file.
const propLoader = new GLTFLoader();
const propTemplates = new Map();
// One promise per model asked for, forever: a failed load resolves null and
// STAYS null for the session, or restoreProps would re-ask for a broken
// file every time a template arrived and never converge.
const propTemplatePromises = new Map();

function propLibraryEntry(key) {
  return state.propLibrary.find((entry) => entry.key === key) || null;
}

// The library loads NOTHING up front any more. Eager loading pulled all
// 241 MB of models through the wire and the parser at every boot, which a
// desktop shrugged at and the iPad died of: an iOS tab gets a fraction of
// a desktop's memory, and the boot-time spike of parsing a hundred models
// while the vault was still cutting was the difference between the studio
// working there and not opening at all. A model now loads the first time
// something actually needs its geometry: a placement, a restore, or a
// tile whose thumbnail file is missing.
function ensurePropTemplate(key) {
  if (propTemplates.has(key)) return Promise.resolve(propTemplates.get(key));
  const entry = propLibraryEntry(key);
  if (!entry) return Promise.resolve(null);
  if (!propTemplatePromises.has(key)) {
    const done = beginLoading("Loading " + (entry.label || entry.key));
    propTemplatePromises.set(key, loadPropTemplate(entry)
      .then((template) => {
        propTemplates.set(key, template);
        return template;
      })
      .catch((error) => {
        logStudio("prop " + key + " would not load: " + error.message);
        return null;
      })
      .finally(done));
  }
  return propTemplatePromises.get(key);
}

async function loadPropLibrary() {
  let payload = null;
  try {
    payload = await fetchJson("/api/props");
  } catch (error) {
    return;                              // no library, the old props stand
  }
  const entries = (payload.props || []).filter((entry) => entry && entry.key && entry.file);
  if (!entries.length) return;
  state.propLibrary = entries;
  state.propCredits = payload.library || null;
  buildPropTiles();
  // The type select is still the source of truth for what Place will place,
  // exactly as the material select is behind the material tiles. Every
  // manifest entry is offered: whether its file loads is only knowable by
  // loading it, which now happens when it is chosen.
  const select = document.getElementById("prop-type");
  select.innerHTML = "";
  for (const entry of entries) {
    const option = document.createElement("option");
    option.value = entry.key;
    option.textContent = entry.label || entry.key;
    select.appendChild(option);
  }
  if (select.options.length) select.value = select.options[0].value;
  logStudio("prop library: " + entries.length + " models");
  // A cold boot restores a study's props before this manifest arrives, so
  // anything it had to skip gets a second chance now that the names are
  // known (the models themselves follow, one ensure at a time).
  if (propsAwaitingLibrary) restoreProps();
}

// Whose shadow is worth a shadow pass. Draw calls become the bottleneck
// before triangles do, and a tuft of grass casting a shadow doubles its
// cost for something nobody will ever look for.
const SHADOWLESS = new Set(["planting"]);

function castsShadow(entry) {
  if (!entry) return true;
  if (!SHADOWLESS.has(entry.group)) return true;
  // A tree is planting and its shadow is half the reason to place it; a
  // dandelion is planting too. The size decides, not the group alone.
  const height = entry.sizeMetres ? entry.sizeMetres[1] : null;
  return height === null || height > 1.2;
}

async function loadPropTemplate(entry) {
  const gltf = await propLoader.loadAsync("/api/props/" + encodeURIComponent(entry.file));
  const model = gltf.scene;
  // glTF is Y-up by convention and the studio is Z-up.
  model.rotation.x = Math.PI / 2;
  model.updateMatrixWorld(true);
  const measured = new THREE.Box3().setFromObject(model);
  const height = measured.max.z - measured.min.z;
  // Scale ONLY when the manifest declares a height, and trust the file
  // otherwise. The old fallback was `: 1`, which quietly made every prop
  // exactly one metre tall: a photoscanned pine tree came into the scene the
  // size of a fire hydrant, and so did the fire hydrant. Poly Haven's models
  // are authored in metres and are already right; the hand-built props
  // declare a height because they are not modelled to any scale at all.
  const wanted = +entry.heightMetres > 0 ? +entry.heightMetres : null;
  if (wanted && height > 0.0001) model.scale.multiplyScalar(wanted / height);
  model.updateMatrixWorld(true);
  // Stood on the ground rather than centred on it: a prop's feet are its
  // origin as far as the scene is concerned.
  const stood = new THREE.Box3().setFromObject(model);
  model.position.z -= stood.min.z;
  // Not everything casts. Draw calls become the bottleneck before triangles
  // do, and a shadow pass over a hundred tufts of grass costs as much as one
  // over a hundred buildings for something nobody will ever look for.
  const casts = castsShadow(entry);
  model.traverse((child) => {
    if (child.isMesh) { child.castShadow = casts; child.receiveShadow = true; }
  });
  const template = new THREE.Group();
  template.add(model);
  return template;
}

function buildPropTiles() {
  const holder = document.getElementById("prop-tiles");
  const select = document.getElementById("prop-type");
  if (!holder) return;
  holder.innerHTML = "";
  // In groups, on the manifest's own `group`, which the client has carried
  // and ignored since the library arrived. Planting, site, street and
  // furniture are what a person is looking for when they open this, and
  // twenty-nine ungrouped tiles are a pile.
  const ordered = [...state.propLibrary].sort((a, b) =>
    String(a.group || "other").localeCompare(String(b.group || "other"))
    || String(a.label || a.key).localeCompare(String(b.label || b.key)));
  let group = null;
  for (const entry of ordered) {
    if ((entry.group || "other") !== group) {
      group = entry.group || "other";
      const heading = document.createElement("span");
      heading.className = "tile-family";
      heading.textContent = group;
      heading.dataset.group = group;
      holder.appendChild(heading);
    }
    // The picture is a FILE, not a render: a .thumb.png snapped once on
    // the desktop sits beside each model, and drawing it costs an image
    // fetch instead of the model itself. Only a prop with no snapshot yet
    // falls back to loading its geometry for a live preview -- the cost
    // the whole lazy library exists to avoid paying a hundred times.
    const tile = previewTile(entry.key, entry.label || entry.key,
      (canvasEl) => {
        fillFlat(canvasEl, new THREE.Color(0x2a2e34));
        const picture = new Image();
        picture.onload = () => {
          canvasEl.getContext("2d").drawImage(
            picture, 0, 0, canvasEl.width, canvasEl.height);
        };
        picture.onerror = () => {
          ensurePropTemplate(entry.key).then((template) => {
            if (template) renderObjectPreview(template, canvasEl);
          });
        };
        picture.src = "/api/props/"
          + encodeURIComponent(entry.file + ".thumb.png");
      });
    tile.dataset.group = group;
    // Scale in words, which is Blender's own advice and the only method in
    // the whole survey that does not put a stock human being in the picture.
    tile.title = (entry.label || entry.key)
      + (entry.sizeMetres ? "  " + entry.sizeMetres.map(
        (n) => n.toFixed(n < 1 ? 2 : 1)).join(" x ") + " m" : "")
      + (entry.credit ? " -- " + entry.credit : "");
    tile.addEventListener("click", async () => {
      select.value = entry.key;
      paintTileSelection(holder, entry.key);
      showPropCredit(entry);
      // Choosing IS picking up. Param: "it should just be a drop down and
      // i click that it gets attached to my cursor and then i move the
      // cursor to the place i like click again and the prop stays." So the
      // model is carrying, not arming: the prop exists from this moment,
      // follows the cursor, and the next click puts it down. The SHELF
      // STAYS OPEN: closing itself after every click was the old picker's
      // worst habit. The model itself may not be here yet -- this click is
      // often the very first thing to want it -- so the carry waits for
      // the load, behind the same toast every other load shows.
      const template = await ensurePropTemplate(entry.key);
      if (!template && !PROP_BUILDERS[entry.key]) return;
      carryNewProp(entry.key);
    });
    holder.appendChild(tile);
  }
  paintTileSelection(holder, select.value);
}

function showPropCredit(entry) {
  const line = document.getElementById("prop-credit");
  if (!line) return;
  line.textContent = entry.credit
    ? entry.credit + (entry.licence ? " (" + entry.licence + ")" : "")
    : "";
}

// A prop preview is the same rig the materials use, with the ball hidden
// and the model framed by its own bounding box.
function renderObjectPreview(object, canvasEl) {
  if (!previewRig) {
    fillFlat(canvasEl, new THREE.Color(0x2a2e34));
    return;
  }
  const shown = object.clone();
  previewRig.holder.add(shown);
  previewRig.ball.visible = false;
  const box = new THREE.Box3().setFromObject(shown);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  const reach = Math.max(size.x, size.y, size.z) || 1;
  // Framed from the same three-quarter angle every time, so a row of props
  // reads as a set rather than as a pile of unrelated photographs.
  const distance = reach * 2.6;
  previewRig.camera.position.set(
    centre.x + distance * 0.62, centre.y - distance * 0.72, centre.z + distance * 0.42);
  previewRig.camera.lookAt(centre);
  // The rig's frustum is sized for the material ball (far plane 20). A
  // cliff face framed from sixty metres sat entirely BEYOND it, and every
  // large prop's preview came out an empty square -- sixteen of the
  // library's models, measured. The planes follow the framing, then go
  // back, so the ball keeps its tuned depth precision.
  previewRig.camera.near = Math.max(distance / 50, 0.01);
  previewRig.camera.far = distance * 4 + reach;
  previewRig.camera.updateProjectionMatrix();
  drawPreview(canvasEl);
  previewRig.holder.remove(shown);
  previewRig.ball.visible = true;
  previewRig.camera.near = 0.05;
  previewRig.camera.far = 20;
  previewRig.camera.updateProjectionMatrix();
  previewRig.camera.position.set(0, -3.05, 1.02);
  previewRig.camera.lookAt(0, 0, 0);
}

function placeProp(type, x, y, rotation, save, scale = 1) {
  const template = propTemplates.get(type);
  // A clone shares geometry and materials with its template, which is what
  // makes twenty figures cost one model; it is also why disposeProp does
  // not free anything for a library prop (see there).
  const object = template ? template.clone() : makeProp(type);
  object.position.set(x, y, 0);
  object.rotation.z = rotation;
  // A prop's feet are its origin (loadPropTemplate shifts min.z to 0), so
  // a uniform scale about the origin grows it from the GROUND UP -- the
  // rule Param set: "make sure they always stay attached to ground and
  // not grow from center, but ground up."
  object.scale.setScalar(scale);
  propsGroup.add(object);
  object.userData.fromLibrary = !!template;
  const record = { type, x, y, rotation, scale,
    layer: state.activeLayer, object };
  object.visible = layerVisible(record.layer);
  state.props.push(record);
  if (save) saveProps();
  return record;
}

// A library prop is a clone that SHARES its template's materials, so
// writing emissive on one lit every copy of that model in the scene. An
// outline owns nothing: it is one helper object that follows whichever prop
// is selected and is thrown away when the selection moves on.
let propOutline = null;

function clearPropOutline() {
  if (!propOutline) return;
  propsGroup.remove(propOutline);
  propOutline.geometry.dispose();
  propOutline.material.dispose();
  propOutline = null;
}

function setPropOutline(record) {
  clearPropOutline();
  if (!record) return;
  propOutline = new THREE.BoxHelper(record.object, 0x93a6bb);
  propOutline.material.depthTest = false;
  propOutline.renderOrder = 2;
  // The outline must never CATCH the pointer: it lives in propsGroup, and
  // a line raycast has a one-metre default threshold, so the box around
  // the selected prop was hijacking clicks near its edges -- "if i click
  // on an object it doesnt always select".
  propOutline.raycast = () => {};
  propsGroup.add(propOutline);
}

// The outline is a box around where the prop WAS, so a carried prop has to
// drag it along. Cheap: BoxHelper.update recomputes from the object.
function refreshPropOutline() {
  if (propOutline) propOutline.update();
}

// ---------- the gumball ----------
// Rhino's gesture set, cut down to what a ground prop can do (Param:
// "can we do a gumball where the rotate is like we might find in rhino
// and scale is also like that off the gumball"): a blue ring about Z to
// rotate, a gold square off the ring to scale about the feet, and the
// body itself to move (the existing carry). The record stays the truth;
// saveProps runs on release, not per pixel.
let propGumball = null;

function clearPropGumball() {
  if (!propGumball) return;
  propsGroup.remove(propGumball);
  for (const part of propGumball.children) {
    part.geometry.dispose();
    part.material.dispose();
  }
  propGumball = null;
}

function setPropGumball(record) {
  clearPropGumball();
  if (!record || !state.propEdit) return;
  const box = new THREE.Box3().setFromObject(record.object);
  const radius = Math.max(0.5,
    0.62 * Math.hypot(box.max.x - box.min.x, box.max.y - box.min.y));
  propGumball = new THREE.Group();
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(radius, Math.max(0.02, radius * 0.03), 10, 96),
    new THREE.MeshBasicMaterial({ color: 0x2f6fe4, transparent: true,
      opacity: 0.85, depthTest: false }));
  ring.renderOrder = 3;
  ring.userData.handle = "rotate";
  const grip = new THREE.Mesh(
    new THREE.BoxGeometry(radius * 0.16, radius * 0.16, radius * 0.16),
    new THREE.MeshBasicMaterial({ color: 0xd2a53c, transparent: true,
      opacity: 0.95, depthTest: false }));
  grip.renderOrder = 3;
  grip.position.set(radius * 1.28, 0, 0);
  grip.userData.handle = "scale";
  // The LOOK is slim; the GRAB is generous. A two-centimetre tube needs
  // pixel aim, so each visible handle hides a fat invisible twin that
  // does the actual catching -- the same trick under Rhino's own gumball.
  const grabRing = new THREE.Mesh(
    new THREE.TorusGeometry(radius, Math.max(0.1, radius * 0.14), 8, 48),
    new THREE.MeshBasicMaterial({ visible: false }));
  grabRing.userData.handle = "rotate";
  const grabGrip = new THREE.Mesh(
    new THREE.BoxGeometry(radius * 0.45, radius * 0.45, radius * 0.45),
    new THREE.MeshBasicMaterial({ visible: false }));
  grabGrip.position.copy(grip.position);
  grabGrip.userData.handle = "scale";
  propGumball.add(ring, grip, grabRing, grabGrip);
  propGumball.position.set(record.x, record.y, 0.02);
  propGumball.rotation.z = record.rotation || 0;
  propsGroup.add(propGumball);
}

// Cheap follow while a prop is carried or turned: position and spin only.
// A size change rebuilds instead (setPropGumball), so the ring re-fits.
function refreshPropGumball() {
  if (!propGumball || !state.selectedProp) return;
  propGumball.position.set(state.selectedProp.x, state.selectedProp.y, 0.02);
  propGumball.rotation.z = state.selectedProp.rotation || 0;
}

function gumballHandleAt(event) {
  if (!propGumball) return null;
  // Raycast trusts matrixWorld as stored, and a gumball built THIS frame
  // has not been through a render yet: update it, or the ray tests a
  // ring still sitting at the origin.
  propGumball.updateMatrixWorld(true);
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  const hits = propRaycaster.intersectObjects(propGumball.children, false);
  return hits.length ? hits[0].object.userData.handle : null;
}

let propEditHinted = false;

function selectProp(record) {
  state.selectedProp = record;
  setPropOutline(record);
  setPropGumball(record);
  if (record && !propEditHinted) {
    propEditHinted = true;
    logStudio("selected prop: drag the ring to rotate, the square to "
      + "scale, the body to move; Delete removes");
  }
}

function armProp(type) {
  const already = state.armedPropType === type;
  disarmProp();
  if (already) return;
  state.armedPropType = type;
  controls.enabled = false;
  // Nothing to light any more: the Place button is gone and choosing a
  // prop carries it (see carryNewProp). armProp survives for the keyboard
  // and for anything that still wants the older arming behaviour.
}

function disarmProp() {
  state.armedPropType = null;
  if (!state.propDrag) controls.enabled = true;
}

function groundPointAt(event) {
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  const hit = new THREE.Vector3();
  // The picking plane is the floor itself, not z = 0: they are a hand's
  // width apart and a prop placed on one and drawn on the other slides
  // under the cursor as the camera moves.
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -groundLevel());
  return propRaycaster.ray.intersectPlane(plane, hit) ? hit : null;
}

function propRecordAt(event) {
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  // Matrices first: a prop placed this frame has not rendered yet, and
  // raycast trusts matrixWorld as stored.
  propsGroup.updateMatrixWorld(true);
  // Every hit is tried, not only the first: the nearest hit can be a
  // helper or another prop's stray leaf card, and returning null for it
  // reads as a selection that just did not work.
  const hits = propRaycaster.intersectObjects(propsGroup.children, true);
  for (const hit of hits) {
    let node = hit.object;
    while (node.parent && node.parent !== propsGroup) node = node.parent;
    const record = state.props.find((p) => p.object === node);
    if (record && record.object.visible) return record;
  }
  // A tree is mostly air: a click between the leaves misses every
  // triangle. Fall back to the bounding boxes, nearest box first, so
  // clicking "the tree" means the tree rather than a lottery over its
  // leaf cards.
  const box = new THREE.Box3();
  const point = new THREE.Vector3();
  let best = null;
  let bestDistance = Infinity;
  for (const record of state.props) {
    if (!record.object.visible) continue;
    box.setFromObject(record.object);
    if (!propRaycaster.ray.intersectBox(box, point)) continue;
    const distance = point.distanceToSquared(propRaycaster.ray.origin);
    if (distance < bestDistance) { bestDistance = distance; best = record; }
  }
  return best;
}

const materials = {
  concrete: new THREE.MeshPhysicalMaterial({
    color: 0x939590, side: THREE.DoubleSide,      // neutral mid grey
    map: noiseTexture(256, 205, 14),
    roughness: 0.9, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  "concrete-c50": new THREE.MeshPhysicalMaterial({
    color: 0x5d646c, side: THREE.DoubleSide,      // cooler, darker, denser
    map: noiseTexture(256, 205, 14),
    roughness: 0.72, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  "concrete-sprayed": new THREE.MeshPhysicalMaterial({
    color: 0xcbcbc6, side: THREE.DoubleSide,      // light neutral grey, coarsest
    map: noiseTexture(256, 195, 46),
    roughness: 0.98, roughnessMap: noiseTexture(256, 225, 40),
    metalness: 0.0,
  }),
  timber: new THREE.MeshPhysicalMaterial({
    color: 0xb07a3c, side: THREE.DoubleSide,      // warm brown, not bare white
    map: grainTexture(512),
    roughness: 0.55, metalness: 0.0, sheen: 0.15, sheenColor: 0xd9b98a,
  }),
  brick: new THREE.MeshPhysicalMaterial({
    color: 0x8c4a32, side: THREE.DoubleSide,      // warm red brown, matt
    map: noiseTexture(256, 150, 26),
    roughness: 0.88, roughnessMap: noiseTexture(256, 210, 30),
    metalness: 0.0,
  }),
  tile: new THREE.MeshPhysicalMaterial({
    color: 0xc47a52, side: THREE.DoubleSide,      // lighter, fired sheen
    map: noiseTexture(256, 190, 18),
    roughness: 0.45, metalness: 0.0, sheen: 0.25, sheenColor: 0xe8c9a8,
  }),
  stone: new THREE.MeshPhysicalMaterial({
    color: 0xbfb9a6, side: THREE.DoubleSide,      // pale, mineral
    map: noiseTexture(256, 215, 22),
    roughness: 0.8, roughnessMap: noiseTexture(256, 220, 35),
    metalness: 0.0,
  }),
  steel: new THREE.MeshPhysicalMaterial({
    color: 0xb6bac2, roughness: 0.32, metalness: 1.0, envMapIntensity: 1.2,
  }),
  falsework: new THREE.MeshPhysicalMaterial({
    color: 0x3a3f45, side: THREE.DoubleSide,
    roughness: 0.95, metalness: 0.0, transparent: true, opacity: 0.3,
  }),
};

// ---------- scene building ----------
function meshGeometry(meshData) {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(meshData.vertices.flat());
  const index = [];
  for (const [a, b, c, d] of meshData.faces) index.push(a, b, c, a, c, d);
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const uvs = new Float32Array(meshData.vertices.length * 2);
  meshData.vertices.forEach((v, i) => { uvs[2 * i] = v[0] * 0.15; uvs[2 * i + 1] = v[1] * 0.15; });
  geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  return geometry;
}

// The recipe for a thrust-net drawing: instanced cylinders at the wire
// radius, instanced spheres at the node radius, both on cloned steel with
// per-instance colour armed. The finished net (buildWiresAndNodes) and the
// net the machine is raising (rebuildFormworkObjects) both come from here,
// so the two are literally the same drawing and the handover at the end of
// the raise shows nothing. Flat LineSegments, which the act used to draw,
// read as another medium entirely: no thickness, no material, no nodes.
function netInstances(edgeCount, vertexCount) {
  const cylinder = new THREE.CylinderGeometry(
    state.wireRadius, state.wireRadius, 1, 8, 1, true);
  cylinder.translate(0, 0.5, 0);
  const wireMaterial = materials.steel.clone();
  // Task 6 fix: InstancedMesh.setColorAt writes the instanceColor buffer,
  // but per-instance colour only reaches the fragment shader when the
  // material also opts into the vertex-colour path. vertexColors stays
  // true for the wires' whole lifetime; every instance starts white below
  // so the plain steel look is unchanged until applyWireForces tints it.
  wireMaterial.vertexColors = true;
  wireMaterial.transparent = true;
  const wires = new THREE.InstancedMesh(cylinder, wireMaterial, edgeCount);
  const white = new THREE.Color(0xffffff);
  for (let i = 0; i < edgeCount; i++) wires.setColorAt(i, white);
  // setColorAt is what allocates instanceColor, so a net with no edges at
  // all leaves it null.
  if (wires.instanceColor) wires.instanceColor.needsUpdate = true;
  const nodeMaterial = materials.steel.clone();
  nodeMaterial.transparent = true;
  const nodes = new THREE.InstancedMesh(
    new THREE.SphereGeometry(state.nodeRadius, 12, 8), nodeMaterial, vertexCount);
  // The thrust network is a diagram of the analysis, not a scene object.
  // Once the vault closes, the wires sit hidden inside the shell, and
  // shadow maps ignore both occlusion and opacity, so with castShadow on
  // they projected a grid shadow of an invisible net through the finished
  // vault onto the ground. Overlays cast nothing; castings and columns do.
  wires.castShadow = nodes.castShadow = false;
  return { wires, nodes };
}

// Scratch instances: the two writers below run per edge per frame for the
// whole formwork act, and allocating inside those loops is what turns a
// 1200-edge net into garbage-collector pressure at 60 fps.
const SEGMENT_UP = new THREE.Vector3(0, 1, 0);
const segmentScratch = {
  m: new THREE.Matrix4(), q: new THREE.Quaternion(),
  a: new THREE.Vector3(), b: new THREE.Vector3(),
  d: new THREE.Vector3(), s: new THREE.Vector3(),
};

// One unit cylinder per pair, stood between its two points. `collect`, when
// given, receives a copy of every matrix: that is the forces layer's
// restore record (applyWireForces), and it is filled here so the finished
// net and the act's net are composed by the same arithmetic rather than by
// two copies of it that can drift.
function writeInstancedSegments(mesh, pairs, points, collect) {
  const { m, q, a, b, d, s } = segmentScratch;
  const count = Math.min(mesh.count, pairs.length);
  for (let i = 0; i < count; i++) {
    const p = points[pairs[i][0]];
    const r = points[pairs[i][1]];
    a.set(p[0], p[1], p[2]);
    b.set(r[0], r[1], r[2]);
    d.copy(b).sub(a);
    const length = d.length();
    // A member with no length has no direction to orient by, and a zero
    // scale makes the instance matrix singular -- three derives its normal
    // matrix from it and the mesh renders unlit. Both are real at t = 0,
    // where the machine's net starts reeled onto itself.
    if (length > 1e-9) q.setFromUnitVectors(SEGMENT_UP, d.divideScalar(length));
    s.set(1, Math.max(length, 1e-6), 1);
    m.compose(a, q, s);
    mesh.setMatrixAt(i, m);
    if (collect) collect.push(m.clone());
  }
  mesh.instanceMatrix.needsUpdate = true;
}

function writeInstancedPoints(mesh, points) {
  const m = segmentScratch.m;
  const count = Math.min(mesh.count, points.length);
  for (let i = 0; i < count; i++) {
    m.makeTranslation(points[i][0], points[i][1], points[i][2]);
    mesh.setMatrixAt(i, m);
  }
  mesh.instanceMatrix.needsUpdate = true;
}

// Where the net is DRAWN, against the analysis mid-surface it is solved
// on. The vault is cast on the formwork, so the mould's face is the
// vault's intrados: the net hangs half the built thickness below the
// mid-surface, plus its own radius, which puts the tubes just under the
// face the first course lands on. Each object still clears by its OWN
// radius, which is why there are two values.
//
// This used to be a LIFT of the same size. It was written to cure the
// crown seam (the net breaking through the extrados at the shallow crown)
// and it did, but by drawing the whole vault hanging underneath its own
// formwork -- half a thickness the wrong way. Hanging the net below cures
// the same seam by the same margin and reads the way the thing is built.
// It also agrees with the falsework ghost, which has always sat at
// -(thickness / 2) - 0.05 (see applySceneAtTime).
//
// Same approximation as before: the shift is along +Z rather than the
// local normal, so it is exact where the surface is shallow -- the crown,
// where the seam showed -- and approximate near a steep springing, where
// the net was already comfortably inside the shell either way.
function netClearance() {
  const thickness = state.bundle && state.bundle.provenance
    ? state.bundle.provenance.thickness : 0;
  return {
    wires: -(thickness / 2 + state.wireRadius),
    nodes: -(thickness / 2 + state.nodeRadius),
  };
}

function buildWiresAndNodes(bundle) {
  const { vertices, edges } = bundle.analysis_mesh;
  const { wires, nodes } = netInstances(edges.length, vertices.length);
  // Task 6: the forces layer rebuilds instance matrices (thicker wire =
  // bigger force) and restores them on toggle-off; the base endpoints,
  // orientation and length are collected here so that restore is exact.
  const baseMatrices = [];
  writeInstancedSegments(wires, edges, vertices, baseMatrices);
  writeInstancedPoints(nodes, vertices);
  wires.userData.baseMatrices = baseMatrices;
  return { wires, nodes };
}

function disposeWiresAndNodes() {
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (object) {
      scene.remove(object);
      object.geometry.dispose();
      object.material.dispose();
      // InstancedMesh.dispose() is what frees instanceMatrix/instanceColor
      // GPU buffers in three 0.185 -- disposing the geometry and material
      // alone leaks the instance attribute buffers on every slider drag.
      object.dispose();
      state.objects[key] = null;
    }
  }
}

function disposeShell() {
  const shell = state.objects.shell;
  if (!shell) return;
  scene.remove(shell);
  // The same rule the thrust network follows above: whatever is replaced
  // owns GPU buffers. The shell is rebuilt on every joint gap or taper
  // commit and on every study load, which since the rings slider started
  // reloading is every ring change too. Each casting owns its geometry and
  // a cloned material (see pieceMaterial), so both are ours to free; the
  // textures that clone points at are shared with the registry, and
  // Material.dispose does not touch them.
  for (const segment of shell.children) {
    segment.geometry.dispose();
    segment.material.dispose();
  }
  state.objects.shell = null;
}

function columnGeometryFrom(document_) {
  // Accept either the plain {vertices, faces} shape or a contract-style
  // export (equilibrium.vertices objects + formGraph.faces records).
  let vertices, faces;
  if (document_.vertices && document_.faces) {
    vertices = document_.vertices;
    faces = document_.faces;
  } else if (document_.equilibrium && document_.formGraph) {
    vertices = document_.equilibrium.vertices.map((v) => [v.x, v.y, v.z]);
    faces = document_.formGraph.faces.map((f) => f.vertices);
  } else {
    throw new Error("unrecognised column JSON: need vertices+faces or a contract export");
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(vertices.flat()), 3));
  const index = [];
  for (const face of faces) {
    for (let i = 1; i < face.length - 1; i++) index.push(face[0], face[i], face[i + 1]);
  }
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  return geometry;
}

async function loadColumns(names) {
  const group = new THREE.Group();
  for (const name of names) {
    try {
      const columnDocument = await fetchJson("/api/columns/" + encodeURIComponent(name));
      // bench.columns/1 stamps the radius the exporter swept these solids
      // along. The act's animated members read it, so the two drawings of
      // one set of columns are the same thickness.
      if (typeof columnDocument.radius === "number" && columnDocument.radius > 0) {
        state.columnRadius = columnDocument.radius;
      }
      const geometry = columnGeometryFrom(columnDocument);
      const mesh = new THREE.Mesh(geometry, materials.steel);
      mesh.castShadow = mesh.receiveShadow = true;
      group.add(mesh);
    } catch (error) {
      showBanner("Column file " + name + " failed to load: " + error.message, "error");
    }
  }
  return group;
}

// M1 fix: boot() and importColumns() both need to replace the columns
// group rather than add another one on top of it -- every re-import used
// to call boot(), and boot() used to add a fresh group with no dispose,
// so each re-import stacked one more copy of the columns into the scene.
// Both call sites now share this one dispose-then-reload path.
// Only the LOADED study's own columns file draws. The columns folder is
// server-global, so every study's exported columns rendered into every
// scene at once, which is the stray column geometry Param saw.
function columnsForStudy(names, exportName) {
  if (!exportName) return [];
  return (names || []).filter((n) => n === exportName + "-columns.json");
}

async function reloadColumns(names) {
  if (state.objects.columns) {
    scene.remove(state.objects.columns);
    state.objects.columns = null;
  }
  const previousRadius = state.columnRadius;
  state.columnRadius = null;
  if (names.length) {
    state.objects.columns = await loadColumns(names);
    scene.add(state.objects.columns);
  }
  // boot() learns which columns file belongs to the study only AFTER the
  // first study load, so the act's members are first built on the fallback
  // radius. A radius that arrives or changes rebuilds them at the width the
  // exporter actually swept, at whatever instant the timeline is showing.
  if (state.columnRadius !== previousRadius && formworkObjects) {
    rebuildFormworkObjects();
  }
  // The group is added AFTER buildScene, whose rebuildTimeline was the last
  // thing to decide what the scene shows, so nothing had yet ruled on this
  // group: the exported solids stood at their finished height over a net
  // still lying flat on the ground at t = 0, which is the machine drawn in
  // two different instants at once. Scene-only, so a columns reload never
  // moves the camera -- the rule rebuildWiresAndNodes follows for the same
  // reason.
  if (state.timeline) applySceneAtTime(state.timeline.t);
}

function buildScene(bundle, preserve) {
  // A study load replaces the shell and the thrust network wholesale, so
  // it frees them on the way out rather than leaving them to the garbage
  // collector, which never sees the GPU side.
  disposeShell();
  disposeWiresAndNodes();
  for (const key of Object.keys(state.objects)) {
    if (key === "columns") continue;
    const object = state.objects[key];
    if (object) scene.remove(object);
  }
  const columns = state.objects.columns;
  state.objects = {};
  if (columns) state.objects.columns = columns;
  state.bundle = bundle;

  const falsework = new THREE.Mesh(meshGeometry(bundle.analysis_mesh), materials.falsework);
  falsework.position.z = -0.02;
  state.objects.falsework = falsework;
  scene.add(falsework);

  const { wires, nodes } = buildWiresAndNodes(bundle);
  state.objects.wires = wires;
  state.objects.nodes = nodes;
  scene.add(wires); scene.add(nodes);
  applyWireForces();

  rebuildGround();

  applyCut(preserve);
  buildLayerToggles();
  updateVectorLayers();
  updateMaterialControls();
  restoreProps();
  updateHud();
}

// ---------- saved scenes ----------
// A scene is every setting that decides what the viewport looks like, plus
// the still it looked like when it was saved. It lives on the server rather
// than in browser storage: it is authored by hand, it cannot be rebuilt
// from anything, and a cleared cache is not a reason to lose one.

// The still, cropped to what the eye actually composed (the panel is a
// 300 CSS px overlay over the right of the viewport, so the scene behind it
// was never part of the picture).
//
// The renderer is built with preserveDrawingBuffer (see the WebGLRenderer
// above), which is what makes reading the canvas legal at all. It is NOT
// permission to read whenever: resize() runs first thing every frame and
// its guard compares the DPR-scaled backing store against CSS pixels, so on
// any display scaled above 100% it reassigns canvas.width every frame, and
// assigning that width resets the drawing buffer. Render and read in one
// synchronous block, never across a callback.
function captureThumbnail(width = 240) {
  // The recorder owns the canvas while it runs: it forces 1920x1080 and
  // disables the corrective resize, and an extra render here would land on
  // the frame it is about to upload.
  if (state.recording) return null;
  renderView();
  const sourceHeight = canvas.height;
  const cut = Math.min(canvas.width - 1,
    Math.round(300 * renderer.getPixelRatio()));
  const sourceWidth = canvas.width - cut;
  if (sourceWidth < 8 || sourceHeight < 8) return null;
  const target = document.createElement("canvas");
  target.width = width;
  target.height = Math.max(1, Math.round(width * sourceHeight / sourceWidth));
  // One intermediate at twice the target: the reduction is 10x or more on a
  // full-screen viewport, and browsers only box-filter a single drawImage
  // approximately at that ratio, which turns a net of wires into moire.
  const middle = document.createElement("canvas");
  middle.width = target.width * 2;
  middle.height = target.height * 2;
  const middleContext = middle.getContext("2d");
  middleContext.imageSmoothingQuality = "high";
  middleContext.drawImage(
    canvas, 0, 0, sourceWidth, sourceHeight, 0, 0, middle.width, middle.height);
  const context = target.getContext("2d");
  context.imageSmoothingQuality = "high";
  context.drawImage(middle, 0, 0, target.width, target.height);
  // JPEG, not the recorder's PNG: a 240px still of a lit render is 5 to 9 kB
  // at this quality and 40 to 70 kB as a PNG, and the server caps it.
  return target.toDataURL("image/jpeg", 0.8);
}

// Everything worth keeping, and nothing that cannot be rebuilt: no bundle,
// no THREE handles, no derived exposure base, no HDRI texture (its NAME is
// enough to load it again).
function collectScene() {
  const control = (id) => document.getElementById(id);
  return {
    camera: { position: camera.position.toArray(), target: controls.target.toArray(),
      fov: camera.fov, frame: state.cameraAspect },
    showMode: state.showMode,
    environmentMode: state.environmentMode,
    weatherPreset: state.weatherPreset,
    backgroundTone: +control("background-tone").value,
    brightness: state.brightness,
    contrast: state.contrast,
    hdri: {
      name: state.hdriName, projection: state.hdriProjection,
      scale: state.hdriScale, height: state.hdriHeight, rotation: state.hdriRotation,
    },
    sun: {
      azimuth: +control("sun-azimuth").value,
      elevation: +control("sun-elevation").value,
      elevationSetting: state.sunElevationSetting,
      colour: control("sun-colour").value,
      colourOverride: state.sunColourOverride,
      intensity: sun.intensity,
      intensityOverride: state.sunIntensityOverride,
    },
    dayCycle: {
      seconds: state.dayCycle.seconds,
      peakElevation: state.dayCycle.peakElevation,
      record: state.dayCycle.record,
    },
    ground: { preset: state.groundPreset, radius: state.groundRadius,
      scaleX: state.ground.scaleX, scaleY: state.ground.scaleY,
      relief: state.ground.relief, offset: state.ground.offset.slice(),
      rotation: state.ground.rotation },
    props: state.props.map((record) => ({
      type: record.type, x: record.x, y: record.y, rotation: record.rotation,
      scale: record.scale, layer: record.layer || 1,
    })),
    propLayers: state.propLayers.map((layer) => ({
      id: layer.id, name: layer.name, visible: layer.visible })),
    layers: Object.assign({}, state.layers),
    cut: {
      material: control("material-select").value,
      pattern: state.pattern, size: state.size, thickness: state.thickness,
      jointGap: state.jointGap, taper: state.taper, source: state.source,
    },
    appearance: Object.assign({}, state.appearance),
    timeline: state.timeline ? {
      t: state.timeline.t, speed: state.timeline.speed,
      orbitSpeed: state.timeline.orbitSpeed,
    } : null,
  };
}

// Replaying a scene is an ordering problem, not a copying one. Three rules
// decide the sequence below:
//   1. The cut lives in the bundle URL, so every cut parameter is written
//      into state BEFORE the single loadStudy call. Restoring by poking the
//      controls instead would fire six change handlers, six overlapping
//      server cuts, and two of them through a 1.5 s settle timer that would
//      land after the restore had finished.
//   2. Anything buildScene reads (ground, net radii, joint gap, taper,
//      layers, appearance) has to be in state before it builds, or be
//      rebuilt afterwards.
//   3. The camera goes LAST, after everything that moves it.
async function applyScene(record) {
  const scene_ = record.state || {};
  const control = (id) => document.getElementById(id);
  const cut = scene_.cut || {};
  if (cut.material) control("material-select").value = cut.material;
  if (cut.pattern) { state.pattern = cut.pattern; state.patternChosen = true; }
  if (typeof cut.size === "number") {
    state.size = cut.size; control("size-slider").value = cut.size;
  }
  if (typeof cut.thickness === "number") {
    state.thickness = cut.thickness; control("thickness-input").value = cut.thickness;
  }
  // The joint-gap and taper sliders are gone from the panel: the gap is
  // pinned at 0.001 and the taper at 0. A scene saved while they existed
  // still carries the numbers, so the state is restored and nothing is
  // written to a control that is no longer on the page.
  if (typeof cut.jointGap === "number") state.jointGap = cut.jointGap;
  if (typeof cut.taper === "number") state.taper = cut.taper;
  state.source = cut.source || null;
  if (scene_.ground) {
    if (scene_.ground.preset) {
      state.groundPreset = scene_.ground.preset;
      control("ground-preset").value = scene_.ground.preset;
    }
    if (typeof scene_.ground.radius === "number") {
      state.groundRadius = scene_.ground.radius;
      control("ground-radius").value = scene_.ground.radius;
      control("ground-radius-value").textContent = scene_.ground.radius;
    }
    if (typeof scene_.ground.scaleX === "number") state.ground.scaleX = scene_.ground.scaleX;
    if (typeof scene_.ground.scaleY === "number") state.ground.scaleY = scene_.ground.scaleY;
    if (typeof scene_.ground.relief === "number") state.ground.relief = scene_.ground.relief;
    if (Array.isArray(scene_.ground.offset)) state.ground.offset = scene_.ground.offset.slice(0, 2);
    if (typeof scene_.ground.rotation === "number") state.ground.rotation = scene_.ground.rotation;
    syncGroundControls();
  }
  if (scene_.layers) state.layers = Object.assign({}, state.layers, scene_.layers);
  if (scene_.appearance) state.appearance = Object.assign({}, scene_.appearance);

  const study = record.study || control("study-select").value;
  if (study) control("study-select").value = study;
  const loaded = await loadStudy(study);
  if (loaded === false) {
    showBanner("The scene's study would not load: " + (state.lastRefusal || ""), "error");
    return false;
  }

  // Props: cleared and replaced rather than merged, because a scene is a
  // whole picture. placeProp with save=false keeps the per-study layout in
  // localStorage untouched until the user moves one themselves.
  if (Array.isArray(scene_.props)) {
    for (const existing of state.props) {
      disposeProp(existing.object);
      propsGroup.remove(existing.object);
    }
    state.props = [];
    state.selectedProp = null;
    adoptLayers(scene_.propLayers);
    // Every model the scene stands on, loaded before any is placed: the
    // library is lazy now, and a scene that placed only what happened to
    // be resident would come back missing furniture.
    await Promise.all([...new Set(scene_.props.map((entry) => entry.type))]
      .filter((type) => propLibraryEntry(type))
      .map((type) => ensurePropTemplate(type)));
    for (const entry of scene_.props) {
      if (!knownPropType(entry.type)) continue;
      const record = placeProp(entry.type, +entry.x || 0, +entry.y || 0,
        +entry.rotation || 0, false, +entry.scale || 1);
      record.layer = +entry.layer || 1;
    }
    applyLayerVisibility();
  }

  // The environment owns background, fog, exposure base and the sun's
  // defaults, so it goes before the sun and before the grade.
  if (scene_.environmentMode) state.environmentMode = scene_.environmentMode;
  if (scene_.weatherPreset) state.weatherPreset = scene_.weatherPreset;
  control("environment-mode").value = state.environmentMode;
  control("weather-preset").value = state.weatherPreset;
  if (typeof scene_.backgroundTone === "number") {
    control("background-tone").value = scene_.backgroundTone;
  }
  if (typeof scene_.brightness === "number") {
    state.brightness = scene_.brightness; control("brightness").value = scene_.brightness;
  }
  if (typeof scene_.contrast === "number") {
    state.contrast = scene_.contrast; control("contrast").value = scene_.contrast;
  }
  const hdri = scene_.hdri || {};
  if (hdri.projection) {
    state.hdriProjection = hdri.projection; control("hdri-projection").value = hdri.projection;
  }
  for (const [key, id] of [["scale", "hdri-scale"], ["height", "hdri-height"],
                           ["rotation", "hdri-rotation"]]) {
    if (typeof hdri[key] === "number") {
      state["hdri" + key[0].toUpperCase() + key.slice(1)] = hdri[key];
      control(id).value = hdri[key];
    }
  }
  if (state.environmentMode === "hdri" && hdri.name && state.hdriName !== hdri.name) {
    // loadHdri stamps the sun sliders from the photograph, which is why the
    // sun is restored after it, below.
    await refreshHdriList(hdri.name);
    await loadHdri(hdri.name);
  }
  applyEnvironment();
  regenerateEnvironment();

  // The sun last of the light, because both the weather preset and an HDRI
  // load write over it. The two overrides are guards that stop a preset
  // writing, not appliers, so the colour and intensity are written here too.
  const sunState = scene_.sun || {};
  if (typeof sunState.azimuth === "number") control("sun-azimuth").value = sunState.azimuth;
  if (typeof sunState.elevation === "number") control("sun-elevation").value = sunState.elevation;
  if (typeof sunState.elevationSetting === "number") {
    state.sunElevationSetting = sunState.elevationSetting;
  }
  state.sunColourOverride = sunState.colourOverride || null;
  state.sunIntensityOverride = typeof sunState.intensityOverride === "number"
    ? sunState.intensityOverride : null;
  if (sunState.colour) {
    control("sun-colour").value = sunState.colour;
    sun.color.set(sunState.colour);
  }
  if (typeof sunState.intensity === "number") sun.intensity = sunState.intensity;
  applySunFromSliders();
  applyGrade();

  // The scene's own instant, through the scene-only applier: applyTimeline
  // would fling the camera onto its orbit ring, and the camera is the point
  // of a saved scene.
  if (scene_.timeline && state.timeline) {
    for (const [key, id] of [["speed", "timeline-speed"],
                             ["orbitSpeed", "orbit-speed"]]) {
      if (typeof scene_.timeline[key] === "number") {
        state.timeline[key] = scene_.timeline[key];
        control(id).value = scene_.timeline[key];
      }
    }
    state.timeline.playing = false;
    paintPlayButtons("Play");
    const t = Math.min(timelineDuration(),
      Math.max(0, +scene_.timeline.t || 0));
    applySceneAtTime(t);
    // The module's own handle, not getElementById("scrubber"): the element's
    // id is "timeline-scrubber", so that lookup returned null and restoring
    // a scene died on it with "Cannot set properties of null". The static
    // test below now checks every id the script asks for against the page.
    scrubber.value =
      Math.round(1000 * (timelineDuration() ? t / timelineDuration() : 0));
  }
  if (scene_.showMode) { state.showMode = scene_.showMode; paintShowButtons(); }
  if (state.timeline) applySceneAtTime(state.timeline.t);
  rebuildAppearance();
  syncAppearanceControls();
  buildLayerToggles();
  updateVectorLayers();

  // The camera last, and then held: the build clock drives its own orbit
  // (applyTimeline's autoSpin), which would throw a restored framing away
  // the moment Play was pressed. A saved scene is a framing somebody chose,
  // so playing it keeps that framing. A study loaded fresh still starts on
  // the orbit, exactly as it always has.
  const view = scene_.camera;
  if (view && typeof view.fov === "number") {
    camera.fov = view.fov;
    camera.updateProjectionMatrix();
  }
  if (view && typeof view.frame === "string") {
    state.cameraAspect = view.frame;
    applyCameraAspect();
  }
  if (view && Array.isArray(view.position) && Array.isArray(view.target)) {
    camera.position.fromArray(view.position);
    controls.target.fromArray(view.target);
    controls.update();
    // No need to disable the orbit any more: a take now starts from
    // wherever the camera is, so playing a restored scene orbits from the
    // framing it was saved at rather than from a ring of its own.
    if (state.timeline) state.timeline.orbitBase = null;
  }
  // Everything above wrote controls silently; give them their faces back
  // (segments, picker names and swatches, the ground dials).
  repaintSettingControls();
  logStudio("restored scene " + (record.name || "the last view"));
  rememberSession();
  return true;
}

// ---------- the studio opens where it was left ----------
// The same record a saved scene carries, kept for the last thing on screen
// rather than for a name the user chose: the vault, the framing, the floor,
// the light and the cut. Param asked for it in those words, "remember the
// last vault that was selected and shown, and the same view and scene too".
//
// In browser storage rather than beside the scenes on disk, deliberately.
// This is a per-window convenience, not a document: two windows open on two
// vaults should each reopen on their own, and it must never appear in the
// scene picker as a scene nobody saved.
const SESSION_KEY = "bench-studio-session";

function rememberSession() {
  if (!state.bundle) return;
  const study = document.getElementById("study-select").value;
  if (!study) return;
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      study, state: collectScene(), when: new Date().toISOString(),
    }));
  } catch (error) { /* a full or blocked store is not worth a banner */ }
}

function rememberedSession() {
  try {
    const stored = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    if (stored && typeof stored.study === "string" && stored.state) return stored;
  } catch (error) { /* corrupt entry: open as if there were none */ }
  return null;
}

// Written when the window goes away and whenever the view settles, so a
// crash or a killed server loses at most the last camera move.
window.addEventListener("beforeunload", rememberSession);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") rememberSession();
});

async function refreshScenes() {
  const payload = await fetchJson("/api/scenes");
  state.scenes = payload.scenes || [];
  renderSceneList();
}

function renderSceneList() {
  const list = document.getElementById("scene-list");
  if (!list) return;
  list.innerHTML = "";
  if (!state.scenes.length) {
    const empty = document.createElement("div");
    empty.className = "scene-empty";
    // Named after the button that actually exists (it says Save, not
    // "Save scene"), in the same lowercase register as the other empties.
    empty.textContent = "no saved scenes yet -- frame a view and press Save";
    list.appendChild(empty);
    return;
  }
  const current = document.getElementById("study-select").value;
  for (const row of state.scenes) {
    const tile = document.createElement("button");
    tile.className = "scene-tile";
    tile.title = row.unreadable
      ? "This scene file is damaged and cannot be restored"
      : "Restore " + row.name;
    if (row.thumbnail) {
      const image = document.createElement("img");
      image.src = "/api/scenes/" + encodeURIComponent(row.id) + "/thumbnail";
      image.alt = "";
      tile.appendChild(image);
    }
    const name = document.createElement("span");
    name.className = "scene-name";
    name.textContent = row.name;
    tile.appendChild(name);
    const study = document.createElement("span");
    study.className = "scene-study";
    // A scene carries its study, and restoring one saved on a DIFFERENT
    // study loads that study first. Saying so on the tile is the difference
    // between a deliberate switch and a surprise.
    if (row.unreadable) {
      study.textContent = "damaged";
      study.classList.add("scene-elsewhere");
    } else if (row.study && row.study !== current) {
      study.textContent = "loads " + row.study;
      study.classList.add("scene-elsewhere");
    } else {
      study.textContent = row.study || "";
    }
    tile.appendChild(study);
    tile.addEventListener("click", async () => {
      if (row.unreadable) {
        showBanner("That scene file is damaged; delete it and save a new one", "error");
        return;
      }
      try {
        await applyScene(await fetchJson("/api/scenes/" + encodeURIComponent(row.id)));
      } catch (error) {
        showBanner("Could not restore that scene: " + error.message, "error");
      }
    });
    const remove = document.createElement("button");
    remove.className = "scene-delete";
    // The same glyph the banner close uses: a letter x sits on the text
    // baseline, low and left in an 18px square, where this one centres.
    remove.textContent = "✕";
    remove.title = "Delete this scene";
    remove.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (!window.confirm("Delete the scene \"" + row.name + "\"?")) return;
      await fetch("/api/scenes/" + encodeURIComponent(row.id), { method: "DELETE" });
      logStudio("deleted scene " + row.name);
      await refreshScenes();
    });
    const holder = document.createElement("div");
    holder.style.position = "relative";
    holder.appendChild(tile);
    holder.appendChild(remove);
    list.appendChild(holder);
  }
}

document.getElementById("scene-save").addEventListener("click", async () => {
  if (!state.bundle) {
    showBanner("Load a study before saving a scene", "error");
    return;
  }
  const study = document.getElementById("study-select").value;
  const suggested = study + " " + new Date().toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit",
  });
  const name = window.prompt("Name this scene", suggested);
  if (!name) return;
  const thumbnail = captureThumbnail();
  const response = await fetch("/api/scenes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, study, state: collectScene(), thumbnail }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    showBanner("Scene not saved: " + (body.detail || response.status), "error");
    return;
  }
  logStudio("saved scene " + name);
  await refreshScenes();
});

// The scene list opens from the shelf's Scenes tab now; refreshScenes is
// called by renderShelf when that drawer shows.

// ---------- the sun ----------
// One instrument in place of three sliders and a colour picker. The site
// and the instant are the real variables; azimuth, elevation, colour and
// strength all follow from them, and the widget draws what follows rather
// than asking for it.
//
// The site defaults to London because the studio is in Wales and the vault
// work is British; it is a state field, so a location control can be added
// later without touching any of this.
const SUN_SITE = { latitude: 51.507, longitude: -0.1278, northOffset: 0 };

function sunDay() {
  // The day the sun is being placed on. A date control can be added later;
  // for now it is today, taken once at load so a take is not interrupted by
  // midnight.
  return state.sunDay;
}

function minutesToDate(minutes) {
  const day = sunDay();
  return new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(),
    day.getUTCDate(), 0, 0, 0) + Math.round(minutes * 60000));
}

function currentSun() {
  return sunPosition(minutesToDate(state.sunMinutes),
    SUN_SITE.latitude, SUN_SITE.longitude, SUN_SITE.northOffset);
}

// The one place the scene learns what the sun is doing. Everything else
// asks for a time, not for an angle.
function applySunFromTime() {
  const placed = currentSun();
  const light = sunLight(placed.elevation);
  // The scene's angle is not the compass bearing. applySunAt measures from
  // +X counterclockwise, the survey convention puts north at +Y and east at
  // +X, so a compass bearing A points along (sin A, cos A) and the scene
  // angle is 90 - A. Everything that still speaks in scene angles (the sky,
  // the HDRI estimate) keeps reading the hidden input, which holds that.
  const sceneAngle = ((90 - placed.azimuth) % 360 + 360) % 360;
  document.getElementById("sun-azimuth").value = Math.round(sceneAngle);
  document.getElementById("sun-elevation").value =
    Math.round(Math.max(0, placed.elevation));
  const colour = new THREE.Color(light.colour);
  if (!state.sunColourOverride) sun.color.copy(colour);
  document.getElementById("sun-colour").value = "#" + colour.getHexString();
  // Strength is the ramp's own figure relative to full sun, and the floor
  // keeps a night scene lit by something rather than going black.
  if (state.sunIntensityOverride === null) {
    sun.intensity = 0.35 + 2.9 * light.strength;
  }
  applySunAt(sceneAngle, Math.max(-2, placed.elevation));
  paintSunWidget();
  paintDayTrack();
}

// ---------- drawing the instrument ----------
function paintSunWidget() {
  const canvasEl = document.getElementById("sun-dial");
  if (!canvasEl) return;
  const context = canvasEl.getContext("2d");
  const width = canvasEl.width, height = canvasEl.height;
  const placed = currentSun();
  const light = sunLight(placed.elevation);
  const colour = "#" + new THREE.Color(light.colour).getHexString();
  context.clearRect(0, 0, width, height);

  // Both halves are measured off the canvas rather than written down, so
  // the instrument fits whatever width the panel gives it. It has been
  // 276 wide, then 186, then 234; the constants never followed.
  const half = width / 2;
  const pad = 14;
  const cx = half / 2, cy = height / 2;
  const radius = Math.min(half, height) / 2 - pad;
  context.strokeStyle = "#262a30";
  context.lineWidth = 3;
  context.beginPath();
  context.arc(cx, cy, radius, 0, Math.PI * 2);
  context.stroke();
  context.strokeStyle = "#3c4048";
  context.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const angle = i * Math.PI / 2;
    context.beginPath();
    context.moveTo(cx + Math.sin(angle) * (radius - 5), cy - Math.cos(angle) * (radius - 5));
    context.lineTo(cx + Math.sin(angle) * (radius + 5), cy - Math.cos(angle) * (radius + 5));
    context.stroke();
  }
  context.fillStyle = "#6b7078";
  context.textAlign = "center";
  context.font = "9px system-ui, sans-serif";
  context.fillText("N", cx, cy - radius - 9);
  const bearing = placed.azimuth * Math.PI / 180;
  const handX = cx + Math.sin(bearing) * radius;
  const handY = cy - Math.cos(bearing) * radius;
  context.strokeStyle = "#40454d";
  context.beginPath();
  context.moveTo(cx, cy);
  context.lineTo(handX, handY);
  context.stroke();
  context.globalAlpha = placed.elevation > 0 ? 1 : 0.4;
  context.fillStyle = colour;
  context.beginPath();
  context.arc(handX, handY, 6.5, 0, Math.PI * 2);
  context.fill();
  context.globalAlpha = 1;
  context.strokeStyle = "rgba(0,0,0,0.5)";
  context.stroke();

  // The arc: how high, with the horizon drawn so a set sun is visibly below
  // the line rather than merely a small number.
  // The arc's origin is the bottom-left of the right half, and its radius
  // is whatever fits between there and the two edges.
  const ax = half + pad;
  const base = height - pad;
  const span = Math.min(half - pad * 2, height - pad * 2);
  context.strokeStyle = "#262a30";
  context.lineWidth = 3;
  context.beginPath();
  context.arc(ax, base, span, -Math.PI / 2, 0);
  context.stroke();
  context.strokeStyle = "#3c4048";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(ax - 8, base);
  context.lineTo(ax + span + 8, base);
  context.stroke();
  const clamped = Math.max(-6, Math.min(90, placed.elevation));
  const arc = (clamped / 90) * (Math.PI / 2);
  const ex = ax + Math.cos(arc) * span;
  const ey = base - Math.sin(arc) * span;
  context.globalAlpha = placed.elevation > 0 ? 1 : 0.4;
  context.fillStyle = colour;
  context.beginPath();
  context.arc(ex, ey, 6.5, 0, Math.PI * 2);
  context.fill();
  context.globalAlpha = 1;
  context.strokeStyle = "rgba(0,0,0,0.5)";
  context.stroke();

  const hours = Math.floor(state.sunMinutes / 60) % 24;
  const minutes = Math.round(state.sunMinutes % 60);
  document.getElementById("sun-time").textContent =
    String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  // Degrees, said as degrees. "286 / -4" beside a clock reading 19:01 ran
  // together into "19:01286 / -4" the moment the block was narrow.
  document.getElementById("sun-angles").textContent =
    Math.round(placed.azimuth) + "\u00b0 az  "
    + Math.round(placed.elevation) + "\u00b0 alt";
}

// The day track carries its own legend: the sky colour the model produces
// at each hour is painted into it, so golden hour is a place on the bar
// rather than a number to remember.
// Twenty-five solar positions and a gradient is too much to redraw sixty
// times a second while a day cycle runs, and the sky it paints only changes
// when the day or the site does. So the band is baked once into its own
// canvas and the handle is drawn over it.
let dayTrackBand = null;
let dayTrackKey = null;

function paintDayTrack() {
  const canvasEl = document.getElementById("day-track");
  if (!canvasEl) return;
  const context = canvasEl.getContext("2d");
  const width = canvasEl.width, height = canvasEl.height;
  const key = sunDay().toDateString() + SUN_SITE.latitude + SUN_SITE.longitude;
  if (dayTrackKey === key && dayTrackBand) {
    context.clearRect(0, 0, width, height);
    context.drawImage(dayTrackBand, 0, 0);
    drawDayHandle(context, width, height);
    return;
  }
  const gradient = context.createLinearGradient(0, 0, width, 0);
  for (let stop = 0; stop <= 24; stop += 1) {
    const placed = sunPosition(minutesToDate(stop * 60),
      SUN_SITE.latitude, SUN_SITE.longitude, SUN_SITE.northOffset);
    const light = sunLight(placed.elevation);
    const day = new THREE.Color(light.colour);
    // Night is the sky, not the sun: below the horizon the track fades to
    // the deep blue a scene actually reads as at that hour.
    const night = new THREE.Color(0x0a0d1a);
    const mix = Math.max(0, Math.min(1, (placed.elevation + 6) / 8));
    day.lerp(night, 1 - mix);
    gradient.addColorStop(stop / 24, "#" + day.getHexString());
  }
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "rgba(255,255,255,0.22)";
  context.lineWidth = 1;
  for (const hour of [6, 12, 18]) {
    const x = Math.round((hour / 24) * width) + 0.5;
    context.beginPath();
    context.moveTo(x, 6);
    context.lineTo(x, height - 6);
    context.stroke();
  }
  dayTrackBand = document.createElement("canvas");
  dayTrackBand.width = width;
  dayTrackBand.height = height;
  dayTrackBand.getContext("2d").drawImage(canvasEl, 0, 0);
  dayTrackKey = key;
  drawDayHandle(context, width, height);
}

function drawDayHandle(context, width, height) {
  const handle = (state.sunMinutes / 1440) * width;
  context.fillStyle = "#f2f3f5";
  context.strokeStyle = "rgba(0,0,0,0.45)";
  context.beginPath();
  context.roundRect(Math.max(0, Math.min(width - 6, handle - 3)), -2, 6, height + 4, 3);
  context.fill();
  context.stroke();
}

// ---------- driving it ----------
function setSunMinutes(minutes) {
  state.sunMinutes = Math.max(0, Math.min(1439, minutes));
  applySunFromTime();
  regenerateEnvironment();
  paintGroupSummaries();
}




function dragSunDial(event) {
  const canvasEl = document.getElementById("sun-dial");
  const rect = canvasEl.getBoundingClientRect();
  const scale = canvasEl.width / rect.width;
  const x = (event.clientX - rect.left) * scale;
  const y = (event.clientY - rect.top) * scale;
  // The compass sets the TIME, because time is the real variable: the
  // bearing the user asks for is searched over the day and the nearest
  // instant that produces it wins. Dragging the sun therefore moves the
  // clock, and the elevation follows from the date and the site rather
  // than being invented.
  const wanted = (Math.atan2(x - 74, 76 - y) * 180 / Math.PI + 360) % 360;
  let best = state.sunMinutes, closest = 999;
  for (let m = 0; m < 1440; m += 2) {
    const placed = sunPosition(minutesToDate(m), SUN_SITE.latitude, SUN_SITE.longitude,
      SUN_SITE.northOffset);
    let delta = Math.abs(((placed.azimuth - wanted + 540) % 360) - 180);
    if (delta < closest) { closest = delta; best = m; }
  }
  setSunMinutes(best);
}

// What each folded group says about itself. Every one of these reads scene
// state, which is why the table lives here and is handed to the panel
// machinery rather than living beside it.
const GROUP_SUMMARIES = {
  "Ground": () => {
    const select = document.getElementById("ground-preset");
    const label = select.options[select.selectedIndex];
    return (label ? label.textContent : "") + ", " + state.groundRadius + " m";
  },
  "Environment": () => {
    const select = document.getElementById("environment-mode");
    const label = select.options[select.selectedIndex];
    return label ? label.textContent : "";
  },
  "Sun": () => {
    const hours = Math.floor(state.sunMinutes / 60) % 24;
    const minutes = Math.round(state.sunMinutes % 60);
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0")
  ;
  },
  "Props": () => state.props.length
    ? state.props.length + " placed" : "none placed",
  "Scenes": () => state.scenes.length ? state.scenes.length + " saved" : "none saved",
  "Image": () => state.brightness.toFixed(2) + " / "
    + (state.contrast >= 0 ? "+" : "") + state.contrast.toFixed(2),
};

setGroupSummaries(GROUP_SUMMARIES);

// ---------- the tab rail ----------
// One section on show at a time, chosen from the buttons on the viewport.
// The panel keeps its permanent header (theme, build stamp) and footer
// (views, restart); the middle is whichever tab is lit. The choice is a
// per-browser convenience, so localStorage, with Skin as the first-run
// home: it is where the daily work starts once a vault folder is set.
function activateTab(sectionId) {
  let known = false;
  for (const button of document.querySelectorAll("#tab-rail button")) {
    if (button.dataset.section === sectionId) known = true;
  }
  if (!known) sectionId = "study-section";
  for (const button of document.querySelectorAll("#tab-rail button")) {
    const active = button.dataset.section === sectionId;
    button.classList.toggle("active", active);
    const section = document.getElementById(button.dataset.section);
    if (!section) continue;
    section.classList.toggle("hidden", !active);
    if (active) section.open = true;
  }
  try {
    localStorage.setItem("vaulted-tab", sectionId);
  } catch (error) {
    /* a private window is not a reason to refuse a tab */
  }
}

{
  for (const button of document.querySelectorAll("#tab-rail button")) {
    button.addEventListener("click", () => activateTab(button.dataset.section));
  }
  let remembered = null;
  try {
    remembered = localStorage.getItem("vaulted-tab");
  } catch (error) { remembered = null; }
  activateTab(remembered || "study-section");
}

// ---------- light or dark ----------
// Nine variables, because the panel's colours all come from the token block
// now. Before the Spectrum pass this would have been thirty hexes found by
// hand and half of them missed.
function applyTheme(theme) {
  const light = theme === "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
  const button = document.getElementById("theme-toggle");
  // The button names what it will DO, not what is on, which is the one
  // choice that stops a toggle being ambiguous in a screenshot.
  if (button) button.textContent = light ? "Dark" : "Light";
  try {
    localStorage.setItem("bench-studio-theme", light ? "light" : "dark");
  } catch (error) {
    /* a private window is not a reason to refuse a theme */
  }
}

{
  let remembered = null;
  try {
    remembered = localStorage.getItem("bench-studio-theme");
  } catch (error) { remembered = null; }
  applyTheme(remembered === "light" ? "light" : "dark");
  const button = document.getElementById("theme-toggle");
  if (button) {
    button.addEventListener("click", () => {
      applyTheme(document.documentElement.dataset.theme === "light"
        ? "dark" : "light");
    });
  }
}

// ---------- the material library ----------
// Loaded sets, most recently used last. Small on purpose: a set is four
// textures at 1024 square with mipmaps, about 21 MB of video memory, and
// nothing in this studio looks at more than one or two at a time. Eviction
// DISPOSES, unlike the QS plugin's caches, because a WebGL texture is not
// reclaimed by dropping a reference the way a GDI+ bitmap is.
const LIBRARY_CACHE_LIMIT = 6;
const libraryCache = new Map();
const libraryLoads = new Map();     // key -> in-flight promise, so a double
                                    // click does not fetch the set twice

function libraryEntry(key) {
  return state.materialLibrary.find((entry) => entry.key === key) || null;
}

// The ground has its own curated library (Param: two folders, one for the
// skin and one for the ground), so its lookups go to its own list.
function groundLibraryEntry(key) {
  return state.groundLibrary.find((entry) => entry.key === key) || null;
}

function isLibraryKey(key) {
  return typeof key === "string" && key.includes("/");
}

async function ensureLibraryMaterial(key) {
  if (libraryCache.has(key)) {
    // Touch it: a Map keeps insertion order, so deleting and re-setting is
    // what makes this least-recently-used rather than first-in-first-out.
    const set = libraryCache.get(key);
    libraryCache.delete(key);
    libraryCache.set(key, set);
    return set;
  }
  if (libraryLoads.has(key)) return libraryLoads.get(key);
  const entry = libraryEntry(key);
  if (!entry) return null;
  const done = beginLoading("Loading " + (entry.label || "material"));
  const loading = loadLibraryMaterial(entry, {
    px: VIEWPORT_PX,
    // The most the hardware offers rather than a number chosen to be safe.
    // A vault is looked at from underneath, which is every texture's worst
    // angle, and anisotropy is the only thing that answers it.
    anisotropy: renderer.capabilities.getMaxAnisotropy(),
    relief: state.relief,
    occlusion: state.occlusion,
  }).then((set) => {
    libraryCache.set(key, set);
    while (libraryCache.size > LIBRARY_CACHE_LIMIT) {
      const oldest = libraryCache.keys().next().value;
      if (oldest === key || oldest === state.appearance.skin) break;
      disposeLibraryMaterial(libraryCache.get(oldest));
      libraryCache.delete(oldest);
    }
    return set;
  }).catch((error) => {
    logStudio("material " + key + " would not load: " + error.message);
    return null;
  }).finally(() => { libraryLoads.delete(key); done(); });
  libraryLoads.set(key, loading);
  return loading;
}

// ---------- the weight system ----------
// The first material dropdown is gone from the panel on Param's word: "the
// logic for that is that it calculates weight of the material... automated
// calculation worth setting up with the thickness of material plus the type
// of material." The type now comes from the chosen SKIN, the weight from a
// density table, and the sprayed distinction from the Pattern control.
//
// Densities in kg/m3. Family first, then name keywords refine the ones
// where the family is not one substance: there are different metals and
// different concretes, as he said. Values are the standard ones (BS EN
// 1991-1-1 territory), with the structural seven mirroring staging.py so
// the display never disagrees with the analysis' own self-weight.
const STRUCTURAL_DENSITIES = {
  concrete: 2400, "concrete-c50": 2400, "concrete-sprayed": 2300,
  timber: 385, brick: 1900, tile: 1800, stone: 2500,
};
const FAMILY_DENSITIES = {
  concrete: 2400, brick: 1900, clay: 1900, stone: 2400, timber: 500,
  plaster: 850, paint: 2400, slate: 2800, metal: 7850, aggregate: 1600,
};
const NAME_DENSITIES = [
  [/copper/, 8940], [/aluminium/, 2700], [/steel/, 7850], [/brass/, 8500],
  [/granite/, 2700], [/marble/, 2700], [/limestone/, 2400],
  [/sandstone/, 2300], [/rubble/, 2200], [/travertine/, 2400],
];

function skinDensity() {
  const skin = state.appearance.skin;
  if (isLibraryKey(skin)) {
    const entry = libraryEntry(skin);
    if (entry) {
      for (const [pattern, density] of NAME_DENSITIES) {
        if (pattern.test(entry.name)) return density;
      }
      if (FAMILY_DENSITIES[entry.family]) return FAMILY_DENSITIES[entry.family];
    }
  }
  const structural = document.getElementById("material-select").value;
  return STRUCTURAL_DENSITIES[structural] || 2400;
}

// Which of the server's seven structural materials this skin implies: the
// cut request, friction and the analysis' self-weight all key on it. A
// family with no structural analogue (a metal or plaster FINISH on a
// vault) falls back to concrete; the sprayed variant is chosen by the
// Pattern control, never here.
const FAMILY_TO_STRUCTURAL = {
  brick: "brick", stone: "stone", clay: "tile", timber: "timber",
  concrete: "concrete",
};

function structuralClassFor(skin) {
  if (patternIsMonolithic()) return "concrete-sprayed";
  if (isLibraryKey(skin)) {
    const entry = libraryEntry(skin);
    if (entry && FAMILY_TO_STRUCTURAL[entry.family]) {
      return FAMILY_TO_STRUCTURAL[entry.family];
    }
  }
  return "concrete";
}

function patternIsMonolithic() {
  return document.getElementById("pattern-select").value === "monolithic-bands";
}

// The readout: q = thickness x density x g, live under the thickness
// slider. This is the number a true analysis load runs on, said where the
// thickness is chosen.
function updateWeightNote() {
  const note = document.getElementById("weight-note");
  if (!note) return;
  const density = skinDensity();
  const thickness = state.thickness;
  const kgPerM2 = density * thickness;
  const kNPerM2 = kgPerM2 * 9.80665 / 1000;
  note.textContent = "weight: " + density + " kg/m3 x "
    + Math.round(thickness * 1000) + " mm = "
    + kNPerM2.toFixed(2) + " kN/m2 (" + Math.round(kgPerM2) + " kg/m2)";
}

// The size of one repeat, in metres, for whatever the vault is wearing.
// Null when it is not wearing a library material at all, which is what
// keeps the old hand-tuned 0.15 in force for the procedural skins.
function activeTileMetres() {
  if (!isLibraryKey(state.appearance.skin)) return null;
  const entry = libraryEntry(state.appearance.skin);
  if (!entry) return null;
  return entry.tileMetres || [DEFAULT_TILE_METRES, DEFAULT_TILE_METRES];
}

async function refreshMaterialLibrary() {
  let payload = null;
  try {
    payload = await fetchJson("/api/materials");
  } catch (error) {
    return;                         // no library chosen, the skins stand
  }
  state.materialLibrary = payload.materials || [];
  state.materialRoot = payload.root || "";
  const select = document.getElementById("render-skin");
  // The four built-in skins keep their places at the top: they need no
  // folder and they are what a study looks like before anybody chooses.
  for (const option of Array.from(select.options)) {
    if (isLibraryKey(option.value)) option.remove();
  }
  for (const entry of state.materialLibrary) {
    const option = document.createElement("option");
    option.value = entry.key;
    option.textContent = entry.label;
    select.appendChild(option);
  }
  // A remembered choice that survived a folder change is honoured; one
  // whose material has gone falls back rather than showing nothing.
  if (isLibraryKey(state.appearance.skin)) {
    if (libraryEntry(state.appearance.skin)) {
      select.value = state.appearance.skin;
      await ensureLibraryMaterial(state.appearance.skin);
      rebuildAppearance();
    } else {
      logStudio("the remembered material " + state.appearance.skin
        + " is not in this library");
      state.appearance.skin = "none";
      select.value = "none";
    }
  }
  // The ground reads its OWN library, from its own folder. One shared list
  // was how gravel ended up offered as a vault skin and board-marked
  // concrete as a floor.
  try {
    const groundPayload = await fetchJson("/api/ground-materials");
    state.groundLibrary = groundPayload.materials || [];
    state.groundRoot = groundPayload.root || "";
  } catch (error) {
    state.groundLibrary = [];
    state.groundRoot = "";
  }
  const ground = document.getElementById("ground-preset");
  for (const option of Array.from(ground.options)) {
    if (isLibraryKey(option.value)) option.remove();
  }
  for (const entry of state.groundLibrary) {
    const option = document.createElement("option");
    option.value = entry.key;
    option.textContent = entry.label;
    ground.appendChild(option);
  }
  if (isLibraryKey(state.groundPreset)) {
    if (groundLibraryEntry(state.groundPreset)) {
      ground.value = state.groundPreset;
      await loadGroundMaterial(state.groundPreset);
    } else {
      state.groundPreset = "dark-studio";
      ground.value = "dark-studio";
      rebuildGround();
    }
  }
  buildSkinTiles();
  buildGroundTiles();
  // The restore above set the selects without change events; the picker
  // faces need telling (his floor wore pebbles while the picker still
  // said Dark studio).
  repaintSettingControls();
  logStudio("material library: " + state.materialLibrary.length
    + " skin materials, " + state.groundLibrary.length + " ground materials");
}

// ---------- pickers ----------
// A tile grid is a choice, so it stays shut until it is wanted, and the
// trigger carries what is currently chosen: a small round preview and the
// name. This is the dropdown Param asked for, without giving up the
// picture that made the tiles worth having.
function wirePicker(triggerId, holderId, selectId, paint, openInstead) {
  const trigger = document.getElementById(triggerId);
  const holder = document.getElementById(holderId);
  const select = document.getElementById(selectId);
  if (!trigger || !holder || !select) return;
  // A grid big enough to need a search box gets one, named after the grid
  // it filters, and it opens and shuts with it. Only the material library
  // has one today; the others are four tiles and a search field over four
  // tiles is furniture.
  const search = document.getElementById(holderId.replace("-tiles", "-search"));
  trigger.addEventListener("click", () => {
    // An asset picker opens the shelf; the inline grid never shows again
    // but keeps being painted, because the trigger's swatch borrows its
    // tiles.
    if (openInstead) { openInstead(); return; }
    const opening = holder.classList.contains("hidden");
    holder.classList.toggle("hidden", !opening);
    trigger.classList.toggle("open", opening);
    if (search) {
      search.classList.toggle("hidden", !opening);
      if (opening) search.focus();
    }
  });
  select.addEventListener("change", () => paintPicker(triggerId, selectId, paint));
  paintPicker(triggerId, selectId, paint);
}

function paintPicker(triggerId, selectId, paint) {
  const trigger = document.getElementById(triggerId);
  const select = document.getElementById(selectId);
  if (!trigger || !select) return;
  const chosen = select.options[select.selectedIndex];
  const name = trigger.querySelector(".chosen-name");
  if (name && chosen) name.textContent = chosen.textContent;
  const swatch = trigger.querySelector(".chosen-swatch");
  if (swatch && paint) paint(swatch, select.value);
}

// The trigger's own little preview: a canvas would be another context to
// keep, so it borrows the tile that is already drawn for the same value.
function borrowTileImage(swatch, holderId, value) {
  const tile = document.querySelector(
    "#" + holderId + ' .tile[data-value="' + CSS.escape(value) + '"]');
  const source = tile && (tile.querySelector("canvas") || tile.querySelector("img"));
  if (!source) return;
  swatch.style.backgroundImage = "url(" + (source.tagName === "IMG"
    ? source.src : source.toDataURL()) + ")";
  swatch.style.backgroundSize = "cover";
  swatch.style.backgroundPosition = "center";
}

function wireAllPickers() {
  // The asset pickers open the SHELF now: the inline grids stay built
  // and hidden purely so the trigger swatches have tiles to borrow.
  for (const [trigger, holder, select, openInstead] of [
    ["material-picker", "material-tiles", "material-select"],
    ["skin-picker", "skin-tiles", "render-skin", () => openShelf("materials")],
    ["ground-picker", "ground-tiles", "ground-preset", () => openShelf("materials")],
    ["weather-picker", "weather-tiles", "weather-preset"],
    ["hdri-picker", "hdri-tiles", "hdri-select", () => openShelf("skies")],
  ]) {
    wirePicker(trigger, holder, select,
      (swatch, value) => borrowTileImage(swatch, holder, value), openInstead);
  }
}

// ---------- the camera menu ----------
// FOV with its lens equivalent, the frame ratio, and the grade -- the
// things that belong to the LENS rather than the scene (Param: "a camera
// menu on the top right... FOV, mm lens, move the brightness and
// contrast there. Some preset screen ratios, this also needs to all be
// picked up by the animation recording").

// Full-frame vertical equivalence: three.js fov is the VERTICAL angle
// and a 35mm frame is 24mm tall, so f = 12 / tan(fov/2). A 27 degree
// vertical view reads 50mm, exactly as the photography tables have it.
function lensMillimetres(fov) {
  return Math.max(1, Math.round(12 / Math.tan((fov * Math.PI / 180) / 2)));
}

function syncCameraControls() {
  const fov = Math.round(camera.fov);
  document.getElementById("camera-fov").value = fov;
  document.getElementById("camera-fov-value").textContent = fov;
  document.getElementById("camera-mm").textContent = lensMillimetres(camera.fov);
  document.getElementById("camera-aspect").value = state.cameraAspect;
  paintSegmented("camera-aspect-segments", "camera-aspect");
}

// The letterbox is nothing but CSS on the canvas: resize() reads the
// canvas's own box every frame and sets the renderer, the composer and
// camera.aspect from it, so constraining the box constrains everything.
function applyCameraAspect() {
  if (state.cameraAspect === "fill") {
    canvas.style.left = ""; canvas.style.top = "";
    canvas.style.width = ""; canvas.style.height = "";
    return;
  }
  const ratio = +state.cameraAspect;
  const maxW = window.innerWidth, maxH = window.innerHeight;
  let w = maxW, h = Math.round(maxW / ratio);
  if (h > maxH) { h = maxH; w = Math.round(maxH * ratio); }
  canvas.style.left = Math.round((maxW - w) / 2) + "px";
  canvas.style.top = Math.round((maxH - h) / 2) + "px";
  canvas.style.width = w + "px";
  canvas.style.height = h + "px";
}

// What the recorder renders at: the chosen frame, longest side 1920,
// dimensions kept even for the encoder. Fill records the classic 1080p.
function recordingFrame() {
  if (state.cameraAspect === "fill") return { width: 1920, height: 1080 };
  const ratio = +state.cameraAspect;
  const even = (n) => Math.max(2, 2 * Math.round(n / 2));
  return ratio >= 1
    ? { width: 1920, height: even(1920 / ratio) }
    : { width: even(1920 * ratio), height: 1920 };
}

document.getElementById("camera-fov").addEventListener("input", (e) => {
  camera.fov = +e.target.value;
  camera.updateProjectionMatrix();
  document.getElementById("camera-fov-value").textContent = e.target.value;
  document.getElementById("camera-mm").textContent = lensMillimetres(camera.fov);
});
document.getElementById("camera-fov").addEventListener("change", () => {
  rememberSession();
});
document.getElementById("camera-aspect").addEventListener("change", (e) => {
  state.cameraAspect = e.target.value;
  applyCameraAspect();
  paintSegmented("camera-aspect-segments", "camera-aspect");
  rememberSession();
});
window.addEventListener("resize", applyCameraAspect);

// The scene restore and the library boot write their controls SILENTLY
// on purpose (dispatching change would fire six overlapping server
// cuts), so what they wrote has to be repainted by hand. Everything in
// here is render-only: segment highlights, picker faces, slider
// readouts. Param: "the menu needs to stay tuned to the settings
// already applied instead of starting fresh" -- the settings WERE
// applied; only their faces had gone stale.
function repaintSettingControls() {
  paintSegmented("environment-segments", "environment-mode");
  for (const [trigger, holder, select] of [
    ["material-picker", "material-tiles", "material-select"],
    ["skin-picker", "skin-tiles", "render-skin"],
    ["ground-picker", "ground-tiles", "ground-preset"],
    ["weather-picker", "weather-tiles", "weather-preset"],
    ["hdri-picker", "hdri-tiles", "hdri-select"],
  ]) {
    paintPicker(trigger, select,
      (swatch, value) => borrowTileImage(swatch, holder, value));
  }
  syncGroundControls();
  syncAppearanceControls();
  syncCameraControls();
}

// ---------- the shelf ----------
// The bottom asset drawer (Param: "a little tile at the bottom where if
// you click it, it expands... 4 columns a row, more space to breathe,
// scroll around it, give it categories"). Three kinds share one body:
// props place on click and the drawer STAYS OPEN (its predecessor's
// worst habit was closing itself); materials select on click and assign
// by button, because one picture can dress either the vault or the
// floor; skies load on click and keep their projection dials beside
// them. The selects underneath remain the source of truth throughout --
// the shelf only ever sets a select and dispatches change.
let shelfKind = null;
let shelfCategory = "all";
let shelfMaterialKey = null;

function openShelf(kind) {
  shelfKind = kind;
  shelfCategory = "all";
  shelfMaterialKey = null;
  document.getElementById("shelf-body").classList.remove("hidden");
  for (const button of document.querySelectorAll("#shelf-tabs button[data-shelf]")) {
    button.classList.toggle("active", button.dataset.shelf === kind);
  }
  renderShelf();
}

function closeShelf() {
  shelfKind = null;
  document.getElementById("shelf-body").classList.add("hidden");
  for (const button of document.querySelectorAll("#shelf-tabs button[data-shelf]")) {
    button.classList.remove("active");
  }
}

function shelfChips(holder, names, chosen, pick) {
  holder.innerHTML = "";
  for (const name of names) {
    const chip = document.createElement("button");
    chip.textContent = name;
    chip.classList.toggle("active", name === chosen);
    chip.addEventListener("click", () => pick(name));
    holder.appendChild(chip);
  }
}

function renderShelf() {
  const cats = document.getElementById("shelf-cats");
  const grid = document.getElementById("shelf-grid");
  const propHolder = document.getElementById("prop-tiles");
  document.getElementById("shelf-sky-settings").classList
    .toggle("hidden", shelfKind !== "skies");
  document.getElementById("shelf-assign-skin").classList
    .toggle("hidden", shelfKind !== "materials");
  document.getElementById("shelf-assign-ground").classList
    .toggle("hidden", shelfKind !== "materials");
  document.getElementById("scene-save").classList
    .toggle("hidden", shelfKind !== "scenes");
  document.getElementById("stamp-group").classList
    .toggle("hidden", shelfKind !== "layers");
  document.getElementById("layer-group").classList
    .toggle("hidden", shelfKind !== "layers");
  document.getElementById("layer-tabs").classList
    .toggle("hidden", shelfKind !== "layers");
  document.getElementById("scene-list").classList
    .toggle("hidden", shelfKind !== "scenes");
  propHolder.classList.toggle("hidden", shelfKind !== "props");
  grid.classList.toggle("hidden",
    shelfKind === "props" || shelfKind === "scenes");
  grid.classList.toggle("wide", shelfKind === "skies");
  document.getElementById("prop-credit").textContent = "";
  if (shelfKind === "props") { renderShelfProps(cats, propHolder); return; }
  if (shelfKind === "materials") { renderShelfMaterials(cats, grid); return; }
  if (shelfKind === "skies") { cats.innerHTML = ""; renderShelfSkies(grid); return; }
  if (shelfKind === "layers") { cats.innerHTML = ""; renderShelfLayers(grid); return; }
  if (shelfKind === "scenes") { cats.innerHTML = ""; refreshScenes(); }
}

// ---------- the Layers drawer ----------
// The same grid the props and materials wear (Param: "move it to the
// props and materials display format with the elements being shown as
// thumbnails and then i can select multiple or unselect them, duplicate
// them, group them"): one tile per placed object on the OPEN layer,
// click to select and unselect several. The layers themselves are tabs
// along the drawer's bottom edge; the open tab is where newly placed
// props land, and its eye hides the whole set.
const gatheredProps = new Set();

function propLabel(record) {
  const entry = (state.propLibrary || []).find((e) => e.key === record.type);
  return entry ? entry.label : record.type;
}

function paintStampButton() {
  const count = [...gatheredProps]
    .filter((record) => state.props.includes(record)).length;
  const stamp = document.getElementById("stamp-group");
  stamp.disabled = !count;
  stamp.textContent = count ? "Place copies of " + count : "Place copies";
  document.getElementById("layer-group").disabled = !count;
}

function renderShelfLayers(grid) {
  grid.innerHTML = "";
  for (const record of [...gatheredProps]) {
    if (!state.props.includes(record)) gatheredProps.delete(record);
  }
  const members = state.props.filter((r) => r.layer === state.activeLayer);
  if (!members.length) {
    const empty = document.createElement("div");
    empty.className = "tile-family";
    empty.textContent = "nothing on this layer yet -- placed props land here";
    grid.appendChild(empty);
  }
  members.forEach((record, index) => {
    const template = propTemplates.get(record.type);
    const tile = previewTile(record.type + "#" + index, propLabel(record),
      (canvasEl) => {
        if (template) renderObjectPreview(template, canvasEl);
      });
    tile.classList.toggle("active", gatheredProps.has(record));
    tile.title = propLabel(record)
      + "  (" + record.x.toFixed(1) + ", " + record.y.toFixed(1) + ")"
      + " -- click to select or unselect";
    tile.addEventListener("click", () => {
      // A tile toggles membership of the working selection; the last one
      // picked is also the viewport's selected object.
      if (gatheredProps.has(record)) {
        gatheredProps.delete(record);
        if (state.selectedProp === record) selectProp(null);
      } else {
        gatheredProps.add(record);
        selectProp(record);
      }
      tile.classList.toggle("active", gatheredProps.has(record));
      paintStampButton();
    });
    grid.appendChild(tile);
  });
  renderLayerTabs();
  paintStampButton();
}

// The tab strip: one tab per layer, a + for a fresh one, and the open
// tab's own eye and cross at the end of the row.
function renderLayerTabs() {
  const strip = document.getElementById("layer-tabs");
  strip.innerHTML = "";
  for (const layer of state.propLayers) {
    const tab = document.createElement("button");
    tab.className = "layer-tab"
      + (layer.id === state.activeLayer ? " active" : "")
      + (layer.visible === false ? " off" : "");
    tab.textContent = layer.name;
    tab.title = "Open this layer: newly placed props land on it. "
      + "Double-click to rename.";
    tab.addEventListener("click", () => {
      state.activeLayer = layer.id;
      gatheredProps.clear();
      renderShelf();
    });
    tab.addEventListener("dblclick", () => {
      const fresh = window.prompt("Rename layer", layer.name);
      if (fresh) { layer.name = fresh; saveProps(); renderShelf(); }
    });
    strip.appendChild(tab);
  }
  const add = document.createElement("button");
  add.className = "layer-tab";
  add.textContent = "+";
  add.title = "New layer";
  add.addEventListener("click", () => {
    newLayer(null);
    gatheredProps.clear();
    saveProps();
    renderShelf();
  });
  strip.appendChild(add);
  const active = layerById(state.activeLayer);
  const eye = document.createElement("button");
  eye.className = "layer-eye";
  eye.textContent = active && active.visible === false ? "Hidden" : "Shown";
  eye.title = "Show or hide everything on the open layer";
  eye.addEventListener("click", () => {
    if (!active) return;
    active.visible = active.visible === false;
    applyLayerVisibility();
    saveProps();
    renderShelf();
  });
  const del = document.createElement("button");
  del.className = "layer-delete";
  del.textContent = "✕";
  del.title = "Delete the open layer and every prop on it";
  del.addEventListener("click", () => deleteLayer(state.activeLayer));
  strip.append(eye, del);
}

// Group: the selected objects move house to a fresh layer of their own,
// staying exactly where they stand.
function groupToNewLayer() {
  const chosen = [...gatheredProps]
    .filter((record) => state.props.includes(record));
  if (!chosen.length) return;
  const home = newLayer(null);
  for (const record of chosen) record.layer = home.id;
  gatheredProps.clear();
  applyLayerVisibility();
  saveProps();
  renderShelf();
  logStudio(chosen.length + " props grouped onto " + home.name);
}

document.getElementById("layer-group").addEventListener("click", groupToNewLayer);

function deleteLayer(id) {
  const layer = layerById(id);
  if (!layer) return;
  const members = state.props.filter((record) => record.layer === id);
  if (members.length
      && !window.confirm("Delete " + layer.name + " and its "
        + members.length + " props?")) {
    return;
  }
  for (const record of members) {
    disposeProp(record.object);
    propsGroup.remove(record.object);
  }
  state.props = state.props.filter((record) => record.layer !== id);
  state.propLayers = state.propLayers.filter((entry) => entry.id !== id);
  if (!state.propLayers.length) {
    state.propLayers = [{ id: 1, name: "Layer 1", visible: true }];
    state.nextLayerId = 2;
  }
  if (!layerById(state.activeLayer)) {
    state.activeLayer = state.propLayers[0].id;
  }
  selectProp(null);
  saveProps();
  renderShelf();
}

// ---------- the stamp ----------
// Ticked objects become one rubber stamp (Param: "i grab 3 random
// objects from the layer tile and then group and duplicate, i can then
// place many of these objects until i click esc then it releases
// them"). The stamp is defs relative to the group's centroid; one live
// instance rides the cursor, every click plants it and spawns the next,
// Escape removes the one in hand and ends the run.
let stampRig = null;

function spawnStampInstance(x, y) {
  stampRig.records = stampRig.defs.map((def) => {
    const record = placeProp(def.type, x + def.dx, y + def.dy,
      def.rotation, false, def.scale);
    return record;
  });
}

function beginStamp() {
  const chosen = [...gatheredProps]
    .filter((record) => state.props.includes(record));
  if (!chosen.length) return;
  let cx = 0, cy = 0;
  for (const record of chosen) { cx += record.x; cy += record.y; }
  cx /= chosen.length; cy /= chosen.length;
  stampRig = {
    defs: chosen.map((record) => ({ type: record.type,
      dx: record.x - cx, dy: record.y - cy,
      rotation: record.rotation, scale: record.scale || 1 })),
    records: [],
    placed: 0,
  };
  spawnStampInstance(cx + 1.5, cy + 1.5);
  controls.enabled = false;
  closeShelf();
  logStudio("stamp of " + stampRig.defs.length
    + ": every click places a copy, escape lets go");
}

function moveStamp(hit) {
  for (let i = 0; i < stampRig.records.length; i++) {
    const def = stampRig.defs[i];
    const record = stampRig.records[i];
    record.x = hit.x + def.dx;
    record.y = hit.y + def.dy;
    record.object.position.set(record.x, record.y, 0);
  }
}

function placeStampInstance(hit) {
  stampRig.placed += 1;
  const planted = stampRig.records.slice();
  pushUndo("placing " + planted.length + (planted.length === 1
    ? " copy" : " copies"), () => {
    for (const record of planted) removePropRecord(record);
  });
  saveProps();
  spawnStampInstance(hit.x, hit.y);
}

function endStamp() {
  // The copy in hand never arrived: it goes, the planted ones stay.
  for (const record of stampRig.records) {
    disposeProp(record.object);
    propsGroup.remove(record.object);
    state.props = state.props.filter((p) => p !== record);
  }
  const planted = stampRig.placed;
  stampRig = null;
  controls.enabled = true;
  saveProps();
  logStudio("stamp released: " + planted
    + (planted === 1 ? " copy" : " copies") + " placed");
}

document.getElementById("stamp-group").addEventListener("click", beginStamp);

function renderShelfProps(cats, holder) {
  const groups = [...new Set(state.propLibrary.map(
    (entry) => entry.group || "other"))].sort();
  shelfChips(cats, ["all", ...groups], shelfCategory, (name) => {
    shelfCategory = name;
    renderShelf();
  });
  for (const child of holder.children) {
    const group = child.dataset.group || "other";
    child.classList.toggle("hidden",
      shelfCategory !== "all" && group !== shelfCategory);
  }
}

function renderShelfMaterials(cats, grid) {
  // ONE browser over BOTH libraries, merged by key: the folders are
  // curated copies of the same QS stack, so "brick/paver-dark" is the
  // same picture wherever it lives, and which library holds it only
  // decides which Assign button lights up.
  const merged = new Map();
  for (const entry of state.materialLibrary || []) {
    merged.set(entry.key, { entry, skin: true, ground: false });
  }
  for (const entry of state.groundLibrary || []) {
    const seen = merged.get(entry.key);
    if (seen) seen.ground = true;
    else merged.set(entry.key, { entry, skin: false, ground: true });
  }
  const rows = [...merged.values()].sort((a, b) =>
    a.entry.family.localeCompare(b.entry.family)
    || a.entry.label.localeCompare(b.entry.label));
  const families = [...new Set(rows.map((row) => row.entry.family))];
  shelfChips(cats, ["all", ...families], shelfCategory, (name) => {
    shelfCategory = name;
    renderShelf();
  });
  grid.innerHTML = "";
  let family = null;
  for (const row of rows) {
    if (shelfCategory !== "all" && row.entry.family !== shelfCategory) continue;
    if (row.entry.family !== family) {
      family = row.entry.family;
      const heading = document.createElement("span");
      heading.className = "tile-family";
      heading.textContent = family;
      grid.appendChild(heading);
    }
    const tile = imageTile(row.entry.key, row.entry.label,
      tileUrl(row.entry, row.skin ? undefined : GROUND_BASE));
    tile.title = row.entry.label
      + (row.entry.tileMetres
        ? "  " + Math.round(row.entry.tileMetres[0] * 1000) + " x "
          + Math.round(row.entry.tileMetres[1] * 1000) + " mm"
        : "")
      + (row.skin && row.ground ? "  (skin + ground)"
        : row.skin ? "  (skin)" : "  (ground)");
    tile.addEventListener("click", () => {
      shelfMaterialKey = row.entry.key;
      paintTileSelection(grid, row.entry.key);
      document.getElementById("shelf-assign-skin").disabled = !row.skin;
      document.getElementById("shelf-assign-ground").disabled = !row.ground;
    });
    grid.appendChild(tile);
  }
  const current = shelfMaterialKey || state.appearance.skin;
  paintTileSelection(grid, current);
  const chosen = merged.get(current);
  document.getElementById("shelf-assign-skin").disabled = !(chosen && chosen.skin);
  document.getElementById("shelf-assign-ground").disabled = !(chosen && chosen.ground);
  if (chosen) shelfMaterialKey = current;
}

function renderShelfSkies(grid) {
  grid.innerHTML = "";
  const select = document.getElementById("hdri-select");
  const names = [...select.options].map((o) => o.value).filter(Boolean);
  for (const name of names) {
    const tile = document.createElement("button");
    tile.className = "tile";
    tile.dataset.value = name;
    tile.title = name;
    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = "/api/hdri/" + encodeURIComponent(name) + "/thumbnail";
    image.alt = "";
    tile.appendChild(image);
    const label = document.createElement("span");
    label.textContent = name.replace(/\.hdr$/i, "").replace(/_(\d+k)$/i, "");
    tile.appendChild(label);
    tile.addEventListener("click", () => {
      // Choosing a sky MEANS looking at it: the environment follows.
      const mode = document.getElementById("environment-mode");
      if (mode.value !== "hdri") {
        mode.value = "hdri";
        mode.dispatchEvent(new Event("change"));
      }
      if (select.value !== name) {
        select.value = name;
        select.dispatchEvent(new Event("change"));
      }
      paintTileSelection(grid, name);
      repaintSettingControls();
    });
    grid.appendChild(tile);
  }
  paintTileSelection(grid, select.value);
}

function assignShelfMaterial(selectId) {
  if (!shelfMaterialKey) return;
  const select = document.getElementById(selectId);
  if (![...select.options].some((o) => o.value === shelfMaterialKey)) {
    logStudio(shelfMaterialKey + " is not in that library's folder");
    return;
  }
  if (select.value === shelfMaterialKey) return;
  select.value = shelfMaterialKey;
  select.dispatchEvent(new Event("change"));
}

document.getElementById("shelf-close").addEventListener("click", closeShelf);
for (const button of document.querySelectorAll("#shelf-tabs button[data-shelf]")) {
  button.addEventListener("click", () => {
    if (shelfKind === button.dataset.shelf) closeShelf();
    else openShelf(button.dataset.shelf);
  });
}
document.getElementById("shelf-assign-skin").addEventListener("click",
  () => assignShelfMaterial("render-skin"));
document.getElementById("shelf-assign-ground").addEventListener("click",
  () => assignShelfMaterial("ground-preset"));

// ---------- preview balls ----------
// A material is a look, so the panel shows the look, not a rectangle of
// colour beside a word. Every rendering tool worth copying draws its
// materials as spheres under a fixed rig, and the sphere here carries the
// SAME registry material the vault would be cut in: the preview cannot
// drift from the thing it previews, because it IS the thing.
//
// One small renderer, hidden, shared by every tile. Its own environment,
// because a PMREM texture belongs to the context that made it and cannot be
// borrowed from the main view.
const PREVIEW_SIZE = 128;

// A SECOND WebGL context, and a machine is allowed to refuse one: browsers
// cap how many a page may hold, and a driver can fail a context outright.
// The whole rig is therefore built inside a guard, and every tile falls
// back to the material's own colour if it could not be built. A panel that
// shows flat colour is a disappointment; a panel that throws before the
// first frame is a dead studio.
let previewRig = null;

function buildPreviewRig() {
  try {
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setSize(PREVIEW_SIZE, PREVIEW_SIZE, false);
    // The same operator as the viewport, or a swatch would promise a
    // colour the scene does not keep.
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 1.05 * EXPOSURE_GAIN;
    const previewScene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 20);
    // Z-up like the studio, so a prop preview stands the way it stands in
    // the scene rather than lying on its face.
    camera.up.set(0, 0, 1);
    camera.position.set(0, -3.05, 1.02);
    camera.lookAt(0, 0, 0);
    // Its own generator, not the main renderer's: a PMREM texture belongs
    // to the context that made it and cannot be lent to another.
    const previewPmrem = new THREE.PMREMGenerator(renderer);
    previewScene.environment = previewPmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const key = new THREE.DirectionalLight(0xfff4e6, 2.4);
    key.position.set(-1.6, -2.2, 2.4);
    const rim = new THREE.DirectionalLight(0xbcd4ff, 1.1);
    rim.position.set(2.2, 1.6, 0.9);
    previewScene.add(key, rim, new THREE.HemisphereLight(0xb8c6d8, 0x2a2622, 0.6));
    const ball = new THREE.Mesh(new THREE.SphereGeometry(1, 64, 40), materials.concrete);
    previewScene.add(ball);
    const holder = new THREE.Group();
    previewScene.add(holder);
    return { renderer, scene: previewScene, camera, ball, holder };
  } catch (error) {
    console.warn("no preview context; tiles fall back to flat colour", error);
    return null;
  }
}

previewRig = buildPreviewRig();

// The tile is a 2D canvas: the WebGL canvas is drawn into it once, so one
// context serves any number of tiles and none of them holds a live context
// open. Same rule as the scene thumbnail: render and read in one turn.
//
// Cover semantics, not stretch: the rig renders square, and a tile whose
// canvas is wider than tall (a 2:1 sky) takes the central band of that
// square at full width instead of a squashed copy of all of it. The CSS
// box and the buffer then agree on one aspect, and nothing the painter
// composed is cropped away by the box it is shown in.
function drawPreview(canvasEl) {
  const context = canvasEl.getContext("2d");
  context.clearRect(0, 0, canvasEl.width, canvasEl.height);
  if (!previewRig) return false;
  previewRig.renderer.render(previewRig.scene, previewRig.camera);
  const source = previewRig.renderer.domElement;
  const scale = Math.min(source.width / canvasEl.width,
    source.height / canvasEl.height);
  const cutWidth = canvasEl.width * scale;
  const cutHeight = canvasEl.height * scale;
  context.drawImage(source,
    (source.width - cutWidth) / 2, (source.height - cutHeight) / 2,
    cutWidth, cutHeight, 0, 0, canvasEl.width, canvasEl.height);
  return true;
}

function fillFlat(canvasEl, colour) {
  const context = canvasEl.getContext("2d");
  context.fillStyle = "#" + colour.getHexString();
  context.fillRect(0, 0, canvasEl.width, canvasEl.height);
}

function renderMaterialPreview(material, canvasEl) {
  if (!previewRig) {
    fillFlat(canvasEl, material.color || new THREE.Color(0x9a9c9d));
    return;
  }
  previewRig.ball.visible = true;
  previewRig.ball.material = material;
  drawPreview(canvasEl);
}

// A tile: the preview, and the name beneath it. Nothing else, and no text
// beside the picture. The buffer takes the same aspect the CSS box shows
// (1 for a material, 2 for a sky), stated by the caller once.
function previewTile(value, label, paint, aspect = 1) {
  const tile = document.createElement("button");
  tile.className = "tile";
  tile.dataset.value = value;
  tile.title = label;
  const canvasEl = document.createElement("canvas");
  canvasEl.width = PREVIEW_SIZE;
  canvasEl.height = Math.round(PREVIEW_SIZE / aspect);
  tile.appendChild(canvasEl);
  const name = document.createElement("span");
  name.textContent = label;
  tile.appendChild(name);
  paint(canvasEl);
  return tile;
}

function closePicker(holder) {
  const trigger = document.querySelector(
    '.picker[aria-controls="' + holder.id + '"]') || holder.previousElementSibling;
  holder.classList.add("hidden");
  if (trigger && trigger.classList) trigger.classList.remove("open");
}

function paintTileSelection(holder, value) {
  for (const tile of holder.querySelectorAll(".tile")) {
    tile.classList.toggle("active", tile.dataset.value === value);
  }
}

// The two tile grids the panel shows. Both are driven by a select that is
// still there and still the source of truth: every other piece of code
// reads its value, and a picture that quietly disagreed with what the
// server was asked to cut would be worse than no picture at all.
function buildTileGrid(holderId, selectId, materialFor) {
  const holder = document.getElementById(holderId);
  const select = document.getElementById(selectId);
  if (!holder || !select) return;
  holder.innerHTML = "";
  for (const option of select.options) {
    const material = materialFor(option.value);
    if (!material) continue;
    const tile = previewTile(option.value, option.textContent,
      (canvasEl) => renderMaterialPreview(material, canvasEl));
    tile.addEventListener("click", () => {
      if (select.value === option.value) return;
      select.value = option.value;
      select.dispatchEvent(new Event("change"));
      paintTileSelection(holder, option.value);
    });
    holder.appendChild(tile);
  }
  paintTileSelection(holder, select.value);
}

// A floor previewed on a floor. The plane is tilted away from the camera so
// the joint spacing reads, which a sphere cannot show: the whole reason for
// choosing paving over concrete is the size of the pieces.
function renderGroundPreview(preset, canvasEl) {
  if (!previewRig) {
    fillFlat(canvasEl, new THREE.Color(0x2a2e34));
    return;
  }
  const material = groundMaterial(preset);
  const tile = material.userData.groundTileMetres;
  if (tile && material.map) {
    // Six metres of ground in the preview, so the joints are the size they
    // would be under a person rather than under a vault. Squared up for
    // the tile: the floor's random lay angle belongs to the floor.
    const [u, v] = groundRepeat(3, tile);
    material.map.repeat.set(u, v);
    material.map.rotation = 0;
  }
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), material);
  previewRig.holder.add(plane);
  previewRig.ball.visible = false;
  previewRig.camera.position.set(0, -3.4, 2.2);
  previewRig.camera.lookAt(0, 0.4, 0);
  drawPreview(canvasEl);
  previewRig.holder.remove(plane);
  plane.geometry.dispose();
  previewRig.ball.visible = true;
  previewRig.camera.position.set(0, -3.05, 1.02);
  previewRig.camera.lookAt(0, 0, 0);
  // Put the repeat back where the scene wants it, since the material is the
  // same object the floor itself is drawn with -- INCLUDING the scale
  // dials and the lay angle, or painting one picker tile would silently
  // reset the floor.
  if (tile && material.map) {
    const [u, v] = groundRepeat(state.groundRadius, tile);
    material.map.repeat.set(u * state.ground.scaleX, v * state.ground.scaleY);
    material.map.rotation = state.ground.rotation || 0;
  }
}

// The weather presets, each rendered as its own sky. The preview rig gets
// its own Sky mesh, because the scene's one belongs to the scene and a
// preview must not touch the uniforms the viewport is drawing from.
let previewSky = null;

function renderWeatherPreview(preset, canvasEl) {
  const settings = WEATHER[preset];
  if (!previewRig || !settings) {
    fillFlat(canvasEl, new THREE.Color(settings ? settings.fogColor : 0x2a2e34));
    return;
  }
  if (!previewSky) {
    previewSky = new Sky();
    previewSky.scale.setScalar(4000);
    previewSky.material.uniforms.up.value.set(0, 0, 1);
    previewSky.material.uniforms.cloudCoverage.value = 0;
    previewRig.scene.add(previewSky);
  }
  const uniforms = previewSky.material.uniforms;
  uniforms.turbidity.value = settings.turbidity;
  uniforms.rayleigh.value = settings.rayleigh;
  uniforms.mieCoefficient.value = settings.mieCoefficient;
  uniforms.mieDirectionalG.value = settings.mieDirectionalG;
  // The sun sits where this preset wants it, or where the studio's own sun
  // is standing, so the tiles answer "what would this weather look like
  // now" rather than "what does this weather look like at noon".
  const elevation = settings.elevation === null
    ? Math.max(2, currentSun().elevation) : settings.elevation;
  const azimuth = 40 * Math.PI / 180;
  const height = elevation * Math.PI / 180;
  uniforms.sunPosition.value.set(
    Math.cos(height) * Math.cos(azimuth),
    Math.cos(height) * Math.sin(azimuth),
    Math.sin(height)).normalize();
  previewSky.visible = true;
  previewRig.ball.visible = false;
  const exposure = previewRig.renderer.toneMappingExposure;
  previewRig.renderer.toneMappingExposure = settings.exposure * 1.9 * EXPOSURE_GAIN;
  // Looking at the horizon, slightly above it, which is where the weather
  // of a sky actually reads.
  previewRig.camera.position.set(0, 0, 0.2);
  previewRig.camera.lookAt(0, 4, 0.9);
  drawPreview(canvasEl);
  previewRig.renderer.toneMappingExposure = exposure;
  previewSky.visible = false;
  previewRig.ball.visible = true;
  previewRig.camera.position.set(0, -3.05, 1.02);
  previewRig.camera.lookAt(0, 0, 0);
}

function buildWeatherTiles() {
  const holder = document.getElementById("weather-tiles");
  const select = document.getElementById("weather-preset");
  if (!holder || !select) return;
  holder.innerHTML = "";
  for (const option of select.options) {
    // 2:1 like the HDRI grid: both grids offer skies, and a sky keeps one
    // shape. The cover-crop in drawPreview keeps the horizon band the
    // painter composed.
    const tile = previewTile(option.value, option.textContent,
      (canvasEl) => renderWeatherPreview(option.value, canvasEl), 2);
    tile.addEventListener("click", () => {
      if (select.value === option.value) return;
      select.value = option.value;
      select.dispatchEvent(new Event("change"));
      paintTileSelection(holder, option.value);
    });
    holder.appendChild(tile);
  }
  paintTileSelection(holder, select.value);
}

// The sky list, as skies. The thumbnails are decoded by the server the
// first time they are asked for, because the files run to hundreds of
// megabytes and nothing in a browser should touch one to draw an inch of it.
function buildHdriTiles(names) {
  const holder = document.getElementById("hdri-tiles");
  const select = document.getElementById("hdri-select");
  if (!holder || !select) return;
  holder.innerHTML = "";
  for (const name of names) {
    const tile = document.createElement("button");
    tile.className = "tile";
    tile.dataset.value = name;
    tile.title = name;
    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = "/api/hdri/" + encodeURIComponent(name) + "/thumbnail";
    image.alt = "";
    tile.appendChild(image);
    const label = document.createElement("span");
    // The name without its extension and its resolution suffix: the file
    // is called what it is called, but the tile is a picture of a place.
    label.textContent = name.replace(/\.hdr$/i, "").replace(/_(\d+k)$/i, "");
    tile.appendChild(label);
    tile.addEventListener("click", () => {
      if (select.value === name) return;
      select.value = name;
      select.dispatchEvent(new Event("change"));
      paintTileSelection(holder, name);
    });
    holder.appendChild(tile);
  }
  paintTileSelection(holder, select.value);
}

function buildMaterialTiles() {
  buildTileGrid("material-tiles", "material-select",
    (value) => materials[value] || null);
  buildSkinTiles();
}

// A tile whose picture is a file rather than a render. The library's own
// 256 pixel colour crop, served by the backend and drawn by the browser, so
// a hundred and fifty-eight of them cost no video memory whatever. This is
// also the most legible thing that could go in a tile: QS crops each
// picture to ONE unit before it enters the stack, and a picture of one
// brick reads at 180 pixels where a picture of a wall does not.
function imageTile(value, label, source) {
  const tile = document.createElement("button");
  tile.className = "tile";
  tile.dataset.value = value;
  tile.title = label;
  const image = document.createElement("img");
  image.loading = "lazy";
  image.decoding = "async";
  image.alt = "";
  image.src = source;
  tile.appendChild(image);
  const name = document.createElement("span");
  name.textContent = label;
  tile.appendChild(name);
  return tile;
}

function chooseSkin(value) {
  const select = document.getElementById("render-skin");
  if (select.value === value) return;
  select.value = value;
  select.dispatchEvent(new Event("change"));
  paintTileSelection(document.getElementById("skin-tiles"), value);
}

// One grid for both places a library material can be worn: the vault and
// the ground it stands on. The built-in presets come first and are rendered
// on the preview object, because there are a handful of them and they have
// no picture of their own; the library follows as pictures, in families.
function buildLibraryGrid(holderId, selectId, searchId, paintBuiltin,
                          list, base) {
  const holder = document.getElementById(holderId);
  const select = document.getElementById(selectId);
  if (!holder || !select) return;
  const entries = list || state.materialLibrary;
  const query = ((document.getElementById(searchId) || {}).value || "")
    .trim().toLowerCase();
  holder.innerHTML = "";

  const choose = (value) => {
    if (select.value === value) return;
    select.value = value;
    select.dispatchEvent(new Event("change"));
    paintTileSelection(holder, value);
  };

  if (!query) {
    for (const option of select.options) {
      if (isLibraryKey(option.value)) continue;
      const tile = previewTile(option.value, option.textContent,
        (canvasEl) => paintBuiltin(option.value, canvasEl));
      tile.addEventListener("click", () => choose(option.value));
      holder.appendChild(tile);
    }
  }

  // The library in families, because a search across a hundred and fifty
  // near-identical bricks is the difference between adjusting a choice and
  // making a new one.
  let family = null;
  for (const entry of entries) {
    if (query && !(entry.key + " " + entry.label).toLowerCase().includes(query)) continue;
    if (entry.family !== family) {
      family = entry.family;
      const heading = document.createElement("span");
      heading.className = "tile-family";
      heading.textContent = family;
      holder.appendChild(heading);
    }
    const tile = imageTile(entry.key, entry.label, tileUrl(entry, base));
    // The size is what an architect wants to know about a picture of a
    // brick, and it is the number that decides how it lays on.
    if (entry.tileMetres) {
      tile.title = entry.label + "  "
        + Math.round(entry.tileMetres[0] * 1000) + " x "
        + Math.round(entry.tileMetres[1] * 1000) + " mm";
    }
    tile.addEventListener("click", () => choose(entry.key));
    holder.appendChild(tile);
  }
  paintTileSelection(holder, select.value);
}

function buildSkinTiles() {
  buildLibraryGrid("skin-tiles", "render-skin", "skin-search",
    (value, canvasEl) => {
      const material = value === "none"
        ? (materials[document.getElementById("material-select").value]
          || materials.concrete)
        : (skinMaterialCache[value]
          || (SKINS[value] && (skinMaterialCache[value] = SKINS[value]())));
      if (material) renderMaterialPreview(material, canvasEl);
    });
}

function buildGroundTiles() {
  // A floor previewed on a floor: the plane is tilted away from the camera
  // so the joint spacing reads, which a sphere cannot show, and the size of
  // the pieces is the whole reason for choosing paving over concrete. The
  // ground grid draws from its OWN library and its own routes.
  buildLibraryGrid("ground-tiles", "ground-preset", "ground-search",
    (value, canvasEl) => renderGroundPreview(value, canvasEl),
    state.groundLibrary, GROUND_BASE);
}

function paintMaterialSwatches() {
  const material = document.getElementById("material-select");
  const skin = document.getElementById("render-skin");
  const materialHolder = document.getElementById("material-tiles");
  const skinHolder = document.getElementById("skin-tiles");
  if (materialHolder) paintTileSelection(materialHolder, material.value);
  if (skinHolder) paintTileSelection(skinHolder, skin.value);
  // The "no skin" tile shows the material it would fall back to, so the two
  // grids never disagree about what the vault is wearing.
  const none = skinHolder && skinHolder.querySelector('.tile[data-value="none"] canvas');
  if (none) renderMaterialPreview(materials[material.value] || materials.concrete, none);
}

// Built once the module has finished declaring the skins it previews: the
// call used to sit here and reached SKINS in its temporal dead zone, which
// is a blank panel and a ReferenceError before the first frame.

// ---------- the cut (Task 8: pieces and their course/size come from the server) ----------
// Mirrors app.py's own SIZE_MIN/SIZE_MAX. The bundle's top level "size" is
// meant to be the requested size (see bundle.py), but a client that trusts
// a server value blindly is exactly how a poisoned value like the old
// authored-cut sentinel reaches the screen; this is the defence in depth
// for that class of bug, not the fix for it.
const SIZE_MIN = 0.3, SIZE_MAX = 3.0;

function applyCut(preserve) {
  paintMaterialSwatches();
  repaintScrubs();
  // The cut always follows the LOADED bundle's own size, never the
  // slider's current position. The pieces the viewer draws are built
  // server-side at the bundle's own size, and each one is looked up in
  // state.segmentIndex by the key the cut gave it. Re-cutting here to the
  // slider's number instead would rebuild the index around cells the drawn
  // pieces know nothing about, which is the defect the ring/wedge binning
  // this replaces used to have: measured on Trial 2 against an 8-ring
  // bundle, every slider value from 4 to 16 orphaned keys, and the first
  // missing key threw inside applySceneAtTime, which while playing killed
  // the render loop until reload. The slider asks the server for a
  // matching bundle instead: see its change handler, which follows the
  // thickness slider.
  if (!state.bundle) return;
  const size = state.bundle.size;
  // Only adopt a usable number in the API's own range. state.size otherwise
  // keeps whatever it already held, so a bad value here cannot poison the
  // next reload the way an unguarded copy did.
  if (typeof size === "number" && Number.isFinite(size) && size >= SIZE_MIN && size <= SIZE_MAX) {
    state.size = size;
    document.getElementById("size-slider").value = size;
    document.getElementById("size-value").textContent = Math.round(size * 1000);
  }
  // bundle.py is explicit that document["size"] is the REQUESTED size and
  // that an authored cut ignores it (its own target_size is None). The
  // number above is therefore what the control asked for, not what the cut
  // used, and calling it a "target" when nothing targeted it is the same
  // claim the Data panel already refuses to make. The units span, which
  // the slider's live input handler never touches, carries the correction
  // so a mid-drag label stays true rather than reverting to "mm target".
  // The correction is two words, not a sentence. The long form ran to 466
  // pixels inside a 300 pixel panel, printed straight through the words
  // "Piece size" and then off the right edge -- found in the first
  // screenshot of the studio ever taken here, 2026-09-04. The HUD carries
  // the explanation in full, which is where a sentence belongs.
  document.getElementById("size-units").textContent =
    state.bundle.tessellation.source === "imported"
      ? " mm requested" : " mm target";
  // Same defence for the pattern (Task 9, the half of C1 Task 8 left open):
  // an authored cut's own pattern name (tess["pattern"] in staging.py, not
  // the requested one) is only adopted when it is one the server actually
  // offers, so a bundle carrying a Grasshopper-authored pattern name never
  // leaves the pattern control pointing at an option it does not have.
  // Without this, selecting a material still sent whichever pattern the
  // client last held, so choosing sprayed concrete kept requesting bonded
  // courses instead of the monolithic bands its own default names.
  const pattern = state.bundle.pattern;
  if (typeof pattern === "string" && state.patterns.includes(pattern)) {
    state.pattern = pattern;
    document.getElementById("pattern-select").value = pattern;
  }
  // The bundle STATES which cut it is and which the study could offer;
  // the viewer used to infer this from target_size being null, a side
  // effect that could not tell a study with no Skin from one whose Skin
  // was overridden. The control appears only where there is a choice to
  // make, so a study without a Skin looks exactly as it always has.
  const available = state.bundle.source_available || ["generated"];
  const row = document.getElementById("source-row");
  const toggle = document.getElementById("source-toggle");
  if (row && toggle) {
    // The switch appears only where there is a choice to make, and it says
    // which end it is at whether or not the study offers both.
    row.classList.toggle("hidden", available.length < 2);
    toggle.checked = state.bundle.source === "generated";
    toggle.disabled = available.length < 2;
    row.classList.toggle("authored", state.bundle.source === "authored");
    row.classList.toggle("generated", state.bundle.source === "generated");
    state.source = state.bundle.source;
    // A cut that loaded clears the last refusal. Which skin is on is said
    // by the switch itself; it does not also need a sentence beneath it.
    state.lastRefusal = null;
  }
  document.getElementById("piece-count").textContent = state.bundle.pieces.length;
  document.getElementById("course-count").textContent = state.bundle.tessellation.courses;
  // The index the timeline looks a casting up in, keyed by the PIECE's own
  // key: pieces.py emits exactly one casting per cell of the cut
  // tessellation, so the cell's own key is the piece's identity too. The
  // array order is the drop order.
  state.segmentIndex = new Map();
  state.bundle.pieces.forEach((piece, position) => {
    state.segmentIndex.set(piece.key, {
      course: piece.course, order: position,
    });
  });
  rebuildTimeline(preserve);
}

// ---------- FEA layers ----------
const LAYERS = [
  ["stress", "Stress heatmap"],
  ["deflection", "Deflection heatmap"],
  ["loads", "Load vectors"],
  ["reactions", "Reaction vectors"],
  ["overlays", "Text overlays"],
  ["pulse", "Integrity pulse"],
  ["forces", "Wire forces"],
];

function finalStage() {
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return null;
  const last = staging.stages[staging.stages.length - 1];
  return last.struck_now && last.struck_now.converged ? last.struck_now : null;
}

// The third reading, in the one place all three readers can share it.
// brick, tile and stone carry no ananke_fea preset (staging.FEA_MATERIALS),
// so staging.py never calls the struck-now runner for them and writes
// struck_now.status "unavailable" instead of a solve result. finalStage()
// therefore returns null for those materials however many staged runs
// complete, which makes "finalStage() is null" mean any of three different
// things -- no staged run exists at all, a staged run exists and this
// material has no solver, or a staged run exists, was solved, and did not
// converge -- three statements a reader must never see conflated.
// updateHud and applyPulse were given the no-solver reading in commit
// 022f9c5; layerAvailability, the sibling nobody re-read, was still
// printing the first when it meant the second (commit 8444539). What was
// still missing after both fixes is the state one over: a stage that DID
// reach the runner and came back with converged false. That is not "no
// staging" (staging.stages is non-empty) and it is not "unavailable"
// (struck_now.status is not "unavailable"), so it fell through to
// layerAvailability's oldest, most generic branches, the same ones that
// answer for a bundle with no staging at all.
function stagingUnavailable() {
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return false;
  // some, not every: staging.py decides this per material, before any
  // stage runs, so it is all or nothing in practice -- and a bundle where
  // it somehow is not still has a stage nobody solved, which is the thing
  // worth saying.
  return staging.stages.some(
    (stage) => stage.struck_now && stage.struck_now.status === "unavailable");
}

function craVerdict() {
  // The final stage's verdict is the whole-study verdict; run_staging
  // writes one cra entry per stage and no separate whole-vault solve.
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return null;
  return staging.stages[staging.stages.length - 1].cra || null;
}

// Keyed by material, not by the numeric mu value: stone's friction is 0.6,
// the same number staging.py gives concrete, so a value-keyed lookup would
// attribute it to EN 1992-1-1 clause 6.2.5, a smooth precast concrete
// joint, when it was deliberately sourced as the middle of the 0.5 to 0.7
// span the dry stone rigid block literature uses. See staging.py's own
// FRICTION comment, which this mirrors.
const FRICTION_PROVENANCE = {
  "concrete": "mu 0.60: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint",
  "concrete-c50": "mu 0.60: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint",
  "concrete-sprayed": "mu 0.60: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint",
  "timber": "mu 0.40: literature value for dry timber on timber contact (Eurocode 5 gives none)",
  "brick": "mu 0.60: EN 1992-1-1 clause 6.2.5, the same value for a mortared brick bed joint",
  "tile": "mu 0.60: EN 1992-1-1 clause 6.2.5, the same value for a mortared tile bed joint",
  "stone": "mu 0.60: middle of the 0.5 to 0.7 span the dry stone rigid block literature uses, quoted no more precisely than the source supports",
};

function layerAvailability(name) {
  const stage = finalStage();
  const v = state.bundle && state.bundle.verification;
  if (name === "pulse") {
    return state.bundle && state.bundle.staging
      ? { on: true } : { on: false, why: "run staged analysis first" };
  }
  if (name === "stress" || name === "deflection") {
    if (stage) return { on: true };
    // stage is null and the question is why, in the same words updateHud
    // and applyPulse already use for the same struck_now on the same
    // screen. A staged run (staging.stages.length) settles two of the
    // three readings below before the "no staging at all" fallback is
    // even reachable, because both of them describe a run that already
    // happened and can never be answered by telling the reader to run one.
    const staging = state.bundle && state.bundle.staging;
    const staged = !!(staging && staging.stages && staging.stages.length);
    if (staged) {
      // Two reasons a finished run still has no per-node field to colour
      // with, and only two: either the material has no ananke_fea preset
      // (stagingUnavailable, updateHud's "not available for this
      // material") or the solver ran and did not converge (updateHud's
      // "no equilibrium found"). Neither is "no staging exists".
      if (stagingUnavailable()) {
        return v
          ? { on: true, why: "peaks only: struck-now fields are not available for this material" }
          : { on: false, why: "not available for this material, and no verification data" };
      }
      return v
        ? { on: true, why: "peaks only: no equilibrium found on the last staged run" }
        : { on: false, why: "no equilibrium found on the last staged run, and no verification data" };
    }
    if (v) return { on: true, why: "peaks only until a staged run exists" };
    return { on: false, why: "no staging and no verification data" };
  }
  if (name === "reactions") {
    return state.bundle && Object.keys(state.bundle.reactions).length
      ? { on: true }
      : { on: false, why: "this contract shipped no reaction vectors" };
  }
  if (name === "forces") {
    const bundle = state.bundle;
    const forceCount = bundle && bundle.member_forces ? bundle.member_forces.length : 0;
    const edgeCount = bundle ? bundle.analysis_mesh.edges.length : 0;
    return forceCount && forceCount === edgeCount
      ? { on: true }
      : { on: false, why: "this contract shipped no member forces" };
  }
  return { on: true };
}

function buildLayerToggles() {
  const holder = document.getElementById("layer-toggles");
  holder.innerHTML = "";
  for (const [name, label] of LAYERS) {
    const availability = layerAvailability(name);
    const wrap = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = !!state.layers[name];
    box.disabled = !availability.on;
    if (availability.why) wrap.title = availability.why;
    box.addEventListener("change", () => setLayer(name, box.checked));
    wrap.appendChild(box);
    wrap.appendChild(document.createTextNode(label));
    holder.appendChild(wrap);
  }
}

function setLayer(name, on) {
  state.layers[name] = on;
  if (name === "loads" || name === "reactions") updateVectorLayers();
  if (name === "stress" || name === "deflection") recolourSegments();
  if (name === "forces") applyWireForces();
  if (name === "pulse" && !on && state.objects.shell) {
    // The pulse is the only thing that writes emissive on segment
    // materials; turning it off sweeps that back to zero rather than
    // leaving the last frame's tint stuck on the shell.
    for (const segment of state.objects.shell.children) {
      segment.material.emissiveIntensity = 0;
    }
  }
  updateHud();
}

const STRESS_SCALE = (() => {
  // Diverging palette: compression blue, zero pale, tension red. These same
  // three hexes are hand-mirrored in studio.css's #legend-bar gradient;
  // keep both in sync or the on-screen legend will silently drift from the
  // scale it is meant to describe.
  const compression = new THREE.Color(0x2255cc), zero = new THREE.Color(0xf2efe8),
        tension = new THREE.Color(0xcc2211);
  return (value, magnitude) => {
    const u = Math.max(-1, Math.min(1, value / magnitude));
    return u < 0 ? zero.clone().lerp(compression, -u) : zero.clone().lerp(tension, u);
  };
})();

// ---------- wire forces (Task 6) ----------
// Colours and thickens each thrust-network wire by its own TNA member
// force. Tension positive, same convention as STRESS_SCALE: compression
// toward blue, tension toward red. buildWiresAndNodes stores the base
// (endpoint/orientation/length) matrix per edge on wires.userData so this
// can rebuild thicker/tinted matrices when on and restore the originals
// exactly when off, without touching the "wires" visibility toggle.
// buildWiresAndNodes also sets the material's vertexColors true for good:
// setColorAt alone writes the instanceColor buffer, but per-instance
// colour only reaches a pixel when the material opts into that path, so
// both the on and off states below rely on it being set already.
function applyWireForces() {
  const wires = state.objects.wires;
  const base = wires && wires.userData.baseMatrices;
  if (!wires || !base) return;
  const availability = layerAvailability("forces");
  const active = !!(state.layers.forces && availability.on);
  if (!active) {
    const white = new THREE.Color(0xffffff);
    for (let i = 0; i < base.length; i++) {
      wires.setMatrixAt(i, base[i]);
      wires.setColorAt(i, white);
    }
    wires.instanceMatrix.needsUpdate = true;
    wires.instanceColor.needsUpdate = true;
    wires.material.color.copy(materials.steel.color);
    return;
  }
  const forces = state.bundle.member_forces;
  let magnitude = 1e-9;
  for (const force of forces) magnitude = Math.max(magnitude, Math.abs(force));
  const position = new THREE.Vector3(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
  const m = new THREE.Matrix4();
  wires.material.color.set(0xffffff);   // tint through instance colour, not the material
  forces.forEach((force, i) => {
    base[i].decompose(position, quaternion, scale);
    const radiusScale = 1 + 2 * Math.abs(force) / magnitude;
    m.compose(position, quaternion, new THREE.Vector3(radiusScale, scale.y, radiusScale));
    wires.setMatrixAt(i, m);
    wires.setColorAt(i, STRESS_SCALE(force, magnitude));
  });
  wires.instanceMatrix.needsUpdate = true;
  wires.instanceColor.needsUpdate = true;
}

function stressValue(pair, surface, magnitude) {
  // The signed value the heatmap colours: the picked surface's dominant
  // principal, or the worst over both surfaces. Tension positive.
  if (!pair) return -0.3 * magnitude;   // verification-peaks fallback tint
  if (surface === "top" || surface === "bottom") {
    const p = pair[surface];
    return Math.abs(p[1]) > p[0] ? p[1] : p[0];
  }
  const worstTension = Math.max(pair.top[0], pair.bottom[0]);
  const worstCompression = Math.min(pair.top[1], pair.bottom[1]);
  return Math.abs(worstCompression) > worstTension ? worstCompression : worstTension;
}

function fieldPerRenderVertex(nodeField, fallback) {
  // nodeField: {"nodeId": [dx,dy,dz]}. vertex_sources averages it onto the
  // render mesh exactly as subdivision.py's interpolate_vertex_field does.
  const sources = state.bundle.render_mesh.vertex_sources;
  return sources.map((ids) => {
    let x = 0, y = 0, z = 0, found = 0;
    for (const id of ids) {
      const v = nodeField[String(id)];
      if (v) { x += v[0]; y += v[1]; z += v[2]; found += 1; }
    }
    return found ? [x / found, y / found, z / found] : fallback;
  });
}

function recolourSegments() {
  if (!state.bundle || !state.objects.shell) return;
  const stage = finalStage();
  const exaggeration = +document.getElementById("exaggeration").value;
  const surface = document.getElementById("stress-surface").value;
  const wantStress = state.layers.stress, wantDeflection = state.layers.deflection;
  const mesh = state.bundle.render_mesh;
  const v = state.bundle.verification;
  const displacement = stage && wantDeflection
    ? fieldPerRenderVertex(stage.displacements, [0, 0, 0]) : null;
  const stressMagnitude = stage
    ? Math.max(Math.abs(stage.peak_compression), stage.peak_tension, 1)
    : (v && v.stress ? Math.max(Math.abs(v.stress.peak_compression), 1) : 1);
  // No staging means no per-node displacement field to exaggerate the
  // shell with, but the field sourcing rule still owes the deflection
  // layer an honest "peaks only" tint, scaled off the verification file's
  // peak magnitude, the same way the stress fallback does.
  const deflectionPeakOnly = !stage && wantDeflection && v && v.displacement
    ? Math.max(v.displacement.peak_magnitude, 1e-9) : null;
  let deflectionMax = 1e-9;
  if (displacement) for (const d of displacement) {
    deflectionMax = Math.max(deflectionMax, Math.hypot(d[0], d[1], d[2]));
  }
  // Smooth per-vertex stress: face values averaged onto analysis vertices,
  // then carried to render vertices through vertex_sources, the same rule
  // the displacement field uses. Null means no adjacent face had data.
  // Two fields under "per surface", not three. buildPieceMeshes writes
  // userData.surface as `index < count ? 1 : -1` and nothing else, so a
  // corner is always top or bottom and the third field the "per" branch
  // used to smooth was never read by any corner: a full smoothing pass
  // over the analysis faces plus an interpolation onto every render
  // vertex, run on every recolour, whose result went nowhere. The
  // stress-surface control's own "worst" option is unaffected -- that one
  // comes through pickedField below, which is read.
  let topField = null, bottomField = null, pickedField = null;
  if (stage && wantStress) {
    const analysis = state.bundle.analysis_mesh;
    const sources = mesh.vertex_sources;
    const smooth = (which) => interpolateScalarField(
      smoothStressField(analysis.faces, analysis.vertices.length, stage.stresses, which),
      sources);
    if (surface === "per") {
      topField = smooth("top");
      bottomField = smooth("bottom");
    } else {
      pickedField = smooth(surface);
    }
  }
  // No-data reads as a neutral mid grey, not white: white sits inside the
  // STRESS_SCALE gradient's own pale-zero region (0xf2efe8), so a bank of
  // missing corners used to look like a bank of zero stress instead of a
  // hole in coverage. Grey is clearly outside every scale this function
  // paints (compression blue, zero pale beige, tension red).
  const noData = new THREE.Color(0x808080);
  for (const segment of state.objects.shell.children) {
    const weights = segment.userData.weights;
    const surfaceOf = segment.userData.surface;
    const base = segment.userData.basePositions;
    const positions = segment.geometry.getAttribute("position");
    const colours = new Float32Array(weights.length * 3);
    let displaced = false;
    for (let i = 0; i < weights.length; i++) {
      let colour = null;
      if (wantStress) {
        if (pickedField || topField) {
          const field = pickedField || (surfaceOf[i] === 1 ? topField : bottomField);
          // A cut piece vertex is not a mesh vertex, so the field is read
          // through the weights the cut recorded for it rather than a bare
          // index. sampleScalar renormalises over whatever weighted corners
          // do have data, so null here means every one of them is missing,
          // not just one -- an honest "no data" reads as grey, not white.
          const value = sampleScalar(field, weights[i]);
          colour = value === null ? noData : STRESS_SCALE(value, stressMagnitude);
        } else {
          // Verification peaks only: the flat honest tint, as before.
          colour = STRESS_SCALE(stressValue(null, surface, stressMagnitude), stressMagnitude);
        }
      } else if (deflectionPeakOnly) {
        colour = STRESS_SCALE(0.3 * deflectionPeakOnly, deflectionPeakOnly);
      }
      const d = displacement ? sampleVector(displacement, weights[i], null) : null;
      if (!colour && wantDeflection && d) {
        colour = STRESS_SCALE(Math.hypot(d[0], d[1], d[2]), deflectionMax);
      }
      if (!colour) colour = noData;
      colours[3 * i] = colour.r;
      colours[3 * i + 1] = colour.g;
      colours[3 * i + 2] = colour.b;
      if (wantDeflection && d) {
        positions.setXYZ(i,
          base[3 * i] + d[0] * exaggeration,
          base[3 * i + 1] + d[1] * exaggeration,
          base[3 * i + 2] + d[2] * exaggeration);
        displaced = true;
      } else {
        positions.setXYZ(i, base[3 * i], base[3 * i + 1], base[3 * i + 2]);
      }
    }
    positions.needsUpdate = true;
    segment.geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    // Recomputing crease normals costs a pass over every vertex, and the
    // shape only actually changes when a displacement was painted in above.
    // Skip it when this pass wrote positions straight back from
    // basePositions -- unless the previous pass left the geometry bent, in
    // which case the normals still belong to that bent shape and must be
    // reset to match the flat positions just written. That reset must
    // restore the stored welded buffer, not recompute per piece: a
    // recompute here is per-piece crease normals even on a sprayed shell,
    // so two clicks of a heatmap (on, then off) would undo the one-surface
    // weld buildPieceMeshes did, and the course joints would step in the
    // light again until the next rebuild.
    if (displaced) {
      segment.geometry.setAttribute("normal",
        new THREE.BufferAttribute(creaseNormals(positions.array), 3));
    } else if (segment.userData.wasDisplaced) {
      segment.geometry.setAttribute("normal",
        new THREE.BufferAttribute(segment.userData.baseNormals.slice(), 3));
    }
    segment.userData.wasDisplaced = displaced;
    // Off the heatmaps, the piece goes back to the material it was built
    // with, tint and all: pieceMaterial recomputes it from the key rather
    // than handing back a bare registry clone, which used to discard the
    // per casting tint before the first frame was ever drawn.
    const previous = segment.material;
    const wantHeatmap = wantStress || wantDeflection;
    // A staged per-vertex field is data, not scenography: unlit and exempt
    // from tone mapping, it reads identically under any environment mode,
    // exposure or contrast setting. The peaks-only fallback (no stage,
    // verification only) is not a field, it is one flat tint standing in
    // for a whole surface, so it keeps ordinary lighting rather than
    // claiming an exemption a single colour has no field to earn.
    segment.material = wantHeatmap && stage
      ? new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, toneMapped: false })
      : wantHeatmap
        ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })
        : pieceMaterial(segment.userData.key);
    // What is discarded here is always a per piece instance, never the
    // shared registry entry, so freeing it is safe: without this, every
    // layer toggle and every exaggeration nudge leaked one material per
    // casting.
    if (previous && previous !== segment.material) previous.dispose();
  }
  updateLegend(stressMagnitude, deflectionMax, deflectionPeakOnly, stage);
}

function updateLegend(stressMagnitude, deflectionMax, deflectionPeakOnly, stage) {
  const legend = document.getElementById("legend");
  const showStress = state.layers.stress, showDeflection = state.layers.deflection;
  // Mirrors layerAvailability("stress"/"deflection"): both layers only have
  // real data when a converged final stage or a verification bundle is
  // present. Without either, stressMagnitude/deflectionMax are just the
  // 1 Pa / 1e-9 floors recolourSegments falls back to, so the legend must
  // hide rather than print a fabricated "-0.00 / 0.00" scale.
  const hasData = !!(stage || (state.bundle && state.bundle.verification));
  if (!state.bundle || (!showStress && !showDeflection) || !hasData) {
    legend.classList.add("hidden");
    return;
  }
  legend.classList.remove("hidden");
  const surface = document.getElementById("stress-surface").value;
  const surfaceLabels = {
    per: "top and bottom skins",
    worst: "worst of both",
    top: "top surface",
    bottom: "bottom surface",
  };
  const title = document.getElementById("legend-title");
  const minLabel = document.getElementById("legend-min");
  const zeroLabel = document.getElementById("legend-zero");
  const maxLabel = document.getElementById("legend-max");
  if (showStress) {
    legend.classList.remove("deflection");
    title.textContent = stage
      ? "stress, MPa (" + (surfaceLabels[surface] || surface) + ")"
      : "stress, MPa (peaks only)";
    minLabel.textContent = (-stressMagnitude / 1e6).toFixed(2);
    zeroLabel.textContent = "0";
    maxLabel.textContent = (stressMagnitude / 1e6).toFixed(2);
    return;
  }
  legend.classList.add("deflection");
  title.textContent = stage ? "deflection, mm" : "deflection, mm (peaks only)";
  minLabel.textContent = "0";
  zeroLabel.textContent = "";
  maxLabel.textContent = stage
    ? (deflectionMax * 1000).toFixed(2)
    : (deflectionPeakOnly ? (deflectionPeakOnly * 1000).toFixed(2) : "");
}

// ---------- vector layers ----------
function updateVectorLayers() {
  for (const key of ["loadArrows", "reactionArrows"]) {
    if (state.objects[key]) { scene.remove(state.objects[key]); state.objects[key] = null; }
  }
  if (!state.bundle) return;
  const bundle = state.bundle;
  if (state.layers.loads) {
    state.objects.loadArrows = arrowField(
      Object.entries(bundle.loads), 0x66aaff, "tip");
    scene.add(state.objects.loadArrows);
  }
  if (state.layers.reactions && Object.keys(bundle.reactions).length) {
    // Real TNA reaction vectors from the contract, shipped in the bundle.
    state.objects.reactionArrows = arrowField(
      Object.entries(bundle.reactions), 0x66dd77, "tail");
    scene.add(state.objects.reactionArrows);
  }
}

function arrowField(entries, colour, anchor) {
  // One LineSegments for every shaft plus one instanced cone set for heads:
  // two draw calls however many nodes there are. Arrows draw exactly along
  // the shipped vector: loads arrive pointing down, reactions as exported.
  // anchor 'tip' stands the shaft before the node so the head lands at the point of application; 'tail' leaves the node along the vector.
  const vertices = state.bundle.analysis_mesh.vertices;
  let magnitudeMax = 1e-9;
  for (const [, v] of entries) magnitudeMax = Math.max(magnitudeMax, Math.hypot(v[0], v[1], v[2]));
  const positions = [];
  const cone = new THREE.ConeGeometry(0.06, 0.18, 8);
  const heads = new THREE.InstancedMesh(
    cone, new THREE.MeshBasicMaterial({ color: colour }), entries.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  entries.forEach(([id, vector], i) => {
    const at = vertices[+id];
    const v = new THREE.Vector3(vector[0], vector[1], vector[2]);
    const length = 0.4 + 2.0 * (v.length() / magnitudeMax);
    const dir = v.lengthSq() ? v.clone().normalize() : new THREE.Vector3(0, 0, -1);
    const start = new THREE.Vector3(...at);
    const tipAnchored = anchor === "tip";
    // The analysis node sits on the mid-surface, half a thickness inside
    // the drawn shell, so a head composed at the node is buried in opaque
    // geometry. The tip-anchored arrow stands off by that half thickness
    // and the cone's own half height, so its point touches the outer
    // surface at the point of application.
    const lift = tipAnchored ? state.bundle.provenance.thickness / 2 : 0;
    const surface = start.clone().addScaledVector(dir, -lift);
    const from = tipAnchored ? surface.clone().addScaledVector(dir, -length) : start;
    const to = tipAnchored ? surface : start.clone().addScaledVector(dir, length);
    positions.push(from.x, from.y, from.z, to.x, to.y, to.z);
    q.setFromUnitVectors(up, dir);
    const headAt = tipAnchored ? to.clone().addScaledVector(dir, -0.09) : to;
    m.compose(headAt, q, new THREE.Vector3(1, 1, 1));
    heads.setMatrixAt(i, m);
  });
  const lines = new THREE.LineSegments(
    new THREE.BufferGeometry().setAttribute(
      "position", new THREE.BufferAttribute(new Float32Array(positions), 3)),
    new THREE.LineBasicMaterial({ color: colour }));
  const group = new THREE.Group();
  group.add(lines); group.add(heads);
  return group;
}

// ---------- integrity pulse ----------
function currentStageIndex(build) {
  // Which build stage the timeline is inside: stages are courses, and a
  // course's segments occupy a contiguous run of the drop order. build is
  // elapsed time since the net finished inflating (see applySceneAtTime),
  // so the stage reported here always matches the segments actually on
  // screen.
  if (!state.bundle.staging || !state.timeline) return null;
  const stages = state.bundle.staging.stages;
  if (!stages || !stages.length) return null;
  // placementStep, the one shared stagger: the HUD's stage line and the
  // integrity pulse both hang off this number, and reading the picture
  // at a different rate once had a finished sprayed vault quoting a
  // stage still halfway down the drop order.
  const placed = Math.floor(build / placementStep());
  // Walked over the pieces, which are what actually drop, in the same order
  // the index and the picture use.
  let coursesDone = 0, count = 0;
  for (const piece of state.bundle.pieces) {
    count += 1;
    if (count > placed) break;
    coursesDone = Math.max(coursesDone, piece.course + 1);
  }
  return Math.max(0, Math.min(stages.length - 1, coursesDone - 1));
}

function applyPulse(build) {
  if (!state.layers.pulse || !state.bundle || !state.objects.shell) return;
  const index = currentStageIndex(build);
  if (index === null) return;
  const stage = state.bundle.staging.stages[index];
  // Green means the struck-now FEA solve converged, red means it did not.
  // "unavailable" (brick, tile, stone: no ananke_fea preset, see
  // staging.FEA_MATERIALS) is neither -- no solve was ever attempted, so it
  // gets a neutral grey rather than the red that would say a solve was run
  // and lost. The form finding already guarantees compression-only
  // equilibrium by construction, so a separate rigid-block lens is not
  // what this pulse is for either; see the Data panel for the CRA verdict
  // where a study happens to carry one.
  const struck = stage.struck_now;
  const unavailable = !!(struck && struck.status === "unavailable");
  const good = !!(struck && struck.converged);
  const tint = unavailable ? 0x2a2a2a : good ? 0x1a3a1a : 0x3a1a1a;
  const pulse = 0.5 + 0.5 * Math.sin(build * 4);
  for (const segment of state.objects.shell.children) {
    if (!segment.visible) continue;
    segment.material.emissive = new THREE.Color(tint);
    segment.material.emissiveIntensity = 0.4 * pulse;
  }
}

function updateHud() {
  const hud = document.getElementById("hud");
  if (!state.bundle || !state.layers.overlays) { hud.textContent = ""; return; }
  const v = state.bundle.verification;
  // The caption must name the thickness actually on screen, which is the
  // bundle's own provenance, not whatever the thickness control currently
  // reads -- those two can drift apart (a mid-run slider nudge, a still
  // loading bundle) and the HUD must never claim a thickness the shell
  // isn't built at.
  const provenanceThickness = state.bundle.provenance.thickness;
  // Same correction the size control carries and the Data panel already
  // makes in as many words: bundle.size is the size that was REQUESTED,
  // and an authored cut ignores it. The HUD is what a user reads during
  // playback, so it is the last place that may quote a target the cut on
  // screen never had.
  const sizeCaption = state.bundle.tessellation.source === "imported"
    ? "authored cut, the size control is not used"
    : Math.round(state.bundle.size * 1000) + " mm target";
  const lines = [state.bundle.export + "  (" + state.bundle.material + ", " +
    sizeCaption + ", " +
    state.bundle.pieces.length + " pieces in " +
    state.bundle.tessellation.courses + " courses)"];
  const thicknessMm = Math.round(provenanceThickness * 1000);
  let thicknessLine = "shell thickness " + thicknessMm + " mm";
  if (v && v.thickness && Math.abs(v.thickness - provenanceThickness) > 1e-9) {
    const verifiedMm = Math.round(v.thickness * 1000);
    thicknessLine += " (verified run used " + verifiedMm + " mm)";
  }
  lines.push(thicknessLine);
  if (state.taper > 0) {
    lines.push("crown taper " + Math.round(state.taper * 100) +
      "% (drawing only: the analysis used a uniform thickness)");
  }
  if (v && v.stress) {
    lines.push("peak compression " + (v.stress.peak_compression / 1e6).toFixed(2) + " MPa, utilisation " + (100 * v.stress.utilisation).toFixed(1) + "%");
    let deflectionLine = "peak deflection " + (v.displacement.peak_magnitude * 1000).toFixed(2) + " mm";
    if (v.deflection && v.deflection.span_over_deflection) {
      deflectionLine += " (1 / " + Math.round(v.deflection.span_over_deflection) + ")";
    }
    lines.push(deflectionLine);
  } else {
    lines.push("no verification run embedded yet");
  }
  const staging = state.bundle.staging;
  if (staging && staging.stages && staging.stages.length) {
    // Same build clock applySceneAtTime derives: the HUD's stage line must
    // match what is actually on screen, not run ahead during inflation.
    const build = Math.max(0, state.timeline.t - openingSeconds());
    const index = currentStageIndex(build);
    const stage = staging.stages[index === null ? staging.stages.length - 1 : index];
    lines.push("stage " + stage.stage + " of " + staging.stages.length);
    lines.push("formwork carries " + (stage.formwork_carries_newtons / 1000).toFixed(1) + " kN");
    const struck = stage.struck_now;
    // Three readings, not two: a real convergence failure ("no equilibrium
    // found") must never be the label for a material nobody ever tried to
    // solve. staging.py's FEA_MATERIALS materials (concrete, timber, ...)
    // are the only ones that reach a real runner call at all; brick, tile
    // and stone come back with struck.status "unavailable" instead, and
    // that has to read as "not available for this material", not failure.
    let struckLine;
    if (struck && struck.converged) {
      struckLine = "struck now: stands (peak tension " + (struck.peak_tension / 1e6).toFixed(2) +
        " MPa, peak compression " + (struck.peak_compression / 1e6).toFixed(2) + " MPa)";
    } else if (struck && struck.status === "unavailable") {
      struckLine = "struck now: not available for this material -- " + struck.message;
    } else {
      struckLine = "struck now: no equilibrium found -- " + (struck && struck.message ? struck.message : "no solve result");
    }
    lines.push(struckLine);
  }
  hud.textContent = lines.join("\n");
}

// The event log is UI chrome, not scene state: the purity contract below
// covers the scene functions (applyTimeline, applySceneAtTime and their
// kin), which must stay pure in t so a recording is deterministic. Reading
// the wall clock here is unrelated to that; logStudio only timestamps a
// line for the reader, it never drives anything drawn in the scene.
const eventLog = { lines: [], timer: null };

function logStudio(message) {
  const stamp = new Date().toLocaleTimeString("en-GB", { hour12: false });
  // The same line travels with any problem report: what the user did just
  // before is usually the half of the story the error message leaves out.
  recentLog.push(stamp + "  " + message);
  while (recentLog.length > 40) recentLog.shift();
  eventLog.lines.push(stamp + "  " + message);
  while (eventLog.lines.length > 7) eventLog.lines.shift();
  const element = document.getElementById("event-log");
  element.textContent = "";
  for (const line of eventLog.lines) {
    const row = document.createElement("div");
    row.textContent = line;
    element.appendChild(row);
  }
  element.classList.remove("faded");
  if (eventLog.timer) clearTimeout(eventLog.timer);
  eventLog.timer = setTimeout(() => element.classList.add("faded"), 8000);
}

const bannerState = { timer: null, remaining: 0, since: 0, level: "info" };

function showBanner(text, level = "info") {
  // Anything shown to the user in red is worth writing down: the banner
  // fades after twelve seconds and the log does not.
  if (level === "error") reportProblem(text, null);
  const banner = document.getElementById("banner");
  document.getElementById("banner-text").textContent = text;
  banner.classList.remove("hidden");
  bannerState.level = level;
  bannerState.remaining = level === "error" ? 12000 : 6000;
  if (bannerState.timer) clearTimeout(bannerState.timer);
  bannerState.since = Date.now();
  bannerState.timer = setTimeout(
    () => document.getElementById("banner").classList.add("hidden"),
    bannerState.remaining);
  logStudio(text);
}

function armBannerTimer() {
  if (bannerState.timer) clearTimeout(bannerState.timer);
  bannerState.since = Date.now();
  bannerState.timer = setTimeout(
    () => document.getElementById("banner").classList.add("hidden"),
    bannerState.remaining);
}

document.getElementById("banner-close").addEventListener("click", () =>
  document.getElementById("banner").classList.add("hidden"));
document.getElementById("banner").addEventListener("mouseenter", () => {
  if (bannerState.timer) clearTimeout(bannerState.timer);
  bannerState.remaining -= Date.now() - bannerState.since;
});
document.getElementById("banner").addEventListener("mouseleave", () => {
  if (bannerState.remaining > 0) armBannerTimer();
});

// ---------- data panel ----------
// The residual is the SINE of an angle, which docs/BENCH.md quotes in
// degrees and millimetres beside the bare number because a sine of 0.33 is
// not something a reader converts in their head. Same conversion the
// measurement script prints.
function residualDegrees(sine) {
  return Math.asin(Math.min(1, Math.max(-1, sine))) * 180 / Math.PI;
}

// Total cap points across every drawn casting: the denominator the clamped
// count is meaningless without. "137 cap points clamped" and "137 of 41265"
// are not the same statement.
function capPointCount() {
  return (state.bundle && state.bundle.pieces || []).reduce(
    (total, piece) => total + piece.mid.length, 0);
}

function renderDataPanel(v) {
  const content = document.getElementById("data-content");
  content.innerHTML = "";

  // ---------- Cut section ----------
  // A cut that dropped analysis faces, missed a joint plane, or clamped a
  // point off the surface looks identical on screen to a clean one, so
  // every field bundle.py's tessellation summary carries is disclosed here
  // rather than trusted silently. Rendered unconditionally on any loaded
  // bundle, ahead of the verification early-out below, the same reason the
  // CRA section renders ahead of it.
  const tess = state.bundle && state.bundle.tessellation;
  if (tess) {
    const cutHeading = document.createElement("h3");
    cutHeading.textContent = "Cut";
    content.appendChild(cutHeading);

    const patternLine = document.createElement("p");
    patternLine.textContent = tess.pattern + " ("
      + (tess.source === "imported" ? "imported from Grasshopper" : "generated") + ")";
    content.appendChild(patternLine);

    const sizeLine = document.createElement("p");
    sizeLine.textContent = tess.source === "imported"
      ? "no target size of its own: an authored cut ignores the size control entirely"
      : "target size " + tess.target_size + " m";
    content.appendChild(sizeLine);

    const countLine = document.createElement("p");
    countLine.textContent = tess.cells + " pieces, " + tess.courses + " courses";
    content.appendChild(countLine);

    // An authored cut whose cells carry no course lands every one of them
    // in course 0 (tessellation.from_document), so the vault collapses to
    // a single course and the drop sequence, taperAt and the stage mapping
    // all follow that collapse. The flag saying so shipped in the bundle
    // and was never rendered anywhere a user could see it.
    if (tess.courses_inferred) {
      const inferredLine = document.createElement("p");
      inferredLine.textContent = "no cell in this authored cut carried a "
        + "course, so every one was placed in course 0: the courses above "
        + "are inferred, not authored, and the drop sequence, the crown "
        + "taper and the stage mapping all read this vault as one course.";
      content.appendChild(inferredLine);
    }

    // The spec asks for boundary sub-edges per piece, before and after, in
    // BENCH.md and in the Data panel where the user can see them. The
    // bundle has carried both since pieces.py started reporting them; the
    // panel is the only place a user meets a specific loaded cut, and the
    // rim outlier is exactly the caveat it exists for.
    const fpp = tess.facets_per_piece;
    if (fpp) {
      const facetLine = document.createElement("p");
      facetLine.textContent = "facets per piece: min " + fpp.min + " / median "
        + fpp.median + " / max " + fpp.max
        + (fpp.max_course === undefined || fpp.max_course === null
          ? "" : " (the max belongs to course " + fpp.max_course + ")")
        + ". This is the number the retired ring and wedge binning's 30 to "
        + "86 boundary edges per cell compares against: a four sided "
        + "voussoir has four.";
      content.appendChild(facetLine);
    }
    const bpp = tess.boundary_points_per_piece;
    if (bpp) {
      const boundaryLine = document.createElement("p");
      boundaryLine.textContent = "boundary points per piece: min " + bpp.min
        + " / median " + bpp.median + " / max " + bpp.max
        + ". These count every subdivided boundary point rather than the "
        + "joints themselves, so read facets per piece for the headline.";
      content.appendChild(boundaryLine);
    }

    const chordLine = document.createElement("p");
    chordLine.textContent = "cap chord deviation " + tess.chord_mm.toFixed(3)
      + " mm against a 5.0 mm target, " + tess.rounds + " subdivision round(s), "
      + "limited by " + tess.limit;
    content.appendChild(chordLine);

    // The single worst-corner number badly misrepresents the cut, so the
    // whole distribution is shown, not only tess.corner_residual (which
    // stays the worst corner alone, equal to stats.max below): the median
    // is what describes a typical joint, and the max describes only its
    // own worst corner, which the studio names by course rather than
    // leaving the reader to assume it is typical.
    // Guarded, not assumed. corner_residual_stats landed late in the
    // cutting wave and REQUIRED_BUNDLE_KEYS did not name it until this
    // fix, so every machine that ran this branch mid-wave has a cached
    // bundle without it. Dereferencing stats.count on one of those threw
    // out of the Data button's click handler AFTER content.innerHTML = ""
    // and BEFORE the panel was unhidden, so the button read as doing
    // nothing at all. A missing sub-field degrades to a line saying so.
    const stats = tess.corner_residual_stats;
    if (!stats) {
      const residualMissing = document.createElement("p");
      residualMissing.textContent = "corner normal residual: not measured in "
        + "this bundle, which was cached before the distribution was "
        + "reported. Delete the cached bundle, or change any control, to "
        + "re-cut.";
      content.appendChild(residualMissing);
    } else {
      const residualWhat = document.createElement("p");
      residualWhat.textContent = "corner normal residual, over " + stats.count
        + " corners: the sine of the angle between a corner's one stored "
        + "normal and the plane of the facet that does not own it, since a "
        + "corner belongs to two joints and one normal cannot lie in both";
      content.appendChild(residualWhat);
      const residualDistribution = document.createElement("p");
      // In degrees as well as the bare sine, the way docs/BENCH.md quotes
      // it: a sine of 0.33 is not a number a reader converts in their head,
      // and the whole point of the distribution is that it can be read.
      residualDistribution.textContent = "median " + stats.median.toFixed(4)
        + " (" + residualDegrees(stats.median).toFixed(2) + " degrees)"
        + ", mean " + stats.mean.toFixed(4)
        + " (" + residualDegrees(stats.mean).toFixed(2) + " degrees)"
        + ", p99 " + stats.p99.toFixed(4)
        + " (" + residualDegrees(stats.p99).toFixed(2) + " degrees)"
        + ", max " + stats.max.toFixed(4)
        + " (" + residualDegrees(stats.max).toFixed(2) + " degrees, its own "
        + "worst corner, in course(s) " + stats.worst_corner_courses.join(", ")
        + "). The median describes the cut; the max describes only its worst "
        + "corner, which clusters with the rest of the tail in the rim course, "
        + "where the cut follows the mesh's own irregular boundary rather "
        + "than a straight chord.";
      content.appendChild(residualDistribution);
      const residualCounts = document.createElement("p");
      residualCounts.textContent = "corners over threshold: " + stats.over.map(
        function (entry) {
          return entry.count + " of " + stats.count + " over " + entry.threshold
            + " (" + residualDegrees(entry.threshold).toFixed(1) + " degrees)";
        }
      ).join(", ");
      content.appendChild(residualCounts);
    }

    // With denominators and, for the clamp, with the magnitude. The same
    // 137 clamped points are either rounding noise or ten times the 5 mm
    // chord target depending on how far they moved, which is why the
    // report carries clamped_max_m and clamped_median_m at all.
    const capPoints = capPointCount();
    const clampedLine = document.createElement("p");
    let clampedText = tess.clamped_points + " of " + capPoints
      + " cap point(s) clamped to the nearest render mesh face";
    if (typeof tess.clamped_max_m === "number"
        && typeof tess.clamped_median_m === "number") {
      clampedText += ", reaching " + (tess.clamped_max_m * 1000).toFixed(1)
        + " mm at the worst and " + (tess.clamped_median_m * 1000).toFixed(1)
        + " mm at the median";
    } else {
      clampedText += " (by how far: not measured in this cached bundle)";
    }
    clampedText += "; " + tess.missing_planes
      + " boundary facet(s) with no joint plane to project onto";
    clampedLine.textContent = clampedText;
    content.appendChild(clampedLine);

    const coverage = tess.report;
    const analysisFaces = state.bundle.analysis_mesh.faces.length;
    const coverageLine = document.createElement("p");
    coverageLine.textContent = "coverage: " + coverage.orphan_faces.length
      + " of " + analysisFaces + " analysis face(s) orphaned, "
      + coverage.double_faces.length + " doubled; of " + tess.cells
      + " cell(s), " + coverage.open_facets.length + " open facet(s), "
      + coverage.slivers.length + " sliver(s), "
      + coverage.coverage_holes.length + " coverage hole(s), "
      + coverage.broken_boundary.length + " broken boundary entrie(s)";
    content.appendChild(coverageLine);

    // A folded cell is named and nowhere excluded: it is still cut, still
    // capped and still drawn, with one lobe of its cap inside out. It
    // enters none of the counts above, so naming it here is the only way
    // anyone learns which piece on screen is the bad one.
    const folded = coverage.folded;
    const foldedLine = document.createElement("p");
    foldedLine.textContent = !folded
      ? "folded cells: not measured in this cached bundle"
      : folded.length
        ? "folded: " + folded.length + " cell(s) whose welded outline "
          + "crosses itself -- " + folded.join(", ") + ". Each is still cut, "
          + "still capped and still drawn, with one lobe of its cap inside "
          + "out, and enters none of the coverage counts above."
        : "folded: no cell's welded outline crosses itself";
    content.appendChild(foldedLine);

    if (tess.backward_turn_degrees !== null && tess.backward_turn_degrees !== undefined) {
      const wobbleLine = document.createElement("p");
      wobbleLine.textContent = tess.backward_steps + " of the plan's own rim step(s) "
        + "turn backward, " + tess.backward_turn_degrees.toFixed(3)
        + " degrees of backward turn total";
      content.appendChild(wobbleLine);
    }

    if (tess.source === "imported") {
      const provenanceLine = document.createElement("p");
      provenanceLine.textContent = "provenance: " + JSON.stringify(tess.provenance || {});
      content.appendChild(provenanceLine);
      const zLine = document.createElement("p");
      zLine.textContent = tess.z_offset_max === null || tess.z_offset_max === undefined
        ? "measured z offset against the thrust surface: unmeasured"
        : "measured z offset against the thrust surface: "
          + (tess.z_offset_max * 1000).toFixed(1) + " mm";
      content.appendChild(zLine);
    }

    const interpolationLine = document.createElement("p");
    interpolationLine.textContent = "a piece's own points are not render mesh "
      + "vertices, so every field value shown on a casting is sampled by "
      + "interpolation through the barycentric weights the cut recorded for "
      + "it, not read off a single mesh vertex directly: a heatmap value at "
      + "a point is an interpolated reading, not a lookup.";
    content.appendChild(interpolationLine);
  }

  // The CRA verdict no longer pops up: it is gone from the badge, the HUD
  // and the integrity pulse, since the form finding already guarantees
  // compression-only equilibrium by construction and no size the API
  // permits reaches the rigid-block budget in any case. The Data panel
  // keeps the honest record where a study happens to carry one, rendered
  // BEFORE the verification early-out so it still shows on a
  // staged-but-unverified study, and rendered not at all, not as an empty
  // heading, when there is no verdict to report.
  const verdict = craVerdict();
  if (verdict) {
    const craHeading = document.createElement("h3");
    craHeading.textContent = "CRA rigid-block verdict";
    content.appendChild(craHeading);
    const line = document.createElement("p");
    line.textContent = verdict.stands === true
      ? "stands as rigid blocks under friction, self-weight only"
      : verdict.stands === false
        ? "does not stand as rigid blocks (" + verdict.status + ")"
        : "not run: " + (verdict.message || verdict.status);
    content.appendChild(line);
    const mu = document.createElement("p");
    mu.textContent = FRICTION_PROVENANCE[state.bundle.material]
      || ("mu " + verdict.mu);
    content.appendChild(mu);
    const counts = document.createElement("p");
    counts.textContent = verdict.blocks + " blocks, "
      + verdict.interfaces + " contact interfaces";
    content.appendChild(counts);
    const faceted = document.createElement("p");
    faceted.textContent = "the verdict is computed on a faceted model, not "
      + "on the castings drawn here. The analysis model replaces each cell "
      + "with a single voussoir whose faces are planar, one per neighbour, "
      + "so its surface cuts the chord wherever the vault curves: it sits "
      + "inside the drawn surface, carries less volume than the cell it "
      + "stands for, and both errors grow as the segmentation coarsens. "
      + "Position is the larger of the two, and on this vault it has been "
      + "measured in metres against a shell half thickness of 0.1 m, so "
      + "the solver weighs blocks that do not sit where the vault is "
      + "shown. Neither error is quoted as a figure against what is on "
      + "screen, and the reason is that the drawing has since moved: a "
      + "casting here is projected onto its own flat joint planes, shrunk "
      + "by the joint gap and thinned by the crown taper, all in the same "
      + "dimension. The measurements in docs/BENCH.md were taken against "
      + "the mesh-following block model this viewer no longer draws, and "
      + "are a distance between two analysis models rather than a "
      + "distance to these pieces";
    content.appendChild(faceted);
    const skipped = state.bundle.staging && state.bundle.staging.cra_skipped;
    if (skipped && skipped.length) {
      const missing = document.createElement("p");
      missing.textContent = skipped.length + " piece(s) could not be modelled "
        + "as a voussoir and are absent from the rigid-block model, so this "
        + "verdict describes less than the whole vault: "
        // entry.ring/entry.wedge are voussoirs.py's own field names,
        // unchanged there by Task 7's ruling: ring is the course index and
        // wedge is the piece's position within it, not a ring/wedge polar
        // bin. The sentence a user reads says so honestly without asking
        // voussoirs.py to rename anything.
        + skipped.map(function (entry) {
            return "course " + entry.ring + " piece " + entry.wedge
              + " (" + entry.reason + ")";
          }).join("; ");
      content.appendChild(missing);
    }
  }

  // Verification content: early-out if no verification file.
  if (!v) {
    const p = document.createElement("p");
    p.textContent = "no verification run embedded yet";
    content.appendChild(p);
    return;
  }

  const heading = document.createElement("h3");
  heading.textContent = (v.export || "") + " -- " + (v.material || "");
  content.appendChild(heading);

  if (v.material_assumptions) {
    const assumptions = document.createElement("p");
    assumptions.textContent = v.material_assumptions;
    content.appendChild(assumptions);
  }

  const cross = v.cross_check;
  if (cross) {
    const reactions = document.createElement("p");
    reactions.textContent = "reactions agree: " + (cross.reactions_agree ? "yes" : "no");
    content.appendChild(reactions);
    const strict = document.createElement("p");
    strict.textContent = "strict per-member agreement: " + (cross.strict_agrees ? "yes" : "no");
    content.appendChild(strict);
    if (cross.member_note) {
      const note = document.createElement("p");
      note.textContent = cross.member_note;
      content.appendChild(note);
    }
  }

  if (v.tension_sweep && v.tension_sweep.length) {
    const label = document.createElement("p");
    label.textContent = "tension sweep";
    content.appendChild(label);
    const table = document.createElement("table");
    const head = document.createElement("tr");
    for (const text of ["factor", "peak tension (MPa)", "utilisation %", "state"]) {
      const th = document.createElement("th");
      th.textContent = text;
      head.appendChild(th);
    }
    table.appendChild(head);
    for (const row of v.tension_sweep) {
      const tr = document.createElement("tr");
      const cells = [
        row.factor,
        (row.peak_tension / 1e6).toFixed(2),
        (100 * row.utilisation).toFixed(1),
        row.tension_present ? "TENSION" : "compression",
      ];
      for (const value of cells) {
        const td = document.createElement("td");
        td.textContent = value;
        tr.appendChild(td);
      }
      table.appendChild(tr);
    }
    content.appendChild(table);
  }

  const headline = document.createElement("ul");
  if (v.displacement) {
    const li = document.createElement("li");
    li.textContent = "peak deflection " + (v.displacement.peak_magnitude * 1000).toFixed(2) + " mm";
    if (v.deflection && v.deflection.span_over_deflection) {
      li.textContent += " (1 / " + Math.round(v.deflection.span_over_deflection) + ")";
    }
    headline.appendChild(li);
  }
  if (v.stress) {
    const compression = document.createElement("li");
    compression.textContent = "peak compression " + (v.stress.peak_compression / 1e6).toFixed(2) + " MPa";
    headline.appendChild(compression);
    const utilisation = document.createElement("li");
    utilisation.textContent = "utilisation " + (100 * v.stress.utilisation).toFixed(1) + "%";
    headline.appendChild(utilisation);
  }
  if (headline.children.length) content.appendChild(headline);
}

// ---------- data plumbing ----------
async function fetchJson(url) {
  const response = await fetch(url);
  if (response.ok) return response.json();
  // The server refuses in sentences ("this plan is not star shaped about
  // its axis..."), and every one of them used to reach the banner wrapped
  // in a URL and a JSON envelope, which reads as a crash rather than as an
  // answer. The sentence is the message; the address stays in the log,
  // where a diagnosis wants it.
  const text = await response.text();
  let detail = text;
  try {
    const body = JSON.parse(text);
    if (body && typeof body.detail === "string") detail = body.detail;
  } catch (parseError) { /* not JSON: the raw text is the best there is */ }
  logStudio("request refused " + response.status + ": " + url);
  const error = new Error(detail);
  error.status = response.status;
  error.detail = detail;
  error.url = url;
  throw error;
}

// ---------- pattern control (Task 9) ----------
// generators.PLANNED and generators.MATERIAL_NOTES are the honesty
// mechanism: a pattern named in the spec but not built yet is listed and
// disabled rather than silently absent, and a material whose intended
// pattern is not built yet says so in pattern-note instead of quietly
// drawing bonded courses under the missing pattern's name.
function patternLabel(pattern) {
  // The monolithic cut IS the sprayed option now, and the control says so
  // in the builder's own words (Param: "add the sprayed option there").
  if (pattern === "monolithic-bands") return "Sprayed monolithic";
  // Sentence case, because every neighbouring control speaks it: "White
  // presentation", "Golden hour", "Per surface". Title Case here made the
  // pattern list the one Capitalised Column in the panel.
  const words = pattern.split("-").join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function populatePatternSelect(payload) {
  const select = document.getElementById("pattern-select");
  select.innerHTML = "";
  for (const pattern of payload.patterns) {
    const option = document.createElement("option");
    option.value = pattern;
    option.textContent = patternLabel(pattern);
    select.appendChild(option);
  }
  for (const pattern of Object.keys(payload.patterns_planned)) {
    const option = document.createElement("option");
    option.value = pattern;
    option.textContent = patternLabel(pattern) + " (arrives " + payload.patterns_planned[pattern] + ")";
    option.disabled = true;
    select.appendChild(option);
  }
}

// Changing the material writes the material's honesty note always, but
// only applies the material's default pattern while the user has never
// explicitly chosen one: an explicit choice (state.patternChosen) rides
// through every material change, which is what makes comparing timber
// and sprayed concrete under the same monolithic bands possible at all.
function updatePatternForMaterial(material) {
  if (!state.patternChosen) {
    const pattern = state.patternDefaults[material] || state.pattern;
    state.pattern = pattern;
    document.getElementById("pattern-select").value = pattern;
  }
  document.getElementById("pattern-note").textContent = state.patternNotes[material] || "";
}

// A commit whose requested parameters equal what the loaded bundle
// already answers issues no request at all. bundle.size is the REQUESTED
// size by bundle.py's own contract, so this comparison is honest for
// authored cuts too, where the size is requested and then unused.
function requestMatchesLoaded(material) {
  const loaded = state.bundle;
  return !!loaded
    && loaded.export === document.getElementById("study-select").value
    && loaded.material === material
    && loaded.pattern === state.pattern
    && loaded.size === state.size
    && loaded.provenance.thickness === state.thickness;
}

// Size and thickness commits settle before they cut: stepping a slider
// five times costs one request, RELOAD_SETTLE_MS after the last step.
// The selects commit immediately; they share the token, not the timer.
const RELOAD_SETTLE_MS = 1500;

function scheduleReload() {
  if (state.reloadTimer) clearTimeout(state.reloadTimer);
  state.reloadTimer = setTimeout(() => {
    state.reloadTimer = null;
    const select = document.getElementById("study-select");
    const material = document.getElementById("material-select").value;
    if (!select.value || requestMatchesLoaded(material)) return;
    loadStudy(select.value);
  }, RELOAD_SETTLE_MS);
}

// One fill of the study select, shared by boot and the delete button. A
// null selection leaves the choice to the caller; "" leaves the select
// blank with a placeholder so a just-deleted study is not silently
// replaced by whichever study sorts first.
function populateStudySelect(studies, selection) {
  const select = document.getElementById("study-select");
  select.innerHTML = "";
  if (selection === "") {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "(no study selected)";
    select.appendChild(blank);
  }
  const names = [];
  for (const study of studies) {
    const option = document.createElement("option");
    option.value = study.export;
    option.textContent = study.export + (study.has_verification ? " (verified)" : "");
    select.appendChild(option);
    names.push(study.export);
  }
  if (selection !== null) select.value = selection;
  return names;
}

async function loadStudy(exportName) {
  // Another study is another scene: yesterday's undos would put things
  // back into a picture that is no longer on screen.
  clearUndoHistory();
  // An immediate load supersedes a pending settle timer: without this, a
  // size commit followed within the settle window by a material, pattern
  // or study change fires two full server cuts instead of one.
  if (state.reloadTimer) { clearTimeout(state.reloadTimer); state.reloadTimer = null; }
  const material = document.getElementById("material-select").value;
  // The incoming material's own stored appearance (or the defaults, if it
  // has none) must be in place before the pieces below are built, or the
  // first frame of a material switch briefly shows the PREVIOUS material's
  // tint, finish and skin.
  restoreAppearance(material);
  // The token: whoever increments last owns the screen. A response that
  // comes back to find a newer sequence number is dropped silently, so
  // two overlapping cuts can never race each other onto the canvas.
  const sequence = ++state.loadSequence;
  // Reported back so a caller that CHANGED something to trigger this
  // load can put its control back when the load was refused.
  let loaded = false;
  const status = document.getElementById("cut-status");
  const overlay = document.getElementById("cut-overlay");
  const materialLabel = document.querySelector(
    '#material-select option[value="' + material + '"]').textContent;
  status.textContent = "cutting " + materialLabel + ", " + patternLabel(state.pattern) + ", "
    + Math.round(state.size * 1000) + " mm pieces at "
    + Math.round(state.thickness * 1000) + " mm...";
  overlay.classList.remove("hidden");
  // Cut timing: the elapsed time reuses the very pieces the "cutting..."
  // status text above already assembled (materialLabel, the pattern, the
  // size) rather than recomputing them a second way.
  const startedAt = Date.now();
  let url = "/api/studies/" + encodeURIComponent(exportName) +
    "/bundle?material=" + material + "&pattern=" + encodeURIComponent(state.pattern) +
    "&size=" + state.size + "&thickness=" + state.thickness;
  // Omitted entirely when null, so the server applies its own default
  // (the Skin when the study has one). Sending a source the study cannot
  // offer is a 400 that names the problem, which is what the control's
  // own note is for.
  if (state.source) url += "&source=" + encodeURIComponent(state.source);
  try {
    // Fetched alongside the bundle: a missing or unpaired formwork
    // document is an expected state (404 with the reason), never a load
    // failure, so it resolves to null instead of throwing.
    const formworkPromise = fetch(
      "/api/studies/" + encodeURIComponent(exportName) + "/formwork")
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
    const fresh = await fetchJson(url);
    if (sequence !== state.loadSequence) return "superseded";
    // Held locally until this load is confirmed the winner: assigned
    // before the check, a superseded load clobbered the winning study's
    // formwork with its own.
    const formwork = await formworkPromise;
    if (sequence !== state.loadSequence) return "superseded";
    state.formwork = formwork;
    overlay.classList.add("hidden");
    status.textContent = "";
    // Same export means the user is comparing settings, not changing
    // subject: the viewing state survives the swap. Captured HERE, before
    // buildScene replaces state.bundle, because timelineDuration reads
    // the old bundle's piece count and cannot be asked afterwards.
    const preserve = state.bundle && state.timeline
      && state.bundle.export === fresh.export
      ? { f: state.timeline.t / timelineDuration(), playing: state.timeline.playing }
      : null;
    // BEFORE buildScene: the scene's first applySceneAtTime already runs
    // with formworkSeconds() > 0, hiding the instanced wires for the act,
    // so the act's own objects have to exist by then or the viewport
    // opens empty until the first play.
    rebuildFormworkObjects();
    buildScene(fresh, preserve);
    await reloadColumns(columnsForStudy(state.columnFiles || [], exportName));
    loaded = true;
    logStudio("loaded " + exportName + " (" + materialLabel + ", "
      + patternLabel(state.pattern) + ", " + state.size + " m) in "
      + ((Date.now() - startedAt) / 1000).toFixed(1) + "s");
  } catch (error) {
    if (sequence !== state.loadSequence) return;
    overlay.classList.add("hidden");
    status.textContent = "";
    state.lastRefusal = error.detail || error.message;
    showBanner("Failed to load study: " + error.message, "error");
    // A failed SWITCH leaves the previous study's scene on screen, and
    // the source row would otherwise sit there labelled with that
    // study's Skin against a study that never loaded.
    if (!state.bundle || state.bundle.export !== exportName) {
      const row = document.getElementById("source-row");
      if (row) row.classList.add("hidden");
    }
  }
  return loaded;
}

async function boot(preferredExport) {
  applyEnvironment();
  try {
    const payload = await fetchJson("/api/studies");
    state.studies = payload.studies;
    state.patterns = payload.patterns;
    state.patternDefaults = payload.pattern_defaults;
    state.patternNotes = payload.pattern_notes;
    populatePatternSelect(payload);
    updatePatternForMaterial(document.getElementById("material-select").value);
    const names = populateStudySelect(payload.studies, null);
    const select = document.getElementById("study-select");
    // M2 fix: after an export-pair import, boot() must land on the export
    // that was just imported, not silently fall back to studies[0]. The
    // preferred name only wins when it actually exists in the fresh list
    // (an incomplete pair, for instance, never appears here at all).
    // Where the studio was left, if it was left anywhere that still
    // exists. An explicitly preferred export still wins: that is a fresh
    // import asking to be shown, which beats a memory of yesterday.
    const remembered = preferredExport ? null : rememberedSession();
    const toLoad = preferredExport && names.includes(preferredExport)
      ? preferredExport
      : (names.length ? names[0] : null);
    if (remembered && names.includes(remembered.study)) {
      select.value = remembered.study;
      state.columnFiles = payload.columns || [];
      // The whole record, not just the name: applyScene loads the study
      // once with the remembered cut and then puts the floor, the light
      // and the camera back, in that order.
      const restored = await applyScene(remembered);
      if (restored === false && toLoad) {
        // The remembered cut may no longer be possible: the Skin could
        // have gone, or the study could have been re-exported with a plan
        // the studio's own cutter refuses. Fall back to opening it plainly.
        logStudio("could not reopen where we left off; opening " + toLoad);
        select.value = toLoad;
        await loadStudy(toLoad);
      }
    } else if (toLoad) {
      select.value = toLoad;
      await loadStudy(toLoad);
    }
    state.columnFiles = payload.columns || [];
    await reloadColumns(columnsForStudy(state.columnFiles, document.getElementById("study-select").value));
  } catch (error) {
    // The error object, not just its message: a banner-sourced report
    // carries no stack, and "Cannot set properties of null" without one is
    // a symptom with nowhere to look. The diagnostics log is for finding
    // things, so it gets the whole error.
    reportProblem("boot failed: " + error.message, error);
    showBanner("Server not reachable: " + error.message, "error");
  }
}

// ---------- the folder the vaults are read from ----------
// The studio reads one folder. Choosing it opens the native Windows dialog
// on the server, because a browser cannot be made to hand over a path: file
// inputs withhold it by design, and here the server and the browser are the
// same machine anyway.
async function showFolder() {
  const row = document.getElementById("folder-path");
  try {
    const folder = await fetchJson("/api/folder");
    // The tail of the path, which is the part that says where you are. The
    // whole thing is on the tooltip for anyone who wants it.
    const parts = folder.path.split(/[\\/]/).filter(Boolean);
    row.textContent = parts.length > 2
      ? "..." + parts.slice(-2).join("/") : folder.path;
    row.title = folder.path + " (" + folder.studies + " vaults)";
    return folder;
  } catch (error) {
    row.textContent = "could not read the folder";
    return null;
  }
}

// Re-read the folder and refill the vault list, keeping the vault on screen
// selected if it is still there. This is what the Refresh button is for:
// new saves appear without a page reload.
async function refreshStudies(preferred) {
  const payload = await fetchJson("/api/studies");
  state.studies = payload.studies;
  state.columnFiles = payload.columns || [];
  const select = document.getElementById("study-select");
  const wanted = preferred || select.value;
  const names = populateStudySelect(payload.studies, null);
  if (names.includes(wanted)) select.value = wanted;
  await showFolder();
  return names;
}

document.getElementById("folder-choose").addEventListener("click", async () => {
  const status = document.getElementById("import-status");
  status.textContent = "waiting for the folder dialog...";
  let chosen = null;
  try {
    chosen = (await (await fetch("/api/folder/browse", { method: "POST" })).json()).path;
  } catch (error) {
    status.textContent = "the folder dialog could not be opened";
    return;
  }
  if (!chosen) { status.textContent = "no folder chosen"; return; }
  const response = await fetch("/api/folder", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path: chosen }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    status.textContent = "not a folder: " + (body.detail || response.status);
    return;
  }
  const folder = await response.json();
  logStudio("reading vaults from " + folder.path);
  status.textContent = folder.studies + " vaults in this folder";
  // The vault on screen came from the old folder and may not exist in the
  // new one, so the scene is emptied rather than left standing under a
  // list it no longer belongs to.
  clearScene();
  liveStamps = null;
  const names = await refreshStudies(null);
  if (names.length) {
    document.getElementById("study-select").value = names[0];
    await loadStudy(names[0]);
  }
});

document.getElementById("study-refresh").addEventListener("click", async () => {
  const names = await refreshStudies(null);
  logStudio("folder re-read: " + names.length + " vaults");
});

// The hand-upload path is gone with its controls (Param, 2026-09-04: the
// folder is the way in now, and a second way in that nobody uses is one
// more thing to read past). putFile, importExportPair and importColumns
// lived here; the routes they called are still there for the exporter,
// which is their real caller.

// ---------- UI wiring ----------
document.getElementById("delete-study").addEventListener("click", async () => {
  const select = document.getElementById("study-select");
  const name = select.value;
  if (!name) return;
  if (!window.confirm("Delete the study \"" + name + "\" and its files?")) return;
  const response = await fetch("/api/uploads/exports/" + encodeURIComponent(name),
    { method: "DELETE" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    showBanner("Delete refused: " + (body.detail || response.status), "error");
    return;
  }
  logStudio("deleted " + name);
  clearScene();
  const payload = await fetchJson("/api/studies");
  state.studies = payload.studies;
  populateStudySelect(payload.studies, "");
});

// Clear scene: deselect everything and empty the viewport without
// touching any file. Selecting a study again brings it straight back.
function clearScene() {
  state.source = null;
  state.formwork = null;
  state.bundle = null;
  selectProp(null);
  rebuildFormworkObjects();
  disposeShell();
  disposeWiresAndNodes();
  for (const key of Object.keys(state.objects)) {
    const object = state.objects[key];
    if (object) scene.remove(object);
    state.objects[key] = null;
  }
  const select = document.getElementById("study-select");
  select.value = "";
  const row = document.getElementById("source-row");
  if (row) row.classList.add("hidden");
}
// clearScene has no button any more: two buttons named Clear sat a row
// apart, and this one emptied the whole viewport when Param wanted props
// gone. It remains the study-switching primitive above.

// LIVE: poll the studies list and reload the moment the loaded study's
// files change on disk, which is exactly what a Grasshopper Live push
// does. The dot glows while polling sees a fresh stamp arrive.
// Every study's stamp as of the last poll. Live is not "reload the study I
// am looking at" any more: it follows Grasshopper, so a push to a DIFFERENT
// vault brings that vault up, which is what a live link to a modeller means
// (Param: "when live mode is turned on in the grasshopper and we had a
// different vault loaded or same one even, these parameters change to show
// for the live model").
let liveStamps = null;
let liveFlash = 0;
function paintLive(fresh) {
  const button = document.getElementById("live-toggle");
  if (!button) return;
  if (fresh) liveFlash = Date.now() + 1200;
  const flaring = state.live && Date.now() < liveFlash;
  button.className = state.live ? (flaring ? "on fresh" : "on") : "off";
  button.title = state.live
    ? "Live: this study reloads as Grasshopper pushes it. Click to stop following."
    : "Live is off: Grasshopper pushes are ignored. Click to follow again.";
}
document.getElementById("live-toggle").addEventListener("click", () => {
  state.live = !state.live;
  // The stamps are forgotten on the way back in, so switching Live on
  // adopts whatever is on disk NOW as the baseline rather than chasing
  // every push that happened while nobody was watching.
  liveStamps = null;
  paintLive(false);
  logStudio(state.live ? "live: following Grasshopper" : "live: off");
});
paintLive(false);
setInterval(async () => {
  const select = document.getElementById("study-select");
  if (!state.live) { paintLive(false); return; }
  try {
    const payload = await fetchJson("/api/studies");
    state.studies = payload.studies;
    state.columnFiles = payload.columns || [];
    const stamps = {};
    for (const row of payload.studies) stamps[row.export] = row.stamp;
    if (liveStamps === null) {
      // First look: adopt what is on disk as the baseline. Without this,
      // opening the studio would reload every study it has never seen.
      liveStamps = stamps;
      paintLive(false);
      return;
    }
    // The newest push wins. A vault that has just appeared counts as
    // pushed: that is what a first Live send from Grasshopper looks like
    // from this side.
    let pushed = null;
    for (const [name, stamp] of Object.entries(stamps)) {
      const before = liveStamps[name];
      if (before === undefined || stamp > before) {
        if (!pushed || stamp > stamps[pushed]) pushed = name;
      }
    }
    liveStamps = stamps;
    if (!pushed) { paintLive(false); return; }
    paintLive(true);
    if (pushed === select.value) {
      logStudio("live: " + pushed + " changed in Grasshopper, reloading");
      await loadStudy(pushed);
    } else {
      // A different vault than the one on screen: follow it, because Live
      // means "show me what Grasshopper is working on".
      logStudio("live: following Grasshopper to " + pushed);
      select.value = pushed;
      state.source = null;
      await loadStudy(pushed);
    }
  } catch (error) { /* the next tick retries */ }
}, 2000);

document.getElementById("study-select").addEventListener("change", (e) => {
  // A source choice belongs to the study it was made on. Carried across,
  // the previous study's "authored" rode into the next study's request
  // and 400'd every study without a Skin: basic navigation broke after
  // opening one Skin study. Null means "whatever this study has".
  state.source = null;
  loadStudy(e.target.value);
});
// Set while a SKIN choice is driving the structural material, so the
// change handler below keeps the appearance the user just chose instead of
// restoring the one this material remembered -- without the flag, choosing
// copper flipped material to concrete, whose memory restored last week's
// brick, which flipped material to brick, wearing the wrong skin.
let skinDrivenMaterialChange = false;

document.getElementById("material-select").addEventListener("change", (e) => {
  if (skinDrivenMaterialChange) {
    skinDrivenMaterialChange = false;
    // The just-chosen appearance becomes this material's memory.
    persistAppearance();
  } else {
    // Same rule as loadStudy: the incoming material's stored appearance is
    // restored before anything is rebuilt, never after.
    restoreAppearance(e.target.value);
  }
  updatePatternForMaterial(e.target.value);
  const select = document.getElementById("study-select");
  if (select.value && !requestMatchesLoaded(e.target.value)) loadStudy(select.value);
});
// The search filters the grid as it is typed. It matches "family/name" as
// one string, which is how the QS picker does it and is what a person means
// when they type "brick stock".
{
  const search = document.getElementById("skin-search");
  if (search) search.addEventListener("input", () => buildSkinTiles());
}

// One handler for every library folder. The vault folder proved the shape
// and it is copied rather than reinvented: browse without setting, so the
// validating and the remembering live in one place; the tail of the path,
// because the end of a path is the part worth reading; and a failure that
// says which of the two steps failed.
async function showLibraryFolder(kind, rowId, unit) {
  const row = document.getElementById(rowId);
  if (!row) return;
  try {
    const folder = await fetchJson("/api/" + kind + "/folder");
    if (!folder.path) { row.textContent = "no folder chosen"; return; }
    const parts = folder.path.split(/[\\/]/).filter(Boolean);
    row.textContent = parts.length > 2
      ? "..." + parts.slice(-2).join("/") : folder.path;
    row.title = folder.path + " (" + folder.count + " " + unit + ")";
  } catch (error) {
    row.textContent = "could not read the folder";
  }
}

async function chooseLibraryFolder(kind, rowId, unit, afterwards) {
  const row = document.getElementById(rowId);
  row.textContent = "waiting for the folder dialog...";
  let chosen = null;
  try {
    chosen = (await (await fetch("/api/" + kind + "/folder/browse",
      { method: "POST" })).json()).path;
  } catch (error) {
    row.textContent = "the folder dialog could not be opened";
    return;
  }
  if (!chosen) { await showLibraryFolder(kind, rowId, unit); return; }
  const response = await fetch("/api/" + kind + "/folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: chosen }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    row.textContent = "not a folder: " + (body.detail || response.status);
    return;
  }
  await afterwards();
  await showLibraryFolder(kind, rowId, unit);
}

async function showMaterialFolder() {
  const row = document.getElementById("material-folder-path");
  if (!row) return;
  try {
    const folder = await fetchJson("/api/materials/folder");
    if (!folder.path) { row.textContent = "no folder chosen"; return; }
    const parts = folder.path.split(/[\\/]/).filter(Boolean);
    row.textContent = parts.length > 2
      ? "..." + parts.slice(-2).join("/") : folder.path;
    row.title = folder.path + " (" + folder.count + " materials)";
  } catch (error) {
    row.textContent = "could not read the folder";
  }
}

document.getElementById("material-folder-choose").addEventListener("click", async () => {
  const row = document.getElementById("material-folder-path");
  row.textContent = "waiting for the folder dialog...";
  let chosen = null;
  try {
    chosen = (await (await fetch(
      "/api/materials/folder/browse", { method: "POST" })).json()).path;
  } catch (error) {
    row.textContent = "the folder dialog could not be opened";
    return;
  }
  if (!chosen) { await showMaterialFolder(); return; }
  const response = await fetch("/api/materials/folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: chosen }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    row.textContent = "not a folder: " + (body.detail || response.status);
    return;
  }
  // Everything currently loaded came out of the OLD folder, so it goes:
  // a material cached under "brick/stock-red" from one library is not the
  // same material as "brick/stock-red" in another.
  for (const [key, set] of libraryCache) {
    if (key !== state.appearance.skin) disposeLibraryMaterial(set);
  }
  libraryCache.clear();
  await refreshMaterialLibrary();
  await showMaterialFolder();
});

// The ground's own folder, on the generic machinery. Its afterwards
// disposes the GROUND set, not the skin cache: loadGroundMaterial bypasses
// libraryCache entirely.
document.getElementById("ground-folder-choose").addEventListener("click", () =>
  chooseLibraryFolder("ground-materials", "ground-folder-path", "materials",
    async () => {
      if (groundLibrarySet) {
        disposeLibraryMaterial(groundLibrarySet);
        groundLibrarySet = null;
      }
      await refreshMaterialLibrary();
      rebuildGround();
    }));

// Relief and occlusion are properties of the MATERIAL, not of a piece, so
// they are written straight onto the loaded sets: no texture is re-uploaded
// and no piece mesh is rebuilt, which is why they can move live.
function applySurfaceControls() {
  for (const set of libraryCache.values()) {
    setSurface(set, state.relief, state.occlusion);
  }
  // The floor's relief is its own dial now (state.ground.relief), so the
  // vault's Relief slider no longer flattens or deepens the paving.
  setSurface(groundLibrarySet, state.ground.relief, state.occlusion);
  document.getElementById("material-relief-value").textContent =
    Math.round(state.relief * 10);
  document.getElementById("material-occlusion-value").textContent =
    Math.round(state.occlusion * 100);
}

// Restarting, without a terminal. The page does not reload when the socket
// answers again -- it reloads when the BUILD it is told has changed, which
// is the difference between "the server is up" and "the server is the one I
// asked for". A restart that came back on the old build would put us
// straight back in the fault this button exists to end.
document.getElementById("restart-studio").addEventListener("click", async () => {
  const button = document.getElementById("restart-studio");
  const status = document.getElementById("restart-status");
  // Asked BEFORE the restart, because both halves of "did it come back"
  // are answers to questions about the old process.
  let before = { build: "", pid: null };
  try {
    before = await (await fetch("/api/health", { cache: "no-store" })).json();
  } catch (error) {
    /* no answer now means no comparison later; the timeout will say so */
  }
  button.disabled = true;
  status.textContent = "restarting...";
  try {
    const asked = await fetch("/api/restart", { method: "POST" });
    // A 404 is not a network error and sails straight past a catch. A
    // server old enough to lack this route cannot restart itself, and
    // waiting forty seconds for it to is the wrong thing to do next.
    if (asked.status === 404) {
      button.disabled = false;
      status.textContent = "this server is older than the button; "
        + "close its window and start it again";
      return;
    }
  } catch (error) {
    // The connection dropping IS the restart, on a server that got as far
    // as replacing itself before answering. Carry on and wait for it.
  }
  const deadline = Date.now() + 40000;
  while (Date.now() < deadline) {
    await new Promise((wake) => setTimeout(wake, 500));
    let health = null;
    try {
      health = await (await fetch("/api/health", { cache: "no-store" })).json();
    } catch (error) {
      status.textContent = "waiting for the server...";
      continue;
    }
    // A different PROCESS is what a restart produces. A different build is
    // what an EDIT produces, and a restart with nothing changed on disk
    // gives the first and not the second: waiting only for the build left
    // the page saying "waiting for the new build" through a restart that
    // had already happened.
    const replaced = health
      && ((health.pid && health.pid !== before.pid)
        || (health.build && health.build !== before.build));
    if (replaced) {
      status.textContent = "reloading";
      location.reload();
      return;
    }
    status.textContent = "the old server is still answering...";
  }
  button.disabled = false;
  status.textContent = "it did not come back; start it from the shortcut";
});

// Stopping, from anywhere. The desktop can end the server from a shortcut;
// a laptop or a phone on the tailnet can only ask the server itself, so the
// button exists on the page. Success is the health check going QUIET, the
// mirror image of the restart above -- with one twist: through the tailnet
// proxy a dead server still gets the page a reply, a 502 from the proxy
// itself, so "not ok" has to count as quiet alongside "no connection".
document.getElementById("stop-studio").addEventListener("click", async () => {
  if (!window.confirm("Stop the studio server? Every open page loses it "
      + "until the server is started again.")) return;
  const button = document.getElementById("stop-studio");
  const status = document.getElementById("restart-status");
  button.disabled = true;
  status.textContent = "stopping...";
  try {
    const asked = await fetch("/api/stop", { method: "POST" });
    if (asked.status === 404) {
      button.disabled = false;
      status.textContent = "this server is older than the button; "
        + "stop it from the desktop";
      return;
    }
  } catch (error) {
    // The connection dropping IS the stop, on a server that got as far as
    // exiting before answering. Carry on and confirm the quiet below.
  }
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    await new Promise((wake) => setTimeout(wake, 500));
    try {
      const health = await fetch("/api/health", { cache: "no-store" });
      if (!health.ok) throw new Error("the proxy answered for a dead server");
      status.textContent = "the server is still answering...";
    } catch (error) {
      status.textContent = "stopped";
      // The gesture reverses in place: the button that stopped the server
      // gives its seat to the one that starts it (Param: "if i stop the
      // server we need a ztart server too").
      button.hidden = true;
      button.disabled = false;
      document.getElementById("start-studio").hidden = false;
      return;
    }
  }
  button.disabled = false;
  status.textContent = "it would not stop; end it from the desktop";
});

// Starting again, from the page that stopped it. The studio is gone, but
// the waker on the desktop is not, and it answers in two places: at this
// origin's /start mount when the page came through the tailnet, and on
// its own loopback port when the page is the desktop's. Both are knocked
// and neither answer is read -- the knock is the message -- then the page
// waits for its own server to answer again and reloads onto it. The
// waker's spawn cooldown makes the double knock a single launch.
document.getElementById("start-studio").addEventListener("click", async () => {
  const button = document.getElementById("start-studio");
  const status = document.getElementById("restart-status");
  button.disabled = true;
  status.textContent = "asking the desktop to start the studio...";
  fetch("/start", { cache: "no-store" }).catch(() => {});
  fetch("http://127.0.0.1:8611/start", { mode: "no-cors", cache: "no-store" })
    .catch(() => {});
  const deadline = Date.now() + 100000;
  while (Date.now() < deadline) {
    await new Promise((wake) => setTimeout(wake, 800));
    try {
      const reply = await fetch("/api/health", { cache: "no-store" });
      if (!reply.ok) throw new Error("the proxy answered for a dead server");
      const health = await reply.json();
      if (health && health.studio) {
        status.textContent = "reloading";
        location.reload();
        return;
      }
    } catch (error) {
      status.textContent = "waiting for the server...";
    }
  }
  button.disabled = false;
  status.textContent = "the desktop did not answer; use the Vaulted shortcut";
});

// The banner folds away on its own handle (Param: "a little tile arrow
// attached to the mid left side of the banner"). The state is a body
// class so the panel, the tab rail, the handle and the log all move on
// CSS alone, and it is remembered per browser: an iPad that collapsed
// the panel to look at the vault gets it back collapsed.
function applyPanelCollapsed(collapsed) {
  document.body.classList.toggle("panel-collapsed", collapsed);
  const handle = document.getElementById("panel-collapse");
  handle.textContent = collapsed ? "‹" : "›";
  handle.title = collapsed ? "Open the panel" : "Collapse the panel";
}

document.getElementById("panel-collapse").addEventListener("click", () => {
  const collapsed = !document.body.classList.contains("panel-collapsed");
  applyPanelCollapsed(collapsed);
  try {
    localStorage.setItem("panel-collapsed", collapsed ? "1" : "");
  } catch (error) { /* a browser without storage still gets the fold */ }
});

try {
  applyPanelCollapsed(localStorage.getItem("panel-collapsed") === "1");
} catch (error) { /* open, the default */ }

document.getElementById("material-relief").addEventListener("input", (e) => {
  state.relief = +e.target.value;
  applySurfaceControls();
});

document.getElementById("material-occlusion").addEventListener("input", (e) => {
  state.occlusion = +e.target.value;
  applySurfaceControls();
});

document.getElementById("hdri-folder-choose").addEventListener("click", () =>
  chooseLibraryFolder("hdri", "hdri-folder-path", "skies", async () => {
    // The sky on screen came out of the old folder, so it goes with it.
    if (state.hdriTexture) { state.hdriTexture.dispose(); state.hdriTexture = null; }
    if (state.hdriBackdrop) { state.hdriBackdrop.dispose(); state.hdriBackdrop = null; }
    state.hdriName = null;
    disposeHdriDome();
    const files = await refreshHdriList(null);
    if (files && files.length) await loadHdri(files[0]);
    else applyEnvironment();
  }));

document.getElementById("props-folder-choose").addEventListener("click", () =>
  chooseLibraryFolder("props", "props-folder-path", "models", async () => {
    // Every template belongs to the old folder. Placed props keep standing
    // until a study is reloaded, which is the honest behaviour: they are in
    // the scene, and the scene has not been asked to change.
    propTemplates.clear();
    propTemplatePromises.clear();
    await loadPropLibrary();
  }));

document.getElementById("render-skin").addEventListener("change", async (e) => {
  state.appearance.skin = e.target.value;
  persistAppearance();
  // The skin now decides the structural material (the weight system): a
  // brick skin cuts and weighs as brick, a limestone one as stone. The
  // sprayed variant is the Pattern control's call, so it is respected.
  const derived = structuralClassFor(state.appearance.skin);
  const structural = document.getElementById("material-select");
  if (structural.value !== derived) {
    skinDrivenMaterialChange = true;
    structural.value = derived;
    structural.dispatchEvent(new Event("change"));
  }
  updateWeightNote();
  // A library material has to arrive before it can be worn. rebuildAppearance
  // is called either way: once now, so the panel and the log keep up, and
  // again when the textures land.
  if (isLibraryKey(state.appearance.skin)) {
    const set = await ensureLibraryMaterial(state.appearance.skin);
    if (set) {
      const entry = set.entry;
      logStudio("wearing " + entry.label + (entry.tileMetres
        ? " at " + Math.round(entry.tileMetres[0] * 1000) + " x "
          + Math.round(entry.tileMetres[1] * 1000) + " mm"
        : " at an unknown size, laid at "
          + Math.round(DEFAULT_TILE_METRES * 1000) + " mm"));
    }
  }
  rebuildAppearance();
});
document.getElementById("material-tint").addEventListener("change", (e) => {
  state.appearance.tint = e.target.value;
  persistAppearance();
  rebuildAppearance();
});
document.getElementById("material-variation").addEventListener("input", (e) => {
  document.getElementById("material-variation-value").textContent = Math.round(+e.target.value * 100);
});
document.getElementById("material-variation").addEventListener("change", (e) => {
  state.appearance.variation = +e.target.value;
  persistAppearance();
  rebuildAppearance();
});
document.getElementById("material-grain").addEventListener("change", (e) => {
  state.appearance.grain = e.target.checked;
  persistAppearance();
  rebuildAppearance();
  logStudio(e.target.checked
    ? "grain matched: the picture runs up the slope of each voussoir"
    : "grain freed: back to the hashed quarter-turn deal");
});
document.getElementById("uv-randomise").addEventListener("click", () => {
  // A new deal, not an increment: pressing it twice should not walk back
  // through the same sequence.
  state.appearance.uvSeed = Math.floor(Math.random() * 1e9);
  persistAppearance();
  rebuildAppearance();
  logStudio("texture windows re-dealt across the voussoirs");
});
document.getElementById("material-finish").addEventListener("input", (e) => {
  document.getElementById("material-finish-value").textContent = Math.round(+e.target.value * 100);
});
document.getElementById("material-finish").addEventListener("change", (e) => {
  state.appearance.finish = +e.target.value;
  persistAppearance();
  rebuildAppearance();
});
document.getElementById("material-reset").addEventListener("click", () => {
  state.appearance = { tint: null, finish: null, skin: "none" };
  localStorage.removeItem(appearanceStorageKey(document.getElementById("material-select").value));
  syncAppearanceControls();
  rebuildAppearance();
});
// Exactly the pattern select's shape, and for the same reason: the cut
// source is a server-side cut parameter, so changing it re-requests the
// bundle rather than touching the scene.
document.getElementById("source-toggle").addEventListener("change", async (e) => {
  const previous = state.source;
  state.source = e.target.checked ? "generated" : "authored";
  const study = document.getElementById("study-select");
  if (!study.value) return;
  const loaded = await loadStudy(study.value);
  if (loaded === false) {
    // A source can exist and still be uncuttable: this vault's plan is
    // not star shaped, so the studio's polar generator refuses it by
    // name and only the Skin can cut it. The control goes back to the cut
    // still on screen rather than sitting on a source the study never
    // loaded, and the refusal is written under the control, where it
    // stays after the banner has gone rather than reading as a fault.
    state.source = previous;
    e.target.checked =
      (state.bundle ? state.bundle.source : previous) === "generated";
    if (state.lastRefusal) logStudio("skin refused: " + state.lastRefusal);
  }
});
document.getElementById("pattern-select").addEventListener("change", (e) => {
  state.pattern = e.target.value;
  state.patternChosen = true;
  // The sprayed distinction lives HERE now, as Param asked: choosing the
  // monolithic pattern makes the cut sprayed concrete; leaving it hands
  // the material back to whatever the skin implies.
  const structural = document.getElementById("material-select");
  const derived = structuralClassFor(state.appearance.skin);
  if (structural.value !== derived) {
    skinDrivenMaterialChange = true;
    structural.value = derived;
    structural.dispatchEvent(new Event("change"));
    updateWeightNote();
    return;                      // the material change reloads if needed
  }
  updateWeightNote();
  const select = document.getElementById("study-select");
  if (select.value && !requestMatchesLoaded(structural.value)) loadStudy(select.value);
});
// Exactly the thickness slider's shape, and for the same reason: the piece
// size is a property of the BUNDLE, not of the client. "input" only moves
// the live label, "change" (drag release) commits the value; re-cutting
// client-side while the drawn pieces stay at the old size is what used to
// orphan piece keys and stop the render loop. The commit itself goes
// through scheduleReload's settle window rather than asking the server
// directly.
document.getElementById("size-slider").addEventListener("input", (e) => {
  document.getElementById("size-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("size-slider").addEventListener("change", (e) => {
  state.size = +e.target.value;
  scheduleReload();
});
document.getElementById("thickness-input").addEventListener("input", (e) => {
  document.getElementById("thickness-value").textContent = Math.round(+e.target.value * 1000);
  // The weight readout tracks the drag live: it is the number the
  // thickness is being chosen FOR.
  state.thickness = +e.target.value;
  updateWeightNote();
});
document.getElementById("thickness-input").addEventListener("change", (e) => {
  state.thickness = +e.target.value;
  updateWeightNote();
  scheduleReload();
});
// The joint gap and the crown taper lost their controls in the Skin panel
// rework. The gap is a hairline constant (state.jointGap) and the taper is
// pinned at zero until it can drive the thickness the analysis uses rather
// than only the drawing. Both are still read by buildPieceMeshes, so
// bringing either back is a control and a handler, not an engine change.
// Sun slider input moves the light and the sky uniform live (cheap);
// the PMREM ambient catches up on release, and only in sky mode, where
// the sky is what the environment is made of.
for (const id of ["sun-azimuth", "sun-elevation"]) {
  document.getElementById(id).addEventListener("input", applySunFromSliders);
  document.getElementById(id).addEventListener("change", () => {
    if (state.environmentMode === "sky") regenerateEnvironment();
  });
}
// F1: state.sunElevationSetting tracks only what the slider itself was set
// to by hand. applyDayCycle also writes this same slider's value (clamped
// to its min="5" for display -- see applyDayCycle), and that write must
// NOT feed back into the day cycle's own peak, or the peak degrades toward
// the slider's floor a little more on every play. This listener is the
// only writer of state.sunElevationSetting.
document.getElementById("sun-elevation").addEventListener("input", (e) => {
  state.sunElevationSetting = +e.target.value;
});
// S5: the colour input owns the light's colour outright once touched;
// applyEnvironment's preset writes check the override before setting
// sun.color, so this survives an environment/background redraw until the
// next weather-preset change, which nulls it (colour only, no PMREM: the
// sky uniform and the studio room environment neither one reads sun.color).
document.getElementById("sun-colour").addEventListener("input", (e) => {
  state.sunColourOverride = e.target.value;
  sun.color.set(e.target.value);
});
document.getElementById("background-tone").addEventListener("input", applyEnvironment);
document.getElementById("brightness").addEventListener("input", (e) => {
  state.brightness = +e.target.value;
  applyGrade();
});
document.getElementById("contrast").addEventListener("input", (e) => {
  state.contrast = +e.target.value;
  applyGrade();
});
document.getElementById("environment-mode").addEventListener("change", async (e) => {
  state.environmentMode = e.target.value;
  applyEnvironment();
  if (state.environmentMode === "hdri" && !state.hdriTexture) {
    const files = await refreshHdriList();
    if (files === null) return; // fetch failed; already bannered
    const name = document.getElementById("hdri-select").value;
    if (name) { await loadHdri(name); return; }
  }
  regenerateEnvironment();
});
document.getElementById("hdri-select").addEventListener("change", (e) => {
  if (e.target.value) loadHdri(e.target.value);
});
document.getElementById("hdri-projection").addEventListener("change", (e) => {
  state.hdriProjection = e.target.value;
  applyHdriBackdrop();
});
document.getElementById("hdri-scale").addEventListener("change", (e) => {
  state.hdriScale = +e.target.value;
  applyHdriBackdrop();
});
document.getElementById("hdri-height").addEventListener("change", (e) => {
  state.hdriHeight = +e.target.value;
  applyHdriBackdrop();
});
// Dragging the rotation slider spins the live dome/background directly
// (cheap: no geometry rebuild); releasing it re-aims the sun from the
// stored pixel-estimate azimuth, the same formula loadHdri uses.
document.getElementById("hdri-rotation").addEventListener("input", (e) => {
  state.hdriRotation = +e.target.value;
  const rotation = THREE.MathUtils.degToRad(state.hdriRotation);
  scene.environmentRotation.set(Math.PI / 2, 0, rotation);
  if (hdriDome) {
    hdriDome.children[0].rotation.y = rotation;
  } else {
    scene.backgroundRotation.set(Math.PI / 2, 0, rotation);
  }
});
document.getElementById("hdri-rotation").addEventListener("change", () => {
  if (state.hdriEstimateAzimuth === null) return;
  const azimuth = ((180 - state.hdriEstimateAzimuth + state.hdriRotation) % 360 + 360) % 360;
  document.getElementById("sun-azimuth").value = Math.round(azimuth);
  applySunFromSliders();
});
document.getElementById("weather-preset").addEventListener("change", (e) => {
  state.weatherPreset = e.target.value;
  state.sunColourOverride = null; // a new preset picks the colour again
  state.sunIntensityOverride = null; // F4: same reset, for the intensity override
  const preset = WEATHER[e.target.value];
  if (preset.elevation !== null) {
    document.getElementById("sun-elevation").value = preset.elevation;
  }
  applyEnvironment();
  regenerateEnvironment();
});
// Both ground controls go through the one rebuild, so a preset switch can
// never leave a paver scaled for the previous disc.
document.getElementById("ground-radius").addEventListener("input", (e) => {
  state.groundRadius = +e.target.value;
  document.getElementById("ground-radius-value").textContent = state.groundRadius;
  // Committed live, unlike the Node and Wire sliders: this rebuild is one
  // 64-segment disc and a texture repeat, not thousands of instances, so
  // there is nothing to defer to the end of the drag.
  if (state.objects.ground) rebuildGround();
});
function syncGroundControls() {
  // One Scale dial (Param: "lets just make that scale and keep it
  // uniform"). Old scenes may still carry unequal axes; the dial shows X
  // and the first touch unifies them.
  const pairs = [["ground-scale", state.ground.scaleX, 100],
                 ["ground-relief", state.ground.relief, 10]];
  for (const [id, value, factor] of pairs) {
    const slider = document.getElementById(id);
    if (!slider) continue;
    slider.value = value;
    document.getElementById(id + "-value").textContent = Math.round(value * factor);
  }
}

// The floor texture's own dials. Scale is ONE multiplier over the
// real-world repeat, both axes together -- a texture stretched on one
// axis stops being a picture of its material; relief is the floor's own
// depth, decoupled from the vault's; the randomise button slides the
// whole pattern.
document.getElementById("ground-scale").addEventListener("input", (e) => {
  state.ground.scaleX = +e.target.value;
  state.ground.scaleY = +e.target.value;
  document.getElementById("ground-scale-value").textContent = Math.round(+e.target.value * 100);
  if (state.objects.ground) rebuildGround();
});
document.getElementById("ground-relief").addEventListener("input", (e) => {
  state.ground.relief = +e.target.value;
  document.getElementById("ground-relief-value").textContent = Math.round(state.ground.relief * 10);
  setSurface(groundLibrarySet, state.ground.relief, state.occlusion);
});
document.getElementById("ground-randomise").addEventListener("click", () => {
  // The slide alone was invisible -- shifting a periodic pattern by a
  // fraction of one tile lands the grid back on itself. The random LAY
  // ANGLE is what the eye actually sees change.
  state.ground.offset = [Math.random(), Math.random()];
  state.ground.rotation = Math.random() * Math.PI * 2;
  if (state.objects.ground) rebuildGround();
  logStudio("floor pattern turned and slid to a fresh lay");
});

document.getElementById("ground-preset").addEventListener("change", async (e) => {
  state.groundPreset = e.target.value;
  // A library floor has maps to fetch; loadGroundMaterial rebuilds when
  // they land, and rebuilds at once for a built-in preset.
  await loadGroundMaterial(state.groundPreset);
  if (state.objects.ground) rebuildGround();
});

{
  const search = document.getElementById("ground-search");
  if (search) search.addEventListener("input", () => buildGroundTiles());
}
// ---------- carrying a prop ----------
// One idea in place of two. A prop being carried is a real prop in the
// scene that happens to be following the cursor: it can be looked at from
// any angle while it is carried, it lands where the ground is under the
// pointer, and picking an existing one back up is the same state again.
// Escape puts it back where it came from, or removes it if it was new.
function carryNewProp(type) {
  if (!state.bundle) return;
  const centre = state.centre || new THREE.Vector3();
  const record = placeProp(type, centre.x, centre.y, 0, false);
  state.carrying = { record, from: null };
  selectProp(record);
  controls.enabled = false;
  logStudio("carrying a " + type + ": click to place it, escape to cancel");
}

function carryExistingProp(record) {
  state.carrying = { record, from: { x: record.x, y: record.y } };
  selectProp(record);
  controls.enabled = false;
}

function dropCarriedProp() {
  if (!state.carrying) return;
  const { record, from } = state.carrying;
  state.carrying = null;
  controls.enabled = true;
  if (!from) {
    pushUndo("placing the " + record.type, () => removePropRecord(record));
  } else if (Math.abs(record.x - from.x) > 0.001
      || Math.abs(record.y - from.y) > 0.001) {
    const before = { x: from.x, y: from.y };
    pushUndo("the move", () => {
      record.x = before.x;
      record.y = before.y;
      record.object.position.set(before.x, before.y, 0);
      if (state.selectedProp === record) {
        refreshPropOutline();
        setPropGumball(record);
      }
      saveProps();
    });
  }
  // Outside edit mode the landed prop goes back to being furniture: no
  // outline lingers, and no key can quietly move it afterwards.
  if (!state.propEdit) selectProp(null);
  saveProps();
}

function cancelCarry() {
  if (!state.carrying) return;
  const { record, from } = state.carrying;
  state.carrying = null;
  controls.enabled = true;
  if (from) {
    // It was already in the scene: put it back where it stood.
    record.x = from.x;
    record.y = from.y;
    record.object.position.set(from.x, from.y, 0);
  } else {
    // It was new: it never really arrived.
    disposeProp(record.object);
    propsGroup.remove(record.object);
    state.props = state.props.filter((entry) => entry !== record);
    selectProp(null);
  }
  saveProps();
}

document.getElementById("prop-browse").addEventListener("click", () => {
  openShelf("props");
});

document.getElementById("prop-edit").addEventListener("click", (e) => {
  state.propEdit = !state.propEdit;
  e.target.classList.toggle("active", state.propEdit);
  canvas.style.cursor = state.propEdit ? "pointer" : "";
  if (state.propEdit) {
    logStudio("prop edit on: click a prop to pick it up and drag or click to place; "
      + "R and Shift+R rotate, + and - scale, Delete removes, Escape cancels");
  } else {
    // Leaving edit mode drops any carry and clears the selection: the
    // scene goes back to being all camera.
    if (state.carrying) dropCarriedProp();
    selectProp(null);
    logStudio("prop edit off");
  }
});

document.getElementById("props-clear").addEventListener("click", () => {
  if (!state.bundle) return;
  for (const record of state.props) { disposeProp(record.object); propsGroup.remove(record.object); }
  state.props = [];
  selectProp(null);
  saveProps();
});
canvas.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || !state.bundle) return;
  // A stamp in hand: this click plants the whole group and loads the
  // next copy. Escape is the only way out.
  if (stampRig) {
    const hit = groundPointAt(event);
    if (hit) placeStampInstance(hit);
    return;
  }
  // Carrying something: this click puts it down (whatever the mode -- the
  // carry began with a deliberate library choice).
  if (state.carrying) {
    dropCarriedProp();
    return;
  }
  // The gumball outranks everything: its handles are the explicit
  // controls and they sit over other geometry by design.
  if (state.propEdit && state.selectedProp) {
    const handle = gumballHandleAt(event);
    if (handle) {
      const record = state.selectedProp;
      const ground = groundPointAt(event);
      if (ground) {
        state.gumball = {
          mode: handle, record,
          startRotation: record.rotation || 0,
          startScale: record.scale || 1,
          startAngle: Math.atan2(ground.y - record.y, ground.x - record.x),
          startDistance: Math.max(0.05,
            Math.hypot(ground.x - record.x, ground.y - record.y)),
        };
        controls.enabled = false;
        canvas.setPointerCapture(event.pointerId);
      }
      return;
    }
  }
  // Placed props are furniture until the Edit button says otherwise: a
  // click on a tree while composing the camera must never yank the tree
  // (Param: "when an object is placed we can only click the edit mode to
  // move the props around, scale them and rotate them").
  const record = state.propEdit ? propRecordAt(event) : null;
  if (record) {
    // Clicking a prop picks it back up, which is the same gesture that
    // placed it. Dragging still works for anyone who prefers to drag: the
    // pointer capture below keeps it under the cursor until release.
    carryExistingProp(record);
    state.propDrag = true;
    canvas.setPointerCapture(event.pointerId);
  } else if (state.selectedProp) {
    selectProp(null);
  }
});
canvas.addEventListener("pointermove", (event) => {
  // The stamp rides the cursor as one unit.
  if (stampRig) {
    const hit = groundPointAt(event);
    if (hit) moveStamp(hit);
    return;
  }
  // A live gumball drag: the ring turns the prop, the square scales it,
  // both measured in plan about the prop's feet, the way Rhino reads a
  // gumball drag in top view.
  if (state.gumball) {
    const ground = groundPointAt(event);
    if (!ground) return;
    const { mode, record, startRotation, startScale, startAngle,
      startDistance } = state.gumball;
    if (mode === "rotate") {
      const angle = Math.atan2(ground.y - record.y, ground.x - record.x);
      record.rotation = startRotation + (angle - startAngle);
      record.object.rotation.z = record.rotation;
    } else {
      const distance = Math.hypot(ground.x - record.x, ground.y - record.y);
      record.scale = Math.min(5, Math.max(0.2,
        startScale * distance / startDistance));
      record.object.scale.setScalar(record.scale);
    }
    refreshPropOutline();
    refreshPropGumball();
    return;
  }
  const carried = state.carrying && state.carrying.record;
  if (!carried) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  carried.x = hit.x;
  carried.y = hit.y;
  carried.object.position.set(hit.x, hit.y, 0);
  refreshPropOutline();
  refreshPropGumball();
});
function endPropDrag(event) {
  if (canvas.hasPointerCapture && canvas.hasPointerCapture(event.pointerId)) {
    canvas.releasePointerCapture(event.pointerId);
  }
  if (state.gumball) {
    const record = state.gumball.record;
    const before = { rotation: state.gumball.startRotation,
                     scale: state.gumball.startScale };
    state.gumball = null;
    controls.enabled = true;
    if (Math.abs((record.rotation || 0) - before.rotation) > 1e-6
        || Math.abs((record.scale || 1) - before.scale) > 1e-6) {
      pushUndo("the adjustment", () => {
        record.rotation = before.rotation;
        record.scale = before.scale;
        record.object.rotation.z = before.rotation;
        record.object.scale.setScalar(before.scale);
        if (state.selectedProp === record) {
          refreshPropOutline();
          setPropGumball(record);
        }
        saveProps();
      });
    }
    // A scale drag changed the prop's size: rebuild the ring to fit.
    setPropGumball(record);
    saveProps();
    return;
  }
  if (!state.propDrag) return;
  state.propDrag = false;
  // A drag that actually moved the prop is a placement. A press and release
  // that did not move it leaves the prop in hand, so a click-move-click
  // works as well as a press-drag-release, and neither has to be learnt.
  const carried = state.carrying && state.carrying.record;
  const from = state.carrying && state.carrying.from;
  const moved = carried && from
    && (Math.abs(carried.x - from.x) > 0.001 || Math.abs(carried.y - from.y) > 0.001);
  if (moved) dropCarriedProp();
}
canvas.addEventListener("pointerup", endPropDrag);
canvas.addEventListener("pointercancel", endPropDrag);
window.addEventListener("keydown", (event) => {
  // Escape puts a carried prop back where it came from, or removes it if it
  // never had anywhere to go back to.
  if (event.key === "Escape" && stampRig) {
    endStamp();
    return;
  }
  if (event.key === "Escape" && state.carrying) {
    cancelCarry();
    return;
  }
  if (event.key === "Escape" && shelfKind) {
    closeShelf();
    return;
  }
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  if (!state.propEdit || !state.selectedProp) return;
  if (event.key === "r" || event.key === "R") {
    // R turns one way, Shift+R the other: fifteen degrees a press.
    const step = event.shiftKey ? -Math.PI / 12 : Math.PI / 12;
    state.selectedProp.rotation += step;
    state.selectedProp.object.rotation.z = state.selectedProp.rotation;
    refreshPropOutline();
    refreshPropGumball();
    saveProps();
  } else if (event.key === "+" || event.key === "=" || event.key === "-"
      || event.key === "_") {
    // Scale about the feet, never the centre: the prop's origin IS the
    // ground (placeProp), so growing keeps it planted. Clamped so a
    // mis-tap cannot make a 40 m dandelion or an invisible tree.
    const grow = event.key === "+" || event.key === "=";
    const next = (state.selectedProp.scale || 1) * (grow ? 1.1 : 1 / 1.1);
    state.selectedProp.scale = Math.min(5, Math.max(0.2, next));
    state.selectedProp.object.scale.setScalar(state.selectedProp.scale);
    refreshPropOutline();
    setPropGumball(state.selectedProp);  // the ring re-fits the new size
    saveProps();
  } else if (event.key === "Delete" || event.key === "Backspace") {
    const record = state.selectedProp;
    const gone = { type: record.type, x: record.x, y: record.y,
                   rotation: record.rotation, scale: record.scale,
                   layer: record.layer };
    pushUndo("deleting the " + gone.type, async () => {
      await ensurePropTemplate(gone.type);
      const again = placeProp(gone.type, gone.x, gone.y, gone.rotation,
        false, gone.scale);
      again.layer = gone.layer;
      again.object.visible = layerVisible(again.layer);
      saveProps();
    });
    // removePropRecord also puts a carried corpse down, or the outline
    // keeps following the cursor and the camera stays locked.
    removePropRecord(record);
  }
});
// "change" (drag release), not "input": the file's own convention for every
// other slider that rebuilds something, and this one re-runs the recolour
// over every casting's geometry. On the real export that is 233 of them per
// event, which a drag fires dozens of.
document.getElementById("exaggeration").addEventListener("change", () => recolourSegments());
document.getElementById("stress-surface").addEventListener("change", () => recolourSegments());
// The three ways of looking at the vault. Timeline is not among them on
// purpose: playing is its own way of looking and switches to it by itself,
// so there is no mode to choose before pressing Play.
const SHOW_BUTTONS = [["show-formwork", "framework"], ["show-shell", "shell"],
                      ["show-both", "both"]];

function paintShowButtons() {
  for (const [id, mode] of SHOW_BUTTONS) {
    const button = document.getElementById(id);
    if (button) button.classList.toggle("active", state.showMode === mode);
  }
}

function setShowMode(mode) {
  // Choosing a view during a take stops the take. The buttons and the
  // animation are two ways of owning the scene and they cannot both hold
  // it: picking one is a decision to look at the thing rather than watch
  // it being built.
  if (state.timeline && state.timeline.playing) {
    state.timeline.playing = false;
    paintPlayButtons("Play");
  }
  state.showMode = mode;
  paintShowButtons();
  if (state.timeline) applySceneAtTime(state.timeline.t);
}

for (const [id, mode] of SHOW_BUTTONS) {
  document.getElementById(id).addEventListener("click", () => setShowMode(mode));
}
document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  renderDataPanel(state.bundle ? state.bundle.verification : null);
  panel.classList.toggle("hidden");
});
document.getElementById("data-close").addEventListener("click", () =>
  document.getElementById("data-panel").classList.add("hidden"));
document.getElementById("run-button").addEventListener("click", startRun);

// M5 fix: reload with the material/pattern/size/thickness the run actually
// solved with, not whatever the controls read when the run happens to
// finish. A slider nudge mid-run must not orphan the run's own result -- it
// must show up, and the controls must be set back to match so the display
// stays honest about what's on screen.
function applyRunParamsToControls({ material, pattern, size, thickness }) {
  document.getElementById("material-select").value = material;
  // Assigning .value fires no change event, and the change handler is the
  // only other writer of pattern-note. So: load in limestone with the note
  // showing, switch material mid-run, let the run finish, and the material
  // is restored here with the note left at whatever the mid-run switch put
  // there -- empty for every material but tile and stone. The studio then
  // draws bonded courses under a limestone label with the caveat that the
  // Armadillo dual is not built gone from the screen, which is the exact
  // failure the note exists to prevent.
  //
  // The note only, never the pattern: updatePatternForMaterial also forces
  // the material's default pattern, and calling it here would overwrite
  // the pattern this run actually solved with.
  document.getElementById("pattern-note").textContent =
    state.patternNotes[material] || "";
  document.getElementById("pattern-select").value = pattern;
  document.getElementById("size-slider").value = size;
  document.getElementById("size-value").textContent = Math.round(size * 1000);
  document.getElementById("thickness-input").value = thickness;
  document.getElementById("thickness-value").textContent = Math.round(thickness * 1000);
  state.pattern = pattern;
  state.size = size;
  state.thickness = thickness;
}

function watchRun(runId, exportName, status, params) {
  const poll = setInterval(async () => {
    try {
      const run = await fetchJson("/api/runs/" + runId);
      // "of" is 0 until the cut finishes, because the number of stages is
      // the number of courses the cut produces and nothing knows it before
      // then. "stage 0 of 0" reads as a run that has nothing to do; say
      // what it is actually doing instead.
      const progress = run.of ? "stage " + run.stage + " of " + run.of : "cutting";
      status.textContent = run.state + " (" + progress + ") " + run.message;
      if (run.state === "done") {
        clearInterval(poll);
        applyRunParamsToControls(params);
        await loadStudy(exportName);
        logStudio("analysis finished: " + exportName);
      }
      if (run.state === "failed") {
        clearInterval(poll);
        logStudio("analysis failed: " + exportName + (run.message ? " -- " + run.message : ""));
      }
    } catch (error) {
      clearInterval(poll);
      status.textContent = "lost contact with the server: " + error.message;
    }
  }, 1000);
}

async function startRun() {
  const status = document.getElementById("run-status");
  const exportName = document.getElementById("study-select").value;
  const material = document.getElementById("material-select").value;
  // Captured now, at POST time, so a later slider nudge cannot change what
  // this run is understood to have solved.
  const params = { material, pattern: state.pattern, size: state.size, thickness: state.thickness };
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        export: exportName, material, pattern: params.pattern,
        size: params.size, thickness: params.thickness,
        // The cut on screen is the cut the run stages: without this a
        // Skin study's generated view ran the authored cut and reported
        // done for a stage plan the user never saw.
        source: state.source || undefined,
      }),
    });
    const body = await response.json();
    if (response.status === 409) {
      status.textContent = "watching the live run";
      watchRun(body.run, exportName, status, params);
      return;
    }
    // A refusal carries a precise reason: app.py 400s a size outside the
    // slider's range, a thickness outside 0.05 to 0.5 m, and a material or
    // pattern it does not offer, each naming what to use instead. Without
    // this check the refusal body has no "run" key, watchRun polls
    // /api/runs/undefined, that 404s, and the one thing the user is told
    // is "lost contact with the server" -- a connection failure that never
    // happened, in place of a sentence saying exactly what to change.
    if (!response.ok) {
      status.textContent = "run refused: " + (body && body.detail
        ? body.detail : "HTTP " + response.status);
      return;
    }
    logStudio("analysis started: " + exportName);
    watchRun(body.run, exportName, status, params);
  } catch (error) {
    status.textContent = "run failed to start: " + error.message;
  }
}

// ---------- placement timeline ----------
const DROP_HEIGHT = 12, STRIKE_SECONDS = 2, DROP_SECONDS = 0.8,
      BUILD_TARGET_SECONDS = 35;

function easeOutCubic(u) { return 1 - Math.pow(1 - u, 3); }

// How far apart two castings start, derived in exactly one place, and
// derived from the COUNT: the build always takes BUILD_TARGET_SECONDS
// whatever the cut, so a 1200 piece tile vault takes the same wall clock
// as a 15 piece stone one. Each casting still falls for DROP_SECONDS, so
// with the stagger smaller than the fall time several castings are
// airborne at once. Three clocks read the drop order and all three have
// to read it the same way: applySceneAtTime (what the picture does),
// timelineDuration (the scrubber and the recorded frame count) and
// currentStageIndex (the HUD's stage line and the integrity pulse).
function placementStep() {
  return BUILD_TARGET_SECONDS / Math.max(1, placementCount());
}

// The formwork act: when the study ships a bench.frames/1 document, the
// timeline's first act is the MACHINE building the formwork (net reeled
// out, raised, finished), and the abstract inflation reveal is replaced,
// because the act ends on the solved state exactly (the writer's time-100
// frame equals the contract's equilibrium) and re-inflating an already
// raised net would play the reveal twice. Studies without frames keep
// today's inflation act untouched.
const FORMWORK_SECONDS = 12;

function formworkSeconds() {
  return state.formwork && Array.isArray(state.formwork.frames)
    && state.formwork.frames.length ? FORMWORK_SECONDS : 0;
}

function openingSeconds() {
  // The first act's length: the machine build when frames exist, else the
  // inflation reveal. Every derivation of the build clock goes through
  // here so the two acts can never drift apart.
  const machine = formworkSeconds();
  return machine > 0 ? machine : state.timeline.inflateSeconds;
}

function duringFormworkAct(t) {
  return formworkSeconds() > 0 && t < formworkSeconds();
}

function rebuildTimeline(preserve) {
  state.timeline = {
    playing: false, t: 0,
    speed: +document.getElementById("timeline-speed").value,
    inflateSeconds: INFLATE_SECONDS,
    orbitSpeed: +document.getElementById("orbit-speed").value,
    autoSpin: true,
    // Read off the viewport when a take starts (captureOrbitBase). Null
    // until then, and while it is null the timeline does not touch the
    // camera at all, so loading a study leaves the view where it was.
    orbitBase: null,
  };
  state.centre = sceneCentroid();
  if (!preserve) {
    // applyTimeline's autoSpin camera.lookAt(state.centre) and controls'
    // damped approach toward controls.target must aim at the same point,
    // or live orbit, drag-release and the recorded camera each settle on
    // a different seam. Sync once here, outside applyTimeline, so
    // applyTimeline stays a pure function of t. A same-export reload
    // skips it: the centre is the same point, and the camera is wherever
    // the user put it.
    controls.target.copy(state.centre);
    controls.update();
  }
  buildPieceMeshes();
  if (preserve) {
    // Same export, new bundle: the fraction is what carries between two
    // different drop sequences, and it is applied through the scene-only
    // helper so the camera stays put. The playing flag rides across too,
    // so a swap mid-animation keeps animating. applySceneAtTime's own first
    // line is what writes state.timeline.t, so this preserve path depends
    // on that assignment happening here.
    applySceneAtTime(preserve.f * timelineDuration());
    state.timeline.playing = preserve.playing;
    paintPlayButtons(preserve.playing ? "Pause" : "Play");
    scrubber.value = Math.round(1000 * preserve.f);
  } else {
    applyTimeline(0);
    scrubber.value = 0;
  }
  recolourSegments();
}

// How many castings drop, which is the number of PIECES and not the number
// of cells: a cell split into two patches ships two of them.
function placementCount() {
  return state.bundle && state.bundle.pieces ? state.bundle.pieces.length : 0;
}

// The reveal for a study with no machine of its own: a fixed few seconds
// rather than a slider. Param's ruling, and the reason is that the
// animation now belongs to Grasshopper: where there are frames the machine
// IS the reveal, and where there are none this is a courtesy, not a
// setting worth a control.
const INFLATE_SECONDS = 3;

// The last act. Once the formwork has dropped away the take carries on
// turning, so the finished vault is seen once on its own rather than the
// film ending on the frame the strike finishes. Param asked for exactly
// this: "at the end of the animation when the form work drops away, can we
// continue the rotation one more time so we look at the final form".
//
// HALF a revolution at the spin rate in force (Param: "change the
// animation rotation at the end to just a half rotation instead of a
// full when finished"), floored so a still camera still pauses on the
// result, and capped so a very slow spin does not quietly add a minute
// to every take and every recording.
const ADMIRE_MIN_SECONDS = 4;
const ADMIRE_MAX_SECONDS = 40;

function admireSeconds() {
  const spin = state.timeline ? state.timeline.orbitSpeed : 0;
  if (!(spin > 0)) return ADMIRE_MIN_SECONDS;
  return Math.min(ADMIRE_MAX_SECONDS,
    Math.max(ADMIRE_MIN_SECONDS, Math.PI / spin));
}

function timelineDuration() {
  const step = placementStep();
  return openingSeconds() + placementCount() * step
    + DROP_SECONDS + STRIKE_SECONDS + admireSeconds();
}

function pieceTint(key) {
  // A deterministic lightness nudge per casting, so no two pieces look
  // identical and the same study always looks the same. The amount is now
  // a dial (Param: "a slider for that too, changing the amount of colour
  // differentiation"); 1 keeps the old +-0.03. Library skins sit on a
  // white base whose lightness clamps upward, so their nudge is
  // darken-only and the whole dialled range shows.
  const amplitude = 0.06 * (state.appearance.variation ?? 1);
  const t = segmentUVOffset(key)[0] % 1;
  return isLibraryKey(state.appearance.skin)
    ? -t * amplitude
    : t * amplitude - amplitude / 2;
}

// Render skins. "none" is not a factory: it means "show the registry
// material", which appearanceMaterialBase reads straight from materials[].
// The three procedural skins (white presentation, basalt, ply) are gone on
// Param's word: the library is the skin catalogue now. A remembered or
// scene-saved legacy key simply finds no factory here and falls through to
// the registry look.
const SKINS = {
  none: null,
};

const skinMaterialCache = {};

function appearanceMaterialBase() {
  // The base pieceMaterial clones from: a skin's material when one is
  // chosen, else the registry entry for the loaded study's own material
  // (unchanged from before this task). A skin only ever substitutes the
  // BASE material a piece is built from; it carries no information back to
  // the server and never touches state.bundle.material, so the whole-shell
  // weld in buildPieceMeshes -- which triggers on sprayedMaterial(), i.e.
  // the ANALYSIS material being concrete-sprayed -- keeps working exactly
  // as before under any skin, including "none".
  const skin = state.appearance.skin;
  // A library material, if one is chosen AND has finished loading. Before
  // it has, the registry entry stands in: a frame of the old material beats
  // a frame of nothing, and rebuildAppearance runs again when it arrives.
  if (isLibraryKey(skin) && libraryCache.has(skin)) {
    return libraryCache.get(skin).material;
  }
  if (skin !== "none" && SKINS[skin]) {
    if (!skinMaterialCache[skin]) skinMaterialCache[skin] = SKINS[skin]();
    return skinMaterialCache[skin];
  }
  return materials[state.bundle.material] || materials.concrete;
}

function pieceMaterial(key) {
  // The tint is a property of the casting, not a one-shot at build time.
  // recolourSegments reassigns every piece's material on every call, and
  // all three callers of buildPieceMeshes call it immediately afterwards
  // with no heatmap layer on at first load: while that branch handed back
  // a fresh untinted clone, the tint never once reached the screen and two
  // castings always looked identical. Recomputed here from the piece's own
  // key, which is deterministic, so any number of rebuilds and heatmap
  // toggles land on the same colour.
  //
  // Each casting owns its instance so the pulse can write emissive per
  // piece, and so the tint never leaks into the shared registry entry
  // other code reads from.
  const own = appearanceMaterialBase().clone();
  // Task 5: the tint/finish overrides are render-only and apply before the
  // per-piece HSL variation below, which is unchanged -- a tint override
  // still gets the same per-casting lightness nudge a plain material does.
  const { tint, finish } = state.appearance;
  if (tint !== null) own.color.set(tint);
  if (finish !== null) own.roughness = finish;
  // Sprayed concrete is one continuous surface, so it gets no per piece
  // variation at all.
  if (!sprayedMaterial()) own.color.offsetHSL(0, 0, pieceTint(key));
  return own;
}

function taperAt(course) {
  // Pieces thin toward the crown, which is where the least load arrives.
  const courses = Math.max(1, state.bundle.tessellation.courses - 1);
  return 1 - state.taper * Math.min(1, course / courses);
}

function buildPieceMeshes() {
  disposeShell();
  const tile = activeTileMetres();
  const group = new THREE.Group();
  // Thickness on screen is what the bundle was solved at, never the live
  // slider, which can drift while a bundle loads.
  const gap = sprayedMaterial() ? 0 : state.jointGap;
  const built = [];
  for (const piece of state.bundle.pieces) {
    const count = piece.mid.length;
    const half = state.bundle.provenance.thickness * taperAt(piece.course) / 2;
    const points = [];
    for (const sign of [1, -1]) {
      for (let i = 0; i < count; i++) {
        const m = piece.mid[i], n = piece.normals[i];
        points.push([
          m[0] + n[0] * half * sign,
          m[1] + n[1] * half * sign,
          m[2] + n[2] * half * sign,
        ]);
      }
    }
    // The joint: shrink the whole casting toward its own centroid, so
    // neighbours stand apart by twice the inset and the cut reads.
    let cx = 0, cy = 0, cz = 0;
    for (const p of points) { cx += p[0]; cy += p[1]; cz += p[2]; }
    const centre = [cx / points.length, cy / points.length, cz / points.length];
    let extent = 1e-9;
    for (const p of points) {
      extent = Math.max(extent, Math.hypot(
        p[0] - centre[0], p[1] - centre[1], p[2] - centre[2]));
    }
    const shrink = Math.max(0, 1 - (gap / 2) / extent);
    const positions = [], weights = [], surface = [];
    for (const face of piece.faces) {
      for (let corner = 1; corner < face.length - 1; corner++) {
        for (const index of [face[0], face[corner], face[corner + 1]]) {
          const p = points[index];
          // shrink === 1 must push p verbatim: c + (p - c) is not p in
          // floats, and the sprayed weld below groups corners by exact
          // bit pattern, which the engine only guarantees for the raw
          // offsets from mid and normal.
          if (shrink === 1) {
            positions.push(p[0], p[1], p[2]);
          } else {
            positions.push(
              centre[0] + (p[0] - centre[0]) * shrink,
              centre[1] + (p[1] - centre[1]) * shrink,
              centre[2] + (p[2] - centre[2]) * shrink);
          }
          weights.push(piece.sources[index % count]);
          surface.push(index < count ? 1 : -1);
        }
      }
    }
    built.push({ piece, positions, weights, surface, centre });
  }
  // Sprayed concrete is one continuous surface: the joint gap is zero,
  // the shrink factor is exactly 1 and shared boundary points are
  // bit-identical across pieces at taper 0, so the crease normals are
  // computed over the WHOLE shell in one call and sliced back per piece.
  // Course joints then stop stepping in the light. With the crown taper
  // above zero, adjacent courses are offset by different half
  // thicknesses and their shared points honestly stop welding. Jointed
  // materials keep per-piece normals: their pieces are genuinely
  // separate and the lighting step at a joint is honest.
  let welded = null;
  if (sprayedMaterial()) {
    let total = 0;
    for (const entry of built) total += entry.positions.length;
    const all = new Array(total);
    let cursor = 0;
    for (const entry of built) {
      for (let i = 0; i < entry.positions.length; i++) {
        all[cursor + i] = entry.positions[i];
      }
      cursor += entry.positions.length;
    }
    welded = creaseNormals(all);
  }
  // A library material is ONE SHEET for the whole vault, cut into
  // voussoirs: mapped at one uniform scale, identical on every piece
  // (Param: "keep it always uniform... the texture scale on the skin
  // always needs to be the same between objects"), and the sheet is sized
  // by the largest footprint so no face ever repeats. Each piece samples
  // its own hashed window of the sheet -- voussoirs sawn from one slab.
  // The seed rides in the key so the Randomise button re-deals every
  // piece at once. The plain structural look keeps the eyeballed box
  // projection: it has no picture to lay out.
  const grain = !!(tile && state.appearance.grain);
  let sheet = 0;
  if (tile) {
    for (const entry of built) {
      // The frame is found on the TOP SURFACE alone: a piece is 200 mm
      // thick with a small face, so over the whole solid the joint walls
      // out-weigh the faces and tip the plane edge-on. The surface flags
      // already say which triangles are the top.
      const top = [];
      const { positions, surface } = entry;
      for (let i = 0, v = 0; i < positions.length; i += 9, v += 3) {
        if (surface[v] === 1 && surface[v + 1] === 1 && surface[v + 2] === 1) {
          for (let j = 0; j < 9; j++) top.push(positions[i + j]);
        }
      }
      entry.top = top;
      sheet = Math.max(sheet, footprintSpan(positions, grain, top));
    }
  }
  const seed = state.appearance.uvSeed || 0;
  let offset = 0;
  for (const entry of built) {
    const { piece, positions, weights, surface, centre } = entry;
    const normals = welded
      ? welded.slice(offset, offset + positions.length)
      : creaseNormals(positions);
    offset += positions.length;
    const seedKey = piece.key + "#" + seed;
    // With the grain matched, v runs up the slope of each voussoir, so the
    // per-piece quarter-turns collapse to 0 or 180 degrees (grain has no
    // arrow) and the seed's own parity turns the whole deal 90 degrees at
    // once -- the switch for pictures whose grain runs across the image
    // rather than down it. Without it, the hashed quarter-turn per piece
    // keeps the courses from reading as aligned copies.
    // No GLOBAL component in either branch: pressing Randomise must deal
    // every piece its own hand (Param: "its random for every instance"),
    // and the old seed-parity term turned the whole deal 90 degrees at
    // once, which read as one rotation applied to everything. Grain
    // matched still only flips 0/180, because grain has no arrow but
    // does have a direction.
    const turn = grain
      ? (uvQuarterTurn(seedKey) & 1) * 2
      : uvQuarterTurn(seedKey);
    const window_ = segmentWindow(seedKey);
    const uvs = tile
      ? sheetUVs(positions, sheet,
          { grain, windowU: window_[0], windowV: window_[1], rotation: turn,
            frameSource: entry.top })
      : boxUVs(positions, centre, segmentUVOffset(seedKey));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    const mesh = new THREE.Mesh(geometry, pieceMaterial(piece.key));
    mesh.castShadow = mesh.receiveShadow = true;
    mesh.userData.key = piece.key;
    // The casting's own centroid height. Piece geometry is in absolute
    // world coordinates and the mesh sits at the origin, so the sprayed
    // growth needs this to scale a piece about itself rather than about
    // z = 0 (see applySceneAtTime).
    mesh.userData.centreZ = centre[2];
    mesh.userData.weights = weights;
    mesh.userData.surface = surface;
    mesh.userData.basePositions = new Float32Array(positions);
    // The welded normal, stored so a deflection reset can restore it
    // rather than recompute it: see recolourSegments.
    mesh.userData.baseNormals = normals;
    group.add(mesh);
  }
  state.objects.shell = group;
  scene.add(group);
}

function sprayedMaterial() {
  // Keyed on the PATTERN, not the material name: the sprayed distinction
  // is the Pattern control's now (Param: "all of those pattern changes
  // will be kept to the skin pattern option we have"). The material check
  // stays as a fallback for bundles cut before the pattern rode along.
  return state.bundle && (state.bundle.pattern === "monolithic-bands"
    || state.bundle.material === "concrete-sprayed");
}

function updateMaterialControls() {
  // Sprayed concrete is monolithic, so buildPieceMeshes forces its joint
  // gap to zero. Leaving the slider live and labelled in millimetres asks
  // the reader to drag a control that does nothing, so it is disabled and
  // says why.
  //
  // The crown taper is deliberately NOT here. It is applied to every
  // material, sprayed included: sprayed concrete can be laid thinner at
  // the crown, and taperAt has no material branch. Marking a control that
  // works as inert would be its own dishonesty.
  // Sprayed concrete is monolithic and opens no joints. There is no longer
  // a control to disable and say so on, so it says so in the log, once, on
  // the load that chose it.
  if (sprayedMaterial()) {
    logStudio("sprayed concrete is monolithic: no joints are opened");
  }
}

// ---------- Task 5: tint, finish and render skins (render-only) ----------
function appearanceStorageKey(material) {
  return "bench-studio-appearance:" + material;
}

function persistAppearance() {
  const material = document.getElementById("material-select").value;
  localStorage.setItem(appearanceStorageKey(material), JSON.stringify(state.appearance));
}

function syncAppearanceControls() {
  document.getElementById("render-skin").value = state.appearance.skin;
  document.getElementById("material-tint").value = state.appearance.tint || "#ffffff";
  const finish = state.appearance.finish !== null ? state.appearance.finish : 0.5;
  document.getElementById("material-finish").value = finish;
  document.getElementById("material-finish-value").textContent = Math.round(finish * 100);
  const variation = state.appearance.variation ?? 1;
  document.getElementById("material-variation").value = variation;
  document.getElementById("material-variation-value").textContent = Math.round(variation * 100);
  document.getElementById("material-grain").checked = !!state.appearance.grain;
}

// Called from both the material-select change handler and loadStudy, both
// BEFORE the incoming material's pieces are built, so a stored override
// (or the lack of one) is always in state.appearance by the time
// pieceMaterial first reads it for the material being switched to.
function restoreAppearance(material) {
  let appearance = { tint: null, finish: null, skin: "none",
    variation: 1, uvSeed: 0, grain: false };
  const stored = localStorage.getItem(appearanceStorageKey(material));
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      appearance = {
        tint: parsed.tint || null,
        finish: typeof parsed.finish === "number" ? parsed.finish : null,
        skin: typeof parsed.skin === "string" ? parsed.skin : "none",
        variation: typeof parsed.variation === "number" ? parsed.variation : 1,
        uvSeed: typeof parsed.uvSeed === "number" ? parsed.uvSeed : 0,
        grain: parsed.grain === true,
      };
    } catch (error) { /* corrupt localStorage entry: fall back to the defaults above */ }
  }
  state.appearance = appearance;
  syncAppearanceControls();
  // The restore can install a library skin nothing has loaded yet -- the
  // most silent of the fallback paths: the vault wore the registry look
  // while the picker claimed the library material. Load it, then redraw.
  if (isLibraryKey(appearance.skin) && !libraryCache.has(appearance.skin)) {
    ensureLibraryMaterial(appearance.skin).then((set) => {
      if (set && state.appearance.skin === appearance.skin) rebuildAppearance();
    });
  }
}

// The joint-gap handler's exact rebuild shape, reused across the four
// appearance controls: a tint, finish or skin change never touches the
// bundle, so it never needs a server round trip, only a redraw.
// The disclosure that used to sit under these controls as a permanent
// sentence. It is said once, in the log, when a skin or a tint is actually
// applied: the panel is for controls and the log is for sentences.
let appearanceDisclosed = false;

function discloseAppearance() {
  if (appearanceDisclosed) return;
  appearanceDisclosed = true;
  logStudio("skin, tint and shine are render only: the analysis is unchanged");
}

function rebuildAppearance() {
  discloseAppearance();
  updateWeightNote();
  if (!state.bundle) return;
  buildPieceMeshes();
  recolourSegments();
  if (state.timeline) applySceneAtTime(state.timeline.t);
}

function sceneCentroid() {
  const vertices = state.bundle.analysis_mesh.vertices;
  let x = 0, y = 0;
  for (const v of vertices) { x += v[0]; y += v[1]; }
  return new THREE.Vector3(x / vertices.length, y / vertices.length, 2);
}

// The opening move: the net rises from the flat form diagram into its
// found shape before any piece is placed. inflationFactor(t) is 0 to
// inflateSeconds in, 1 after. The formGraph the contract ships is the flat
// form diagram itself: on the real export its xy already matches the
// thrust surface and its z is zero throughout, so this is a straight
// interpolation of z toward the equilibrium surface, not an invented
// effect.
function inflationFactor(t) {
  // With a formwork act, the machine raising the net IS the reveal: the
  // net is hidden while the act plays (see the wires/nodes visibility in
  // applySceneAtTime) and stands fully formed the instant it ends, so the
  // factor is a step, not a ramp. The pieces gate on inflate < 1 keeps
  // castings out of the air for the whole act, exactly as it does for
  // inflation.
  if (formworkSeconds() > 0) return t >= formworkSeconds() ? 1 : 0;
  // 0 is the flat form diagram, 1 the found thrust surface.
  const seconds = state.timeline.inflateSeconds;
  if (seconds <= 0) return 1;
  return Math.min(1, Math.max(0, t / seconds));
}

function applyInflation(u) {
  // The wires and nodes are instanced, so inflation moves the whole group
  // rather than rebuilding instances: the net rises from the flat plan
  // into form. z is scaled because the form diagram sits at z = 0 and
  // shares the thrust surface's xy exactly.
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    // Floored exactly as the sprayed growth is, and for the same reason: a
    // scale of 0 makes the model matrix singular, three derives its normal
    // matrix from it, and the whole net renders unlit. t = 0 is a frame
    // every recording writes, so without the floor frame 0 of every take
    // is wrong.
    if (object) object.scale.z = Math.max(0.001, u);
  }
}

// The act's scene objects, held OUTSIDE state.objects on purpose:
// buildScene resets state.objects wholesale, which made the disposal
// branch below dead code and left every previous study's group parked in
// the scene. A module-level handle survives the reset, so disposal is
// real and exactly one group ever exists.
let formworkObjects = null;

// The width of a column when the study ships no columns file to read it
// from: the exporter's own figure, which every export to date carries.
const COLUMN_RADIUS = 0.05;

function columnRadius() {
  return state.columnRadius > 0 ? state.columnRadius : COLUMN_RADIUS;
}

function rebuildFormworkObjects() {
  if (formworkObjects) {
    scene.remove(formworkObjects.group);
    for (const child of formworkObjects.group.children) {
      child.geometry.dispose();
      child.material.dispose();
      // InstancedMesh owns instanceMatrix/instanceColor GPU buffers that
      // neither of those frees: the rule disposeWiresAndNodes documents.
      if (child.dispose) child.dispose();
    }
    formworkObjects = null;
  }
  const doc = state.formwork;
  if (!doc || !Array.isArray(doc.frames) || !doc.frames.length) return;
  const group = new THREE.Group();
  const handles = { group, net: null, nodes: null, members: null };
  const edges = Array.isArray(doc.edges) ? doc.edges : [];
  const members = doc.columns && Array.isArray(doc.columns.members)
    ? doc.columns.members : [];
  const vertexCount = doc.vertexCount || doc.frames[0].vertices.length;
  if (edges.length) {
    const net = netInstances(edges.length, vertexCount);
    // Every instance moves every frame, and an InstancedMesh keeps the
    // bounding sphere it was first culled against: left on, the net
    // vanishes the moment the machine carries it outside that sphere.
    net.wires.frustumCulled = net.nodes.frustumCulled = false;
    handles.net = net.wires;
    handles.nodes = net.nodes;
    group.add(net.wires);
    group.add(net.nodes);
  }
  if (members.length) {
    const radius = columnRadius();
    const cylinder = new THREE.CylinderGeometry(radius, radius, 1, 8, 1, true);
    cylinder.translate(0, 0.5, 0);
    const barMaterial = materials.steel.clone();
    // Transparent so the columns can fade out with the rest of the machine
    // on the strike, the same way the finished net's material does.
    barMaterial.transparent = true;
    const bars = new THREE.InstancedMesh(cylinder, barMaterial, members.length);
    // Columns are structure: they cast and receive shadows exactly as the
    // exported solids do in loadColumns, which is half of looking the same.
    bars.castShadow = bars.receiveShadow = true;
    bars.frustumCulled = false;
    handles.members = bars;
    group.add(bars);
  }
  // Seeded at the CURRENT instant, not at zeros and not at frame 0: a
  // rebuild mid-scrub (a radius slider, a columns import) must not snap the
  // machine back to the start, and a zero-filled buffer is a degenerate,
  // invisible net until the first apply.
  const seed = interpolateFormworkFrame(
    doc.frames,
    machineTime(state.timeline ? state.timeline.t : 0, formworkSeconds()));
  if (handles.net) writeInstancedSegments(handles.net, edges, seed.vertices);
  if (handles.nodes) writeInstancedPoints(handles.nodes, seed.vertices);
  if (handles.members) {
    writeInstancedSegments(handles.members, members, seed.columnNodes);
  }
  formworkObjects = handles;
  scene.add(group);
}

// The formwork act's whole scene contribution, pure in t like everything
// else on this clock. The net follows the interpolated frame and then
// yields to the finished instanced wires at act end: its final pose IS
// theirs by the writer's time-100 guarantee, and now its drawing is theirs
// too, so the handover is invisible. The columns are the machine's other
// half: raised with the net, standing through the build while the vault is
// cast on it, and taken away with the formwork on the strike, on the same
// fade and the same drop. formworkVisibility (fields.js) owns those rules
// and is tested on its own; this function only applies them.
function applyFormworkAct(t, strikeU) {
  const doc = state.formwork;
  const seconds = formworkSeconds();
  const show = formworkVisibility({
    t, seconds, strikeU, showMode: state.showMode,
    hasMembers: !!(formworkObjects && formworkObjects.members),
    hasColumnMesh: !!state.objects.columns,
  });
  // The exported column solids and the animated members are the same tubes
  // at the same radius, so drawn together they z-fight: exactly one of the
  // two is on screen at any instant.
  if (state.objects.columns) state.objects.columns.visible = show.columnMesh;
  if (!formworkObjects || !doc) return;
  formworkObjects.group.visible = show.group;
  if (!show.group) return;
  const frame = interpolateFormworkFrame(doc.frames, machineTime(t, seconds));
  const lift = netClearance();
  if (formworkObjects.net) {
    formworkObjects.net.visible = show.net;
    if (show.net) {
      writeInstancedSegments(formworkObjects.net, doc.edges, frame.vertices);
      formworkObjects.net.position.z = lift.wires;
    }
  }
  if (formworkObjects.nodes) {
    formworkObjects.nodes.visible = show.net;
    if (show.net) {
      writeInstancedPoints(formworkObjects.nodes, frame.vertices);
      formworkObjects.nodes.position.z = lift.nodes;
    }
  }
  if (formworkObjects.members) {
    const bars = formworkObjects.members;
    bars.visible = show.members;
    if (show.members) {
      writeInstancedSegments(bars, doc.columns.members, frame.columnNodes);
      // The column heads meet the net at the net's own nodes, so they
      // carry the net's display shift or the joint that holds the whole
      // machine together comes apart by half a thickness. The feet go the
      // same distance under the ground plane, where nothing sees them.
      // Then the strike: the same fade and the same 1.5 m drop the net
      // takes in applySceneAtTime, because it is one machine leaving.
      bars.material.opacity = 1 - strikeU;
      bars.position.z = lift.wires - 1.5 * strikeU;
    }
  }
}

// Everything that depends on the build/strike clock but not on the camera:
// inflation, segment drop/visibility, falsework, wires/nodes strike state,
// and the integrity pulse. setLayer's wires/falsework toggle and
// rebuildWiresAndNodes both need to recompute this scene state after the
// objects they touch change, but neither one should be allowed to move the
// camera -- only applyTimeline's own scrubber/play/record callers get to
// do that. Kept pure in t, same as applyTimeline: no clock reads here
// either.
function applySceneAtTime(t) {
  state.timeline.t = t;
  // Guarded like every sibling that touches these two (recolourSegments,
  // applyPulse, setLayer). disposeShell sets state.objects.shell to null,
  // and this function is reachable from setLayer and rebuildWiresAndNodes,
  // neither of which is ordered after a rebuild; the falsework is built in
  // the same pass. An unguarded read throws out of frame() before the
  // frame is rescheduled, which kills the render loop until the page is
  // reloaded, and that is a heavy price for a null check.
  if (!state.objects.shell || !state.objects.falsework) return;
  const inflate = inflationFactor(t);
  applyInflation(inflate);
  // The timeline opens with the net inflating into form; everything after
  // it (drop, strike, pulse) runs on build time, which only starts once
  // inflation is complete.
  const build = Math.max(0, t - openingSeconds());
  const sprayed = sprayedMaterial();
  const step = placementStep();
  for (const segment of state.objects.shell.children) {
    // No piece exists on screen while the net is still finding its form:
    // gate on inflation, not on the drop-window arithmetic below, or the
    // first casting reads build = 0 as "the very start of its drop" and
    // hangs at DROP_HEIGHT for the whole inflation window instead of being
    // absent. inflate reaches exactly 1 the instant build time begins.
    if (inflate < 1) {
      segment.visible = false;
      continue;
    }
    const position = state.segmentIndex.get(segment.userData.key).order;
    // The stagger placementStep derives is smaller than DROP_SECONDS on
    // any real cut, so castings overlap in flight for every material and
    // sprayed concrete reads as continuous build up without any special
    // case here.
    const start = position * step;
    if (build < start) {
      segment.visible = false;
      continue;
    }
    const u = Math.min(1, (build - start) / DROP_SECONDS);
    segment.visible = true;
    if (sprayed) {
      // Sprayed concrete thickens on the formwork where it is sprayed, so
      // the casting grows about its OWN centroid and stays where it will
      // stand. Piece geometry is absolute and the mesh sits at the origin,
      // so a bare scale.z scales about z = 0 instead: a crown casting on
      // Trial 2, whose centroid is 6.85 m up, was drawn as a sliver lying
      // on the ground stretching vertically through the falsework to its
      // true height, which is a piece arriving from elsewhere, not
      // concrete being built up. Compensating the position by
      // centreZ * (1 - grown) pins the centroid in place while the
      // thickness comes on.
      const grown = 0.001 + 0.999 * easeOutCubic(u);
      segment.scale.set(1, 1, grown);
      segment.position.z = segment.userData.centreZ * (1 - grown);
    } else {
      // Both halves reset, so switching material mid-timeline can never
      // leave a piece carrying the other branch's growth or offset.
      segment.scale.set(1, 1, 1);
      segment.position.z = DROP_HEIGHT * (1 - easeOutCubic(u));
    }
  }
  const buildEnd = placementCount() * step + DROP_SECONDS;
  const strikeU = build <= buildEnd ? 0 : Math.min(1, (build - buildEnd) / STRIKE_SECONDS);
  const falsework = state.objects.falsework;
  // Three states, the owner's own words. Animation follows the build
  // story: fade in with the inflation, stand through the build, strike
  // away at the end. Always pins the resting ghost for inspection even
  // after the strike. Hidden removes the ghost shell everywhere, build
  // phase included.
  const mode = state.formworkMode;
  falsework.visible = mode === "always" || (mode === "animation" && strikeU < 1);
  falsework.material.opacity = mode === "always" ? 0.3 : 0.3 * inflate * (1 - strikeU);
  // R3: the ghost is built from the analysis mid-surface mesh
  // (buildPieceMeshes offsets the real, opaque pieces from that same
  // surface by half the shell thickness). The old -0.02 constant sat
  // comfortably inside the opaque shell's own thickness and was never
  // visible from outside it. Half the thickness clears the intrados
  // exactly; 5 cm of air on top of that keeps it legible as a ghost
  // rather than flush against the shell.
  // The BUNDLE's own thickness, same reason arrowField's lift does at
  // studio.js:1396: state.thickness is the control's live value and can
  // drift from what the shell on screen was actually built at.
  falsework.position.z = mode === "always"
    ? -(state.bundle.provenance.thickness / 2) - 0.05
    : -0.02 - 1.5 * strikeU;
  // The strike takes the thrust network with it: wires and nodes fade,
  // drop and vanish on the same clock, and scrubbing back restores them
  // because everything here is computed from t (by way of build). The Show
  // select, not this checkbox, now owns whether the net is visible outside
  // the strike window (applyShowMode).
  //
  // Crown seam (2026-08-16-studio-finish task 4): the probe caught the same
  // seam here too, in Timeline, once the crown course has landed and before
  // the strike starts dropping the net away -- shell fully placed, wires
  // still at opacity 1 (see
  // .superpowers/sdd/2026-08-16-studio-finish/crown-seam-timeline-strike-950-before.png,
  // scrubber 950/1000, strikeU still 0). The shell is drawn over the net
  // here exactly as it is in Both mode, so the same clearance applies:
  // applyShowMode's comment above the "both" branch has the full diagnosis
  // and the normal-direction caveat. It is additive with the strike's own
  // drop so the net still lands 1.5 m clear of the shell once struck.
  // Fix round 1: wires and nodes are separate InstancedMeshes with separate
  // radii (state.wireRadius, state.nodeRadius, default 0.02 / 0.03, both
  // user-adjustable up to 0.10 via the Node/Wire size sliders) -- a shared
  // clearance under-cleared whichever one had the bigger radius, and the
  // Node size slider alone could push the white dots back through the
  // shell at any clearance computed from wireRadius. Each object clears by
  // its own radius.
  const clearance = netClearance();
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (!object) continue;
    // Hidden for the whole formwork act: the act's own net IS the net,
    // moving; the instanced wires would draw it a second time, flat on
    // the ground at the solved plan, which is two nets and both wrong.
    object.visible = strikeU < 1 && !duringFormworkAct(t);
    object.material.opacity = 1 - strikeU;
    object.position.z = clearance[key] - 1.5 * strikeU;
  }
  // The pulse is a Timeline effect: build is the elapsed drop-order clock
  // and has no meaning in Framework/Shell/Both, which show a fixed rest
  // state with no build order to be partway through. Calling it
  // unconditionally left the last frame's emissive tint stuck on the shell
  // after switching Show mode away from Timeline; applyShowMode's own
  // sweep, below, clears that residue on entry to the other three modes.
  applyFormworkAct(t, strikeU);
  if (state.showMode === "timeline") applyPulse(build);
  applyShowMode();
}

// R4: the Show select is a lens over the same scene function. Timeline
// shows whatever t says; the other three are the rest state with a fixed
// choice of net and shell. Falsework stays with its own select, except
// framework mode, which is the bare net by definition.
function applyShowMode() {
  // Guarded like applySceneAtTime guards shell/falsework, above: an
  // unguarded read of nodes or bundle throws out of frame() before the
  // frame is rescheduled, which kills the render loop until the page is
  // reloaded. shell and wires were guarded already; nodes and bundle are
  // built alongside them (buildScene, rebuildWiresAndNodes) but were not.
  if (!state.objects.shell || !state.objects.wires || !state.objects.nodes || !state.bundle) return;
  if (state.showMode === "timeline") return;
  const shellOn = state.showMode === "shell" || state.showMode === "both";
  const netOn = state.showMode === "framework" || state.showMode === "both";
  applyInflation(1);
  for (const segment of state.objects.shell.children) {
    segment.visible = shellOn;
    segment.position.set(0, 0, 0);
    segment.rotation.set(0, 0, 0);
    segment.scale.set(1, 1, 1);
    // applyPulse only runs in Timeline (see applySceneAtTime, above), so
    // leaving here without sweeping this back would leave the last
    // Timeline frame's tint stuck on the shell in Shell/Both. Same sweep
    // setLayer("pulse", false) does when the pulse layer itself is turned
    // off.
    segment.material.emissiveIntensity = 0;
  }
  state.objects.wires.visible = netOn;
  state.objects.nodes.visible = netOn;
  // The strike (applySceneAtTime, above) is the only thing that fades
  // wires/nodes: it writes material.opacity toward 0 and position.z toward
  // -1.5 as strikeU rises, and touches nothing else on either object.
  // scale.z is inflation-driven, not strike-driven, and applyInflation(1)
  // above already put it back to 1, so opacity and position.z are the only
  // two properties this lens needs to restore to their built values.
  state.objects.wires.material.opacity = 1;
  state.objects.nodes.material.opacity = 1;
  // Crown seam (2026-08-16-studio-finish task 4). Diagnosis, probed with
  // studio_probe.mjs against the real "Algebraic TNA method" export in Both
  // mode, camera close on the ridge: buildWiresAndNodes draws the net
  // straight off bundle.analysis_mesh with no display offset (z = 0, right
  // above), i.e. the raw structural mid-surface; buildPieceMeshes offsets
  // the opaque shell off that same mid-surface family by half the built
  // thickness a side. Nothing keeps those two independently-built surfaces
  // a guaranteed distance apart, and at the crown -- the shallowest, most
  // tightly curved part of this vault -- they come close enough that the
  // net's own wire/node radius is enough to break through the shell's
  // extrados: Param's black line with regularly spaced white dots along
  // the ridge, confirmed in
  // .superpowers/sdd/2026-08-16-studio-finish/crown-seam-both-before.png
  // and the tight crown-seam-both-closeup-before.png beside it, which shows
  // one wire segment and one node sphere both breaking the surface.
  // Pushing the net along +Z by half the built thickness plus its own
  // radius is a display-only fix, not a re-derivation of the true offset
  // surface: it approximates "outward along the local normal" and is only
  // guaranteed to clear the shell where that normal is close to vertical,
  // which is exactly the shallow crown region where the seam shows; it
  // would under- or over-clear a steeply sloped stretch nearer the
  // springing, where the net was already comfortably inside the shell.
  // Framework mode has no shell to clash with, so it keeps rendering the
  // net at its true mid-surface position, z = 0, for the form-finding
  // diagram. Fix round 1: wires and nodes are separate InstancedMeshes at
  // separate, independently user-adjustable radii (state.wireRadius,
  // state.nodeRadius), so each clears the shell by its OWN radius -- a
  // shared clearance under-cleared whichever one was bigger, and growing
  // the Node size slider alone could push the white dots back through.
  const clearance = netClearance();
  state.objects.wires.position.z = state.showMode === "both" ? clearance.wires : 0;
  state.objects.nodes.position.z = state.showMode === "both" ? clearance.nodes : 0;
  const falsework = state.objects.falsework;
  if (falsework) {
    const wanted = state.formworkMode === "always" && state.showMode !== "framework";
    falsework.visible = wanted;
    if (wanted) {
      falsework.material.opacity = 0.3;
      // Same offset as the always branch in applySceneAtTime above, so
      // the two never disagree about where the ghost sits at rest. The
      // BUNDLE's own thickness, same reason arrowField's lift does at
      // studio.js:1396: state.thickness is the control's live value and
      // can drift from what the shell on screen was actually built at.
      falsework.position.z = -(state.bundle.provenance.thickness / 2) - 0.05;
    }
  }
}

// The framing the take orbits from: the camera's own distance, height and
// bearing about the scene centre, read off the viewport rather than set by
// sliders. Param's ruling, and it is the simpler thing as well as the one
// he asked for: whatever you can see is what the animation shows, from
// where you left it. The current rotation is subtracted out so a capture
// taken mid-take does not jump the camera a quarter turn.
// The controls keep gliding after a drag ends -- that is what damping IS
// -- and any leftovers still in them when a take starts keep nudging the
// camera off the captured base for the next dozen frames: the play-press
// jump's SECOND cause (the first was lookAt re-aiming). One update with
// damping off applies the remainder whole and clears it, so the capture
// that follows reads a camera that has finished arriving.
function settleControls() {
  const damped = controls.enableDamping;
  controls.enableDamping = false;
  controls.update();
  controls.enableDamping = damped;
}

function captureOrbitBase(atT) {
  if (!state.timeline) return;
  // The bearing is captured FOR a clock. The subtraction below must use
  // the t the take will actually RUN from, not whatever the clock reads
  // at capture: captured at the end of a finished take and played from
  // zero, the add-back was nothing while the subtraction was a whole
  // take's turn, and the camera leapt backwards by exactly the previous
  // take's rotation -- Param: "its decided where the start of the
  // animation is, its not based off where the current viewport is".
  const reference = typeof atT === "number" ? atT : state.timeline.t;
  // The orbit turns about what the CAMERA is aimed at, not the bundle's
  // centre: lookAt(state.centre) on the first played frame re-aimed a
  // panned or off-centre view, which read as a jump and a lens change
  // (Param: "it should start exactly where play is started from").
  // The VAULT owns the circle: radius, height and bearing are measured
  // about the scene centre, so the turn keeps the vault in the frame all
  // the way round (Param: "keep the focus on that during its turntable
  // motion"). The AIM starts wherever the user was looking -- lookFrom --
  // and applyTimeline eases it onto the circle's centre, which is what
  // makes the first frame exactly the frame Play was pressed on.
  const centre = state.centre ? state.centre.clone() : controls.target.clone();
  const offset = camera.position.clone().sub(centre);
  const radius = Math.hypot(offset.x, offset.y);
  state.timeline.orbitBase = {
    centre,
    lookFrom: controls.target.clone(),
    aimFromT: reference,
    // Straight overhead there is no bearing to orbit on, so the distance
    // falls back to the true one and the take turns about that instead of
    // collapsing onto the axis.
    radius: radius > 0.05 ? radius : camera.position.distanceTo(centre),
    height: offset.z,
    // The same clamped clock applyTimeline adds back, or a capture taken
    // mid-take jumps the camera by exactly the opening act's length.
    azimuth: Math.atan2(offset.y, offset.x)
      - state.timeline.orbitSpeed * Math.max(0, reference - openingSeconds()),
  };
}

function applyTimeline(t) {
  applySceneAtTime(t);
  const base = state.timeline.orbitBase;
  if (base && state.timeline.autoSpin && !state.userDragging) {
    const centre = base.centre || state.centre;
    // The camera holds its framing through the whole opening act -- the
    // formwork growing into its final form deserves a still witness, Param
    // ruled -- and starts its turn the instant build time begins.
    const angle = base.azimuth
      + state.timeline.orbitSpeed * Math.max(0, t - openingSeconds());
    camera.position.set(
      centre.x + base.radius * Math.cos(angle),
      centre.y + base.radius * Math.sin(angle),
      centre.z + base.height);
    // The aim GLIDES from wherever the user was looking onto the
    // circle's own centre -- by the time the turn begins the vault is
    // framed, and it stays framed for the whole revolution. A capture
    // taken mid-take (a drag's end) eases again from the new framing.
    // Capped: an opening act can run a minute, and a pan that long reads
    // as drift rather than intent. Six seconds is a deliberate camera
    // move, and the vault is framed well before the turn begins.
    const hold = Math.min(6, Math.max(0.8, openingSeconds() - base.aimFromT));
    const u = Math.min(1, Math.max(0, (t - base.aimFromT) / hold));
    const eased = u * u * (3 - 2 * u);
    const aim = base.lookFrom ? base.lookFrom.clone().lerp(centre, eased) : centre;
    camera.lookAt(aim);
    controls.target.copy(aim);
  }
}

// ---------- record mode ----------
async function recordAnimation() {
  const status = document.getElementById("record-status");
  if (!state.timeline || !state.bundle) { status.textContent = "load a study first"; return; }
  // F1: capture the peak from the same source the day-cycle button reads,
  // not the slider -- applyDayCycle's own writes below clamp that slider
  // for display, and reading it back here would let a mid-recording clamp
  // feed into the very peak the recording is driven from.
  if (state.dayCycle.record) state.dayCycle.peakElevation = state.sunElevationSetting;
  const target = "study-" + state.bundle.slug;
  const fps = 60;
  const speed = state.timeline.speed;
  const total = Math.ceil(timelineDuration() / speed * fps);
  status.textContent = "recording " + total + " frames at " + recordingFrame().width + "x"
    + recordingFrame().height + " (a few MB each on disk)";
  const wasPlaying = state.timeline.playing;
  // F2: a live day cycle must not keep advancing off frame()'s wall clock
  // while the recording also drives it off frameIndex -- two clocks racing
  // the same state would make a recording non-deterministic.
  const wasDayCyclePlaying = state.dayCycle.playing;
  state.timeline.playing = false;
  state.dayCycle.playing = false;
  // Everything startPlaying arms, recording must arm too. Without the
  // timeline show mode, applyShowMode erased every computed frame back to
  // the finished vault (and hid the formwork act outright); without an
  // orbit base, applyTimeline held the camera still. Both were only ever
  // set by pressing Play, which is why a recording taken after Play looked
  // fine and a fresh one came out frozen.
  const wasShowMode = state.showMode;
  state.showMode = "timeline";
  paintShowButtons();
  settleControls();
  // A recording always runs from frame zero, so its bearing is captured
  // for t = 0 -- whatever the clock read when Record was pressed.
  captureOrbitBase(0);
  // The chosen frame rides into the take: ratio, FOV and the grade are
  // all camera truths the recording must keep.
  const frame = recordingFrame();
  renderer.setSize(frame.width, frame.height, false);
  composer.setSize(frame.width, frame.height);
  camera.aspect = frame.width / frame.height;
  camera.updateProjectionMatrix();
  state.recording = true;   // resize() must skip while this is set
  try {
    for (let frameIndex = 0; frameIndex < total; frameIndex++) {
      if (state.dayCycle.record) {
        // Deterministic: frameIndex alone drives u, so a recording is
        // reproducible frame for frame like applyTimeline already is. The
        // day maps over the whole recording, so layering it with the build
        // timeline is a deliberate choice a user who checks the box makes.
        applyDayCycle(frameIndex / Math.max(1, total - 1));
        if (state.environmentMode === "sky" && frameIndex % 30 === 0) regenerateEnvironment();
      }
      applyTimeline(frameIndex * speed / fps);
      renderView();
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      const response = await fetch(
        "/api/frames/" + target + "?frame=" + (frameIndex + 1),
        { method: "POST", body: blob });
      if (!response.ok) throw new Error("frame upload failed: " + response.status);
      if (frameIndex % 30 === 0) status.textContent = "frame " + frameIndex + " / " + total;
    }
    if (state.dayCycle.record) {
      // F4: persist the recording's own final sun state, the same way
      // frame()'s live day cycle already does at the end of a play, so the
      // next redraw (a slider nudge, a mode change) does not silently
      // revert the sun mid-review.
      state.sunColourOverride = document.getElementById("sun-colour").value;
      state.sunIntensityOverride = sun.intensity;
    }
    status.textContent = "stitching...";
    const stitched = await fetch("/api/frames/" + target + "/stitch?fps=" + fps, { method: "POST" });
    const body = await stitched.json();
    status.textContent = stitched.ok
      ? "saved " + body.video
      : "stitch failed: " + (body.detail || stitched.status);
  } catch (error) {
    status.textContent = "recording failed: " + error.message;
  } finally {
    // No explicit canvas-size restore here: this flag flip is what lets
    // resize() act again, and it picks the canvas back up to its CSS size
    // (including the composer, via the resize() edit above) on the very
    // next frame().
    state.recording = false;
    state.timeline.playing = wasPlaying;
    state.dayCycle.playing = wasDayCyclePlaying;
    state.showMode = wasShowMode;
    paintShowButtons();
    applyShowMode();
  }
}
document.getElementById("record-button").addEventListener("click", recordAnimation);

// ---------- day cycle ----------
// S5: frame() is the only wall-clock advancer (see below); this button
// only arms/disarms state.dayCycle.playing and captures the elevation the
// arc peaks at, exactly as play-button arms state.timeline.playing.
function trackDragTo(event) {
  const canvasEl = document.getElementById("day-track");
  const rect = canvasEl.getBoundingClientRect();
  const u = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  setSunMinutes(Math.round(u * 1439));
}

// Everything below is module-level initialisation, and a throw here takes
// the whole studio down before the first frame. Each block therefore
// reports itself and lets the rest run: a studio with a dead sun widget is
// a bad afternoon, a studio that will not open is a lost one.
function guarded(what, work) {
  try {
    work();
  } catch (error) {
    console.error(what, error);
    reportProblem("could not set up " + what + ": " + error.message, error);
  }
}

for (const [id, handler] of [["sun-dial", dragSunDial], ["day-track", trackDragTo]]) {
  const element = document.getElementById(id);
  element.addEventListener("pointerdown", (event) => {
    element.setPointerCapture(event.pointerId);
    state.dayCycle.playing = false;
    handler(event);
  });
  element.addEventListener("pointermove", (event) => {
    if (element.hasPointerCapture(event.pointerId)) handler(event);
  });
  element.addEventListener("pointerup", (event) => {
    element.releasePointerCapture(event.pointerId);
  });
}
guarded("the sun instrument", () => {
  sunInstrumentReady = true;
  setSunMinutes(state.sunMinutes);
});

document.getElementById("day-cycle-button").addEventListener("click", () => {
  if (state.dayCycle.playing) {
    state.dayCycle.playing = false;
    document.getElementById("day-cycle-button").textContent = "Day cycle";
    return;
  }
  // F1: read the slider's own last hand-set value, not its live display --
  // applyDayCycle also writes this slider (clamped to its min="5" for
  // display), so reading .value here would let a previous cycle's clamped
  // display become the next cycle's peak, flattening the sun a little more
  // on every play.
  state.dayCycle.peakElevation = state.sunElevationSetting;
  state.dayCycle.t = 0;
  state.dayCycle.playing = true;
  document.getElementById("day-cycle-button").textContent = "Pause";
});
document.getElementById("day-cycle-seconds").addEventListener("input", (e) => {
  state.dayCycle.seconds = +e.target.value;
});
document.getElementById("day-cycle-record").addEventListener("change", (e) => {
  state.dayCycle.record = e.target.checked;
});

// ---------- render loop ----------
function resize() {
  if (state.recording) return;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w || canvas.height !== h) {
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

controls.addEventListener("start", () => { state.userDragging = true; });
controls.addEventListener("end", () => {
  state.userDragging = false;
  rememberSession();
  // Moving the camera mid-take moves the take with it: the orbit carries on
  // from where the drag left off instead of snapping back to where it began.
  if (state.timeline && state.timeline.playing) {
    settleControls();
    captureOrbitBase();
  }
});

// The play control lives twice -- the Animation section and the shelf tab
// strip (Param: "add a play button next to the scene tile") -- and one
// painter keeps their labels telling the same story.
function paintPlayButtons(text) {
  const panel = document.getElementById("play-button");
  if (panel) panel.textContent = text;
  // The shelf's control is an ICON tile: a triangle at rest, two bars
  // while the take runs.
  const shelf = document.getElementById("shelf-play");
  if (shelf) {
    shelf.textContent = text === "Pause" ? "❚❚" : "▶";
    shelf.title = text === "Pause" ? "Pause the animation" : "Play the animation";
  }
}

function startPlaying(fromTheTop) {
  // Playing IS the animation view: it switches to it rather than asking
  // which mode the scene should be in first, and it takes its framing from
  // wherever the camera is standing at that moment.
  state.showMode = "timeline";
  paintShowButtons();
  settleControls();
  // Decide WHERE the clock starts before capturing the bearing for it.
  const fromT = (fromTheTop || state.timeline.t >= timelineDuration())
    ? 0 : state.timeline.t;
  captureOrbitBase(fromT);
  if (fromT !== state.timeline.t) applyTimeline(fromT);
  state.timeline.playing = true;
  paintPlayButtons("Pause");
}

document.getElementById("play-button").addEventListener("click", () => {
  if (!state.timeline) return;
  if (state.timeline.playing) {
    state.timeline.playing = false;
    paintPlayButtons("Play");
    return;
  }
  startPlaying(false);
});
// ---------- the undo history ----------
// A small recorded history (Param's words) of the things a session does
// to a scene: sky, environment, skin, floor, placements, moves, turns,
// scales, deletions. Each entry is a closure that puts ONE thing back;
// the button undoes the most recent. The history belongs to the scene it
// happened in, so switching study empties it.
const undoHistory = [];
const UNDO_CAP = 50;
let undoReplaying = false;

function paintUndoButton() {
  const button = document.getElementById("shelf-undo");
  if (!button) return;
  button.disabled = !undoHistory.length;
  button.title = undoHistory.length
    ? "Undo " + undoHistory[undoHistory.length - 1].label
    : "Nothing to undo yet";
}

function pushUndo(label, undo) {
  // Replaying an undo runs the same handlers that record history; gating
  // here is what keeps undo from writing its own next entry.
  if (undoReplaying) return;
  undoHistory.push({ label, undo });
  if (undoHistory.length > UNDO_CAP) undoHistory.shift();
  paintUndoButton();
}

function clearUndoHistory() {
  undoHistory.length = 0;
  paintUndoButton();
}

async function undoLast() {
  const entry = undoHistory.pop();
  paintUndoButton();
  if (!entry) return;
  undoReplaying = true;
  try {
    await entry.undo();
    logStudio("undid " + entry.label);
  } catch (error) {
    logStudio("could not undo " + entry.label + ": " + error.message);
  } finally {
    undoReplaying = false;
  }
}
document.getElementById("shelf-undo").addEventListener("click", undoLast);

// The selects carry the sky, the environment, the skin and the floor, and
// every road to them -- panel picker or drawer assign -- ends in a change
// event, so one listener per select records them all.
function undoableSelect(id, label) {
  const select = document.getElementById(id);
  let previous = select.value;
  select.addEventListener("change", () => {
    const before = previous;
    previous = select.value;
    if (before === select.value) return;
    // A first-ever choice (the select was still empty) has no before to
    // return to.
    if (!before) return;
    pushUndo(label, () => {
      select.value = before;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });
}
undoableSelect("hdri-select", "the sky change");
undoableSelect("environment-mode", "the environment change");
undoableSelect("render-skin", "the skin change");
undoableSelect("ground-preset", "the floor change");

function removePropRecord(record) {
  if (state.carrying && state.carrying.record === record) {
    state.carrying = null;
    state.propDrag = false;
    controls.enabled = true;
  }
  disposeProp(record.object);
  propsGroup.remove(record.object);
  state.props = state.props.filter((p) => p !== record);
  if (state.selectedProp === record) selectProp(null);
  saveProps();
}

document.getElementById("shelf-play").addEventListener("click", () => {
  document.getElementById("play-button").click();
});
document.getElementById("shelf-restart").addEventListener("click", () => {
  document.getElementById("restart-button").click();
});
document.getElementById("shelf-record").addEventListener("click", () => {
  document.getElementById("record-button").click();
});
document.getElementById("restart-button").addEventListener("click", () => {
  if (!state.timeline) return;
  startPlaying(true);
});

scrubber.addEventListener("input", () => {
  if (!state.timeline) return;
  state.timeline.playing = false;
  paintPlayButtons("Play");
  applyTimeline((+scrubber.value / 1000) * timelineDuration());
  updateHud();
});
for (const [id, prop] of [["orbit-speed", "orbitSpeed"]]) {
  document.getElementById(id).addEventListener("input", (e) => {
    if (state.timeline) { state.timeline[prop] = +e.target.value; applyTimeline(state.timeline.t); }
  });
}
// Speed is a playback rate, not a scene parameter: routing it through the
// loop above would call applyTimeline on every drag tick, which snaps an
// orbited camera back onto the ring for no scene effect at all. It is set
// here instead, alongside the label it already updates, with no
// applyTimeline call.
document.getElementById("timeline-speed").addEventListener("input", (e) => {
  document.getElementById("timeline-speed-value").textContent = (+e.target.value).toFixed(2);
  if (state.timeline) state.timeline.speed = +e.target.value;
});

let lastTime = performance.now();
let playingFrameCount = 0;
let dayCycleFrames = 0;
function frame(now) {
  const delta = Math.min(0.1, (now - lastTime) / 1000);
  lastTime = now;
  resize();
  if (state.timeline && state.timeline.playing) {
    applyTimeline(Math.min(state.timeline.t + delta * state.timeline.speed, timelineDuration()));
    if (state.timeline.t >= timelineDuration()) {
      state.timeline.playing = false;
      paintPlayButtons("Play");
    }
    // M6 fix: the HUD's stage/formwork lines track state.timeline.t, so
    // they must refresh while playing too -- but updateHud is string work
    // best not repeated every single frame, so it runs at a throttled
    // cadence instead of unthrottled per frame.
    playingFrameCount += 1;
    if (playingFrameCount % 15 === 0) updateHud();
  }
  if (state.dayCycle.playing) {
    state.dayCycle.t = Math.min(state.dayCycle.t + delta, state.dayCycle.seconds);
    applyDayCycle(state.dayCycle.t / state.dayCycle.seconds);
    dayCycleFrames += 1;
    // PMREM at most every 30 frames while the sky follows the sun, and once
    // more on the final frame so the ambient lands exactly at sunset.
    if (state.environmentMode === "sky" && (dayCycleFrames % 30 === 0
        || state.dayCycle.t >= state.dayCycle.seconds)) regenerateEnvironment();
    if (state.dayCycle.t >= state.dayCycle.seconds) {
      state.dayCycle.playing = false;
      // The colour input holds the cycle's final (sunset) value; without
      // this, the next applyEnvironment call (a slider nudge, a mode
      // change) would overwrite it with the active preset's own colour.
      // F4: the intensity gets the same treatment, so a sunset that ends
      // dim does not snap back to the preset's full daylight brightness.
      state.sunColourOverride = document.getElementById("sun-colour").value;
      state.sunIntensityOverride = sun.intensity;
      document.getElementById("day-cycle-button").textContent = "Day cycle";
    }
  }
  if (state.timeline && document.activeElement !== scrubber) {
    scrubber.value = Math.round(1000 * state.timeline.t / timelineDuration());
  }
  // While the take's turntable owns the camera, the controls must not
  // also steer it: their damping re-applies whatever inertia remains,
  // every frame, on top of the pinned orbit. A drag mid-take hands
  // ownership back (userDragging), and its end settles and recaptures.
  const turntableOwns = state.timeline && state.timeline.playing
    && state.timeline.orbitBase && state.timeline.autoSpin
    && !state.userDragging;
  if (!turntableOwns) controls.update();
  renderView();
  requestAnimationFrame(frame);
}

// The tile grids are built here, after SKINS and skinMaterialCache exist.
guarded("the material tiles", buildMaterialTiles);
guarded("the ground tiles", buildGroundTiles);
guarded("the weather tiles", buildWeatherTiles);
guarded("the pickers", wireAllPickers);
guarded("the setting segments", () => buildSegmented("environment-segments", "environment-mode"));
guarded("the camera frame segments", () => {
  buildSegmented("camera-aspect-segments", "camera-aspect");
  syncCameraControls();
});
guarded("the slider rows", () => upgradeSliders());
guarded("the panel groups", buildGroups);
// The libraries load in the background: the studio is usable before either
// arrives, a folder with nothing in it simply leaves the old props, and no
// material folder chosen leaves the four built-in skins.
loadPropLibrary().catch((error) => logStudio("prop library: " + error.message));
refreshMaterialLibrary().catch(
  (error) => logStudio("material library: " + error.message));
// Said once at boot, and printed in the panel. A page that reports the same
// build after an edit is a cached page, which is a different problem from a
// change that did not land, and the two have been confused three times.
logStudio("studio build "
  + ((document.getElementById("build-stamp") || {}).textContent || "unstamped"));
showMaterialFolder();
// The sky list used to be reachable only by entering HDRI mode, so the Sky
// picker showed a placeholder word until then and a remembered sky was not
// offered back. Built at boot, like every other library.
refreshHdriList(null).catch(() => {});
showLibraryFolder("hdri", "hdri-folder-path", "skies");
showLibraryFolder("props", "props-folder-path", "models");
showLibraryFolder("ground-materials", "ground-folder-path", "materials");
boot();
requestAnimationFrame(frame);

// The probe rig reads app state through this hook. Camera and controls are
// exported too so a capture run can frame a detail (the rim, a joint) that
// the default framing, tuned for a full-size vault, leaves illegible.
// applyDayCycle is exposed too (Task 3), so a probe can drive u directly
// through the real pure function instead of re-deriving its formula in
// probe-script JS, which would drift from the function it is meant to check.
// placeProp joins them so a probe can populate a scene without synthesising
// a pointer gesture per prop. Placing twenty by hand through click events is
// how a check nobody runs gets written.
window.__studio = { state, scene, camera, controls, applyDayCycle, placeProp,
  ensurePropTemplate, renderObjectPreview };
// The page's boot-fault banner (index.html) stands down once evaluation has
// made it to here: from this line on, a stray rejection is an incident for
// the diagnostics log, not a "half-built panel" alarm.
window.__studioReady = true;

export { state, buildScene, setLayer, applyCut, applyTimeline, timelineDuration, rebuildTimeline };
