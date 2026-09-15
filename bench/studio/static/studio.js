import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Sky } from "three/addons/objects/Sky.js";
import { GroundedSkybox } from "three/addons/objects/GroundedSkybox.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { buildLiveSeries, liveSpecs, liveCut, seriesToCsv } from "./live_graphs.js";
import {
  upgradeSliders, paintScrub, repaintScrubs, settleRangeFills,
  buildSegmented, paintSegmented,
  buildGroups, paintGroupSummaries, setGroupSummaries,
} from "/static/panel.js";
import {
  readMechanism, checkNetVertices, checkRouteDirection, turnsFor,
  wireCentreline, reelContactRadius, ribChain, chainLength,
  derivePlacements, SPOOL_RADIUS_LIMIT,
} from "/static/mechanism.js";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { Pass, FullScreenQuad } from "three/addons/postprocessing/Pass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { BrightnessContrastShader } from "three/addons/shaders/BrightnessContrastShader.js";
import { RectAreaLightUniformsLib } from "three/addons/lights/RectAreaLightUniformsLib.js";
import {
  boxUVs, segmentUVOffset, segmentWindow, sheetUVs, footprintSpan, uvQuarterTurn,
  smoothStressField, interpolateScalarField,
  sampleScalar, sampleVector, creaseNormals, estimateSunFromEquirect,
  interpolateFormworkFrame, machineTime, machineRetreats, formworkVisibility,
  groundRepeat, finalOrbitTurn,
  sunPosition, sunLight, timeAtElevation, utcOffsetMinutes, localClockMinutes,
  FLY_SPEEDS, FLY_KEYS, flyStep, lensStep, lookTurn,
  fixtureFaces, spotShadowGrants, screenGroundAxes, arrowStep,
} from "/static/fields.js";
import { equirectHorizonColour } from "/static/fields.js";
import {
  applyTiling, LATTICE_SCALE, BLEND_SHARPNESS, TILED_CHUNKS,
} from "/static/tiling.js";
import {
  applyWind, windParameters, windUniformsFrom, adoptWind, WIND_DEFAULTS,
} from "/static/wind.js";
import { completeScene, SCENE_VERSION } from "/static/scene_defaults.js";
import {
  ATMOSPHERE_PRESETS, ATMOSPHERE_SKY_GLSL, ATMOSPHERE_LINEAR_OFF,
  atmosphereFromPreset, adoptAtmosphere, atmosphereIsOn, atmosphereLayers,
  atmospherePreviewPixels, createAtmosphere, installAtmosphere, writeAtmosphere,
  SHAFT_STEPS, SHAFT_MAX_DISTANCE, SHAFT_GAIN, SHAFTS_GLSL, SHAFTS_COMPOSITE_GLSL,
  SHAFT_PLATE_STEPS, SHAFT_MAX_STEPS, SHAFT_ACCUMULATE, SHAFT_GOLDEN, SHAFTS_ACCUMULATE_GLSL,
  SHAFTS_VERTEX, shaftsStrength,
} from "/static/atmosphere.js";
import {
  loadLibraryMaterial, disposeLibraryMaterial, tileUrl, setRepeat, setSurface,
  repeatsFor, DEFAULT_TILE_METRES, VIEWPORT_PX, GROUND_BASE,
  CONSTRAINED_DEVICE,
} from "/static/pbr.js";
import {
  computeAnalysisInput, buildAnalysisHtml, buildGraphSpecs,
} from "/static/data_analysis.js";

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
  mechanism: null,     // bench.mechanism/1 payload, or null: the machine's SHAPE (see buildMachine)
  showMachine: true,   // Param's ruling: the machine rides with the formwork, with its own toggle
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
  cameraAspect: "fill",  // the Camera frame: "fill" or a ratio as a string
  projection: "perspective",  // or "orthographic": a picture, or a drawing
  stillSize: "a3-300",   // the plate the Render button writes
  detail: "balanced",    // how soon distant props drop detail in the viewport; stills and takes ignore it
  stillRendering: false, // a plate in flight; the button and resize both check it
  // The cut. mode "off" or "plane"; axis is which way the plane
  // faces; offset is where along that axis it sits, in metres.
  section: { mode: "off", axis: "y", offset: 0, cutMachine: false },
  cameraView: null,      // the snapped view last taken, for the highlight
  weatherPreset: "clear",    // E2: a key of WEATHER
  // The atmosphere (atmosphere.js): a preset key and its dials. None until
  // he picks one, in every environment mode, so nothing changes unasked.
  atmosphere: atmosphereFromPreset("none"),
  // Calm until he turns it up (wind.js), so nothing already made moves.
  wind: { ...WIND_DEFAULTS },
  groundPreset: "dark-studio", // E4: a key of GROUNDS, independent of the environment mode
  groundRadius: 60,     // the floor disc's radius in metres, the Ground size slider (rebuildGround)
  // The floor texture's own dials: per-axis scale multipliers over the
  // real-world repeat, its own relief depth, and a slid offset from the
  // Randomise button (rebuildGround applies all four).
  // `breakup` is the per-tile randomising (tiling.js); `seed` is which
  // arrangement of it, so Randomise can hand him a different one.
  ground: { scaleX: 1, scaleY: 1, relief: 1, offset: [0, 0], rotation: 0,
    breakup: false, seed: [0, 0] },
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
  // The scatter's rules. Param: "select the props we want, how often each
  // one appears, the size ratio we pick, and some other relevant
  // settings". species is [{ type, weight }]; everything else is the
  // recipe a Dice re-rolls without changing.
  scatter: {
    species: [], spacing: 0.9, sizeMin: 0.8, sizeMax: 1.3,
    clump: 30, clumpSize: 6, clearance: 1.5, turn: 360, seed: 1,
    radius: 4,
  },
  scatterStroke: 0,     // bumped per brush click, mixed into the seed
  scatterBrushLayer: null,  // the open layer, taken when a scatter tool is armed
  scatterRuns: [],      // [{ layer, records, minted }], newest last, for Remove last
  scatterArmed: false,  // waiting for him to drag a rectangle on the floor
  propDrag: false,
  hdriTexture: null,         // E3: the decoded equirect, set by loadHdri (Task 4)
  hdriName: null,
  hdriProjection: "projected", // Task 2: "projected" builds a GroundedSkybox dome; "infinite" is the flat equirect background
  hdriScale: 60,       // GroundedSkybox radius, metres
  hdriHeight: 2,        // GroundedSkybox height (camera height above ground in the source photo), metres
  hdriRotation: 0,      // degrees, spins the dome/background about the world vertical
  skyBrightness: 1,     // multiplies the environment mode's own intensity
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
  recordStop: false,   // set by pressing the button again; the loop checks it each frame
  analysisSliders: { loadsScale: 1, reactionsScale: 1, forcesScale: 1,
                     thrustScale: 1 },
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
  outline: 0,            // the dark line inked round each voussoir, in metres
  // What a newly placed lamp is given, and what the Lights sliders write
  // to when no single lamp is selected. The literals are LAMP_LUMENS and
  // LAMP_KELVIN, which are declared with the lamp itself far below: a
  // reference here would be reading them before they exist.
  lampLumens: 4000,      // a small floodlight, in the units lamps are sold in
  lampKelvin: 3000,      // warm white
  lampTint: "#ffffff",   // the gel the next fixture wears: white is none
  lampInvisible: false,  // whether the next fixture shows its body at all
  // The next SPOT's beam. Its own object, because four loose fields
  // beside three lamp ones is where a state block stops being readable.
  spot: { aperture: 45, softness: 0.35, reach: 0, shadow: true },
  hdriBackdrop: null,    // the sharp visible sky, separate from the one that lights
  materialLibrary: [],   // the SKIN index from /api/materials, or empty
  materialRoot: "",      // where it is being read from, for the panel
  groundLibrary: [],     // the GROUND index from /api/ground-materials
  groundRoot: "",        // its folder, for the panel
};

const canvas = document.getElementById("view");
const scrubber = document.getElementById("timeline-scrubber");
// The live graphs' state, declared this early because applyTheme runs
// during boot and invalidates them (see "the live graphs" far below).
const liveGraphs = { series: null, specs: null, cards: new Map(), shown: false,
  wanted: true, dirty: true, building: false, lastK: -1, drawnK: -1, prestress: 0.1,
  tucked: false };
const LIVE_GRAPHS_KEY = "vaulted-live-graphs";
const LIVE_PRESTRESS_KEY = "vaulted-live-prestress";
// Tucked to the side or not, as he left it; nothing stored is expanded.
const LIVE_TUCKED_KEY = "vaulted-live-graphs-tucked";
try {
  liveGraphs.wanted = localStorage.getItem(LIVE_GRAPHS_KEY) !== "0";
  liveGraphs.tucked = localStorage.getItem(LIVE_TUCKED_KEY) === "1";
  // Nothing stored is not zero: +null is 0, and a fresh browser opened
  // with the dial at nought and every cable slack through the act.
  const stored = localStorage.getItem(LIVE_PRESTRESS_KEY);
  const kept = stored === null ? NaN : +stored;
  if (Number.isFinite(kept) && kept >= 0 && kept <= 1) liveGraphs.prestress = kept;
} catch (error) { /* default on, a tenth */ }
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
// LOCAL clipping, not global. A plane set on the renderer cuts
// everything the renderer draws -- the gumball, the thrust arrows, the
// lamp halos, the sun helpers -- and makes it impossible to cut the
// shell while the machine stands beside it, which is exactly the
// drawing Param described. Per-material costs one walk of the scene
// whenever the section moves and buys the whole distinction.
renderer.localClippingEnabled = true;

// Every exposure number in this file was tuned by eye against ACES, and so
// carries ACES's hidden 1/0.6 inside it. Neutral applies no such gain, so
// the factor is put back here once rather than rewritten into a dozen
// presets whose numbers would then mean nothing to anybody reading them.
const EXPOSURE_GAIN = 1 / 0.6;

// The atmosphere's fog chunks and shared uniforms (atmosphere.js), put in
// place before the first program is built with fog: a program compiled
// under three's own chunks is cached under the same key and never picks
// these up. Nothing is fogged at boot, so this line is early enough; it
// sits up here so nothing that renders ever can come before it.
const atmosphere = createAtmosphere(THREE);

// ---------- the wind's shared air ----------
// One set of uniform objects every swaying material holds by reference, the
// prop's own and its shadow's alike, so one write moves both (wind.js says
// why that is the whole of it). windTime runs with the live view while there
// is any wind at all, stands still for a still, and is the take's own clock
// in a take, frame by frame, so a take is reproducible.
const windAir = {
  windTime: { value: 0 },
  windStrength: { value: 0 },
  windGusts: { value: 0.5 },
  windDirection: { value: new THREE.Vector2(1, 0) },
};
let windWarned = false;

// The one onBeforeCompile every swaying material wears. A named function
// shared by all of them, so three builds one program per variant and every
// material keeps its own model's numbers (this.userData.windModel). It
// calls the atmosphere's injector itself, because a material's own hook
// shadows the one on the prototype.
function windCompile(shader) {
  atmosphere.inject(shader);
  const reached = applyWind(shader, THREE.ShaderChunk,
    Object.assign({}, windAir, this.userData.windModel));
  if (!reached && !windWarned) {
    windWarned = true;
    reportProblem("the vendored vertex chunks no longer have the shape wind.js "
      + "splices into; placed props will stand still in the wind until it is "
      + "checked against three 0.185.0's project_vertex and worldpos_vertex");
  }
}

// Every material that sways wears it the same way.
function wearWind(material, windModel) {
  material.userData.windModel = windModel;
  material.onBeforeCompile = windCompile;
  material.needsUpdate = true;
  return material;
}

function applyWindState() {
  const air = windUniformsFrom(state.wind);
  windAir.windStrength.value = air.strength;
  windAir.windGusts.value = air.gusts;
  windAir.windDirection.value.set(air.direction[0], air.direction[1]);
}
if (!installAtmosphere(THREE, atmosphere.inject)) {
  reportProblem("the vendored fog chunks no longer have the shape the "
    + "atmosphere replaces; the height fog may be wrong until atmosphere.js "
    + "is checked against three 0.185.0's fog_fragment and fog_vertex");
}
// How much of the sun's light a Sun glow of 100% puts in the lobe, tuned
// by eye against the Sky's horizon so a golden hour glows without a noon
// blowing out.
const ATMOSPHERE_SUN_GAIN = 0.22;
// What is left of a moonlit fog at the bottom of the night, as a share of
// the moon's colour: faint, and blue, so a night fog still reads as air.
const ATMOSPHERE_NIGHT_FLOOR = 0.035;
// The Reinhard exposure the server bakes an HDRI backdrop with
// (hdri_preview.preview_rows: _tone(value, 3.2)), so the horizon colour
// the fog fades to is the one the backdrop actually shows.
const BACKDROP_REINHARD_EXPOSURE = 3.2;

const scene = new THREE.Scene();
// TWO CAMERAS, ONE BINDING. `camera` is a let, not a const, and every one
// of the hundred-odd places that reads it picks up whichever projection
// is current. The alternative -- keeping a PerspectiveCamera and writing
// an orthographic projectionMatrix into it -- renders correctly and picks
// wrongly, because Raycaster.setFromCamera branches on isPerspectiveCamera
// and would go on building cone rays through an orthographic frame. The
// gumball would drift from the pointer and nothing would say why.
const perspectiveCamera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
const orthographicCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, -500, 500);
let camera = perspectiveCamera;
camera.position.set(24, -24, 14);
camera.up.set(0, 0, 1);
orthographicCamera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
const propRaycaster = new THREE.Raycaster();

const pmrem = new THREE.PMREMGenerator(renderer);
const studioEnvironment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environment = studioEnvironment;

// ---------- the reflection capture ----------
// Param, 2026-09-13, over a dark olive block under the arch: "I really
// need the anchor to be a better material. use the steel polished dark
// material we have."
//
// IT ALREADY WORE IT, and measured, it had loaded whole: Metal036's
// colour, normal and roughness maps, metalness 1. What it could not do
// was look like steel, because a polished metal shows almost nothing but
// its surroundings -- and its surroundings, to three, are the ENVIRONMENT
// MAP, which is the HDRI. His sides of dark steel were faithfully
// mirroring the green meadow on the horizon of evening_meadow, a meadow
// that is nowhere in a scene he has filled with beech wood, and the
// colour map's 0.28 average (reflecting 6.5 per cent) left the olive as
// the only thing to see. No finish fixes that; the reflection is of the
// wrong world.
//
// So, as Unreal does with a reflection capture: a cube photograph of the
// ACTUAL scene, taken where the steel stands, and handed to the parts
// that wear the polished steel in place of the HDRI. Measured in his own
// setup: the anchor went from olive to dark steel grey, and the capture
// took 108 ms on a software rasteriser.
//
// It is taken when the scene has settled after a change, never per
// frame, and never during a take (the sun moving would ask for six extra
// renders a frame); a still and a take each take one as they begin.
const REFLECTION_SIZE = 256;
const REFLECTION_SETTLE_MS = 400;
// A person's eye above the lowest part that wears it: the anchor sits on
// the ground, and a capture on the ground would see only the floor.
const REFLECTION_EYE = 0.8;
const reflectionTarget = new THREE.WebGLCubeRenderTarget(REFLECTION_SIZE, {
  type: THREE.HalfFloatType, generateMipmaps: true,
  minFilter: THREE.LinearMipmapLinearFilter });
const reflectionCamera = new THREE.CubeCamera(0.05, 2000, reflectionTarget);
// When the scene last changed in a way the capture would see, or 0 once
// it has been taken since.
let reflectionDirtyAt = 1;
// Bumped by anything that changes what the light rays would draw without
// moving the camera, the sun or the fog, which the rays' own signature
// already watches (shaftsChanged). Declared here, above its first caller.
let shaftsRevision = 0;
let reflectionsTaken = 0;

function noteReflectionsChanged() { reflectionDirtyAt = performance.now(); shaftsRevision += 1; }

// How bright the environment is, as the MODE'S OWN base times his dial.
// Param: "if i want to darken the hdri so that its dark enough for the
// lights to work well, we dont have that option". There was none: each
// environment mode wrote environmentIntensity outright and nothing could
// move it afterwards, so a sky bright enough to see by drowned every
// fixture placed under it. The base is remembered here so the dial
// multiplies the preset rather than replacing it, and the background is
// dimmed with it or a dark scene sits inside a blazing photograph.
let environmentBase = 1.0;

function setEnvironmentIntensity(base) {
  environmentBase = base;
  applySkyBrightness();
}

// ---------- daylight, and the night ----------
// Param's screenshot: the Night preset, Brightness at 0, and a scene in
// full afternoon. Three faults stood behind it. The dial reached only the
// environment map: the sun stayed at 3.0, the hemisphere at 0.5, the
// studio backdrop at its daytime tone, and in sky mode the sky itself is
// a MESH that backgroundIntensity never touches. The instrument floored
// the sun at 0.35 "so a night scene is lit by something", so no hour was
// ever dark. And the Night preset placed the sun at twenty degrees, which
// is an afternoon under a dark fog.
//
// So: every daylight source is a BASE times the one dial (the sun, the
// sky light, the sky mesh, the backdrop, the fog, the HDRI dome, the
// environment); the sun goes out below the horizon and a moon takes the
// shadow over; the sky light, the sky and the fog fade with the night
// factor; stars come out; and Night is an hour, not an angle.
const lightBase = {
  sun: 3.0,          // the sun's, or the moon's, intensity before the dial
  hemi: 0.5,         // the sky light's, before the dial and the night
  backdrop: null,    // the studio backdrop's daytime colour, a THREE.Color
  fog: null,         // the fog's daytime colour, or null
};
// Moonlight against full sun. Physically nearer one part in four hundred
// thousand, but the eye adapts and a picture cannot: eight per cent is a
// moonlit night that still shows where the vault stands (five, measured,
// left it a black hole wherever no lamp reached).
const MOON_STRENGTH = 0.08;
const MOON_COLOUR = 0xb4c4e0;
// The ramp's own top, 0.35 + 2.9, from before the floor went.
const FULL_SUN = 3.25;
// What is left of the sky light at the bottom of the night: a tenth. The
// moon lights the night; this is the sky's own faint glow on the shadowed
// side, without which a moonlit shadow is a hole in the picture.
const NIGHT_FLOOR = 0.1;
// What the visible sky is multiplied by (see the Sky's shader patch).
const skyDaylight = { value: 1 };
// False until the instrument has been placed once, so applyEnvironment
// can run during boot before the sun has a time to be at.
let sunInstrumentReady = false;

// How much day is left in the sky: 1 with the sun two degrees up, 0 at
// twelve below (astronomical twilight is eighteen; twelve is where a
// picture reads as night), smooth between.
function nightFactor(elevation) {
  const t = Math.max(0, Math.min(1, (elevation + 12) / 14));
  return t * t * (3 - 2 * t);
}

function daylightNow() {
  return sunInstrumentReady ? nightFactor(currentSun().elevation) : 1;
}

function applySkyBrightness() {
  const dial = state.skyBrightness;
  const night = daylightNow();
  scene.environmentIntensity = environmentBase * dial;
  // The studio's room environment is stand-in daylight and knows no
  // clock, so it takes the night here; a sky's PMREM is captured dark
  // already, and a photograph's daylight is the photograph's own.
  if (state.environmentMode === "studio") {
    scene.environmentIntensity *= Math.max(NIGHT_FLOOR, night);
  }
  scene.backgroundIntensity = dial;
  sun.intensity = lightBase.sun * dial;
  // Sky light is the sky's: it goes with the night. The sun's own floor
  // is the moon (applySunFromTime).
  hemi.intensity = lightBase.hemi * dial * Math.max(NIGHT_FLOOR, night);
  // The visible sky, for the eye. The PMREM takes it WITHOUT the dial
  // (regenerateEnvironment), or the environment would be dimmed twice.
  skyDaylight.value = dial * (0.03 + 0.97 * night);
  if (lightBase.backdrop && scene.background && scene.background.isColor) {
    scene.background.copy(lightBase.backdrop).multiplyScalar(dial * (0.08 + 0.92 * night));
  }
  if (lightBase.fog && scene.fog) {
    // The fog follows the backdrop it fades into: the sky's night in Sky
    // mode (as it always has), the studio wall's in Studio, and none in
    // HDRI, where the photograph keeps its own daylight.
    const fogNight = state.environmentMode === "hdri" ? 1
      : state.environmentMode === "studio" ? 0.08 + 0.92 * night : 0.06 + 0.94 * night;
    scene.fog.color.copy(lightBase.fog).multiplyScalar(dial * fogNight);
  }
  paintAtmosphereLight(dial, night);
  // A photograph's dome is a lit mesh, not a background: dimmed by its
  // own colour, which multiplies the map.
  if (hdriDome) hdriDome.children[0].material.color.setScalar(dial);
  stars.material.opacity = (1 - night) * Math.min(1, dial);
  stars.visible = state.environmentMode === "sky" && stars.material.opacity > 0.01;
}
// The atmosphere's light, written wherever the day's light is (the end of
// the daylight chain above, so the clock, the day cycle and the dial all
// reach it): the sun's glow in the fog is the sun's own colour and power,
// the moon's by night, from where it stands; and a moonlit fog keeps a
// faint blue floor rather than going to black. The Sky's copy of the fog
// colour follows the scene's, so the two meet at the horizon.
function paintAtmosphereLight(dial, night) {
  const uniforms = atmosphere.uniforms;
  const on = atmosphereIsOn(state.atmosphere);
  if (on && scene.fog && state.environmentMode !== "hdri") {
    scene.fog.color.add(new THREE.Color(MOON_COLOUR)
      .multiplyScalar(ATMOSPHERE_NIGHT_FLOOR * dial * (1 - night)));
  }
  if (scene.fog) uniforms.atmoSkyColour.value.copy(scene.fog.color);
  uniforms.atmoSunColour.value.copy(sun.color).multiplyScalar(on
    ? sun.intensity * (state.atmosphere.sunGlow / 100) * ATMOSPHERE_SUN_GAIN : 0);
  uniforms.atmoSunDir.value.copy(sun.position).normalize();
}

// The floor the fog lies on moves with the study (groundLevel reads the
// bundle), so its base is settled every frame; one subtraction.
function settleAtmosphereFloor() {
  atmosphere.uniforms.atmoBase.value =
    (state.bundle ? groundLevel() : 0) + state.atmosphere.base;
}

// The one fog object, made the first time any fog is wanted and kept for
// the life of the page (applyEnvironment). A new Fog per call made every
// fogged material ask for its program again (three compares the fog by
// identity), and flipping fog on and off recompiles them all.
let atmosphereFog = null;
// The horizon colours the atmosphere fades to, per mode: the Sky's, read
// back from the sky itself at each regeneration, and a photograph's,
// averaged from its horizon band on load. null until known.
let skyHorizon = null;
let hdriHorizon = null;

// The atmosphere's densities and the old linear fog's range. The linear
// term is the weather's own haze, and stays exactly as it was in Sky mode
// while the atmosphere is None; once the atmosphere is chosen it owns the
// fog and the linear term is pushed out of sight. A plan or an elevation
// (orthographic) is a drawing, and stays clean.
function applyAtmosphere() {
  const on = atmosphereIsOn(state.atmosphere);
  if (atmosphereFog) {
    const linear = state.environmentMode === "sky" && !on;
    const preset = WEATHER[state.weatherPreset];
    atmosphereFog.near = linear ? preset.fogNear : ATMOSPHERE_LINEAR_OFF;
    atmosphereFog.far = linear ? preset.fogFar : 2 * ATMOSPHERE_LINEAR_OFF;
  }
  writeAtmosphere(atmosphere.uniforms, on && !camera.isOrthographicCamera
    ? atmosphereLayers(state.atmosphere, state.bundle ? groundLevel() : 0) : null);
  applyShafts();
}

// How hard the shafts are driven, and whether the pass runs at all.
// AT ZERO IT DOES NOT RUN: the composer skips a disabled pass outright,
// so the frame is the frame it was before the shafts existed, down to
// the number of buffer swaps, and the depth attachment stops being
// resolved, which is the only per-frame cost it has. A plan or an
// elevation gets none either, for the reason the fog gets none: a
// world-distance march from a parallel projection is not a measurement
// of anything.
function applyShafts() {
  if (!shaftsPass) return;
  const strength = camera.isOrthographicCamera ? 0 : shaftsStrength(state.atmosphere);
  shaftsPass.march.uniforms.shaftStrength.value = strength;
  composerTarget.resolveDepthBuffer = strength > 0;
  composer.renderTarget2.resolveDepthBuffer = strength > 0;
}

// Whether the pass runs THIS frame, settled before the composer walks
// its list. The shadow map does not exist until something has been
// drawn with a shadow in it, and marching a map that is not there is a
// black frame, so the arming asks for it every frame rather than
// latching a decision taken at boot.
function armShafts() {
  if (!shaftsPass) return;
  const map = sun.shadow.map;
  shaftsPass.enabled = shaftsPass.march.uniforms.shaftStrength.value > 0
    && !!(map && map.depthTexture);
}

// WHETHER THE VIEW HAS HELD STILL since the last frame, for the rays' live
// refinement: everything the march reads that is not in the depth buffer,
// and the revision the rest of the studio bumps. The triangles drawn so far
// this frame stand in for what the depth buffer holds: a layer hidden, a
// study loaded or a prop tier swapped changes them. A gesture of any kind
// on the page bumps the revision, so a prop dragged at constant triangles
// is seen too.
const shaftSignature = new Float64Array(80);

function shaftsChanged() {
  let i = 0;
  let changed = false;
  const put = (value) => {
    if (shaftSignature[i] !== value) { shaftSignature[i] = value; changed = true; }
    i += 1;
  };
  for (const e of camera.matrixWorld.elements) put(e);
  for (const e of camera.projectionMatrix.elements) put(e);
  for (const e of sun.shadow.matrix.elements) put(e);
  const u = atmosphere.uniforms;
  put(u.atmoDensity.value.x); put(u.atmoDensity.value.y);
  put(u.atmoFalloff.value.x); put(u.atmoFalloff.value.y);
  put(u.atmoBase.value); put(u.atmoSunStart.value); put(u.atmoMaxOpacity.value);
  put(u.atmoSunExponent.value);
  put(u.atmoSunDir.value.x); put(u.atmoSunDir.value.y); put(u.atmoSunDir.value.z);
  put(u.atmoSunColour.value.r); put(u.atmoSunColour.value.g); put(u.atmoSunColour.value.b);
  put(shaftsPass.march.uniforms.shaftStrength.value);
  put(shaftsPass.width); put(shaftsPass.height);
  put(shaftsRevision);
  put(renderer.info.render.triangles);
  put(windAir.windTime.value);
  put(windAir.windStrength.value);
  return changed;
}

// Any gesture on the page may have changed the scene without changing
// anything the signature reads.
for (const kind of ["pointerdown", "pointerup", "wheel", "keydown", "input", "change"]) {
  window.addEventListener(kind, () => { shaftsRevision += 1; }, true);
}
window.addEventListener("pointermove", (event) => {
  if (event.buttons) shaftsRevision += 1;
}, true);

// This frame's matrices, written from inside the pass (see settle).
function settleShafts() {
  const uniforms = shaftsPass.march.uniforms;
  const map = sun.shadow.map;
  if (!map || !map.depthTexture) return;
  // Settled now, while the matrices are this frame's: the view refines only
  // on a frame that matches the one before it.
  shaftsPass.still = !shaftsChanged();
  uniforms.shaftShadowMap.value = map.depthTexture;
  uniforms.shaftShadowMatrix.value.copy(sun.shadow.matrix);
  uniforms.shaftEye.value.copy(camera.position);
  uniforms.shaftCameraWorld.value.copy(camera.matrixWorld);
  uniforms.shaftProjectionInverse.value.copy(camera.projectionMatrixInverse);
  // The slab is what a bias in metres has to be measured against: the
  // map's depth runs across sun.shadow.camera, so half a metre of it is
  // half a metre divided by its depth. Enough to clear the map's own
  // texel slope, little enough that a shaft still meets its caster.
  const slab = Math.max(1, sun.shadow.camera.far - sun.shadow.camera.near);
  uniforms.shaftBias.value = 0.5 / slab;
  // Where this tile sits in the WHOLE plate, so the dither each pixel
  // gets is the one it would have had in a plate rendered in one piece.
  // gl_FragCoord counts up from the bottom and a view offset counts down
  // from the top, which is the whole of the second term.
  const view = camera.view;
  if (view && view.enabled) {
    uniforms.shaftPixelOrigin.value.set(
      view.offsetX, view.fullHeight - view.offsetY - view.height);
  } else {
    uniforms.shaftPixelOrigin.value.set(0, 0);
  }
}

// A still and a take march at full resolution with no upsample at all;
// the live view marches at half and blends the result back. Called
// around both, and the composer hands the pass its new size on the way
// through, so this only has to say which scale is wanted.
function setShaftResolution(full) {
  if (!shaftsPass) return;
  shaftsPass.fullResolution = full;
  shaftsPass.setSize(shaftsPass.width, shaftsPass.height);
  // A plate's frames are not the live view's, and a live view coming back
  // from a plate refines afresh.
  shaftsPass.accumulated = 0;
  shaftsRevision += 1;
}
let environmentTarget = null; // the disposable PMREM target behind sky/hdri modes
let hdriDome = null; // the disposable GroundedSkybox group, hdri mode + projected only (Task 2)

// R2: render, tone-map to display space, then grade. Contrast pivots
// around mid grey, which is only meaningful AFTER tone mapping, so the
// grade pass sits last, on the OutputPass's sRGB result. samples: 4
// keeps the antialiasing the direct canvas render had.
// The depth attachment the light shafts march against. In r185 this
// texture hangs on the single-sample framebuffer and the multisampled
// one is blitted into it, DEPTH_BUFFER_BIT and all; measured on this
// GPU (Brave, ANGLE D3D11, RTX 4090, no multisampled_render_to_texture)
// the resolved depth came back identical texel for texel to the same
// scene drawn with no MSAA at all, so the shafts read the frame the
// eye is actually shown rather than a depth pre-pass of their own.
// resolveDepthBuffer is FALSE until the shafts are turned on, so a
// studio that never uses them pays for the allocation and nothing else.
const composerTarget = new THREE.WebGLRenderTarget(1, 1, {
  samples: 4, type: THREE.HalfFloatType,
  depthTexture: new THREE.DepthTexture(1, 1),
});
composerTarget.resolveDepthBuffer = false;
// EffectComposer clones this target for its second buffer, and a clone
// is a structural copy: the second buffer gets a depth texture of its
// OWN. That matters because the shafts add a third swapping pass, so
// the RenderPass draws into either buffer depending on the frame, and
// the pass reads the depth of whichever one it was handed.
const composer = new EffectComposer(renderer, composerTarget);
// Held, not anonymous: switching projection means handing this pass the
// other camera, and a pass nobody has a name for cannot be told.
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);

// ---------- the light shafts ----------
// Param asked for "a fog but super detailed nice fog we might find in
// the likes of unreal engine". The height fog (atmosphere.js) is the
// analytic half of that and it is blind to what stands in the way: air
// in the vault's shadow glows exactly as brightly as air beside it. This
// is the volumetric half. It marches the sun's shadow map through the
// same fog, so a low sun behind the vault throws real shafts between the
// ribs and leaves the air behind them dark.
//
// It sits straight after the RenderPass, which means what it adds is
// linear HDR and the OutputPass tone maps it afterwards: an inscatter
// above 1 is legal here and comes back as a highlight rather than as
// clipped white. (The grade is last of all, on the tone-mapped result,
// which is why the order of these four passes is not arbitrary.)
//
// HALF RESOLUTION for the live view, put back with a depth-aware
// upsample; FULL resolution, no upsample, for a still and for a take.
// A plate is drawn in tiles through camera.setViewOffset, and anything
// that reads its neighbours reads the wrong ones across a tile edge --
// the tiling comment in renderStill says so in full. At full resolution
// every pixel is its own answer and a tile is exactly the piece of the
// plate it stands for.
class ShaftsPass extends Pass {
  constructor(shared) {
    super();
    this.march = new THREE.ShaderMaterial({
      name: "shafts.march",
      defines: { SHAFT_MAX_STEPS, SHAFT_GAIN },
      // The atmosphere's own uniform objects, by reference, so the fog
      // the shafts are made of is the same fog the surfaces wear: one
      // write of a density moves both.
      uniforms: Object.assign({
        tDepth: { value: null },
        shaftShadowMap: { value: null },
        shaftShadowMatrix: { value: new THREE.Matrix4() },
        shaftProjectionInverse: { value: new THREE.Matrix4() },
        shaftCameraWorld: { value: new THREE.Matrix4() },
        shaftEye: { value: new THREE.Vector3() },
        shaftStrength: { value: 0 },
        shaftBias: { value: 0 },
        shaftMaxDistance: { value: SHAFT_MAX_DISTANCE },
        shaftPixelOrigin: { value: new THREE.Vector2() },
        shaftSteps: { value: SHAFT_STEPS },
        shaftSeed: { value: 0 },
      }, shared),
      vertexShader: SHAFTS_VERTEX,
      fragmentShader: SHAFTS_GLSL,
    });
    this.composite = new THREE.ShaderMaterial({
      name: "shafts.composite",
      uniforms: {
        tDiffuse: { value: null },
        tShafts: { value: null },
        tDepth: { value: null },
        // The same matrix object the march holds, so the upsample
        // measures distance the way the march measured it.
        shaftProjectionInverse: this.march.uniforms.shaftProjectionInverse,
        shaftLowResolution: { value: new THREE.Vector2(1, 1) },
        shaftUpsample: { value: 1 },
      },
      vertexShader: SHAFTS_VERTEX,
      fragmentShader: SHAFTS_COMPOSITE_GLSL,
    });
    this.accumulate = new THREE.ShaderMaterial({
      name: "shafts.accumulate",
      uniforms: { tHistory: { value: null }, tCurrent: { value: null }, weight: { value: 1 } },
      vertexShader: SHAFTS_VERTEX,
      fragmentShader: SHAFTS_ACCUMULATE_GLSL,
    });
    const buffer = () => new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.HalfFloatType, depthBuffer: false });
    // Half resolution for the live view while it moves; full resolution for
    // a plate, and for the live view once it holds still, which adds its
    // frames together in `history` through `scratch`.
    this.target = buffer();
    this.full = buffer();
    this.history = buffer();
    this.scratch = buffer();
    // How many refining frames `history` holds, and whether the view has
    // held still since the last frame (settleShafts decides).
    this.accumulated = 0;
    this.still = false;
    this.fullResolution = false;
    this.width = 1;
    this.height = 1;
    // Set by the studio to the function that writes this frame's
    // matrices. It runs HERE rather than in renderView because the
    // sun's shadow map and its matrix are made by the RenderPass, one
    // pass earlier: read a frame too soon they are the previous
    // frame's, and through a day cycle that is a shaft that lags the
    // shadow it belongs to.
    this.settle = null;
    this._quad = new FullScreenQuad(this.march);
  }

  setSize(width, height) {
    this.width = width;
    this.height = height;
    const scale = this.fullResolution ? 1 : 0.5;
    const wide = Math.max(1, Math.round(width * scale));
    const tall = Math.max(1, Math.round(height * scale));
    this.target.setSize(wide, tall);
    this.full.setSize(width, height);
    this.history.setSize(width, height);
    this.scratch.setSize(width, height);
    this.composite.uniforms.shaftLowResolution.value.set(wide, tall);
    this.composite.uniforms.shaftUpsample.value = this.fullResolution ? 0 : 1;
    this.accumulated = 0;
  }

  draw(renderer_, target, material) {
    renderer_.setRenderTarget(target);
    this._quad.material = material;
    this._quad.render(renderer_);
  }

  render(renderer_, writeBuffer, readBuffer) {
    if (this.settle) this.settle();
    // The depth of the buffer the RenderPass just drew into, which is
    // the one handed here as the read buffer.
    this.march.uniforms.tDepth.value = readBuffer.depthTexture;
    this.composite.uniforms.tDepth.value = readBuffer.depthTexture;
    this.composite.uniforms.tDiffuse.value = readBuffer.texture;
    const march = this.march.uniforms;
    let source = this.target;
    let upsample = 1;
    if (this.fullResolution) {
      // A PLATE: a still's tile or a take's frame, full resolution, the
      // plate's own step count, one pass and no history, so a tile is the
      // piece of the whole plate it stands for and a take is reproducible.
      march.shaftSteps.value = SHAFT_PLATE_STEPS;
      march.shaftSeed.value = 0;
      this.draw(renderer_, this.full, this.march);
      source = this.full;
      upsample = 0;
    } else if (this.still) {
      // THE LIVE VIEW, HELD STILL: another 32 steps a pixel at full
      // resolution, each frame asking the sun about a different place in
      // every segment, added into the running mean -- until eight frames
      // hold 256 samples, after which it marches nothing at all.
      if (this.accumulated < SHAFT_ACCUMULATE) {
        march.shaftSteps.value = SHAFT_STEPS;
        march.shaftSeed.value = (this.accumulated * SHAFT_GOLDEN) % 1;
        this.draw(renderer_, this.full, this.march);
        const mean = this.accumulate.uniforms;
        mean.tHistory.value = this.history.texture;
        mean.tCurrent.value = this.full.texture;
        mean.weight.value = 1 / (this.accumulated + 1);
        this.draw(renderer_, this.scratch, this.accumulate);
        [this.history, this.scratch] = [this.scratch, this.history];
        this.accumulated += 1;
      }
      source = this.history;
      upsample = 0;
    } else {
      // THE LIVE VIEW, MOVING: cheap, at half resolution, and the history
      // starts again the moment it stops.
      march.shaftSteps.value = SHAFT_STEPS;
      march.shaftSeed.value = 0;
      this.draw(renderer_, this.target, this.march);
      this.accumulated = 0;
    }
    this.composite.uniforms.tShafts.value = source.texture;
    this.composite.uniforms.shaftUpsample.value = upsample;
    renderer_.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    this._quad.material = this.composite;
    this._quad.render(renderer_);
  }

  dispose() {
    this.march.dispose();
    this.composite.dispose();
    this.accumulate.dispose();
    this.target.dispose();
    this.full.dispose();
    this.history.dispose();
    this.scratch.dispose();
    this._quad.dispose();
  }
}

// Built only where it can run. On the iPad path there is NO PASS AT
// ALL, rather than a pass held at zero: a raymarch of the shadow map
// per pixel is the one effect a constrained device cannot afford, and
// the dial that would drive it is hidden there too, because a dial that
// moves nothing is worse than no dial.
const shaftsPass = CONSTRAINED_DEVICE ? null : new ShaftsPass(atmosphere.uniforms);
if (shaftsPass) {
  shaftsPass.enabled = false;
  // The matrices the frame is drawn with, written from inside the pass.
  // A pass earlier they are still the previous frame numbers, and through
  // a day cycle that is a shaft lagging the shadow it belongs to.
  shaftsPass.settle = settleShafts;
  composer.addPass(shaftsPass);
}
composer.addPass(new OutputPass());
const gradePass = new ShaderPass(BrightnessContrastShader);
composer.addPass(gradePass);

// The strip and cube fixtures give their light from their faces, through
// RectAreaLight, and three's WebGL renderer reads the LTC tables that
// light is shaded with from UniformsLib as soon as one exists. Without
// them every lit surface goes black the moment a strip is placed. They
// are filled here, once, before anything renders; UniformsLib belongs to
// the module, so the tile preview's second renderer shares them. Checked,
// so a vendor upgrade that moves them is loud rather than a dark studio.
try {
  RectAreaLightUniformsLib.init();
} catch (error) {
  reportProblem("the area-light tables failed to initialise (" + error.message
    + "), so strip and cube fixtures will light nothing; re-vendor "
    + "vendor/addons/lights from three 0.185.0", error);
}
if (!THREE.UniformsLib.LTC_FLOAT_1 || !THREE.UniformsLib.LTC_HALF_1) {
  reportProblem("the area-light tables are missing, so strip and cube "
    + "fixtures will light nothing; re-vendor vendor/addons/lights from "
    + "three 0.185.0");
}

// Every lit material loops over the rect lights, and three unrolls that
// loop: each strip put four more copies of the whole area-light shading
// into every program, and every change in the count recompiles all of
// them. Measured on the 4090, the fifth strip froze the page for ten
// seconds. Rolled back into a plain loop (GLSL ES 3.0 indexes a uniform
// array with a loop counter), the same strip compiles in under two and
// shades the same. Patched on the vendored chunk before any program is
// built, and checked, like the Sky's daylight patch.
const RECT_AREA_UNROLLED = /#pragma unroll_loop_start\s*(for \( int i = 0; i < NUM_RECT_AREA_LIGHTS; i \+\+ \) \{[^}]*\})\s*#pragma unroll_loop_end/;

function rollRectAreaLoop(chunks) {
  const before = chunks.lights_fragment_begin;
  const after = before.replace(RECT_AREA_UNROLLED, "$1");
  if (after === before) {
    reportProblem("the vendored rect-light loop no longer has the shape the "
      + "roll patch expects, so every strip or cube placed will stall the "
      + "page while it recompiles; check lights_fragment_begin in three 0.185.0");
    return false;
  }
  chunks.lights_fragment_begin = after;
  return true;
}
rollRectAreaLoop(THREE.ShaderChunk);

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

// The prop gumball's handle group. It lives up here, a long way from the
// gumball section that builds it, for one reason: renderView sizes it on
// every frame, and a `let` declared down there would sit in its temporal
// dead zone if a render ever happened during boot.
let propGumball = null;
// The instanced props' batches, declared up here for the same reason:
// renderView settles them every frame (see "the instanced props").
const propBatches = new Map();

function renderView() {
  clampCameraAboveFloor();
  // Every render path goes through here, the recorder's included, so the
  // gumball's screen-constant size is settled in one place.
  sizePropGumball();
  // So are the instanced props, and BEFORE the shadow fit, which measures
  // the batches: a stroke's new casters have to be in them when it looks.
  settlePropInstances();
  // And so is the shadow fit, for the same reason and one more: a scatter
  // places hundreds of casters in a burst, and re-measuring the scene per
  // prop would be quadratic. Marking it dirty and settling it once a
  // frame costs one traverse whatever happens.
  if (shadowFitPending) fitSunShadow();
  if (spotFitPending) fitSpotShadows();
  // One projection of one point: the badge rides its prop as the camera
  // moves, rather than sitting where the prop used to be on screen.
  placeHoverBadge();
  settleAtmosphereFloor();
  armShafts();
  composer.render();
}

// How far out the sun stands. applySunAt places it on a sphere of this
// radius, so it is also what the shadow slab's near and far are measured
// from.
const SUN_DISTANCE = 60;

const sun = new THREE.DirectionalLight(0xffffff, 3.0);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
// A starting box, immediately replaced by fitSunShadow once anything is
// in the scene. It used to be the WHOLE policy: a fixed 60 m square,
// written here and never touched again, which is 29 mm texels on a 2048
// map. Every vault measured is 22.8 m wide, so two thirds of the map was
// spent on empty ground, and on a 200 mm voussoir that is the difference
// between a bed joint casting a readable line and a stepped one. It also
// silently lost the shadow of anything scattered beyond 30 m.
sun.shadow.camera.left = -30; sun.shadow.camera.right = 30;
sun.shadow.camera.top = 30; sun.shadow.camera.bottom = -30;
scene.add(sun);

// Set whenever the set of shadow casters changes; settled in renderView.
let shadowFitPending = true;
const shadowBox = new THREE.Box3();
const shadowSphere = new THREE.Sphere();

function noteCastersChanged() { shadowFitPending = true; noteReflectionsChanged(); }

// The parts that wear the capture: the permanent works, which are the
// anchor and the tension tie, and the principal bars, which wear the same
// polished dark steel.
function reflectionWearers() {
  const worn = [];
  if (machineObjects) {
    machineObjects.permanent.traverse((object) => { if (object.isMesh) worn.push(object); });
  }
  if (state.objects.principal) worn.push(state.objects.principal);
  return worn;
}

function captureReflections() {
  reflectionDirtyAt = 0;
  const wearers = reflectionWearers();
  if (!wearers.length) return;
  const box = new THREE.Box3();
  for (const mesh of wearers) box.expandByObject(mesh);
  if (box.isEmpty()) return;
  // NOT IN ITS OWN PHOTOGRAPH: a part that could see itself would carry a
  // black hole where the camera stood inside it.
  const shown = wearers.map((mesh) => mesh.visible);
  for (const mesh of wearers) mesh.visible = false;
  reflectionCamera.position.set((box.min.x + box.max.x) / 2,
    (box.min.y + box.max.y) / 2, box.min.z + REFLECTION_EYE);
  reflectionCamera.update(renderer, scene);
  wearers.forEach((mesh, i) => { mesh.visible = shown[i]; });
  for (const mesh of wearers) wearReflection(mesh.material);
  reflectionsTaken += 1;
}

// Handed only to what is metal: a capture on a matte material would change
// nothing but its shader.
function wearReflection(material) {
  for (const one of Array.isArray(material) ? material : [material]) {
    if (!one || !one.isMeshStandardMaterial || one.metalness < 0.5) continue;
    if (one.envMap === reflectionTarget.texture) continue;
    one.envMap = reflectionTarget.texture;
    one.needsUpdate = true;
  }
}

// A bounding SPHERE, not a box, because the shadow camera looks down the
// sun's own axis: a box measured in world axes would need re-measuring
// every time the sun moved, and a sphere is the same size seen from
// anywhere. That is what makes this a caster fit rather than a sun fit,
// and why the day cycle does not have to trigger it.
function fitSunShadow() {
  shadowFitPending = false;
  shadowBox.makeEmpty();
  scene.traverse((object) => {
    if (object.isMesh && object.castShadow) shadowBox.expandByObject(object);
  });
  if (shadowBox.isEmpty()) return;
  shadowBox.getBoundingSphere(shadowSphere);
  // The light aims at the origin (sun.target is never moved), so the map
  // has to reach whatever is furthest from THERE, not from the casters'
  // own centre. A vault sitting off-origin would otherwise fall out of
  // its own shadow map.
  const reach = Math.max(1,
    shadowSphere.center.length() + shadowSphere.radius) * 1.02;
  const box = sun.shadow.camera;
  box.left = -reach; box.right = reach;
  box.top = reach; box.bottom = -reach;
  // A tight slab is what gives the depth test its precision, and the sun
  // is always SUN_DISTANCE from the origin whatever the hour.
  box.near = Math.max(0.1, SUN_DISTANCE - reach);
  box.far = SUN_DISTANCE + reach;
  box.updateProjectionMatrix();
}
const hemi = new THREE.HemisphereLight(0xbfd4e6, 0x30271f, 0.5);
scene.add(hemi);

// E2: one physical sky shared by backdrop and lighting. The shader's up
// vector defaults to Y-up; this scene is Z-up.
const sky = new Sky();
sky.scale.setScalar(450);
sky.visible = false;
sky.material.uniforms.up.value.set(0, 0, 1);
sky.material.uniforms.cloudCoverage.value = 0; // the cloud block is hardcoded Y-up; scattering respects up, clouds do not
// The sky is a mesh, so nothing dims it but its own shader: one uniform,
// multiplied in at the end, is the whole of the dial's and the night's
// reach into it. Patched on the vendored source rather than kept as a
// fork, and checked, so a vendor upgrade that moves the line is loud.
{
  const shader = sky.material;
  const before = shader.fragmentShader;
  shader.fragmentShader = before
    .replace("uniform vec3 up;", "uniform vec3 up;\n\t\tuniform float daylight;")
    .replace("gl_FragColor = vec4( texColor, 1.0 );",
      "gl_FragColor = vec4( texColor * daylight, 1.0 );");
  // The atmosphere over the sky, chained after the daylight line: the
  // same height-fog integral the ground takes, at the sky's distance, so a
  // fogged floor meets a fogged sky at the horizon with no seam. Declared
  // through the daylight uniform's own line.
  shader.fragmentShader = shader.fragmentShader
    .replace("uniform float daylight;", "uniform float daylight;\n" + ATMOSPHERE_SKY_GLSL)
    .replace("gl_FragColor = vec4( texColor * daylight, 1.0 );",
      "gl_FragColor = vec4( atmosphereSky( texColor * daylight, direction ), 1.0 );");
  if (shader.fragmentShader === before) {
    reportProblem("the vendored Sky shader no longer has the line the daylight patch expects");
  }
  if (!shader.fragmentShader.includes("atmosphereSky( texColor * daylight, direction )")) {
    reportProblem("the vendored Sky shader no longer takes the atmosphere patch, "
      + "so a fogged floor will meet an unfogged sky at the horizon");
  }
  shader.uniforms.daylight = skyDaylight;
  Object.assign(shader.uniforms, atmosphere.uniforms);
  shader.needsUpdate = true;
}
scene.add(sky);

// Stars, for a sky the clock has taken past dusk. Two thousand points on
// the upper hemisphere, additive, unattenuated, most faint and a few
// bright and warm; they fade in with the night and out with the dial, and
// show in sky mode only: a photograph brings its own sky, and the studio
// backdrop is a wall. Outside the fog, or at two hundred metres they
// would be fogged to nothing on the very night they are for.
function starField() {
  const count = 2000;
  const positions = new Float32Array(count * 3);
  const colours = new Float32Array(count * 3);
  let seed = 7;
  const rnd = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const radius = 200;
  for (let i = 0; i < count; i++) {
    const az = rnd() * Math.PI * 2;
    const el = Math.asin(rnd());              // even over the hemisphere
    positions[i * 3] = radius * Math.cos(el) * Math.cos(az);
    positions[i * 3 + 1] = radius * Math.cos(el) * Math.sin(az);
    positions[i * 3 + 2] = radius * Math.sin(el);
    const bright = rnd() ** 3;
    const warm = rnd() < 0.2;
    const v = 0.35 + 0.65 * bright;
    colours[i * 3] = v;
    colours[i * 3 + 1] = v * (warm ? 0.9 : 0.96);
    colours[i * 3 + 2] = v * (warm ? 0.72 : 1);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
  const material = new THREE.PointsMaterial({
    size: 1.8, sizeAttenuation: false, vertexColors: true, transparent: true,
    opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending,
    toneMapped: false, fog: false,
  });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.visible = false;
  points.raycast = () => {};
  return points;
}
const stars = starField();
scene.add(stars);

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
    hemisphere: 0.15, fogColor: 0x10141c, fogNear: 60, fogFar: 250,
    // An hour, not an angle: the picker moves the clock past dusk (see
    // its handler), and the instrument does the rest. The twenty degrees
    // this used to hold was an afternoon under a dark fog.
    elevation: null, night: true,
  },
};

// F1: the shared position math, callable with an unclamped elevation so
// applyDayCycle can render a genuine sub-5-degree dawn (and a captured low
// peak) even though the slider it also writes for display cannot show a
// value under its own min="5" -- see applyDayCycle.
function applySunAt(azimuthDeg, elevationDeg) {
  const az = THREE.MathUtils.degToRad(azimuthDeg);
  const el = THREE.MathUtils.degToRad(elevationDeg);
  const r = SUN_DISTANCE;
  sun.position.set(r * Math.cos(el) * Math.cos(az), r * Math.cos(el) * Math.sin(az), r * Math.sin(el));
  sky.material.uniforms.sunPosition.value.copy(sun.position).normalize();
  noteReflectionsChanged();
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

// timeAtElevation answers in UTC and state.sunMinutes is the site's own
// clock, so the two have to be put in one frame. Without this the day
// cycle in Sydney ran from 19:00 to 08:00 and swept the night.
function localMinutes(when) {
  return localClockMinutes(when, SUN_SITE.longitude);
}

function dayCycleStart() {
  const dawn = timeAtElevation(sunDay(), SUN_SITE.latitude, SUN_SITE.longitude, -6, false);
  return dawn ? localMinutes(dawn) : 5 * 60;
}

function dayCycleEnd() {
  const dusk = timeAtElevation(sunDay(), SUN_SITE.latitude, SUN_SITE.longitude, -6, true);
  return dusk ? localMinutes(dusk) : 21 * 60;
}

function setEnvironmentTexture(texture, target) {
  // The studio texture is permanent; sky and hdri targets are disposable,
  // and leaking one per regeneration is a GPU leak the browser never
  // reports. Dispose the old target before adopting the new one.
  if (environmentTarget) environmentTarget.dispose();
  environmentTarget = target || null;
  scene.environment = texture;
  noteReflectionsChanged();
}

function paintSkyDials() {
  // A dial that does nothing in the current mode is hidden, not shown
  // dead (Param's ruling, 2026-09-11). Projection and Rotation tune an
  // HDRI photograph and nothing else: in Sky mode the sky is a mesh and
  // in Studio the background is a flat colour, so there is nothing for
  // Rotation to turn, and the sun re-aim it drives on release returns at
  // once without a photograph to read an azimuth from. Scale and Height
  // tune only the grounded dome. Brightness acts in every mode, so it
  // stays. Called wherever the mode, the projection or the drawer changes.
  const hdri = state.environmentMode === "hdri";
  const dome = hdri && state.hdriProjection === "projected";
  // The drawer's dials tune the photograph and nothing else now that the
  // settings of the air live in the Scene section, so outside HDRI the
  // block would be an empty strip: it stands aside with them. Read off the
  // drawer's own row, which shows only while the Skies drawer is open.
  const drawerOpen = !document.getElementById("shelf-sky-modes").classList.contains("hidden");
  document.getElementById("shelf-sky-settings").classList.toggle("hidden", !drawerOpen || !hdri);
  document.getElementById("hdri-projection-row").classList.toggle("hidden", !hdri);
  document.getElementById("hdri-rotation-row").classList.toggle("hidden", !hdri);
  document.getElementById("hdri-scale-row").classList.toggle("hidden", !dome);
  document.getElementById("hdri-height-row").classList.toggle("hidden", !dome);
}

function applyEnvironment() {
  // The cheap pass: lights, backdrop ownership, fog, row visibility.
  // PMREM lives in regenerateEnvironment only (E6).
  applySunFromSliders();
  document.getElementById("background-row").classList.toggle("hidden", state.environmentMode !== "studio");
  paintSkyDials();
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
  // ONE fog object, made the first time fog is wanted and kept: Sky mode
  // always has fog (the weather's haze), and the atmosphere brings it to
  // Studio and HDRI too. Only those two, with the atmosphere at None, have
  // none. Assigned before the branches below, whose dial pass paints it.
  if (state.environmentMode === "sky" || atmosphereIsOn(state.atmosphere)) {
    atmosphereFog = atmosphereFog || new THREE.Fog(0xffffff, ATMOSPHERE_LINEAR_OFF, 2 * ATMOSPHERE_LINEAR_OFF);
    scene.fog = atmosphereFog;
  } else {
    scene.fog = null;
  }
  applyAtmosphere();
  if (state.environmentMode === "sky") {
    const preset = WEATHER[state.weatherPreset];
    const uniforms = sky.material.uniforms;
    uniforms.turbidity.value = preset.turbidity;
    uniforms.rayleigh.value = preset.rayleigh;
    uniforms.mieCoefficient.value = preset.mieCoefficient;
    uniforms.mieDirectionalG.value = preset.mieDirectionalG;
    sky.visible = true;
    scene.background = null;
    // The weather's own fog colour while the atmosphere is None, exactly
    // as before it existed; the sky's measured horizon once it is chosen.
    lightBase.fog = atmosphereIsOn(state.atmosphere) && skyHorizon
      ? skyHorizon.clone() : new THREE.Color(preset.fogColor);
    lightBase.backdrop = null;
    scene.backgroundRotation.set(0, 0, 0);
    scene.environmentRotation.set(0, 0, 0);
    // F4: a day cycle's captured intensity survives an environment redraw
    // the same way its captured colour already does, below.
    if (state.sunIntensityOverride === null) lightBase.sun = preset.sunIntensity;
    // F3: the colour input must show the truth. A preset write bypasses the
    // input's own "input" handler (the only other place that sets
    // sun.color), so it has to sync #sun-colour itself or the swatch keeps
    // showing whatever an earlier override or preset left behind.
    if (state.sunColourOverride === null) {
      sun.color.set(preset.sunColor);
      document.getElementById("sun-colour").value = "#" + sun.color.getHexString();
    }
    sun.shadow.radius = preset.shadowRadius;
    lightBase.hemi = preset.hemisphere;
    state.exposureBase = preset.exposure;
    setEnvironmentIntensity(0.6);
  } else if (state.environmentMode === "hdri") {
    sky.visible = false;
    // The photograph's own horizon, or a pale grey until one has loaded.
    lightBase.fog = hdriHorizon ? hdriHorizon.clone() : new THREE.Color(0xa7adb3);
    lightBase.backdrop = null;
    applyHdriBackdrop();
    lightBase.hemi = 0.25;
    state.exposureBase = 0.7;
    setEnvironmentIntensity(1.0);
  } else {
    sky.visible = false;
    const tone = +document.getElementById("background-tone").value / 100;
    scene.background = new THREE.Color().setHSL(0.6, 0.08, 0.06 + 0.5 * tone);
    lightBase.backdrop = scene.background.clone();
    // The studio's fog fades into the studio's wall.
    lightBase.fog = lightBase.backdrop.clone();
    scene.backgroundRotation.set(0, 0, 0);
    scene.environmentRotation.set(0, 0, 0);
    if (state.sunIntensityOverride === null) lightBase.sun = 3.0;
    if (state.sunColourOverride === null) {
      sun.color.set(0xffffff);
      document.getElementById("sun-colour").value = "#" + sun.color.getHexString();
    }
    sun.shadow.radius = 1;
    lightBase.hemi = 0.5;
    // Light concretes were clipping to white under the room environment plus
    // filmic tone mapping, which made three different presets look identical.
    state.exposureBase = 0.85;
    setEnvironmentIntensity(0.6);
  }
  applyGrade();
  // The environment's presets write the sun's colour and intensity as a
  // last resort, from a time when nothing else knew what colour a sun
  // should be. Something does now, and it is the instrument: whichever
  // preset has just been applied, the derived sun goes back on top of it,
  // or a mode change would silently flatten an evening back to white noon.
  if (sunInstrumentReady) applySunFromTime();
}

// The fog's colour follows the Sky every time the sun moves, not only at
// the environment capture. The day cycle and the recorder move the sun
// every frame but capture every 30, and a fog colour measured only at the
// capture held for 30 frames and then jumped, as much as 55 grey levels
// in one frame at dawn: a strobe about once a second in an animation.
// Measured like regenerateEnvironment measures it (the bare sky, no dial,
// no night, no fog), and only while an atmosphere is chosen in Sky mode,
// which is the only time the fog is made of the Sky's horizon.
let horizonHolder = null;
function followSkyHorizon() {
  if (state.environmentMode !== "sky" || !atmosphereIsOn(state.atmosphere)) return;
  horizonHolder = horizonHolder || new THREE.Scene();
  horizonHolder.add(sky); // borrows the mesh, as regenerateEnvironment does
  const shown = skyDaylight.value;
  skyDaylight.value = 1;
  const measured = readSkyHorizon(horizonHolder);
  skyDaylight.value = shown;
  scene.add(sky);
  if (measured) skyHorizon = measured;
  if (skyHorizon) lightBase.fog = skyHorizon.clone();
}

function regenerateEnvironment() {
  // The one PMREM site (E6): mode entry, weather change, sun slider
  // release in sky mode, and HDRI load all land here.
  if (state.environmentMode === "sky") {
    const holder = new THREE.Scene();
    holder.add(sky); // borrows the mesh; a mesh lives in one scene at a time
    // Captured with the night in and the dial OUT: the dial reaches the
    // environment through environmentIntensity, and a sky captured
    // already dimmed would be dimmed twice. A night sky lights a night.
    const shown = skyDaylight.value;
    // First the horizon the atmosphere fades to, read off the bare sky:
    // no dial and no night (the daylight chain applies both to the fog),
    // and no fog over it, since this is the colour the fog is made of.
    skyDaylight.value = 1;
    const measured = readSkyHorizon(holder);
    if (measured) skyHorizon = measured;
    if (skyHorizon && atmosphereIsOn(state.atmosphere)) lightBase.fog = skyHorizon.clone();
    skyDaylight.value = 0.03 + 0.97 * daylightNow();
    // The capture sees the atmosphere over the sky as the eye does, but
    // like the sky itself without the dial.
    const keptAtmosphere = holdAtmosphereForCapture();
    const target = pmrem.fromScene(holder, 0.04);
    keptAtmosphere();
    skyDaylight.value = shown;
    scene.add(sky);
    applySkyBrightness();
    setEnvironmentTexture(target.texture, target);
  } else if (state.environmentMode === "hdri" && state.hdriTexture) {
    const target = pmrem.fromEquirectangular(state.hdriTexture);
    setEnvironmentTexture(target.texture, target);
  } else {
    setEnvironmentTexture(studioEnvironment, null);
  }
}

// The Sky's horizon, measured: the sky mesh rendered four times into a
// strip a few pixels tall, looking out just above the horizon to the four
// quarters, and averaged. The quarters sit side by side in one target
// (32 by 4 each) and are read back once, because a read stalls the GPU and
// this runs every frame the sun moves (followSkyHorizon). The strip is half
// float and linear (a render target is never tone mapped), which is the
// fog's own space. A pixel is held to a luminance of 4 first, so a sun
// sitting on the horizon tints the answer rather than taking it over. The
// atmosphere is off while it looks, since the fog must not be made from
// itself.
const HORIZON_STRIP = { width: 128, height: 4 };
// The brightest the Sky's fog colour may be, as linear luminance (see the
// end of readSkyHorizon): about a sunlit pale wall's, tuned by eye.
const SKY_FOG_CEILING = 0.75;
let horizonTarget = null;
let horizonCamera = null;

function readSkyHorizon(holder) {
  try {
    const quarterWidth = HORIZON_STRIP.width / 4;
    if (!horizonTarget) {
      horizonTarget = new THREE.WebGLRenderTarget(HORIZON_STRIP.width, HORIZON_STRIP.height,
        { type: THREE.HalfFloatType });
      // Scissored, so each quarter's clear leaves the others standing.
      horizonTarget.scissorTest = true;
      horizonCamera = new THREE.PerspectiveCamera(12, quarterWidth / HORIZON_STRIP.height, 0.1, 1000);
      horizonCamera.up.set(0, 0, 1);
    }
    const density = atmosphere.uniforms.atmoDensity.value.clone();
    atmosphere.uniforms.atmoDensity.value.set(0, 0);
    const kept = renderer.getRenderTarget();
    const pixels = new Uint16Array(HORIZON_STRIP.width * HORIZON_STRIP.height * 4);
    const sum = [0, 0, 0];
    let count = 0;
    horizonCamera.position.set(0, 0, 2);
    for (let quarter = 0; quarter < 4; quarter++) {
      const angle = quarter * Math.PI / 2;
      // Four degrees up: the band the sky's own horizon glow lives in.
      horizonCamera.lookAt(Math.cos(angle), Math.sin(angle), 2 + Math.tan(4 * Math.PI / 180));
      horizonTarget.viewport.set(quarter * quarterWidth, 0, quarterWidth, HORIZON_STRIP.height);
      horizonTarget.scissor.copy(horizonTarget.viewport);
      renderer.setRenderTarget(horizonTarget);
      renderer.render(holder, horizonCamera);
    }
    renderer.readRenderTargetPixels(horizonTarget, 0, 0,
      HORIZON_STRIP.width, HORIZON_STRIP.height, pixels);
    for (let i = 0; i < pixels.length; i += 4) {
      const r = THREE.DataUtils.fromHalfFloat(pixels[i]);
      const g = THREE.DataUtils.fromHalfFloat(pixels[i + 1]);
      const b = THREE.DataUtils.fromHalfFloat(pixels[i + 2]);
      const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const scale = luminance > 4 ? 4 / luminance : 1;
      sum[0] += r * scale; sum[1] += g * scale; sum[2] += b * scale;
      count += 1;
    }
    renderer.setRenderTarget(kept);
    atmosphere.uniforms.atmoDensity.value.copy(density);
    // Nothing read (a device that cannot read a half-float strip answers
    // zeros, not an error) is not a black horizon.
    if (!count || !sum.every(Number.isFinite) || !(sum[0] + sum[1] + sum[2] > 0)) return null;
    const horizon = new THREE.Color(sum[0] / count, sum[1] / count, sum[2] / count);
    // The Sky's radiance and the lit scene's are only loosely commensurate
    // (the sky model's own 0.04 scale against a 3.25 sun): measured, the
    // horizon came back two to three times brighter than a sunlit wall, and
    // a tenth of a veil of it washed the whole vault out. Held to a ceiling
    // with its hue kept; the sky is fogged toward the same colour, so the
    // horizon still meets the ground without a seam.
    const luminance = 0.2126 * horizon.r + 0.7152 * horizon.g + 0.0722 * horizon.b;
    if (luminance > SKY_FOG_CEILING) horizon.multiplyScalar(SKY_FOG_CEILING / luminance);
    return horizon;
  } catch (error) {
    reportProblem("the sky's horizon colour could not be measured (" + error.message
      + "); the atmosphere keeps the weather's own fog colour", error);
    return null;
  }
}

// During the environment capture the atmosphere over the sky wears its
// colours without the dial, exactly as skyDaylight does, or a dimmed day
// would light the scene dimmed twice. Answers the function that puts the
// eye's colours back.
function holdAtmosphereForCapture() {
  const uniforms = atmosphere.uniforms;
  const sky_ = uniforms.atmoSkyColour.value.clone();
  const sun_ = uniforms.atmoSunColour.value.clone();
  const dial = Math.max(1e-3, state.skyBrightness);
  uniforms.atmoSkyColour.value.multiplyScalar(1 / dial);
  uniforms.atmoSunColour.value.multiplyScalar(1 / dial);
  return () => {
    uniforms.atmoSkyColour.value.copy(sky_);
    uniforms.atmoSunColour.value.copy(sun_);
  };
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
  paintSkyDials();
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
    applySkyBrightness();   // the new dome wears the dial at once
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
  // The value above was set without a change event, so the faces that read
  // it are told. The shelf's Skies tile draws from this same select.
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
    // The atmosphere fades toward this photograph's own horizon, measured
    // the way the backdrop shows it (applyEnvironment, below, adopts it).
    const horizon = equirectHorizonColour(image.data, image.width, image.height, 4,
      { exposure: BACKDROP_REINHARD_EXPOSURE });
    hdriHorizon = horizon ? new THREE.Color(horizon[0], horizon[1], horizon[2]) : null;
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
    lightBase.sun = estimate.intensity;
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

// ---------- the floor's per-tile randomising ----------
// The shared uniforms, held once and written in place, so changing the
// seed moves every tap on the next frame with no recompile. Turning the
// effect ON or OFF does recompile, because it is a different shader:
// that is what customProgramCacheKey below is for.
const tilingUniforms = {
  tileSeed: { value: new THREE.Vector2(0, 0) },
  tileLattice: { value: LATTICE_SCALE },
  tileSharpness: { value: BLEND_SHARPNESS },
};

function writeTilingUniforms() {
  tilingUniforms.tileSeed.value.set(state.ground.seed[0], state.ground.seed[1]);
}

let tilingSaidChunks = false;
let tilingSaidBump = false;

// Give one material the lattice. The hook REPLACES the one atmosphere.js
// put on Material.prototype, so it has to do that job too or this floor
// alone would lose its fog uniforms and stand clear in a fogged scene.
function installGroundTiling(material) {
  if (!material || material.userData.tilingInstalled) return;
  material.userData.tilingInstalled = true;
  material.onBeforeCompile = function tiledFloor(shader) {
    // FIRST. atmosphere.js hangs the fog's uniforms on the prototype,
    // and a material with its own hook shadows it (its own comment says
    // so). Without this line the floor would be the one surface in the
    // scene with no height fog on it.
    atmosphere.inject(shader);
    if (!state.ground.breakup) return;
    const rewritten = applyTiling(shader, THREE.ShaderChunk, tilingUniforms);
    if (rewritten < 1 && !tilingSaidChunks) {
      tilingSaidChunks = true;
      reportProblem("the floor's per-tile randomising found none of the "
        + "map chunks it rewrites; three's shader chunks have moved and "
        + "tiling.js needs checking against three 0.185.0");
    }
  };
  // The shader DIFFERS by whether the lattice is in it, so the cache key
  // has to say so. Without this, three hands back the program it built
  // the first time and the toggle does nothing at all.
  material.customProgramCacheKey = () => (state.ground.breakup ? "tiled" : "plain");
  // A floor whose relief is a height map keeps its repeat in the relief:
  // three reads a bump map three times to take its own finite
  // difference, and a difference taken across a lattice edge would draw
  // a ridge along every edge. Said once, rather than quietly looking
  // half-done.
  if (material.bumpMap && !material.normalMap && !tilingSaidBump) {
    tilingSaidBump = true;
    logStudio("this floor's relief is a height map, which the per-tile "
      + "randomising leaves alone: its colour will vary and its bumps "
      + "will still repeat");
  }
}

// Both faces of the toggle, and the rebuild that a change of shader
// needs. The material is cached and shared, so needsUpdate is what makes
// three throw the old program away.
function setGroundBreakup(on) {
  state.ground.breakup = !!on;
  const box = document.getElementById("ground-breakup");
  if (box) box.checked = state.ground.breakup;
  const material = groundLibrarySet ? groundLibrarySet.material
    : (state.objects.ground ? state.objects.ground.material : null);
  if (material) material.needsUpdate = true;
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
  installGroundTiling(material);
  writeTilingUniforms();
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

// ---------- lamps ----------
// Param: "some light props... when we turn the sky dark and place an orb
// light say inside the pavilion, it will glow. We should then allow more
// settings to customise the warm and cool colour of the light too."
//
// A lamp is a prop like any other -- carried, placed, moved by the
// gumball, layered, saved -- that happens to carry a real light. Two
// numbers describe it, and they are the two an architect actually
// specifies: how much light (lumens, the number on the box) and what
// colour that light is (kelvin, the other number on the box).
// Param, 2026-09-12: "also can we make them brighter." 1600 lm was both
// the default AND most of the way to the dial's old 6000 ceiling, so a
// fixture asked to light a dark pavilion had a reading light's output and
// nowhere to go. The dial runs to 20000 lm now and a new fixture arrives
// at 4000.
const LAMP_LUMENS = 4000;            // a small floodlight, in the units lamps are sold in
const LAMP_KELVIN = 3000;            // warm white
const LAMP_TINT = "#ffffff";         // no gel at all: the warmth alone
const KELVIN_MIN = 1800, KELVIN_MAX = 6500;
// The spot's own four, and the range its aperture runs over. The
// aperture is the WHOLE cone in degrees, which is how a spot is
// specified on its own box; three wants the half angle in radians, and
// layFixtureBeam is the one place that conversion happens.
const SPOT_APERTURE = 45;            // degrees, the whole cone
const SPOT_SOFTNESS = 0.35;          // 0 a hard edge, 1 all penumbra
const SPOT_REACH = 0;                // metres; 0 is as far as it carries
const SPOT_SHADOW = true;            // a spot with no shadow reads as a glow
const APERTURE_MIN = 5, APERTURE_MAX = 150;

// Colour temperature to RGB, the Tanner Helland approximation, which is
// accurate enough over 1000-40000 K for anything anyone will look at.
// The point of it is that "warm" and "cool" stop being two swatches and
// become a dial with candlelight at one end and overcast noon at the
// other.
function kelvinColour(kelvin) {
  const t = Math.min(40000, Math.max(1000, kelvin)) / 100;
  let r, g, b;
  if (t <= 66) {
    r = 255;
    g = 99.4708025861 * Math.log(t) - 161.1195681661;
  } else {
    r = 329.698727446 * Math.pow(t - 60, -0.1332047592);
    g = 288.1221695283 * Math.pow(t - 60, -0.0755148492);
  }
  if (t >= 66) b = 255;
  else if (t <= 19) b = 0;
  else b = 138.5177312231 * Math.log(t - 10) - 305.0447927307;
  const clamp = (v) => Math.min(1, Math.max(0, v / 255));
  // Through SRGBColorSpace, because those coefficients are gamma-encoded
  // bytes: read as linear they come out washed and far too pale.
  return new THREE.Color().setRGB(clamp(r), clamp(g), clamp(b),
    THREE.SRGBColorSpace);
}

// A fixture's own colour: its warmth, through its own gel.
// Param, 2026-09-12: "we need to make all the lights have individual
// controls and colours etc, more that any light we put in needs its own
// controls."
//
// Warmth and tint are two different controls and both are his. Kelvin
// puts the fixture somewhere on the one line from candlelight to overcast
// noon, which is where a real lamp lives; the tint is a gel held over it,
// which is where a theatre lamp lives. White is no gel at all, so a
// fixture that has never been tinted comes out exactly as it did before
// the control existed.
const tintScratch = new THREE.Color();

function fixtureColour(record) {
  const kelvin = Math.min(KELVIN_MAX, Math.max(KELVIN_MIN,
    +record.kelvin || LAMP_KELVIN));
  const colour = kelvinColour(kelvin);   // a fresh Color, safe to multiply
  const tint = typeof record.tint === "string" ? record.tint : LAMP_TINT;
  if (tint === LAMP_TINT) return colour;
  // Through SRGBColorSpace for the same reason kelvinColour is: a swatch
  // hands back a gamma-encoded hex, and read as linear a mid tint comes
  // out far darker than the square he picked.
  tintScratch.setStyle(tint, THREE.SRGBColorSpace);
  return colour.multiply(tintScratch);
}

// The three fixtures. Param: "i didnt want the orb light with a lamp end.
// i wanted a sphere light only, lamp strip where we can resize it, cube
// lamp ... resize all of these actually."
//
// So: no stem, no foot, no furniture. Each one is EMITTER PLUS LIGHT and
// nothing else, and each is sized by the record's own size vector, which
// is what makes a strip a strip rather than a sphere stretched by eye.
//
// How a fixture gives its light: from its shape. Param: "the light itself
// when we scale it and chnage the shape etc it doesnt make that objects
// light project from the shape just from a point."
//
// The sphere keeps one PointLight at its centre, and there it is not a
// stand-in: a sphere that emits evenly from its surface lights anything
// outside it exactly as a point of the same output at its centre does.
// The strip and the cube emit from their FACES: one RectAreaLight on each
// face that gives light, sized to that face and aimed straight out of it,
// each carrying its share of the output by area. So a twelve metre strip
// lights a twelve metre stripe of floor, not a round pool at its middle.
// The strip's two end caps are left out: at sixty millimetres square they
// carry almost nothing, and two more lights per strip is cost for no
// picture. fixtureFaces (fields.js) does the geometry, tested under node.
//
// What a rect light gives up: it lights only Standard and Physical
// materials (every lit surface here is one), and it casts no shadow (no
// fixture ever did; the sun is what the shadow study is for). Its tables
// are initialised at boot, beside the composer.
//
// The Glow dial, a camera-facing halo sprite on every fixture, was removed
// on 2026-09-11 (Param: "glow doesnt work well id rather remove it"). A
// fixture now reads as a light by what it lights.
const STRIP_FACES = ["+y", "-y", "+z", "-z"];
const BOX_FACES = ["+x", "-x", "+y", "-y", "+z", "-z"];

function lightEmitter(geometry, lift, faces) {
  const group = new THREE.Group();
  // UNLIT (MeshBasicMaterial): it is the source, so nothing in the scene
  // should be shading it, and applyPropLight pushes its colour above 1 so
  // it reads as brighter than white rather than as a pale ball.
  // Built WARM rather than white. applyPropLight writes the real colour
  // from the fixture's own kelvin the moment one is placed, but a tile's
  // preview never gets that call, so a pure white emitter came out white
  // on the pale tile ground and Param could barely see it. 3000 K is the
  // default it will wear anyway, so the tile now shows what he is about
  // to place rather than a blank.
  const globe = new THREE.Mesh(geometry,
    new THREE.MeshBasicMaterial({ color: kelvinColour(LAMP_KELVIN),
      toneMapped: false }));
  globe.position.z = lift;
  globe.userData.lampGlobe = true;
  globe.castShadow = globe.receiveShadow = false;
  geometry.computeBoundingBox();
  group.add(globe);
  if (!faces) {
    // decay 2 is the inverse square, which is what makes a lamp read as a
    // lamp: bright at the wall it is near and gone across the room.
    const light = new THREE.PointLight(0xffffff, 1, 0, 2);
    light.position.z = lift;
    light.userData.lampLight = true;
    // A point light's shadow is six renders of the whole scene, every
    // frame. Deliberately off: the lights are for mood, and the sun is
    // what the shadow study is for.
    light.castShadow = false;
    group.add(light);
  } else {
    for (const face of faces) {
      const light = new THREE.RectAreaLight(0xffffff, 1, 1, 1);
      light.userData.lampLight = true;
      light.userData.lampFace = face;
      light.castShadow = false;
      group.add(light);
    }
  }
  // Laid out and lit at the defaults now, so a tile's preview, which never
  // gets a record, carries emitters that match the shape it shows.
  layFixtureEmitters(group, LAMP_LUMENS, kelvinColour(LAMP_KELVIN));
  return group;
}

// Every emitter a fixture carries, laid to its shape as it stands now and
// given its colour and its share of the output. A rect light needs its
// WORLD size written on it: three shades one from its rotation alone, so
// the group's scale moves where it sits but never how big it is. Width
// and height go on before power, because three turns power into intensity
// by dividing by the area. propsGroup is never scaled, so the group's own
// scale is its size in the world.
const faceAxes = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
const faceBasis = new THREE.Matrix4();

function layFixtureEmitters(object, lumens, colour) {
  const globe = object.children.find((child) => child.userData.lampGlobe);
  if (!globe) return;
  if (!globe.geometry.boundingBox) globe.geometry.computeBoundingBox();
  const box = globe.geometry.boundingBox;
  const half = [(box.max.x - box.min.x) / 2, (box.max.y - box.min.y) / 2,
    (box.max.z - box.min.z) / 2];
  const lights = object.children.filter(
    (child) => child.isLight && child.userData.lampLight);
  const laid = fixtureFaces(half, globe.position.toArray(), object.scale.toArray(),
    lights.filter((light) => light.isRectAreaLight)
      .map((light) => light.userData.lampFace));
  let next = 0;
  for (const light of lights) {
    light.color.copy(colour);
    if (!light.isRectAreaLight) {
      // three.js takes lumens directly and does the 4*pi itself.
      light.power = lumens;
      continue;
    }
    const face = laid[next++];
    light.position.fromArray(face.position);
    for (let k = 0; k < 3; k++) faceAxes[k].fromArray(face.axes[k]);
    faceBasis.makeBasis(faceAxes[0], faceAxes[1], faceAxes[2]);
    light.quaternion.setFromRotationMatrix(faceBasis);
    light.width = face.width;
    light.height = face.height;
    light.power = lumens * face.share;
  }
}

// The one writer of a placed fixture's light. applyPropLight calls it for
// colour and output, and applyPropSize for every change of shape: the
// Size and Length dials, the gumball, the + and - keys, undo and every
// restore. No path can leave the light the size the fixture used to be.
function syncFixtureEmission(record) {
  if (!isLamp(record) || !record.object) return;
  const lumens = Math.max(0, +record.lumens || 0);
  layFixtureEmitters(record.object, lumens, fixtureColour(record));
  layFixtureBeam(record);
}

// The spot's beam, written from the record's own four. Here rather than
// beside them because a resize is also a change of beam: the housing
// grows and the cone has to still come out of its mouth.
function layFixtureBeam(record) {
  const spot = record.object.children.find((child) => child.isSpotLight);
  if (!spot) return;
  const aperture = Math.min(APERTURE_MAX, Math.max(APERTURE_MIN,
    +record.aperture || SPOT_APERTURE));
  // three.js takes the HALF angle in radians; the dial is the whole
  // cone in degrees, which is the number printed on a spot's box.
  spot.angle = (aperture * Math.PI / 180) / 2;
  spot.penumbra = record.softness === undefined
    ? SPOT_SOFTNESS : Math.min(1, Math.max(0, +record.softness || 0));
  // Zero is three's own word for no limit, and the dial says so.
  spot.distance = Math.max(0, +record.reach || 0);
  // The Shadow tick is a WISH, not the answer. Whether this spot gets a
  // shadow map can only be settled over the whole scene, because it is
  // the scene as a whole that runs out of texture units -- see
  // fitSpotShadows, which runs once a frame and decides for all of them.
  noteSpotShadowsChanged();
}

// ---------- the spots' shadow budget ----------
// Param, 2026-09-12: "right now theres a huge glitch with the spot
// light", with a photograph of a scene that was nothing but sky. The
// cause was not the spot: it was seventeen of them, each asking for a
// shadow map, each costing one fragment texture unit. Past the card's
// limit every physical material fails to link, and a material that
// will not link draws BLACK -- which is why the fog went with it.
//
// Measured on this machine: nine shadow-casting spots link, the tenth
// does not, with or without a four-map floor. The reserve below is what
// the material's own maps, the sun's shadow and the area-light tables
// need out of the same sixteen; the spots share the rest. Read from the
// renderer rather than hard-coded, so a card with thirty-two units is
// allowed more -- up to a ceiling, because past a handful of shadowed
// spots the cost is real and the picture barely changes.
const SPOT_SHADOW_RESERVE = 10;
const SPOT_SHADOW_CEILING = 8;

function spotShadowBudget() {
  const units = (renderer && renderer.capabilities
    && renderer.capabilities.maxTextures) || 16;
  return Math.max(1, Math.min(SPOT_SHADOW_CEILING, units - SPOT_SHADOW_RESERVE));
}

let spotFitPending = true;
let spotShadowRefused = 0;

function noteSpotShadowsChanged() { spotFitPending = true; }

// Grant the shadow to as many spots as the budget allows and take it
// from the rest, once a frame, over the scene as a whole. A spot on a
// hidden layer is not drawn at all, so it neither gets a shadow nor
// spends a slot on one -- which is what makes hiding a layer give the
// shadows back to the layer he is working on.
function fitSpotShadows() {
  spotFitPending = false;
  const budget = spotShadowBudget();
  const beams = [];
  const wishes = [];
  for (const record of state.props) {
    if (!isSpot(record) || !record.object) continue;
    const beam = record.object.children.find((child) => child.isSpotLight);
    if (!beam) continue;
    beams.push(beam);
    const wanted = record.shadow === undefined ? SPOT_SHADOW
      : record.shadow !== false;
    wishes.push(wanted && record.object.visible !== false);
  }
  const grants = spotShadowGrants(wishes, budget);
  let granted = 0;
  let wanted = 0;
  grants.forEach((allow, i) => {
    beams[i].castShadow = allow;
    if (allow) granted += 1;
    if (wishes[i]) wanted += 1;
  });
  // Said once per change of the shortfall, never once a frame: a spot
  // that is lit but casts nothing is a decision he should be told
  // about, and a decision repeated sixty times a second is noise.
  const refused = wanted - granted;
  if (refused !== spotShadowRefused) {
    spotShadowRefused = refused;
    if (refused > 0) {
      logStudio(refused + (refused === 1 ? " spot is" : " spots are")
        + " lit but cast no shadow: this card links " + budget
        + " spot shadows at once, and past that every material goes black");
    }
  }
  return { wanted, granted, budget };
}

// A sphere of light, hanging where he puts it. 0.25 m radius, so the
// default reads as a bare bulb rather than a beach ball.
function lightSphere() {
  return lightEmitter(new THREE.SphereGeometry(0.25, 24, 16), 0.25, null);
}

// A strip: two metres by sixty by sixty, the shape of a real linear
// fitting. Long in X, so a rotation about Z aims it the way he wants.
function lightStrip() {
  return lightEmitter(new THREE.BoxGeometry(2.0, 0.06, 0.06), 0.03, STRIP_FACES);
}

// A cube of light, for a light box or a glowing plinth.
function lightCube() {
  return lightEmitter(new THREE.BoxGeometry(0.4, 0.4, 0.4), 0.2, BOX_FACES);
}

// A PANEL: the soft box a photograph wants. A flat slab that gives its
// light out of ONE face, so it lights what it faces and leaves the wall
// behind it alone -- which is the whole difference between a panel and a
// cube of the same size. 1.2 by 0.8 is the size a real softbox is sold
// at. It goes through the same face machinery the strip and the cube
// use, with a list of one, so its rect light is laid, sized and shared
// by the code that is already tested under node.
//
// Which face: -Z, its own underside, the same way the spot points. Both
// are aimed by the gumball's rings, and two fixtures that point the same
// way at rest are one thing to learn rather than two.
function lightPanel() {
  return lightEmitter(new THREE.BoxGeometry(1.2, 0.8, 0.04), 0.02, ["-z"]);
}

// A SPOT, and its aperture. Param: "can we add spot lights too where we
// can vary the aperture etc".
//
// A cone of housing with a lit mouth, and a real THREE.SpotLight down
// its own -Z. The target is a CHILD of the group, so the gumball's
// rotation rings aim the beam: turn the fixture and the pool of light
// turns with it. At rest it points straight down, which is what a spot
// on a track is, and the Z arrow lifts it to where it belongs.
//
// It is the one fixture that casts a shadow by default, and deliberately
// so: a spot with nothing to interrupt it reads as a glow rather than as
// a beam. Every other fixture stays shadowless (the sun is what the
// shadow study is for), and this one's shadow is a single map.
const SPOT_LIFT = 0.14;

function lightSpot() {
  const group = new THREE.Group();
  // The housing: a cone open at the mouth, apex up. ConeGeometry stands
  // on +Y, so it is turned on to +Z once here rather than by a wrapper
  // object whose rotation the emitter layout would then have to undo.
  const shell = new THREE.Mesh(
    new THREE.ConeGeometry(0.16, 0.26, 20, 1, true).rotateX(Math.PI / 2),
    propMaterial(0x2c2f34));
  shell.material.side = THREE.DoubleSide;   // it is seen from inside too
  shell.position.z = SPOT_LIFT;
  // The lit mouth, which is the source: unlit, double sided so it reads
  // from below and from the side, and carrying the globe mark every
  // other fixture's emitter carries, so applyPropLight colours it and
  // layFixtureEmitters can find it.
  const lens = new THREE.Mesh(new THREE.CircleGeometry(0.15, 20),
    new THREE.MeshBasicMaterial({ color: kelvinColour(LAMP_KELVIN),
      toneMapped: false, side: THREE.DoubleSide }));
  lens.position.z = SPOT_LIFT - 0.12;
  lens.userData.lampGlobe = true;
  lens.castShadow = lens.receiveShadow = false;
  lens.geometry.computeBoundingBox();
  const light = new THREE.SpotLight(0xffffff, 1, 0,
    (SPOT_APERTURE * Math.PI / 180) / 2, SPOT_SOFTNESS, 2);
  // SET, not nudged: three gives a new SpotLight the position (0, 1, 0)
  // (Object3D.DEFAULT_UP), so writing z alone leaves it a metre to one
  // side and the beam comes out at forty-five degrees. Caught by the
  // node harness on the day this was written.
  light.position.set(0, 0, SPOT_LIFT - 0.12);
  light.userData.lampLight = true;
  // NOT here. The shadow is granted by fitSpotShadows over the whole
  // scene, before the first frame that could draw it: a restore of a
  // layout holding seventeen spots must never have even one frame in
  // which all seventeen are asking for a map.
  light.castShadow = false;
  light.shadow.mapSize.set(1024, 1024);
  // The near plane clears the housing, which sits behind the light: a
  // shell inside the shadow frustum would draw its own mouth as a black
  // ring on everything below it.
  light.shadow.camera.near = 0.3;
  light.shadow.bias = -0.0015;
  // The target is a child, so the group's rotation carries it and the
  // gumball aims the beam.
  const target = new THREE.Object3D();
  target.position.set(0, 0, -1);
  light.target = target;
  group.add(shell, lens, light, target);
  layFixtureEmitters(group, LAMP_LUMENS, kelvinColour(LAMP_KELVIN));
  return group;
}

// The old fixture, kept ONLY so a scene saved before 2026-09-09 still
// opens: its props name "orb-light", and a type with no builder is drawn
// as nothing at all. It builds the sphere now, without the stem and foot
// he did not want.
function propOrbLight() {
  return lightSphere();
}

const PROP_BUILDERS = {
  figure: propFigure, tree: propTree, pallets: propPallets,
  barrier: propBarrier, cone: propCone, "orb-light": propOrbLight,
  "light-sphere": lightSphere, "light-strip": lightStrip,
  "light-cube": lightCube, "light-spot": lightSpot,
  "light-panel": lightPanel,
};

// The fixtures the Lights tab offers. They are code, not files, so they
// need no folder and no fetch, and they are deliberately NOT in the prop
// library: Param asked for them out of Props and in a tab of their own.
// sizeMetres is the built geometry's own size, which the tab's sliders
// then stretch through record.size.
const LIGHT_KINDS = [
  { key: "light-sphere", label: "Sphere", sizeMetres: [0.5, 0.5, 0.5] },
  { key: "light-strip", label: "Strip", sizeMetres: [2.0, 0.06, 0.06] },
  { key: "light-cube", label: "Cube", sizeMetres: [0.4, 0.4, 0.4] },
  { key: "light-spot", label: "Spot", sizeMetres: [0.32, 0.32, 0.26] },
  { key: "light-panel", label: "Panel", sizeMetres: [1.2, 0.8, 0.04] },
];

// Which prop types are lamps. A set rather than a name test, so a second
// lamp (a downlight, a strip) is one builder and one entry here.
// "orb-light" stays for one reason only: a scene saved before
// 2026-09-09 names it, and a type nothing recognises is drawn as
// nothing. It builds the sphere now, without the stem and foot.
const LAMP_TYPES = new Set(["orb-light", "light-sphere", "light-strip",
  "light-cube", "light-spot", "light-panel"]);

// The spot is the only fixture with a beam, so it is the only one the
// aperture, softness, reach and shadow controls reach. A name test
// rather than a set, because there is one of it and a set of one reads
// as though a second were coming.
function isSpot(record) {
  return !!record && record.type === "light-spot";
}

function isLamp(record) {
  return !!record && LAMP_TYPES.has(record.type);
}

// A prop's size on each axis, uniform unless it carries a size vector.
// Param wanted every fixture resizable, and a strip is only a strip while
// its length can move without its thickness following.
function applyPropSize(record) {
  if (!record || !record.object) return;
  const scale = record.scale || 1;
  const size = record.size;
  if (Array.isArray(size) && size.length === 3) {
    record.object.scale.set(scale * (+size[0] || 1), scale * (+size[1] || 1),
      scale * (+size[2] || 1));
  } else {
    record.object.scale.setScalar(scale);
  }
  // A fixture's light follows its shape; any other prop returns at once.
  syncFixtureEmission(record);
}

// A lamp's two numbers, written on to the objects that answer for them.
// Called on placement, on restore, and whenever the sliders move.
function applyPropLight(record) {
  if (!isLamp(record)) return;
  const lumens = Math.max(0, +record.lumens || 0);
  const colour = fixtureColour(record);
  record.object.traverse((child) => {
    if (child.isMesh && child.userData.lampGlobe) {
      // Pushed above 1 so the source reads as brighter than white rather
      // than as a pale ball, and brighter with the fixture's output. Off
      // entirely reads as a globe that is simply off.
      //
      // The curve saturated at 3000 lm while the dial stopped at 6000, so
      // the top half of the dial moved the room and never the globe: a
      // fixture at its brightest read exactly like one at half. It spans
      // the new range instead, and 4000 lm (the new default) lands within
      // a hair of where 1600 lm used to, so nothing already placed
      // changes character.
      const punch = lumens > 0 ? 1.2 + 2.8 * Math.min(1, lumens / 12000) : 0.25;
      child.material.color.copy(colour).multiplyScalar(punch);
    }
  });
  // And the light itself, from every face that gives it.
  syncFixtureEmission(record);
  // Body shown or not. Here rather than in its own pass because every
  // write to a fixture already comes through this function: a dial, a
  // placement, a restore, a scene.
  applyFixtureBody(record);
}

// SHOWN OR NOT, with the light unchanged either way.
// Param, 2026-09-12: "Can you also add an invisible button to the menu
// so the light shape itself doesnt show but its glow is there. If i then
// want to click it again to edit the menu and turn off the invisible
// function, i can still click the object where it is or use the layer
// tile to select the object."
//
// The MATERIAL is hidden, never the object. Object3D.visible = false
// would take the fixture out of the raycast along with the picture, and
// a fixture that can never be clicked again is a fixture he has lost --
// which is the one thing he asked for by name. three's Raycaster tests
// neither object.visible nor material.visible (it calls raycast on
// every child and Mesh.raycast gives up only on a missing material), so
// a hidden material is skipped by the renderer and still picked by
// propRecordAt. The gumball, the outline, the layer tiles and the whole
// record are untouched.
//
// The shadow pass needs no separate handling: WebGLShadowMap renders a
// mesh only `else if (material.visible)`, so the body's shadow goes with
// the body rather than hanging in the air. Verified live rather than
// read: see the probe note in the Invisible test.
//
// The emitters are lights, not meshes, so nothing here touches them:
// same lumens, same colour, same pool on the floor.
function applyFixtureBody(record) {
  if (!isLamp(record) || !record.object) return;
  const shown = !record.invisible;
  record.object.traverse((child) => {
    if (child.isMesh) child.material.visible = shown;
  });
}

// A restore hands back both numbers. An entry saved before lamps existed
// has neither, and falls back to the current defaults rather than to
// darkness -- a lamp that restores unlit looks broken, not remembered.
function adoptLampSettings(record, entry) {
  if (!isLamp(record)) return;
  record.lumens = typeof entry.lumens === "number" ? entry.lumens
    : state.lampLumens;
  record.kelvin = typeof entry.kelvin === "number" ? entry.kelvin
    : state.lampKelvin;
  // A fixture saved before the tint existed has none, and white is the
  // right answer for it: white is no gel, which is what it was wearing.
  record.tint = typeof entry.tint === "string" ? entry.tint : state.lampTint;
  record.invisible = typeof entry.invisible === "boolean" ? entry.invisible
    : !!state.lampInvisible;
  // The spot's four, each falling back to the drawer's own default
  // rather than to zero: a spot restored with a nought aperture is a
  // spot that has gone out.
  if (isSpot(record)) {
    record.aperture = typeof entry.aperture === "number" ? entry.aperture
      : state.spot.aperture;
    record.softness = typeof entry.softness === "number" ? entry.softness
      : state.spot.softness;
    record.reach = typeof entry.reach === "number" ? entry.reach
      : state.spot.reach;
    record.shadow = typeof entry.shadow === "boolean" ? entry.shadow
      : state.spot.shadow;
  }
  applyPropLight(record);
}


function makeProp(type) {
  const group = PROP_BUILDERS[type]();
  group.traverse((child) => {
    // A lamp's globe is the one mesh that must not: it is a source, and
    // a source casting a hard sun shadow of itself reads as a ball of
    // plastic rather than as a light.
    if (child.isMesh && !child.userData.lampGlobe) {
      child.castShadow = true; child.receiveShadow = true;
    }
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
  // A hidden prop leaves its cluster's buffer, so the grouping is stale.
  notePropsMoved();
  // A hidden spot is not drawn and so spends no shadow slot: hiding a
  // layer gives its shadows back to the layer being worked on.
  noteSpotShadowsChanged();
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

// Where the next placement goes: the OPEN layer, whatever is being placed
// (Param: "in layers the scatters i do should land in the layer thats
// active not create a new one, same with lights etc"). With no open layer
// it falls back to the first, and only with no layer at all is one made;
// the caller owns that one, and its undo takes it away again. Placing
// never changes which layer is open: only the tab strip, + and Group do.
function resolvePlacementLayer() {
  let layer = layerById(state.activeLayer);
  if (!layer && state.propLayers.length) layer = state.propLayers[0];
  let minted = null;
  if (!layer) layer = minted = newLayer(null);
  state.activeLayer = layer.id;
  return { layer, minted };
}

// The same layer, and shown if it was hidden, for a placement that is
// actually happening. Only a placement reveals: arming a tool asks
// resolvePlacementLayer alone, because a reveal at the arm is a change
// to the scene with no undo entry behind it, and pressing Area and then
// Escape would leave a layer shown that the user had hidden by hand.
function placementLayer() {
  const target = resolvePlacementLayer();
  showLayerForPlacing(target.layer);
  return target;
}

// A placement onto a hidden layer would plant props nobody can see, which
// reads as a scatter or a fixture that failed. The layer is shown instead,
// and the log says so.
function showLayerForPlacing(layer) {
  if (!layer || layer.visible !== false) return;
  layer.visible = true;
  applyLayerVisibility();
  saveProps();
  refreshLayersShelf();
  logStudio(layer.name + " was hidden, so it is shown again to take what you "
    + "place; hide it again from the Layers drawer when you are done");
}

// The layer the readouts name: where the next placement will land.
function placingOntoName() {
  const layer = layerById(state.activeLayer) || state.propLayers[0];
  return layer ? layer.name : "a new layer";
}

// The undo half of a minted layer. Only the entry whose action made the
// layer calls this, and it reads state.props NOW, not the entry's own
// records: props grouped or restored onto the layer since keep it alive.
// Never the last layer. Returns where it stood, for the redo.
function dropLayerIfEmpty(layer) {
  if (!layer || state.props.some((record) => record.layer === layer.id)) return -1;
  if (state.propLayers.length <= 1) return -1;
  const index = state.propLayers.indexOf(layer);
  if (index < 0) return -1;
  state.propLayers.splice(index, 1);
  if (!layerById(state.activeLayer)) state.activeLayer = state.propLayers[0].id;
  return index;
}

// The redo half: the SAME layer comes back, same id and same place in the
// strip, so every later entry that names its id still finds it. The id
// counter only ever climbs. An id already taken (a scene applied since)
// is left alone.
function reinstateLayer(layer, index) {
  if (!layer || layerById(layer.id)) return;
  const at = index >= 0 ? Math.min(index, state.propLayers.length) : state.propLayers.length;
  state.propLayers.splice(at, 0, layer);
  state.nextLayerId = Math.max(state.nextLayerId, layer.id + 1);
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

// ---------- the layout, and where it is kept ----------
// A layout written as one object per prop was about two hundred bytes a
// prop, so a 25,375-prop field was five megabytes of JSON, written whole
// to browser storage on every gesture. The store's quota is five: the
// write threw, and because taking each prop of an undone stroke away
// saved the layout again, the throw came out of the undo itself (Param's
// log: "could not undo scattering 1846 props: ... exceeded the quota").
//
// So a prop is nine numbers now, to the millimetre and the ten-thousandth
// of a radian, its type an index into a list written once; the write
// waits until the gestures stop; a layout too big for the browser leaves
// a marker there instead of throwing; and the server keeps a copy beside
// the study that always fits, which is also what a second device opens.
const LAYOUT_STRIDE = 9;
const LAYOUT_SETTLE_MS = 600;
const layoutMemo = new Map();   // propsKey -> the layout last written or pulled this session
const layoutAwaiting = new Set();  // keys restored from nothing, until the server has answered
const layoutOverQuota = new Set(); // keys whose last write left only the marker here
let layoutWrite = null;         // the write waiting for the gestures to stop
let layoutTooBigSaid = false;
let layoutServerSaid = false;
// Bumped when a scene takes the props over: a layout still arriving from
// the server must not put the study's field back over the scene's.
let propsGeneration = 0;

function roundMm(value) { return Math.round((+value || 0) * 1000) / 1000; }
function roundTurn(value) { return Math.round((+value || 0) * 10000) / 10000; }

function encodeProps(props) {
  const types = [];
  const typeIndex = new Map();
  const rows = [];
  const extras = {};
  // Which scatter each row belongs to, as runs of [id, how many], 0 for a
  // prop placed by hand. A scatter's rows mostly sit together, so a field
  // of a million is a short list here rather than a million numbers.
  const scatter = [];
  props.forEach((p, i) => {
    const id = p.scatter || 0;
    if (scatter.length && scatter[scatter.length - 2] === id) scatter[scatter.length - 1] += 1;
    else scatter.push(id, 1);
    let t = typeIndex.get(p.type);
    if (t === undefined) { t = types.length; types.push(p.type); typeIndex.set(p.type, t); }
    rows.push(t, roundMm(p.x), roundMm(p.y), roundMm(p.z || 0), roundTurn(p.rotation),
      roundTurn(p.rotX || 0), roundTurn(p.rotY || 0), roundMm(p.scale || 1), p.layer || 1);
    // Only a fixture carries these, and a fixture always does.
    if (p.size || p.lumens !== undefined || p.kelvin !== undefined
        || p.tint !== undefined || p.invisible !== undefined) {
      extras[i] = { size: p.size, lumens: p.lumens, kelvin: p.kelvin,
        tint: p.tint, invisible: p.invisible,
        // A spot's beam. Undefined on every other fixture, and JSON
        // drops an undefined key, so no other prop pays for these.
        aperture: p.aperture, softness: p.softness, reach: p.reach,
        shadow: p.shadow };
    }
  });
  return { stride: LAYOUT_STRIDE, types, rows, extras, scatter };
}

// A layout written before scatters were named has no runs at all, and its
// plantings are worked out on the way in (adoptLegacyScatters).
function layoutKnowsScatters(block) {
  return !!block && !Array.isArray(block) && Array.isArray(block.scatter);
}

// Both shapes a layout or a scene has ever held: the list of objects
// written until 2026-09-11, and the rows written since.
function decodeProps(block) {
  if (Array.isArray(block)) return block;
  if (!block || !Array.isArray(block.rows) || !Array.isArray(block.types)) return null;
  const stride = +block.stride || LAYOUT_STRIDE;
  const rows = block.rows;
  const extras = block.extras || {};
  const entries = [];
  for (let i = 0; i + stride <= rows.length; i += stride) {
    const entry = { type: block.types[rows[i]], x: rows[i + 1], y: rows[i + 2],
      z: rows[i + 3], rotation: rows[i + 4], rotX: rows[i + 5], rotY: rows[i + 6],
      scale: rows[i + 7], layer: rows[i + 8] };
    const extra = extras[entries.length];
    if (extra) Object.assign(entry, extra);
    entries.push(entry);
  }
  if (Array.isArray(block.scatter)) {
    let at = 0;
    for (let r = 0; r + 1 < block.scatter.length; r += 2) {
      const id = +block.scatter[r] || 0;
      const count = +block.scatter[r + 1] || 0;
      for (let k = 0; k < count && at < entries.length; k += 1, at += 1) {
        if (id) entries[at].scatter = id;
      }
    }
  }
  return entries;
}

// Asked for after every change and done once they stop. WHERE it goes and
// WHAT it holds are taken now, not when it runs: a study switched in the
// meantime must not be handed the last study's props.
function saveProps() {
  if (!state.bundle) return;   // no study, nowhere to key the layout
  if (layoutWrite) clearTimeout(layoutWrite.timer);
  layoutWrite = {
    key: propsKey(),
    export: state.bundle.export,
    props: state.props,
    layers: state.propLayers,
    // The scatter's RULES, not its output. The props it made are already
    // in the list above as ordinary records; what would otherwise be
    // lost on a reload is the species he picked, the spacing he tuned
    // and the seed that produced a field he liked -- and a dice with no
    // seed to go back to is not a dice.
    scatter: state.scatter,
    timer: setTimeout(flushProps, LAYOUT_SETTLE_MS),
  };
}

function flushProps() {
  const pending = layoutWrite;
  if (!pending) return;
  clearTimeout(pending.timer);
  // Restored from nothing, or from the marker, with the server's copy
  // still on its way: held until it has been heard (pullServerLayout lets
  // it go), or an edit made in the meantime would be written over a whole
  // field it never saw.
  if (layoutAwaiting.has(pending.key)) return;
  layoutWrite = null;
  const layout = {
    saved: Date.now(),
    layers: pending.layers.map((layer) => ({
      id: layer.id, name: layer.name, visible: layer.visible })),
    props: encodeProps(pending.props),
    scatter: pending.scatter,
  };
  layoutMemo.set(pending.key, layout);
  const text = JSON.stringify(layout);
  try {
    localStorage.setItem(pending.key, text);
    layoutOverQuota.delete(pending.key);
  } catch (error) {
    // Too big for the browser. A marker stays, so a reload knows to ask
    // the server rather than restore whatever was there before.
    layoutOverQuota.add(pending.key);
    try {
      localStorage.setItem(pending.key, JSON.stringify({ saved: layout.saved, onServer: true }));
    } catch (again) { /* the store is full of something else; the server has it */ }
    if (!layoutTooBigSaid) {
      layoutTooBigSaid = true;
      logStudio("the prop layout is too big for the browser's store; it is kept on the server");
    }
  }
  putLayout(pending.export, text);
}

// One PUT at a time, and only the newest layout of each study. Over the
// tailnet a large layout takes seconds, and two in flight can land in
// either order: the bigger, older one arriving last put back a field the
// user had just undone.
const layoutPutQueue = new Map();   // export -> the newest text not yet sent
let layoutPutting = false;

function putLayout(exportName, text) {
  layoutPutQueue.set(exportName, text);
  if (!layoutPutting) sendLayout();
}

function sendLayout() {
  const next = layoutPutQueue.entries().next();
  if (next.done) { layoutPutting = false; return; }
  const [exportName, text] = next.value;
  layoutPutQueue.delete(exportName);
  layoutPutting = true;
  fetch("/api/studies/" + encodeURIComponent(exportName) + "/layout", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: text,
  }).then((response) => {
    if (!response.ok) throw new Error("the server said " + response.status);
  }).catch((error) => {
    // Once a session: a studio started before this route existed answers
    // every write with a 404, and a line per gesture drowned the log.
    if (!layoutServerSaid) {
      layoutServerSaid = true;
      logStudio("the prop layout did not reach the server: " + error.message);
    }
  }).finally(sendLayout);
}

// The server's copy wins when it is newer: the layout another device
// wrote, or the one the browser was too small to hold. Asked once a study
// is built.
async function pullServerLayout() {
  if (!state.bundle) return;
  const key = propsKey();
  const generation = propsGeneration;
  let remote = null;
  try {
    const response = await fetch("/api/studies/"
      + encodeURIComponent(state.bundle.export) + "/layout");
    if (response.status === 200) remote = await response.json();   // 204: none kept yet
  } catch (error) {
    remote = null;
  }
  const awaiting = layoutAwaiting.delete(key);
  if (!state.bundle || propsKey() !== key) return;
  const heldBack = !!layoutWrite && layoutWrite.key === key;
  // Nothing on the server, or a scene opened in the meantime (a scene is a
  // whole picture and owns the props now): whatever was held back goes.
  if (!remote || propsGeneration !== generation) {
    if (heldBack) flushProps();
    return;
  }
  if (awaiting) {
    // Restored from nothing: the server's field wins over anything drawn
    // in the moments before it arrived, which it has never seen.
    if (heldBack) {
      layoutWrite = null;
      logStudio("the prop layout arrived from the server and replaced what was drawn before it");
    }
  } else {
    // Restored from this browser's own copy: the server's wins only when
    // it is newer, and never over a change in hand.
    if (layoutWrite || brushStroke || state.carrying) return;
    const local = layoutMemo.get(key) || readLocalLayout(key);
    if (local && !local.onServer && (+local.saved || 0) >= (+remote.saved || 0)) return;
  }
  layoutMemo.set(key, remote);
  restoreProps(remote);
}

function readLocalLayout(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null");
  } catch (error) {
    return null;
  }
}

// Mirrors disposeShell's rule: whatever is replaced owns GPU buffers.
function disposeProp(object) {
  // A batched prop owns nothing but its place in the batch: it gives the
  // place back, and the batch is written again on the next frame.
  if (object.instancedIn) { leaveBatch(object); return; }
  // Library props share one template's geometry and materials, so
  // freeing them here would empty the template everything else is still
  // drawing from. The template owns its resources for the session.
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

// The scatter's rules, as they were left. Species are filtered against
// the library that is actually here: a layout written when a prop pack
// was installed must not put a species in the mix that nothing can
// place, or the first brush stroke fails with nothing to say why.
function adoptScatter(saved) {
  if (!saved || typeof saved !== "object") return;
  const known = new Set((state.propLibrary || []).map((entry) => entry.key));
  const species = Array.isArray(saved.species)
    ? saved.species
      .filter((one) => one && known.has(one.type))
      .map((one) => ({ type: one.type,
        weight: Math.max(1, Math.min(9, +one.weight || 1)) }))
    : [];
  const number = (key, low, high) => {
    const value = +saved[key];
    if (!Number.isFinite(value)) return state.scatter[key];
    return Math.max(low, Math.min(high, value));
  };
  state.scatter = {
    species,
    // The dial's own floor. At 0.6 a reload quietly loosened every dense
    // field he had tuned below it, and the next stroke came out sparse.
    spacing: number("spacing", 0.3, 3),
    sizeMin: number("sizeMin", 0.3, 1),
    sizeMax: number("sizeMax", 1, 3),
    clump: number("clump", 0, 100),
    clumpSize: number("clumpSize", 1, 20),
    clearance: number("clearance", 0, 8),
    turn: saved.turn === 0 ? 0 : 360,
    seed: Math.max(1, Math.min(99999, Math.round(+saved.seed) || 1)),
    radius: number("radius", 0.5, 20),
  };
}

function restoreProps(given) {
  // A write still waiting for the gestures to stop would be overtaken by
  // the read below, and the props it held would come back as they were.
  flushProps();
  for (const record of state.props) { disposeProp(record.object); propsGroup.remove(record.object); }
  state.props = [];
  // Through selectProp, never by assignment: the outline and the gumball
  // follow the selection, and a bare null leaves them orbiting a corpse.
  selectProp(null);
  let layout = given || layoutMemo.get(propsKey()) || null;
  if (!layout) {
    let stored = null;
    try {
      stored = localStorage.getItem(propsKey());
      layout = JSON.parse(stored || "[]");
    } catch (error) {
      layout = [];
    }
    // Nothing kept in this browser, or only the marker a too-big layout
    // leaves: the server's copy decides, and until it has been heard
    // nothing may be written over it (flushProps, pullServerLayout).
    if (!stored || (layout && layout.onServer)) layoutAwaiting.add(propsKey());
  }
  // Three shapes on disk: the old bare array of props, the layered
  // {layers, props} that replaced it, and the same with its props as
  // rows (decodeProps). All restore.
  let entries = layout;
  const knowsScatters = !Array.isArray(layout) && !!layout
    && layoutKnowsScatters(layout.props);
  if (!Array.isArray(layout) && layout && layout.props) {
    adoptLayers(layout.layers);
    adoptScatter(layout.scatter);
    entries = decodeProps(layout.props);
  } else {
    adoptLayers(null);
  }
  if (!Array.isArray(entries)) entries = [];
  propsAwaitingLibrary = false;
  // Every model this layout is still waiting for, loaded together and
  // answered with ONE re-run once the last has landed. A re-run per model
  // placed a field of eighteen variants nineteen times over on a cold open.
  const waiting = [];
  for (const entry of entries) {
    if (!knownPropType(entry.type)) {
      // Either the manifest is still in flight, or this prop is gone from
      // it. Either way the entry stays in the saved layout untouched, so a
      // library that arrives late can put it back.
      propsAwaitingLibrary = true;
      // Known to the manifest but not loaded yet: ask for exactly this
      // model. ensure dedupes, and only the call that CREATED a load joins
      // the wait below, so repeated restores cannot multiply into repeated
      // fetches or repeated re-runs.
      if (propLibraryEntry(entry.type) && !propTemplatePromises.has(entry.type)) {
        waiting.push(ensurePropTemplate(entry.type));
      }
      continue;
    }
    const record = placeProp(entry.type, +entry.x || 0, +entry.y || 0,
      +entry.rotation || 0, false, +entry.scale || 1, +entry.z || 0,
      +entry.rotX || 0, +entry.rotY || 0);
    if (Array.isArray(entry.size) && entry.size.length === 3) {
      record.size = entry.size.map(Number);
      applyPropSize(record);
    }
    record.layer = +entry.layer || 1;
    if (entry.scatter) record.scatter = +entry.scatter;
    adoptLampSettings(record, entry);
  }
  settleRestoredScatters(knowsScatters);
  applyLayerVisibility();
  // A failed load resolves null rather than rejecting, so one bad model
  // cannot hold the rest of the field back for ever.
  if (waiting.length) {
    Promise.all(waiting).then(() => { if (propsAwaitingLibrary) restoreProps(); });
  }
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

// The library by key and by family, rebuilt whenever the list itself is
// replaced (loadPropLibrary always assigns a new array, never edits one).
// A scatter dart asks for its variant's entry three times and a stroke
// throws thousands of darts, and a find over 270 entries each time was a
// million comparisons a stamp before a single disc had been tested.
let libraryIndexFor = null;
let libraryByKey = new Map();
let libraryByFamily = new Map();

function libraryIndex() {
  if (libraryIndexFor !== state.propLibrary) {
    libraryIndexFor = state.propLibrary;
    libraryByKey = new Map();
    libraryByFamily = new Map();
    for (const entry of state.propLibrary || []) {
      libraryByKey.set(entry.key, entry);
      const family = entry.family || entry.key;
      if (!libraryByFamily.has(family)) libraryByFamily.set(family, []);
      libraryByFamily.get(family).push(entry);
    }
  }
  return libraryByKey;
}

function propLibraryEntry(key) {
  return libraryIndex().get(key) || null;
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
  // A built-in prop is code, not a file. Letting it fall through would
  // fetch a model that does not exist and log a load failure for a prop
  // that is working perfectly; null is the right answer, and every
  // caller already falls back to PROP_BUILDERS on one.
  if (entry.builtIn) return Promise.resolve(null);
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

// One built object per built-in, kept for the life of the page. The tile
// redraws on every library load and on a theme change, and building a
// fresh group each time would strand its buffers on the GPU.
const builtInPreviews = new Map();

// THE QUIET TONE A PREVIEW'S SOURCE WEARS. Param, looking at the Lights
// drawer: "make the colour less obnoxious". A placed fixture's globe
// wears its own warmth multiplied by its output, which at four thousand
// lumens is a saturated orange; five of those at two hundred pixels
// each read as five orange blobs, and the choice being made in that
// drawer is about SHAPE -- a sphere, a bar, a box, a cone, a slab.
// Warm off-white, so it still reads as a source and not as a stone.
const PREVIEW_GLOBE = 0xd9d3c9;

// A preview is an ICON of the fixture, not a photograph of it lit. The
// copy the drawer draws is its own object with its own materials
// (makeProp builds fresh ones per call), so calming it here cannot
// reach a single placed light.
function builtInPreview(key) {
  if (!builtInPreviews.has(key)) {
    const object = makeProp(key);
    object.traverse((child) => {
      if (child.isMesh && child.userData.lampGlobe && child.material) {
        child.material.color.set(PREVIEW_GLOBE);
      }
    });
    builtInPreviews.set(key, object);
  }
  return builtInPreviews.get(key);
}

// The type select is the source of truth for what a placement places,
// exactly as the material select is behind the material tiles. Every
// entry is offered, built-ins first: whether a library model's file
// loads is only knowable by loading it, which happens when it is chosen.
function listPropTypes() {
  const select = document.getElementById("prop-type");
  if (!select) return;
  select.innerHTML = "";
  for (const entry of state.propLibrary) {
    const option = document.createElement("option");
    option.value = entry.key;
    option.textContent = entry.label || entry.key;
    select.appendChild(option);
  }
  if (select.options.length) select.value = select.options[0].value;
}

// Props that are code rather than files. They need no folder, no fetch
// and no manifest, so they are offered even when the prop library is
// missing entirely -- which is exactly the state a new machine is in.
// Empty since 2026-09-09: the one built-in was the orb light, and the
// lights moved to their own tab on Param's word ("maybe we need to make a
// light tile and put all the lights there and not in props"). Kept as the
// seam it is, because a built-in prop needs no folder and no fetch and is
// exactly what a machine with no library should still be offered.
const BUILT_IN_PROPS = [];

async function loadPropLibrary() {
  // Always on the shelf, whatever the fetch below does.
  state.propLibrary = BUILT_IN_PROPS.slice();
  let payload = null;
  try {
    payload = await fetchJson("/api/props");
  } catch (error) {
    buildPropTiles();                    // no library: the built-ins stand
    listPropTypes();
    return;
  }
  // A distance tier is part of its model, never a prop of its own
  // (tools/props/lod.mjs). The server hides them, but a studio started
  // before it learned to offered all 450 as white, textureless tiles
  // reading "0 triangles", so the page refuses them too.
  const entries = (payload.props || []).filter((entry) => entry && entry.key && entry.file
    && !/\.lod\d\.glb$/i.test(entry.file));
  state.propLibrary = [...BUILT_IN_PROPS, ...entries];
  state.propCredits = payload.library || null;
  buildPropTiles();
  listPropTypes();
  if (!entries.length) return;
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

// ---------- the instanced props ----------
// A placed library prop is ONE INSTANCE of its variant's batch. A field
// of 25,375 grass tufts was 25,375 cloned groups, and the renderer paid a
// draw call for every clone and another for every caster in the shadow
// map: 48,078 calls a frame, one core flat out, the 4090 at 6% and the
// viewport at two frames a second. Batched, the same field is a draw call
// per variant, per mesh in its model, per detail tier.
//
// The RECORD is untouched and is still the truth. record.object is still
// an Object3D whose position, rotation, scale and visible every existing
// writer sets exactly as before: the carry, the gumball, R and plus and
// minus, the stamp, the layer eye, every undo. It is a PROXY. It carries
// no mesh and stands outside the scene graph, so the renderer never walks
// 25,000 of them; once a frame settlePropInstances compares each proxy
// with what it last saw, and only a batch that changed, or a view that
// moved, is written again.
//
// Two small liberties let a proxy answer what a clone used to. Its PARENT
// is propsGroup although propsGroup does not list it, so its world matrix
// carries the floor's drop and nothing renders it. And it wears a
// GEOMETRY holding only its model's bounds, which is all
// Box3.setFromObject reads, so the selection outline, the lift's height
// and the box pick measure it exactly as they measured the clone.

// A tier is drawn while the model's bounding radius covers at least this
// many pixels; below the second, the far tier. Draft stretches each
// threshold, so detail goes sooner, and Full never leaves the first. A
// still and a take always render at Full, whatever the viewport is set
// to: detail traded for speed while composing must never reach a plate.
const PROP_TIER_PIXELS = [48, 14];
// Below this many pixels across, a prop is not drawn at all.
//
// A blade of grass seventy metres off covers 0.95 of a pixel -- measured
// in his own scene -- and half a million of them were being rasterised
// to contribute a shimmer the ground texture already carries. This is
// Unreal's cull distance for foliage, expressed the way the tiers are:
// in how much of the screen one prop actually covers, so it follows the
// lens and the window rather than being a number of metres that is
// wrong at every other focal length.
//
// A probe's handle sits beside it (setCullPixels) so the figure can be
// argued from a measured picture rather than from taste.
let PROP_CULL_PIXELS = 0.75;
function setCullPixels(n) { PROP_CULL_PIXELS = n; }
const DETAIL_REACH = { draft: 2.5, balanced: 1, full: 0 };
const DETAIL_KEY = "vaulted-prop-detail";

function propInstance(type, template) {
  const batch = propBatch(type, template);
  const proxy = new THREE.Object3D();
  proxy.parent = propsGroup;           // for its world matrix only; see above
  proxy.geometry = batch.bounds;       // for Box3.setFromObject only
  proxy.instancedIn = batch;
  proxy.batchIndex = batch.proxies.length;
  batch.proxies.push(proxy);
  batch.dirty = true;
  return proxy;
}

// Given back by disposeProp, which every removal already calls. Swapped
// with the last rather than spliced, so taking a whole stroke away is a
// constant cost per prop and not a pass over the batch for each one.
function leaveBatch(proxy) {
  const batch = proxy.instancedIn;
  if (!batch) return;
  const last = batch.proxies.pop();
  if (last !== proxy) {
    batch.proxies[proxy.batchIndex] = last;
    last.batchIndex = proxy.batchIndex;
  }
  proxy.instancedIn = null;
  batch.dirty = true;
}

function propBatch(type, template) {
  let batch = propBatches.get(type);
  if (batch) return batch;
  template.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(template);
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const bounds = new THREE.BufferGeometry();
  bounds.setAttribute("position", new THREE.Float32BufferAttribute(
    [box.min.x, box.min.y, box.min.z, box.max.x, box.max.y, box.max.z], 3));
  bounds.computeBoundingBox();
  const near = bakeTier(template, null);
  // THE MODEL'S OWN WIND, from how tall it actually stands once scaled.
  const model = windParameters(box.max.z - box.min.z);
  const windModel = {
    windHeight: { value: model.height },
    windBend: { value: model.bend },
    windFrequency: { value: model.frequency },
  };
  for (const part of near.parts) {
    for (const material of [].concat(part.material)) {
      if (!material || material.userData.windModel) continue;
      wearWind(material, windModel);
    }
  }
  // AND ITS SHADOW'S. three draws a mesh's shadow with its
  // customDepthMaterial when it has one, copying each part's map and alpha
  // test onto it per draw, so the leaf cards cut their shadows as they move.
  // The distance material is the point lights' equivalent.
  const shadowOf = (made) => wearWind(made, windModel);
  batch = {
    type, proxies: [], tiers: [near], dirty: true, bounds,
    radius: sphere.radius, centre: sphere.center.clone(),
    casts: near.parts.some((part) => part.castShadow),
    windDepth: shadowOf(new THREE.MeshDepthMaterial()),
    windDistance: shadowOf(new THREE.MeshDistanceMaterial()),
    // How far a tip can travel at full strength, for the cull: a cluster
    // whose sphere did not allow for it would pop out while still leaning
    // into view. Scaled props reach a little further, hence the margin.
    windReach: model.bend * model.height * 1.6,
    // Cut into a spatial grid the first time it is settled, and re-cut
    // whenever the props themselves change. The camera moving never
    // touches this.
    clusters: new Map(), clusterSize: 0, grouped: false,
  };
  propBatches.set(type, batch);
  const entry = propLibraryEntry(type);
  if (entry && Array.isArray(entry.lods)) loadPropLods(batch, entry, template);
  return batch;
}

// Every mesh of a model with its geometry baked into the model's own
// space, so ONE instance matrix places them all, and its material kept as
// it is: the batch draws with the template's own materials, which is also
// why the section plane still cuts a batched field. A far tier borrows
// its materials from the near one, mesh for mesh, because a sidecar
// carries no textures of its own (tools/props/lod.mjs).
function bakeTier(root, borrow) {
  root.updateMatrixWorld(true);
  const parts = [];
  root.traverse((child) => {
    if (!child.isMesh) return;
    const geometry = child.geometry.clone();
    floatAttributes(geometry);
    geometry.applyMatrix4(child.matrixWorld);
    const from = borrow ? borrow[parts.length] : child;
    parts.push({ geometry, material: from.material,
      castShadow: from.castShadow, receiveShadow: from.receiveShadow });
  });
  return { parts, meshes: [], capacity: 0, slots: [], count: 0 };
}

// The fetch QUANTISES: positions arrive as 16-bit integers that the
// node's own scale undoes, which is fine for a clone that keeps the node
// and fatal for a bake, whose applyMatrix4 writes floats back into an
// Int16Array. What the bake transforms is widened to floats first.
function floatAttributes(geometry) {
  for (const name of ["position", "normal", "tangent"]) {
    const attribute = geometry.getAttribute(name);
    if (!attribute) continue;
    if (attribute.array instanceof Float32Array
        && !attribute.isInterleavedBufferAttribute) continue;
    const size = attribute.itemSize;
    const out = new Float32Array(attribute.count * size);
    for (let i = 0; i < attribute.count; i++) {
      out[i * size] = attribute.getX(i);
      if (size > 1) out[i * size + 1] = attribute.getY(i);
      if (size > 2) out[i * size + 2] = attribute.getZ(i);
      if (size > 3) out[i * size + 3] = attribute.getW(i);
    }
    geometry.setAttribute(name, new THREE.BufferAttribute(out, size));
  }
}

// The far tiers arrive after the batch is already drawing: until they
// do, every instance draws near, which is only slower. A sidecar whose
// meshes do not line up with the model's one for one cannot borrow its
// materials, and is not drawn at all rather than drawn wrong.
function loadPropLods(batch, entry, template) {
  const model = template.children[0];
  const near = batch.tiers[0].parts;
  entry.lods.forEach((lod, index) => {
    propLoader.loadAsync("/api/props/" + encodeURIComponent(lod.file)).then((gltf) => {
      const side = gltf.scene;
      side.rotation.copy(model.rotation);
      side.scale.copy(model.scale);
      side.position.copy(model.position);
      const holder = new THREE.Group();
      holder.add(side);
      let meshes = 0;
      side.traverse((child) => { if (child.isMesh) meshes += 1; });
      if (meshes !== near.length) return;
      batch.tiers[index + 1] = bakeTier(holder, near);
      batch.dirty = true;
    }).catch(() => { /* a missing tier is only slower, never wrong */ });
  });
}

// ---------- clustered instancing ----------
// Param, 2026-09-13, with his stats readout: "we are running at 2fps,
// and its extremely slow ... we need to drastically speed this up, to
// retain in 40-60 fps range. how we do that we will have to understand
// the inner working of unreal engine, because clearly they have
// optimised for this."
//
// MEASURED FIRST, and the triangle count was a red herring. The frame
// was not waiting on the GPU at all: settling the instances cost 408 ms
// of JavaScript, of which 212 ms was writing all 930,429 instance
// matrices into their buffers -- every frame, while the camera moved.
// With the camera perfectly still it still cost 160 ms. At 438
// nanoseconds a prop, a million props is two frames a second before the
// GPU is asked for anything.
//
// And nearly all of that work was wasted, because AN INSTANCE MATRIX
// DOES NOT CHANGE WHEN THE CAMERA MOVES. What changes is which LOD tier
// each instance belongs to, and whether it is in view -- and the old
// code expressed that by re-packing every tier's buffer from scratch,
// since a tier is a densely packed list and one instance crossing a
// threshold moves everything after it.
//
// This is the problem Unreal solves with hierarchical instancing, and
// the answer is the same one: stop deciding per instance and start
// deciding per CLUSTER. The instances are grouped once into a spatial
// grid; each cluster's matrices are written once and then left alone;
// and a frame walks the clusters -- hundreds, not a million -- culling
// each and choosing its tier. A cluster whose answer has not changed
// costs nothing whatever.
//
// ONE MESH PER PART PER CLUSTER, and a tier change swaps that mesh's
// GEOMETRY rather than hiding one mesh and showing another. Every tier
// of a batch already shares its materials (bakeTier borrows them), so
// the swap changes no shader, no material and no buffer: it points an
// existing draw at a different, already-resident set of triangles.

// How many clusters a batch is cut into, about. Fewer and a cluster
// spans too much ground for one tier to be right across it; more and
// the draw calls climb, which in WebGL is a real cost paid on the CPU.
// Sixteen puts a scatter of a hundred thousand into clusters of a few
// thousand each, and a scene of forty species into a few hundred draws.
let CLUSTER_TARGET = 8;
// A probe's handle on the grid, so the size can be chosen by
// measurement rather than by taste. Nothing in the studio calls it.
function setClusterTarget(n) { CLUSTER_TARGET = n; }
const CLUSTER_MIN_METRES = 2;

function clusterKey(ix, iy) {
  // Two 21-bit halves in one double, the same trick the keep-out grid
  // uses, so a cluster's key is a number and its map is a fast one.
  return (ix + 1048576) * 2097152 + (iy + 1048576);
}

// Which grid a batch's instances are cut on. Taken from the ground they
// actually cover, so a scatter over a whole site and a handful of props
// in one corner both come out around CLUSTER_TARGET clusters.
function clusterSizeFor(batch) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const proxy of batch.proxies) {
    const p = proxy.position;
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  if (!isFinite(minX)) return CLUSTER_MIN_METRES;
  const span = Math.max(maxX - minX, maxY - minY);
  return Math.max(CLUSTER_MIN_METRES, span / Math.sqrt(CLUSTER_TARGET));
}

function newCluster(key) {
  return { key, proxies: [], meshes: [], buffer: null, capacity: 0, count: 0,
    slots: [], cx: 0, cy: 0, cz: 0, radius: 0, shown: -2, dirty: true };
}

// Cut a batch into clusters and write every matrix, ONCE. Everything
// expensive lives here, and here runs only when the props themselves
// change -- a placement, a move, a deletion, a layer hidden -- never
// because the camera moved.
function groupBatch(batch) {
  const size = clusterSizeFor(batch);
  batch.clusterSize = size;
  for (const cluster of batch.clusters.values()) {
    cluster.proxies.length = 0;
    cluster.dirty = true;
  }
  for (const proxy of batch.proxies) {
    if (!proxy.visible) continue;
    const p = proxy.position;
    const key = clusterKey(Math.floor(p.x / size), Math.floor(p.y / size));
    let cluster = batch.clusters.get(key);
    if (!cluster) { cluster = newCluster(key); batch.clusters.set(key, cluster); }
    cluster.proxies.push(proxy);
  }
  for (const [key, cluster] of [...batch.clusters]) {
    if (!cluster.proxies.length) { disposeCluster(batch, cluster); batch.clusters.delete(key); }
    else writeCluster(batch, cluster);
  }
  batch.grouped = true;
}

// One cluster's matrices and its bounding sphere. The sphere is grown
// from the instances' own positions plus the model's radius, which is
// what the frustum test and the tier both read.
function writeCluster(batch, cluster) {
  const needed = cluster.proxies.length;
  if (!cluster.buffer || cluster.capacity < needed) {
    let capacity = 64;
    while (capacity < needed) capacity *= 2;
    cluster.buffer = new THREE.InstancedBufferAttribute(
      new Float32Array(capacity * 16), 16);
    cluster.buffer.setUsage(THREE.StaticDrawUsage);
    cluster.capacity = capacity;
    // The meshes hold the old buffer by reference, so they have to be
    // pointed at the new one.
    for (const mesh of cluster.meshes) mesh.instanceMatrix = cluster.buffer;
  }
  const array = cluster.buffer.array;
  const c = batch.centre;
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  let biggest = 0;
  for (let i = 0; i < needed; i++) {
    const proxy = cluster.proxies[i];
    const m = proxy.matrix.elements;
    array.set(m, i * 16);
    cluster.slots[i] = proxy.record;
    const x = m[0] * c.x + m[4] * c.y + m[8] * c.z + m[12];
    const y = m[1] * c.x + m[5] * c.y + m[9] * c.z + m[13];
    const z = m[2] * c.x + m[6] * c.y + m[10] * c.z + m[14];
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (z < minZ) minZ = z;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
    if (z > maxZ) maxZ = z;
    const scale = Math.max(Math.abs(proxy.scale.x), Math.abs(proxy.scale.y),
      Math.abs(proxy.scale.z));
    if (scale > biggest) biggest = scale;
  }
  cluster.slots.length = needed;
  cluster.count = needed;
  cluster.cx = (minX + maxX) / 2;
  cluster.cy = (minY + maxY) / 2;
  cluster.cz = (minZ + maxZ) / 2;
  cluster.radius = 0.5 * Math.hypot(maxX - minX, maxY - minY, maxZ - minZ)
    + batch.radius * biggest;
  cluster.buffer.addUpdateRange(0, needed * 16);
  cluster.buffer.needsUpdate = true;
  sizeCluster(batch, cluster);
  cluster.dirty = false;
  // The tier it was showing was chosen for a cluster that no longer
  // stands where this one does.
  cluster.shown = -2;
}

// One InstancedMesh per part, made once and kept. A tier change swaps
// the geometry underneath it; nothing else about the draw changes.
function sizeCluster(batch, cluster) {
  const parts = batch.tiers[0].parts;
  if (cluster.meshes.length === parts.length) {
    for (const mesh of cluster.meshes) mesh.count = cluster.count;
    return;
  }
  for (const mesh of cluster.meshes) { propsGroup.remove(mesh); mesh.dispose(); }
  cluster.meshes = parts.map((part) => {
    const mesh = new THREE.InstancedMesh(part.geometry, part.material, 0);
    mesh.instanceMatrix = cluster.buffer;
    mesh.castShadow = part.castShadow;
    mesh.receiveShadow = part.receiveShadow;
    mesh.customDepthMaterial = batch.windDepth;
    mesh.customDistanceMaterial = batch.windDistance;
    // Culled per CLUSTER below, not per mesh by three: a cluster's own
    // sphere is measured here and is the honest one, and three's would
    // be recomputed off an instance buffer it cannot see change.
    mesh.frustumCulled = false;
    mesh.propSlots = cluster.slots;
    mesh.count = cluster.count;
    mesh.visible = false;
    propsGroup.add(mesh);
    return mesh;
  });
  // Clipping planes live on MATERIALS, and applySection only reaches the
  // ones worn by meshes already in the scene.
  if (state.section.mode === "plane") applySection();
}

function disposeCluster(batch, cluster) {
  for (const mesh of cluster.meshes) { propsGroup.remove(mesh); mesh.dispose(); }
  cluster.meshes.length = 0;
  cluster.buffer = null;
  cluster.capacity = 0;
}

// Point a cluster's meshes at one tier's geometry, or hide them. The
// whole per-frame cost of a cluster that has changed its mind.
function showCluster(batch, cluster, tier) {
  if (cluster.shown === tier) return;
  cluster.shown = tier;
  if (tier < 0) {
    for (const mesh of cluster.meshes) mesh.visible = false;
    return;
  }
  const parts = batch.tiers[tier].parts;
  for (let i = 0; i < cluster.meshes.length; i++) {
    const mesh = cluster.meshes[i];
    const part = parts[i] || parts[0];
    if (mesh.geometry !== part.geometry) mesh.geometry = part.geometry;
    mesh.count = cluster.count;
    mesh.visible = cluster.count > 0;
  }
}

const propViewSeen = new Float64Array(34).fill(NaN);
const propCull = new THREE.Frustum();
const propViewMatrix = new THREE.Matrix4();
const propCullSphere = new THREE.Sphere();
// `record` names the ONE batch whose grouping has gone stale. Called
// with nothing, every batch is stale, which is right for a deletion or
// a hidden layer and would be ruinous for one prop being dragged: a
// bare call re-cuts nine hundred thousand instances into their grid.
//
// THERE IS NO COUNTER BESIDE THIS, and there was: a first attempt gated
// the settle on one, and it was wrong within the hour. A far LOD tier
// arriving from the network sets batch.dirty without coming through
// here, the counter never moved, and every cluster in the scene went on
// drawing at full detail for ever -- measured, 1.6 billion triangles
// against the 198 million the same scene drew before. The gate asks the
// batches themselves instead, which is forty questions a frame and
// cannot be forgotten by whoever next writes to dirty.
function notePropsMoved(record) {
  if (record) {
    const batch = record.object && record.object.instancedIn;
    // A prop that is not instanced -- a fixture, a decal -- is its own
    // object in the scene and needs nothing settled.
    if (batch) batch.dirty = true;
    return;
  }
  for (const batch of propBatches.values()) batch.dirty = true;
}

// Once a frame, from renderView, so the recorder and the still export
// inherit it.
function settlePropInstances() {
  if (!propBatches.size) return;
  camera.updateMatrixWorld();
  const reach = state.recording ? 0
    : (state.detail in DETAIL_REACH ? DETAIL_REACH[state.detail] : 1);
  const view = camera.matrixWorld.elements;
  const lens = camera.projectionMatrix.elements;
  const height = renderer.domElement.height;
  let moved = false;
  for (let i = 0; i < 16; i++) {
    if (propViewSeen[i] !== view[i]) { propViewSeen[i] = view[i]; moved = true; }
    if (propViewSeen[16 + i] !== lens[i]) { propViewSeen[16 + i] = lens[i]; moved = true; }
  }
  if (propViewSeen[32] !== reach) { propViewSeen[32] = reach; moved = true; }
  if (propViewSeen[33] !== height) { propViewSeen[33] = height; moved = true; }
  // Forty questions, not nine hundred thousand: has anything at all
  // changed since the last frame? A frame in which the camera held
  // still and no prop was touched returns here, having done nothing.
  let stale = false;
  for (const batch of propBatches.values()) {
    if (batch.dirty || !batch.grouped) { stale = true; break; }
  }
  if (!moved && !stale) return;
  if (moved) {
    propViewMatrix.copy(camera.matrixWorld).invert().premultiply(camera.projectionMatrix);
    propCull.setFromProjectionMatrix(propViewMatrix);
  }
  propsGroup.updateWorldMatrix(true, false);
  for (const batch of propBatches.values()) {
    if (!batch.tiers[0].parts.length) continue;
    if (batch.dirty || !batch.grouped) {
      // A proxy's own matrix is composed from its position, rotation and
      // scale here rather than by three, because a proxy is not in the
      // scene graph (see propInstance).
      for (const proxy of batch.proxies) proxy.updateMatrix();
      groupBatch(batch);
      if (batch.casts) noteCastersChanged();
      batch.dirty = false;
    }
    settleClusters(batch, reach, height);
    if (batch.retired && !batch.proxies.length) disposePropBatch(batch);
  }
}
// A prop folder swapped under a standing field: each batch is filed
// under a name no placement will ask for, goes on drawing what already
// stands, and is freed by the settle above once the last of it has gone.
let retiredBatchCount = 0;

function retirePropBatches() {
  for (const [key, batch] of [...propBatches]) {
    if (batch.retired) continue;
    propBatches.delete(key);
    batch.retired = true;
    retiredBatchCount += 1;
    propBatches.set(key + "#retired-" + retiredBatchCount, batch);
  }
}

// Everything a batch owns and its templates do not: the baked geometry
// of every tier, the bounds the proxies wore, and the instance buffers,
// which InstancedMesh.dispose frees and geometry.dispose does not.
function disposePropBatch(batch) {
  for (const [key, held] of propBatches) {
    if (held === batch) { propBatches.delete(key); break; }
  }
  for (const cluster of batch.clusters.values()) disposeCluster(batch, cluster);
  batch.clusters.clear();
  for (const tier of batch.tiers) {
    if (!tier) continue;
    for (const part of tier.parts) part.geometry.dispose();
  }
  batch.bounds.dispose();
}

// Every visible instance of a batch, sorted into its tier by how many
// pixels its model covers from here. Written from scratch each time: a
// tier is a packed list, and a moving camera re-deals most of it anyway.
// Every cluster of a batch, culled and given its tier. This is the whole
// of what a moving camera costs now: a sphere test and a division per
// cluster, and nothing at all for a cluster that has not changed its
// mind since the last frame.
function settleClusters(batch, reach, height) {
  const lift = propsGroup.matrixWorld.elements;
  const eye = camera.matrixWorld.elements;
  // The lens is read off the camera that HAS one, by name: an orthographic
  // camera has no fov, and its pixels a metre are its frame over its zoom.
  const ortho = camera === orthographicCamera;
  const perMetre = ortho
    ? height * orthographicCamera.zoom
      / Math.max(1e-6, orthographicCamera.top - orthographicCamera.bottom)
    : height / (2 * Math.max(1e-6, Math.tan(THREE.MathUtils.degToRad(
      perspectiveCamera.fov) / 2) / (perspectiveCamera.zoom || 1)));
  for (const cluster of batch.clusters.values()) {
    if (cluster.dirty) writeCluster(batch, cluster);
    const x = cluster.cx + lift[12];
    const y = cluster.cy + lift[13];
    const z = cluster.cz + lift[14];
    // Only what casts nothing is culled by the view. A tree behind the
    // camera still throws its shadow across the frame.
    if (!batch.casts) {
      propCullSphere.center.set(x, y, z);
      propCullSphere.radius = cluster.radius + batch.windReach * windAir.windStrength.value;
      if (!propCull.intersectsSphere(propCullSphere)) { showCluster(batch, cluster, -1); continue; }
    }
    let t = 0;
    if (reach > 0) {
      const distance = ortho ? 1 : Math.max(1e-3,
        Math.hypot(x - eye[12], y - eye[13], z - eye[14]));
      // The MODEL's own radius, not the cluster's: what decides a tier is
      // how many pixels one prop covers, and a cluster of a thousand
      // tufts covers a great many however small each of them is.
      const pixels = batch.radius * perMetre / distance;
      // Too small to be seen at all: nothing is drawn. Only where the
      // detail dial allows tiers in the first place, so "full" still
      // draws every blade however far off it stands.
      if (pixels < PROP_CULL_PIXELS * reach) { showCluster(batch, cluster, -1); continue; }
      if (pixels < PROP_TIER_PIXELS[1] * reach) t = 2;
      else if (pixels < PROP_TIER_PIXELS[0] * reach) t = 1;
      while (t > 0 && !batch.tiers[t]) t -= 1;
    }
    showCluster(batch, cluster, t);
  }
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
  // One tile per FAMILY: eight tufts of the same grass are one thing to
  // choose and eight shapes to place.
  const ordered = familyEntries(state.propLibrary).sort((a, b) =>
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
        // A built-in has no file and so no snapshot beside it: it is
        // built and drawn on the spot, which costs nothing because it is
        // a handful of primitives rather than a photoscan.
        if (entry.builtIn) {
          renderObjectPreview(builtInPreview(entry.key), canvasEl);
          return;
        }
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
      + (entry.variants > 1 ? "  --  " + entry.variants + " variants, one at random each time" : "")
      + (entry.credit ? " -- " + entry.credit : "");
    tile.addEventListener("click", async () => {
      select.value = entry.key;
      paintTileSelection(holder, entry.key);
      showPropCredit(entry);
      // A family carries one of its variants, drawn fresh each time.
      const variant = pickVariant(entry.key);
      // Choosing IS picking up. Param: "it should just be a drop down and
      // i click that it gets attached to my cursor and then i move the
      // cursor to the place i like click again and the prop stays." So the
      // model is carrying, not arming: the prop exists from this moment,
      // follows the cursor, and the next click puts it down. The SHELF
      // STAYS OPEN: closing itself after every click was the old picker's
      // worst habit. The model itself may not be here yet -- this click is
      // often the very first thing to want it -- so the carry waits for
      // the load, behind the same toast every other load shows.
      const template = await ensurePropTemplate(variant);
      if (!template && !PROP_BUILDERS[variant]) return;
      carryNewProp(variant);
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

// A decal is a prop whose geometry is a plane, which is what lets it
// have the gumball, the layers, the scatter and the undo for nothing.
// The one thing it cannot inherit is where it sits.
//
// loadPropTemplate stands every prop on its feet by shifting min.z to 0,
// and propsGroup sits AT groundLevel, so a prop placed at z = 0 is
// exactly coplanar with the floor. For anything solid that is right. For
// a plane it is z-fighting, and the two millimetres baked into the GLB
// were eaten by that same normalisation: the plane's lowest point WAS
// the lift, so shifting it to zero cancelled it exactly.
//
// So the lift is applied here instead, where the floor is known. Two
// millimetres is invisible from any camera that can see the vault and
// settles the depth test outright -- the same trick, and the same
// reasoning, as HDRI_DROP.
const DECAL_LIFT = 0.002;

function isDecal(type) {
  const entry = (state.propLibrary || []).find((e) => e.key === type);
  return !!entry && entry.group === "decals";
}

// EVERY PROP CARRIES A NUMBER, so that it can be named. Param: "i
// would like a bounding box with the object type and id so i can
// reference it in layers". The label alone cannot do that -- a field of
// beeches is twelve tiles all reading "Beech" -- so the hover badge and
// the layer tile both show a number, and they always agree because
// there is only one number and one place it is minted.
//
// Session-scoped, and never reused: deleting a prop does not renumber
// the ones that remain, which is what makes a number written down stay
// true while he works. A reload numbers them again in the order the
// layout restores, which is the order the Layers drawer lists them in,
// so the badge and the tile still agree afterwards.
let propSerial = 0;

function nextPropId() {
  propSerial += 1;
  return propSerial;
}

function placeProp(type, x, y, rotation, save, scale = 1, z = 0,
                   rotX = 0, rotY = 0) {
  // Falsy rather than undefined: a restore hands back the saved 0.002,
  // which is truthy and kept, while a fresh placement passes nothing.
  if (!z && isDecal(type)) z = DECAL_LIFT;
  const template = propTemplates.get(type);
  // A library prop is one instance of its variant's batch, drawn with the
  // template's own geometry and materials: twenty figures cost one model
  // and one draw call, and twenty thousand tufts cost the same one (see
  // "the instanced props"). The object it answers to is a proxy.
  const object = template ? propInstance(type, template) : makeProp(type);
  // z is a deliberate height offset, zero for everything placed on the
  // ground and negative for the assets Param needs to sink into it
  // ("allowing them to clip below ground, as some assets need to do so").
  object.position.set(x, y, z);
  object.rotation.set(rotX, rotY, rotation);
  // A prop's feet are its origin (loadPropTemplate shifts min.z to 0), so
  // a uniform scale about the origin grows it from the GROUND UP -- the
  // rule Param set: "make sure they always stay attached to ground and
  // not grow from center, but ground up."
  object.scale.setScalar(scale);
  // record.size, when it carries one, stretches the three axes apart --
  // which is what lets a strip light be lengthened without becoming a
  // longer, fatter strip. Applied again by applyPropSize below whenever
  // either number moves.
  // A proxy stands outside the scene graph; a lamp is its own object in it.
  if (!object.instancedIn) propsGroup.add(object);
  object.userData.fromLibrary = !!template;
  const record = { id: nextPropId(), type, x, y, z, rotation, rotX, rotY,
    scale, layer: state.activeLayer, object };
  // The batch's pick answers with a record, so the proxy knows its own.
  if (object.instancedIn) object.record = record;
  // A lamp arrives lit, wearing whatever the Lights sliders currently
  // say. The caller (a restore, a scene) may overwrite both numbers and
  // call applyPropLight again; placing one by hand should not need to.
  if (isLamp(record)) {
    record.lumens = state.lampLumens;
    record.kelvin = state.lampKelvin;
    record.tint = state.lampTint;
    record.invisible = state.lampInvisible;
    // A spot arrives with a beam as well: the same four the drawer is
    // showing, so placing one by hand needs no second gesture.
    if (isSpot(record)) Object.assign(record, state.spot);
    applyPropLight(record);
  }
  object.visible = layerVisible(record.layer);
  state.props.push(record);
  // The layer this landed on has a prop more, which can make a type
  // bulk there that was not, and always changes the planting's extent.
  clearPlantings();
  notePropsMoved();
  // One more caster. A scatter is hundreds of these in a row, which is
  // why this marks rather than measures. (It sat after the return for a
  // while, and no placed prop ever told the shadow fit it had arrived.)
  noteCastersChanged();
  // The Lights heading counts the lamps in the scene, so a placement has
  // to tell it. Without this the row said "Lights" over two lamps.
  if (isLamp(record)) syncLightControls();
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
  propOutline.material.fog = false;  // drawn over everything, so never veiled
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

// ---------- a gathered set is a real selection ----------
// Param, 2026-09-12: "the select with the shift and click on layers
// menu doesnt select all items, still only one at a time. so if i want
// to do multiple operations like delete when selecting many then they
// all delete. also if i select all those objects and press edit, then i
// would like only one gumball between all objects where i can move them
// all as a group."
//
// The gathering already existed -- shift-clicking the layer tiles filled
// gatheredProps, and the tiles lit up -- but nothing except "Place
// copies" and "Move to layer" ever read it. The viewport outlined one
// prop, the gumball stood on one prop, and Delete took one prop, so a
// set of four looked and behaved exactly like a set of one. Measured
// before this change: four tiles lit, one outline, and Delete removing
// a single prop.
//
// WHO A GESTURE ACTS ON: the gathered set when it holds more than one,
// and the single selected prop otherwise. One answer, so Delete, the
// gumball and the undo cannot disagree about what "the selection" is.
function actingProps() {
  const many = stillPlaced([...gatheredProps]);
  if (many.length > 1) return many;
  return state.selectedProp ? [state.selectedProp] : [];
}

// ---------- is it still in the scene? ----------
// Asked of a whole planting at once, so it cannot walk the list for each
// record: state.props.includes over each of 930,000 blades is a walk of
// 930,000 for every one of them, and the Delete that asked it held the
// tab for 27.8 s (measured, 2026-09-13; 5.2 s at 400,000, of which the
// walk was 5.07). One set built per ask takes 23 ms at 400,000.
//
// Built fresh each time rather than kept up to date: a kept set would
// hold every deleted prop alive until the next ask, and after a planting
// has gone that is the whole field.
const STILL_PLACED_BY_SCAN = 32;

function stillPlaced(records) {
  // A handful is cheaper to look for than a set of a million is to build.
  if (records.length < STILL_PLACED_BY_SCAN) {
    return records.filter((r) => r && state.props.includes(r));
  }
  const placed = new Set(state.props);
  return records.filter((r) => r && placed.has(r));
}

// Where one gumball stands for many props: the middle of their feet.
// Their FEET, not their bodies -- a prop's origin is where it meets the
// ground (placeProp), and a group turned about the mean of its origins
// stays on the ground, which is where groups of props live.
function groupCentre(records) {
  let x = 0, y = 0, z = 0;
  for (const record of records) {
    x += record.x;
    y += record.y;
    z += record.z || 0;
  }
  const n = records.length || 1;
  return { x: x / n, y: y / n, z: z / n };
}

// An outline per member, so a set of four looks like a set of four.
// The primary keeps its own (setPropOutline); these are the rest.
//
// CAPPED, because each is a draw call: the drawer already refuses to
// picture a layer past LAYER_TILE_CAP, so a gathering is bounded in
// practice, but a shift-click over a scattered field must not turn six
// hundred props into six hundred line objects.
const GROUP_OUTLINE_CAP = 200;
let groupOutlines = [];

function clearGroupOutlines() {
  for (const outline of groupOutlines) {
    propsGroup.remove(outline);
    outline.geometry.dispose();
    outline.material.dispose();
  }
  groupOutlines = [];
}

function refreshGroupOutlines() {
  clearGroupOutlines();
  const acting = actingProps();
  if (acting.length < 2) return;
  const outline = (helper) => {
    helper.material.depthTest = false;
    helper.material.fog = false;
    helper.renderOrder = 2;
    // As with every other helper in propsGroup: a line raycast has a
    // one metre threshold and would hijack clicks near its edges.
    helper.raycast = () => {};
    propsGroup.add(helper);
    groupOutlines.push(helper);
  };
  // A WHOLE SCATTER IN THE SELECTION is drawn as the scatter's own box, in
  // the selection's colour. Two hundred outlines round two hundred of its
  // four hundred and forty-six trees said nothing about the rest.
  const counted = new Map();   // planting -> how many of it are acting
  for (const record of acting) {
    const planting = plantingOf(record);
    if (planting) counted.set(planting, (counted.get(planting) || 0) + 1);
  }
  const whole = new Set();
  for (const [planting, n] of counted) {
    const bounds = plantingBounds(planting);
    if (!bounds || n < planting.members) continue;
    whole.add(planting);
    outline(new THREE.Box3Helper(bounds, new THREE.Color(0x93a6bb)));
  }
  let drawn = 0;
  for (const record of acting) {
    if (drawn >= GROUP_OUTLINE_CAP) break;
    if (record === state.selectedProp || !record.object) continue;
    if (whole.has(plantingOf(record))) continue;
    outline(new THREE.BoxHelper(record.object, 0x93a6bb));
    drawn += 1;
  }
}

// ---------- a scatter is one thing ----------
// Param, 2026-09-12: "instead of doing individual bounding boxes for
// each scatter element with the hover over mouse funciton, turn it into
// a scatter bounding box only".
//
// He is right: a box round one blade of grass out of a hundred thousand
// names nothing anybody wants to refer to, and the badge over it reads
// "Grass #431029", which is not a thing he placed. What he placed was a
// scatter. So a scattered prop answers for its whole run.
//
// Each member carries its run, stamped as it lands, because searching
// the runs for a record would be a walk over every prop in every run on
// every hover -- 930,429 of them in his own scene.
let scatterRunCount = 0;

function markScatterRun(run, only) {
  if (!run.id) {
    scatterRunCount += 1;
    run.id = scatterRunCount;
  }
  for (const record of (only || run.records)) record.run = run;
  // The bounds are measured once, when they are first wanted, and thrown
  // away whenever the run changes.
  run.bounds = null;
}

// THE PLANTING A PROP BELONGS TO: the scatter that placed it, carried on
// the record as record.scatter and written into the layout beside it.
//
// It used to be worked out from what was on the layer -- every type there
// in bulk, sixty-four or more -- because nothing a layout kept said which
// props had been scattered. That was wrong for the case Param met next:
// trees are scattered sparsely by nature, his beeches came to 50, 36, 26
// and 15 of four kinds, none of them bulk, and every tree boxed alone
// ("It also should have been that these trees should be one scatter").
// A count cannot tell a sparse scatter from props placed by hand; the
// scatter that placed them can.
//
// ONE SCATTER IS ONE MIX ON ONE LAYER, however many strokes painted it:
// a stroke is how the brush was moved, not a thing he placed. A new
// stroke joins the newest planting on its layer whose kinds its species
// could all have made, and starts a new one otherwise (scatterIdFor).
const plantings = new Map();   // "layer:scatter" -> { layer, scatter, bounds, members }
// The highest id handed out since the field was last restored, so a new
// scatter never takes the number of one already standing.
let scatterIdCeiling = 0;

function clearPlantings() { plantings.clear(); }

// Null for anything placed by hand, which keeps its own box.
function plantingOf(record) {
  if (!record || !record.scatter) return null;
  const key = record.layer + ":" + record.scatter;
  let planting = plantings.get(key);
  if (!planting) {
    planting = { layer: record.layer, scatter: record.scatter, bounds: null, members: 0 };
    plantings.set(key, planting);
  }
  return planting;
}

// A planting is its scatter ON ITS LAYER: props grouped onto a layer of
// their own keep their scatter's number and become a planting there.
function inPlanting(record, planting) {
  return record.scatter === planting.scatter && record.layer === planting.layer;
}

// What the badge and the Layers drawer call it, in the same words, so the
// one in the viewport can be found in the drawer.
function plantingName(planting) {
  return "Scatter #" + planting.scatter + " of "
    + planting.members.toLocaleString() + " props";
}

// Measured once and kept: over three quarters of a million records that
// is a walk worth not repeating sixty times a second, and a planting
// does not move on its own.
function plantingBounds(planting) {
  if (planting.bounds) return planting.bounds;
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  let members = 0;
  for (const record of state.props) {
    if (!inPlanting(record, planting)) continue;
    members += 1;
    const scale = record.scale || 1;
    const reach = propFootprint(record.type) * scale;
    const z = record.z || 0;
    if (record.x - reach < minX) minX = record.x - reach;
    if (record.y - reach < minY) minY = record.y - reach;
    if (z < minZ) minZ = z;
    if (record.x + reach > maxX) maxX = record.x + reach;
    if (record.y + reach > maxY) maxY = record.y + reach;
    // Its own height, not twice its spread: a beech is 31 m tall on a
    // 16 m crown, and a box of twice the crown stopped at its middle.
    const top = z + propStature(record.type) * scale;
    if (top > maxZ) maxZ = top;
  }
  planting.members = members;
  planting.bounds = members
    ? new THREE.Box3(new THREE.Vector3(minX, minY, minZ),
      new THREE.Vector3(maxX, maxY, maxZ))
    : null;
  return planting.bounds;
}

// Every member of a planting, gathered only when something is actually
// going to be done to them: the hover itself never needs the list.
function plantingRecords(planting) {
  return state.props.filter((record) => inPlanting(record, planting));
}

// The scatter a new stroke or fill belongs to: the newest planting on its
// layer whose every kind the species now chosen could have made, or a new
// one. So painting more beeches joins the beeches, and switching the mix
// to grass starts the grass. Walked once per stroke, not per stamp.
function scatterIdFor(layerId) {
  const mayPlace = new Set();
  for (const one of state.scatter.species) {
    const members = familyMembers(one.type);
    if (!members.length) mayPlace.add(one.type);
    for (const member of members) mayPlace.add(member.key);
  }
  const fits = new Map();   // scatter id -> could this mix have made all of it
  for (const record of state.props) {
    if (!record.scatter || record.layer !== layerId) continue;
    if (fits.get(record.scatter) === false) continue;
    fits.set(record.scatter, mayPlace.has(record.type));
  }
  let join = 0;
  for (const [id, fit] of fits) if (fit && id > join) join = id;
  if (join) return join;
  scatterIdCeiling += 1;
  return scatterIdCeiling;
}

// ---------- plantings in a layout saved before scatters were named ----------
// Everything written before 2026-09-13 carries no scatter id, his own
// field included, and nothing it kept says which strokes placed what: the
// rows of his beeches and his ground cover are interleaved (measured,
// rows 139 to 1,969 of 98,812). So it is worked out once, on the way in,
// and written back with the next save, after which it is never guessed.
//
// A kind on a layer was scattered if it is there in bulk, or if its
// members stand at different sizes: the scatter draws every size from its
// range, and a prop placed by hand arrives at exactly 1. What was
// scattered is split by stature -- the ground cover, and what stands
// above a person -- because that is the line between the field painted
// underneath and the trees painted over it.
const LEGACY_BULK = 64;
const LEGACY_SIZE_SPREAD = 0.02;
const LEGACY_TALL_METRES = 2;

function adoptLegacyScatters() {
  const kinds = new Map();
  for (const record of state.props) {
    if (record.scatter) continue;
    const key = record.layer + "|" + record.type;
    let kind = kinds.get(key);
    if (!kind) {
      kind = { layer: record.layer, type: record.type, records: [],
        low: Infinity, high: -Infinity };
      kinds.set(key, kind);
    }
    kind.records.push(record);
    const scale = record.scale || 1;
    if (scale < kind.low) kind.low = scale;
    if (scale > kind.high) kind.high = scale;
  }
  const groups = new Map();   // "layer|tall" -> { layer, tall, kinds }
  for (const kind of kinds.values()) {
    const scattered = kind.records.length >= LEGACY_BULK
      || (kind.records.length > 1 && kind.high - kind.low >= LEGACY_SIZE_SPREAD);
    if (!scattered) continue;
    const tall = propStature(kind.type) >= LEGACY_TALL_METRES ? 1 : 0;
    const key = kind.layer + "|" + tall;
    if (!groups.has(key)) groups.set(key, { layer: kind.layer, tall, kinds: [] });
    groups.get(key).kinds.push(kind);
  }
  // In a fixed order, so the same layout names its scatters the same way
  // every time it is opened until the names are saved.
  const ordered = [...groups.values()].sort((a, b) => a.layer - b.layer || a.tall - b.tall);
  for (const group of ordered) {
    scatterIdCeiling += 1;
    for (const kind of group.kinds) {
      for (const record of kind.records) record.scatter = scatterIdCeiling;
    }
  }
}

// After a field is restored: the ceiling is the highest name it came back
// with, and a layout too old to carry names has them worked out.
function settleRestoredScatters(knowsScatters) {
  let top = 0;
  for (const record of state.props) if (record.scatter > top) top = record.scatter;
  scatterIdCeiling = top;
  if (!knowsScatters) adoptLegacyScatters();
  clearPlantings();
}

// ---------- the hover badge ----------
// Param, 2026-09-12: "i would like a bounding box with the object type
// and id so i can reference it in layers, that pops up when i hover
// over items with the mouse."
//
// A box in a colour of its OWN. The selection's outline is blue-grey,
// and a hover drawn in the same colour would say "this is selected"
// about something the pointer merely happens to be over; amber says
// "this is what you are pointing at" and nothing more. Like the
// outline, it lives in propsGroup and must never catch the pointer --
// a line raycast has a one metre default threshold, which is what made
// the selection box hijack clicks near its edges once already.
const HOVER_COLOUR = 0xd9a441;
let hoverBox = null;
let hoveredProp = null;
let lastHoverPick = 0;
// The anchor is taken ONCE, when the hover changes, and re-projected
// every frame. Measuring the object per frame would mean traversing a
// tree's several hundred leaf cards sixty times a second to place a
// label, and the prop does not move while it is being hovered.
const hoverAnchor = new THREE.Vector3();
const hoverBounds = new THREE.Box3();
// How often the pointer asks what is under it. A pick is a raycast over
// every prop and, where that misses, a box test over every prop: on a
// scattered field that is real work, and sixty a second to place a
// label is not worth it. Twenty a second reads as instant.
const HOVER_PICK_MS = 50;
// Above this many props the box-by-box fallback is skipped. It measures
// every prop in the scene, which is what lets a click between a tree's
// leaves still find the tree; on a field of thousands it is a stall per
// pick, and badging one tuft out of four thousand is not worth one.
const HOVER_FALLBACK_CAP = 400;

function clearHoverBox() {
  if (!hoverBox) return;
  propsGroup.remove(hoverBox);
  hoverBox.geometry.dispose();
  hoverBox.material.dispose();
  hoverBox = null;
}

function setHoveredProp(record) {
  if (record === hoveredProp) return;
  hoveredProp = record;
  clearHoverBox();
  const badge = document.getElementById("hover-badge");
  if (!record || !record.object) {
    if (badge) badge.classList.add("hidden");
    paintLayerPointer();
    return;
  }
  // A SCATTERED PROP ANSWERS FOR ITS RUN. One box round the whole
  // planting, and a name for the thing he actually placed.
  const planting = plantingOf(record);
  const bounds = planting ? plantingBounds(planting) : null;
  if (bounds) {
    hoverBox = new THREE.Box3Helper(bounds, new THREE.Color(HOVER_COLOUR));
    hoverAnchor.set((bounds.min.x + bounds.max.x) / 2,
      (bounds.min.y + bounds.max.y) / 2, bounds.max.z);
  } else {
    hoverBox = new THREE.BoxHelper(record.object, HOVER_COLOUR);
    hoverBounds.setFromObject(record.object);
    if (hoverBounds.isEmpty()) {
      hoverAnchor.set(record.x, record.y, record.z || 0);
    } else {
      hoverAnchor.set((hoverBounds.min.x + hoverBounds.max.x) / 2,
        (hoverBounds.min.y + hoverBounds.max.y) / 2, hoverBounds.max.z);
    }
  }
  hoverBox.material.depthTest = false;
  hoverBox.material.fog = false;
  hoverBox.renderOrder = 2;
  hoverBox.raycast = () => {};
  // The box is in propsGroup's own space, and a run's bounds are
  // measured in it too (a record's x and y are group coordinates), so
  // the two agree without a conversion.
  propsGroup.add(hoverBox);
  if (badge) {
    badge.textContent = (bounds
      ? plantingName(planting)
      : propTag(record)) + "  \u00b7  " + layerName(record.layer);
    badge.classList.remove("hidden");
  }
  placeHoverBadge();
  paintLayerPointer();
}

// The badge follows its prop as the camera moves, which is one
// projection of one point per frame.
const hoverProjected = new THREE.Vector3();

function placeHoverBadge() {
  const badge = document.getElementById("hover-badge");
  if (!badge || !hoveredProp) return;
  hoverProjected.copy(hoverAnchor).project(camera);
  // Behind the eye: the projection flips through the origin and the
  // badge would appear on the opposite side of the screen from the
  // thing it names.
  if (hoverProjected.z > 1) { badge.classList.add("hidden"); return; }
  badge.classList.remove("hidden");
  const rect = canvas.getBoundingClientRect();
  badge.style.left =
    Math.round(rect.left + (hoverProjected.x * 0.5 + 0.5) * rect.width) + "px";
  badge.style.top =
    Math.round(rect.top + (-hoverProjected.y * 0.5 + 0.5) * rect.height) + "px";
}

// ---------- nudging what the pointer is over ----------
// Param: "the arrow keys to move it say 0.2m each time".
const NUDGE_METRES = 0.2;
// A run of taps is ONE undo. Twenty presses that each pushed an entry
// would flush the fifty the history holds and leave nothing else in it,
// and a nudge is plainly one adjustment rather than twenty.
const NUDGE_JOIN_MS = 1500;
let lastNudge = null;

function nudgeHoveredProp(key) {
  const record = hoveredProp;
  if (!record) return false;
  const forward = new THREE.Vector3();
  camera.getWorldDirection(forward);
  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  const step = arrowStep(key, screenGroundAxes(forward.toArray(),
    right.toArray(), up.toArray()), NUDGE_METRES);
  if (!step) return false;
  const now = performance.now();
  const joining = lastNudge && lastNudge.record === record
    && now - lastNudge.at < NUDGE_JOIN_MS;
  if (!joining) {
    const from = { x: record.x, y: record.y };
    pushUndo("the nudge", () => {
      record.x = from.x;
      record.y = from.y;
      record.object.position.set(from.x, from.y, record.z || 0);
      notePropsMoved(record);
      if (state.selectedProp === record) {
        refreshPropOutline();
        refreshPropGumball();
      }
      if (hoverBox) hoverBox.update();
      saveProps();
    });
  }
  lastNudge = { record, at: now };
  record.x += step[0];
  record.y += step[1];
  record.object.position.set(record.x, record.y, record.z || 0);
  notePropsMoved(record);
  if (hoverBox) hoverBox.update();
  hoverAnchor.x += step[0];
  hoverAnchor.y += step[1];
  placeHoverBadge();
  if (state.selectedProp === record) {
    refreshPropOutline();
    refreshPropGumball();
  }
  saveProps();
  refreshLayersShelf();
  return true;
}

// What the pointer is over, at most twenty times a second. Nothing is
// hovered while something is being carried, dragged, aimed or stamped:
// the pointer is already spoken for, and a badge naming a second prop
// during a drag is noise. Nor during a still, where it would reach the
// picture.
function hoverPick(event) {
  if (state.carrying || state.gumball || stampRig || aimingLight || state.recording
      || document.body.classList.contains("stilling")) {
    setHoveredProp(null);
    return;
  }
  const now = performance.now();
  if (now - lastHoverPick < HOVER_PICK_MS) return;
  lastHoverPick = now;
  setHoveredProp(propRecordAt(event,
    state.props.length <= HOVER_FALLBACK_CAP));
}

// ---------- the gumball ----------
// Rhino's gesture set, cut down to what a ground prop can do (Param:
// "can we do a gumball where the rotate is like we might find in rhino
// and scale is also like that off the gumball"): a blue ring about Z to
// rotate, a gold square off the ring to scale about the feet, and the
// body itself to move (the existing carry). The record stays the truth;
// saveProps runs on release, not per pixel.
// The handle group itself is declared far above, next to renderView,
// because renderView sizes it every frame and a `let` down here would be
// in its temporal dead zone if anything ever rendered during boot.

function clearPropGumball() {
  if (!propGumball) return;
  propsGroup.remove(propGumball);
  for (const part of propGumball.children) {
    part.geometry.dispose();
    part.material.dispose();
  }
  propGumball = null;
}

// Rhino's gumball, as Param drew it: an arrow per axis to move along,
// an arc per axis to turn about, a small square per axis to scale by,
// and a dot at the origin. Axis colours are Rhino's own and are not
// negotiable to anyone who has used it -- X red, Y green, Z blue.
//
// WORLD ALIGNED, like Rhino's default: the gumball does not spin with
// the object it is driving. A gumball that turned with its prop would
// make "drag the red arrow" mean a different direction after every
// rotation, which is exactly the confusion the fixed frame prevents.
const GUMBALL_AXES = [
  { key: "x", colour: 0xd63b3b, dir: [1, 0, 0] },
  { key: "y", colour: 0x3faa4f, dir: [0, 1, 0] },
  { key: "z", colour: 0x2f6fe4, dir: [0, 0, 1] },
];

// Param: "can we make it about 3 times smaller? Have it a default size
// for all objects." It used to be cut to the prop's own footprint, which
// is why a fifteen-metre beech wore a gumball you could park a car in
// and a bollard wore one you had to hunt for. Rhino's answer, and now
// ours: build it at UNIT size and scale it per frame off the camera
// distance, so it holds one size ON SCREEN whatever it drives and
// however far away you stand. The fraction is of the viewport height.
const GUMBALL_SCREEN = 0.1;

// The world height the camera sees where the gumball stands, which is
// what keeps the handles a constant size on screen however far away the
// prop is. The two projections answer it differently and there is no
// common formula: distance is the whole story in perspective and means
// NOTHING in orthographic, where the frame is the same width at the
// near plane as at the far one. Left on the perspective formula, an
// orthographic gumball grew with every step the eye took backwards.
function visibleHeightAt(point) {
  if (camera.isOrthographicCamera) {
    return orthoFrameHeight / (camera.zoom || 1);
  }
  const distance = camera.position.distanceTo(point);
  return 2 * distance
    * Math.tan(THREE.MathUtils.degToRad(perspectiveCamera.fov) / 2);
}

function sizePropGumball() {
  if (!propGumball) return;
  const span = visibleHeightAt(propGumball.position);
  propGumball.scale.setScalar(Math.max(1e-4, GUMBALL_SCREEN * span));
}

// ---------- the gumball raised by a double click ----------
// Param, 2026-09-12: "if i double click while its hovered over the
// gumball comes up and i can move the object around, double clicking
// anywhere to turn it off. this does not move us into edit mode."
//
// So there are two ways to have handles, and only one of them is a
// mode. This holds the record whose gumball is up WITHOUT edit mode;
// edit mode gives handles to whatever is selected, as it always has.
// Everything downstream -- the drag, the undo, the save -- is the same
// gumball either way, which is the point of doing it with one variable
// rather than with a second set of handles.
let gumballLoose = null;

function gumballIsUpFor(record) {
  return !!record && (state.propEdit || gumballLoose === record);
}

function setPropGumball(record) {
  clearPropGumball();
  if (!gumballIsUpFor(record)) return;
  // ONE gumball for the whole gathering, standing at its centre.
  propGumball = new THREE.Group();
  const radius = 1;                       // sized on screen, not in metres
  const slim = radius * 0.02;
  const fat = radius * 0.1;                       // the invisible grab
  const stem = radius * 1.05;
  const head = radius * 0.085;
  const cube = radius * 0.075;

  const paint = (colour) => new THREE.MeshBasicMaterial({
    color: colour, transparent: true, opacity: 0.92, depthTest: false, fog: false });
  const hidden = () => new THREE.MeshBasicMaterial({ visible: false });
  // The LOOK is slim; the GRAB is generous. A one-centimetre tube needs
  // pixel aim, so every visible handle hides a fat invisible twin that
  // does the actual catching -- the trick under Rhino's own gumball.
  const add = (mesh, handle, grab) => {
    mesh.renderOrder = 3;
    mesh.userData.handle = handle;
    propGumball.add(mesh);
    if (grab) {
      grab.userData.handle = handle;
      grab.position.copy(mesh.position);
      grab.rotation.copy(mesh.rotation);
      propGumball.add(grab);
    }
  };

  for (const axis of GUMBALL_AXES) {
    const direction = new THREE.Vector3(...axis.dir);
    // Three.js cylinders and cones stand up +Y; turn each onto its axis.
    const lie = new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), direction);

    const shaft = new THREE.Mesh(
      new THREE.CylinderGeometry(slim, slim, stem, 8), paint(axis.colour));
    shaft.quaternion.copy(lie);
    shaft.position.copy(direction).multiplyScalar(stem / 2);
    const grabShaft = new THREE.Mesh(
      new THREE.CylinderGeometry(fat, fat, stem, 8), hidden());
    grabShaft.quaternion.copy(lie);
    add(shaft, "move-" + axis.key, grabShaft);

    const tip = new THREE.Mesh(
      new THREE.ConeGeometry(head, head * 2.4, 12), paint(axis.colour));
    tip.quaternion.copy(lie);
    tip.position.copy(direction).multiplyScalar(stem + head);
    const grabTip = new THREE.Mesh(
      new THREE.ConeGeometry(fat, head * 2.6, 8), hidden());
    grabTip.quaternion.copy(lie);
    add(tip, "move-" + axis.key, grabTip);

    // The scale square, part way out, the way Rhino seats it inboard of
    // the arrow so the two never fight for the same pixels.
    const square = new THREE.Mesh(
      new THREE.BoxGeometry(cube, cube, cube), paint(axis.colour));
    square.position.copy(direction).multiplyScalar(stem * 0.62);
    const grabSquare = new THREE.Mesh(
      new THREE.BoxGeometry(fat * 2, fat * 2, fat * 2), hidden());
    add(square, "scale-" + axis.key, grabSquare);

    // The arc turns ABOUT this axis, so it is drawn in the plane the
    // axis is normal to, and wears the axis colour.
    const arc = new THREE.Mesh(
      new THREE.TorusGeometry(stem * 0.78, slim, 8, 40, Math.PI / 2),
      paint(axis.colour));
    const grabArc = new THREE.Mesh(
      new THREE.TorusGeometry(stem * 0.78, fat * 0.8, 6, 24, Math.PI / 2),
      hidden());
    // A torus is born in the XY plane about +Z; stand it about its axis.
    arc.quaternion.copy(lie).multiply(
      new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, 0)));
    add(arc, "rot-" + axis.key, grabArc);
  }

  const origin = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 0.05, 12, 10),
    new THREE.MeshBasicMaterial({ color: 0xf4f4f4, transparent: true,
      opacity: 0.95, depthTest: false, fog: false }));
  origin.renderOrder = 3;
  propGumball.add(origin);

  const acting = actingProps();
  const stand = acting.length > 1 ? groupCentre(acting) : record;
  propGumball.position.set(stand.x, stand.y, (stand.z || 0) + 0.02);
  propsGroup.add(propGumball);
  // Sized before it is ever seen or raycast: a click that lands between
  // the build and the next render must test the gumball at the size it
  // will be drawn at, not at unit size.
  sizePropGumball();
}

// Cheap follow while a prop is carried or turned: position only. Its
// SIZE no longer follows anything about the prop, so scaling a prop
// leaves the gumball alone; only the camera changes how big it draws.
function refreshPropGumball() {
  if (!propGumball || !state.selectedProp) return;
  // Position only. The gumball is world-aligned by design, so a turning
  // prop must not carry it round (see setPropGumball).
  const acting = actingProps();
  const stand = acting.length > 1 ? groupCentre(acting) : state.selectedProp;
  propGumball.position.set(stand.x, stand.y, (stand.z || 0) + 0.02);
}

// Every outline the selection owns, moved to where its prop now is.
function refreshGroupOutlinePositions() {
  for (const outline of groupOutlines) outline.update();
}

function gumballHandleAt(event) {
  if (!propGumball) return null;
  // Raycast trusts matrixWorld as stored, and a gumball built THIS frame
  // has not been through a render yet: size it and update it, or the ray
  // tests a ring still sitting at the origin at the wrong size.
  sizePropGumball();
  propGumball.updateMatrixWorld(true);
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  const hits = propRaycaster.intersectObjects(propGumball.children, false);
  return hits.length ? hits[0].object.userData.handle : null;
}

// The two readings every gumball drag needs, both taken against a plane
// chosen for the gesture rather than against the ground. The ground plane
// is useless for a vertical drag (the ray barely moves along it, and from
// a low camera it reaches past infinity), and useless again for a
// rotation about anything but Z.
const gumballPlane = new THREE.Plane();
const gumballHit = new THREE.Vector3();
const AXIS_VECTORS = [
  new THREE.Vector3(1, 0, 0),
  new THREE.Vector3(0, 1, 0),
  new THREE.Vector3(0, 0, 1),
];

function gumballOrigin(record) {
  return new THREE.Vector3(record.x, record.y, record.z || 0);
}

function pointerRay(event) {
  const rect = canvas.getBoundingClientRect();
  propRaycaster.setFromCamera(new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1), camera);
  return propRaycaster.ray;
}

// How far along one world axis the pointer sits, in metres. The plane
// CONTAINS the axis and is turned as square to the eye as a plane
// containing that axis can be, which keeps the reading steady at any
// camera angle. Null when the ray is parallel to it.
function axisDistanceAt(event, record, index) {
  const ray = pointerRay(event);
  const direction = AXIS_VECTORS[index];
  const view = new THREE.Vector3();
  camera.getWorldDirection(view);
  // The part of the view direction square to the axis: that is the
  // normal of the plane we want.
  const normal = view.clone().addScaledVector(direction,
    -view.dot(direction));
  if (normal.lengthSq() < 1e-9) return null;    // sighting down the axis
  normal.normalize();
  const origin = gumballOrigin(record);
  gumballPlane.setFromNormalAndCoplanarPoint(normal, origin);
  if (!ray.intersectPlane(gumballPlane, gumballHit)) return null;
  return gumballHit.sub(origin).dot(direction);
}

// The pointer's angle about one world axis, measured in the plane that
// axis is normal to. For Z this is the old ground-plane reading; for X
// and Y it is the same idea stood on its side.
function rotationAngleAt(event, record, index) {
  const ray = pointerRay(event);
  const normal = AXIS_VECTORS[index];
  const origin = gumballOrigin(record);
  gumballPlane.setFromNormalAndCoplanarPoint(normal, origin);
  if (!ray.intersectPlane(gumballPlane, gumballHit)) return null;
  const local = gumballHit.sub(origin);
  const u = AXIS_VECTORS[(index + 1) % 3];
  const v = AXIS_VECTORS[(index + 2) % 3];
  if (local.lengthSq() < 1e-12) return null;
  return Math.atan2(local.dot(v), local.dot(u));
}

// ---------- moving a gathering as one ----------
// Every member is written from where it STOOD when the drag began, not
// from where it is now: accumulating a delta per frame drifts, and a
// drag that goes out and comes back would not land where it started.
const groupRotation = new THREE.Quaternion();
const groupAxis = new THREE.Vector3();
const groupOffset = new THREE.Vector3();
const groupEuler = new THREE.Euler();
const groupStartQuaternion = new THREE.Quaternion();

// What each member has to remember for the length of one drag.
function captureGroup(records) {
  return records.map((record) => ({ record,
    x: record.x, y: record.y, z: record.z || 0,
    rotation: record.rotation || 0, rotX: record.rotX || 0,
    rotY: record.rotY || 0, scale: record.scale || 1 }));
}

// Slide the whole group by one vector.
function moveGroup(captured, dx, dy, dz) {
  for (const was of captured) {
    was.record.x = was.x + dx;
    was.record.y = was.y + dy;
    was.record.z = was.z + dz;
    was.record.object.position.set(was.record.x, was.record.y, was.record.z);
  }
  // ONE mark for the whole pass: a group gesture is one
  // gesture over one batch, and marking per member would re-cut
  // its grid once for every prop in it.
  for (const was of captured) notePropsMoved(was.record);
}

// Turn the whole group about one axis through a point. Each member's
// POSITION swings round the centre and the member itself turns by the
// same angle, which is what makes a group turn rather than a flock of
// props each spinning on the spot.
function turnGroup(captured, centre, index, angle) {
  groupAxis.set(index === 0 ? 1 : 0, index === 1 ? 1 : 0, index === 2 ? 1 : 0);
  groupRotation.setFromAxisAngle(groupAxis, angle);
  for (const was of captured) {
    groupOffset.set(was.x - centre.x, was.y - centre.y, was.z - centre.z);
    groupOffset.applyQuaternion(groupRotation);
    was.record.x = centre.x + groupOffset.x;
    was.record.y = centre.y + groupOffset.y;
    was.record.z = centre.z + groupOffset.z;
    was.record.object.position.set(was.record.x, was.record.y, was.record.z);
    groupStartQuaternion.setFromEuler(
      groupEuler.set(was.rotX, was.rotY, was.rotation, "XYZ"));
    groupStartQuaternion.premultiply(groupRotation);
    groupEuler.setFromQuaternion(groupStartQuaternion, "XYZ");
    was.record.rotX = groupEuler.x;
    was.record.rotY = groupEuler.y;
    was.record.rotation = groupEuler.z;
    applyPropRotation(was.record);
  }
  // ONE mark for the whole pass: a group gesture is one
  // gesture over one batch, and marking per member would re-cut
  // its grid once for every prop in it.
  for (const was of captured) notePropsMoved(was.record);
}

// Grow or shrink the group about its centre: each member's distance
// from the centre scales with its own size, so the arrangement keeps
// its shape rather than the props merely getting bigger in place.
function scaleGroup(captured, centre, factor) {
  for (const was of captured) {
    was.record.x = centre.x + (was.x - centre.x) * factor;
    was.record.y = centre.y + (was.y - centre.y) * factor;
    was.record.z = centre.z + (was.z - centre.z) * factor;
    was.record.object.position.set(was.record.x, was.record.y, was.record.z);
    was.record.scale = Math.min(5, Math.max(0.2, was.scale * factor));
    applyPropSize(was.record);
  }
  // ONE mark for the whole pass: a group gesture is one
  // gesture over one batch, and marking per member would re-cut
  // its grid once for every prop in it.
  for (const was of captured) notePropsMoved(was.record);
}

// Put every member back exactly as it stood. One undo for one drag.
function restoreGroup(captured) {
  for (const was of captured) {
    Object.assign(was.record, { x: was.x, y: was.y, z: was.z,
      rotation: was.rotation, rotX: was.rotX, rotY: was.rotY,
      scale: was.scale });
    applyPropRotation(was.record);
    applyPropSize(was.record);
    was.record.object.position.set(was.x, was.y, was.z);
  }
  // ONE mark for the whole pass: a group gesture is one
  // gesture over one batch, and marking per member would re-cut
  // its grid once for every prop in it.
  for (const was of captured) notePropsMoved(was.record);
}

// Every rotation the record carries, written onto the object at once.
// Z is the old `rotation`, kept under its own name so scenes and layouts
// saved before tilt existed still read.
function applyPropRotation(record) {
  record.object.rotation.set(record.rotX || 0, record.rotY || 0,
    record.rotation || 0);
  notePropsMoved(record);
}

// How tall this prop stands, for bounding the lift. Measured from the
// object rather than the template, so a scaled prop gets its real height.
function propHeightOf(record) {
  const box = new THREE.Box3().setFromObject(record.object);
  const height = box.max.z - box.min.z;
  return Number.isFinite(height) && height > 0.2 ? height : 5;
}

let propEditHinted = false;

function selectProp(record) {
  state.selectedProp = record;
  setPropOutline(record);
  // BEFORE the gumball, which asks where the group's centre is and
  // therefore needs the group to be settled first.
  refreshGroupOutlines();
  setPropGumball(record);
  paintLayerChosen();
  // Selecting a lamp aims the Lights sliders at that lamp alone, so they
  // have to show its numbers rather than the last thing they showed.
  syncLightControls();
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

// `fallback` runs the box-by-box sweep when the ray hit nothing, which
// is what lets a click between a tree's leaf cards still find the tree.
// It measures every prop in the scene, so the hover pick turns it off
// on a big field (HOVER_FALLBACK_CAP); a real click always gets it.
function propRecordAt(event, fallback = true) {
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
    // A batched prop is one instance of a batch mesh: the hit says which
    // instance, and the tier's slot list says whose record it is.
    if (hit.object.propSlots) {
      const mine = hit.object.propSlots[hit.instanceId];
      if (mine && mine.object.visible) return mine;
      continue;
    }
    let node = hit.object;
    while (node.parent && node.parent !== propsGroup) node = node.parent;
    const record = state.props.find((p) => p.object === node);
    if (record && record.object.visible) return record;
  }
  // A tree is mostly air: a click between the leaves misses every
  // triangle. Fall back to the bounding boxes, nearest box first, so
  // clicking "the tree" means the tree rather than a lottery over its
  // leaf cards.
  if (!fallback) return null;
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
  // The principal lines' metal while the library's polished dark steel
  // loads (and forever if it cannot): darker silver, not black -- his
  // correction after the whole net briefly went near-black.
  bar: new THREE.MeshPhysicalMaterial({
    color: 0x787d86, roughness: 0.35, metalness: 1.0, envMapIntensity: 1.2,
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
  // Born not casting: syncNetShadow at every visibility/opacity writer
  // decides from live state, so a SOLID net grounds itself while a
  // fading one goes quiet (see syncNetShadow's own comment).
  wires.castShadow = nodes.castShadow = false;
  return { wires, nodes };
}

// Shadow maps ignore opacity, so a net fading out on the strike used to
// keep casting a full hard grid shadow -- the old fix was a blanket
// castShadow false, which then left a SOLID net on screen with no shadow
// at all (Param: "the formwork doesnt project a shadow?"). The flag now
// follows the state at every writer: casting while present and solid,
// quiet the moment it fades or hides.
function syncNetShadow(object) {
  object.castShadow = object.visible && object.material.opacity > 0.6;
}

// ---------- the principal lines ----------
// One per leg (Param): "they run up the middle and its the row that the
// columns connect to". Each exported column TREE is one leg; its branch
// tips touch the net, and the row of net edges threading those touch
// points -- walked on down to the leg's own springing -- is that leg's
// principal line. Dressed as rectangular bars in a darker steel over the
// ordinary silver net; the library's polished dark steel once it
// arrives, a plain darker silver until then.
const PRINCIPAL_SKIN = "metal/steel-polished-dark";

// What a cable is: near-black, not the net's bright silver. Param, on
// seeing the machine's wires against his formwork: "the cables should be
// black to match the cables used on formwork". It multiplies the polished
// dark steel above, so the metal's own grain still reads through.
const CABLE_BLACK = 0x24262a;

// How far the plant reverses out over the strike. Param: "have the
// mechanism go backwards from its position on each side (backwards
// mirrored) when the collapse and fade of the mechanism happens instead
// of having it fall under the ground." It fades as it goes, so this only
// has to read as driving away, and it is gone by the time it stops:
// three metres, on his measure ("they only need to move 3m back in
// total, before reaching 0 opacity"). The fade runs on the same strike
// fraction, so the last metre is already the faintest.
const MACHINE_RETREAT = 3;

function principalEdges() {
  const members = state.columnMembers || [];
  const bundle = state.bundle;
  if (!bundle || !members.length) return [];
  const vertices = bundle.analysis_mesh.vertices;
  const edges = bundle.analysis_mesh.edges;

  // The column trees, by shared endpoints: one tree is one leg.
  const keyOf = (p) => p.map((c) => Math.round(c * 1000)).join(",");
  const parent = new Map();
  const find = (k) => {
    let root = k;
    while (parent.get(root) !== root) root = parent.get(root);
    parent.set(k, root);
    return root;
  };
  const degree = new Map();
  for (const member of members) {
    for (const p of [member.from, member.to]) {
      const k = keyOf(p);
      if (!parent.has(k)) parent.set(k, k);
      degree.set(k, (degree.get(k) || 0) + 1);
    }
    parent.set(find(keyOf(member.from)), find(keyOf(member.to)));
  }
  // Tips: degree-one endpoints at the HIGH end of their member; the
  // degree-one LOW ends are the feet on the ground.
  const tipsByTree = new Map();
  for (const member of members) {
    const high = member.from[2] >= member.to[2] ? member.from : member.to;
    if ((degree.get(keyOf(high)) || 0) !== 1) continue;
    const tree = find(keyOf(high));
    if (!tipsByTree.has(tree)) tipsByTree.set(tree, []);
    tipsByTree.get(tree).push(high);
  }

  // Each tip lands on its nearest net vertex, within a metre.
  const nearestVertex = (p) => {
    let best = -1, bestDistance = 1;
    for (let i = 0; i < vertices.length; i++) {
      const v = vertices[i];
      const d = Math.hypot(v[0] - p[0], v[1] - p[1], v[2] - p[2]);
      if (d < bestDistance) { bestDistance = d; best = i; }
    }
    return best;
  };

  // The net as a weighted graph, built once.
  const adjacency = new Map();
  edges.forEach(([a, b], index) => {
    if (!adjacency.has(a)) adjacency.set(a, []);
    if (!adjacency.has(b)) adjacency.set(b, []);
    adjacency.get(a).push([b, index]);
    adjacency.get(b).push([a, index]);
  });
  const span = (a, b) => {
    const va = vertices[a], vb = vertices[b];
    return Math.hypot(va[0] - vb[0], va[1] - vb[1], va[2] - vb[2]);
  };
  const dijkstra = (from) => {
    const dist = new Map([[from, 0]]);
    const via = new Map();
    const done = new Set();
    for (;;) {
      let node = null, best = Infinity;
      for (const [k, d] of dist) {
        if (!done.has(k) && d < best) { best = d; node = k; }
      }
      if (node === null) return { dist, via };
      done.add(node);
      for (const [next, edge] of adjacency.get(node) || []) {
        const d = best + span(node, next);
        if (d < (dist.has(next) ? dist.get(next) : Infinity)) {
          dist.set(next, d);
          via.set(next, [node, edge]);
        }
      }
    }
  };
  const backtrack = (via, from, to, into) => {
    let at = to;
    while (at !== from && via.has(at)) {
      const [previous, edge] = via.get(at);
      into.add(edge);
      at = previous;
    }
  };

  const supports = new Set(bundle.supports || []);
  const principal = new Set();
  for (const tips of tipsByTree.values()) {
    const nodes = [...new Set(tips.map(nearestVertex).filter((i) => i >= 0))];
    if (!nodes.length) continue;
    nodes.sort((a, b) => vertices[a][2] - vertices[b][2]);
    // Consecutive touch points, threaded along the net...
    for (let i = 1; i < nodes.length; i++) {
      const { via } = dijkstra(nodes[i - 1]);
      backtrack(via, nodes[i - 1], nodes[i], principal);
    }
    // ...and the walk on down from the lowest to this leg's springing.
    if (supports.size) {
      const { dist, via } = dijkstra(nodes[0]);
      let target = null, best = Infinity;
      for (const support of supports) {
        const d = dist.has(support) ? dist.get(support) : Infinity;
        if (d < best) { best = d; target = support; }
      }
      if (target !== null) backtrack(via, nodes[0], target, principal);
    }
  }
  return [...principal].map((index) => edges[index]);
}

function buildPrincipalBars() {
  const previous = state.objects.principal;
  if (previous) {
    scene.remove(previous);
    previous.geometry.dispose();
    if (!previous.userData.libraryMaterial) previous.material.dispose();
    state.objects.principal = null;
  }
  if (!state.bundle) return;
  const pairs = principalEdges();
  if (!pairs.length) return;
  // A square section comfortably over the wires' own diameter, so the
  // tube inside a principal bar never surfaces through its faces -- and
  // it keeps that margin if the Wire size slider grows the net. 64 mm
  // on his word ("increase the size by another 20mm" over the 44).
  const section = Math.max(0.064, 2.2 * state.wireRadius);
  const geometry = new THREE.BoxGeometry(section, 1, section);
  geometry.translate(0, 0.5, 0);
  const mesh = new THREE.InstancedMesh(
    geometry, materials.bar.clone(), pairs.length);
  mesh.material.transparent = true;
  writeInstancedSegments(mesh, pairs, state.bundle.analysis_mesh.vertices);
  mesh.castShadow = false;
  state.objects.principal = mesh;
  scene.add(mesh);
  // The library texture, asynchronously and only if this build is still
  // the one on screen when it lands.
  ensureLibraryMaterial(PRINCIPAL_SKIN).then((set) => {
    if (!set || state.objects.principal !== mesh) return;
    const worn = set.material.clone();
    worn.transparent = true;
    mesh.material.dispose();
    mesh.material = worn;
    mesh.userData.libraryMaterial = true;
    syncNetShadow(mesh);
    // A new coat, so it has to be handed the capture afresh.
    noteReflectionsChanged();
  });
  if (state.timeline) applySceneAtTime(state.timeline.t);
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
  for (const key of ["wires", "nodes", "principal"]) {
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
    // The inked outline is a child of its casting and owns its own
    // buffers; its MATERIAL is shared by every piece on the vault and
    // lives as long as the page, so it is not freed here.
    for (const child of segment.children) {
      if (child.geometry) child.geometry.dispose();
    }
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

// One bench.columns/1 solid into the columns group. It stamps the radius
// the exporter swept it along, which the act's animated members read so the
// two drawings of one set of columns are the same thickness, and its raw
// members feed the principal-line walk: their tree tips are where the
// columns meet the net.
function addColumnSolid(group, columnDocument) {
  if (typeof columnDocument.radius === "number" && columnDocument.radius > 0) {
    state.columnRadius = columnDocument.radius;
  }
  if (Array.isArray(columnDocument.members)) {
    state.columnMembers.push(...columnDocument.members);
  }
  const mesh = new THREE.Mesh(columnGeometryFrom(columnDocument), materials.steel);
  mesh.castShadow = mesh.receiveShadow = true;
  group.add(mesh);
}

async function loadColumns(names) {
  const group = new THREE.Group();
  for (const name of names) {
    try {
      addColumnSolid(group, await fetchJson("/api/columns/" + encodeURIComponent(name)));
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
  state.columnMembers = [];
  // ONE FORMAT (Param, 2026-09-15): the formwork document carries its own
  // column solid, served as columns.solid, and that is what Formwork and
  // Both draw. A separate columns file stands in only for a study
  // exported before the export stopped writing one.
  const ownSolid = state.formwork && state.formwork.columns
    && state.formwork.columns.solid;
  if (ownSolid) {
    state.objects.columns = new THREE.Group();
    try {
      addColumnSolid(state.objects.columns, ownSolid);
    } catch (error) {
      showBanner("The formwork's columns failed to draw: " + error.message, "error");
    }
    scene.add(state.objects.columns);
  } else if (names.length) {
    state.objects.columns = await loadColumns(names);
    scene.add(state.objects.columns);
  }
  // The principal lines are DEFINED by where these columns touch the
  // net, so they are rebuilt whenever the columns are.
  buildPrincipalBars();
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
  buildPrincipalBars();

  rebuildGround();

  applyCut(preserve);
  buildLayerToggles();
  updateVectorLayers();
  updateMaterialControls();
  restoreProps();
  pullServerLayout();
  updateHud();
  // The weight line was written only when an appearance control was
  // touched, so a freshly loaded study showed an empty row until you
  // moved something -- exactly when you most want to know what the vault
  // is being weighed as.
  updateWeightNote();
  // LAST, and on every rebuild. A clipping plane lives on a material,
  // so every mesh this function builds arrives uncut: without this a
  // re-cut or a change of study quietly heals the section while the
  // control still reads Plane.
  applySection();
  // A rebuild replaces every caster in the scene.
  noteCastersChanged();
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
function collectScene(options) {
  // The session asks for everything BUT the props (sessionScene): encoding
  // a 100,000-prop field only to throw it away cost 20 ms on every camera
  // release.
  const withProps = !options || options.props !== false;
  const control = (id) => document.getElementById(id);
  return {
    sceneVersion: SCENE_VERSION,
    camera: { position: camera.position.toArray(), target: controls.target.toArray(),
      fov: perspectiveCamera.fov, frame: state.cameraAspect },
    showMode: state.showMode,
    // Never saved until 2026-09-14, so a scene came back in the last
    // picture's sky brightness, surface depth and machine.
    skyBrightness: state.skyBrightness,
    relief: state.relief,
    occlusion: state.occlusion,
    showMachine: state.showMachine !== false,
    environmentMode: state.environmentMode,
    weatherPreset: state.weatherPreset,
    atmosphere: { ...state.atmosphere },
    wind: { ...state.wind },
    backgroundTone: +control("background-tone").value,
    brightness: state.brightness,
    contrast: state.contrast,
    outline: state.outline,
    lamp: { lumens: state.lampLumens, kelvin: state.lampKelvin,
            tint: state.lampTint, invisible: state.lampInvisible,
            spot: Object.assign({}, state.spot) },
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
      intensity: lightBase.sun,     // before the dial, which is its own field
      intensityOverride: state.sunIntensityOverride,
    },
    // WHERE and WHEN, saved beside the angles the two of them produce.
    // The angles alone were never enough to reproduce a picture: reopen
    // a June noon in December and the numbers restore while the reason
    // for them is gone.
    // Which drawing convention the scene was composed in. A plan saved
    // and reopened as a perspective is a different image entirely, and
    // the camera position alone cannot say which was meant.
    projection: state.projection,
    cameraView: state.cameraView,
    // The cut travels with the scene. A sectioned plate reopened whole
    // is a different drawing, and the camera alone cannot say which
    // was meant.
    section: { ...state.section },
    orthoHeight: orthoFrameHeight,
    orthoZoom: orthographicCamera.zoom,
    site: {
      latitude: SUN_SITE.latitude,
      longitude: SUN_SITE.longitude,
      northOffset: SUN_SITE.northOffset,
      day: isoDay(sunDay()),
      minutes: state.sunMinutes,
    },
    dayCycle: {
      seconds: state.dayCycle.seconds,
      peakElevation: state.dayCycle.peakElevation,
      record: state.dayCycle.record,
    },
    ground: { preset: state.groundPreset, radius: state.groundRadius,
      scaleX: state.ground.scaleX, scaleY: state.ground.scaleY,
      relief: state.ground.relief, offset: state.ground.offset.slice(),
      rotation: state.ground.rotation,
      breakup: state.ground.breakup, seed: state.ground.seed.slice() },
    // Rows, not objects: see "the layout, and where it is kept". A scene
    // of a 25,000-prop field was five megabytes as objects, over the
    // server's four-megabyte scene limit.
    props: withProps ? encodeProps(state.props) : undefined,
    propLayers: withProps ? state.propLayers.map((layer) => ({
      id: layer.id, name: layer.name, visible: layer.visible })) : undefined,
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
  // COMPLETED BEFORE IT IS READ (scene_defaults.js): a setting the scene
  // does not carry is the studio's own default, never the last picture's.
  const scene_ = completeScene(record.state);
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
    if (Array.isArray(scene_.ground.seed)) state.ground.seed = scene_.ground.seed.slice(0, 2);
    // Through the setter, so the checkbox and the material's own program
    // follow a restored scene rather than showing the last one's answer.
    setGroundBreakup(!!scene_.ground.breakup);
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

  // loadStudy just wrote THIS DEVICE's per-material appearance memory over
  // the scene's own look (restoreAppearance runs on its way in) -- which
  // is why a scene restored on another device came back with the right
  // sky and the wrong skin and floor (Param's report). The scene is the
  // authority: its appearance goes back on top, the library skin and
  // floor it names are loaded before the tail's rebuild repaints, and
  // the device memory follows the screen from here on.
  if (scene_.appearance) {
    state.appearance = Object.assign({}, scene_.appearance);
    if (isLibraryKey(state.appearance.skin)
        && !libraryCache.has(state.appearance.skin)) {
      await ensureLibraryMaterial(state.appearance.skin);
    }
    persistAppearance();
  }
  if (scene_.ground && scene_.ground.preset) {
    await loadGroundMaterial(scene_.ground.preset);
  }

  // Props: cleared and replaced rather than merged, because a scene is a
  // whole picture. placeProp with save=false keeps the per-study layout in
  // localStorage untouched until the user moves one themselves.
  // Either shape a scene has held: a list of objects, or rows.
  const sceneProps = decodeProps(scene_.props);
  if (sceneProps) {
    // The scene owns the props now: a layout still arriving from the
    // server, or a model re-run the study's own restore left waiting, must
    // not put the study's field back over it.
    propsGeneration += 1;
    propsAwaitingLibrary = false;
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
    await Promise.all([...new Set(sceneProps.map((entry) => entry.type))]
      .filter((type) => propLibraryEntry(type))
      .map((type) => ensurePropTemplate(type)));
    for (const entry of sceneProps) {
      if (!knownPropType(entry.type)) continue;
      const record = placeProp(entry.type, +entry.x || 0, +entry.y || 0,
        +entry.rotation || 0, false, +entry.scale || 1, +entry.z || 0,
        +entry.rotX || 0, +entry.rotY || 0);
      if (Array.isArray(entry.size) && entry.size.length === 3) {
        record.size = entry.size.map(Number);
        applyPropSize(record);
      }
      record.layer = +entry.layer || 1;
      if (entry.scatter) record.scatter = +entry.scatter;
      adoptLampSettings(record, entry);
    }
    settleRestoredScatters(layoutKnowsScatters(scene_.props));
    applyLayerVisibility();
  }

  // The environment owns background, fog, exposure base and the sun's
  // defaults, so it goes before the sun and before the grade.
  if (scene_.environmentMode) state.environmentMode = scene_.environmentMode;
  if (scene_.weatherPreset) state.weatherPreset = scene_.weatherPreset;
  control("environment-mode").value = state.environmentMode;
  control("weather-preset").value = state.weatherPreset;
  // A scene saved before the atmosphere existed carries none, and comes
  // back as None rather than inheriting whatever fog was showing.
  state.atmosphere = adoptAtmosphere(scene_.atmosphere);
  control("atmosphere-preset").value = state.atmosphere.preset;
  syncAtmosphereControls();
  // A scene from before the wind is a calm.
  state.wind = adoptWind(scene_.wind);
  syncWindControls();
  applyWindState();
  if (typeof scene_.backgroundTone === "number") {
    control("background-tone").value = scene_.backgroundTone;
    control("background-tone-value").textContent = Math.round(scene_.backgroundTone);
  }
  // The sky's own brightness, applied with the sun below.
  state.skyBrightness = scene_.skyBrightness;
  control("sky-brightness").value = Math.round(scene_.skyBrightness * 100);
  control("sky-brightness-value").textContent = Math.round(scene_.skyBrightness * 100);
  paintScrub(control("sky-brightness"));
  // The skin's surface depth and crevice shading.
  state.relief = scene_.relief;
  state.occlusion = scene_.occlusion;
  control("material-relief").value = scene_.relief;
  control("material-occlusion").value = scene_.occlusion;
  applySurfaceControls();
  // The machine, shown or put away.
  state.showMachine = scene_.showMachine;
  control("show-machine").checked = scene_.showMachine;
  // The day cycle's length, its peak and whether a take carries it.
  state.dayCycle.seconds = scene_.dayCycle.seconds;
  state.dayCycle.peakElevation = scene_.dayCycle.peakElevation;
  state.dayCycle.record = scene_.dayCycle.record;
  control("day-cycle-seconds").value = scene_.dayCycle.seconds;
  control("day-cycle-record").checked = scene_.dayCycle.record;
  if (typeof scene_.brightness === "number") {
    state.brightness = scene_.brightness; control("brightness").value = scene_.brightness;
  }
  if (typeof scene_.contrast === "number") {
    state.contrast = scene_.contrast; control("contrast").value = scene_.contrast;
    paintGradeReadings();
  }
  // After loadStudy, which rebuilt the pieces: the ribbons this turns on
  // have to exist before they can be shown.
  if (typeof scene_.outline === "number") {
    state.outline = scene_.outline;
    control("outline-width").value = scene_.outline;
    applyOutline();
  }
  // Older scenes carry "glow", the removed halo dial: ignored on purpose.
  if (scene_.lamp) {
    if (typeof scene_.lamp.lumens === "number") state.lampLumens = scene_.lamp.lumens;
    if (typeof scene_.lamp.kelvin === "number") state.lampKelvin = scene_.lamp.kelvin;
    if (typeof scene_.lamp.tint === "string") state.lampTint = scene_.lamp.tint;
    if (typeof scene_.lamp.invisible === "boolean") {
      state.lampInvisible = scene_.lamp.invisible;
    }
    // A scene saved before the spot existed carries no beam, and the
    // drawer keeps the defaults rather than taking an undefined one.
    if (scene_.lamp.spot) {
      Object.assign(state.spot, scene_.lamp.spot);
    }
  }
  syncLightControls();
  const hdri = scene_.hdri || {};
  if (hdri.projection) {
    state.hdriProjection = hdri.projection; control("hdri-projection").value = hdri.projection;
  }
  // The readings follow the sliders on restore as well, or a scene comes
  // back showing the last scene's numbers beside the right dials.
  for (const [key, id] of [["scale", "hdri-scale"], ["height", "hdri-height"],
                           ["rotation", "hdri-rotation"]]) {
    if (typeof hdri[key] === "number") {
      state["hdri" + key[0].toUpperCase() + key.slice(1)] = hdri[key];
      control(id).value = hdri[key];
      paintScrub(control(id));
      // The dial's own reading, by the id pairing every dial keeps.
      const reading = document.getElementById(id + "-value");
      if (reading) {
        reading.textContent = key === "height"
          ? hdri[key].toFixed(1) : String(Math.round(hdri[key]));
      }
    }
  }
  if (state.environmentMode === "hdri" && hdri.name && state.hdriName !== hdri.name) {
    // loadHdri stamps the sun sliders from the photograph, which is why the
    // sun is restored after it, below.
    await refreshHdriList(hdri.name);
    await loadHdri(hdri.name);
    // loadHdri swallows its own failures (and banners the raw cause), so
    // the one sign the sky did not land is the name not being stamped.
    // Say what it means for the SCENE: the sky file left the folder, and
    // everything else still restored (Param's live case: a scene saved
    // under evening_meadow after that file moved out of the sky folder).
    if (state.hdriName !== hdri.name) {
      showBanner('This scene\'s sky "' + hdri.name + '" is not in the sky '
        + "folder any more; the rest of the scene is restored under the "
        + "current sky.", "error");
    }
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
  if (typeof sunState.intensity === "number") lightBase.sun = sunState.intensity;
  applySunFromSliders();
  applySkyBrightness();

  // The site AFTER the angles, and only when the scene carries one. A
  // scene saved before this existed holds angles and no place, and
  // re-solving those against today's date at London would move its sun
  // out from under a camera that was framed around it. Where the scene
  // does carry a site, the instant IS the sun and the saved angles are
  // simply what applySunFromTime recomputes.
  const siteState = scene_.site;
  if (siteState && typeof siteState.latitude === "number") {
    SUN_SITE.latitude = siteState.latitude;
    SUN_SITE.longitude = typeof siteState.longitude === "number"
      ? siteState.longitude : SUN_SITE.longitude;
    SUN_SITE.northOffset = typeof siteState.northOffset === "number"
      ? siteState.northOffset : 0;
    const day = dayFromIso(siteState.day);
    if (day) state.sunDay = day;
    if (typeof siteState.minutes === "number") {
      state.sunMinutes = siteState.minutes;
    }
    syncSiteControls();
    applySunFromTime();
  }
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
    perspectiveCamera.fov = view.fov;
    perspectiveCamera.updateProjectionMatrix();
  }
  // The projection BEFORE the position, so the eye lands in the camera
  // that is going to use it. Restoring the place first and swapping
  // afterwards would frame the ortho view off the old distance.
  //
  // AND THE SAVED FRAMING AFTER THE SWITCH, which is the whole of a bug
  // this shipped with. setProjection's orthographic branch re-seeds
  // orthoFrameHeight from perspectiveFrameHeight() and sets zoom to 1,
  // because that is what makes a live toggle seamless. On a restore that
  // is exactly wrong: it threw away the numbers written two lines above
  // and re-derived them from a perspective eye that applyScene has not
  // even repositioned yet. So the pair is written first, for
  // setProjection's PERSPECTIVE branch which reads both to place the
  // eye, and written again afterwards to survive the orthographic one.
  if (typeof scene_.orthoHeight === "number") orthoFrameHeight = scene_.orthoHeight;
  if (typeof scene_.orthoZoom === "number") orthographicCamera.zoom = scene_.orthoZoom;
  if (scene_.projection === "orthographic" || scene_.projection === "perspective") {
    setProjection(scene_.projection);
    if (typeof scene_.orthoHeight === "number") orthoFrameHeight = scene_.orthoHeight;
    if (typeof scene_.orthoZoom === "number") {
      orthographicCamera.zoom = scene_.orthoZoom;
      orthographicCamera.updateProjectionMatrix();
    }
    applyCameraFrustum(viewportAspect());
    paintScaleBar();
  }
  state.cameraView = scene_.cameraView || null;
  if (scene_.section && typeof scene_.section === "object") {
    Object.assign(state.section, scene_.section);
    applySection();
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
      study, state: sessionScene(), when: new Date().toISOString(),
    }));
  } catch (error) { /* a full or blocked store is not worth a banner */ }
}

// The session reopens the VIEW. The props come back from the study's own
// layout, which buildScene restores anyway; carrying them here as well
// wrote the whole field into browser storage a second time on every blur.
function sessionScene() {
  return collectScene({ props: false });
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
// The prop layout's waiting write goes first, on both (listeners run in
// the order they were added): a tab closed within the settle time of the
// last gesture would otherwise lose that gesture.
window.addEventListener("beforeunload", (event) => {
  flushProps();
  // A layout too big for the browser lives only on the server, so a PUT
  // still going when the tab closes is the last gesture lost: the browser
  // is asked to hold the page while one is.
  if ((layoutPutting || layoutPutQueue.size) && layoutOverQuota.size) {
    event.preventDefault();
    event.returnValue = "";
  }
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") flushProps();
});
window.addEventListener("beforeunload", rememberSession);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") rememberSession();
});

async function refreshScenes() {
  const payload = await fetchJson("/api/scenes");
  state.scenes = payload.scenes || [];
  renderSceneList();
}

// How many times each scene has been updated this session. Its `saved`
// stamp is to the second, and two updates inside one second would
// otherwise ask for the same picture twice.
const sceneThumbnailTurns = new Map();

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
      // VERSIONED BY WHEN IT WAS SAVED. Param, 2026-09-14: "when i update a
      // scene we need to update the thumbnail too". The server did write
      // the new picture; the drawer asked for it at the same address, and
      // a browser hands back an image it already holds for an address
      // without asking again, so the old picture stayed on the tile.
      image.src = "/api/scenes/" + encodeURIComponent(row.id) + "/thumbnail?v="
        + encodeURIComponent(row.saved || "") + "-" + (sceneThumbnailTurns.get(row.id) || 0);
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
    // Update in place: the view on screen now, written over this scene,
    // keeping its name. Param: "a little refresh icon appears in the
    // bottom right corner of the thumbnail which allows me to update that
    // scene with what i have."
    //
    // It sits at the tile's BOTTOM right, diagonally opposite the delete
    // cross, so the destructive control and the one he will reach for
    // often can never be caught by the same slip of a click.
    const update = document.createElement("button");
    update.className = "scene-update";
    update.textContent = "\u27f3";        // the reload glyph, needing no legend
    update.title = "Update this scene with the view on screen now";
    update.addEventListener("click", async (event) => {
      // The tile beneath restores the scene; this must not do both.
      event.stopPropagation();
      if (!state.bundle) {
        showBanner("Load a study before updating a scene", "error");
        return;
      }
      const response = await fetch(
        "/api/scenes/" + encodeURIComponent(row.id),
        { method: "PUT", headers: { "content-type": "application/json" },
          body: JSON.stringify({
            study: document.getElementById("study-select").value,
            state: collectScene(), thumbnail: captureThumbnail() }) });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        // 405 does not mean anything is wrong with the scene: it means the
        // ROUTE is missing from the running server. The studio serves its
        // JavaScript fresh from disk on every load, but the Python process
        // keeps the routes it started with, so a NEW route reaches the
        // browser long before it reaches the server. "Method Not Allowed"
        // is the least useful thing that could be said about that.
        showBanner(response.status === 405
          ? "Scene not updated: this studio server was started before the "
            + "update route existed. Restart it and this will work."
          : "Scene not updated: " + (body.detail || response.status), "error");
        return;
      }
      logStudio("updated scene " + row.name);
      sceneThumbnailTurns.set(row.id, (sceneThumbnailTurns.get(row.id) || 0) + 1);
      await refreshScenes();
    });
    const holder = document.createElement("div");
    // Named, so the pip can be revealed by hovering ANYWHERE on the tile.
    // A sibling selector cannot do it: the delete cross sits between the
    // tile and the pip in the DOM, so "+" never matches.
    holder.className = "scene-holder";
    holder.style.position = "relative";
    holder.appendChild(tile);
    holder.appendChild(remove);
    holder.appendChild(update);
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

// ---------- a new scene ----------
// Param, 2026-09-15: "can we add a new scene button to scene tile, where it
// just gives us a blank scene to start from, not deleting any other saved
// scenes".
//
// A BLANK SCENE IS A SCENE LIKE ANY OTHER. It goes through applyScene, the
// one road a picture is restored by, carrying no props and nothing else, so
// completeScene gives every setting the studio's own default: exactly what
// an old scene that never saved a setting gets. What any scene may leave
// unsaid (SCENE_LEFT_AS_THEY_ARE) stays as it is on screen: the vault with
// its cut and its skin, where the camera stands, and the sun's place and
// hour. The atmosphere and the wind take their adopters' defaults, which
// are none and the light breeze.
//
// NOTHING SAVED IS TOUCHED. No request here reaches /api/scenes. The
// study's working layout is written empty, as Clear writes it, so a reload
// opens on the blank start rather than on the field it replaced; a saved
// scene keeps its own props inside itself. And the picture it replaced is
// one undo away.
function blankScene() {
  return { props: [], propLayers: [] };
}

let startingNewScene = false;

async function startNewScene() {
  if (!state.bundle) {
    showBanner("Load a study before starting a new scene", "error");
    return false;
  }
  // A second press while the first is still rebuilding would take the
  // half-built blank as the picture to undo back to.
  if (startingNewScene) return false;
  startingNewScene = true;
  try {
    const before = collectScene();
    const study = document.getElementById("study-select").value;
    const started = await applyScene({ name: "a blank start", study, state: blankScene() });
    if (!started) return false;
    saveProps();
    refreshLayersShelf();
    // AFTER the apply: loadStudy clears the history on its way in, and an
    // entry pushed first would be gone before anyone could press Ctrl+Z.
    pushUndo("new scene", async () => {
      await applyScene({ name: "the scene before", study, state: before });
      saveProps();
      refreshLayersShelf();
    }, startNewScene);
    logStudio("new scene: a blank start around " + study + "; no saved scene was touched");
    return true;
  } finally {
    startingNewScene = false;
  }
}

document.getElementById("scene-new").addEventListener("click", startNewScene);

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

// A handful of somewheres a vault might stand, not a gazetteer. Anything
// not on the list is typed straight into the two readings, and the select
// then says Custom rather than snapping to whichever of these is nearest.
// Zurich earns its place because the BRG corpus this work argues with was
// written there, and a figure reproducing one of theirs should be able to
// stand under their sun.
const SUN_PLACES = [
  { name: "London", latitude: 51.507, longitude: -0.128 },
  { name: "Cardiff", latitude: 51.481, longitude: -3.179 },
  { name: "Edinburgh", latitude: 55.953, longitude: -3.188 },
  { name: "Zurich", latitude: 47.377, longitude: 8.542 },
  { name: "Barcelona", latitude: 41.385, longitude: 2.173 },
  { name: "Cairo", latitude: 30.044, longitude: 31.236 },
  { name: "New York", latitude: 40.713, longitude: -74.006 },
  { name: "Sydney", latitude: -33.869, longitude: 151.209 },
];

// UTC parts, because minutesToDate builds the instant out of UTC parts.
// Reading the local ones here would disagree by a day either side of
// midnight, and the sun would jump a date the first time the box was
// touched without anyone changing it.
function isoDay(day) {
  const pad = (n) => String(n).padStart(2, "0");
  return day.getUTCFullYear() + "-" + pad(day.getUTCMonth() + 1)
    + "-" + pad(day.getUTCDate());
}

function dayFromIso(text) {
  const parts = String(text || "").split("-").map(Number);
  if (parts.length !== 3 || !parts.every(Number.isFinite)) return null;
  return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
}

// One writer for the whole block, so the dials, their readings, the date
// box and the place name cannot come to disagree about where the studio
// thinks it is standing.
function syncSiteControls() {
  const write = (id, value, reading) => {
    const input = document.getElementById(id);
    if (!input) return;
    input.value = value;
    paintScrub(input);
    const span = document.getElementById(id + "-value");
    if (span) span.textContent = reading;
  };
  write("site-latitude", SUN_SITE.latitude, SUN_SITE.latitude.toFixed(2));
  write("site-longitude", SUN_SITE.longitude, SUN_SITE.longitude.toFixed(2));
  write("site-north", SUN_SITE.northOffset, Math.round(SUN_SITE.northOffset));
  const date = document.getElementById("site-date");
  if (date) date.value = isoDay(sunDay());
  const select = document.getElementById("site-place");
  if (select) {
    // Half of the dials' own step, so a place stays selected while the
    // reading it wrote is still on screen.
    const here = SUN_PLACES.find((place) =>
      Math.abs(place.latitude - SUN_SITE.latitude) < 0.005
      && Math.abs(place.longitude - SUN_SITE.longitude) < 0.005);
    select.value = here ? here.name : "";
  }
}

// Everything that moves the site comes through here. The sun has to be
// re-solved, and a change that moved a dial without re-solving would
// leave a correct number over a stale shadow, which is the one failure
// mode nobody spots in a still.
function setSite(patch) {
  Object.assign(SUN_SITE, patch);
  syncSiteControls();
  applySunFromTime();
}

function sunDay() {
  // The day the sun is being placed on. A date control can be added later;
  // for now it is today, taken once at load so a take is not interrupted by
  // midnight.
  return state.sunDay;
}

// THE CLOCK IS LOCAL TO THE SITE. The rule itself lives in fields.js,
// beside the solar maths and reachable by the node harness that tests
// it; these two are only the studio's way of saying "at this site".
function siteUtcOffsetMinutes() {
  return utcOffsetMinutes(SUN_SITE.longitude);
}

function minutesToDate(minutes) {
  const day = sunDay();
  return new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(),
    day.getUTCDate(), 0, 0, 0)
    + Math.round((minutes - siteUtcOffsetMinutes()) * 60000));
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
  // The sun by day and the moon by night. The ramp runs out at the
  // horizon, and the floor that once kept "a night scene lit by something"
  // is gone: what lights a night is the moon, stood opposite the sun the
  // way a full moon is, cool, and five per cent as strong.
  const moon = light.strength <= 0;
  const colour = new THREE.Color(moon ? MOON_COLOUR : light.colour);
  if (!state.sunColourOverride) sun.color.copy(colour);
  document.getElementById("sun-colour").value = "#" + colour.getHexString();
  if (state.sunIntensityOverride === null) {
    lightBase.sun = moon ? FULL_SUN * MOON_STRENGTH : FULL_SUN * light.strength;
  }
  applySunAt(sceneAngle, Math.max(-2, placed.elevation));
  if (moon) {
    // The sky keeps the true sun, under the horizon, so it is dark; only
    // the light stands where the moon does, opposite, and never lower
    // than twelve degrees or its shadows would run off the ground.
    const az = THREE.MathUtils.degToRad(sceneAngle + 180);
    const el = THREE.MathUtils.degToRad(Math.max(12, Math.min(60, -placed.elevation)));
    sun.position.set(SUN_DISTANCE * Math.cos(el) * Math.cos(az),
      SUN_DISTANCE * Math.cos(el) * Math.sin(az), SUN_DISTANCE * Math.sin(el));
    // The two-degree clamp above keeps a dusk's glow. Past six under, the
    // sky's sun goes to its true depth: from a camera twelve metres up
    // the clamped disc stood above the far edge of the ground, a warm
    // sun in the middle of the night (photographed before this went in).
    if (placed.elevation < -6) {
      const deep = THREE.MathUtils.degToRad(placed.elevation);
      const along = THREE.MathUtils.degToRad(sceneAngle);
      sky.material.uniforms.sunPosition.value.set(
        Math.cos(deep) * Math.cos(along), Math.cos(deep) * Math.sin(along), Math.sin(deep));
    }
  }
  followSkyHorizon();
  applySkyBrightness();
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
  // The zone is stated whenever it is not zero, because a clock that
  // silently means something other than UTC is how the Sydney fault got
  // in: the number looked ordinary and was eleven hours out.
  const offset = siteUtcOffsetMinutes() / 60;
  document.getElementById("sun-time").textContent =
    String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0")
    + (offset ? " UTC" + (offset > 0 ? "+" : "") + offset : "");
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
  "Sky": () => Math.round(state.skyBrightness * 100) + "%",
  "Atmosphere": () => {
    const select = document.getElementById("atmosphere-preset");
    const label = select.options[select.selectedIndex];
    const rays = state.atmosphere.shafts ? ", rays " + state.atmosphere.shafts + "%" : "";
    return (label ? label.textContent : "") + rays;
  },
  "Wind": () => state.wind.strength
    ? state.wind.strength + "% from " + Math.round(state.wind.from) + "\u00b0" : "calm",
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
  // The graphs' inks are read at draw time, so they are drawn again.
  invalidateLiveGraphs();
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
// Raised from 6 when the machine arrived: it wears FIVE library sets at
// once (two aluminium frames share one), and with the vault's skin and a
// ground preset also resident, a limit of six evicted -- and DISPOSED --
// a texture that live machine meshes still pointed at. Twelve sets is
// about 250 MB of video memory, which this machine has in abundance.
const LIBRARY_CACHE_LIMIT = 12;

// Keys something on screen is still WEARING. Eviction skips these: the
// cache is least-recently-used, and "least recently loaded" is not the
// same as "no longer needed" once a build wears five sets at once.
const libraryPins = new Set();
const libraryCache = new Map();
const libraryLoads = new Map();     // key -> in-flight promise, so a double
                                    // click does not fetch the set twice

// The boot fetch of the material LIST, so anything needing a library
// material can wait for it. It is deliberately not awaited at boot -- the
// studio is usable before it arrives -- and that is a race the machine
// can lose: buildMachine runs on study open, and a name looked up against
// a list still in flight misses, returns null, and gives up FOR GOOD. It
// is a race, so which parts end up skinned varies between reloads, which
// is what "the color scheme changed again" looks like from the outside.
let materialLibraryReady = null;

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
  // A key that is real but not yet LISTED must wait, not fail: an empty
  // list means the boot fetch is still in flight, not that the folder is
  // empty. Re-checked after the wait, since another caller may have
  // started the same load while this one waited.
  if (!state.materialLibrary.length && materialLibraryReady) {
    await materialLibraryReady;
    if (libraryCache.has(key)) return libraryCache.get(key);
    if (libraryLoads.has(key)) return libraryLoads.get(key);
  }
  const entry = libraryEntry(key);
  if (!entry) {
    // Said out loud. A silent null here is what let a whole machine wear
    // the fallback grey through two rounds of fixes without a word.
    logStudio("material " + key + " is not in the library folder");
    return null;
  }
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
    // Walked rather than looped on the head: a pinned or protected key at
    // the head must be STEPPED OVER, not treated as a reason to stop, or
    // one pin would keep the cache growing without bound.
    for (const oldest of [...libraryCache.keys()]) {
      if (libraryCache.size <= LIBRARY_CACHE_LIMIT) break;
      if (oldest === key || oldest === state.appearance.skin) continue;
      if (libraryPins.has(oldest)) continue;
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

function structuralDensity() {
  const structural = document.getElementById("material-select").value;
  return STRUCTURAL_DENSITIES[structural] || 2400;
}

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
  return structuralDensity();
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
// Whose density the vault is being weighed by, in words: the library
// skin's own label when it is wearing one, else the structural material
// the select names.
function weighedAsLabel() {
  const skin = state.appearance.skin;
  if (isLibraryKey(skin)) {
    const entry = libraryEntry(skin);
    if (entry && entry.label) return entry.label;
  }
  const select = document.getElementById("material-select");
  const option = select && select.options[select.selectedIndex];
  return option ? option.textContent : "the structural material";
}

function updateWeightNote() {
  const note = document.getElementById("weight-note");
  if (!note) return;
  const density = skinDensity();
  const thickness = state.thickness;
  const kgPerM2 = density * thickness;
  const kNPerM2 = kgPerM2 * 9.80665 / 1000;
  // Param: "just showing how much density and weight is added and what
  // material. Nothing too detailed." So: the name first, because that is
  // what he changed to get here, then the density it brings and the load
  // that follows. One line, and the tooltip carries the rest.
  note.textContent = weighedAsLabel() + ": " + Math.round(density)
    + " kg/m3 x " + Math.round(thickness * 1000) + " mm = "
    + kNPerM2.toFixed(2) + " kN/m2 (" + Math.round(kgPerM2) + " kg/m2)";
  note.title = Math.abs(density - structuralDensity()) > 1
    ? "The skin's own density, and the weight the analysis is run at."
    : "The structural material's density, and the weight the analysis "
      + "is run at.";
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
  // The restore above set the selects without change events; the faces
  // that read them need telling (his floor wore pebbles while a picker,
  // since removed, still said Dark studio).
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
  // The skin, floor and sky pickers are gone (2026-09-14): each only
  // opened a shelf tile, which is where those are chosen. What remains
  // are the pickers whose grids are their own.
  for (const [trigger, holder, select, openInstead] of [
    ["material-picker", "material-tiles", "material-select"],
    ["weather-picker", "weather-tiles", "weather-preset"],
    ["atmosphere-picker", "atmosphere-tiles", "atmosphere-preset"],
  ]) {
    wirePicker(trigger, holder, select,
      (swatch, value) => borrowTileImage(swatch, holder, value), openInstead);
  }
  // The weather and the atmosphere share the drawer's row: opening one
  // puts the other away, so the drawer never carries both grids at once.
  for (const [trigger, holder, other] of [
    ["weather-picker", "weather-tiles", "atmosphere-tiles"],
    ["atmosphere-picker", "atmosphere-tiles", "weather-tiles"],
  ]) {
    document.getElementById(trigger).addEventListener("click", () => {
      if (!document.getElementById(holder).classList.contains("hidden")) {
        closePicker(document.getElementById(other));
      }
    });
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
  const fov = Math.round(perspectiveCamera.fov);
  document.getElementById("camera-fov").value = fov;
  document.getElementById("camera-fov-value").textContent = fov;
  document.getElementById("camera-mm").textContent =
    lensMillimetres(perspectiveCamera.fov);
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

// ---------- projection ----------
// An orthographic camera is what turns a picture into a drawing: every
// bay of an arcade the same width on the page, a springing line straight
// rather than raked, and a measurable image. A perspective view argues
// how a vault feels; an orthographic one states what it is.
//
// How tall the frame is, in metres, at the orbit target. Zoom is left to
// OrbitControls, which dollies an orthographic camera by changing .zoom
// rather than the distance, so this is only the base the zoom divides.
let orthoFrameHeight = 20;

// The perspective camera's own frame height where the orbit target sits:
// h = 2 d tan(fov / 2). Switching on this number is what makes the two
// projections frame the same thing, so the toggle reads as a change of
// convention rather than a jump to somewhere else entirely.
function perspectiveFrameHeight() {
  const distance = perspectiveCamera.position.distanceTo(controls.target);
  return 2 * distance * Math.tan(perspectiveCamera.fov * Math.PI / 360);
}

// Both resize paths funnel here. An orthographic camera has no .aspect:
// its shape is four planes, so a resize that wrote .aspect and called
// updateProjectionMatrix would silently do nothing at all and leave the
// drawing stretched.
function applyCameraFrustum(aspect) {
  if (camera.isOrthographicCamera) {
    const half = orthoFrameHeight / 2;
    camera.top = half;
    camera.bottom = -half;
    camera.right = half * aspect;
    camera.left = -half * aspect;
  } else {
    camera.aspect = aspect;
  }
  camera.updateProjectionMatrix();
}

function viewportAspect() {
  const w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
  return w / h;
}

function setProjection(kind) {
  const wanted = kind === "orthographic" ? orthographicCamera : perspectiveCamera;
  if (wanted === camera) return;
  if (wanted.isOrthographicCamera) {
    orthoFrameHeight = perspectiveFrameHeight();
    wanted.zoom = 1;
  } else {
    // Coming back the other way, the ortho zoom is what decided how big
    // things looked, so the perspective camera is placed at the distance
    // that frames the same height. Without this, zooming in orthographic
    // and switching back throws the eye across the room.
    const visible = orthoFrameHeight / (orthographicCamera.zoom || 1);
    const distance = visible
      / (2 * Math.tan(perspectiveCamera.fov * Math.PI / 360));
    const back = new THREE.Vector3()
      .subVectors(orthographicCamera.position, controls.target);
    if (back.lengthSq() < 1e-9) back.set(0, -1, 0);
    wanted.position.copy(controls.target).add(back.setLength(distance));
  }
  if (wanted.isOrthographicCamera) wanted.position.copy(camera.position);
  wanted.up.copy(camera.up);
  wanted.quaternion.copy(camera.quaternion);
  camera = wanted;
  renderPass.camera = camera;
  // OrbitControls reads .object on every update, so rebinding it is the
  // whole of handing the mouse over.
  controls.object = camera;
  controls.update();
  state.projection = kind;
  // A plan or an elevation is a drawing: the atmosphere clears from it,
  // and comes back with the perspective.
  applyAtmosphere();
  applyCameraFrustum(viewportAspect());
  clampCameraAboveFloor();
  paintProjectionControls();
  paintScaleBar();
  paintFrameWidth();
  rememberSession();
}

// The six standing places a drawing is made from. Distance is kept, so a
// snap turns the model rather than walking away from it. Top looks down
// the -Z axis, where the camera's own up would be parallel to the view
// and the matrix degenerate, so up becomes +Y there: plan north up.
const CAMERA_VIEWS = {
  front: [0, -1, 0], back: [0, 1, 0], left: [-1, 0, 0],
  right: [1, 0, 0], top: [0, 0, 1],
  iso: [1, -1, 0.8],
};

function snapCameraTo(name) {
  const axis = CAMERA_VIEWS[name];
  if (!axis) return;
  const distance = camera.position.distanceTo(controls.target) || 30;
  const direction = new THREE.Vector3(...axis).normalize();
  camera.up.set(0, 0, 1);
  if (name === "top") camera.up.set(0, 1, 0);
  camera.position.copy(controls.target)
    .add(direction.multiplyScalar(distance));
  // A plan looking straight down would otherwise be clamped up out of
  // its own view by the floor guard, which exists for the orbit and not
  // for a snapped elevation.
  if (name !== "top") clampCameraAboveFloor();
  controls.update();
  state.cameraView = name;
  paintProjectionControls();
  paintScaleBar();
  rememberSession();
}

// A scale bar means something only in an orthographic view, where one
// metre is the same number of pixels everywhere in the frame. In
// perspective it would be a lie that looked like a measurement, so it is
// hidden rather than approximated.
const SCALE_STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500];

// A frame's width in metres is the one reading a parallel projection can
// honestly offer where a focal length cannot mean anything. Height is
// what the frustum is built from, so the width is that times the aspect,
// and it moves when the viewport or the chosen frame ratio does.
function frameWidthMetres() {
  return (orthoFrameHeight / (orthographicCamera.zoom || 1)) * viewportAspect();
}

// Typing a width writes ZOOM, never orthoFrameHeight. Zoom is precisely
// the quantity OrbitControls owns for an orthographic camera, so the
// next wheel notch multiplies from where the typing left off instead of
// fighting it; and applyCameraFrustum builds the four planes from
// orthoFrameHeight alone, so writing zoom needs no frustum rewrite while
// writing the height would need one every time.
function setFrameWidthMetres(metres) {
  const wanted = Math.max(0.01, +metres || 0);
  orthographicCamera.zoom = (orthoFrameHeight * viewportAspect()) / wanted;
  orthographicCamera.updateProjectionMatrix();
  paintFrameWidth();
  paintScaleBar();
}

// One painter, which also owns the row swap. Keyed on the camera itself
// rather than on state.projection, so it follows the binding and not a
// remembered word.
function paintFrameWidth() {
  const lens = document.getElementById("camera-fov-row");
  const width = document.getElementById("camera-width-row");
  if (!lens || !width) return;
  const ortho = !!camera.isOrthographicCamera;
  lens.classList.toggle("hidden", ortho);
  width.classList.toggle("hidden", !ortho);
  if (!ortho) return;
  const metres = frameWidthMetres();
  const dial = document.getElementById("camera-width");
  if (dial) {
    // The travel comes from the model, as the section offset's does: a
    // fixed half-metre to two hundred runs a 23 m vault off the bottom
    // of its own scale.
    const box = new THREE.Box3();
    if (state.objects.shell) box.setFromObject(state.objects.shell);
    const span = box.isEmpty() ? 40
      : Math.max(1, box.getSize(new THREE.Vector3()).length());
    dial.min = (span / 20).toFixed(2);
    dial.max = (span * 3).toFixed(2);
    dial.value = Math.min(+dial.max, Math.max(+dial.min, metres));
    paintScrub(dial);
  }
  const reading = document.getElementById("camera-width-value");
  if (reading) reading.textContent = metres.toFixed(2);
}

function paintScaleBar() {
  const bar = document.getElementById("scale-bar");
  if (!bar) return;
  if (!camera.isOrthographicCamera) { bar.hidden = true; return; }
  const pixels = canvas.clientHeight || 1;
  const metresPerPixel = (orthoFrameHeight / (camera.zoom || 1)) / pixels;
  // Aim at a fifth of the frame, then take the nearest round length at or
  // under it: a bar reading "37 m" is a number, not a scale.
  const target = metresPerPixel * (canvas.clientWidth || 1) * 0.2;
  let metres = SCALE_STEPS[0];
  for (const step of SCALE_STEPS) if (step <= target) metres = step;
  bar.hidden = false;
  bar.style.width = Math.round(metres / metresPerPixel) + "px";
  bar.textContent = metres < 1 ? Math.round(metres * 1000) + " mm"
    : metres + " m";
}

// ---------- the print-resolution still ----------
// An A3 plate at 300 dpi is 4961 x 3508 and the recorder stops at 1920,
// so every figure in the thesis has gone to press as an upscale. A
// 1500-voussoir vault at 1920 wide gives each piece about forty pixels,
// which is not enough to see a joint.
//
// TILED, because a 4961 px canvas is not a thing to ask a tab to hold in
// one piece: the drawing buffer alone is 70 MB before the composer's
// half-float target and its 4x MSAA are counted, and the ceiling is the
// driver's, not ours. camera.setViewOffset gives the sub-frustum for one
// tile of a larger frame, on both projections
// (three.core.js:46515 documents exactly this use), so each tile is an
// ordinary render of the same scene through a narrowed camera.
//
// Two traps the plan warned of are NOT traps here, both measured before
// this was written. The inked ribbon's width is a world-space offset in
// metres applied in the vertex shader, so it gains pixels on a bigger
// plate rather than thinning. And no pass in the composer reads a
// resolution: RenderPass, OutputPass and the grade are per-pixel, so
// grading a tile gives the same answer as grading the whole. Both
// become real the moment GTAO or bloom lands.
const STILL_TILE = 2048;

// Named for the page, because 4961 x 3508 means something and "8K" does
// not. Ratios are the paper's, so a plate composed at 4:3 and rendered
// at A3 would be letterboxed rather than stretched: the frame ratio is
// what decides shape, and these decide how many pixels it gets.
const STILL_SIZES = [
  { key: "2k", label: "2K", long: 2048 },
  { key: "4k", label: "4K", long: 3840 },
  { key: "a3-300", label: "A3", long: 4961 },
  { key: "a2-300", label: "A2", long: 7016 },
  { key: "8k", label: "8K", long: 7680 },
];

function stillFrame() {
  const size = STILL_SIZES.find((s) => s.key === state.stillSize)
    || STILL_SIZES[2];
  // The composed frame's own shape, so what is rendered is what was
  // framed. "fill" has no ratio of its own, so it takes the viewport's.
  const ratio = state.cameraAspect === "fill"
    ? (canvas.clientWidth || 16) / (canvas.clientHeight || 9)
    : +state.cameraAspect;
  const even = (n) => Math.max(2, 2 * Math.round(n / 2));
  return ratio >= 1
    ? { width: size.long, height: even(size.long / ratio) }
    : { width: even(size.long * ratio), height: size.long };
}

function paintStillReadout(text) {
  const line = document.getElementById("still-readout");
  if (line) line.textContent = text;
  // And on the cover, while one is up, so the wait says what it is doing.
  const cover = document.getElementById("still-cover-text");
  if (cover && document.body.classList.contains("stilling")) cover.textContent = text;
}

// ---------- a picture has no helpers in it ----------
// Param, 2026-09-13, over an 8K plate with an amber line across it: "we
// also must not have any object selection box, it always wants to be a
// clean still." The hover box stayed up because nothing clears it until
// the pointer moves, and a still is rendered with the pointer still. So
// every helper the studio draws over the scene is put away for a still
// and for a take, and each is put back exactly as it was afterwards.
function pictureHelpers() {
  return [propOutline, hoverBox, propGumball, scatterOutline, ...groupOutlines]
    .filter(Boolean);
}

function hideHelpersForPicture() {
  setHoveredProp(null);
  const helpers = pictureHelpers();
  const shown = helpers.map((helper) => helper.visible);
  for (const helper of helpers) helper.visible = false;
  return () => helpers.forEach((helper, i) => { helper.visible = shown[i]; });
}

function paintStillControls() {
  const select = document.getElementById("still-size");
  if (select) select.value = state.stillSize;
  paintSegmented("still-size-segments", "still-size");
  const frame = stillFrame();
}

// The size line, written when the SIZE changes and never on the way out
// of a render. paintStillControls used to write it whenever nothing was
// rendering, which meant the finally clause wiped the line saying the
// plate had been written the instant it was written: the render worked
// and reported nothing, which reads exactly like "it never saves".
function paintStillSize() {
  const frame = stillFrame();
  const tiles = Math.ceil(frame.width / STILL_TILE)
    * Math.ceil(frame.height / STILL_TILE);
  paintStillReadout(frame.width + " by " + frame.height + " pixels, "
    + tiles + (tiles === 1 ? " tile" : " tiles"));
}

// READING THE COMPOSER'S TARGET DOES NOT WORK HERE, and the reason is
// two lines up in this file: composerTarget is HalfFloatType. Half float
// pixels read into a Uint8Array come back as zeros, and the first plate
// rendered that way was 2048 by 1316 of pure black with every channel's
// extrema (0, 0). It is written down because the idea is a good one and
// somebody will have it again: it needs a byte-typed target and a copy
// pass into it, not a different buffer name.
//
// So the tile is read off the CANVAS, which is the path the recorder
// already proves, and the viewport is covered instead of being kept
// still. resize() is held off by state.recording throughout, and the
// canvas keeps its CSS box because setSize is called with updateStyle
// false, so nothing moves on the page; only the backing store changes,
// and the cover is what stops that being seen.

async function renderStill() {
  if (state.stillRendering || state.recording) return;
  if (!state.bundle) { paintStillReadout("load a study first"); return; }
  // Asked again at the moment it matters: a plate from a stale server goes
  // where the old code sends it.
  if (await checkServerCode()) {
    paintStillReadout("restart the studio first: this server predates the still fixes");
    showBanner("Restart studio first (foot of the panel): this server is older than its "
      + "code, and would put the still where the old code does.", "error");
    return;
  }
  const frame = stillFrame();
  const target = "study-" + state.bundle.slug;
  const across = Math.ceil(frame.width / STILL_TILE);
  const down = Math.ceil(frame.height / STILL_TILE);
  const button = document.getElementById("still-render");
  // A fixture's card is an overlay, and a plate is a picture: it goes
  // before the first tile rather than being hidden and remembered.
  closeFixturePanel();
  state.stillRendering = true;
  if (button) button.disabled = true;

  // OFF SCREEN, and that is the whole difference between this and the
  // recorder. A take is watched, so it renders to the canvas; a plate is
  // not, and resizing the visible canvas twelve times made the viewport
  // leap about (Param: "it jumps all over the place"). With
  // renderToScreen off, the composer's last pass stops at its own render
  // target, the canvas is never touched, and the pixels are read back
  // from that target instead.
  const wasPixelRatio = renderer.getPixelRatio();
  const wasWidth = canvas.width, wasHeight = canvas.height;
  document.body.classList.add("stilling");
  paintStillReadout("framing the plate");
  state.recording = true;          // resize() must keep its hands off
  const restoreHelpers = hideHelpersForPicture();
  // The plate is framed now and will not change: its reflections are
  // photographed once, for it.
  captureReflections();
  const began = performance.now();
  let sent = 0;
  try {
    renderer.setPixelRatio(1);
    composer.setPixelRatio(1);
    setShaftResolution(true);
    for (let row = 0; row < down; row += 1) {
      for (let column = 0; column < across; column += 1) {
        const x = column * STILL_TILE;
        const y = row * STILL_TILE;
        // The last tile in a row or column is short, and asking for a
        // full one would render past the frame and paste over its own
        // neighbour.
        const width = Math.min(STILL_TILE, frame.width - x);
        const height = Math.min(STILL_TILE, frame.height - y);
        renderer.setSize(width, height, false);
        composer.setSize(width, height);
        // The frustum is the WHOLE frame's, narrowed to this tile. The
        // aspect handed to applyCameraFrustum is therefore the plate's,
        // not the tile's, or every tile would be framed as though it
        // were the entire picture.
        camera.setViewOffset(frame.width, frame.height, x, y, width, height);
        applyCameraFrustum(frame.width / frame.height);
        renderView();
        // Render and read in one synchronous block, the rule
        // captureThumbnail states in full: assigning canvas.width
        // resets the drawing buffer.
        const blob = await new Promise(
          (resolve) => canvas.toBlob(resolve, "image/png"));
        const index = row * across + column;
        const response = await fetch("/api/still/" + target + "?tile=" + index
          + "&x=" + x + "&y=" + y, { method: "POST", body: blob });
        if (!response.ok) throw new Error("tile " + index + " was refused");
        sent += 1;
        paintStillReadout("tile " + sent + " of " + (across * down));
      }
    }
    const stitched = await fetch("/api/still/" + target + "/stitch?width="
      + frame.width + "&height=" + frame.height, { method: "POST" });
    if (!stitched.ok) throw new Error(await stitched.text());
    const done = await stitched.json();
    const seconds = ((performance.now() - began) / 1000).toFixed(1);
    paintStillReadout(frame.width + " by " + frame.height + " written in "
      + seconds + " s: " + done.still);
    logStudio("still: " + done.still);
  } catch (error) {
    paintStillReadout("the plate failed: " + (error.message || error));
    logStudio("still failed: " + (error.message || error));
  } finally {
    // Every one of these restores something the loop above took, and the
    // order matters: the view offset first, because applyCameraFrustum
    // below is what puts the ordinary frustum back.
    camera.clearViewOffset();
    renderer.setPixelRatio(wasPixelRatio);
    composer.setPixelRatio(wasPixelRatio);
    renderer.setSize(wasWidth, wasHeight, false);
    composer.setSize(wasWidth, wasHeight);
    setShaftResolution(false);
    state.recording = false;       // resize() picks the canvas back up
    restoreHelpers();
    document.body.classList.remove("stilling");
    state.stillRendering = false;
    applyCameraFrustum(viewportAspect());
    if (button) button.disabled = false;
    paintStillControls();
  }
}

// ---------- the section ----------
// A section through the crown in parallel projection, cut faces filled,
// with the inked outline on and the intrados stress lens still painted,
// is not a render at all. It is a drawing, and it is the one image the
// studio could not make: the argument is INSIDE the shell -- voussoir
// joints, thickness varying with thrust, the net under the masonry, the
// interface between permanent works and plant.

const SECTION_AXES = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };

function sectionNormal() {
  const axis = SECTION_AXES[state.section.axis] || SECTION_AXES.y;
  return new THREE.Vector3(axis[0], axis[1], axis[2]);
}

function sectionPlane() {
  // THREE.Plane holds the SIGNED distance from the origin along its
  // normal, so a plane standing at offset d has constant -d. Get that
  // sign backwards and every positive offset puts the cut behind the
  // model, which reads as "the section does nothing" rather than as an
  // error anybody would go looking for.
  return new THREE.Plane(sectionNormal(), -state.section.offset);
}

// Whether a mesh belongs to the machine rather than to the works being
// sectioned. Asked by ANCESTRY, not by material: the machine shares
// material instances with the permanent works, so a material-level test
// would cut both or neither and the toggle would do nothing at all.
function isMachinePart(object) {
  const group = machineObjects && machineObjects.group;
  if (!group) return false;
  for (let node = object; node; node = node.parent) {
    if (node === group) return true;
  }
  return false;
}

// THERE IS NO CAP, AND THAT IS THE FINDING.
//
// The plan called for the folklore cheap cap: a coloured plane a
// millimetre behind the cut so the shell reads solid. Built and
// photographed, it fails twice over. A section is normally viewed
// FACE ON, and a plane whose normal points at the camera fills the
// whole frame: it is a backdrop, not a cut face. To read as a cut it
// would have to be trimmed to the outline of the cut, which is exactly
// the work the cheap version existed to avoid.
//
// And it is not needed. Every vault material in this studio is already
// THREE.DoubleSide -- all twelve, from the greys at the top of the
// material table down -- so a clipped closed solid draws its own
// interior and the cut caps itself. The photograph shows the arch
// profile, the courses receding, the shell thickness and the springing,
// with no cap in the scene at all. The folklore assumes single-sided
// materials, which this studio does not have.
//
// What is still missing is a flat POCHE, the filled cut of a
// traditional section drawing. That needs the stencil two-pass, which
// was always scheduled as the three-day version, and it is the thing
// the cut-fill colour will belong to when it arrives.

function applySection() {
  const on = state.section.mode === "plane";
  const planes = on ? [sectionPlane()] : [];
  const none = [];
  scene.traverse((object) => {
    if (!object.material) return;
    const spared = isMachinePart(object) && !state.section.cutMachine;
    const mine = on && !spared ? planes : none;
    const materials = Array.isArray(object.material)
      ? object.material : [object.material];
    for (const material of materials) {
      if (!material) continue;
      material.clippingPlanes = mine;
      // The shadow is cut with the surface, or a sectioned vault goes
      // on casting the shadow of the half that is no longer drawn.
      material.clipShadows = true;
    }
  });
  // No needsUpdate here: the renderer keeps the plane COUNT in its
  // program cache key and recompiles by itself when that changes.
  // Setting it would rebuild every shader in the scene on every tick of
  // the offset dial.
  paintSectionControls();
}

// The dial's travel comes from the MODEL, not from a guess. Shipped at
// -30 to 30 it ran over a barrel about four metres deep, so nine tenths
// of the travel did nothing and the useful part was four pixels wide.
// Re-derived whenever the axis or the study changes.
function fitSectionRange() {
  const dial = document.getElementById("section-offset");
  if (!dial) return;
  const shell = state.objects.shell;
  const box = new THREE.Box3();
  if (shell) box.setFromObject(shell);
  if (box.isEmpty()) return;                 // no study yet; keep the default
  const axis = state.section.axis;
  const low = axis === "x" ? box.min.x : axis === "z" ? box.min.z : box.min.y;
  const high = axis === "x" ? box.max.x : axis === "z" ? box.max.z : box.max.y;
  // A hair beyond each face, so both ends of the dial are reachable and
  // "all of it" and "none of it" are both places the dial can stand.
  const margin = Math.max(0.1, (high - low) * 0.02);
  dial.min = (low - margin).toFixed(2);
  dial.max = (high + margin).toFixed(2);
  // A hundred steps across whatever that turns out to be.
  dial.step = Math.max(0.001, ((high - low) + 2 * margin) / 200).toFixed(3);
  state.section.offset = Math.min(+dial.max,
    Math.max(+dial.min, state.section.offset));
}

function paintSectionControls() {
  fitSectionRange();
  const select = document.getElementById("section-mode");
  if (select) select.value = state.section.mode;
  paintSegmented("section-mode-segments", "section-mode");
  const axis = document.getElementById("section-axis");
  if (axis) axis.value = state.section.axis;
  paintSegmented("section-axis-segments", "section-axis");
  const offset = document.getElementById("section-offset");
  if (offset) {
    offset.value = state.section.offset;
    paintScrub(offset);
    const reading = document.getElementById("section-offset-value");
    if (reading) reading.textContent = (+state.section.offset).toFixed(2);
  }
  const machine = document.getElementById("section-machine");
  if (machine) machine.checked = !!state.section.cutMachine;
}

function paintProjectionControls() {
  const select = document.getElementById("camera-projection");
  if (select) select.value = state.projection;
  paintSegmented("camera-projection-segments", "camera-projection");
  for (const button of document.querySelectorAll("#camera-views button")) {
    button.classList.toggle("active", button.dataset.view === state.cameraView);
  }
}

document.getElementById("camera-fov").addEventListener("input", (e) => {
  // The PERSPECTIVE camera's lens, named outright. An orthographic
  // camera has no fov, so writing camera.fov while one was active would
  // hang a dead property off it and the dial would stop doing anything
  // the moment the projection changed.
  perspectiveCamera.fov = +e.target.value;
  perspectiveCamera.updateProjectionMatrix();
  document.getElementById("camera-fov-value").textContent = e.target.value;
  document.getElementById("camera-mm").textContent =
    lensMillimetres(perspectiveCamera.fov);
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

// ---------- Ctrl and the wheel: the lens; Ctrl and the right button: the look ----------
// Both are taken in the capture phase on the window, before the orbit
// controls on the canvas can hear them: Ctrl and the wheel would otherwise
// dolly the camera AND zoom the whole page, and Ctrl and the right button
// would pan. Only over the viewport, and never while a take or a plate owns
// the camera.
let lensSaveTimer = null;
window.addEventListener("wheel", (event) => {
  if (!event.ctrlKey || event.target !== canvas) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if (state.recording || !camera.isPerspectiveCamera) return;
  const slider = document.getElementById("camera-fov");
  perspectiveCamera.fov = lensStep(perspectiveCamera.fov, event.deltaY,
    +slider.min, +slider.max);
  perspectiveCamera.updateProjectionMatrix();
  syncCameraControls();
  paintScrub(slider);
  // Remembered once the wheel has stopped, not on every notch.
  clearTimeout(lensSaveTimer);
  lensSaveTimer = setTimeout(rememberSession, 400);
}, { capture: true, passive: false });

let lookDrag = null;
const lookDirection = new THREE.Vector3();
window.addEventListener("pointerdown", (event) => {
  if (event.button !== 2 || !event.ctrlKey || event.target !== canvas) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if (state.recording) return;
  canvas.setPointerCapture(event.pointerId);
  lookDrag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY,
    // The orbit point stays as far in front of the eye as it was, so an
    // orbit after the look swings round what is now in front of it.
    distance: Math.max(0.5, camera.position.distanceTo(controls.target)) };
}, true);
window.addEventListener("pointermove", (event) => {
  if (!lookDrag || event.pointerId !== lookDrag.pointerId) return;
  event.stopImmediatePropagation();
  const dx = event.clientX - lookDrag.x;
  const dy = event.clientY - lookDrag.y;
  lookDrag.x = event.clientX;
  lookDrag.y = event.clientY;
  lookDirection.subVectors(controls.target, camera.position);
  const turned = lookTurn(lookDirection.toArray(), dx, dy);
  controls.target.set(camera.position.x + turned[0] * lookDrag.distance,
    camera.position.y + turned[1] * lookDrag.distance,
    camera.position.z + turned[2] * lookDrag.distance);
  camera.lookAt(controls.target);
}, true);
const endLook = (event) => {
  if (!lookDrag || event.pointerId !== lookDrag.pointerId) return;
  event.stopImmediatePropagation();
  lookDrag = null;
  rememberSession();
};
window.addEventListener("pointerup", endLook, true);
window.addEventListener("pointercancel", endLook, true);
// The section. Mode and axis rebuild the cap, the offset only moves the
// plane, and every one of them re-walks the scene because a material
// added since the last call (a prop just placed, a course just cut)
// carries no plane until it is told.
document.getElementById("section-mode").addEventListener("change", (e) => {
  if (e.target.value === "box") {
    // Offered and refused, in the studio's own register: the control
    // says what is coming rather than pretending one plane is all
    // there is. A box is six planes and a cap per face.
    logStudio("a box section is not built yet; the plane is");
    e.target.value = state.section.mode;
    paintSegmented("section-mode-segments", "section-mode");
    return;
  }
  state.section.mode = e.target.value;
  applySection();
  rememberSession();
});
document.getElementById("section-axis").addEventListener("change", (e) => {
  state.section.axis = e.target.value;
  applySection();
  rememberSession();
});
document.getElementById("section-offset").addEventListener("input", (e) => {
  state.section.offset = +e.target.value;
  applySection();
});
document.getElementById("section-offset").addEventListener("change", rememberSession);
document.getElementById("section-machine").addEventListener("change", (e) => {
  state.section.cutMachine = e.target.checked;
  applySection();
  rememberSession();
});
// Typing a width is the point of this dial: a plate reproduced at an
// exact frame width is a plate somebody else can redraw.
document.getElementById("camera-width").addEventListener("input", (e) => {
  setFrameWidthMetres(+e.target.value);
});
document.getElementById("camera-width").addEventListener("change", () => {
  rememberSession();
});
document.getElementById("camera-projection").addEventListener("change", (e) => {
  setProjection(e.target.value);
});
for (const button of document.querySelectorAll("#camera-views button")) {
  button.addEventListener("click", () => snapCameraTo(button.dataset.view));
}
// An orthographic zoom changes metres per pixel without moving anything,
// so the bar has to follow the controls and not only the resize.
controls.addEventListener("change", () => {
  paintScaleBar();
  // A wheel notch in orthographic changes zoom and nothing
  // else, so the width reading has to follow it.
  paintFrameWidth();
});
// A snapped view survives only until the mouse disagrees with it: after
// an orbit the highlight would be claiming a view the camera is not at.
controls.addEventListener("start", () => {
  if (!state.cameraView) return;
  state.cameraView = null;
  paintProjectionControls();
});

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
    ["weather-picker", "weather-tiles", "weather-preset"],
    ["atmosphere-picker", "atmosphere-tiles", "atmosphere-preset"],
  ]) {
    paintPicker(trigger, select,
      (swatch, value) => borrowTileImage(swatch, holder, value));
  }
  paintTileSelection(document.getElementById("atmosphere-tiles"), state.atmosphere.preset);
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
    chip.title = name === "all" ? "Show every group" : "Show only " + name;
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
  document.getElementById("shelf-sky-modes").classList
    .toggle("hidden", shelfKind !== "skies");
  paintSkyDials();
  document.getElementById("shelf-assign-skin").classList
    .toggle("hidden", shelfKind !== "materials");
  document.getElementById("shelf-assign-ground").classList
    .toggle("hidden", shelfKind !== "materials");
  document.getElementById("scene-new").classList
    .toggle("hidden", shelfKind !== "scenes");
  document.getElementById("scene-save").classList
    .toggle("hidden", shelfKind !== "scenes");
  const shelfEdit = document.getElementById("shelf-prop-edit");
  shelfEdit.classList.toggle("hidden", shelfKind !== "layers");
  // Opened afresh, it must show the mode the scene is actually in.
  shelfEdit.classList.toggle("active", state.propEdit);
  document.getElementById("stamp-group").classList
    .toggle("hidden", shelfKind !== "layers");
  document.getElementById("layer-group").classList
    .toggle("hidden", shelfKind !== "layers");
  document.getElementById("layer-delete-chosen").classList
    .toggle("hidden", shelfKind !== "layers");
  // The Layers grid is smaller tiles, like the fixtures: it is a list of
  // things to find, not a catalogue to choose from.
  grid.classList.toggle("layers", shelfKind === "layers");
  document.getElementById("layer-tabs").classList
    .toggle("hidden", shelfKind !== "layers");
  document.getElementById("scene-list").classList
    .toggle("hidden", shelfKind !== "scenes");
  propHolder.classList.toggle("hidden", shelfKind !== "props");
  document.getElementById("scatter-panel").classList
    .toggle("hidden", shelfKind !== "scatter");
  document.getElementById("lights-panel").classList
    .toggle("hidden", shelfKind !== "lights");
  // Leaving the drawer must put the region drag down, or the canvas keeps
  // a capture-phase listener that eats his next click on a prop.
  // Opening ANOTHER drawer puts the tool down. A CLOSED shelf does not:
  // arming the brush now folds the drawer away to clear the floor, and
  // the first click then re-rendered the shelf, saw no scatter tab, and
  // disarmed the brush it had just been asked to paint with.
  if (shelfKind && shelfKind !== "scatter" && state.scatterArmed) disarmScatterArea();
  grid.classList.toggle("hidden",
    shelfKind === "props" || shelfKind === "scenes"
    || shelfKind === "scatter" || shelfKind === "lights");
  grid.classList.toggle("wide", shelfKind === "skies");
  document.getElementById("prop-credit").textContent = "";
  if (shelfKind === "props") { renderShelfProps(cats, propHolder); return; }
  if (shelfKind === "scatter") { cats.innerHTML = ""; renderShelfScatter(); return; }
  if (shelfKind === "lights") { cats.innerHTML = ""; renderShelfLights(); return; }
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
// Above this many props PLACED BY HAND on a layer the drawer stops giving
// each its own tile. A scatter is one tile however big it is, and every
// picture is the .thumb.png beside its model (section 6), so a tile costs
// an image the browser already holds rather than an offscreen render;
// the cap only keeps a drawer of hand-placed things to a few screens.
const LAYER_TILE_CAP = 300;

function layerName(id) {
  const layer = layerById(id);
  return layer ? layer.name : "This layer";
}

const gatheredProps = new Set();
// The index a shift-click measures its run from, in the layer's own
// member order. Reset whenever the drawer is rebuilt for a new layer.
let layersAnchor = null;
// The tiles as last drawn, one item each, in the order they are shown:
// what a shift-click runs over, and what the selection repaints.
let layerItems = [];

function propLabel(record) {
  const entry = (state.propLibrary || []).find((e) => e.key === record.type);
  return entry ? entry.label : record.type;
}

// What a prop is CALLED, wherever it is named: the hover badge, the
// layer tile, the log. A library prop takes its catalogue label; a
// fixture takes the name of its kind, because "light-spot" is a key and
// "Spot" is the thing he placed.
function propDisplayName(record) {
  if (isLamp(record)) {
    const kind = LIGHT_KINDS.find((one) => one.key === record.type);
    if (kind) return kind.label;
  }
  return propLabel(record);
}

// The name and the number together, which is the whole of what he asked
// the badge to show: "Beech #7" says which beech, and the tile carrying
// the same words is how the one in the viewport is found in the drawer.
function propTag(record) {
  return propDisplayName(record) + " #" + (record.id || 0);
}

function paintStampButton() {
  const count = stillPlaced([...gatheredProps]).length;
  const stamp = document.getElementById("stamp-group");
  stamp.disabled = !count;
  stamp.textContent = count ? "Place copies of " + count : "Place copies";
  document.getElementById("layer-group").disabled = !count;
  // Delete takes what a gesture acts on (actingProps): a whole scatter
  // picked from its tile, a run shift-clicked, or the one prop selected.
  const going = actingProps().length;
  const del = document.getElementById("layer-delete-chosen");
  del.disabled = !going;
  del.textContent = going > 1 ? "Delete " + going.toLocaleString() : "Delete";
  del.title = going
    ? "Delete the " + (going > 1 ? going.toLocaleString() + " selected props" : "selected prop")
      + "; Ctrl+Z brings them back"
    : "Nothing selected to delete: pick a tile here, or a prop in the viewport";
}

function renderShelfLayers(grid) {
  grid.innerHTML = "";
  layerItems = [];
  const kept = new Set(stillPlaced([...gatheredProps]));
  for (const record of [...gatheredProps]) {
    if (!kept.has(record)) gatheredProps.delete(record);
  }
  const members = state.props.filter((r) => r.layer === state.activeLayer);
  if (!members.length) {
    const empty = document.createElement("div");
    empty.className = "tile-family";
    empty.textContent = "nothing on this layer yet -- placed props land here";
    grid.appendChild(empty);
  }
  // WHAT IS ON THE LAYER, AS HE PLACED IT. Param, 2026-09-13, over a
  // drawer that said only "53 props, 4 kinds. Too many to picture": "we
  // also must find a way to display the objects in layers whether
  // thumbnail or not, perhaps when i select an object it highlights the
  // prop placed so we can confer that way. this means i can easily
  // delete many items that are placed."
  //
  // A scatter is one tile, because it is one thing he placed (section 14),
  // and a prop placed by hand is one tile each. Pointing at a tile puts
  // the amber box over what it names in the viewport; clicking selects it
  // there; Delete, or the Delete button, takes the selection.
  const scatters = new Map();   // planting -> { planting, first, kinds, chosen }
  const byHand = [];
  for (const record of members) {
    const planting = plantingOf(record);
    if (!planting) { byHand.push(record); continue; }
    let entry = scatters.get(planting);
    if (!entry) {
      entry = { planting, first: record, kinds: new Map(), chosen: 0 };
      scatters.set(planting, entry);
    }
    entry.kinds.set(record.type, (entry.kinds.get(record.type) || 0) + 1);
    if (gatheredProps.has(record)) entry.chosen += 1;
  }
  const heading = (text) => {
    const span = document.createElement("span");
    span.className = "tile-family";
    span.textContent = text;
    grid.appendChild(span);
  };
  const ordered = [...scatters.values()]
    .sort((a, b) => a.planting.scatter - b.planting.scatter);
  if (ordered.length) heading("scattered");
  for (const entry of ordered) {
    const { planting, first, kinds } = entry;
    plantingBounds(planting);
    const common = [...kinds].sort((a, b) => b[1] - a[1]);
    // Pictured by the kind most of it is, and named in the badge's words.
    const tile = previewTile("scatter#" + planting.scatter, "Scatter #" + planting.scatter,
      (canvasEl) => paintPropThumb(canvasEl, common[0][0]));
    tile.title = plantingName(planting) + ": "
      + common.slice(0, 5).map(([type, n]) =>
        propDisplayName({ type }) + " " + n.toLocaleString()).join(", ")
      + (common.length > 5 ? " and " + (common.length - 5) + " more kinds" : "")
      + " -- click to select all of it, Delete removes it";
    tile.classList.toggle("active", entry.chosen === planting.members);
    layerItems.push({ tile, first, records: () => plantingRecords(planting),
      chosenIn: (acting) => plantingRecords(planting).every((r) => acting.has(r)) });
    grid.appendChild(tile);
  }
  const shown = byHand.slice(0, LAYER_TILE_CAP);
  if (byHand.length && ordered.length) heading("placed by hand");
  for (const record of shown) {
    // THE SAME WORDS THE BADGE SHOWS. Hovering a prop in the viewport
    // names it "Beech #7"; the tile has to say "Beech #7" too, or the
    // number is a label pointing at nothing.
    const tile = previewTile("prop#" + record.id, propTag(record),
      (canvasEl) => paintPropThumb(canvasEl, record.type));
    tile.title = propTag(record)
      + "  (" + record.x.toFixed(1) + ", " + record.y.toFixed(1) + ")"
      + " -- click to select: drag it in the viewport, Delete removes";
    tile.classList.toggle("active", gatheredProps.has(record));
    layerItems.push({ tile, first: record, records: () => [record],
      chosenIn: (acting) => acting.has(record) });
    grid.appendChild(tile);
  }
  if (byHand.length > shown.length) {
    heading("and " + (byHand.length - shown.length).toLocaleString()
      + " more placed by hand -- pick them in the viewport");
  }
  layerItems.forEach((item, index) => wireLayerTile(item, index));
  renderLayerTabs();
  paintStampButton();
  paintLayerPointer();
}

// One tile's gestures, the same for a scatter and for one prop.
function wireLayerTile(item, index) {
  const { tile, first } = item;
  // Pointing at a tile points at what it names: the amber box and the
  // badge stand over it in the viewport, so the drawer and the scene can
  // be read against each other without clicking either. Delete then takes
  // what is pointed at, exactly as it does over the viewport.
  tile.addEventListener("pointerenter", () => setHoveredProp(first));
  tile.addEventListener("pointerleave", () => {
    if (hoveredProp === first) setHoveredProp(null);
  });
  tile.addEventListener("click", (event) => {
    // Shift takes the whole run from the last plain click to this one,
    // over the tiles as they are shown.
    if (event.shiftKey && layersAnchor !== null
        && layersAnchor < layerItems.length) {
      const lo = Math.min(layersAnchor, index);
      const hi = Math.max(layersAnchor, index);
      for (let i = lo; i <= hi; i++) {
        for (const record of layerItems[i].records()) gatheredProps.add(record);
      }
      setPropEdit(true, true);
      // THE VIEWPORT HAS TO SHOW IT. Before this, a shift-click lit
      // four tiles and left the scene outlining one prop with its
      // gumball on that prop alone, so a set of four looked exactly
      // like a set of one -- which is what he was reporting.
      // selectProp settles the group's outlines and stands the
      // gumball at its centre.
      selectProp(first);
      return;
    }
    layersAnchor = index;
    // A tile toggles membership of the working selection; the last one
    // picked is also the viewport's selected object.
    const records = item.records();
    if (records.every((record) => gatheredProps.has(record))) {
      for (const record of records) gatheredProps.delete(record);
      selectProp(records.includes(state.selectedProp) ? null : state.selectedProp);
      return;
    }
    for (const record of records) gatheredProps.add(record);
    // Picking a prop here IS asking to work on it (Param: "I should
    // be able to select delete and move any of the props ... instead
    // of having to find the edit button and press it"), so edit mode
    // comes on with the selection rather than being hunted for.
    // Quietly, because the mode change is a consequence of the click
    // and not a thing he asked for in its own right -- and as a LOAN
    // worth one placement, not a mode he now has to notice and undo.
    const granted = !state.propEdit;
    setPropEdit(true, true);
    if (granted) propEditOneShot = true;
    selectProp(first);
  });
}

// The tiles follow the selection wherever it was made: a prop clicked in
// the viewport lights its tile as surely as a tile lights its prop.
function paintLayerChosen() {
  if (shelfKind !== "layers" || !layerItems.length) return;
  const acting = new Set(actingProps());
  for (const item of layerItems) {
    item.tile.classList.toggle("active", item.chosenIn(acting));
  }
  paintStampButton();
}

// And the tile of whatever the pointer is over in the viewport wears the
// hover box's amber, brought into view if the drawer has scrolled past it.
function paintLayerPointer() {
  if (shelfKind !== "layers" || !layerItems.length) return;
  const planting = plantingOf(hoveredProp);
  for (const item of layerItems) {
    const pointed = !!hoveredProp && (planting
      ? plantingOf(item.first) === planting
      : item.first === hoveredProp);
    item.tile.classList.toggle("pointed", pointed);
    // Not when the pointer is on the tile itself: scrolling the grid out
    // from under it would hand the hover to the next tile along.
    if (pointed && !item.tile.matches(":hover")) {
      item.tile.scrollIntoView({ block: "nearest" });
    }
  }
}

// A placed prop's picture: the .thumb.png beside its model (section 6), a
// live render only for a model with no snapshot yet, and a built-in's own
// handful of primitives.
function paintPropThumb(canvasEl, type) {
  fillFlat(canvasEl, new THREE.Color(0x2a2e34));
  const entry = propLibraryEntry(type);
  if (entry && entry.builtIn) {
    renderObjectPreview(builtInPreview(entry.key), canvasEl);
    return;
  }
  const template = propTemplates.get(type);
  if (!entry || !entry.file) {
    if (template) renderObjectPreview(template, canvasEl);
    return;
  }
  const picture = new Image();
  picture.onload = () => canvasEl.getContext("2d")
    .drawImage(picture, 0, 0, canvasEl.width, canvasEl.height);
  picture.onerror = () => { if (template) renderObjectPreview(template, canvasEl); };
  picture.src = "/api/props/" + encodeURIComponent(entry.file + ".thumb.png");
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
      layersAnchor = null;     // a new layer, a new run to measure from
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
// staying exactly where they stand. It is one undo entry: the undo puts
// each back on the layer it came from and takes the fresh layer away once
// it is empty (Ctrl+Z after a Group used to undo whatever came before it);
// the redo brings the SAME layer back and moves them again.
function groupToNewLayer(again) {
  const chosen = stillPlaced(again ? again.chosen : [...gatheredProps]);
  if (!chosen.length) return;
  const openBefore = again ? again.openBefore : state.activeLayer;
  let home;
  if (again) {
    reinstateLayer(again.home, again.at);
    home = again.home;
    state.activeLayer = home.id;
  } else {
    home = newLayer(null);
  }
  const before = chosen.map((record) => record.layer);
  for (const record of chosen) record.layer = home.id;
  gatheredProps.clear();
  applyLayerVisibility();
  saveProps();
  renderShelf();
  let at = -1;
  pushUndo("grouping " + chosen.length + " props", () => {
    chosen.forEach((record, i) => {
      // One whose old layer has gone since stays where it is.
      if (layerById(before[i])) record.layer = before[i];
    });
    at = dropLayerIfEmpty(home);
    if (layerById(openBefore)) state.activeLayer = openBefore;
    applyLayerVisibility();
    saveProps();
    renderShelf();
  }, () => groupToNewLayer({ chosen, home, at, openBefore }));
  logStudio(chosen.length + " props grouped onto " + home.name);
}

document.getElementById("layer-group").addEventListener("click", () => groupToNewLayer());
document.getElementById("layer-delete-chosen").addEventListener("click",
  () => deletePropsWithUndo(actingProps()));

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

// ---------- the corner readout ----------
// What a renderer puts in the corner. Four of the numbers the page can
// see for itself; three it cannot, and those come from /api/stats.
//
// renderer.info.autoReset is turned OFF here, once, and the counters are
// reset at the top of each frame instead. Left on, it clears them on
// EVERY render call, and the composer ends a frame with a fullscreen
// copy pass, so anything read afterwards reports that pass alone: one
// draw call and one triangle, identical however much is on screen. That
// is exactly what the first budget measurement got wrong.
let statsFrames = 0;
let statsSince = 0;
let statsShown = { fps: 0, calls: 0, triangles: 0 };

function noteFrame() {
  const info = composer.renderer.info;
  if (info.autoReset) info.autoReset = false;
  statsFrames += 1;
  const now = performance.now();
  if (!statsSince) statsSince = now;
  if (now - statsSince >= 500) {
    statsShown = { fps: Math.round(statsFrames * 1000 / (now - statsSince)),
      calls: info.render.calls, triangles: info.render.triangles };
    statsFrames = 0;
    statsSince = now;
    paintStats();
  }
  info.reset();
}

function paintStats() {
  const overlay = document.getElementById("stats-overlay");
  if (!overlay || overlay.classList.contains("hidden")) return;
  const write = (id, text) => {
    const box = document.getElementById(id);
    if (box) box.textContent = text;
  };
  write("stat-objects", String(state.props.length));
  write("stat-calls", statsShown.calls.toLocaleString());
  write("stat-tris", statsShown.triangles >= 1e6
    ? (statsShown.triangles / 1e6).toFixed(1) + " M"
    : statsShown.triangles.toLocaleString());
  write("stat-fps", String(statsShown.fps));
}

// The machine's own two, polled rather than pushed. A second is plenty:
// neither moves meaningfully faster, and the route caches for that long
// anyway so a faster poll would read the same numbers.
async function pollMachineStats() {
  const overlay = document.getElementById("stats-overlay");
  if (!overlay || overlay.classList.contains("hidden")) return;
  try {
    const body = await fetchJson("/api/stats");
    const gpu = body.gpu;
    document.getElementById("stat-vram").textContent = gpu
      ? (gpu.vramUsedMb / 1024).toFixed(1) + " / "
        + (gpu.vramTotalMb / 1024).toFixed(0) + " GB"
      : "--";
    document.getElementById("stat-gpu").textContent =
      gpu ? gpu.busy + "%" : "--";
    document.getElementById("stat-cpu").textContent =
      typeof body.cpu === "number" ? body.cpu.toFixed(0) + "%" : "--";
  } catch (error) {
    // An older server has no such route. Say nothing and show dashes:
    // the four browser-side numbers are still worth having.
    for (const id of ["stat-vram", "stat-gpu", "stat-cpu"]) {
      const box = document.getElementById(id);
      if (box) box.textContent = "--";
    }
  }
}
setInterval(pollMachineStats, 1000);

function toggleStats(on) {
  const overlay = document.getElementById("stats-overlay");
  if (!overlay) return;
  overlay.classList.toggle("hidden", !on);
  const tile = document.getElementById("shelf-stats");
  if (tile) tile.classList.toggle("active", !!on);
  if (on) { paintStats(); pollMachineStats(); }
}

const statsOverlay = document.getElementById("stats-overlay");
if (statsOverlay) statsOverlay.addEventListener("click", () => toggleStats(false));
const statsTile = document.getElementById("shelf-stats");
if (statsTile) statsTile.addEventListener("click", () =>
  toggleStats(statsOverlay.classList.contains("hidden")));

// ---------- the live graphs ----------
// Four cards down the left edge that play with the take: the model in
// live_graphs.js, sampled once per study and drawn once, then a cursor
// and four readings that follow the clock. The series are built lazily
// from whatever the studio holds (the bundle, the formwork document, the
// columns) and thrown away whenever any of those changes; the cursor is
// moved from the render loop, so play, scrub and record all drive it and
// applyTimeline stays a pure function of t.
// (liveGraphs itself is declared beside the scrubber, far above: applyTheme
// runs during boot and invalidates the graphs, and a const declared down
// here would still be in its temporal dead zone when it did.)

// The studio's clock, as numbers, so the module stays pure.
function liveClock() {
  return { duration: timelineDuration(), opening: openingSeconds(),
    formwork: formworkSeconds(), step: placementStep(), drop: DROP_SECONDS,
    strike: STRIKE_SECONDS, pieces: placementCount() };
}

// The graphs' inks, read off the theme at draw time.
function liveTheme() {
  const style = getComputedStyle(document.documentElement);
  const read = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
  return { ink: read("--ink", "#e6e6e6"), ink2: read("--ink-2", "#a0a0a0"),
    line: read("--line", "#393939"), scrim: read("--scrim", "rgba(16,18,22,0.85)"),
    a: read("--graph-a", "#5fb3a6"), aFill: read("--graph-a-fill", "rgba(95,179,166,0.16)"),
    b: read("--graph-b", "#d9a25f"),
    c: read("--graph-c", "#d77a8a"), cFill: read("--graph-c-fill", "rgba(215,122,138,0.16)"),
    font: "system-ui, sans-serif", mono: "ui-monospace, monospace" };
}

// The exporter's final column forces: the formwork route's, when the
// contract's mould block carried them, else the columns document's own.
function liveColumnForces() {
  const formwork = state.formwork;
  if (formwork && formwork.columns && Array.isArray(formwork.columns.forces)) {
    return formwork.columns.forces;
  }
  const members = state.columnMembers || [];
  const forces = members.map((m) => (m && typeof m.force === "number") ? m.force : null);
  return forces.length && forces.every((f) => f !== null) ? forces : null;
}

function invalidateLiveGraphs() {
  liveGraphs.dirty = true;
  liveGraphs.lastK = -1;
}

// A full rebuild is the series and every plot, a long frame of its own,
// so a dial dragged across asks for one once the hand stops rather than
// one per frame of the drag (which froze the take while it moved).
const LIVE_REBUILD_MS = 150;
function invalidateLiveGraphsSoon() {
  clearTimeout(liveGraphs.rebuildTimer);
  liveGraphs.rebuildTimer = setTimeout(invalidateLiveGraphs, LIVE_REBUILD_MS);
}

// Plotly sizes a plot from its box when it draws, and its responsive flag
// only listens to the window; so a card whose box changes afterwards (the
// notes line grows, a card comes or goes, the panel is shown again) is
// redrawn to its new size here. A card's height is its grid row's, never
// its plot's, so a redraw cannot feed back into another.
const liveCardWatch = typeof ResizeObserver === "function"
  ? new ResizeObserver((entries) => {
    if (!window.Plotly) return;
    for (const entry of entries) {
      const plot = entry.target.querySelector(".live-plot");
      if (!plot || !plot._fullLayout || entry.contentRect.height <= 0) continue;
      const done = window.Plotly.Plots.resize(plot);
      if (done && done.catch) done.catch(() => { /* hidden meanwhile */ });
    }
  })
  : null;

function showLiveGraphs(on) {
  const panel = document.getElementById("graphs-panel");
  if (!panel) return;
  liveGraphs.shown = !!on;
  panel.classList.toggle("hidden", !on);
  const tile = document.getElementById("shelf-graphs");
  if (tile) tile.classList.toggle("active", !!on);
  if (on) { liveGraphs.lastK = -1; tickLiveGraphs(true); }
}

// Tucked slides the whole column off the left edge and leaves its handle
// on the screen; it is independent of shown, so hiding, showing and Play
// all keep whichever he left. While tucked the cards cost nothing: the
// tick does no Plotly work until they come back, and coming back draws
// the take's current instant at once.
function applyGraphsTucked(on) {
  liveGraphs.tucked = !!on;
  const panel = document.getElementById("graphs-panel");
  if (panel) panel.classList.toggle("tucked", liveGraphs.tucked);
  const handle = document.getElementById("graphs-collapse");
  if (handle) {
    handle.textContent = liveGraphs.tucked ? "›" : "‹";
    handle.title = liveGraphs.tucked ? "Bring the graphs back" : "Tuck the graphs to the side";
  }
}

function setGraphsTucked(on) {
  applyGraphsTucked(on);
  try { localStorage.setItem(LIVE_TUCKED_KEY, on ? "1" : "0"); } catch (error) { /* ditto */ }
  if (!on) { liveGraphs.lastK = -1; tickLiveGraphs(true); }
}

// The sample under the take's clock, and the clock itself clamped to the
// series: what the cursor stands on and where the traces stop.
function liveCursorAt(series) {
  const n = series.t.length;
  const duration = series.t[n - 1] || 1;
  const t = Math.max(0, Math.min(duration, state.timeline.t));
  return { k: Math.round((n - 1) * t / duration), t };
}

// What the header says the vault is weighed as. A skin that sets the
// density is named: "concrete, 200 mm at 8940 kg/m3" was a copper skin's
// density on a concrete cut, and read as a contradiction.
function liveSkinWord(bundle, density) {
  const structural = STRUCTURAL_DENSITIES[bundle.material];
  const fromSkin = bundle.provenance.density_from_skin
    || (structural && Math.abs(density - structural) > 1);
  if (!fromSkin) return "";
  const skin = state.appearance.skin;
  const entry = isLibraryKey(skin) ? libraryEntry(skin) : null;
  if (!entry) return "a library skin";
  // The bundle was weighed with the skin worn when it was cut, and a
  // swap within one structural class since (granite for limestone, both
  // stone) re-cuts nothing. So when the skin worn now would weigh the
  // vault differently, it is not the one this density came from: say a
  // library skin and name none, rather than credit the wrong one.
  if (Math.abs(skinDensity() - density) > 1) return "a library skin";
  let word = entry.family || entry.name;
  for (const [pattern] of NAME_DENSITIES) {
    if (pattern.test(entry.name)) { word = pattern.source; break; }
  }
  // A family word that is the cut's own class says nothing ("timber cut
  // in a timber skin", "stone cut in a stone skin"): name the skin itself.
  if (FAMILY_TO_STRUCTURAL[word] === bundle.material) {
    word = (entry.label || entry.name).toLowerCase();
  }
  return (/^[aeiou]/i.test(word) ? "an " : "a ") + word + " skin";
}

// Wanted is the user's own switch, remembered; shown is whether the
// cards are up now. Play brings them up when wanted; the close button
// and the tile move the switch.
function setLiveGraphsWanted(on) {
  liveGraphs.wanted = !!on;
  try { localStorage.setItem(LIVE_GRAPHS_KEY, on ? "1" : "0"); } catch (error) { /* ditto */ }
  showLiveGraphs(on);
}

async function buildLiveGraphs() {
  if (!state.bundle || !state.timeline || liveGraphs.building) return;
  liveGraphs.building = true;
  try {
    await ensurePlotly();
    const bundle = state.bundle;
    // Weighed as the bundle was: the provenance density is the skin's
    // when a skin overrides, exactly what staging weighed the courses with.
    const density = bundle.provenance.density || skinDensity() || structuralDensity();
    const series = buildLiveSeries({
      bundle, formwork: state.formwork, clock: liveClock(),
      thickness: bundle.provenance.thickness, density,
      columnForcesKN: liveColumnForces(), columnRadiusM: state.columnRadius,
      prestress: liveGraphs.prestress,
    });
    const specs = liveSpecs(series, liveTheme());
    liveGraphs.series = series;
    liveGraphs.specs = specs;
    const holder = document.getElementById("graphs-cards");
    // A card the new specs no longer name (a study without columns after
    // one with them) comes down, or a stale plot would stand under the
    // new study's numbers.
    for (const [id, card] of [...liveGraphs.cards]) {
      if (specs.some((spec) => spec.id === id)) continue;
      const plot = card.querySelector(".live-plot");
      if (plot && window.Plotly) window.Plotly.purge(plot);
      if (liveCardWatch) liveCardWatch.unobserve(card);
      card.remove();
      liveGraphs.cards.delete(id);
    }
    const study = document.getElementById("graphs-study");
    const skinWord = liveSkinWord(bundle, density);
    if (study) study.textContent = bundle.export + ", " + bundle.material
      + (skinWord ? " cut in " + skinWord : "") + ", "
      + Math.round(bundle.provenance.thickness * 1000) + " mm, weighed at "
      + Math.round(density) + " kg/m3";
    // Every card, and the notes line under them, is in place BEFORE any
    // plot is drawn: the cards share the column's height, and a card
    // appended after an earlier one was drawn left that one clipped to
    // its new row with no x axis.
    for (const spec of specs) {
      let card = liveGraphs.cards.get(spec.id);
      if (!card) {
        card = document.createElement("div");
        card.className = "live-card";
        card.innerHTML = '<header><span class="live-name"></span><span class="live-unit"></span>'
          + '<span class="live-reading"></span><span class="live-label"></span>'
          + '<span class="live-aside"></span></header><div class="live-plot"></div>';
        holder.appendChild(card);
        liveGraphs.cards.set(spec.id, card);
        if (liveCardWatch) liveCardWatch.observe(card);
      }
      card.querySelector(".live-name").textContent = spec.name;
      card.querySelector(".live-unit").textContent = spec.unit;
    }
    // In the specs' order, so a card that arrives later (a study with
    // columns after one without) stands where it belongs, not last.
    for (const spec of specs) holder.appendChild(liveGraphs.cards.get(spec.id));
    const notes = document.getElementById("graphs-notes");
    if (notes) notes.textContent = series.notes.join(" ");
    // The first frame is already cut at the take's clock, so no frame of
    // whole curves flashes before the first tick trims them.
    const cursor = liveCursorAt(series);
    for (const spec of specs) {
      const plot = liveGraphs.cards.get(spec.id).querySelector(".live-plot");
      const cut = liveCut(spec, cursor.k, cursor.t);
      const data = spec.data.map((trace, i) => Object.assign({}, trace,
        { x: cut.x[i], y: cut.y[i] }));
      const shape = spec.layout.shapes[spec.layout.shapes.length - 1];
      shape.x0 = shape.x1 = cursor.t;
      await window.Plotly.react(plot, data, spec.layout,
        { displayModeBar: false, responsive: true, doubleClick: false });
      // A click on a graph is a seek: the take goes to that instant and
      // waits there, which is the "pinpoint" he asked for.
      if (!plot.liveSeekBound) {
        plot.liveSeekBound = true;
        plot.on("plotly_click", (event) => {
          const point = event && event.points && event.points[0];
          if (point && Number.isFinite(point.x)) seekLiveGraphs(point.x);
        });
      }
    }
    liveGraphs.dirty = false;
    liveGraphs.lastK = -1;
  } catch (error) {
    reportProblem("the live graphs could not be built: " + error.message, error);
    liveGraphs.dirty = false;
  } finally {
    liveGraphs.building = false;
  }
  tickLiveGraphs(true);
}

// Once a frame from the render loop: the readings every time the sample
// changes, and with them each card's traces cut at the clock and its
// cursor, in ONE Plotly.update per card, so the curves grow as the take
// plays, a scrub back truncates them, and a paused take shows them up to
// the cursor. On a constrained device, while playing, the traces follow
// every second sample and the cursor alone moves between (a relayout of
// one shape); paused, they always stand at the cursor.
function tickLiveGraphs(force) {
  if (!liveGraphs.shown || !state.timeline || !state.bundle) return;
  if (liveGraphs.tucked) return;
  if (liveGraphs.dirty) { if (!liveGraphs.building) buildLiveGraphs(); return; }
  const series = liveGraphs.series;
  if (!series || !liveGraphs.specs) return;
  const { k, t } = liveCursorAt(series);
  // Paused, the traces stand at the cursor: a constrained device lets
  // them lag a sample while playing, and a one-sample scrub or the sample
  // the take stopped on is made up at once, never left drawn past or short.
  if (liveGraphs.drawnK !== k && !state.timeline.playing) force = true;
  if (k === liveGraphs.lastK && !force) return;
  liveGraphs.lastK = k;
  const grow = force || !CONSTRAINED_DEVICE || Math.abs(k - liveGraphs.drawnK) >= 2;
  if (grow) liveGraphs.drawnK = k;
  for (const spec of liveGraphs.specs) {
    const card = liveGraphs.cards.get(spec.id);
    if (!card) continue;
    card.querySelector(".live-reading").textContent = spec.reading(k).toFixed(2);
    card.querySelector(".live-label").textContent = spec.readingLabel;
    card.querySelector(".live-aside").textContent = spec.aside ? spec.aside(k) : "";
    const plot = card.querySelector(".live-plot");
    const last = spec.layout.shapes.length - 1;
    const patch = {};
    patch["shapes[" + last + "].x0"] = t;
    patch["shapes[" + last + "].x1"] = t;
    if (grow) window.Plotly.update(plot, liveCut(spec, k, t), patch);
    else window.Plotly.relayout(plot, patch);
  }
}

function seekLiveGraphs(t) {
  if (!state.timeline) return;
  state.timeline.playing = false;
  paintPlayButtons("Play");
  applyTimeline(Math.max(0, Math.min(timelineDuration(), t)));
  scrubber.value = Math.round(1000 * state.timeline.t / timelineDuration());
  updateHud();
  tickLiveGraphs(true);
}

// The series as a sheet, to lay the physical model's readings beside.
function downloadLiveSeries() {
  if (!liveGraphs.series || !state.bundle) return;
  const text = seriesToCsv(liveGraphs.series, state.bundle.export);
  const blob = new Blob([text], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = state.bundle.slug + "-live-series.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  logStudio("live graphs: " + link.download + " (" + liveGraphs.series.t.length + " rows)");
}

{
  const tile = document.getElementById("shelf-graphs");
  if (tile) tile.addEventListener("click", () => setLiveGraphsWanted(!liveGraphs.shown));
  const close = document.getElementById("graphs-close");
  if (close) close.addEventListener("click", () => setLiveGraphsWanted(false));
  applyGraphsTucked(liveGraphs.tucked);
  const tuck = document.getElementById("graphs-collapse");
  if (tuck) tuck.addEventListener("click", () => setGraphsTucked(!liveGraphs.tucked));
  const csv = document.getElementById("graphs-csv");
  if (csv) csv.addEventListener("click", downloadLiveSeries);
  const dial = document.getElementById("graphs-prestress");
  if (dial) {
    dial.value = Math.round(liveGraphs.prestress * 100);
    document.getElementById("graphs-prestress-value").textContent = dial.value;
    dial.addEventListener("input", () => {
      liveGraphs.prestress = +dial.value / 100;
      document.getElementById("graphs-prestress-value").textContent = dial.value;
      try { localStorage.setItem(LIVE_PRESTRESS_KEY, String(liveGraphs.prestress)); } catch (error) { /* ditto */ }
      invalidateLiveGraphsSoon();
    });
  }
}

// ---------- the lights drawer ----------
// Param: "maybe we need to make a light tile and put all the lights there
// and not in props", and "removing the controls from scene and not naming
// it lamp". So: three fixtures, their own tab, their numbers beside them,
// and nothing here calls itself a lamp where he can read it.
function renderShelfLights() {
  const grid = document.getElementById("lights-kinds");
  if (!grid) return;
  grid.innerHTML = "";
  for (const kind of LIGHT_KINDS) {
    const tile = previewTile(kind.key, kind.label,
      (canvasEl) => {
        fillFlat(canvasEl, new THREE.Color(0x2a2e34));
        renderObjectPreview(builtInPreview(kind.key), canvasEl);
      });
    tile.title = kind.label + " light  "
      + kind.sizeMetres.map((n) => n.toFixed(2)).join(" x ") + " m";
    tile.addEventListener("click", () => carryNewProp(kind.key));
    grid.appendChild(tile);
  }
  syncLightSize();
  syncLightControls();
}

// Which fixtures the size dials act on: the selected one, or all of them
// when nothing is selected. Same rule the output and warmth dials use, so
// the whole drawer behaves one way rather than two.
function lightsUnderTheDials() {
  const one = isLamp(state.selectedProp) ? state.selectedProp : null;
  return one ? [one] : state.props.filter(isLamp);
}

function syncLightSize() {
  const chosen = lightsUnderTheDials()[0];
  const size = document.getElementById("light-size");
  const length = document.getElementById("light-length");
  if (!size || !length) return;
  size.value = chosen ? (chosen.scale || 1) : 1;
  length.value = chosen && Array.isArray(chosen.size) ? chosen.size[0] : 1;
  paintScrub(size);
  paintScrub(length);
  document.getElementById("light-size-value").textContent =
    (+size.value).toFixed(2);
  document.getElementById("light-length-value").textContent =
    (+length.value).toFixed(1);
}

function writeLightSize() {
  const scale = +document.getElementById("light-size").value;
  const along = +document.getElementById("light-length").value;
  for (const record of lightsUnderTheDials()) {
    record.scale = scale;
    // Only the long axis stretches. A strip whose thickness followed its
    // length would just be a bigger strip, which is not resizing it.
    record.size = [along, 1, 1];
    applyPropSize(record);
  }
  document.getElementById("light-size-value").textContent = scale.toFixed(2);
  document.getElementById("light-length-value").textContent = along.toFixed(1);
  refreshPropOutline();
  refreshPropGumball();
  saveProps();
}

for (const id of ["light-size", "light-length"]) {
  const input = document.getElementById(id);
  if (input) input.addEventListener("input", writeLightSize);
}

// ---------- the scatter ----------
// Param: "we should have a scatter tile next to props that allows us to
// select the props we want, how often each one appears, the size ratio we
// pick, and some other relevant settings".
//
// What it makes is ORDINARY PROP RECORDS through placeProp. That is the
// whole reason the gumball, the drag, R, plus and minus, Delete, the layer
// eye, undo and the scene round trip all work on a scattered tree with no
// new code: it is a prop like any other, and there is no second universe
// of pickable things to keep in step. How a record is DRAWN is placeProp's
// business, not the scatter's: since 2026-09-11 a library prop is one
// instance of its variant's batch (see "the instanced props"), and nothing
// here had to change for it.
//
// The ceiling is TRIANGLES, not instances, and it is measured rather than
// argued (bench/scripts/scatter_budget.mjs, on the 4090 at 1080p):
// 0.117 ms per million manifest triangles for something that does not cast
// a shadow, 0.175 for something that does, because a caster is drawn again
// for the shadow map. Six of the sixteen-point-seven millisecond frame is
// 35 million manifest triangles, which is about 37,000 of the 941-triangle
// bermuda grass, 1,270 of a median prop, or 175 of the heaviest tree.
const SCATTER_BUDGET_TRIANGLES = 35e6;
const SCATTER_MAX_ITEMS = 6000;

// mulberry32 through Math.imul, which is exact in 32 bits. Do NOT copy the
// seed idiom used by the ground randomiser above: seed * 1103515245 passes
// 2^53 and silently loses its low bits, so it is not the generator it
// looks like.
function scatterRandom(seed) {
  let a = (seed >>> 0) || 1;
  return function next() {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function propEntry(type) {
  return libraryIndex().get(type) || null;
}

// ---------- families ----------
// A species is a FAMILY and a placement is one of its variants. Poly
// Haven ships a grass as a row of tufts fused into one mesh; split.mjs
// cuts the row into grass_medium_01__v1 to __v8, one file each, and
// writes family: "grass_medium_01" on every one. The drawers show the
// family once, and every placement draws a variant at random, so a field
// of one species is a field of eight shapes (Param: "each type is one
// object we can make many variants of").
function familyOf(entry) { return entry.family || entry.key; }

function familyMembers(family) {
  libraryIndex();
  return libraryByFamily.get(family) || [];
}

// The family's label is the variant's with its number taken off, because
// split.mjs names them "<label> 1", "<label> 2", and that is the only
// place the number comes from.
function familyLabel(entry) {
  if (!entry.family) return entry.label || entry.key;
  // The split writes the row's own label on every variant; a variant
  // named "tiny a" rather than "3" has no trailing number to strip.
  if (entry.familyLabel) return entry.familyLabel;
  return String(entry.label || entry.key).replace(/ [0-9]+$/, "");
}

// One variant of a family, or the type itself when it is one already.
// Takes the caller's random when it has one, so a scatter replays the
// same field from the same seed.
function pickVariant(type, random) {
  const members = familyMembers(type);
  if (!members.length) return type;
  const roll = random ? random() : Math.random();
  return members[Math.floor(roll * members.length) % members.length].key;
}

// A library folded to one entry per family, which is what a drawer shows.
// The folded entry borrows its first variant's file, so the thumbnail
// beside that file is the family's picture.
function familyEntries(entries) {
  const seen = new Map();
  for (const entry of entries || []) {
    const family = familyOf(entry);
    if (!seen.has(family)) {
      seen.set(family, Object.assign({}, entry,
        { key: family, label: familyLabel(entry), variants: 1 }));
    } else {
      seen.get(family).variants += 1;
    }
  }
  return [...seen.values()];
}

// The plan radius of one item, from the manifest's own bounds. sizeMetres
// is the model's [x, y, z] in ITS space, where y is up, so the footprint is
// x and z and the height is y. Getting that pair the wrong way round makes
// a 15 cm root plate claim to be two metres tall.
function propFootprint(type) {
  const entry = propEntry(type);
  if (!entry || !entry.sizeMetres) return 0.5;
  return Math.max(entry.sizeMetres[0], entry.sizeMetres[2]) / 2 || 0.5;
}

// How tall one item stands, from the same bounds: y is its height.
function propStature(type) {
  const entry = propEntry(type);
  if (!entry || !entry.sizeMetres) return 1;
  return entry.sizeMetres[1] || 1;
}

function propTriangles(type) {
  const entry = propEntry(type);
  return (entry && entry.triangles) || 20000;
}

// Everything already standing that a new item must not grow through: the
// vault and its works, plus every prop already placed. Boxes rather than
// meshes, because this runs once per candidate and a Box3 test is a
// handful of compares.
// ---------- the keep-out index ----------
// A uniform grid over the keep-out discs, so a dart asks only the cells it
// could touch. Every dart used to walk EVERY disc, and a dart-throwing
// fill throws far more darts than it lands: with 25,000 props down a
// 4,000-dart stamp was a hundred million distance tests, and the brush
// felt glued to the floor. A disc is filed in every cell it overlaps and a
// dart asks every cell its own disc overlaps, so the answer is exact
// whatever the sizes; a 15 m tree files itself in 900 cells, once.
const KEEP_OUT_CELL = 1;   // metres
// How much smaller than what is being planted a thing has to be before
// it is simply stepped over. A third: grass at 0.1 m does not keep out a
// tree at 3 m, and does keep out another blade of grass. Generous enough
// that two props of roughly a size still avoid one another, which is the
// interpenetration the keep-out exists to prevent.
const STEP_OVER_RATIO = 3;

// WHAT A THING KEEPS OUT DEPENDS ON HOW BIG THE NEWCOMER IS. Param,
// 2026-09-13: "we still are placing objects around other objects, so
// around every tree with a circle radius no grass or plants can be placed
// near it ... it might be that only the grass can be placed anywhere under
// or much closer to any collision geometry, or we redefine the collision
// geometry to be more dramatic."
//
// A tree filed one disc the size of its CROWN, and a blade of grass was
// refused anywhere inside it: a bare circle two and a half metres across
// under every beech, which is what he saw. What stands on the ground under
// a tree is its trunk. So a thing files two discs when its base is
// narrower than its crown: the crown, for anything of a size with it, and
// the base, for anything much smaller (by the same third that decides a
// step-over). Grass grows up to the bark; a tree still keeps its distance
// from a tree. The works do the same: their plan capsule keeps out trees,
// and only where they meet the floor keeps out the ground cover, so grass
// runs under the arch up to the springings and the column feet.
const KEEP_ALL = 0;     // one disc for everything: most things, and grass
const KEEP_CROWN = 1;   // tested only by things not much smaller
const KEEP_BASE = 2;    // tested only by things much smaller

function keepOutIndex() {
  return { cells: new Map(), discs: [], seen: [], pass: 0 };
}

function keepOutKey(ix, iy) {
  // Two 21-bit halves in one double, exact to two million cells a side.
  return (ix + 1048576) * 2097152 + (iy + 1048576);
}

// `own` is how big the thing that filed the disc actually is, which
// decides what it is entitled to keep out. Defaults to the disc's own
// radius, which is right for the works: a vault keeps out everything.
function keepOutAdd(index, x, y, r, own = r, role = KEEP_ALL) {
  const id = index.discs.length;
  index.discs.push([x, y, r, own, role]);
  index.seen.push(0);
  const x0 = Math.floor((x - r) / KEEP_OUT_CELL);
  const x1 = Math.floor((x + r) / KEEP_OUT_CELL);
  const y0 = Math.floor((y - r) / KEEP_OUT_CELL);
  const y1 = Math.floor((y + r) / KEEP_OUT_CELL);
  for (let ix = x0; ix <= x1; ix++) {
    for (let iy = y0; iy <= y1; iy++) {
      const key = keepOutKey(ix, iy);
      const bucket = index.cells.get(key);
      if (bucket) bucket.push(id); else index.cells.set(key, [id]);
    }
  }
}

// True when a disc of the given radius at (x, y) touches nothing filed.
// A disc filed in several cells is tested once: the pass number marks it.
function keepOutClear(index, x, y, radius, own = radius) {
  const pass = ++index.pass;
  const x0 = Math.floor((x - radius) / KEEP_OUT_CELL);
  const x1 = Math.floor((x + radius) / KEEP_OUT_CELL);
  const y0 = Math.floor((y - radius) / KEEP_OUT_CELL);
  const y1 = Math.floor((y + radius) / KEEP_OUT_CELL);
  for (let ix = x0; ix <= x1; ix++) {
    for (let iy = y0; iy <= y1; iy++) {
      const bucket = index.cells.get(keepOutKey(ix, iy));
      if (!bucket) continue;
      for (let i = 0; i < bucket.length; i++) {
        const id = bucket[i];
        if (index.seen[id] === pass) continue;
        index.seen[id] = pass;
        const d = index.discs[id];
        // GROUND COVER IS STEPPED OVER. Param, 2026-09-13: "the scatter
        // objects doesnt allow me to place other objects on top. I
        // understand the logic, but it means i cant place trees into a
        // space ive filled with grass."
        //
        // Every placed prop used to file a disc that kept out anything
        // whose centre came near it, whatever the two sizes were. With
        // 930,429 blades of grass on the ground -- his own scene,
        // measured -- the discs tile the whole site and nothing larger
        // can be planted anywhere at all. A tree is not planted BETWEEN
        // blades of grass; it is planted over them, which is what this
        // one comparison says. Grass still keeps out grass, and a tree
        // still keeps out a tree, because those are of a size with one
        // another.
        if (d[3] * STEP_OVER_RATIO < radius) continue;
        // UNDER A CANOPY: a newcomer much smaller than the disc's owner
        // meets its base and not its crown, and one of a size with it
        // meets its crown, which holds the base inside it anyway.
        const under = own * STEP_OVER_RATIO < d[3];
        if (d[4] === KEEP_CROWN && under) continue;
        if (d[4] === KEEP_BASE && !under) continue;
        const dx = x - d[0];
        const dy = y - d[1];
        const reach = d[2] + radius;
        if (dx * dx + dy * dy < reach * reach) return false;
      }
    }
  }
  return true;
}

// A prop's keep-out: its crown at the spacing the dial asks for, and its
// base where the base is narrower. Grass, whose base is its whole
// footprint, files the one disc it always did.
function keepOutAddProp(index, x, y, type, scale, spacing) {
  const own = propFootprint(type) * scale;
  const crown = own * spacing;
  const base = propBaseRadius(type) * scale;
  if (base >= crown) {
    keepOutAdd(index, x, y, crown, own);
    return;
  }
  keepOutAdd(index, x, y, crown, own, KEEP_CROWN);
  keepOutAdd(index, x, y, base, own, KEEP_BASE);
}

// How wide a model stands where it meets the ground: the furthest any of
// its vertices in the lowest slice reaches from its origin. The slice is
// 0.3 m, or a tenth of the model's height for anything under three metres,
// so a trunk's flare is measured and a sapling's lowest leaves are not.
// Measured once per model and kept. Before its model has arrived a type
// answers with its whole footprint, which is the old, cautious disc.
const BASE_SLICE_METRES = 0.3;
const BASE_SLICE_SHARE = 0.1;
const propBaseRadii = new Map();

function propBaseRadius(type) {
  if (propBaseRadii.has(type)) return propBaseRadii.get(type);
  const footprint = propFootprint(type);
  const template = propTemplates.get(type);
  if (!template) return footprint;
  template.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(template);
  if (box.isEmpty()) return footprint;
  const slice = box.min.z + Math.min(BASE_SLICE_METRES,
    (box.max.z - box.min.z) * BASE_SLICE_SHARE);
  const point = new THREE.Vector3();
  let reach = 0;
  template.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    const position = child.geometry.getAttribute("position");
    if (!position) return;
    for (let i = 0; i < position.count; i++) {
      point.fromBufferAttribute(position, i).applyMatrix4(child.matrixWorld);
      if (point.z > slice) continue;
      const r = Math.hypot(point.x, point.y);
      if (r > reach) reach = r;
    }
  });
  const radius = reach > 0 ? Math.min(reach, footprint) : footprint;
  propBaseRadii.set(type, radius);
  return radius;
}

// Where the works meet the floor, as small discs on a half-metre grid: a
// cell holds one wherever a vertex stands within the lowest slice. The
// plan capsule above keeps out what is too big to stand under the works;
// these keep the ground cover off the springings, the column feet and the
// anchors, and nowhere else.
const WORKS_CONTACT_CELL = 0.5;
const WORKS_CONTACT_SLICE = 0.3;
const WORKS_CONTACT_MARGIN = 0.1;
const worksContactCells = new WeakMap();

function worksContact(part) {
  if (worksContactCells.has(part)) return worksContactCells.get(part);
  part.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(part);
  const cells = new Map();
  if (!box.isEmpty()) {
    const floor = box.min.z + WORKS_CONTACT_SLICE;
    const point = new THREE.Vector3();
    const instance = new THREE.Matrix4();
    const file = (mesh, matrix) => {
      const position = mesh.geometry.getAttribute("position");
      if (!position) return;
      for (let i = 0; i < position.count; i++) {
        point.fromBufferAttribute(position, i).applyMatrix4(matrix);
        if (point.z > floor) continue;
        const ix = Math.floor(point.x / WORKS_CONTACT_CELL);
        const iy = Math.floor(point.y / WORKS_CONTACT_CELL);
        cells.set(ix + "," + iy, [ix, iy]);
      }
    };
    part.traverse((child) => {
      if (!child.isMesh || !child.geometry) return;
      if (child.isInstancedMesh) {
        for (let k = 0; k < child.count; k++) {
          child.getMatrixAt(k, instance);
          file(child, instance.premultiply(child.matrixWorld));
        }
      } else {
        file(child, child.matrixWorld);
      }
    });
  }
  const contact = [...cells.values()];
  worksContactCells.set(part, contact);
  return contact;
}

function scatterKeepOut(clearance, spacing) {
  const index = keepOutIndex();
  const box = new THREE.Box3();
  const parts = [state.objects.shell, state.objects.columns,
    state.objects.falsework, machineObjects && machineObjects.permanent].filter(Boolean);
  for (const part of parts) {
    box.setFromObject(part);
    if (!isFinite(box.min.x)) continue;
    // A CAPSULE, not one disc. One disc of half the diagonal round a
    // 23 m by 4 m vault claimed a 12 m circle and nothing could be
    // planted along either long side, which read as "nothing fitted"
    // as often as the spacing did. A row of discs the width of the
    // SHORT side, stepped along the long one, hugs the works instead.
    const w = box.max.x - box.min.x;
    const h = box.max.y - box.min.y;
    const along = w >= h ? "x" : "y";
    const short = Math.min(w, h);
    const long = Math.max(w, h);
    const r = short / 2 + clearance;
    const steps = Math.max(1, Math.ceil((long - short) / Math.max(0.5, short / 2)));
    for (let i = 0; i <= steps; i++) {
      const t = steps ? i / steps : 0.5;
      const cx = along === "x"
        ? box.min.x + short / 2 + t * (long - short) : (box.min.x + box.max.x) / 2;
      const cy = along === "y"
        ? box.min.y + short / 2 + t * (long - short) : (box.min.y + box.max.y) / 2;
      keepOutAdd(index, cx, cy, r, r, KEEP_CROWN);
    }
    // And where it meets the floor, for what can grow under it.
    const reach = WORKS_CONTACT_CELL * Math.SQRT1_2 + WORKS_CONTACT_MARGIN;
    for (const [ix, iy] of worksContact(part)) {
      keepOutAdd(index, (ix + 0.5) * WORKS_CONTACT_CELL, (iy + 0.5) * WORKS_CONTACT_CELL,
        reach, r, KEEP_BASE);
    }
  }
  // A placed prop keeps out by ITS OWN size and the CURRENT spacing. It
  // used to keep out by a fixed 0.6 of its footprint, which ignored both
  // the dial and its scale, so a second stroke could never touch a first
  // one however low the spacing was set.
  const gap = spacing || 1;
  for (const record of state.props) {
    keepOutAddProp(index, record.x, record.y, record.type, record.scale || 1, gap);
  }
  return index;
}

// Dart throwing against a growing list, with a share of the darts thrown
// NEXT TO an item already placed rather than anywhere in the region. That
// second kind is the clumping: at 0 the field is even, at 100 it gathers
// into stands with open ground between, which is what makes planting read
// as planting rather than as sprinkling.
function scatterSolve(region, salt, strokeKeepOut) {
  const rules = state.scatter;
  const chosen = rules.species.filter((s) => familyMembers(s.type).length);
  if (!chosen.length) return { items: [], note: "no species chosen" };
  // The salt is what makes a second click deal DIFFERENT points. Without
  // it a brush clicked twice in one spot re-deals the same arrangement,
  // every point lands on a prop that is now a keep-out disc, and every
  // one is refused: the field would simply stop thickening. Mixed rather
  // than replaced, so the seed still owns the result.
  const random = scatterRandom(
    (rules.seed ^ Math.imul(salt || 0, 0x9E3779B1)) >>> 0);
  const total = chosen.reduce((sum, s) => sum + Math.max(1, s.weight), 0);
  const pick = () => {
    let roll = random() * total;
    for (const s of chosen) {
      roll -= Math.max(1, s.weight);
      if (roll <= 0) return s.type;
    }
    return chosen[chosen.length - 1].type;
  };

  // A stroke keeps ONE index for all its stamps (runScatter hands it
  // back): rebuilt per stamp, it was a pass over every placed prop twenty
  // times a sweep. What each stamp places is filed in it as it lands.
  const keepOut = strokeKeepOut || scatterKeepOut(rules.clearance, rules.spacing);
  const placed = [];
  let triangles = 0;
  let refused = 0;
  const area = region.kind === "disc"
    ? Math.PI * region.r * region.r
    : Math.abs(region.x1 - region.x0) * Math.abs(region.y1 - region.y0);
  // Enough darts to fill the area at the tightest spacing, capped so a
  // huge region cannot spin the tab. Every dart is one cheap test.
  // A hundred per square metre, up from forty: once the rows were split
  // a tuft is twenty centimetres across and forty darts a metre left
  // most of the gaps between them untried (Param: "higher percentage
  // of landing somewhere fresh").
  const darts = Math.min(250000, Math.max(4000, Math.round(area * 100)));
  const clumpShare = rules.clump / 100;

  for (let i = 0; i < darts; i++) {
    if (placed.length >= SCATTER_MAX_ITEMS) break;
    if (triangles >= SCATTER_BUDGET_TRIANGLES) break;
    let x, y;
    if (placed.length && random() < clumpShare) {
      const near = placed[Math.floor(random() * placed.length)];
      const angle = random() * Math.PI * 2;
      const reach = random() * rules.clumpSize / 2;
      x = near.x + Math.cos(angle) * reach;
      y = near.y + Math.sin(angle) * reach;
    } else if (region.kind === "disc") {
      const angle = random() * Math.PI * 2;
      const reach = Math.sqrt(random()) * region.r;
      x = region.x + Math.cos(angle) * reach;
      y = region.y + Math.sin(angle) * reach;
    } else {
      x = region.x0 + random() * (region.x1 - region.x0);
      y = region.y0 + random() * (region.y1 - region.y0);
    }
    if (!withinRegion(region, x, y)) { refused += 1; continue; }
    // The family is chosen by weight; the VARIANT is drawn from the same
    // seeded stream, so its footprint is its own and a replay deals the
    // same shapes.
    const type = pickVariant(pick(), random);
    const scale = rules.sizeMin + random() * (rules.sizeMax - rules.sizeMin);
    const own = propFootprint(type) * scale;
    const radius = own * rules.spacing;
    if (!keepOutClear(keepOut, x, y, radius, own)) { refused += 1; continue; }
    keepOutAddProp(keepOut, x, y, type, scale, rules.spacing);
    placed.push({ type, x, y, scale,
      rotation: rules.turn ? random() * Math.PI * 2 : 0 });
    triangles += propTriangles(type);
  }
  const stopped = placed.length >= SCATTER_MAX_ITEMS ? "the six thousand item cap"
    : triangles >= SCATTER_BUDGET_TRIANGLES ? "the triangle budget"
      : null;
  return { items: placed, triangles, refused, stopped, keepOut };
}

function withinRegion(region, x, y) {
  if (region.kind === "disc") {
    return Math.hypot(x - region.x, y - region.y) <= region.r;
  }
  return x >= Math.min(region.x0, region.x1) && x <= Math.max(region.x0, region.x1)
    && y >= Math.min(region.y0, region.y1) && y <= Math.max(region.y0, region.y1);
}

async function runScatter(region, options) {
  const rules = state.scatter;
  const settings = options || {};
  if (!rules.species.length) { paintScatter(); return; }
  // Every template has to be in hand BEFORE placing, or placeProp falls
  // back to makeProp and plants a primitive instead of the model.
  for (const s of rules.species) {
    for (const member of familyMembers(s.type)) await ensurePropTemplate(member.key);
  }

  const solved = scatterSolve(region, settings.salt,
    settings.stroke ? settings.stroke.keepOut : null);
  if (settings.stroke) settings.stroke.keepOut = solved.keepOut;
  if (!solved.items.length) {
    document.getElementById("scatter-readout").textContent =
      settings.stroke
        ? "no more will fit there: loosen the spacing or widen the brush"
        : "nothing fitted: loosen the spacing, or draw a bigger area";
    return;
  }
  // Every placement lands on the open layer (placementLayer), and a scatter
  // never opens another. A redo names the layer its first run landed on,
  // so it lands there again even when another layer is open by then.
  const target = settings.intoLayer && layerById(settings.intoLayer)
    ? { layer: layerById(settings.intoLayer), minted: null } : placementLayer();
  const home = target.layer;
  showLayerForPlacing(home);
  // The layer this run made, if it had to make one, or the one a redo was
  // handed back: the undo entry that owns it takes it away once empty.
  const owns = target.minted || settings.owns || null;
  const records = solved.items.map((item) => placeProp(
    item.type, item.x, item.y, item.rotation, false, item.scale));
  // Which scatter these belong to: decided once per stroke, and handed
  // back to a redo so it paints into the same one it painted before.
  const stroke = settings.stroke || null;
  if (stroke && !stroke.scatterId) stroke.scatterId = settings.scatterId || scatterIdFor(home.id);
  const scatterId = stroke ? stroke.scatterId : (settings.scatterId || scatterIdFor(home.id));
  // placeProp stamps the open layer; a redo aimed at another re-stamps.
  for (const record of records) {
    record.layer = home.id;
    record.scatter = scatterId;
    record.object.visible = layerVisible(home.id);
  }
  clearPlantings();
  solved.home = home;
  if (settings.stroke) {
    // One stamp of a brush stroke. The stroke owns the undo entry, the
    // run and the save: they happen once, when the pointer lifts.
    const stroke = settings.stroke;
    for (const record of records) stroke.records.push(record);
    if (!stroke.run) {
      stroke.run = { layer: home.id, records: stroke.records };
      state.scatterRuns.push(stroke.run);
    }
    // Every stamp of the stroke, as it lands: the run grows while the
    // pointer is down and its members have to know their run the whole
    // time, not only once it lifts.
    markScatterRun(stroke.run, records);
    if (owns) stroke.run.minted = owns;
    paintScatter(solved);
    return;
  }
  const run = { layer: home.id, records, minted: owns };
  markScatterRun(run);
  state.scatterRuns.push(run);
  // The redo names its layer outright. Replaying the first fill's own
  // settings, whose intoLayer was null, is what used to mint a second
  // "Scatter 1" and split one session across two layers.
  let at = -1;
  pushUndo("scattering " + records.length + " props", () => {
    removePropRecords(records);
    state.scatterRuns = state.scatterRuns.filter((other) => other.records !== records);
    at = dropLayerIfEmpty(owns);
    paintScatter();
    refreshLayersShelf();
  }, () => {
    if (owns && at >= 0) reinstateLayer(owns, at);
    return runScatter(region, Object.assign({}, settings,
      { intoLayer: home.id, owns, scatterId }));
  });
  // The run holds the entry it has just pushed, so Remove last can take
  // the two away together.
  run.entry = undoHistory[undoHistory.length - 1];
  saveProps();
  renderShelf();
  logStudio("scattered " + records.length + " props onto " + home.name);
  paintScatter(solved);
}

function paintScatter(solved) {
  const readout = document.getElementById("scatter-readout");
  if (!readout) return;
  const rules = state.scatter;
  document.getElementById("scatter-undo-last").disabled = !state.scatterRuns.length;
  if (!rules.species.length) {
    readout.textContent = "pick one or more species to scatter";
    return;
  }
  if (!solved) {
    const names = rules.species.map((s) => {
      const entry = propEntry(s.type);
      return (entry ? entry.label || entry.key : s.type) + " x" + s.weight;
    });
    readout.textContent = names.join(", ")
      + "  --  brush it on, or drag an area, onto " + placingOntoName();
    return;
  }
  readout.textContent = solved.items.length + " placed onto "
    + (solved.home ? solved.home.name : placingOntoName()) + ", "
    + (solved.triangles / 1e6).toFixed(1) + " M triangles"
    + (solved.stopped ? "  --  stopped at " + solved.stopped
      + ", loosen the spacing or pick something lighter" : "");
}

// The species grid. Only what is worth scattering: the manifest's own
// height rules out a 48 m forest scan, and a lamp is refused outright
// because each one is a real PointLight and the light count is baked into
// every shader program's cache key.
// Where a shift-click measures its run from: the last tile clicked
// WITHOUT shift. Kept outside the render so it survives the redraw that
// every click causes.
let scatterAnchor = null;
// The group the species grid is showing (Param: "on scatter can we also
// put the categories into the clickable menus like we have with the props
// and materials"). Its own variable, NOT shelfCategory: openShelf resets
// that one to "all", and the brush and the area put the drawer away and
// bring it back through openShelf("scatter") on Escape, so sharing it
// would drop his group after every stroke.
let scatterCategory = "all";

function renderShelfScatter() {
  const grid = document.getElementById("scatter-species");
  const chosen = document.getElementById("scatter-chosen");
  if (!grid || !chosen) return;
  grid.innerHTML = "";
  // In the manifest's own groups, headed, like the Props drawer: a
  // hundred ungrouped tiles is a pile, and he asked for categories.
  // Within a group, shortest first, because that is the order someone
  // building a field reaches for them in.
  // No height ceiling any more. A 12 m cut hid the five beech forest
  // trees and the study tree, which was the first thing Param noticed
  // missing; spacing is a multiple of each item's own width, so a 30 m
  // tree keeps a 36 m clearance of its own accord and needs no fence.
  const ordered = familyEntries(state.propLibrary)
    .filter((entry) => !LAMP_TYPES.has(entry.key))
    .sort((a, b) =>
      String(a.group || "other").localeCompare(String(b.group || "other"))
      || (a.sizeMetres ? a.sizeMetres[1] : 0) - (b.sizeMetres ? b.sizeMetres[1] : 0));
  // The groups as chips in the drawer head, the way Props and Materials
  // offer theirs: "all" first, then only the groups this list holds, in
  // its own order, so no chip opens onto an empty grid. They are drawn
  // here rather than in renderShelf because every tile click redraws
  // through this function alone.
  const cats = document.getElementById("shelf-cats");
  const groups = [...new Set(ordered.map((e) => e.group || "other"))];
  if (!groups.includes(scatterCategory)) scatterCategory = "all";
  if (cats) shelfChips(cats, ["all", ...groups], scatterCategory, (name) => {
    scatterCategory = name;
    renderShelfScatter();
  });
  const shown = scatterCategory === "all" ? ordered
    : ordered.filter((e) => (e.group || "other") === scatterCategory);
  let group = null;
  for (const entry of shown) {
    if ((entry.group || "other") !== group) {
      group = entry.group || "other";
      const heading = document.createElement("span");
      heading.className = "tile-family";
      heading.textContent = group;
      grid.appendChild(heading);
    }
    const tile = previewTile("scatter-" + entry.key, entry.label || entry.key,
      (canvasEl) => {
        fillFlat(canvasEl, new THREE.Color(0x2a2e34));
        const picture = new Image();
        picture.onload = () => canvasEl.getContext("2d")
          .drawImage(picture, 0, 0, canvasEl.width, canvasEl.height);
        picture.onerror = () => ensurePropTemplate(entry.key)
          .then((template) => { if (template) renderObjectPreview(template, canvasEl); });
        picture.src = "/api/props/" + encodeURIComponent(entry.file + ".thumb.png");
      });
    // The label lies about size and the size is what decides whether a
    // thing is scatterable: "Pine roots" is a 15 cm root plate 1.9 m
    // across. So the real dimensions go on the tile.
    const size = entry.sizeMetres;
    tile.title = (entry.label || entry.key)
      + (size ? "  " + size[1].toFixed(2) + " m tall, "
        + Math.max(size[0], size[2]).toFixed(2) + " m across" : "")
      + (entry.variants > 1 ? "  --  " + entry.variants + " variants" : "")
      + "  --  " + (entry.triangles || 0).toLocaleString() + " triangles";
    tile.classList.toggle("active",
      state.scatter.species.some((s) => s.type === entry.key));
    // SHIFT takes the run from the last one clicked to this one, the way
    // a file list does (Param: "if i select a thumb nail ... and scroll
    // down then shift and click i expect it to also select all the object
    // from clicked point 1 to clicked point 2"). The run is over what is
    // ON SCREEN in this order, not over the library, so a heading between
    // two tiles is simply skipped rather than ending the run, and a run
    // under one group chip stays inside that group.
    const here = entry.key;
    tile.addEventListener("click", (event) => {
      const keys = shown.map((item) => item.key);
      const chosenNow = new Set(state.scatter.species.map((sp) => sp.type));
      if (event.shiftKey && scatterAnchor && keys.includes(scatterAnchor)) {
        const from = keys.indexOf(scatterAnchor);
        const to = keys.indexOf(here);
        const lo = Math.min(from, to);
        const hi = Math.max(from, to);
        // A range ADDS. Shift-clicking to widen a selection that then
        // dropped half of it would be its own small betrayal.
        for (let i = lo; i <= hi; i++) {
          if (!chosenNow.has(keys[i])) {
            state.scatter.species.push({ type: keys[i], weight: 1 });
            chosenNow.add(keys[i]);
          }
        }
      } else {
        const at = state.scatter.species.findIndex((sp) => sp.type === here);
        if (at >= 0) state.scatter.species.splice(at, 1);
        else state.scatter.species.push({ type: here, weight: 1 });
        scatterAnchor = here;
      }
      renderShelfScatter();
    });
    grid.appendChild(tile);
  }
  // The chosen species, each with how often it appears, and one way out
  // of the whole selection (Param: "in scatter mode, deselect all needs
  // to be there"). This is the WHOLE mix, whatever group chip is lit:
  // a species picked under another group keeps its pill, its weight and
  // its cross while he browses this one.
  chosen.innerHTML = "";
  if (state.scatter.species.length) {
    const clear = document.createElement("button");
    clear.id = "scatter-deselect";
    clear.textContent = "Deselect all";
    clear.title = "Take every species out of the mix";
    clear.addEventListener("click", () => {
      state.scatter.species = [];
      renderShelfScatter();
    });
    chosen.appendChild(clear);
  }
  for (const species of state.scatter.species) {
    const entry = familyMembers(species.type)[0] || propEntry(species.type);
    const chip = document.createElement("span");
    chip.className = "scatter-chip";
    const name = document.createElement("span");
    name.textContent = entry ? familyLabel(entry) : species.type;
    const weight = document.createElement("input");
    weight.type = "number";
    weight.min = "1";
    weight.max = "9";
    weight.value = String(species.weight);
    weight.title = "How often this one appears, against the others";
    weight.addEventListener("input", () => {
      species.weight = Math.max(1, Math.min(9, +weight.value || 1));
      paintScatter();
    });
    const drop = document.createElement("button");
    drop.textContent = "✕";
    drop.title = "Take this one out of the mix";
    drop.addEventListener("click", () => {
      state.scatter.species = state.scatter.species
        .filter((s) => s !== species);
      renderShelfScatter();
    });
    chip.append(name, weight, drop);
    chosen.appendChild(chip);
  }
  syncScatterControls();
  paintScatter();
}

// The dials, from the rules. Without this a restored layout brings back
// his species and his seed while every slider still shows the default,
// which is the "dial states a value the scene does not have" fault the
// interface language names in section 3.
function syncScatterControls() {
  const rules = state.scatter;
  const write = (id, value, digits, suffix) => {
    const input = document.getElementById(id);
    if (!input) return;
    input.value = value;
    paintScrub(input);
    const reading = document.getElementById(id + "-value");
    if (reading) reading.textContent = (+value).toFixed(digits) + (suffix || "");
  };
  write("scatter-radius", rules.radius, 1);
  write("scatter-spacing", rules.spacing, 2);
  write("scatter-clump", rules.clump, 0);
  write("scatter-clump-size", rules.clumpSize, 1);
  write("scatter-clearance", rules.clearance, 2);
  const low = document.getElementById("scatter-size-min");
  const high = document.getElementById("scatter-size-max");
  if (low && high) {
    low.value = rules.sizeMin;
    high.value = rules.sizeMax;
    paintScrub(low);
    paintScrub(high);
    document.getElementById("scatter-size-value").textContent =
      rules.sizeMin.toFixed(2) + " to " + rules.sizeMax.toFixed(2);
  }
  const turn = document.getElementById("scatter-turn");
  if (turn) turn.value = String(rules.turn);
  const seed = document.getElementById("scatter-seed");
  if (seed) seed.value = String(rules.seed);
}

// Dragging the region. Its listeners go on in CAPTURE phase and come off
// again the moment the drag ends, rather than being woven into the
// existing pointer handling: OrbitControls binds its own pointerdown at
// boot and the studio's prop handling binds another, so anything that
// merely listens later sees a press both of them have already acted on.
let scatterDrag = null;
// The area tool, as Param asked for it once the brush worked: "i drag the
// area it spawns one lot the block rectangle still stays and if i keep
// clicking it continues adding objects, then if i click and drag on a new
// area i can continue placing up until i press esc". So it stays in hand
// after a fill: the rectangle stays on the floor (scatterDrag), a click
// fills it again with a fresh deal, a DRAG draws a new one, and Escape is
// the way out.
//
// A press only becomes a drag once it has travelled this far ("make sure
// the click and drag has enough of a false start so it doesnt make the
// rectangles too easily ... more than 10px"). Twelve is past the wobble of
// a firm click with a mouse or a pen and still only a few millimetres of
// hand; a fingertip wobbles more, so a touch needs twice it.
const AREA_DRAG_PX = 12;
const AREA_DRAG_PX_TOUCH = 24;
let areaPress = null;   // the press in hand: where it began, and whether it became a drag
let scatterOutline = null;

function showScatterOutline(region) {
  hideScatterOutline();
  if (!region) return;
  const points = [];
  if (region.kind === "disc") {
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      points.push(new THREE.Vector3(region.x + Math.cos(a) * region.r,
        region.y + Math.sin(a) * region.r, groundLevel() + 0.005));
    }
  } else {
    const z = groundLevel() + 0.005;
    points.push(new THREE.Vector3(region.x0, region.y0, z),
      new THREE.Vector3(region.x1, region.y0, z),
      new THREE.Vector3(region.x1, region.y1, z),
      new THREE.Vector3(region.x0, region.y1, z),
      new THREE.Vector3(region.x0, region.y0, z));
  }
  scatterOutline = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({ color: 0x93a6bb, depthTest: false, fog: false }));
  scatterOutline.renderOrder = 3;
  // In the SCENE, never in propsGroup: propRecordAt raycasts that group
  // recursively and a stray pickable child there causes a wrong selection
  // rather than a clean miss, which is why the prop outline's raycast is
  // a no-op too.
  scatterOutline.raycast = () => {};
  scene.add(scatterOutline);
}

function hideScatterOutline() {
  if (!scatterOutline) return;
  scene.remove(scatterOutline);
  scatterOutline.geometry.dispose();
  scatterOutline.material.dispose();
  scatterOutline = null;
}

// ---------- the brush ----------
// Param: "its just a circle overlay that stays on the ground and follows
// the mouse around, it scatter the objects in its radius when i click.
// clicking multiple times over an already scattered space increases its
// density still trying to avoid collision".
//
// The densifying falls out of the solver rather than being coded twice:
// scatterKeepOut already reads EVERY placed prop as a keep-out disc, so a
// second stroke over the same ground can only land in the gaps the first
// one left. What it needed was a fresh deal per click, which is the salt.
let scatterBrushAt = null;

// A CLICK IS NOT A DRAG, and the orbit stays live while painting. The
// first cut disabled OrbitControls the moment a tool was armed, which
// meant a field could only be painted from wherever the camera already
// stood (Param: "please allow me to move around the viewport freely dont
// lock me otherwise how can i brush and draw an area i need thats out of
// viewport. make sure the clicking to move and clicking to place are
// different"). So the tools now watch pointerdown and pointerup and act
// only on a press that did not travel: a press that moved is the orbit's,
// and the orbit already had it.
// That lasted one morning. Param: "the double click is wrong because i
// want to drag the brush around etc. so lets stick with left click and
// have right click still to pan and scroll to zoom". So while a tool is
// armed the LEFT button is the tool's: a press paints, a drag keeps
// painting along the path, a release ends the stroke. The camera keeps
// the other two, middle to orbit and right to pan, and the wheel zooms,
// so ground the stroke needs can be brought on screen without letting go
// of the tool. Disarming hands the left button back to the orbit. On a
// touch screen one finger is the tool and two fingers zoom and pan.
const ORBIT_BUTTONS = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY,
  RIGHT: THREE.MOUSE.PAN };
const TOOL_BUTTONS = { LEFT: null, MIDDLE: THREE.MOUSE.ROTATE,
  RIGHT: THREE.MOUSE.PAN };
const ORBIT_TOUCHES = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
const TOOL_TOUCHES = { ONE: null, TWO: THREE.TOUCH.DOLLY_PAN };
// How far the brush travels between stamps, as a share of its radius.
// Half: the discs overlap, so a stroke is a continuous band rather than
// a string of beads, and the keep-out stops the overlap doubling up.
const BRUSH_STEP = 0.5;
// The stroke in hand: the pointer that owns it, where it last stamped,
// every stamp it made (region and salt, so a redo can replay it) and
// every record it placed (so ONE undo takes the whole stroke back).
let brushStroke = null;
// ONE queue for every stamp of every stroke. A second stroke begun while
// the first one's stamps still wait on their models would otherwise solve
// against a keep-out that never saw the first stroke's later stamps, and
// the two would plant through each other.
let scatterQueue = Promise.resolve();

function giveButtonsToTool(armed) {
  controls.mouseButtons = armed ? TOOL_BUTTONS : ORBIT_BUTTONS;
  controls.touches = armed ? TOOL_TOUCHES : ORBIT_TOUCHES;
}

function brushRegion() {
  if (!scatterBrushAt) return null;
  return { kind: "disc", x: scatterBrushAt.x, y: scatterBrushAt.y,
    r: state.scatter.radius };
}

function armScatterBrush() {
  if (state.scatterArmed === "brush") { disarmScatterArea(); return; }
  if (!state.scatter.species.length) {
    logStudio("scatter: pick a species first");
    return;
  }
  disarmScatterArea();
  state.scatterArmed = "brush";
  // The session paints onto the layer open now. Opening any other drawer
  // (the Layers tabs included) puts the tool down, so it cannot change
  // under the brush. Resolved, not revealed: arming shows nothing, so
  // taking the tool up and putting it down again leaves the layers as
  // they were, and the first stroke is what shows a hidden one.
  state.scatterBrushLayer = resolvePlacementLayer().layer.id;
  document.getElementById("scatter-brush").classList.add("active");
  document.getElementById("scatter-readout").textContent =
    "press and drag to paint onto " + placingOntoName()
    + "; middle-drag orbits, right-drag pans; Escape to stop";
  // The drawer gets out of the way: a brush needs the floor, and the
  // floor was under the tiles (Param: "the tiles are a bit in the way").
  // Escape or the button brings it back.
  closeShelf();
  logStudio("scatter: press and drag on the floor to paint, middle-drag to "
    + "orbit, right-drag to pan, Escape to stop");
  giveButtonsToTool(true);
  canvas.addEventListener("pointerdown", onBrushDown);
  canvas.addEventListener("pointermove", onBrushMove);
  canvas.addEventListener("pointerup", onBrushUp);
  canvas.addEventListener("pointercancel", onBrushUp);
  window.addEventListener("keydown", onScatterKey, true);
}

function onBrushDown(event) {
  if (event.button !== 0 || brushStroke) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  // The stroke follows the pointer off the canvas and back; without the
  // capture a fast sweep past the edge would end it.
  canvas.setPointerCapture(event.pointerId);
  brushStroke = { pointerId: event.pointerId, last: null, stamps: [],
    records: [], run: null, busy: Promise.resolve() };
  stampBrush(hit);
}

function onBrushMove(event) {
  const hit = groundPointAt(event);
  if (!hit) return;
  scatterBrushAt = { x: hit.x, y: hit.y };
  showScatterOutline(brushRegion());
  if (!brushStroke || !brushStroke.last) return;
  const step = state.scatter.radius * BRUSH_STEP;
  if (Math.hypot(hit.x - brushStroke.last.x, hit.y - brushStroke.last.y) >= step) {
    stampBrush(hit);
  }
}

// One stamp of the brush, with a fresh salt so it deals different points
// from the last, onto the layer taken when the brush was armed. Stamps
// queue behind each other because a stamp awaits its templates, and two
// running at once would solve against one keep-out.
function stampBrush(hit) {
  const stroke = brushStroke;
  stroke.last = { x: hit.x, y: hit.y };
  scatterBrushAt = { x: hit.x, y: hit.y };
  state.scatterStroke += 1;
  const stamp = { region: brushRegion(), salt: state.scatterStroke };
  stroke.stamps.push(stamp);
  stroke.busy = scatterQueue = scatterQueue.then(async () => {
    await runScatter(stamp.region, { salt: stamp.salt,
      intoLayer: state.scatterBrushLayer, stroke });
    // Painting must survive its own repaint: a redraw of the drawer would
    // otherwise leave the circle behind and the button unlit.
    if (state.scatterArmed === "brush") {
      document.getElementById("scatter-brush").classList.add("active");
      showScatterOutline(brushRegion());
    }
  // A stamp that throws must not stop every stamp queued behind it.
  }).catch((error) => logStudio("scatter: a stamp failed: " + error.message));
}

async function onBrushUp(event) {
  const stroke = brushStroke;
  if (!stroke || event.pointerId !== stroke.pointerId) return;
  brushStroke = null;
  try { canvas.releasePointerCapture(event.pointerId); } catch (error) { /* gone already */ }
  await stroke.busy;
  endBrushStroke(stroke);
}

// The whole stroke is ONE undo entry, however many stamps it took: a
// press, drag and release is one gesture to him, and forty entries for
// one sweep would make the Undo button a lottery. The redo replays the
// stamps, region and salt each, so it deals the same field.
function endBrushStroke(stroke) {
  // The stroke's keep-out index is the whole scene's, and the undo entry
  // below holds the stroke: fifty entries each keeping one was a leak.
  stroke.keepOut = null;
  const records = stroke.records;
  if (!records.length) return;
  const stamps = stroke.stamps;
  // The stroke's own layer: its redo paints back onto it, never onto
  // whatever is open by then, and never onto a fresh one.
  const homeId = records[0].layer;
  const owns = (stroke.run && stroke.run.minted) || null;
  let at = -1;
  pushUndo("painting " + records.length + " props", () => {
    removePropRecords(records);
    state.scatterRuns = state.scatterRuns.filter((run) => run !== stroke.run);
    at = dropLayerIfEmpty(owns);
    paintScatter();
    refreshLayersShelf();
  }, async () => {
    if (owns && at >= 0) reinstateLayer(owns, at);
    const replay = { pointerId: null, last: null, stamps: [], records: [],
      run: null, busy: Promise.resolve(), scatterId: records[0].scatter || 0 };
    for (const stamp of stamps) {
      replay.stamps.push(stamp);
      await runScatter(stamp.region, { salt: stamp.salt, intoLayer: homeId,
        owns, stroke: replay });
    }
    endBrushStroke(replay);
  });
  // The stroke's run holds its history entry, so Remove last can take
  // the two away together.
  if (stroke.run) stroke.run.entry = undoHistory[undoHistory.length - 1];
  saveProps();
  const home = layerById(homeId);
  logStudio("painted " + records.length + " props onto "
    + (home ? home.name : "the scatter"));
}

function armScatterArea() {
  if (state.scatterArmed === "area") { disarmScatterArea(); return; }
  disarmScatterArea();
  if (!state.scatter.species.length) {
    logStudio("scatter: pick a species first");
    return;
  }
  state.scatterArmed = "area";
  // Resolved, not revealed, as the brush does: the first fill shows a
  // hidden layer and says so, and an Escape before then has changed
  // nothing, so there is nothing to undo.
  state.scatterBrushLayer = resolvePlacementLayer().layer.id;
  scatterDrag = null;
  areaPress = null;
  document.getElementById("scatter-area").classList.add("active");
  document.getElementById("scatter-readout").textContent =
    "drag a rectangle to fill it onto " + placingOntoName()
    + ", click to fill it again, drag another to move on; "
    + "middle-drag orbits, right-drag pans; Escape to stop";
  closeShelf();
  logStudio("scatter: drag a rectangle on the floor to fill it, click to fill it "
    + "again, drag another to move on; middle-drag orbits, right-drag pans; Escape to stop");
  giveButtonsToTool(true);
  canvas.addEventListener("pointerdown", onAreaDown);
  canvas.addEventListener("pointermove", onAreaMove);
  canvas.addEventListener("pointerup", onAreaUp);
  canvas.addEventListener("pointercancel", onAreaUp);
  window.addEventListener("keydown", onScatterKey, true);
}

function disarmScatterArea() {
  const wasArmed = state.scatterArmed;
  state.scatterArmed = false;
  scatterDrag = null;
  areaPress = null;
  scatterBrushAt = null;
  state.scatterBrushLayer = null;
  // A stroke still in hand when the tool is put down keeps what it
  // painted, and still gets its one undo entry once its last stamp lands.
  const stroke = brushStroke;
  brushStroke = null;
  if (stroke) stroke.busy.then(() => endBrushStroke(stroke));
  hideScatterOutline();
  for (const id of ["scatter-area", "scatter-brush"]) {
    const button = document.getElementById(id);
    if (button) button.classList.remove("active");
  }
  giveButtonsToTool(false);
  canvas.removeEventListener("pointerdown", onBrushDown);
  canvas.removeEventListener("pointermove", onBrushMove);
  canvas.removeEventListener("pointerup", onBrushUp);
  canvas.removeEventListener("pointercancel", onBrushUp);
  canvas.removeEventListener("pointerdown", onAreaDown);
  canvas.removeEventListener("pointermove", onAreaMove);
  canvas.removeEventListener("pointerup", onAreaUp);
  canvas.removeEventListener("pointercancel", onAreaUp);
  window.removeEventListener("keydown", onScatterKey, true);
  // The drawer that was folded away for the tool comes back with it.
  if (wasArmed) openShelf("scatter");
  paintScatter();
}

// ONE Escape leaves the tool and brings the drawer back. The window's
// general Escape handler would close the drawer this has just reopened,
// so the event stops here, immediately, before it can be seen twice.
function onScatterKey(event) {
  if (event.key !== "Escape") return;
  event.stopImmediatePropagation();
  event.preventDefault();
  disarmScatterArea();
}

function onAreaDown(event) {
  if (event.button !== 0 || areaPress) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  canvas.setPointerCapture(event.pointerId);
  areaPress = { pointerId: event.pointerId, clientX: event.clientX,
    clientY: event.clientY, x0: hit.x, y0: hit.y, dragging: false,
    slop: event.pointerType === "touch" ? AREA_DRAG_PX_TOUCH : AREA_DRAG_PX };
}

// Nothing happens until the press has travelled past the false start.
// From then on the NEW rectangle follows the pointer from the pressed
// corner, so what will be filled is always on screen.
function onAreaMove(event) {
  const press = areaPress;
  if (!press || event.pointerId !== press.pointerId) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  if (!press.dragging) {
    const travelled = Math.hypot(event.clientX - press.clientX,
      event.clientY - press.clientY);
    if (travelled <= press.slop) return;
    press.dragging = true;
  }
  scatterDrag = { kind: "rect", x0: press.x0, y0: press.y0, x1: hit.x, y1: hit.y };
  showScatterOutline(scatterDrag);
  const w = Math.abs(scatterDrag.x1 - scatterDrag.x0);
  const h = Math.abs(scatterDrag.y1 - scatterDrag.y0);
  logStudio("scatter: " + w.toFixed(1) + " by " + h.toFixed(1) + " m so far");
}

// A drag fills the rectangle it drew; a click fills the one already on the
// floor again. Either way the tool stays in hand until Escape.
function onAreaUp(event) {
  const press = areaPress;
  if (!press || event.pointerId !== press.pointerId) return;
  areaPress = null;
  try { canvas.releasePointerCapture(event.pointerId); } catch (error) { /* gone already */ }
  if (event.type === "pointercancel") return;
  if (press.dragging) {
    const hit = groundPointAt(event);
    if (hit) { scatterDrag.x1 = hit.x; scatterDrag.y1 = hit.y; }
    if (Math.abs(scatterDrag.x1 - scatterDrag.x0) < 0.5
        || Math.abs(scatterDrag.y1 - scatterDrag.y0) < 0.5) {
      scatterDrag = null;
      hideScatterOutline();
      logStudio("scatter: that area was too small to fill");
      return;
    }
    showScatterOutline(scatterDrag);
  } else if (!scatterDrag) {
    logStudio("scatter: drag a rectangle first; a click fills the one on the floor again");
    return;
  }
  fillScatterArea();
}

// Every fill deals afresh (its own salt, as a brush stamp does) onto the
// layer taken when the tool was armed, and is its own undo entry. It
// queues behind any fill or stamp still waiting on its models, so a burst
// of clicks cannot solve two fills against one keep-out and plant them
// through each other.
function fillScatterArea() {
  const region = { kind: "rect", x0: scatterDrag.x0, y0: scatterDrag.y0,
    x1: scatterDrag.x1, y1: scatterDrag.y1 };
  state.scatterStroke += 1;
  const salt = state.scatterStroke;
  scatterQueue = scatterQueue.then(async () => {
    await runScatter(region, { salt, intoLayer: state.scatterBrushLayer });
    // A fill repaints the drawer, which would leave the rectangle and the
    // lit button behind while the tool is still in hand.
    if (state.scatterArmed === "area") {
      document.getElementById("scatter-area").classList.add("active");
      if (scatterDrag) showScatterOutline(scatterDrag);
    }
  }).catch((error) => logStudio("scatter: a fill failed: " + error.message));
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
  const chosen = stillPlaced([...gatheredProps]);
  if (!chosen.length) return;
  // The copies land on the open layer, shown if it was hidden.
  placementLayer();
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
    record.object.position.set(record.x, record.y, record.z || 0);
    notePropsMoved(record);
  }
}

function placeStampInstance(hit) {
  stampRig.placed += 1;
  const planted = stampRig.records.slice();
  pushUndo("placing " + planted.length + (planted.length === 1
    ? " copy" : " copies"), () => {
    removePropRecords(planted);
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

// ---------- the scatter's controls ----------
// Each slider writes its number and repaints the readout; none of them
// re-solves, because re-solving on every drag tick would place and remove
// thousands of props while his finger is still moving.
for (const [id, key, digits, suffix] of [
  ["scatter-spacing", "spacing", 2, "x"],
  ["scatter-clump", "clump", 0, ""],
  ["scatter-clump-size", "clumpSize", 1, ""],
  ["scatter-clearance", "clearance", 2, ""],
  ["scatter-radius", "radius", 1, ""],
]) {
  const input = document.getElementById(id);
  if (!input) continue;
  input.addEventListener("input", () => {
    state.scatter[key] = +input.value;
    const readout = document.getElementById(id + "-value");
    if (readout) readout.textContent = (+input.value).toFixed(digits) + suffix;
    if (key === "radius" && scatterBrushAt) showScatterOutline(brushRegion());
    paintScatter();
  });
}

function syncScatterSize() {
  const low = document.getElementById("scatter-size-min");
  const high = document.getElementById("scatter-size-max");
  state.scatter.sizeMin = Math.min(+low.value, +high.value);
  state.scatter.sizeMax = Math.max(+low.value, +high.value);
  document.getElementById("scatter-size-value").textContent =
    state.scatter.sizeMin.toFixed(2) + " to " + state.scatter.sizeMax.toFixed(2);
  paintScatter();
}
for (const id of ["scatter-size-min", "scatter-size-max"]) {
  const input = document.getElementById(id);
  if (input) input.addEventListener("input", syncScatterSize);
}

const scatterTurn = document.getElementById("scatter-turn");
if (scatterTurn) {
  scatterTurn.addEventListener("change", () => {
    state.scatter.turn = +scatterTurn.value;
  });
}

const scatterSeed = document.getElementById("scatter-seed");
if (scatterSeed) {
  scatterSeed.addEventListener("input", () => {
    state.scatter.seed = Math.max(1, +scatterSeed.value || 1);
  });
}

document.getElementById("scatter-dice").addEventListener("click", () => {
  // A fresh deal, said out loud in the box so the seed that produced a
  // field he liked can be typed back in.
  state.scatter.seed = 1 + Math.floor(Math.random() * 99998);
  scatterSeed.value = String(state.scatter.seed);
  paintScatter();
});

document.getElementById("scatter-area").addEventListener("click", armScatterArea);

document.getElementById("scatter-brush").addEventListener("click", armScatterBrush);

const skyBrightness = document.getElementById("sky-brightness");
if (skyBrightness) {
  skyBrightness.addEventListener("input", () => {
    state.skyBrightness = +skyBrightness.value / 100;
    document.getElementById("sky-brightness-value").textContent =
      Math.round(+skyBrightness.value);
    applySkyBrightness();
  });
}

document.getElementById("scatter-undo-last").addEventListener("click", () => {
  const run = state.scatterRuns.pop();
  if (!run) return;
  removePropRecords(run.records);
  // A run that had to make its layer takes it away once it leaves it
  // empty, exactly as its undo does.
  dropLayerIfEmpty(run.minted);
  // And the run's own history entry goes with it. Left standing, the
  // next Ctrl+Z would announce that it had undone a scatter that is
  // already gone and change nothing on screen, and the redo after that
  // would plant back the very props Remove last took away.
  const at = undoHistory.indexOf(run.entry);
  if (at >= 0) undoHistory.splice(at, 1);
  const back = redoHistory.indexOf(run.entry);
  if (back >= 0) redoHistory.splice(back, 1);
  saveProps();
  renderShelf();
  paintScatter();
  paintUndoButton();
  logStudio("removed the last scatter, " + run.records.length + " props");
});

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

// The atmosphere presets, each drawn by its own fog: the same integral the
// shader runs, per pixel, over an eye at head height, a low sun to the
// right and three arches standing off at the distances atmosphere.js
// sets. No WebGL, so the tiles cost no context and look the same on
// every device.
function paintAtmosphereTile(key, canvasEl) {
  const context = canvasEl.getContext("2d");
  const image = context.createImageData(canvasEl.width, canvasEl.height);
  image.data.set(atmospherePreviewPixels(canvasEl.width, canvasEl.height,
    atmosphereFromPreset(key)));
  context.putImageData(image, 0, 0);
}

// A tile's title carries its numbers, in the dials' own units.
function atmosphereTileTitle(key) {
  const preset = ATMOSPHERE_PRESETS[key];
  if (!preset || key === "none") {
    return "None: no atmosphere. Sky mode keeps the weather's own haze";
  }
  return preset.label + ": " + preset.density + " /km thinning every " + preset.height
    + " m, ground mist " + preset.mist + " /km over " + preset.mistHeight + " m, from "
    + preset.start + " m, hiding at most " + preset.maxOpacity + "%, sun glow "
    + preset.sunGlow + "%";
}

function buildAtmosphereTiles() {
  const holder = document.getElementById("atmosphere-tiles");
  const select = document.getElementById("atmosphere-preset");
  if (!holder || !select) return;
  holder.innerHTML = "";
  for (const option of select.options) {
    const tile = previewTile(option.value, option.textContent,
      (canvasEl) => paintAtmosphereTile(option.value, canvasEl), 2);
    tile.title = atmosphereTileTitle(option.value);
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

function buildMaterialTiles() {
  buildTileGrid("material-tiles", "material-select",
    (value) => materials[value] || null);
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

function paintMaterialSwatches() {
  const material = document.getElementById("material-select");
  const materialHolder = document.getElementById("material-tiles");
  if (materialHolder) paintTileSelection(materialHolder, material.value);
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
// 0.1, not the old 0.3: when the floor moved to 100 mm this mirror was
// left behind, so a bundle cut at 100 or 200 mm failed the range test
// here and the slider and its reading kept the PREVIOUS number while the
// vault on screen was cut finer. A mirror that drifts is worse than no
// mirror, so a test now holds the two files to the same pair.
const SIZE_MIN = 0.1, SIZE_MAX = 3.0;

// Said once per refusal rather than on every applyCut, which runs on
// every appearance change too.
let lastCutRefusal = null;

function applyCut(preserve) {
  paintMaterialSwatches();
  repaintScrubs();
  // A cut the generator could not make. The study still opens -- the net,
  // the formwork and the machine are all independent of the voussoirs --
  // so the honest thing is to say why there are none rather than to show
  // an empty vault with no explanation.
  const refusal = state.bundle && state.bundle.tessellation
    && state.bundle.tessellation.cut_refusal;
  if (refusal && refusal !== lastCutRefusal) {
    lastCutRefusal = refusal;
    showBanner("No skin on this study: " + refusal
      + " The net, the formwork and the machine are drawn; there are no "
      + "voussoirs to draw.", "error");
    logStudio("no cut: " + refusal);
  }
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
    document.getElementById("size-slider-value").textContent = Math.round(size * 1000);
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
  ["forces", "Wire forces"],
  ["loads", "Load vectors"],
  ["reactions", "Reaction vectors"],
  ["thrust", "Support thrust"],
];

// The three lenses that PAINT the same surface: two heatmaps recolouring
// the shell and the force-coloured wires. Layered together they read as
// mud (Param: "they overlap eachother, they can only be viewed
// individually"), so choosing one puts the others down.
const EXCLUSIVE_LAYERS = ["stress", "deflection", "forces"];

// What each lens carries under its button when it is on. Values live in
// state so a rebuild of the toggle list never resets a slider.
const LAYER_SLIDERS = {
  forces: { key: "forcesScale", label: "Size",
            min: 0, max: 3, step: 0.1,
            title: "How much a wire thickens with its force; 0 keeps "
              + "them uniform and lets the colour do the talking" },
  loads: { key: "loadsScale", label: "Scale",
           min: 0.2, max: 4, step: 0.1,
           title: "Arrow length multiplier" },
  reactions: { key: "reactionsScale", label: "Scale",
               min: 0.2, max: 4, step: 0.1,
               title: "Arrow length multiplier" },
  thrust: { key: "thrustScale", label: "Scale",
            min: 0.2, max: 4, step: 0.1,
            title: "Arrow length multiplier" },
};

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
// updateHud (and the since-removed pulse) were given the no-solver reading
// in commit 022f9c5; layerAvailability, the sibling nobody re-read, was still
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
  if (name === "thrust") {
    // The thrust arrows are the reactions read differently, so they need
    // exactly what the reactions layer needs.
    return state.bundle && Object.keys(state.bundle.reactions).length
      ? { on: true }
      : { on: false, why: "this contract shipped no reaction vectors" };
  }
  if (name === "stress" || name === "deflection") {
    if (stage) return { on: true };
    // stage is null and the question is why, in the same words updateHud
    // already uses for the same struck_now on the same
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
  // The exaggeration slider is a PERMANENT node (its value and handler
  // live in the page); park it back outside before the holder is wiped,
  // then seat it under the Deflection button below.
  const exaggerationRow = document.getElementById("exaggeration-row");
  document.getElementById("analysis-section").appendChild(exaggerationRow);
  exaggerationRow.classList.add("hidden");
  holder.innerHTML = "";
  for (const [name, label] of LAYERS) {
    const availability = layerAvailability(name);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "layer-btn" + (state.layers[name] ? " active" : "");
    button.textContent = label;
    button.disabled = !availability.on;
    if (availability.why) button.title = availability.why;
    button.addEventListener("click", () => setLayer(name, !state.layers[name]));
    holder.appendChild(button);
    if (name === "thrust") {
      // The pulse taught this panel that a lens explains itself where the
      // question is asked, not in a tooltip.
      const note = document.createElement("div");
      note.className = "layer-note";
      note.textContent = "The push each springing gives the ground, the "
        + "reaction reversed: green stands near vertical, amber leans, "
        + "red past 35 degrees is a push the abutment or a tie must hold.";
      holder.appendChild(note);
    }
    if (name === "deflection") {
      holder.appendChild(exaggerationRow);
      exaggerationRow.classList.toggle("hidden", !state.layers.deflection);
      exaggerationRow.classList.add("layer-slider");
    }
    const spec = LAYER_SLIDERS[name];
    if (spec) {
      const row = document.createElement("label");
      row.className = "layer-slider" + (state.layers[name] ? "" : " hidden");
      if (spec.title) row.title = spec.title;
      const caption = document.createElement("span");
      caption.textContent = spec.label;
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = spec.min;
      slider.max = spec.max;
      slider.step = spec.step;
      slider.value = state.analysisSliders[spec.key];
      slider.addEventListener("change", () => {
        state.analysisSliders[spec.key] = +slider.value;
        // Each slider redraws its own lens: the wire girth is not a
        // vector field.
        if (name === "forces") applyWireForces();
        else updateVectorLayers();
      });
      row.appendChild(caption);
      row.appendChild(slider);
      holder.appendChild(row);
    }
  }
}

function setLayer(name, on) {
  state.layers[name] = on;
  // One painting lens at a time: raising a heatmap or the force wires
  // puts the other two down, and everything they touched repaints.
  if (on && EXCLUSIVE_LAYERS.includes(name)) {
    for (const other of EXCLUSIVE_LAYERS) {
      if (other !== name) state.layers[other] = false;
    }
  }
  const forcesWasOn = name !== "forces" && on
    && EXCLUSIVE_LAYERS.includes(name) && state.showModeBeforeForces;
  if (name === "loads" || name === "reactions" || name === "thrust") {
    updateVectorLayers();
  }
  if (EXCLUSIVE_LAYERS.includes(name)) {
    recolourSegments();
    applyWireForces();
    // Wire forces ARE the net's lens, so raising it shows the bare net
    // (Param: "i cant see the wire forces becuase it doesnt change
    // geometry to formwork") and lowering it -- by its own button or by
    // another lens taking over -- returns to the view it interrupted.
    if (name === "forces" && on) {
      state.showModeBeforeForces = state.showMode;
      setShowMode("framework");
    } else if ((name === "forces" && !on) || forcesWasOn) {
      setShowMode(state.showModeBeforeForces || "both");
      state.showModeBeforeForces = null;
    } else {
      applyShowMode();
    }
  }
  buildLayerToggles();
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
  paintForceLegend(active ? forceMagnitude() : null);
  if (!active) {
    const white = new THREE.Color(0xffffff);
    for (let i = 0; i < base.length; i++) {
      wires.setMatrixAt(i, base[i]);
      wires.setColorAt(i, white);
    }
    wires.instanceMatrix.needsUpdate = true;
    wires.instanceColor.needsUpdate = true;
    if (wires.userData.baseMaterial) wires.material = wires.userData.baseMaterial;
    wires.material.color.copy(materials.steel.color);
    return;
  }
  const forces = state.bundle.member_forces;
  // The 95th percentile, not the maximum: a handful of extreme members
  // owned the linear scale and pressed every other wire into the pale
  // zero end -- colours applied and invisible (measured live: instance
  // colours all ~0.82/0.81/0.79). Normalising by p95 spreads the body of
  // the distribution across the ramp; the extremes saturate, and the
  // legend says so.
  const magnitude = forceMagnitude() || 1e-9;
  const position = new THREE.Vector3(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
  const m = new THREE.Matrix4();
  // And an UNLIT material while the lens is on: the force field is data,
  // not scenography, the same exemption the heatmaps claim. The steel
  // material is stashed and restored when the lens goes down.
  if (!wires.userData.baseMaterial) wires.userData.baseMaterial = wires.material;
  if (!wires.userData.forceMaterial) {
    // No per-vertex colour flag here: these cylinders carry no such
    // attribute, and an unbound attribute samples BLACK, multiplying
    // every instance colour to black (Param's screenshot: a black
    // lattice under a working legend). instanceColor rides any material
    // on its own -- the silver rest state proves it.
    wires.userData.forceMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff, toneMapped: false });
  }
  wires.material = wires.userData.forceMaterial;
  // How much a wire fattens with its force is his slider now; at 0 the
  // net stays uniform and only the colour speaks.
  const girth = state.analysisSliders.forcesScale;
  forces.forEach((force, i) => {
    base[i].decompose(position, quaternion, scale);
    const radiusScale = 1 + 2 * girth * Math.abs(force) / magnitude;
    m.compose(position, quaternion, new THREE.Vector3(radiusScale, scale.y, radiusScale));
    wires.setMatrixAt(i, m);
    wires.setColorAt(i, STRESS_SCALE(force, magnitude));
  });
  wires.instanceMatrix.needsUpdate = true;
  wires.instanceColor.needsUpdate = true;
}

function forceMagnitude() {
  const forces = state.bundle && state.bundle.member_forces;
  if (!forces || !forces.length) return null;
  const sorted = forces.map((force) => Math.abs(force)).sort((a, b) => a - b);
  const p95 = sorted[Math.min(sorted.length - 1,
    Math.floor(0.95 * (sorted.length - 1)))];
  return p95 || sorted[sorted.length - 1] || null;
}

// The key beside the panel, wire-forces edition: same diverging bar the
// stress lens uses (compression blue, tension red), labelled in kN.
function paintForceLegend(magnitude) {
  const legend = document.getElementById("legend");
  if (magnitude === null) {
    // Only claim the legend back if no heatmap owns it; recolourSegments
    // paints its own the moment one does.
    if (!state.layers.stress && !state.layers.deflection) {
      legend.classList.add("hidden");
    }
    return;
  }
  legend.classList.remove("hidden");
  legend.classList.remove("deflection");
  document.getElementById("legend-title").textContent =
    "member force, kN (extremes clamped)";
  document.getElementById("legend-min").textContent = (-magnitude / 1e3).toFixed(1);
  document.getElementById("legend-zero").textContent = "0";
  document.getElementById("legend-max").textContent = (magnitude / 1e3).toFixed(1);
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
    // casting. (The pulse's shared-lens materials, the one exception this
    // guard once carried, left with the pulse.)
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
  for (const key of ["loadArrows", "reactionArrows", "thrustArrows"]) {
    if (state.objects[key]) { scene.remove(state.objects[key]); state.objects[key] = null; }
  }
  if (!state.bundle) return;
  const bundle = state.bundle;
  if (state.layers.loads) {
    state.objects.loadArrows = arrowField(
      Object.entries(bundle.loads), 0x66aaff, "tip",
      state.analysisSliders.loadsScale);
    scene.add(state.objects.loadArrows);
  }
  if (state.layers.reactions && Object.keys(bundle.reactions).length) {
    // Real TNA reaction vectors from the contract, shipped in the bundle.
    state.objects.reactionArrows = arrowField(
      Object.entries(bundle.reactions), 0x66dd77, "tail",
      state.analysisSliders.reactionsScale);
    scene.add(state.objects.reactionArrows);
  }
  if (state.layers.thrust && Object.keys(bundle.reactions).length) {
    // The push each springing gives the ground: the reaction REVERSED,
    // bucketed by how far it leans from vertical -- the same 35-degree
    // line the analysis narrative warns at. Green stands, amber leans,
    // red is a push the abutment or a tie must hold. One arrowField per
    // bucket (a field is one colour), all normalised against the one
    // magnitude so lengths stay comparable across colours.
    const buckets = { stands: [], leans: [], kicks: [] };
    let magnitudeMax = 1e-9;
    for (const [id, vector] of Object.entries(bundle.reactions)) {
      magnitudeMax = Math.max(magnitudeMax,
        Math.hypot(vector[0], vector[1], vector[2]));
      const outward = Math.hypot(vector[0], vector[1]);
      const degrees = Math.atan2(outward, Math.abs(vector[2])) * 180 / Math.PI;
      const push = [-vector[0], -vector[1], -vector[2]];
      (degrees >= 35 ? buckets.kicks
        : degrees >= 20 ? buckets.leans : buckets.stands).push([id, push]);
    }
    const group = new THREE.Group();
    for (const [rows, colour] of [[buckets.stands, 0x3f9e57],
        [buckets.leans, 0xc99a2e], [buckets.kicks, 0xc24936]]) {
      if (rows.length) {
        group.add(arrowField(rows, colour, "tail",
          state.analysisSliders.thrustScale, magnitudeMax));
      }
    }
    state.objects.thrustArrows = group;
    scene.add(group);
  }
}

function arrowField(entries, colour, anchor, lengthScale = 1,
                    magnitudeMaxShared = null) {
  // One LineSegments for every shaft plus one instanced cone set for heads:
  // two draw calls however many nodes there are. Arrows draw exactly along
  // the shipped vector: loads arrive pointing down, reactions as exported.
  // anchor 'tip' stands the shaft before the node so the head lands at the point of application; 'tail' leaves the node along the vector.
  const vertices = state.bundle.analysis_mesh.vertices;
  // A shared magnitude, when given, keeps arrow lengths comparable across
  // sibling fields drawn in different colours (the thrust buckets).
  let magnitudeMax = magnitudeMaxShared || 1e-9;
  if (!magnitudeMaxShared) {
    for (const [, v] of entries) magnitudeMax = Math.max(magnitudeMax, Math.hypot(v[0], v[1], v[2]));
  }
  const positions = [];
  const cone = new THREE.ConeGeometry(0.06, 0.18, 8);
  const heads = new THREE.InstancedMesh(
    cone, new THREE.MeshBasicMaterial({ color: colour }), entries.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  entries.forEach(([id, vector], i) => {
    const at = vertices[+id];
    const v = new THREE.Vector3(vector[0], vector[1], vector[2]);
    const length = (0.4 + 2.0 * (v.length() / magnitudeMax)) * lengthScale;
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
  // The arrows read THROUGH the shell: an anchor half-buried behind
  // opaque pieces was Param's "hard to see them because the shell gets
  // in the way". Depth-test off plus a late render order draws every
  // shaft and head over whatever hides it.
  heads.material.depthTest = false;
  heads.material.fog = false;
  heads.renderOrder = 25;
  const lines = new THREE.LineSegments(
    new THREE.BufferGeometry().setAttribute(
      "position", new THREE.BufferAttribute(new Float32Array(positions), 3)),
    new THREE.LineBasicMaterial({ color: colour, depthTest: false, fog: false }));
  lines.renderOrder = 25;
  const group = new THREE.Group();
  group.add(lines); group.add(heads);
  return group;
}

// ---------- the build stage index ----------
function currentStageIndex(build) {
  // Which build stage the timeline is inside: stages are courses, and a
  // course's segments occupy a contiguous run of the drop order. build is
  // elapsed time since the net finished inflating (see applySceneAtTime),
  // so the stage reported here always matches the segments actually on
  // screen.
  if (!state.bundle.staging || !state.timeline) return null;
  const stages = state.bundle.staging.stages;
  if (!stages || !stages.length) return null;
  // placementStep, the one shared stagger: the HUD's stage line hangs off
  // this number, and reading the picture at a different rate once had a
  // finished sprayed vault quoting a stage still halfway down the drop
  // order.
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

// The integrity pulse lived here until 2026-09-06 (Param: "no more green
// and flashing etc. i dont think it adds enough value"). Its verdict per
// course survives in the Data sheet's build story, where it reads better
// as a sentence than it ever did as a glow.

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

  // The CRA verdict no longer pops up: it is gone from the badge and the
  // HUD, since the form finding already guarantees
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
  // The vault is weighed as what it WEARS, not as the class it is cut
  // like (Param: "if i am picking a copper say, we need to use that
  // material density in the calculations"). Sent only when a skin
  // actually overrides the structural density, so a plain concrete
  // study keeps its existing cache entry and rebuilds nothing.
  const weighAs = skinDensity();
  if (weighAs && Math.abs(weighAs - structuralDensity()) > 1) {
    url += "&density=" + weighAs;
  }
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
    // The machine, on the same terms: absent is an ordinary state of the
    // world and reads as "no machine for this study", exactly as a
    // missing formwork document reads as "no formwork act".
    // THE VAULT WEARS THE MECHANISM EXPORTED WITH IT, and nothing else
    // (Param, 2026-09-15). A vault with none, or one exported before the
    // machine split, loads bare and the log says why.
    const mechanismPromise = fetch(
      "/api/studies/" + encodeURIComponent(exportName) + "/mechanism")
      .then(async (r) => {
        if (r.ok) return r.json();
        const reason = await r.json().then((body) => body.detail)
          .catch(() => r.statusText);
        logStudio("mechanism: " + reason);
        return null;
      })
      .catch(() => null);
    const fresh = await fetchJson(url);
    if (sequence !== state.loadSequence) return "superseded";
    // Held locally until this load is confirmed the winner: assigned
    // before the check, a superseded load clobbered the winning study's
    // formwork with its own.
    const formwork = await formworkPromise;
    const ownMechanism = await mechanismPromise;
    if (sequence !== state.loadSequence) return "superseded";
    const mechanismDocument = ownMechanism;
    state.formwork = formwork;
    state.mechanism = mechanismDocument;
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
    // The bundle, the formwork and the columns are all new: so are the
    // graphs' series.
    invalidateLiveGraphs();
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
  // A zero with a reason: picking the studio's own cut cache (its name
  // says "studies") silenced the import with a bare count once. The
  // server recognises the near-miss and says what a vault export IS.
  status.textContent = folder.studies + " vaults in this folder"
    + (folder.hint ? " -- " + folder.hint : "");
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
  // Param: "when i press refresh in the import menu, i expect it to
  // refresh the loaded vault too, because i upload a new file and it
  // doesnt update even after pushing refresh."
  //
  // It only ever re-read the FOLDER LISTING, so a re-export of the vault
  // already on screen changed the file on disk and nothing else: the
  // listing was identical, and the studio went on drawing the bundle it
  // had loaded minutes earlier. Refresh now reloads the standing vault as
  // well, which is what the button appears to promise.
  const select = document.getElementById("study-select");
  const standing = select.value;
  const names = await refreshStudies(standing);
  logStudio("folder re-read: " + names.length + " vaults");
  if (standing && names.includes(standing)) {
    select.value = standing;
    await loadStudy(standing);
    logStudio("reloaded " + standing + " from the folder");
  }
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
  state.mechanism = null;
  disposeMachine();
  state.bundle = null;
  // No study, no graphs: the cards go with the scene they described.
  showLiveGraphs(false);
  liveGraphs.series = null;
  liveGraphs.dirty = true;
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
// ---------- a server older than its own code ----------
// The page reloads onto new JavaScript by itself; the server does not
// reload onto new Python until it is restarted. When the two disagree the
// studio says so, beside the button that fixes it, rather than letting a
// still quietly go on doing what the old server did (Param, 2026-09-14,
// after a still fixed the day before went on landing in the study folder).
// A server too old to answer the question at all is older still.
let serverStaleSaid = false;

async function checkServerCode() {
  let health = null;
  try {
    health = await (await fetch("/api/health", { cache: "no-store" })).json();
  } catch (error) {
    return null;
  }
  const stale = !("serverStale" in health) || health.serverStale === true;
  const button = document.getElementById("restart-studio");
  const status = document.getElementById("restart-status");
  button.classList.toggle("attention", stale);
  if (stale) {
    status.textContent = "the server is running older code than is on disk: restart it";
    if (!serverStaleSaid) {
      serverStaleSaid = true;
      showBanner("The studio server is older than its own code, so recent fixes "
        + "(stills to the output folder among them) are not running yet. Press "
        + "Restart studio at the foot of the panel.", "error");
    }
  } else if (status.textContent.startsWith("the server is running older code")) {
    status.textContent = "";
  }
  return stale;
}
checkServerCode();
setInterval(checkServerCode, 60000);

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
    // Their batches go on drawing them, but no new placement may join one:
    // it would wear the old folder's model under the new folder's name.
    retirePropBatches();
    await loadPropLibrary();
  }));

document.getElementById("render-skin").addEventListener("change", async (e) => {
  state.appearance.skin = e.target.value;
  // THE NEW MATERIAL WEARS ITS OWN TINT. Param, 2026-09-13: "when i
  // change material the previous tint stays we need to not do that. use
  // the tint of the actual material." The tint was one value on the
  // appearance, so a colour chosen for one material rode onto the next.
  // It belongs to the material it was chosen for: the one being put on
  // gets whatever was chosen for IT, which is nothing until he chooses.
  // Undo replays this handler, so going back puts the old tint back too.
  state.appearance.tint = skinTints()[state.appearance.skin] || null;
  paintTintSwatch();
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
  // The library set has landed by now, so its own colour is known.
  paintTintSwatch();
});
document.getElementById("material-tint").addEventListener("change", (e) => {
  state.appearance.tint = e.target.value;
  skinTints()[state.appearance.skin] = e.target.value;
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
  state.appearance = { tint: null, finish: null, skin: "none", tints: {} };
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
  document.getElementById("size-slider-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("size-slider").addEventListener("change", (e) => {
  state.size = +e.target.value;
  scheduleReload();
});
document.getElementById("thickness-input").addEventListener("input", (e) => {
  document.getElementById("thickness-input-value").textContent = Math.round(+e.target.value * 1000);
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
// The site block. Same split as the sun's own sliders: input re-solves
// and moves the light, which is cheap, and only the release pays for the
// PMREM bake, and only in sky mode where the sky IS the environment.
const SITE_FIELDS = {
  "site-latitude": "latitude",
  "site-longitude": "longitude",
  "site-north": "northOffset",
};
for (const [id, field] of Object.entries(SITE_FIELDS)) {
  const input = document.getElementById(id);
  if (!input) continue;
  input.addEventListener("input", () => setSite({ [field]: +input.value }));
  input.addEventListener("change", () => {
    if (state.environmentMode === "sky") regenerateEnvironment();
  });
}
{
  const select = document.getElementById("site-place");
  if (select) {
    for (const place of [{ name: "Custom" }].concat(SUN_PLACES)) {
      // Custom carries an empty value on purpose: it is what the sync
      // writes when no place matches, and choosing it is a no-op rather
      // than a jump to nowhere.
      select.appendChild(new Option(place.name,
        place.name === "Custom" ? "" : place.name));
    }
    select.addEventListener("change", (event) => {
      const place = SUN_PLACES.find((p) => p.name === event.target.value);
      if (!place) return;
      setSite({ latitude: place.latitude, longitude: place.longitude });
      if (state.environmentMode === "sky") regenerateEnvironment();
    });
  }
  const date = document.getElementById("site-date");
  if (date) {
    date.addEventListener("change", (event) => {
      const day = dayFromIso(event.target.value);
      if (!day) return;             // a half-typed date is not a new day
      state.sunDay = day;
      syncSiteControls();
      applySunFromTime();
      if (state.environmentMode === "sky") regenerateEnvironment();
    });
  }
  syncSiteControls();
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
document.getElementById("show-machine").addEventListener("change", (e) => {
  state.showMachine = !!e.target.checked;
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
document.getElementById("background-tone").addEventListener("input", (e) => {
  document.getElementById("background-tone-value").textContent =
    Math.round(+e.target.value);
  applyEnvironment();
});
// The inked outline. Only a uniform moves, so this is free to drag.
document.getElementById("outline-width").addEventListener("input", (e) => {
  state.outline = Math.max(0, +e.target.value);
  applyOutline();
});

// ---------- the lamp controls ----------
// Which lamps a slider is about to touch: the one that is selected, or
// every lamp in the scene. Selecting a lamp is how you say "just this
// one", which is the same gesture that already moves and scales it, and
// the heading says out loud which of the two is happening.
function lampTargets() {
  if (isLamp(state.selectedProp)) return [state.selectedProp];
  return state.props.filter(isLamp);
}

function syncLightControls() {
  // The heading lives in the Lights drawer now, not the Scene panel.
  const heading = document.getElementById("lights-readout");
  const lamps = state.props.filter(isLamp);
  const one = isLamp(state.selectedProp) ? state.selectedProp : null;
  if (heading) {
    heading.textContent = (one
      ? "tuning the selected fixture"
      : lamps.length
        ? "tuning all " + lamps.length + " fixtures"
        : "click a fixture to place it, then a placed one to tune it")
      + "; new fixtures go onto " + placingOntoName();
  }
  // The sliders show the selected lamp's own numbers, or the defaults a
  // newly placed lamp will wear.
  const lumens = one ? one.lumens : state.lampLumens;
  const kelvin = one ? one.kelvin : state.lampKelvin;
  const write = (id, value, reading) => {
    const input = document.getElementById(id);
    if (!input) return;
    input.value = value;
    paintScrub(input);
    const span = document.getElementById(id + "-value");
    if (span) span.textContent = reading;
  };
  write("lamp-lumens", lumens, Math.round(lumens));
  write("lamp-kelvin", kelvin, Math.round(kelvin));
  // The gel, which is a swatch rather than a dial but keeps the same
  // reading pairing so it can be read at a glance beside the numbers.
  const tint = (one ? one.tint : state.lampTint) || LAMP_TINT;
  const swatch = document.getElementById("lamp-tint");
  if (swatch) {
    swatch.value = tint;
    const reading = document.getElementById("lamp-tint-value");
    if (reading) reading.textContent = tint;
  }
  // Invisible: a toggle rather than a dial, but it keeps the same
  // reading cell so the block can still be read straight down.
  const hidden = one ? !!one.invisible : !!state.lampInvisible;
  const box = document.getElementById("lamp-invisible");
  if (box) {
    box.checked = hidden;
    const said = document.getElementById("lamp-invisible-value");
    if (said) said.textContent = hidden ? "yes" : "no";
  }
  // THE SPOT'S OWN FOUR, offered only when a spot is what the dials
  // are pointed at: a sphere has no aperture, and a control that does
  // nothing in the current mode is hidden rather than shown dead.
  const beam = isSpot(one) ? one : state.spot;
  const offerBeam = isSpot(one) || (!one && state.props.some(isSpot));
  for (const row of document.querySelectorAll("#lights-controls .spot-dial")) {
    row.classList.toggle("hidden", !offerBeam);
  }
  if (offerBeam) {
    const aperture = +beam.aperture || SPOT_APERTURE;
    const softness = beam.softness === undefined ? SPOT_SOFTNESS
      : +beam.softness || 0;
    const reach = +beam.reach || 0;
    write("lamp-aperture", aperture, Math.round(aperture));
    write("lamp-softness", Math.round(softness * 100),
      Math.round(softness * 100));
    write("lamp-reach", reach, reach.toFixed(reach ? 1 : 0));
    const cast = beam.shadow !== false;
    const box = document.getElementById("lamp-shadow");
    if (box) {
      box.checked = cast;
      const said = document.getElementById("lamp-shadow-value");
      if (said) said.textContent = cast ? "on" : "off";
    }
  }
}

// The spot's four, which no other fixture has anything to do with: a
// sphere handed an aperture would carry it through the layout and the
// scene for ever and never use it.
const SPOT_FIELDS = new Set(["aperture", "softness", "reach", "shadow"]);

function writeLamps(field, value) {
  const targets = SPOT_FIELDS.has(field)
    ? lampTargets().filter(isSpot) : lampTargets();
  for (const record of targets) {
    record[field] = value;
    applyPropLight(record);
  }
  // With nothing selected the number is also the default for the next
  // lamp placed, which is what makes "set them all warm, then add
  // another" behave the way anyone would expect.
  if (!isLamp(state.selectedProp)) {
    if (field === "lumens") state.lampLumens = value;
    else if (field === "kelvin") state.lampKelvin = value;
    else if (field === "tint") state.lampTint = value;
    else if (field === "invisible") state.lampInvisible = value;
    else state.spot[field] = value;
  }
  syncLightControls();
  return targets.length;
}

document.getElementById("lamp-lumens").addEventListener("input", (e) => {
  writeLamps("lumens", Math.max(0, +e.target.value));
});
document.getElementById("lamp-kelvin").addEventListener("input", (e) => {
  writeLamps("kelvin", +e.target.value);
});
document.getElementById("lamp-tint").addEventListener("input", (e) => {
  writeLamps("tint", e.target.value);
});
// A toggle has no drag to wait out, so it writes the layout at once.
document.getElementById("lamp-invisible").addEventListener("change", (e) => {
  writeLamps("invisible", !!e.target.checked);
  saveProps();
});
// The layout is per study and lives in localStorage; writing it on every
// pixel of a drag would be a hundred writes for one decision.
// THE SPOT'S FOUR. Aperture, Softness and Reach are dials and write
// as they move; Shadow is a toggle with no drag to wait out, so it
// writes the layout at once, as Invisible does.
document.getElementById("lamp-aperture").addEventListener("input", (e) => {
  writeLamps("aperture", +e.target.value);
});
document.getElementById("lamp-softness").addEventListener("input", (e) => {
  writeLamps("softness", Math.min(1, Math.max(0, +e.target.value / 100)));
});
document.getElementById("lamp-reach").addEventListener("input", (e) => {
  writeLamps("reach", Math.max(0, +e.target.value));
});
document.getElementById("lamp-shadow").addEventListener("change", (e) => {
  writeLamps("shadow", !!e.target.checked);
  saveProps();
});
for (const id of ["lamp-lumens", "lamp-kelvin", "lamp-tint",
                  "lamp-aperture", "lamp-softness", "lamp-reach"]) {
  document.getElementById(id).addEventListener("change", () => saveProps());
}

// ---------- the panel beside the light ----------
// Param, 2026-09-12: "I have an idea only in edit mode we can move them
// around, but if we click them when not in edit mode, then a translucent
// setting pops up next to it where we can control the sliders and
// options for each type of light, then when we click anywhere not on the
// light or the menu it disappears."
//
// His idea exactly. Out of edit mode a left click on a fixture opens a
// card beside it holding THAT fixture's own controls and nothing else;
// every write goes to that fixture alone, never to the selection and
// never to all of them, which is what makes it different from the Lights
// drawer. In edit mode the click still picks the fixture up as it always
// did, and this never opens.
//
// A record, not an id: a fixture has no id, and the record is what every
// writer here already takes.
let fixturePanelFor = null;
const fixtureAnchor = new THREE.Vector3();

// Length is offered where a fixture's light is actually laid on its
// faces, which is the same question as "does stretching it change the
// light". A sphere's point light and a spot's cone do not move when the
// body is stretched, so the dial would be a control that does nothing.
function fixtureStretches(record) {
  return !!record && !!record.object
    && record.object.children.some((child) => child.isRectAreaLight);
}

function fixtureKindLabel(record) {
  const kind = LIGHT_KINDS.find((one) => one.key === record.type);
  return kind ? kind.label : "Fixture";
}

function openFixturePanel(record) {
  fixturePanelFor = record;
  const card = document.getElementById("fixture-panel");
  if (!card) return;
  card.classList.remove("hidden");
  syncFixturePanel();
  placeFixturePanel();
}

function closeFixturePanel() {
  if (!fixturePanelFor) return;
  fixturePanelFor = null;
  const card = document.getElementById("fixture-panel");
  if (card) card.classList.add("hidden");
}

// Every control, from the one fixture. The same four-part dials the
// drawer uses, so the readings are written by the same id pairing.
function syncFixturePanel() {
  const record = fixturePanelFor;
  if (!record) return;
  const name = document.getElementById("fixture-name");
  if (name) name.textContent = fixtureKindLabel(record);
  const write = (id, value, reading) => {
    const input = document.getElementById(id);
    if (!input) return;
    input.value = value;
    paintScrub(input);
    const span = document.getElementById(id + "-value");
    if (span) span.textContent = reading;
  };
  const lumens = Math.max(0, +record.lumens || 0);
  const kelvin = +record.kelvin || LAMP_KELVIN;
  write("fixture-lumens", lumens, Math.round(lumens));
  write("fixture-kelvin", kelvin, Math.round(kelvin));
  const tint = record.tint || LAMP_TINT;
  const swatch = document.getElementById("fixture-tint");
  if (swatch) {
    swatch.value = tint;
    const reading = document.getElementById("fixture-tint-value");
    if (reading) reading.textContent = tint;
  }
  const scale = +record.scale || 1;
  const along = Array.isArray(record.size) ? +record.size[0] || 1 : 1;
  write("fixture-size", scale, scale.toFixed(2));
  write("fixture-length", along, along.toFixed(1));
  const lengthRow = document.getElementById("fixture-length-row");
  if (lengthRow) lengthRow.classList.toggle("hidden", !fixtureStretches(record));
  const hidden = !!record.invisible;
  const body = document.getElementById("fixture-invisible");
  if (body) {
    body.checked = hidden;
    const said = document.getElementById("fixture-invisible-value");
    if (said) said.textContent = hidden ? "yes" : "no";
  }
  // The spot's four, and only for a spot.
  const beamed = isSpot(record);
  for (const row of document.querySelectorAll("#fixture-dials .fixture-spot")) {
    row.classList.toggle("hidden", !beamed);
  }
  if (beamed) {
    const aperture = +record.aperture || SPOT_APERTURE;
    const softness = record.softness === undefined ? SPOT_SOFTNESS
      : +record.softness || 0;
    const reach = +record.reach || 0;
    write("fixture-aperture", aperture, Math.round(aperture));
    write("fixture-softness", Math.round(softness * 100),
      Math.round(softness * 100));
    write("fixture-reach", reach, reach.toFixed(reach ? 1 : 0));
    const cast = record.shadow !== false;
    const box = document.getElementById("fixture-shadow");
    if (box) {
      box.checked = cast;
      const said = document.getElementById("fixture-shadow-value");
      if (said) said.textContent = cast ? "on" : "off";
    }
  }
}

// ONE fixture, never the selection and never all of them. That is the
// whole difference between this card and the drawer.
function writeFixture(field, value) {
  const record = fixturePanelFor;
  if (!record) return;
  record[field] = value;
  applyPropLight(record);
  syncFixturePanel();
  // The drawer may be open on the same fixture, and two controls over
  // one piece of state that disagree is worse than one control.
  syncLightControls();
  saveProps();
}

function writeFixtureSize() {
  const record = fixturePanelFor;
  if (!record) return;
  record.scale = +document.getElementById("fixture-size").value;
  record.size = [+document.getElementById("fixture-length").value, 1, 1];
  applyPropSize(record);
  syncFixturePanel();
  syncLightSize();
  if (state.selectedProp === record) {
    refreshPropOutline();
    refreshPropGumball();
  }
  saveProps();
}

// It follows its fixture while the camera moves, and it closes itself if
// the fixture goes: a delete, a scene, a study reload. The test is the
// object's own parent, which is O(1); state.props.includes would be a
// walk of a scattered field every frame.
function placeFixturePanel() {
  const record = fixturePanelFor;
  if (!record) return;
  if (!record.object || !record.object.parent) { closeFixturePanel(); return; }
  const card = document.getElementById("fixture-panel");
  if (!card) return;
  record.object.updateMatrixWorld(true);
  // The top of the fixture, so the card sits beside the thing rather
  // than over its own light.
  const box = new THREE.Box3().setFromObject(record.object);
  fixtureAnchor.set((box.min.x + box.max.x) / 2, (box.min.y + box.max.y) / 2,
    box.max.z);
  fixtureAnchor.project(camera);
  const rect = canvas.getBoundingClientRect();
  // Behind the camera: there is nowhere on the screen to put it.
  if (fixtureAnchor.z > 1) { card.style.visibility = "hidden"; return; }
  card.style.visibility = "";
  const x = rect.left + (fixtureAnchor.x * 0.5 + 0.5) * rect.width;
  const y = rect.top + (-fixtureAnchor.y * 0.5 + 0.5) * rect.height;
  // Kept whole on the screen: a card half off the right edge is a card
  // whose dials cannot be reached.
  const width = card.offsetWidth || 256;
  const height = card.offsetHeight || 200;
  const left = Math.min(window.innerWidth - width - 12, Math.max(12, x + 18));
  const top = Math.min(window.innerHeight - height - 12, Math.max(12, y - 24));
  card.style.left = Math.round(left) + "px";
  card.style.top = Math.round(top) + "px";
}

document.getElementById("fixture-lumens").addEventListener("input", (e) => {
  writeFixture("lumens", Math.max(0, +e.target.value));
});
document.getElementById("fixture-kelvin").addEventListener("input", (e) => {
  writeFixture("kelvin", +e.target.value);
});
document.getElementById("fixture-tint").addEventListener("input", (e) => {
  writeFixture("tint", e.target.value);
});
document.getElementById("fixture-invisible").addEventListener("change", (e) => {
  writeFixture("invisible", !!e.target.checked);
});
document.getElementById("fixture-aperture").addEventListener("input", (e) => {
  writeFixture("aperture", +e.target.value);
});
document.getElementById("fixture-softness").addEventListener("input", (e) => {
  writeFixture("softness", Math.min(1, Math.max(0, +e.target.value / 100)));
});
document.getElementById("fixture-reach").addEventListener("input", (e) => {
  writeFixture("reach", Math.max(0, +e.target.value));
});
document.getElementById("fixture-shadow").addEventListener("change", (e) => {
  writeFixture("shadow", !!e.target.checked);
});
for (const id of ["fixture-size", "fixture-length"]) {
  document.getElementById(id).addEventListener("input", writeFixtureSize);
}

// "when we click anywhere not on the light or the menu it disappears".
// The viewport decides its own clicks (the pointerdown handler above
// opens the card on a fixture and closes it on anything else), so this
// only has to answer for the rest of the page. BUBBLE phase, so the
// scatter tools' capture-phase handler is untouched.
document.addEventListener("pointerdown", (event) => {
  if (!fixturePanelFor) return;
  if (event.target === canvas) return;
  if (event.target.closest && event.target.closest("#fixture-panel")) return;
  closeFixturePanel();
});
// Both read as percentages because that is how a grade is discussed,
// and both are held as multipliers. Contrast declares its factor: its
// range SPANS zero, and at zero the derivation gives up.
function paintGradeReadings() {
  document.getElementById("brightness-value").textContent =
    Math.round(state.brightness * 100);
  document.getElementById("contrast-value").textContent =
    Math.round(state.contrast * 100);
}

document.getElementById("brightness").addEventListener("input", (e) => {
  state.brightness = +e.target.value;
  paintGradeReadings();
  applyGrade();
});
document.getElementById("contrast").addEventListener("input", (e) => {
  state.contrast = +e.target.value;
  paintGradeReadings();
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
// The readings are written on INPUT and the work done on CHANGE: the
// number must follow his thumb, but rebuilding the dome on every tick of
// a drag would not.
document.getElementById("hdri-scale").addEventListener("input", (e) => {
  document.getElementById("hdri-scale-value").textContent =
    Math.round(+e.target.value);
});
document.getElementById("hdri-scale").addEventListener("change", (e) => {
  state.hdriScale = +e.target.value;
  applyHdriBackdrop();
});
document.getElementById("hdri-height").addEventListener("input", (e) => {
  document.getElementById("hdri-height-value").textContent =
    (+e.target.value).toFixed(1);
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
  document.getElementById("hdri-rotation-value").textContent =
    Math.round(state.hdriRotation);
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
// ---------- the atmosphere's controls ----------
// Each dial, its key in state.atmosphere and the digits its reading shows.
// The reading is the raw value, so a typed number lands as itself.
const ATMOSPHERE_DIALS = [
  ["atmosphere-density", "density", 1],
  ["atmosphere-height", "height", 1],
  ["atmosphere-base", "base", 1],
  ["atmosphere-start", "start", 0],
  ["atmosphere-opacity", "maxOpacity", 0],
  ["atmosphere-glow", "sunGlow", 0],
  ["atmosphere-lobe", "sunLobe", 0],
  ["atmosphere-mist", "mist", 1],
  ["atmosphere-mist-height", "mistHeight", 1],
  ["atmosphere-shafts", "shafts", 0],
];

// The dials show only while a preset is chosen (a dial that does nothing
// is hidden, not shown dead), and wear the state's numbers, readings
// included: a restored scene moves the numbers with the sliders.
// ---------- the wind's dials ----------
const WIND_DIALS = [
  ["wind-strength", "strength", 0],
  ["wind-from", "from", 0],
  ["wind-gusts", "gusts", 0],
];

function syncWindControls() {
  for (const [id, key, digits] of WIND_DIALS) {
    const input = document.getElementById(id);
    input.value = state.wind[key];
    paintScrub(input);
    document.getElementById(id + "-value").textContent = (+state.wind[key]).toFixed(digits);
  }
}

// The studio starts in a breeze, so the air is set before the first frame.
applyWindState();

for (const [id, key, digits] of WIND_DIALS) {
  const input = document.getElementById(id);
  // Every tick moves the air: the strength, the gusts and the direction are
  // uniforms every swaying material holds by reference, so nothing recompiles.
  input.addEventListener("input", () => {
    state.wind[key] = +input.value;
    document.getElementById(id + "-value").textContent = (+input.value).toFixed(digits);
    applyWindState();
  });
}

function syncAtmosphereControls() {
  const on = atmosphereIsOn(state.atmosphere);
  // With none chosen the block stands aside and says where the choice is.
  document.getElementById("atmosphere-hint").classList.toggle("hidden", on);
  for (const label of document.querySelectorAll("#scene-atmosphere-dials .atmosphere-dial")) {
    // The shafts are the one atmosphere dial the iPad never gets: there
    // is no pass behind it there, so it stays away rather than sitting
    // dead among the dials that do work.
    const desktopOnly = label.id === "atmosphere-shafts-row";
    label.classList.toggle("hidden", !on || (desktopOnly && CONSTRAINED_DEVICE));
  }
  for (const [id, key, digits] of ATMOSPHERE_DIALS) {
    const input = document.getElementById(id);
    input.value = state.atmosphere[key];
    paintScrub(input);
    document.getElementById(id + "-value").textContent = state.atmosphere[key].toFixed(digits);
  }
}

for (const [id, key, digits] of ATMOSPHERE_DIALS) {
  const input = document.getElementById(id);
  // Every tick moves the fog: the densities and the glow are uniforms every
  // fogged material holds by reference, so nothing recompiles.
  input.addEventListener("input", () => {
    state.atmosphere[key] = +input.value;
    document.getElementById(id + "-value").textContent = (+input.value).toFixed(digits);
    applyAtmosphere();
    applySkyBrightness();
  });
  // On release the sky's light is captured again with the new air over it.
  input.addEventListener("change", () => {
    if (state.environmentMode === "sky") regenerateEnvironment();
    rememberSession();
  });
}

document.getElementById("atmosphere-preset").addEventListener("change", (e) => {
  state.atmosphere = atmosphereFromPreset(e.target.value);
  syncAtmosphereControls();
  paintTileSelection(document.getElementById("atmosphere-tiles"), state.atmosphere.preset);
  applyEnvironment();
  regenerateEnvironment();
  rememberSession();
});
syncAtmosphereControls();

document.getElementById("weather-preset").addEventListener("change", (e) => {
  state.weatherPreset = e.target.value;
  state.sunColourOverride = null; // a new preset picks the colour again
  state.sunIntensityOverride = null; // F4: same reset, for the intensity override
  const preset = WEATHER[e.target.value];
  if (preset.elevation !== null) {
    document.getElementById("sun-elevation").value = preset.elevation;
  }
  // Night is an HOUR: an hour and a half past dusk at the site, where the
  // instrument puts the sun under the horizon and the moon up. Any other
  // weather chosen while the clock still stands at night brings the day
  // back, or "Clear" at half past midnight would read as a broken preset
  // rather than as a clear night.
  if (preset.night) {
    setSunMinutes(Math.min(1439, dayCycleEnd() + 90));
  } else if (sunInstrumentReady && currentSun().elevation < -0.833) {
    setSunMinutes(Math.round((dayCycleStart() + dayCycleEnd()) / 2));
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
  // WHAT RANDOMISE MEANS. Param, 2026-09-12: "at the moment randomise
  // uv just rotates all uv to a random orientation. but what it should
  // mean is every instance randomises, so that the repeating is
  // different throughout".
  //
  // It used to turn and slide the whole sheet, which re-lays the floor
  // and leaves every repeat within it identical. It now also picks a
  // fresh arrangement of the per-tile randomising and switches that on,
  // because that is the thing he was asking the button to do.
  state.ground.offset = [Math.random(), Math.random()];
  state.ground.rotation = Math.random() * Math.PI * 2;
  state.ground.seed = [Math.random() * 64, Math.random() * 64];
  const was = state.ground.breakup;
  setGroundBreakup(true);
  if (state.objects.ground) rebuildGround();
  logStudio(was
    ? "floor re-laid, and every tile reads from a fresh place in the picture"
    : "floor re-laid, and every tile now reads from its own place in the "
      + "picture rather than repeating");
});

document.getElementById("ground-breakup").addEventListener("change", (e) => {
  setGroundBreakup(e.target.checked);
  if (state.objects.ground) rebuildGround();
  logStudio(state.ground.breakup
    ? "per-tile randomising on: three reads a map instead of one, on the "
      + "floor alone"
    : "per-tile randomising off: the floor repeats its picture as laid");
});

document.getElementById("ground-preset").addEventListener("change", async (e) => {
  state.groundPreset = e.target.value;
  // A library floor has maps to fetch; loadGroundMaterial rebuilds when
  // they land, and rebuilds at once for a built-in preset.
  await loadGroundMaterial(state.groundPreset);
  if (state.objects.ground) rebuildGround();
});

// ---------- carrying a prop ----------
// One idea in place of two. A prop being carried is a real prop in the
// scene that happens to be following the cursor: it can be looked at from
// any angle while it is carried, it lands where the ground is under the
// pointer, and picking an existing one back up is the same state again.
// Escape puts it back where it came from, or removes it if it was new.
// ---------- place, then point ----------
// Param, 2026-09-12: "can we also do a click once to place and then a
// second click elsewhere to point direction of the light". The first
// click lands the fixture, the second says what it is lighting, and the
// beam follows the cursor in between so the aim is chosen by eye rather
// than by arithmetic. Escape leaves it pointing straight down, which is
// where it landed.
//
// WHICH FIXTURES HAVE A DIRECTION AT ALL: a sphere shines every way, and
// a strip and a cube shine out of every face, so aiming them would be a
// gesture with no effect. A spot's cone and a panel's lit face both come
// out of the fixture's own -Z, and both are worth aiming.
const AIMABLE_LIGHTS = new Set(["light-spot", "light-panel"]);

const aimMatrix = new THREE.Matrix4();
const aimQuaternion = new THREE.Quaternion();
const aimEuler = new THREE.Euler();
const AIM_UP = new THREE.Vector3(0, 0, 1);

// Turn a fixture so its -Z looks at a point. Matrix4.lookAt builds a
// basis whose +Z runs from the target back to the eye, which IS a
// light's convention -- the same one three uses for a camera -- so -Z
// lands on the target with no sign to get wrong by hand. Written back
// as the three angles the record already carries, so the gumball, the
// save, the scene and the undo all see an ordinary rotation and none of
// them has to learn what aiming is.
function aimFixtureAt(record, point) {
  const from = new THREE.Vector3(record.x, record.y, record.z || 0);
  if (from.distanceToSquared(point) < 1e-6) return false;
  aimMatrix.lookAt(from, point, AIM_UP);
  aimQuaternion.setFromRotationMatrix(aimMatrix);
  aimEuler.setFromQuaternion(aimQuaternion, "XYZ");
  record.rotX = aimEuler.x;
  record.rotY = aimEuler.y;
  record.rotation = aimEuler.z;
  applyPropRotation(record);
  return true;
}

let aimingLight = null;

function lightKindLabel(type) {
  const kind = LIGHT_KINDS.find((one) => one.key === type);
  return kind ? kind.label.toLowerCase() : "light";
}

function beginAimingLight(record) {
  aimingLight = { record, from: { rotX: record.rotX || 0,
    rotY: record.rotY || 0, rotation: record.rotation || 0 } };
  controls.enabled = false;
  canvas.style.cursor = "crosshair";
  logStudio("click where the " + lightKindLabel(record.type)
    + " should point, or escape to leave it pointing down");
}

function endAimingLight(commit) {
  if (!aimingLight) return;
  const { record, from } = aimingLight;
  aimingLight = null;
  controls.enabled = true;
  canvas.style.cursor = state.propEdit ? "pointer" : "";
  if (!commit) {
    // Escape puts it back where it landed rather than leaving it
    // half-turned at whatever the cursor last passed over.
    Object.assign(record, from);
    applyPropRotation(record);
  } else {
    pushUndo("the aim", () => {
      Object.assign(record, from);
      applyPropRotation(record);
      if (state.selectedProp === record) {
        refreshPropOutline();
        refreshPropGumball();
      }
      saveProps();
    });
  }
  refreshPropOutline();
  refreshPropGumball();
  saveProps();
}

function carryNewProp(type) {
  if (!state.bundle) return;
  const centre = state.centre || new THREE.Vector3();
  // Onto the open layer, which is shown if it was hidden: a fixture placed
  // onto a hidden layer would vanish the moment it landed.
  placementLayer();
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
      notePropsMoved(record);
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
  // A loan of edit mode buys one placement. This was it, so the scene
  // goes back to being all camera rather than leaving him in a mode he
  // never asked for and would have to notice to leave.
  if (propEditOneShot) setPropEdit(false);
  // A prop arriving on the open layer earns its tile at once, and a moved
  // one refreshes the coordinates its tile carries in its tooltip.
  refreshLayersShelf();
  // A NEW spot or panel goes straight into aiming: the click that just
  // placed it was the first of the two. A fixture being MOVED (it has a
  // `from`) is not re-aimed -- it already points where he left it.
  if (!from && AIMABLE_LIGHTS.has(record.type)) beginAimingLight(record);
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
    notePropsMoved(record);
  } else {
    // It was new: it never really arrived.
    disposeProp(record.object);
    propsGroup.remove(record.object);
    state.props = state.props.filter((entry) => entry !== record);
    selectProp(null);
  }
  saveProps();
}

// Edit mode has two buttons now, one on the panel and one in the layers
// drawer where the props are actually being chosen. Both drive this, so
// the two faces can never disagree about which mode the scene is in.
// `quietly` skips the log line for the automatic turn-on that follows
// picking a prop from a layer tile, where the mode change is a
// consequence of what the user did rather than something they asked for.
// Set while edit was granted BY a layer-tile click rather than asked for
// at the button. Such a grant is worth exactly one placement (Param:
// "dont auto turn on edit if i move a prop around via the select prop in
// layer and move it, should be a one time placement"), so the drop that
// ends the move puts the scene back to being all camera.
let propEditOneShot = false;
// How long the two presses of escape may be apart and still count as a
// pair. Long enough not to demand a drum roll, short enough that an
// escape now and another after a minute's work are two first presses.
const ESCAPE_PAIR_MS = 2000;
let escapeAt = 0;

function setPropEdit(on, quietly = false) {
  const was = state.propEdit;
  // Any deliberate press of either Edit button makes the mode his, not a
  // loan: it stops being one-shot and stays until he turns it off.
  if (!quietly) propEditOneShot = false;
  if (!on) propEditOneShot = false;
  state.propEdit = on;
  // ONE FACE now, in the Layers drawer. Param, 2026-09-12: "we can
  // then after this remove the edit mode tile and just keep it in
  // layers and this double click function." The tab strip's tile and
  // the panel's button are gone; the loop stays, because the id list
  // is where a face is added or removed and it has always tolerated a
  // missing one.
  for (const id of ["prop-edit", "shelf-prop-edit", "shelf-edit-tile"]) {
    const button = document.getElementById(id);
    if (button) button.classList.toggle("active", on);
  }
  canvas.style.cursor = on ? "pointer" : "";
  if (on) {
    if (!quietly && !was) {
      logStudio("prop edit on: click a prop to pick it up and drag or click to place; "
        + "R and Shift+R rotate, + and - scale, Delete removes, Escape cancels");
    }
  } else if (was) {
    // Leaving edit mode drops any carry and clears the selection: the
    // scene goes back to being all camera.
    if (state.carrying) dropCarriedProp();
    selectProp(null);
    logStudio("prop edit off");
  }
}

for (const id of ["prop-edit", "shelf-prop-edit", "shelf-edit-tile"]) {
  const button = document.getElementById(id);
  // GUARDED. Two of these three are gone from the page, and an
  // unguarded getElementById here would throw during boot and take
  // every handler written after it down with it.
  if (button) {
    button.addEventListener("click", () => setPropEdit(!state.propEdit));
  }
}

document.getElementById("props-clear").addEventListener("click", () => {
  if (!state.bundle) return;
  for (const record of state.props) { disposeProp(record.object); propsGroup.remove(record.object); }
  state.props = [];
  selectProp(null);
  saveProps();
  refreshLayersShelf();
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
  // Counted before anything else can consume the press, but after the
  // stamp, which owns every click while it is in hand.
  const doubled = isDoubleClick(event);
  if (doubled && !state.propEdit && !state.carrying && !aimingLight) {
    toggleLooseGumball(event);
    return;
  }
  // The second of the two clicks a directional fixture takes: this one
  // says what it is lighting. It cannot collide with the carry below --
  // aiming only begins once the carry has ended.
  if (aimingLight) {
    const hit = groundPointAt(event);
    if (hit) aimFixtureAt(aimingLight.record, hit);
    endAimingLight(true);
    return;
  }
  // Carrying something: this click puts it down (whatever the mode -- the
  // carry began with a deliberate library choice).
  if (state.carrying) {
    dropCarriedProp();
    return;
  }
  // The gumball outranks everything: its handles are the explicit
  // controls and they sit over other geometry by design. Raised by
  // edit mode, or by a double click on one prop -- the handles behave
  // the same either way.
  if (gumballIsUpFor(state.selectedProp)) {
    const handle = gumballHandleAt(event);
    if (handle) {
      const record = state.selectedProp;
      // Every handle names its gesture and its axis, so one reader
      // serves all nine: "move-x", "rot-z", "scale-y".
      const [gesture, letter] = handle.split("-");
      const index = { x: 0, y: 1, z: 2 }[letter];
      // THE WHOLE GATHERING, if there is one. The readings are taken
      // about the point the gumball STANDS on, which for a group is
      // its centre and not any one member -- axisDistanceAt and
      // rotationAngleAt both pivot on whatever x, y, z they are
      // handed, so the centre goes in as if it were a record.
      const acting = actingProps();
      const group = acting.length > 1 ? captureGroup(acting) : null;
      const pivot = group ? groupCentre(acting) : record;
      const start = { mode: gesture, index, record, group, pivot,
        startX: record.x, startY: record.y, startZ: record.z || 0,
        startRotation: record.rotation || 0,
        startRotX: record.rotX || 0, startRotY: record.rotY || 0,
        startScale: record.scale || 1 };
      let reading = null;
      if (gesture === "move") reading = axisDistanceAt(event, pivot, index);
      else if (gesture === "rot") reading = rotationAngleAt(event, pivot, index);
      else {
        const ground = groundPointAt(event);
        reading = ground ? Math.max(0.05,
          Math.hypot(ground.x - pivot.x, ground.y - pivot.y)) : null;
      }
      if (reading !== null) {
        state.gumball = Object.assign(start, { startReading: reading });
        controls.enabled = false;
        canvas.setPointerCapture(event.pointerId);
      }
      return;
    }
  }
  // OUT OF EDIT MODE, a click on a fixture opens that fixture's own
  // card beside it. Param: "if we click them when not in edit mode,
  // then a translucent setting pops up next to it where we can control
  // the sliders and options for each type of light, then when we click
  // anywhere not on the light or the menu it disappears".
  //
  // A click on anything else in the viewport closes it, which is the
  // second half of the same sentence. In edit mode neither happens:
  // there the click picks the fixture up, as it always has.
  if (!state.propEdit && !gumballLoose) {
    const fixture = propRecordAt(event);
    if (isLamp(fixture)) {
      openFixturePanel(fixture);
      return;
    }
    closeFixturePanel();
  }
  // Placed props are furniture until the Edit button says otherwise: a
  // click on a tree while composing the camera must never yank the tree
  // (Param: "when an object is placed we can only click the edit mode to
  // move the props around, scale them and rotate them").
  const record = state.propEdit ? propRecordAt(event) : null;
  if (record) {
    // FIRST CLICK SELECTS, SECOND CARRIES. Param, 2026-09-12: "edit
    // mode when its active and then i select an object the first click
    // doesnt immediately make me drag the object around, but a second
    // click on the object does."
    //
    // A click used to pick the prop up at once, which meant every
    // click meant to CHOOSE a thing also moved it by whatever the hand
    // did next -- and in edit mode a click meant for the camera landed
    // on a prop often enough that this was the common case, not the
    // rare one. Choosing and moving are two gestures now.
    if (state.selectedProp !== record) {
      selectProp(record);
      return;
    }
    // Dragging still works for anyone who prefers it: the pointer
    // capture keeps the prop under the cursor until release.
    carryExistingProp(record);
    state.propDrag = true;
    canvas.setPointerCapture(event.pointerId);
  } else if (state.selectedProp || gatheredProps.size) {
    // Empty ground clears the whole gathering, not merely the primary:
    // a set that survived a click on nothing would go on answering
    // Delete long after it looked like it had been dismissed.
    gatheredProps.clear();
    layersAnchor = null;
    selectProp(null);
    refreshLayersShelf();
  }
});
// A DOUBLE CLICK RAISES THE HANDLES, and another puts them away.
// Deliberately not edit mode: edit mode makes every prop grabbable and
// arms the whole keyboard, and he asked for handles on ONE prop with
// none of that ("this does not move us into edit mode").
//
// COUNTED FROM THE POINTER STREAM, not from the browser's own dblclick
// event. Measured in a headless run: no dblclick arrived at the canvas
// at all. The studio is built on pointer events throughout, a pointer
// capture taken mid-drag can swallow the native event, and counting it
// here lets the second click be answered BEFORE the single-click
// behaviours it would otherwise have to undo -- the fixture card, most
// of all, which would open under the handles.
const DOUBLE_CLICK_MS = 400;
const DOUBLE_CLICK_SLOP = 6;      // pixels; a hand is never quite still
let lastPointerDown = null;

function isDoubleClick(event) {
  const now = performance.now();
  const near = lastPointerDown
    && now - lastPointerDown.at < DOUBLE_CLICK_MS
    && Math.hypot(event.clientX - lastPointerDown.x,
      event.clientY - lastPointerDown.y) < DOUBLE_CLICK_SLOP;
  // A double click consumes its own history, so a third click in the
  // same spot begins a fresh pair rather than counting as another.
  lastPointerDown = near ? null
    : { at: now, x: event.clientX, y: event.clientY };
  return !!near;
}

function toggleLooseGumball(event) {
  const record = hoveredProp || propRecordAt(event);
  if (record && record !== gumballLoose) {
    gumballLoose = record;
    // The card would stand over the very handles it has nothing to do
    // with, so it goes before they arrive.
    closeFixturePanel();
    selectProp(record);
    logStudio("handles on " + propTag(record)
      + ": drag an arrow to move, a ring to turn, a square to scale; "
      + "double-click anywhere to put them away");
    return;
  }
  // Anywhere else, or the same prop again: put them away.
  if (gumballLoose) {
    gumballLoose = null;
    selectProp(null);
  }
}

canvas.addEventListener("pointermove", (event) => {
  // The stamp rides the cursor as one unit.
  if (stampRig) {
    const hit = groundPointAt(event);
    if (hit) moveStamp(hit);
    return;
  }
  // Between the two clicks the beam follows the cursor, so the aim is
  // chosen by looking at it rather than by clicking and hoping.
  if (aimingLight) {
    const hit = groundPointAt(event);
    if (hit) {
      aimFixtureAt(aimingLight.record, hit);
      refreshPropOutline();
    }
    return;
  }
  // A live gumball drag: the ring turns the prop, the square scales it,
  // both measured in plan about the prop's feet, the way Rhino reads a
  // gumball drag in top view.
  if (state.gumball && state.gumball.group) {
    // THE GATHERING, moved as one thing. Param: "only one gumball
    // between all objects where i can move them all as a group."
    const { mode, index, group, pivot, startReading } = state.gumball;
    if (mode === "move") {
      const now = axisDistanceAt(event, pivot, index);
      if (now === null) return;
      const travel = now - startReading;
      moveGroup(group, index === 0 ? travel : 0, index === 1 ? travel : 0,
        index === 2 ? travel : 0);
    } else if (mode === "rot") {
      const now = rotationAngleAt(event, pivot, index);
      if (now === null) return;
      turnGroup(group, pivot, index, now - startReading);
    } else {
      const ground = groundPointAt(event);
      if (!ground) return;
      const distance = Math.hypot(ground.x - pivot.x, ground.y - pivot.y);
      scaleGroup(group, pivot, Math.max(0.05, distance / startReading));
    }
    refreshPropOutline();
    refreshGroupOutlinePositions();
    refreshPropGumball();
    return;
  }
  if (state.gumball) {
    const { mode, index, record, startReading, startX, startY, startZ,
      startRotation, startRotX, startRotY, startScale } = state.gumball;
    if (mode === "move") {
      const now = axisDistanceAt(event, record, index);
      if (now === null) return;
      const travel = now - startReading;
      if (index === 0) record.x = startX + travel;
      else if (index === 1) record.y = startY + travel;
      else {
        // Free to go under the floor, which is the point of the Z arrow,
        // but bounded by the prop's own height so a drag cannot fling it
        // out of sight: one body-length down buries anything.
        const reach = propHeightOf(record) + 1;
        record.z = Math.min(reach, Math.max(-reach, startZ + travel));
      }
      record.object.position.set(record.x, record.y, record.z || 0);
      notePropsMoved(record);
    } else if (mode === "rot") {
      const now = rotationAngleAt(event, record, index);
      if (now === null) return;
      const turned = now - startReading;
      if (index === 0) record.rotX = startRotX + turned;
      else if (index === 1) record.rotY = startRotY + turned;
      else record.rotation = startRotation + turned;
      applyPropRotation(record);
    } else {
      const ground = groundPointAt(event);
      if (!ground) return;
      // Scale stays UNIFORM whichever square is dragged: a prop's size is
      // one number in the record, and three independent ones would need
      // the whole model, the layout and every saved scene to grow to
      // carry them. Worth saying rather than pretending otherwise.
      const distance = Math.hypot(ground.x - record.x, ground.y - record.y);
      record.scale = Math.min(5, Math.max(0.2,
        startScale * distance / startReading));
      // Through applyPropSize, which keeps a stretched strip stretched and
      // lays a fixture's light to its new size.
      applyPropSize(record);
    }
    refreshPropOutline();
    refreshPropGumball();
    return;
  }
  // WHAT THE POINTER IS OVER. Before the carry test below, which
  // returns when nothing is being carried -- which is exactly when a
  // hover is worth having.
  hoverPick(event);
  const carried = state.carrying && state.carrying.record;
  if (!carried) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  carried.x = hit.x;
  carried.y = hit.y;
  carried.object.position.set(hit.x, hit.y, carried.z || 0);
  notePropsMoved(carried);
  refreshPropOutline();
  refreshPropGumball();
});
function endPropDrag(event) {
  if (canvas.hasPointerCapture && canvas.hasPointerCapture(event.pointerId)) {
    canvas.releasePointerCapture(event.pointerId);
  }
  if (state.gumball && state.gumball.group) {
    const captured = state.gumball.group;
    state.gumball = null;
    controls.enabled = true;
    const moved = captured.some((was) =>
      Math.abs(was.record.x - was.x) > 1e-6
      || Math.abs(was.record.y - was.y) > 1e-6
      || Math.abs((was.record.z || 0) - was.z) > 1e-6
      || Math.abs((was.record.rotation || 0) - was.rotation) > 1e-6
      || Math.abs((was.record.scale || 1) - was.scale) > 1e-6);
    if (moved) {
      // ONE entry for the whole drag, however many props it moved:
      // fifty entries for one gesture would flush the history and make
      // undo a fifty-press job.
      pushUndo("the group adjustment", () => {
        restoreGroup(captured);
        refreshPropOutline();
        refreshGroupOutlines();
        setPropGumball(state.selectedProp);
        saveProps();
      });
    }
    setPropGumball(state.selectedProp);
    refreshGroupOutlines();
    saveProps();
    return;
  }
  if (state.gumball) {
    const record = state.gumball.record;
    const before = { x: state.gumball.startX, y: state.gumball.startY,
                     z: state.gumball.startZ || 0,
                     rotation: state.gumball.startRotation,
                     rotX: state.gumball.startRotX || 0,
                     rotY: state.gumball.startRotY || 0,
                     scale: state.gumball.startScale };
    state.gumball = null;
    controls.enabled = true;
    const moved = ["x", "y", "z", "rotation", "rotX", "rotY", "scale"]
      .some((key) => Math.abs((record[key] || 0) - (before[key] || 0)) > 1e-6);
    if (moved) {
      pushUndo("the adjustment", () => {
        Object.assign(record, before);
        applyPropRotation(record);
        applyPropSize(record);
        record.object.position.set(before.x, before.y, before.z);
        notePropsMoved(record);
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
  if (event.key === "Escape" && aimingLight) {
    endAimingLight(false);
    return;
  }
  if (event.key === "Escape" && state.carrying) {
    cancelCarry();
    return;
  }
  // The fixture's own card closes BEFORE the drawer: it is the nearer
  // thing on the screen, and closing the drawer under an open card
  // would leave the card floating over nothing he asked for.
  if (event.key === "Escape" && fixturePanelFor) {
    closeFixturePanel();
    return;
  }
  if (event.key === "Escape" && shelfKind) {
    closeShelf();
    return;
  }
  // Handles raised by a double click are the nearest thing in hand
  // after those, so escape puts them away before it touches the mode.
  if (event.key === "Escape" && gumballLoose) {
    gumballLoose = null;
    selectProp(null);
    return;
  }
  // TWICE. Param: "make esc pressed twice come out of edit mode." The
  // first press drops what is in hand -- the selection -- and the
  // second leaves the mode, so a stray tap cannot throw him out of a
  // mode he is working in. The pair has to be a pair: two presses a
  // minute apart are two first presses.
  if (event.key === "Escape" && state.propEdit) {
    const now = performance.now();
    const paired = escapeAt > 0 && now - escapeAt < ESCAPE_PAIR_MS;
    escapeAt = paired ? 0 : now;
    if (paired) {
      setPropEdit(false);
    } else {
      if (state.selectedProp) selectProp(null);
      logStudio("escape again to leave edit mode");
    }
    return;
  }
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  // ---- the keys the hover badge answers to ----
  // Param: "if i have an object i have hovered over and its got this
  // new bouding box i press delete or backspace it should be deleted or
  // the arrow keys to move it say 0.2m each time".
  //
  // The pointer is the more specific gesture: while it is over a prop,
  // that prop is the one being talked about, whatever else may also be
  // selected. No edit mode is required -- that is the point of it.
  if (hoveredProp && (event.key === "Delete" || event.key === "Backspace")) {
    event.preventDefault();
    // The pointer names ONE prop; a gathering names several. Hovering
    // something outside the gathering deletes that one thing, which is
    // what the badge under the cursor is promising. Hovering a MEMBER
    // deletes the gathering, because that is the thing being pointed
    // at -- deleting one prop out of four he had just selected would
    // read as the gathering having been ignored.
    const acting = actingProps();
    // The badge names the RUN over a scattered prop, so Delete takes
    // what the badge names. One keystroke removing a hundred thousand
    // props is a great deal to do at once, which is why the badge says
    // how many before he presses it, and why it is one undo.
    const planting = plantingOf(hoveredProp);
    const going = planting
      ? plantingRecords(planting)
      : (acting.includes(hoveredProp) ? acting : [hoveredProp]);
    setHoveredProp(null);
    deletePropsWithUndo(going);
    return;
  }
  if (hoveredProp && nudgeHoveredProp(event.key)) {
    event.preventDefault();
    return;
  }
  if (!state.propEdit || !state.selectedProp) return;
  if (event.key === "r" || event.key === "R") {
    // R turns one way, Shift+R the other: fifteen degrees a press.
    const step = event.shiftKey ? -Math.PI / 12 : Math.PI / 12;
    state.selectedProp.rotation += step;
    applyPropRotation(state.selectedProp);
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
    applyPropSize(state.selectedProp);
    refreshPropOutline();
    setPropGumball(state.selectedProp);  // the ring re-fits the new size
    saveProps();
  } else if (event.key === "Delete" || event.key === "Backspace") {
    // The whole gathering when there is one, so "select many, press
    // Delete" means what it says.
    deletePropsWithUndo(actingProps());
  }
});

// ---------- deleting a whole gathering, undoably ----------
// Param: "so if i want to do multiple operations like delete when
// selecting many then they all delete." One undo entry for the lot:
// fifty entries for one keystroke would flush the history and make the
// undo a fifty-press job.
function deletePropsWithUndo(records) {
  const going = stillPlaced(records);
  if (!going.length) return;
  if (going.length === 1) { deletePropWithUndo(going[0]); return; }
  // Everything each one needs to come back as itself, taken before any
  // of them is disposed.
  const gone = going.map((record) => ({ type: record.type, x: record.x,
    y: record.y, z: record.z || 0, rotX: record.rotX || 0,
    rotY: record.rotY || 0, rotation: record.rotation, scale: record.scale,
    layer: record.layer,
    size: Array.isArray(record.size) ? record.size.slice() : null,
    lumens: record.lumens, kelvin: record.kelvin, tint: record.tint,
    invisible: record.invisible, aperture: record.aperture,
    softness: record.softness, reach: record.reach, shadow: record.shadow,
    scatter: record.scatter }));
  pushUndo("deleting " + gone.length + " props", async () => {
    for (const one of gone) {
      await ensurePropTemplate(one.type);
      const again = placeProp(one.type, one.x, one.y, one.rotation, false,
        one.scale, one.z || 0, one.rotX || 0, one.rotY || 0);
      if (one.size) {
        again.size = one.size.slice();
        applyPropSize(again);
      }
      adoptLampSettings(again, one);
      if (one.scatter) again.scatter = one.scatter;
      again.layer = layerById(one.layer) ? one.layer : state.activeLayer;
      again.object.visible = layerVisible(again.layer);
    }
    saveProps();
    refreshLayersShelf();
  });
  // ONE pass over state.props for all of them: the per-record call
  // filters the whole list and rewrites the whole layout each time,
  // which is quadratic over a gathering of any size.
  removePropRecords(going);
  if (propEditOneShot) setPropEdit(false);
}

// ---------- deleting one prop, undoably ----------
// Lifted out of the edit-mode keys so that the hover badge's Delete and
// the selection's Delete are the SAME deletion: one of them growing a
// fault the other does not have is exactly what two copies of this
// would buy.
function deletePropWithUndo(record) {
  if (!record) return;
  {
    const gone = { type: record.type, x: record.x, y: record.y,
                   z: record.z || 0, rotX: record.rotX || 0,
                   rotY: record.rotY || 0,
                   rotation: record.rotation, scale: record.scale,
                   layer: record.layer,
                   // A stretched strip comes back at its own length, and a
                   // fixture at its own output and warmth, not at whatever
                   // the Lights sliders happen to say by the time of the undo.
                   size: Array.isArray(record.size) ? record.size.slice() : null,
                   lumens: record.lumens, kelvin: record.kelvin,
                   scatter: record.scatter };
    pushUndo("deleting the " + gone.type, async () => {
      await ensurePropTemplate(gone.type);
      const again = placeProp(gone.type, gone.x, gone.y, gone.rotation,
        false, gone.scale, gone.z || 0, gone.rotX || 0, gone.rotY || 0);
      if (gone.size) {
        again.size = gone.size.slice();
        applyPropSize(again);
      }
      adoptLampSettings(again, gone);
      if (gone.scatter) again.scatter = gone.scatter;
      // Back onto its old layer, or onto the open one if that has been
      // deleted since: an id with no tab could never be hidden again.
      again.layer = layerById(gone.layer) ? gone.layer : state.activeLayer;
      again.object.visible = layerVisible(again.layer);
      saveProps();
      // Undoing a delete must give the tile back too, or the drawer
      // shows one fewer prop than the scene holds.
      refreshLayersShelf();
    });
    // removePropRecord also puts a carried corpse down, or the outline
    // keeps following the cursor and the camera stays locked.
    removePropRecord(record);
    // A loaned edit mode is spent by a delete just as much as by a
    // placement: the prop it was loaned for is gone.
    if (propEditOneShot) setPropEdit(false);
  }
}
// "change" (drag release), not "input": the file's own convention for every
// other slider that rebuilds something, and this one re-runs the recolour
// over every casting's geometry. On the real export that is 233 of them per
// event, which a drag fires dozens of.
// Two readings that had none: nothing wrote them because there was
// nowhere to write. The work stays on change; only the number follows
// the thumb.
document.getElementById("exaggeration").addEventListener("input", (e) => {
  document.getElementById("exaggeration-value").textContent =
    Math.round(+e.target.value);
});
document.getElementById("exaggeration").addEventListener("change", () => recolourSegments());
document.getElementById("orbit-speed").addEventListener("input", (e) => {
  document.getElementById("orbit-speed-value").textContent =
    (+e.target.value).toFixed(1);
});
document.getElementById("overlays-box").addEventListener("change", (e) => {
  setLayer("overlays", e.target.checked);
});
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
// ---------- the tabbed data sheet ----------
// Analysis leads; Overview is renderDataPanel's sheet unchanged; Graphs
// loads the vendored plotting library the first time it is asked for.
function showDataTab(id) {
  for (const button of document.querySelectorAll("#data-tabs button")) {
    button.classList.toggle("active", button.dataset.tab === id);
  }
  for (const pane of document.querySelectorAll("#data-panel .data-tab")) {
    pane.classList.toggle("hidden", pane.id !== id);
  }
  if (id === "data-graphs") renderDataGraphs();
}

function analysisThemeTokens() {
  const style = getComputedStyle(document.documentElement);
  return {
    ink: style.getPropertyValue("--ink").trim() || "#e6e6e6",
    ink2: style.getPropertyValue("--ink-2").trim() || "#a0a0a0",
    line: style.getPropertyValue("--line").trim() || "#393939",
    accent: style.getPropertyValue("--accent").trim() || "#4069fd",
  };
}

function renderAnalysisTab() {
  const holder = document.getElementById("data-analysis");
  if (!state.bundle) {
    holder.innerHTML = "<p>Load a study first.</p>";
    return null;
  }
  // A narrative fault must never take the Data button down with it: the
  // Overview sheet still has the raw numbers, so the failure is shown in
  // place and reported, and the panel opens regardless.
  try {
    const input = computeAnalysisInput(state.bundle, finalStage());
    holder.innerHTML = buildAnalysisHtml(input);
    return input;
  } catch (error) {
    reportProblem("the analysis narrative failed: " + error.message, error);
    holder.textContent = "The narrative could not be built ("
      + error.message + "); the Overview tab still has the raw numbers.";
    return null;
  }
}

let plotlyArrival = null;

function ensurePlotly() {
  // The plotting library is 1.2 MB the boot never pays: injected from the
  // vendor folder the first time the Graphs tab is opened, once.
  if (window.Plotly) return Promise.resolve();
  if (plotlyArrival) return plotlyArrival;
  plotlyArrival = new Promise((arrive, refuse) => {
    const script = document.createElement("script");
    script.src = "/static/vendor/plotly-basic.min.js";
    script.onload = arrive;
    script.onerror = () => refuse(new Error("the plotting library did not load"));
    document.head.appendChild(script);
  });
  return plotlyArrival;
}

async function renderDataGraphs() {
  const holder = document.getElementById("data-graphs");
  if (!state.bundle) {
    holder.innerHTML = "<p>Load a study first.</p>";
    return;
  }
  const input = computeAnalysisInput(state.bundle, finalStage());
  const specs = buildGraphSpecs(input, analysisThemeTokens());
  if (!specs.length) {
    holder.innerHTML = "<p>Graphs read the staged analysis and the member "
      + "forces, and this bundle has neither yet. Run the staged analysis "
      + "and come back.</p>";
    return;
  }
  const done = beginLoading("Preparing graphs");
  try {
    await ensurePlotly();
    holder.innerHTML = "";
    for (const spec of specs) {
      const box = document.createElement("div");
      box.id = spec.id;
      holder.appendChild(box);
      window.Plotly.newPlot(box, spec.data, spec.layout,
        { displayModeBar: false, responsive: true });
    }
  } catch (error) {
    holder.innerHTML = "<p>" + error.message + "</p>";
  } finally {
    done();
  }
}

for (const button of document.querySelectorAll("#data-tabs button")) {
  button.addEventListener("click", () => showDataTab(button.dataset.tab));
}

document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  renderDataPanel(state.bundle ? state.bundle.verification : null);
  renderAnalysisTab();
  showDataTab("data-analysis");
  panel.classList.toggle("hidden");
  // The button wears the sheet's state (his ask), like the Show trio.
  document.getElementById("data-button").classList.toggle(
    "active", !panel.classList.contains("hidden"));
});
document.getElementById("data-close").addEventListener("click", () => {
  document.getElementById("data-panel").classList.add("hidden");
  document.getElementById("data-button").classList.remove("active");
});
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
  document.getElementById("size-slider-value").textContent = Math.round(size * 1000);
  document.getElementById("thickness-input").value = thickness;
  document.getElementById("thickness-input-value").textContent = Math.round(thickness * 1000);
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
  const params = { material, pattern: state.pattern, size: state.size,
    thickness: state.thickness, density: skinDensity() };
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        export: exportName, material, pattern: params.pattern,
        size: params.size, thickness: params.thickness,
        // Staged with the weight the vault is wearing, so the stress
        // numbers describe the building on screen.
        density: params.density,
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
// currentStageIndex (the HUD's stage line).
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
  // The graphs are NOT invalidated here: the only way in is loadStudy,
  // which invalidates once its columns are in. Doing it here too built
  // them once with no columns (the card flashed away and back) and again.
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
// film ending on the frame the strike finishes ("continue the rotation one
// more time so we look at the final form").
//
// It lasts exactly as long as the camera needs to come back round to the
// bearing the take started on, never more than one revolution (Param,
// 2026-09-15; finalOrbitTurn in fields.js holds the rule). That replaces the
// half turn and its 40 s cap: a capped turn could not be relied on to end
// where the take began. A still camera still pauses on the result.
const ADMIRE_MIN_SECONDS = 4;

// Where the formwork has gone, on the take's clock: the end of the strike.
function strikeEndSeconds() {
  return openingSeconds() + placementCount() * placementStep()
    + DROP_SECONDS + STRIKE_SECONDS;
}

function admireSeconds() {
  const spin = state.timeline ? state.timeline.orbitSpeed : 0;
  if (!(spin > 0)) return ADMIRE_MIN_SECONDS;
  return finalOrbitTurn(spin, strikeEndSeconds() - openingSeconds()) / spin;
}

// How far the take's camera has turned at t: the spin since the opening
// act, held on the start bearing once the last turn has brought it there,
// so a frame rounded past the end cannot carry it on.
function orbitTurned(t) {
  const spin = state.timeline.orbitSpeed;
  const turning = strikeEndSeconds() - openingSeconds();
  const whole = spin * turning + finalOrbitTurn(spin, turning);
  return Math.min(spin * Math.max(0, t - openingSeconds()), whole);
}

function timelineDuration() {
  return strikeEndSeconds() + admireSeconds();
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
  // Each casting owns its instance so a lens can tint per piece (the
  // heatmaps swap materials piecewise), and so nothing ever leaks into
  // the shared registry entry other code reads from.
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

// ---------- the inked outline ----------
// Param: "a outline slider... it will just add a dark line around the
// vault voussoirs as an outline. the slider goes from a 0 line to
// thicker line."
//
// Drawn as geometry rather than as lines, because WebGL ignores
// linewidth on every desktop driver: a LineSegments outline is one pixel
// wide for ever, and a slider that cannot thicken is not the feature he
// asked for. So each voussoir gets a ribbon round its own top boundary,
// lying just off the face and running INWARD from the edge. Inward
// matters twice: the line never bleeds across a joint on to its
// neighbour, and at corners the two ribbons overlap instead of leaving a
// notch.
//
// The width is a UNIFORM, not geometry: the ribbon is built once per cut
// with a side vector per vertex, and the slider only moves a number. So
// dragging it is free even on a 1500-piece vault.
const OUTLINE_LIFT = 0.0015;         // metres off the face, against z-fighting
const outlineWidth = { value: 0 };
const outlineMaterial = new THREE.MeshBasicMaterial({
  color: 0x15120f, side: THREE.DoubleSide });
outlineMaterial.onBeforeCompile = (shader) => {
  // This hook shadows the prototype's, so it hands the atmosphere its
  // uniforms itself, or the ribbon would compile a fog with no densities.
  atmosphere.inject(shader);
  shader.uniforms.outlineWidth = outlineWidth;
  shader.vertexShader = "attribute vec3 outlineSide;\n"
    + "uniform float outlineWidth;\n"
    + shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\n  transformed += outlineSide * outlineWidth;");
};

// Which edges of one FACE of the piece are its OUTLINE. Not the order the
// corners arrive in: pieces.py emits "mid" as the cell's used corners,
// which is a list, not a loop, and joining it corner by corner drew long
// chords wandering across the vault -- it looked like a fishing net, not
// like voussoirs. The boundary is derived instead, the way a boundary
// always is: take every edge of every face on the side asked for, and
// keep the ones exactly one face uses. An edge two faces share is an
// interior seam of the triangulation and no part of the piece's outline.
//
// underside picks the far side of the casting: a piece's points run
// 0..count-1 on the top and count..2*count-1 underneath it, so the two
// surfaces are the same loop read off two ranges (Param: "make sure it
// shows on the underside of the skin too, not just the outside"). The
// indices come back rebased to 0..count-1 either way, so one ribbon
// builder serves both.
function boundaryEdges(faces, count, underside) {
  const low = underside ? count : 0;
  const high = low + count;
  const seen = new Map();
  for (const face of faces) {
    let ours = true;
    for (const index of face) {
      if (index < low || index >= high) { ours = false; break; }
    }
    if (!ours) continue;               // the other surface, or a side wall
    for (let i = 0; i < face.length; i++) {
      const a = face[i] - low, b = face[(i + 1) % face.length] - low;
      const key = a < b ? a + ":" + b : b + ":" + a;
      const already = seen.get(key);
      if (already) already.uses += 1;
      else seen.set(key, { a, b, uses: 1 });
    }
  }
  const edges = [];
  for (const edge of seen.values()) {
    if (edge.uses === 1) edges.push(edge);
  }
  return edges;
}

// The ribbon for one FACE of one piece: that face's corners (already
// shrunk the way the casting was), the outward normal at each, and the
// centroid that says which way "inward" is. Called twice per casting,
// once per surface, and the two results are drawn as one mesh.
function outlineRibbon(loop, normals, centre, edges, into) {
  const positions = into ? into.positions : [];
  const sides = into ? into.sides : [];
  for (const edge of edges) {
    const a = loop[edge.a], b = loop[edge.b];
    const na = normals[edge.a], nb = normals[edge.b];
    let nx = na[0] + nb[0], ny = na[1] + nb[1], nz = na[2] + nb[2];
    const nl = Math.hypot(nx, ny, nz) || 1;
    nx /= nl; ny /= nl; nz /= nl;
    let ex = b[0] - a[0], ey = b[1] - a[1], ez = b[2] - a[2];
    const el = Math.hypot(ex, ey, ez);
    if (el < 1e-9) continue;          // a repeated corner draws nothing
    ex /= el; ey /= el; ez /= el;
    // Square to the edge, IN the surface: normal cross edge.
    let sx = ny * ez - nz * ey;
    let sy = nz * ex - nx * ez;
    let sz = nx * ey - ny * ex;
    const sl = Math.hypot(sx, sy, sz) || 1;
    sx /= sl; sy /= sl; sz /= sl;
    const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, mz = (a[2] + b[2]) / 2;
    if (sx * (centre[0] - mx) + sy * (centre[1] - my)
        + sz * (centre[2] - mz) < 0) {
      sx = -sx; sy = -sy; sz = -sz;
    }
    const A = [a[0] + nx * OUTLINE_LIFT, a[1] + ny * OUTLINE_LIFT,
               a[2] + nz * OUTLINE_LIFT];
    const B = [b[0] + nx * OUTLINE_LIFT, b[1] + ny * OUTLINE_LIFT,
               b[2] + nz * OUTLINE_LIFT];
    // Two triangles, the outer pair of corners carrying the side vector
    // that the width uniform stretches along. At width 0 all four sit on
    // the boundary, the quad has no area, and nothing is drawn.
    for (const [point, out] of [[A, 0], [B, 0], [B, 1], [A, 0], [B, 1], [A, 1]]) {
      positions.push(point[0], point[1], point[2]);
      sides.push(out * sx, out * sy, out * sz);
    }
  }
  return { positions, sides };
}

// Zero costs nothing. A vault is one draw call per casting already, and
// drawing 1500 more ribbons with no width in them would double that for
// an invisible result -- so at zero they stop being drawn at all.
function setOutlineVisible(on) {
  if (!state.objects.shell) return;
  for (const segment of state.objects.shell.children) {
    for (const child of segment.children) {
      if (child.userData.outline) child.visible = on;
    }
  }
}

function applyOutline() {
  outlineWidth.value = state.outline;
  document.getElementById("outline-width-value").textContent =
    Math.round(state.outline * 1000);
  // A restored scene writes the slider straight, which leaves the row's
  // fill behind unless it is repainted here.
  paintScrub(document.getElementById("outline-width"));
  setOutlineVisible(state.outline > 0);
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
    // The corners of both surfaces, shrunk exactly as the casting was:
    // the paths the inked outline runs along, once the boundary edges of
    // each are known. A vault is looked at from underneath more than from
    // above, so the underside gets the same line (Param: "make sure it
    // shows on the underside of the skin too").
    const place = (p) => (shrink === 1 ? [p[0], p[1], p[2]] : [
      centre[0] + (p[0] - centre[0]) * shrink,
      centre[1] + (p[1] - centre[1]) * shrink,
      centre[2] + (p[2] - centre[2]) * shrink]);
    const above = [], below = [], under = [];
    for (let i = 0; i < count; i++) {
      above.push(place(points[i]));
      below.push(place(points[i + count]));
      // The underside's outward normal is the surface normal reversed,
      // which is what lifts its ribbon clear of the face rather than
      // burying it in the casting.
      const n = piece.normals[i];
      under.push([-n[0], -n[1], -n[2]]);
    }
    const ribbon = { positions: [], sides: [] };
    outlineRibbon(above, piece.normals, centre,
      boundaryEdges(piece.faces, count, false), ribbon);
    outlineRibbon(below, under, centre,
      boundaryEdges(piece.faces, count, true), ribbon);
    built.push({ piece, positions, weights, surface, centre, outline: ribbon });
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
    mesh.userData.course = piece.course;
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
    // The outline rides as a CHILD of its own casting, which is what makes
    // it follow the build: applySceneAtTime moves, scales and hides each
    // casting and nothing else, so a child inherits the drop, the sprayed
    // growth and the not-yet-placed invisibility for free.
    const ribbon = entry.outline;
    if (ribbon.positions.length) {
      const inked = new THREE.BufferGeometry();
      inked.setAttribute("position", new THREE.BufferAttribute(
        new Float32Array(ribbon.positions), 3));
      inked.setAttribute("outlineSide", new THREE.BufferAttribute(
        new Float32Array(ribbon.sides), 3));
      const line = new THREE.Mesh(inked, outlineMaterial);
      line.castShadow = line.receiveShadow = false;
      line.userData.outline = true;
      line.visible = state.outline > 0;
      mesh.add(line);
    }
    group.add(mesh);
  }
  state.objects.shell = group;
  scene.add(group);
  applyOutline();
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

// Which tint each material has been given, by skin key. A reset, a scene
// or a layout from before this existed carries none.
function skinTints() {
  if (!state.appearance.tints || typeof state.appearance.tints !== "object") {
    state.appearance.tints = {};
  }
  return state.appearance.tints;
}

// The swatch shows the colour the vault is actually wearing: the tint
// chosen for this material, or the material's own when none has been.
// White was shown for "no tint" whatever the material, which read as a
// white tint laid over it.
function paintTintSwatch() {
  let own = "#ffffff";
  if (state.bundle) own = "#" + appearanceMaterialBase().color.getHexString();
  document.getElementById("material-tint").value = state.appearance.tint || own;
}

function syncAppearanceControls() {
  document.getElementById("render-skin").value = state.appearance.skin;
  paintTintSwatch();
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
    variation: 1, uvSeed: 0, grain: false, tints: {} };
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
        tints: {},
      };
      if (parsed.tints && typeof parsed.tints === "object") {
        for (const [skin, hex] of Object.entries(parsed.tints)) {
          if (typeof hex === "string") appearance.tints[skin] = hex;
        }
      }
      // Saved before tints were kept per material: the one tint there was
      // belonged to the material it was saved with.
      if (appearance.tint && !appearance.tints[appearance.skin]) {
        appearance.tints[appearance.skin] = appearance.tint;
      }
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
  // The machine reads the net's own frames (it draws each wire to its net
  // vertex), so it is built on the same beat. It loads library materials,
  // so it finishes asynchronously and shows up a moment later.
  buildMachine();
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
    syncNetShadow(formworkObjects.net);
    if (show.net) {
      writeInstancedSegments(formworkObjects.net, doc.edges, frame.vertices);
      formworkObjects.net.position.z = lift.wires;
    }
  }
  if (formworkObjects.nodes) {
    formworkObjects.nodes.visible = show.net;
    syncNetShadow(formworkObjects.nodes);
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
      syncNetShadow(bars);
    }
  }
}

// ---------- the machine ----------
// bench.mechanism/1: the rig that pulls the net. Shape only -- the motion
// is the formwork frames', which the studio already replays -- so this
// act adds no clock of its own. It rides WITH the formwork (Param's
// ruling), which is also what makes the strike honest: the machine goes
// away with the columns and the net, and the anchors and tension ties
// stay, because those two are the permanent works.
let machineObjects = null;

function disposeMachine() {
  const row = document.getElementById("machine-row");
  if (row) row.classList.add("hidden");
  if (!machineObjects) return;
  scene.remove(machineObjects.group);
  machineObjects.group.traverse((child) => {
    if (child.isMesh) {
      child.geometry.dispose();
      if (child.material && child.material.dispose) child.material.dispose();
    }
  });
  machineObjects = null;
}

// The wire, from a centreline the pure reader has already prepared (see
// wireCentreline in mechanism.js: the frames ARE the centreline by
// Param's ruling, so nothing is offset, and the spools' five-frames-a-turn
// sampling is subdivided by rotation about the drum axis). This function
// only sweeps a circle along that line.
//
// The ring's own axes come from parallel transport, not from the frames:
// each ring's x is the previous ring's x with its along-tangent part
// removed. That is the rotation-minimising frame, and it is what stops a
// tube twisting between rings. The radius is the studio's own wire
// radius, so the machine's wires match the net's by construction.
const WIRE_SIDES = 8;

function loftWire(points, radius) {
  const path = [];
  for (const p of points) {
    const last = path[path.length - 1];
    // A repeated point folds the loft, so it is skipped rather than drawn.
    if (last && Math.hypot(p[0] - last[0], p[1] - last[1], p[2] - last[2]) < 1e-6) continue;
    path.push(p);
  }
  const count = path.length;
  if (count < 2) return null;
  const tangentAt = (i) => {
    const a = path[Math.max(i - 1, 0)], b = path[Math.min(i + 1, count - 1)];
    const d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const l = Math.hypot(d[0], d[1], d[2]) || 1;
    return [d[0] / l, d[1] / l, d[2] / l];
  };
  const positions = [], indices = [];
  let x = null;
  for (let i = 0; i < count; i++) {
    const tn = tangentAt(i);
    if (x) {
      const along = x[0] * tn[0] + x[1] * tn[1] + x[2] * tn[2];
      x = [x[0] - tn[0] * along, x[1] - tn[1] * along, x[2] - tn[2] * along];
      const l = Math.hypot(x[0], x[1], x[2]);
      x = l > 1e-6 ? [x[0] / l, x[1] / l, x[2] / l] : null;
    }
    if (!x) {
      // Any direction square to the tangent will do for the first ring.
      const seed = Math.abs(tn[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
      x = [tn[1] * seed[2] - tn[2] * seed[1], tn[2] * seed[0] - tn[0] * seed[2],
           tn[0] * seed[1] - tn[1] * seed[0]];
      const l = Math.hypot(x[0], x[1], x[2]) || 1;
      x = [x[0] / l, x[1] / l, x[2] / l];
    }
    const y = [tn[1] * x[2] - tn[2] * x[1], tn[2] * x[0] - tn[0] * x[2],
               tn[0] * x[1] - tn[1] * x[0]];
    const p = path[i];
    for (let k = 0; k < WIRE_SIDES; k++) {
      const a = (k / WIRE_SIDES) * Math.PI * 2;
      const cx = Math.cos(a) * radius, cy = Math.sin(a) * radius;
      positions.push(p[0] + x[0] * cx + y[0] * cy,
                     p[1] + x[1] * cx + y[1] * cy,
                     p[2] + x[2] * cx + y[2] * cy);
    }
  }
  for (let r = 0; r + 1 < count; r++) {
    const a = r * WIRE_SIDES, b = (r + 1) * WIRE_SIDES;
    for (let i = 0; i < WIRE_SIDES; i++) {
      const j = (i + 1) % WIRE_SIDES;
      indices.push(a + i, b + i, b + j, a + i, b + j, a + j);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position",
    new THREE.BufferAttribute(new Float32Array(positions), 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function geometryFromPart(part) {
  let geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position",
    new THREE.BufferAttribute(new Float32Array(part.geometry.vertices), 3));
  geometry.setIndex(part.geometry.triangles);
  // Smooth normals while the corners are still shared, so a drum reads as
  // round rather than as a barrel of flat staves.
  geometry.computeVertexNormals();
  // A library material without UVs samples one texel for the whole part,
  // which is why the reels read as flat beige rather than as birch (Param:
  // "The wood texture on the reels arent nice, we have proper textures to
  // use"). Box projection wants a triangle soup, and its scale is UV units
  // per metre, so 1 / tileMetres gives one repeat per the size the picture
  // declares itself to be.
  geometry = geometry.toNonIndexed();
  const positions = geometry.getAttribute("position").array;
  let cx = 0, cy = 0, cz = 0;
  const points = positions.length / 3;
  for (let i = 0; i < positions.length; i += 3) {
    cx += positions[i]; cy += positions[i + 1]; cz += positions[i + 2];
  }
  const centre = points ? [cx / points, cy / points, cz / points] : [0, 0, 0];
  const entry = libraryEntry(part.material);
  const tile = (entry && entry.tileMetres) || [DEFAULT_TILE_METRES, DEFAULT_TILE_METRES];
  const uvs = boxUVs(positions, centre, [0, 0], 1 / tile[0], 1 / tile[1]);
  geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
  return geometry;
}

// Param owns this mapping from the panel, so a re-skin is not a
// re-export. A library material that will not load falls back to a plain
// grey rather than leaving the part invisible: a machine you can see in
// the wrong colour beats a machine you cannot see.
function machineMaterial(part) {
  let base = null;
  if (libraryCache.has(part.material)) base = libraryCache.get(part.material).material;
  const material = base ? base.clone()
    : new THREE.MeshStandardMaterial({ color: 0x8d9298, roughness: 0.55, metalness: 0.6 });
  if (part.tint) material.color.set(part.tint);
  return material;
}

// One machine mesh, remembering which library set it wants and what tint
// goes over it, so skinMachine can re-skin it in place when the set lands.
function machineMesh(geometry, part) {
  const mesh = new THREE.Mesh(geometry, machineMaterial(part));
  mesh.userData.machineSkin = part.material;
  mesh.userData.machineTint = part.tint || null;
  mesh.castShadow = mesh.receiveShadow = true;
  return mesh;
}

// THE fault behind "the material we have now is so ugly": machineMaterial
// only ever READ libraryCache, and nothing had ever asked for the
// machine's materials, so all seven names missed and every part fell
// through to the same 0x8d9298 grey -- frames, motors, reels, pulleys and
// anchor alike, one flat colour on the lot. The names were never wrong;
// all seven exist in his studio-skin folder. buildPrincipalBars has
// fetched its set this way since the bars were added, which is exactly
// why THEY looked right in the same render.
//
// Fetched once per distinct key, worn on every mesh that asked for it,
// and pinned so the cache cannot dispose a set a live mesh points at.
function skinMachine(group, mine) {
  const wanted = new Map();
  group.traverse((object) => {
    const key = object.userData && object.userData.machineSkin;
    if (!key || !isLibraryKey(key)) return;
    if (!wanted.has(key)) wanted.set(key, []);
    wanted.get(key).push(object);
  });
  for (const key of wanted.keys()) libraryPins.add(key);
  const jobs = [];
  for (const [key, meshes] of wanted) {
    jobs.push(ensureLibraryMaterial(key).then((set) => {
      if (!set || mine !== machineBuild) return null;
      for (const mesh of meshes) {
        const worn = set.material.clone();
        // The tint multiplies the albedo, so the grain survives and only
        // the coat's darkness changes -- what anodising actually does.
        if (mesh.userData.machineTint) worn.color.set(mesh.userData.machineTint);
        if (mesh.material.side === THREE.DoubleSide) worn.side = THREE.DoubleSide;
        mesh.material.dispose();
        mesh.material = worn;
      }
      return key;
    }));
  }
  // Counted and said, so "the colour scheme changed again" is answerable
  // from the log instead of from a screenshot.
  Promise.all(jobs).then((worn) => {
    if (mine !== machineBuild) return;
    const landed = worn.filter(Boolean).length;
    logStudio("machine: wearing " + landed + " of " + wanted.size
      + " library materials"
      + (landed < wanted.size ? "; the rest kept the fallback grey" : ""));
    // The worn skins are NEW materials, so the strike's fade has to be
    // told about them; told nothing, the machine reversed out at full
    // strength wearing the library's coats.
    if (machineObjects && machineObjects.machineSkins) {
      machineObjects.skins = machineObjects.machineSkins();
    }
    // The anchor and the tie wear new coats too, which the capture has not
    // been handed yet.
    noteReflectionsChanged();
    renderView();
  });
}

// A reel's winding radius when no wire tells us: the nearest any of its
// own vertices stands to its axis, which is the barrel. The furthest is
// the flange, and a spin worked out at the flange turns too slowly by
// the ratio of the two. The contact radius from the routing frames is
// preferred wherever a wire names the reel (reelContactRadius).
function measureSpoolRadius(part) {
  const v = part.geometry.vertices;
  if (!v.length) return 0.03;
  if (part.axis) {
    const [ox, oy, oz] = part.axis.origin;
    const [dx, dy, dz] = part.axis.direction;
    let nearest = Infinity;
    for (let i = 0; i + 2 < v.length; i += 3) {
      const px = v[i] - ox, py = v[i + 1] - oy, pz = v[i + 2] - oz;
      const along = px * dx + py * dy + pz * dz;
      const r = Math.hypot(px - dx * along, py - dy * along, pz - dz * along);
      if (r > 1e-3 && r < nearest) nearest = r;
    }
    if (Number.isFinite(nearest)) return nearest;
  }
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (let i = 0; i + 2 < v.length; i += 3) {
    minX = Math.min(minX, v[i]); maxX = Math.max(maxX, v[i]);
    minY = Math.min(minY, v[i + 1]); maxY = Math.max(maxY, v[i + 1]);
    minZ = Math.min(minZ, v[i + 2]); maxZ = Math.max(maxZ, v[i + 2]);
  }
  const half = [(maxX - minX) / 2, (maxY - minY) / 2, (maxZ - minZ) / 2]
    .sort((a, b) => b - a);
  return half[1] > 1e-4 ? half[1] : 0.03;
}

// Param counted seven motors and saw one, and the census agrees with him
// about the FILE: mechanism.motors is one body (35,754 vertices that weld
// to a single component) standing beside the seventh spool, and nothing
// in the schema repeats it per reel. Until the exporter authors seven,
// the one motor is stamped at every spool of the same bank, shifted by
// each spool's axis origin relative to the spool it was authored beside.
// That is what he modelled -- a drive on every spool -- and the log says
// it was done here rather than read.
// How much of the bank a single motor body has to cover before it is
// read as being the whole bank rather than one motor of it. Half is a
// wide margin either way: his body reaches 118% of the bank, and one
// motor of seven would reach about 17%.
const MOTOR_BANK_SHARE = 0.5;

function motorShifts(model) {
  const motors = model.parts.filter((part) => part.kind === "motor");
  const reels = model.parts.filter((part) => part.kind === "reel" && part.axis);
  if (motors.length !== 1 || reels.length < 2) return [[0, 0, 0]];
  const v = motors[0].geometry.vertices;
  let cx = 0, cy = 0, cz = 0;
  for (let i = 0; i + 2 < v.length; i += 3) { cx += v[i]; cy += v[i + 1]; cz += v[i + 2]; }
  const count = v.length / 3 || 1;
  const centre = [cx / count, cy / count, cz / count];
  let home = null, best = Infinity;
  for (const reel of reels) {
    const o = reel.axis.origin;
    const d = Math.hypot(o[0] - centre[0], o[1] - centre[1], o[2] - centre[2]);
    if (d < best) { best = d; home = reel; }
  }
  const hd = home.axis.direction;
  // The bank: every reel whose axis runs the same way as the home reel's.
  const bank = reels.filter((reel) => {
    const d = reel.axis.direction;
    return d[0] * hd[0] + d[1] * hd[1] + d[2] * hd[2] > 0.999;
  });
  if (bank.length < 2) return [[0, 0, 0]];
  const shifts = bank.map((reel) => [
    reel.axis.origin[0] - home.axis.origin[0],
    reel.axis.origin[1] - home.axis.origin[1],
    reel.axis.origin[2] - home.axis.origin[2],
  ]);

  // IS THE ONE BODY ONE MOTOR, OR THE WHOLE BANK? Measured, not assumed.
  //
  // The bank's own line is the two spool positions furthest apart; the
  // body's reach along that line is compared with it. On his file the
  // seven spools span 0.820 m and the motor body spans 0.965 m along the
  // same line -- so the single body IS the bank, with all seven motors
  // already modelled in it. Stamping it at each spool made 49 motors a
  // machine and 294 across the site (Param: "I also have found way too
  // many motors?"). It is stamped ONCE.
  //
  // A body that is genuinely one motor is a small fraction of the bank
  // and still gets stamped at every spool, which is what the earlier
  // reading was for and what a later export may well send.
  let axis = null, span = 0;
  for (let i = 0; i < shifts.length; i++) {
    for (let j = i + 1; j < shifts.length; j++) {
      const dx = shifts[j][0] - shifts[i][0];
      const dy = shifts[j][1] - shifts[i][1];
      const dz = shifts[j][2] - shifts[i][2];
      const d = Math.hypot(dx, dy, dz);
      if (d > span) { span = d; axis = [dx / d, dy / d, dz / d]; }
    }
  }
  if (!axis || span < 1e-6) return [[0, 0, 0]];
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i + 2 < v.length; i += 3) {
    const along = v[i] * axis[0] + v[i + 1] * axis[1] + v[i + 2] * axis[2];
    if (along < lo) lo = along;
    if (along > hi) hi = along;
  }
  if (hi - lo > span * MOTOR_BANK_SHARE) return [[0, 0, 0]];
  return shifts;
}

const machineShift = new THREE.Matrix4();
const machineBox = new THREE.Box3();
const machineCorner = new THREE.Vector3();

// The lowest world z any corner of this geometry reaches under a matrix.
function lowestZ(geometry, matrix) {
  geometry.computeBoundingBox();
  machineBox.copy(geometry.boundingBox);
  let low = Infinity;
  for (let i = 0; i < 8; i++) {
    machineCorner.set(i & 1 ? machineBox.max.x : machineBox.min.x,
                      i & 2 ? machineBox.max.y : machineBox.min.y,
                      i & 4 ? machineBox.max.z : machineBox.min.z);
    if (matrix) machineCorner.applyMatrix4(matrix);
    low = Math.min(low, machineCorner.z);
  }
  return low;
}

// One build at a time. buildMachine awaits its materials, so two loads in
// quick succession both got past disposeMachine before either had added
// anything, and the scene ended up with two machines in it.
// Where the machines stand when the document does not say. Param: "if i
// dont add in a mechanism to the json, i need you to be able to add in
// the mechanisms and anchors where applicable."
//
// Runs ONLY on a document with no instances. Verified against his own
// study: 42 supports give two springings of 21, six machines of seven
// cables, and the machine that HE authored lands back at its own spool
// centre to four decimal places, with the other five derived from it.
//
// The shaping is all in mechanism.js, pure and node-tested. This only
// gathers what it needs out of the scene and turns its answer back into
// the instances and wires the rest of the build already understands.
function deriveMachines(model) {
  const loaded = state.bundle;
  const mesh = loaded && loaded.analysis_mesh;
  const ids = loaded && Array.isArray(loaded.supports) ? loaded.supports : [];
  if (!mesh || !Array.isArray(mesh.vertices) || ids.length < 2) return null;
  const points = [];
  for (const id of ids) {
    const v = mesh.vertices[id];
    if (!v) return null;               // a support the net does not carry
    points.push([v[0], v[1], v[2]]);
  }
  // A SPOOL, not a pulley: they arrive under the same `reels` key and
  // only the winding radius separates them. The writer's own figure
  // first, the studio's measurement behind it.
  const spools = [];
  for (const part of model.parts) {
    if (part.kind !== "reel" || !part.axis) continue;
    const radius = Number.isFinite(+part.windingRadius)
      ? +part.windingRadius : measureSpoolRadius(part);
    if (radius < SPOOL_RADIUS_LIMIT) spools.push(part.axis.origin);
  }
  const middle = [0, 0, 0];
  for (const v of mesh.vertices) {
    middle[0] += v[0] / mesh.vertices.length;
    middle[1] += v[1] / mesh.vertices.length;
    middle[2] += v[2] / mesh.vertices.length;
  }
  const derived = derivePlacements(points, spools, middle);
  for (const note of derived.notes) logStudio("machine: " + note);
  if (!derived.instances.length) return null;
  // Back into the net's OWN numbering: derivePlacements works in its own
  // indices into the support list it was given, and every consumer
  // downstream speaks net vertex indices.
  for (const instance of derived.instances) {
    instance.netVertices = instance.netVertices.map((i) => ids[i]);
  }
  for (const anchor of derived.anchors) {
    anchor.netVertices = anchor.netVertices.map((i) => ids[i]);
  }
  derived.wires = derived.wires.map((wire) => ({
    id: wire.id,
    netVertex: ids[wire.support],
    reeveFactor: 1,
    spoolRadius: null,
    // ONE frame, at the spool the cable leaves from. A derived wire
    // knows where the cable ends and nothing about how it wraps, so the
    // free span is drawn and the routed portion is not -- which is the
    // honest picture rather than an invented wrap.
    route: [{
      matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0,
        spools[wire.spool][0], spools[wire.spool][1], spools[wire.spool][2], 1],
      owner: "reel", ownerReel: wire.spool,
    }],
    path: [{ side: wire.side, mechanism: wire.mechanism }],
  }));
  return derived;
}

let machineBuild = 0;

async function buildMachine() {
  const mine = ++machineBuild;
  disposeMachine();
  // Cleared HERE, at the top, not after the build: the wire material adds
  // its own pin part way through, and clearing afterwards wiped it --
  // leaving the cables' metal, which the principal bars wear too, open to
  // eviction on every build.
  libraryPins.clear();
  // The machine needs the document alone. This used to also wait on
  // state.bundle, and on a fresh page the formwork objects are rebuilt
  // BEFORE the bundle lands, so the first build of every session quietly
  // did nothing -- one half of "it did it once, now it doesnt".
  if (!state.mechanism) return;
  const model = readMechanism(state.mechanism);
  if (!model.ok) {
    logStudio("the machine document was not read: " + model.reason);
    return;
  }
  for (const note of model.notes) logStudio("machine: " + note);
  if (!model.parts.length) {
    logStudio("the machine document carries no readable parts");
    return;
  }

  // Loaded before anything is built, so no part pops in wearing the
  // fallback grey a frame after the rest.
  await Promise.all([...new Set(model.parts.map((part) => part.material))]
    .map((key) => ensureLibraryMaterial(key)));
  if (mine !== machineBuild) return;      // another load started meanwhile

  const group = new THREE.Group();
  const permanent = new THREE.Group();      // what remains after the strike
  const temporary = new THREE.Group();      // what leaves with the formwork
  group.add(permanent, temporary);
  const spinners = [];
  // The document is authoritative when it carries instances; the studio
  // derives only when it carries none. Agreed with the exporter session:
  // one source of truth per study, and he can see a wrong placement in
  // the Rhino viewport before exporting, which no importer can offer.
  const derived = model.instances.length ? null : deriveMachines(model);
  if (derived) {
    // THE DERIVED PLACEMENT BECOMES THE MODEL'S, not a parallel copy
    // beside it. Held only in a local it was invisible to everything
    // that reads the model, and two things went wrong at once, both
    // measured on his study with the derivation forced:
    //
    //   reportMachineChecks puts a wire's head into world space through
    //   model.instances, so with none there the head stayed in the
    //   BODY's own space and every derived wire was reported 18 m from
    //   the vertex it names -- a wall of false alarms about correct work;
    //
    //   and the "missing placements" banner below tests the same field,
    //   so it fired on a machine that had in fact been placed, telling
    //   him the machine "is drawn once and does not run" while six of
    //   them stood on screen.
    model.instances = derived.instances;
    model.wires = derived.wires;
    // Anchors are READ before they are derived, the same rule as the
    // instances: the writer emits them whenever a result is wired, and
    // a document that carries its own is never second-guessed.
    if (!model.anchors.length) model.anchors = derived.anchors;
    showBanner("This mechanism carries no placements, so the machines are "
      + "derived from the vault's own supports: " + derived.instances.length
      + " machines pulling " + derived.wires.length + " cables", "info");
  }
  const instances = model.instances.length ? model.instances
    : [{ side: 0, mechanism: 0, matrix: null, mirrored: false, wireIds: [] }];

  // Param, on an export that carried none: "I am only getting one
  // mechanism why?" Because a document with no placements can honestly be
  // drawn only one way -- the body once, where it was authored -- and the
  // fallback above does exactly that. But a SILENT fallback is
  // indistinguishable from a studio that has lost five machines, which is
  // why he had to ask. It says so now, in the banner as well as the log,
  // and names the exporter as where placements come from so the next
  // question starts in the right place.
  if (!model.instances.length) {
    logStudio("machine: this document carries NO instances, so the machine "
      + "is drawn ONCE, where its body was authored. Placements come from "
      + "the exporter, so this is a gap in the export rather than in the "
      + "studio.");
  }
  if (!model.wires.length) {
    logStudio("machine: this document carries NO wires, so no cables are "
      + "drawn and the reels have nothing to measure a take-up against; "
      + "they will not turn.");
  }
  if (!model.instances.length || !model.wires.length) {
    // showBanner logs the text itself, so the two lines above carry the
    // detail and this one carries only what he needs at a glance.
    showBanner("This mechanism export is missing its "
      + [model.instances.length ? null : "machine placements",
         model.wires.length ? null : "wires"].filter(Boolean).join(" and ")
      + ", so the machine is drawn once and does not run", "error");
  }

  // The drums' axes, and the radius each actually winds at, taken from the
  // routing frames it owns: 0.050 on the spools and 0.170 / 0.200 / 0.300
  // on the pulleys, measured, where the document's spoolRadius of 0.030
  // matches nothing in the file.
  const reelAxes = {};
  for (const part of model.parts) {
    if (part.kind !== "reel" || !part.axis) continue;
    reelAxes[part.index] = part.axis;
    // The writer's own measurement first (windingRadius, per reel, from
    // 2026-09-09), then the studio's identical measurement, then the
    // body's bounding box. The document's old global spoolRadius of 0.030
    // matched nothing in the file, which is why it is not in this chain.
    part.contactRadius = part.windingRadius
      || reelContactRadius(model.wires, part.index, part.axis)
      || measureSpoolRadius(part);
  }
  const shifts = motorShifts(model);

  let lowest = Infinity, lowestKind = null;
  const note = (kind, z) => { if (z < lowest) { lowest = z; lowestKind = kind; } };

  // One group per instance under `temporary`, so the strike can drive
  // each side backwards along its OWN direction. A single translation of
  // `temporary` could only ever move both rows the same way, which is
  // why the old strike dropped the lot through the floor instead.
  const sides = instances.map(() => new THREE.Group());
  for (const side of sides) temporary.add(side);


  for (const part of model.parts) {
    // His cable mesh wears the wires' own material, so it is stamped
    // below, once that material exists.
    if (part.kind === "cable") continue;
    const geometry = geometryFromPart(part);
    // The permanent works are authored ONCE, at row scale, in the body's
    // own frame: on the real file the tie is 17.5 m long and centred on
    // x 0, y 0, spanning between the two rows of machines. Stamped per
    // instance it appeared three times a side, overlapping; stamped from
    // the middle machine it sat 1.05 m off the row's centre. So it is
    // stamped once, untransformed (Param: "The anchor should only appear
    // once").
    if (part.permanent) {
      // The anchor is stamped at every frame the document gives -- one per
      // machine, on his ruling -- now that the writer sends the body once
      // and the placements separately. Everything else permanent, and an
      // anchor on a document with no stamps, is drawn ONCE untransformed,
      // which is how the anchor travelled while it was still fused into
      // the tension tie.
      const stamps = part.kind === "anchor" && model.anchors.length
        ? model.anchors : [null];
      for (const stamp of stamps) {
        const mesh = machineMesh(geometry, part);
        if (stamp) {
          mesh.matrixAutoUpdate = false;
          mesh.matrix.fromArray(stamp.matrix);
          if (stamp.mirrored) mesh.material.side = THREE.DoubleSide;
        }
        permanent.add(mesh);
        note(part.kind, lowestZ(geometry, stamp ? mesh.matrix : null));
      }
      continue;
    }
    const placements = part.kind === "motor" ? shifts : [[0, 0, 0]];
    for (const instance of instances) {
      for (const shift of placements) {
        const mesh = machineMesh(geometry, part);
        mesh.matrixAutoUpdate = false;
        if (instance.matrix) mesh.matrix.fromArray(instance.matrix);
        if (shift[0] || shift[1] || shift[2]) {
          mesh.matrix.multiply(machineShift.makeTranslation(shift[0], shift[1], shift[2]));
        }
        // A mirrored instance has its winding reversed by the transform,
        // so its faces light from the inside unless the material knows.
        if (instance.mirrored) mesh.material.side = THREE.DoubleSide;
        sides[instances.indexOf(instance)].add(mesh);
        note(part.kind, lowestZ(geometry, mesh.matrix));
        if (part.spins) spinners.push({ mesh, part, instance, turns: 0 });
      }
    }
  }

  // The wires, IDENTICAL to the net's cables (Param: "the wires are the
  // same as the cables so please make that happen"): the same steel the
  // net clones, transparent from birth so the strike can fade it, and
  // never vertexColors -- a plain Mesh with no colour attribute would
  // multiply by nothing and go black. The routed portion is lofted once
  // per wire from the corrected centreline and stamped with its instance;
  // the free span from the net vertex to the first frame is redrawn every
  // frame.
  // "the cables should be black to match the cables used on formwork."
  // The formwork's cables read black because the principal lines wear the
  // library's polished dark steel, so the machine's wires are given THE
  // SAME KEY rather than a colour chosen to imitate it -- match by
  // sharing, so a re-skin of one is a re-skin of both.
  //
  // One material for every wire, not one per mesh: applyMachineAct fades
  // the whole net out on the strike through this single opacity, and a
  // per-mesh re-skin would break that. So the library's maps are copied
  // ONTO it when they land instead of replacing it.
  const wireMaterial = materials.steel.clone();
  wireMaterial.color.set(CABLE_BLACK);
  wireMaterial.transparent = true;
  libraryPins.add(PRINCIPAL_SKIN);
  ensureLibraryMaterial(PRINCIPAL_SKIN).then((set) => {
    if (!set || mine !== machineBuild) return;
    wireMaterial.map = set.material.map;
    wireMaterial.normalMap = set.material.normalMap;
    wireMaterial.roughnessMap = set.material.roughnessMap;
    wireMaterial.roughness = set.material.roughness;
    wireMaterial.metalness = set.material.metalness;
    wireMaterial.needsUpdate = true;
    renderView();
  });
  // "yes i offset and you use it as centerline": he offsets the routing
  // planes himself, so nothing is added here. The other two readings stay
  // reachable because the document declares which it means, and his
  // exporter now carries that as an authored input rather than a constant
  // -- so a change of mind is one word on his canvas, not a build on each
  // side. Either offset is measured with the radius actually DRAWN, since
  // what has to meet the plane is the tube on screen.
  const routingOffset = model.routingFrameMeaning === "centreline" ? 0
    : model.routingFrameMeaning === "contact" ? state.wireRadius
    : -state.wireRadius;
  // HIS CABLES, AS HE MODELLED THEM (Param, 2026-09-15: "the recreation
  // in the app is really bad ... bring my cable mesh into the vaulted
  // app"). One mesh, authored on the mechanism he built, stamped on every
  // instance the way Frame 1 is, in the wires' black steel. The route
  // frames still turn the reels and hold the free span to the net; only
  // the tube lofted from them gives way.
  const cableParts = model.parts.filter((part) => part.kind === "cable");
  if (cableParts.length && instances.some((instance) => instance.mirrored)) {
    wireMaterial.side = THREE.DoubleSide;
  }
  for (const part of cableParts) {
    const geometry = geometryFromPart(part);
    for (const instance of instances) {
      const mesh = new THREE.Mesh(geometry, wireMaterial);
      mesh.castShadow = mesh.receiveShadow = true;
      mesh.matrixAutoUpdate = false;
      if (instance.matrix) mesh.matrix.fromArray(instance.matrix);
      sides[instances.indexOf(instance)].add(mesh);
    }
  }
  const wires = [];
  for (const wire of model.wires) {
    // The instance NAMES the wires it carries; the path is the fallback
    // for a document that does not.
    const step = wire.path && wire.path.length ? wire.path[0] : null;
    const instance = instances.find((candidate) =>
      candidate.wireIds && candidate.wireIds.includes(wire.id))
      || instances.find((candidate) => step
        && candidate.side === step.side && candidate.mechanism === step.mechanism)
      || instances[0];
    // The wire travels with the machine that pulls it, so it retreats
    // with that side rather than being left stretched across the site.
    const side = sides[instances.indexOf(instance)] || temporary;
    const routed = cableParts.length ? null : loftWire(
      wireCentreline(wire.route, reelAxes, routingOffset), state.wireRadius);
    let mesh = null;
    if (routed) {
      mesh = new THREE.Mesh(routed, wireMaterial);
      if (instance.matrix) {
        mesh.matrixAutoUpdate = false;
        mesh.matrix.fromArray(instance.matrix);
      }
      side.add(mesh);
    }
    const free = new THREE.Mesh(
      new THREE.CylinderGeometry(state.wireRadius, state.wireRadius, 1, WIRE_SIDES, 1, true),
      wireMaterial);
    free.visible = false;
    side.add(free);
    wires.push({ wire, instance, side, mesh, free, rib: null, ribAtFrame0: null });
  }

  // The floor (Param: "I must have the bottom of the machine and anchor to
  // the floor too"). The whole machine is lifted so its lowest point sits
  // on the studio's floor. In the authored file that point is the tie's
  // feet at z -0.117 while the drums bottom at -0.034 and the frame plates
  // at +0.100; z = 0 is the wire plane. So one lift puts the tie on the
  // floor and leaves the drums 83 mm and the plates 217 mm above it, which
  // is how they are authored -- the log says so, so the gap reads as his
  // model's rather than the studio's.
  const floor = groundLevel();
  const lift = Number.isFinite(lowest) ? floor - lowest : 0;
  group.position.z = lift;

  if (mine !== machineBuild) return;      // a newer build owns the scene
  scene.add(group);
  // WHERE EACH MACHINE ACTUALLY STANDS, measured off its own parts once
  // they are placed. The instance matrix cannot say: on his export both
  // rows carry the SAME translation, (0, 0), (0, 1.05) and (0, 2.1), and
  // the far row is a reflection of a body authored off to one side. Read
  // from those origins the three machines of a row sat on one spot, so
  // the outward direction ran along the row and the plant left sideways
  // (Param: "you can see in the animation the machine is moving
  // sideways"). A bounding box over the side's own meshes is where it
  // stands however the document places it.
  // Measured off each mesh's OWN matrix rather than through Box3, whose
  // world matrices are not composed until the first render: asked at
  // build time it handed back the body's authored box for every side, so
  // all six machines came out standing on one spot. A side's parts are
  // its direct children and the side itself sits at the origin until the
  // strike moves it, so the local matrix IS the world placement here.
  const standing = new THREE.Box3();
  const places = sides.map((side, index) => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const mesh of side.children) {
      if (!mesh.isMesh || !mesh.geometry) continue;
      if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
      standing.copy(mesh.geometry.boundingBox).applyMatrix4(mesh.matrix);
      minX = Math.min(minX, standing.min.x);
      maxX = Math.max(maxX, standing.max.x);
      minY = Math.min(minY, standing.min.y);
      maxY = Math.max(maxY, standing.max.y);
    }
    return Number.isFinite(minX)
      ? { side: instances[index].side, x: (minX + maxX) / 2, y: (minY + maxY) / 2 }
      : { side: instances[index].side, x: 0, y: 0 };
  });
  // Backwards is taken per SIDE, not per machine: machineRetreats
  // (fields.js) gives a row one direction, so a row reverses out together
  // and the two rows mirror each other. The vault's own centre is the
  // fallback for a document that carries a single row.
  const works = state.centre && Number.isFinite(state.centre.x)
    ? [state.centre.x, state.centre.y] : null;
  const retreats = machineRetreats(places, works);

  // Every skin the temporary plant wears, transparent from birth as the
  // wires are, so the strike can fade the machine out while it reverses
  // (Param: "move backwards on both sides and fade away"). The permanent
  // works keep their own skins and stay at full strength.
  const machineSkins = () => {
    const skins = new Set();
    temporary.traverse((object) => {
      if (!object.isMesh || !object.material) return;
      object.material.transparent = true;
      skins.add(object.material);
    });
    return [...skins];
  };
  machineObjects = { group, permanent, temporary, sides, retreats, places, spinners,
    wires, model, wireMaterial, lift,
    skins: machineSkins(), machineSkins };
  skinMachine(group, mine);
  const row = document.getElementById("machine-row");
  if (row) row.classList.remove("hidden");
  logStudio("machine: " + model.parts.length + " parts, "
    + instances.length + " instances, " + model.wires.length + " wires, "
    + model.anchors.length + " anchors");
  // A document can carry anchor FRAMES with no body to stamp on them --
  // the writer emits them whenever a result is wired, authored body or
  // not -- and that is a gap worth naming rather than a silent absence.
  if (model.anchors.length && !model.parts.some((part) => part.kind === "anchor")) {
    logStudio("machine: " + model.anchors.length + " anchor frames arrived "
      + "with no anchor body to stand on them; author one under "
      + "mechanism.anchor and they will be drawn");
  }
  if (shifts.length > 1) {
    logStudio("machine: the document carries ONE motor body, and it is "
      + "narrower than the spool bank, so it is stamped at "
      + shifts.length + " spools until the exporter authors them");
  } else {
    logStudio("machine: the motor body already reaches across the spool "
      + "bank, so it is the whole bank and is drawn once per machine");
  }
  if (Number.isFinite(lowest)) {
    logStudio("machine: lifted " + Math.round(lift * 1000) + " mm so its lowest "
      + "point (the " + lowestKind + ", authored at z "
      + Math.round(lowest * 1000) + " mm) sits on the floor");
  }
  // Said once, plainly, because it is the one number in the machine the
  // studio knows to be unverified: the writer fixes reeveFactor at 1.0
  // while Param's unit has four wheels, so the reels turn at the right
  // TIMES and probably the wrong RATE.
  if (model.wires.some((wire) => wire.reeveFactor === 1)) {
    logStudio("machine: the reels turn from a reeve factor of 1.0, which "
      + "the exporter has not authored yet, so their rate is unverified; "
      + "each reel's radius is read from the wire frames it carries");
  }
  logStudio("machine: take-up is measured along each wire's rib through the "
    + "net, halved between the two machines that pull it -- the route meets "
    + "the net at its anchor, so the contract's free span is zero here");
  reportMachineChecks(model);
  // Born into the state the clock dictates. buildMachine is async, so it
  // lands AFTER the load's own applySceneAtTime has run; without this the
  // new machine stood in its default pose until the next control was
  // touched, and then vanished -- the other half of "it did it once".
  if (state.timeline && state.objects.shell && state.objects.falsework) {
    applySceneAtTime(state.timeline.t);
  } else {
    applyMachineAct(0, 0);
  }
}

// Where a wire first meets the machine, in world coordinates: its first
// routing plane, carried through its instance's placement.
const machineHead = new THREE.Vector3();
const machineTail = new THREE.Vector3();
const machineMatrix = new THREE.Matrix4();

function wireHead(entry, into) {
  const first = entry.wire.route[0];
  if (!first) return null;
  into.set(first.matrix[12], first.matrix[13], first.matrix[14]);
  if (entry.instance && entry.instance.matrix) {
    into.applyMatrix4(machineMatrix.fromArray(entry.instance.matrix));
  }
  // The machine stands lifted to the floor and reverses out on the
  // strike; the head has to be where the machine actually is.
  if (entry.side) into.add(entry.side.position);
  into.z += machineObjects.group.position.z + machineObjects.temporary.position.z;
  return into;
}

// Param, on what the machine does while the pieces land: "the reel
// actually still happens slightly as the pieces drop adding prestress to
// cope with the added load, becoming an inverse kinematics engine."
//
// The FRAMES carry no such motion -- they stop at time 90 and hold --
// so this is a studio-side model rather than something read, and it is
// named as one. It is driven by how much load has arrived, which is the
// fraction of castings already placed, and it is deliberately small: a
// few per cent of the take-up already done, not a second act.
const PRESTRESS_TAKE_UP = 0.04;

function prestressFraction(t) {
  const total = placementCount();
  if (!total) return 0;
  const build = Math.max(0, t - openingSeconds() - formworkSeconds());
  const step = placementStep();
  if (!(step > 0)) return 0;
  return Math.min(1, build / (step * total));
}

// The rest modes show the FINISHED net whatever the clock says; only the
// timeline shows the machine building it. The machine follows the same
// rule, because it rides with the formwork (Param: "should always be
// there with formwork"). What went wrong before: this gate showed the
// machine only in the rest modes while formworkVisibility showed the
// formwork only in the timeline, so the two were never on screen
// together -- and in the rest modes the machine honoured the strike while
// the finished net did not, so once the clock had been played or scrubbed
// to the end (and it sticks there across re-cuts, re-selects and every
// control) the machine was struck for the rest of the session. Measured:
// the machine group never left the scene; it was hidden.
const pivotTo = new THREE.Matrix4();
const pivotBack = new THREE.Matrix4();
const spinAxis = new THREE.Vector3();

function applyMachineAct(t, strikeU) {
  if (!machineObjects) return;
  const { group, permanent, temporary, wireMaterial } = machineObjects;
  // Param, 2026-09-09: "when i show shell i expect to see the anchors
  // too". The anchor and the tension tie are the PERMANENT works -- they
  // are cast into the finished building and do not leave with the plant
  // -- so shell shows them and hides only what is temporary. This is the
  // one place the machine parts company with formworkVisibility, which
  // has no permanent half to keep.
  const wanted = state.showMachine !== false;
  group.visible = wanted;
  if (!wanted) return;
  const seconds = formworkSeconds();
  let struck = 0;
  if (state.showMode === "shell") {
    temporary.visible = false;            // the plant has gone; its works stay
  } else if (state.showMode === "timeline") {
    const show = formworkVisibility({ t, seconds, strikeU,
      showMode: state.showMode, hasMembers: true, hasColumnMesh: false });
    temporary.visible = show.group;
    struck = strikeU;
  } else {
    temporary.visible = true;             // standing, as the finished net is
  }
  permanent.visible = true;               // the permanent works remain
  // The machine leaves with the columns and the net, on the same fade,
  // because it is one machine leaving. It REVERSES OUT rather than
  // dropping: "have the mechanism go backwards from its position on each
  // side (backwards mirrored) ... instead of having it fall under the
  // ground." Each row goes back along ITS OWN direction, because taken
  // per machine the ends of a row went sideways instead: "i would prefer
  // that the machines all move backwards on both sides and fade away."
  // The permanent works do not move -- they are cast in.
  for (let i = 0; i < machineObjects.sides.length; i++) {
    const away = machineObjects.retreats[i];
    machineObjects.sides[i].position.set(
      away[0] * MACHINE_RETREAT * struck, away[1] * MACHINE_RETREAT * struck, 0);
  }
  // "and fade away": the plant thins as it reverses, so the strike ends
  // on the vault standing alone rather than on a machine sliding off the
  // edge of the plate.
  for (const skin of machineObjects.skins) skin.opacity = 1 - struck;
  wireMaterial.opacity = 1 - struck;

  const doc = state.formwork;
  if (!doc || !temporary.visible) return;
  const frame = interpolateFormworkFrame(doc.frames, machineTime(t, seconds));
  const vertices = frame && frame.vertices;
  if (!vertices) return;
  const lift = netClearance();
  const prestress = PRESTRESS_TAKE_UP * prestressFraction(t);
  // The free spans are children of `temporary`, so their positions are
  // written in ITS space: the world midpoint less the group's lift and the
  // strike's drop.
  const parentZ = group.position.z + temporary.position.z;
  // The rib each wire pulls, chosen once on the final pose, and its
  // length at frame 0, the reference the spin is measured from.
  const finalPose = doc.frames[doc.frames.length - 1].vertices;
  const firstPose = doc.frames[0].vertices;
  const edges = Array.isArray(doc.edges) ? doc.edges : [];

  for (const entry of machineObjects.wires) {
    const wire = entry.wire;
    if (wire.netVertex === null) continue;
    // The frames carry vertices as TRIPLES, the convention every other
    // reader here uses (writeInstancedPoints reads points[i][0]).
    const point = vertices[wire.netVertex];
    if (!point) continue;
    machineTail.set(point[0], point[1], point[2] + lift.wires);
    const head = wireHead(entry, machineHead);
    if (!head) continue;
    const span = machineTail.distanceTo(head);
    if (!entry.rib) {
      entry.rib = ribChain(edges, finalPose, wire.netVertex);
      // Frame 0 is the reference, so the spin is a pure function of t and
      // cannot drift on a scrub or on a recorded frame played out of order.
      entry.ribAtFrame0 = chainLength(firstPose, entry.rib) / 2;
    }
    entry.ribNow = chainLength(vertices, entry.rib) / 2;
    entry.free.visible = span > 1e-4;
    if (entry.free.visible) {
      // A unit cylinder stood along its own Y, aimed and stretched: one
      // geometry for every span at every frame.
      entry.free.position.copy(machineTail).lerp(head, 0.5);
      entry.free.position.z -= parentZ;
      // Written in the SIDE's space now, not the group's, since the span
      // hangs off a group that walks away during the strike.
      if (entry.side) entry.free.position.sub(entry.side.position);
      entry.free.scale.set(1, span, 1);
      entry.free.quaternion.setFromUnitVectors(
        SEGMENT_UP, machineHead.clone().sub(machineTail).normalize());
    }
  }

  // The spin. Each reel turns by the take-up of a wire it carries, ABOUT
  // ITS OWN AXIS THROUGH ITS OWN ORIGIN -- a rotation about the body's
  // origin instead would swing the drum round the machine -- plus the
  // small prestress the arriving load brings.
  for (const spinner of machineObjects.spinners) {
    const served = machineObjects.wires.find((entry) =>
      entry.instance === spinner.instance
      && entry.wire.route.some((plane) => plane.ownerReel === spinner.part.index));
    if (!served || served.ribAtFrame0 === null) continue;
    const radius = spinner.part.contactRadius || served.wire.spoolRadius || 0.03;
    const turns = turnsFor(served.ribAtFrame0,
      served.ribNow * (1 - prestress), served.wire.reeveFactor, radius);
    spinner.turns = turns;
    const axis = spinner.part.axis;
    if (!axis) continue;
    spinAxis.set(axis.direction[0], axis.direction[1], axis.direction[2]);
    machineMatrix.makeRotationAxis(spinAxis, turns * Math.PI * 2);
    pivotTo.makeTranslation(axis.origin[0], axis.origin[1], axis.origin[2]);
    pivotBack.makeTranslation(-axis.origin[0], -axis.origin[1], -axis.origin[2]);
    spinner.mesh.matrix.identity();
    if (spinner.instance && spinner.instance.matrix) {
      spinner.mesh.matrix.fromArray(spinner.instance.matrix);
    }
    spinner.mesh.matrix.multiply(pivotTo).multiply(machineMatrix).multiply(pivotBack);
  }
}

function reportMachineChecks(model) {
  const doc = state.formwork;
  if (!doc || !doc.frames || !doc.frames.length) return;
  const triples = doc.frames[doc.frames.length - 1].vertices;
  if (!triples || !triples.length) return;
  // mechanism.js's checks take a FLAT array, because they are pure and
  // node-tested; the frames carry triples. Flattened here, at the one
  // boundary between the two, rather than teaching either side about
  // the other's shape.
  const vertices = new Array(triples.length * 3);
  for (let i = 0; i < triples.length; i++) {
    vertices[i * 3] = triples[i][0];
    vertices[i * 3 + 1] = triples[i][1];
    vertices[i * 3 + 2] = triples[i][2];
  }
  // IN WORLD SPACE. The route frames are in the authored body's LOCAL
  // space, so comparing them with the net directly is comparing across a
  // placement -- 16.1 m of it on this study. Run that way the check
  // accused 35 of 42 wires of naming the wrong net vertex; with the
  // instance frame applied the gap is 0.0000 m on all 42 and every
  // declared vertex IS the nearest. A check that cries wolf is worse
  // than no check, because the one time it is right nobody looks.
  const placedHead = (wire) => {
    const first = wire.route[0];
    if (!first) return null;
    const instance = model.instances.find((candidate) =>
      candidate.wireIds && candidate.wireIds.includes(wire.id));
    machineHead.set(first.matrix[12], first.matrix[13], first.matrix[14]);
    if (instance) machineHead.applyMatrix4(machineMatrix.fromArray(instance.matrix));
    return [machineHead.x, machineHead.y, machineHead.z];
  };
  const reversed = checkRouteDirection(model.wires, vertices);
  if (reversed.length) {
    logStudio("machine: " + reversed.length + " wire route(s) read from the "
      + "machine end rather than the net end: " + reversed.slice(0, 4).join(", "));
  }
  const complaints = checkNetVertices(model.wires, vertices, placedHead);
  for (const complaint of complaints.slice(0, 4)) {
    logStudio("machine: " + complaint.reason);
  }
  if (complaints.length > 4) {
    logStudio("machine: and " + (complaints.length - 4) + " more wires whose "
      + "declared net vertex is not the nearest one");
  }
}

// Everything that depends on the build/strike clock but not on the camera:
// inflation, segment drop/visibility, falsework, and the wires/nodes
// strike state. setLayer's wires/falsework toggle and
// rebuildWiresAndNodes both need to recompute this scene state after the
// objects they touch change, but neither one should be allowed to move the
// camera -- only applyTimeline's own scrubber/play/record callers get to
// do that. Kept pure in t, same as applyTimeline: no clock reads here
// either.
function applySceneAtTime(t) {
  state.timeline.t = t;
  // Guarded like every sibling that touches these two (recolourSegments,
  // setLayer). disposeShell sets state.objects.shell to null,
  // and this function is reachable from setLayer and rebuildWiresAndNodes,
  // neither of which is ordered after a rebuild; the falsework is built in
  // the same pass. An unguarded read throws out of frame() before the
  // frame is rescheduled, which kills the render loop until the page is
  // reloaded, and that is a heavy price for a null check.
  if (!state.objects.shell || !state.objects.falsework) return;
  const inflate = inflationFactor(t);
  applyInflation(inflate);
  // The timeline opens with the net inflating into form; everything after
  // it (drop, strike) runs on build time, which only starts once
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
  for (const [key, clear] of [["wires", clearance.wires],
                              ["nodes", clearance.nodes],
                              // The principal bars ride the wires' own
                              // clearance: they dress the same segments.
                              ["principal", clearance.wires]]) {
    const object = state.objects[key];
    if (!object) continue;
    // Hidden for the whole formwork act: the act's own net IS the net,
    // moving; the instanced wires would draw it a second time, flat on
    // the ground at the solved plan, which is two nets and both wrong.
    object.visible = strikeU < 1 && !duringFormworkAct(t);
    object.material.opacity = 1 - strikeU;
    object.position.z = clear - 1.5 * strikeU;
    syncNetShadow(object);
  }
  applyFormworkAct(t, strikeU);
  // Its own call rather than a tail inside the formwork act, which
  // returns early on three separate conditions -- a study with no column
  // members would have had a machine that never moved.
  applyMachineAct(t, strikeU);
  applyShowMode();
}

// R4: the Show select is a lens over the same scene function. Timeline
// shows whatever t says; the other three are the rest state with a fixed
// choice of net and shell. Falsework stays with its own select, except
// framework mode, which is the bare net by definition.
function applyShowMode() {
  shaftsRevision += 1;
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
  syncNetShadow(state.objects.wires);
  syncNetShadow(state.objects.nodes);
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
  const principal = state.objects.principal;
  if (principal) {
    // Net dressing: the bars follow the net, and they step aside while
    // the forces lens is painting data on those same segments.
    principal.visible = netOn && !state.layers.forces;
    principal.material.opacity = 1;
    principal.position.z = state.showMode === "both" ? clearance.wires : 0;
    syncNetShadow(principal);
  }
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
    azimuth: Math.atan2(offset.y, offset.x) - orbitTurned(reference),
  };
}

function applyTimeline(t) {
  // The net, the machine and the pieces move with the clock.
  shaftsRevision += 1;
  applySceneAtTime(t);
  const base = state.timeline.orbitBase;
  if (base && state.timeline.autoSpin && !state.userDragging) {
    const centre = base.centre || state.centre;
    // The camera holds its framing through the whole opening act -- the
    // formwork growing into its final form deserves a still witness, Param
    // ruled -- and starts its turn the instant build time begins.
    const angle = base.azimuth + orbitTurned(t);
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
// Param, on a take running at over ten seconds a frame: "i want high
// quality but its taking 10seconds plus a frame which is too long."
//
// The frames are JPEG at 0.95, his ruling. PNG is lossless deflate, and
// his ground is fine gravel: high-frequency noise is the WORST case for
// it, because it barely compresses, so the encoder does maximum work for
// a maximum-size file. That is also why it grew worse towards the end --
// the opening frames are smooth sky and compress in an instant. Nothing
// is lost that survives the stitch: ffmpeg re-encodes every take to
// H.264 4:2:0, which throws away far more than 0.95 does.
const RECORD_MIME = "image/jpeg";
const RECORD_QUALITY = 0.95;

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
    + recordingFrame().height;
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
  // A RECORDING IS MEASURED IN OUTPUT PIXELS. The viewport renders at the
  // display's own device pixel ratio, and setSize multiplies by it, so on
  // a 2x screen "1080p" was really a 3840x2160 buffer: four times the
  // shading, four times the readback and four times the encode, for a
  // video the button calls 1080p and ffmpeg then wrote at 4K. Pinned to 1
  // for the take and put back afterwards. Edge quality is unaffected --
  // it comes from the composer target's 4x MSAA, which is untouched.
  //
  // The composer keeps its OWN copy of the ratio, taken when it was
  // built, so setting it on the renderer alone would leave every pass
  // still running at the old size.
  const wasPixelRatio = renderer.getPixelRatio();
  renderer.setPixelRatio(1);
  composer.setPixelRatio(1);
  renderer.setSize(frame.width, frame.height, false);
  composer.setSize(frame.width, frame.height);
  setShaftResolution(true);
  applyCameraFrustum(frame.width / frame.height);
  // Measured, not guessed at: the next time a take is slow, the log says
  // which of the three is eating it rather than leaving us to reason.
  const spent = { render: 0, encode: 0, upload: 0 };
  const began = performance.now();
  closeFixturePanel();      // an overlay is not part of the take
  state.recording = true;   // resize() must skip while this is set
  const restoreHelpers = hideHelpersForPicture();
  const windWas = windAir.windTime.value;
  // One capture for the take, as it begins; none while it runs.
  captureReflections();
  state.recordStop = false;
  paintRecordButton();
  let stopped = -1;
  // The previous frame's upload, still in flight. Awaiting it AFTER the
  // next frame has rendered and encoded is what lets the network overlap
  // the GPU instead of taking its turn after it.
  let inFlight = null;
  const settle = async () => {
    if (!inFlight) return;
    const pending = inFlight;
    inFlight = null;
    const at = performance.now();
    const response = await pending;
    spent.upload += performance.now() - at;
    if (!response.ok) throw new Error("frame upload failed: " + response.status);
  };
  try {
    for (let frameIndex = 0; frameIndex < total; frameIndex++) {
      // Param: "if recording and i want to stop theres no way out". Read
      // at the TOP of the frame, before the render and the upload, so a
      // press lands within one frame rather than after another second of
      // work. A take of 900 frames could otherwise only be escaped by
      // closing the tab.
      if (state.recordStop) { stopped = frameIndex; break; }
      if (state.dayCycle.record) {
        // Deterministic: frameIndex alone drives u, so a recording is
        // reproducible frame for frame like applyTimeline already is. The
        // day maps over the whole recording, so layering it with the build
        // timeline is a deliberate choice a user who checks the box makes.
        applyDayCycle(frameIndex / Math.max(1, total - 1));
        if (state.environmentMode === "sky" && frameIndex % 30 === 0) regenerateEnvironment();
      }
      let at = performance.now();
      // The take's own clock, so the same take blows the same way twice.
      windAir.windTime.value = frameIndex / fps;
      applyTimeline(frameIndex * speed / fps);
      renderView();
      spent.render += performance.now() - at;
      at = performance.now();
      const blob = await new Promise(
        (resolve) => canvas.toBlob(resolve, RECORD_MIME, RECORD_QUALITY));
      spent.encode += performance.now() - at;
      // Last frame's upload lands here, having run under this frame's
      // render and encode.
      await settle();
      inFlight = fetch(
        "/api/frames/" + target + "?frame=" + (frameIndex + 1),
        { method: "POST", body: blob });
      if (frameIndex % 30 === 0) {
        const each = (performance.now() - began) / 1000 / (frameIndex + 1);
        status.textContent = "frame " + frameIndex + " / " + total
          + " -- " + each.toFixed(2) + " s each, "
          + Math.round(each * (total - frameIndex) / 60) + " min left";
      }
    }
    if (state.dayCycle.record) {
      // F4: persist the recording's own final sun state, the same way
      // frame()'s live day cycle already does at the end of a play, so the
      // next redraw (a slider nudge, a mode change) does not silently
      // revert the sun mid-review.
      state.sunColourOverride = document.getElementById("sun-colour").value;
      state.sunIntensityOverride = lightBase.sun;
    }
    await settle();                      // the last frame is still in the air
    const each = (performance.now() - began) / 1000 / Math.max(1, total);
    logStudio("recording: " + total + " frames at " + frame.width + "x" + frame.height
      + ", " + each.toFixed(3) + " s each -- render "
      + Math.round(spent.render / 1000) + " s, encode "
      + Math.round(spent.encode / 1000) + " s, waiting on uploads "
      + Math.round(spent.upload / 1000) + " s");
    if (stopped >= 0) {
      // Nothing is stitched: he pressed stop because the take was wrong,
      // and handing him a video of it anyway would be a surprise. The
      // frames already uploaded stay where they are and the next take to
      // the same name writes over them.
      status.textContent = "stopped at frame " + stopped + " of " + total
        + "; nothing stitched";
      return;
    }
    status.textContent = "stitching...";
    const stitched = await fetch("/api/frames/" + target + "/stitch?fps=" + fps, { method: "POST" });
    const body = await stitched.json();
    status.textContent = stitched.ok
      ? "saved " + body.video
      : "stitch failed: " + (body.detail || stitched.status);
    // A stitch failure was shown ONLY here, in a status line that the
    // next click clears, so two eleven-minute takes failed on 2026-09-09
    // and the diagnostics log never heard about either. The frames are
    // still on disk after a failure, and the log now says so and where.
    if (!stitched.ok) {
      logStudio("recording: stitch failed after " + total + " frames: "
        + (body.detail || stitched.status)
        + " -- the frames are kept under the study folder in studio/frames");
    } else {
      logStudio("recording: saved " + body.video);
    }
  } catch (error) {
    status.textContent = "recording failed: " + error.message;
    logStudio("recording failed: " + error.message);
  } finally {
    // No explicit canvas-size restore here: this flag flip is what lets
    // resize() act again, and it picks the canvas back up to its CSS size
    // (including the composer, via the resize() edit above) on the very
    // next frame().
    state.recording = false;
    state.recordStop = false;
    paintRecordButton();
    restoreHelpers();
    windAir.windTime.value = windWas;
    renderer.setPixelRatio(wasPixelRatio);
    composer.setPixelRatio(wasPixelRatio);
    setShaftResolution(false);
    state.timeline.playing = wasPlaying;
    state.dayCycle.playing = wasDayCyclePlaying;
    state.showMode = wasShowMode;
    paintShowButtons();
    applyShowMode();
  }
}
// The one control is both: Record at rest, Stop while a take runs. A
// separate stop would be dead nine tenths of the time, and the press he
// reaches for when he wants out is the one he just pressed. Param: "the
// stop record needs to happen on the record tile too not just in the
// banner menu. show a stop icon when the recording is going." The tile is
// the only face since 2026-09-14, when the panel's Record 1080p went.
function paintRecordButton() {
  const tile = document.getElementById("shelf-record");
  if (tile) {
    tile.textContent = state.recording ? "\u25a0" : "\u25cf";
    tile.title = state.recording ? "Stop the recording" : "Record the animation at 1080p";
    tile.classList.toggle("recording", state.recording);
  }
}

function toggleRecording() {
  if (state.recording) {
    state.recordStop = true;
    document.getElementById("record-status").textContent = "stopping...";
    return;
  }
  recordAnimation();
}

// ---------- day cycle ----------
// S5: frame() is the only wall-clock advancer (see below); this button
// only arms/disarms state.dayCycle.playing and captures the elevation the
// arc peaks at, exactly as togglePlay arms state.timeline.playing.
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
    applyCameraFrustum(w / h);
    paintScaleBar();
    // Width follows the aspect; height does not.
    paintFrameWidth();
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

// The play control is the shelf's icon beside the drawer tabs (Param: "add
// a play button next to the scene tile"), and only that since 2026-09-14.
// Every paint of it comes through here.
function paintPlayButtons(text) {
  // An ICON tile: a triangle at rest, two bars while the take runs.
  const shelf = document.getElementById("shelf-play");
  if (shelf) {
    shelf.textContent = text === "Pause" ? "❚❚" : "▶";
    shelf.title = text === "Pause" ? "Pause the animation" : "Play the animation";
  }
}

// ---------- stopping the take ----------
// Param, 2026-09-12: "add in a stop button to the animation running
// too. which takes us back to the state right before the animation was
// run with the shell in the mode it was in."
//
// Pause holds the take where it is, which is a different thing: it
// leaves the scene mid-build, in timeline mode, with the camera part
// way round its turn. Stop undoes the whole excursion.
//
// TAKEN ON THE WAY IN, and only on the way in. Pressing Play again
// after a pause must not overwrite what this is holding, or Stop would
// put him back in the middle of the take he had just paused.
let beforeTheTake = null;

function paintStopButton() {
  const button = document.getElementById("shelf-stop");
  if (button) button.disabled = !beforeTheTake;
}

function stopTake() {
  if (!state.timeline || !beforeTheTake) return;
  const was = beforeTheTake;
  beforeTheTake = null;
  state.timeline.playing = false;
  paintPlayButtons("Play");
  paintStopButton();
  // The clock is set DIRECTLY rather than through applyTimeline, which
  // would drive the camera round the take's own orbit -- the very
  // thing being undone. setShowMode applies the scene at whatever the
  // clock now reads, which is where it stood before Play.
  state.timeline.t = was.t;
  setShowMode(was.showMode);
  camera.position.fromArray(was.camera);
  controls.target.fromArray(was.target);
  controls.update();
  // The scrubber reads the clock, and nothing else has told it.
  updateHud();
  logStudio("stopped: the scene is back as it stood before the take");
}

function startPlaying(fromTheTop) {
  // Playing IS the animation view: it switches to it rather than asking
  // which mode the scene should be in first, and it takes its framing from
  // wherever the camera is standing at that moment.
  //
  // What it is switching FROM is worth keeping, so Stop has somewhere
  // to go back to. Only on the way in: a resume after a pause is
  // already in timeline mode and must not overwrite it.
  if (state.showMode !== "timeline") {
    beforeTheTake = { showMode: state.showMode,
      t: state.timeline ? state.timeline.t : 0,
      camera: camera.position.toArray(),
      target: controls.target.toArray() };
    paintStopButton();
  }
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
  // "When i run the animation i would like to see 3 tiled graphs": play
  // brings them up, unless he has put them away.
  if (liveGraphs.wanted) showLiveGraphs(true);
}

function togglePlay() {
  if (!state.timeline) return;
  if (state.timeline.playing) {
    state.timeline.playing = false;
    paintPlayButtons("Play");
    return;
  }
  startPlaying(false);
}

function restartTake() {
  if (!state.timeline) return;
  startPlaying(true);
}
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
  if (button) {
    button.disabled = !undoHistory.length;
    button.title = undoHistory.length
      ? "Undo " + undoHistory[undoHistory.length - 1].label
      : "Nothing to undo yet";
  }
  const forward = document.getElementById("shelf-redo");
  if (forward) {
    forward.disabled = !redoHistory.length;
    forward.title = redoHistory.length
      ? "Redo " + redoHistory[redoHistory.length - 1].label
      : "Nothing to redo";
  }
}

// The third argument is how to DO the thing again. It is optional, and
// that is deliberate rather than lazy: most of these entries close over
// records that no longer exist once they are undone, and a redo that
// half worked would be worse than none. An entry without one ends the
// redo branch when it is undone, and the button says so.
const redoHistory = [];

function pushUndo(label, undo, redo) {
  // Replaying an undo runs the same handlers that record history; gating
  // here is what keeps undo from writing its own next entry.
  if (undoReplaying) return;
  undoHistory.push({ label, undo, redo });
  if (undoHistory.length > UNDO_CAP) undoHistory.shift();
  // A fresh action invalidates whatever was undone before it: the branch
  // it would have redone into no longer exists.
  redoHistory.length = 0;
  paintUndoButton();
}

function clearUndoHistory() {
  undoHistory.length = 0;
  paintUndoButton();
}

async function undoLast() {
  const entry = undoHistory.pop();
  if (!entry) { paintUndoButton(); return; }
  if (entry.redo) redoHistory.push(entry);
  else redoHistory.length = 0;   // nothing beyond here can be replayed
  paintUndoButton();
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
async function redoLast() {
  const entry = redoHistory.pop();
  paintUndoButton();
  if (!entry) return;
  // NOT gated by undoReplaying: doing the thing again should record a
  // fresh undo entry, exactly as doing it the first time did. What it
  // must not do is clear the redo branch it is walking, so the stack is
  // put back after the action has pushed its own entry.
  const branch = redoHistory.slice();
  try {
    await entry.redo();
    logStudio("redid " + entry.label);
  } catch (error) {
    logStudio("could not redo " + entry.label + ": " + error.message);
  }
  redoHistory.length = 0;
  for (const item of branch) redoHistory.push(item);
  paintUndoButton();
}

document.getElementById("shelf-undo").addEventListener("click", undoLast);
const redoTile = document.getElementById("shelf-redo");
if (redoTile) redoTile.addEventListener("click", redoLast);

// Full screen, because a presentation render wants the whole display and
// the panel and shelf are not part of the picture. The Escape that leaves
// it is the browser's own and needs nothing here.
const fullTile = document.getElementById("shelf-fullscreen");
if (fullTile) {
  fullTile.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (error) {
      logStudio("full screen was refused: " + error.message);
    }
  });
  document.addEventListener("fullscreenchange", () => {
    fullTile.classList.toggle("active", !!document.fullscreenElement);
    fullTile.title = document.fullscreenElement
      ? "Leave full screen" : "Fill the display with the view";
  });
}
// Ctrl+Z as well as the tile (his ask), because that is the gesture
// every other tool in his day answers to. Cmd+Z too, for the iPad's
// keyboard. Kept off text entry: while a slider reading or a rename
// prompt has focus, Ctrl+Z belongs to the text, not to the scene.
window.addEventListener("keydown", (event) => {
  if (event.key !== "z" && event.key !== "Z") return;
  if (!event.ctrlKey && !event.metaKey) return;
  if (event.shiftKey) {                    // Ctrl+Shift+Z is redo
    const focus = document.activeElement ? document.activeElement.tagName : "";
    if (focus === "INPUT" || focus === "TEXTAREA") return;
    event.preventDefault();
    redoLast();
    return;
  }
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  event.preventDefault();
  undoLast();
});

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
undoableSelect("atmosphere-preset", "the atmosphere change");

function removePropRecord(record) {
  removePropRecords([record]);
}

// Any number at once, in one pass. An undone stroke of 2,000 props was
// 2,000 calls of the one above, each filtering the whole list and writing
// the whole layout again: quadratic in the field, and 2,000 writes of it.
function removePropRecords(records) {
  const gone = new Set(records);
  if (!gone.size) return;
  // A loose gumball on a prop that is leaving goes with it, or the
  // handles hang in the air over nothing.
  if (gone.has(gumballLoose)) gumballLoose = null;
  if (state.carrying && gone.has(state.carrying.record)) {
    state.carrying = null;
    state.propDrag = false;
    controls.enabled = true;
  }
  let lamps = false;
  for (const record of gone) {
    disposeProp(record.object);
    propsGroup.remove(record.object);
    if (isLamp(record)) lamps = true;
  }
  // A caster leaving matters as much as one arriving: clearing a
  // scattered field would otherwise leave the shadow map sized for the
  // props that are gone.
  noteCastersChanged();
  // And a spot leaving hands its shadow slot to the next one waiting.
  noteSpotShadowsChanged();
  state.props = state.props.filter((p) => !gone.has(p));
  notePropsMoved();
  if (gone.has(state.selectedProp)) selectProp(null);
  // And a badge naming a prop that no longer exists is worse than none.
  if (gone.has(hoveredProp)) setHoveredProp(null);
  for (const record of gone) gatheredProps.delete(record);
  // What is on a layer has changed, so what counts as a planting there
  // and how big it is have both to be worked out again.
  clearPlantings();
  refreshGroupOutlines();
  // A lamp leaving changes what the Lights row is talking about, and it
  // may not have been the selected one (which would have said so above).
  if (lamps) syncLightControls();
  // And it takes its own card with it rather than leaving one hanging
  // over the space where it stood.
  if (gone.has(fixturePanelFor)) closeFixturePanel();
  saveProps();
  // The drawer is a picture of state.props, so a prop leaving has to
  // reach it: deleting one in the viewport used to leave its tile behind
  // (Param: "when i deleted a prop via edit, it didnt remove that prop
  // from the layers tile"), and the orphan tile then pointed at a record
  // nothing else in the scene still held.
  refreshLayersShelf();
}

// Re-render the layers drawer, but only when it is the thing on screen.
// Called by every writer of state.props, since the drawer draws that
// list and cannot know on its own when it has gone stale.
function refreshLayersShelf() {
  if (shelfKind === "layers") renderShelf();
}

// The take's four icons call its functions directly. They used to click
// the panel's own Play, Restart, Stop and Record, which were copies of
// them and went on 2026-09-14.
document.getElementById("shelf-play").addEventListener("click", togglePlay);
document.getElementById("shelf-restart").addEventListener("click", restartTake);
document.getElementById("shelf-stop").addEventListener("click", stopTake);
document.getElementById("shelf-record").addEventListener("click", toggleRecording);

scrubber.addEventListener("input", () => {
  if (!state.timeline) return;
  state.timeline.playing = false;
  paintPlayButtons("Play");
  applyTimeline((+scrubber.value / 1000) * timelineDuration());
  updateHud();
});
for (const [id, prop] of [["orbit-speed", "orbitSpeed"]]) {
  document.getElementById(id).addEventListener("input", (e) => {
    if (state.timeline) {
      state.timeline[prop] = +e.target.value;
      applyTimeline(state.timeline.t);
      // The spin rate sets the last act's length, so the take's duration
      // and the graphs' x axis move with it, once the hand stops.
      invalidateLiveGraphsSoon();
    }
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

// ---------- flying with the keys ----------
// W A S D move the camera and the point it orbits together, so letting go
// leaves the orbit where the eye now is; 1 to 4 choose the speed (flyStep,
// fields.js). Not while a take or a plate is being made, which own the
// camera, and not while anything with a caret has the keys.
const flyHeld = new Set();
let flySpeed = FLY_SPEEDS[2];
const flyForward = new THREE.Vector3();
const flyRight = new THREE.Vector3();

function typingHasTheKeys() {
  const tag = document.activeElement ? document.activeElement.tagName : "";
  return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
}

window.addEventListener("keydown", (event) => {
  // Ctrl+S, Ctrl+D and Ctrl+Z belong to the browser and the undo.
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (typingHasTheKeys()) return;
  const key = event.key.toLowerCase();
  if (FLY_SPEEDS[key]) {
    flySpeed = FLY_SPEEDS[key];
    logStudio("moving at " + flySpeed + " m/s (" + key + " of 4)");
    return;
  }
  if (FLY_KEYS.includes(key)) {
    flyHeld.add(key);
    event.preventDefault();
  }
});
window.addEventListener("keyup", (event) => { flyHeld.delete(event.key.toLowerCase()); });
// A key let go while the window was away never sends its keyup, and the
// camera would drive on for ever.
window.addEventListener("blur", () => flyHeld.clear());

function flyCamera(seconds) {
  if (!flyHeld.size || state.recording || state.stillRendering) return;
  if (typingHasTheKeys()) { flyHeld.clear(); return; }
  camera.updateMatrixWorld();
  camera.getWorldDirection(flyForward);
  flyRight.setFromMatrixColumn(camera.matrixWorld, 0);
  const step = flyStep(flyHeld, flyForward.toArray(), flyRight.toArray(), flySpeed, seconds);
  if (!step) return;
  camera.position.x += step[0];
  camera.position.y += step[1];
  camera.position.z += step[2];
  controls.target.x += step[0];
  controls.target.y += step[1];
  controls.target.z += step[2];
}
// How often the sliders' fills are settled. Six times a second is below
// what the eye reads as lag on a dial nobody is dragging, and a drag
// repaints on its own input event long before this comes round.
const RANGE_FILL_MS = 160;
let lastRangeFill = 0;
let playingFrameCount = 0;
let dayCycleFrames = 0;
function frame(now) {
  const delta = Math.min(0.1, (now - lastTime) / 1000);
  lastTime = now;
  resize();
  // Every slider's node and travelled track, six times a second. Here
  // rather than at each of the dozen handlers that write a value
  // without dispatching an event -- a restore, a preset, a scene, a
  // change of selection -- and free when nothing moved, because
  // settleRangeFills writes only what changed.
  if (now - lastRangeFill > RANGE_FILL_MS) {
    lastRangeFill = now;
    settleRangeFills();
  }
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
  // The fixture's own card rides its fixture across the screen, and
  // closes itself if the fixture has gone (a delete, a scene, a
  // reload). One projection a frame, and only while it is open.
  if (fixturePanelFor) placeFixturePanel();
  // Playing or scrubbed, the graphs follow the clock from here, never
  // from applyTimeline, which stays pure in t.
  tickLiveGraphs(false);
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
      state.sunIntensityOverride = lightBase.sun;
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
  // THE RECORDER OWNS THE CAMERA AND THE CANVAS while a take runs, and
  // this is why a recording did not match what he saw on Play.
  //
  // Ownership was gated on state.timeline.playing, which recordAnimation
  // deliberately sets FALSE -- two clocks racing the same state is worse.
  // So during every take this read false, controls.update() ran on each
  // animation frame, and its leftover damping dragged the camera off the
  // bearing applyTimeline had just pinned it to. Live, with playing true,
  // the turntable holds it. Same function, same t, different camera.
  //
  // And renderView() then drew that camera over the frame the recorder
  // had just composed, in the window between its render and its pixel
  // read -- so the file could receive a picture nobody asked for. The
  // recorder renders every frame itself; the loop must keep its hands off
  // the canvas until the take ends.
  // Before the controls settle, so the orbit follows the eye this frame.
  flyCamera(delta);
  // The wind's clock runs while there is wind, and never in renderView,
  // which reads no clock; a still stands the air still for all its tiles.
  if (!state.recording && windAir.windStrength.value > 0) windAir.windTime.value += delta;
  const turntableOwns = state.timeline
    && (state.timeline.playing || state.recording)
    && state.timeline.orbitBase && state.timeline.autoSpin
    && !state.userDragging;
  if (!turntableOwns) controls.update();
  // HERE, in the live loop, and not in renderView: renderView reads no
  // clock, so that a take draws the same frames however long it takes,
  // and waiting for the scene to hold still is a question of the clock.
  // The recorder never runs this loop, so no capture lands mid-take.
  if (reflectionDirtyAt && !state.recording
      && performance.now() - reflectionDirtyAt > REFLECTION_SETTLE_MS) {
    captureReflections();
  }
  if (!state.recording) renderView();
  noteFrame();
  requestAnimationFrame(frame);
}

// The tile grids are built here, after SKINS and skinMaterialCache exist.
guarded("the material tiles", buildMaterialTiles);
guarded("the weather tiles", buildWeatherTiles);
guarded("the atmosphere tiles", buildAtmosphereTiles);
guarded("the pickers", wireAllPickers);
guarded("the setting segments", () => buildSegmented("environment-segments", "environment-mode"));
guarded("the camera frame segments", () => {
  buildSegmented("camera-aspect-segments", "camera-aspect");
  buildSegmented("camera-projection-segments", "camera-projection");
  buildSegmented("section-mode-segments", "section-mode");
  buildSegmented("section-axis-segments", "section-axis");
  paintSectionControls();
  syncCameraControls();
  paintProjectionControls();
  paintScaleBar();
});
guarded("the slider rows", () => upgradeSliders());
// AFTER upgradeSliders, and that is load-bearing. upgradeSliders skips
// any label already carrying .hidden (panel.js), so hiding the width row
// before it runs would leave that dial as a bare slider for ever: never
// a .scrub, never typable, and paintScrub silently returning early on it.
// Both rows are therefore visible in the markup and one is hidden here.
guarded("the projection's own row", paintFrameWidth);
guarded("the output section", () => {
  buildSegmented("still-size-segments", "still-size");
  document.getElementById("still-size").addEventListener("change", (e) => {
    state.stillSize = e.target.value;
    paintStillControls();
    paintStillSize();
    rememberSession();
  });
  document.getElementById("still-render").addEventListener("click", renderStill);
  paintStillControls();
  paintStillSize();
});
guarded("the prop detail", () => {
  // A per-viewer choice, like the theme: the iPad wants Draft where the
  // desktop wants Balanced, and neither is part of any scene.
  try {
    const kept = localStorage.getItem(DETAIL_KEY);
    if (kept && kept in DETAIL_REACH) state.detail = kept;
  } catch (error) { /* a blocked store keeps the default */ }
  const select = document.getElementById("prop-detail");
  buildSegmented("prop-detail-segments", "prop-detail");
  select.value = state.detail;
  paintSegmented("prop-detail-segments", "prop-detail");
  select.addEventListener("change", (e) => {
    state.detail = e.target.value;
    paintSegmented("prop-detail-segments", "prop-detail");
    try { localStorage.setItem(DETAIL_KEY, state.detail); } catch (error) { /* ditto */ }
  });
});
guarded("the panel groups", buildGroups);
// The libraries load in the background: the studio is usable before either
// arrives, a folder with nothing in it simply leaves the old props, and no
// material folder chosen leaves the four built-in skins.
loadPropLibrary().catch((error) => logStudio("prop library: " + error.message));
// The machine chooser is gone (2026-09-15): a vault wears the mechanism
// exported with it. A choice the chooser remembered means nothing now, so
// it is forgotten rather than left to be misread.
try { localStorage.removeItem("vaulted.mechanism.choice"); } catch (error) { /* nothing stored */ }
showLibraryFolder("recordings", "recordings-folder-path", "recordings");
document.getElementById("recordings-folder-choose").addEventListener("click", () =>
  chooseLibraryFolder("recordings", "recordings-folder-path", "recordings",
    async () => {}));
materialLibraryReady = refreshMaterialLibrary().catch(
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
window.__studio = { state, scene, controls, applyDayCycle, placeProp,
  // A probe that places props must be able to take them away: a batched
  // prop's proxy is not propsGroup's child, so parent.remove does nothing.
  disposeProp,
  // The live graphs' series, so a probe can read the model's numbers at
  // an instant rather than a card's rounded text.
  liveGraphs,
  // The instanced batches and the per-frame settle that fills them, so a
  // probe can count what the frame is actually asked to draw -- how many
  // instances, which LOD tier each is in, and how long the settle takes
  // -- rather than inferring it from the frame rate.
  propBatches, settlePropInstances, setClusterTarget, setCullPixels,
  notePropsMoved, applyLayerVisibility, propRecordAt,
  // The keep-out index and the hover, so a probe can ask the two
  // questions a placement asks -- can this land here, and what does the
  // pointer say it is over -- without driving the mouse.
  scatterKeepOut, keepOutClear, keepOutAdd, setHoveredProp, propBaseRadius, runScatter,
  captureReflections, reflectionWearers, get reflectionsTaken() { return reflectionsTaken; },
  // The wind's air and the one render entry, so a probe can hold the wind's
  // clock at an instant and photograph it, shadows included.
  windAir, renderView,
  // A scene restored straight from a record, so a probe can hand it one
  // that is missing settings and see what comes back.
  applyScene, collectScene,
  reflectionTarget,
  ensurePropTemplate, renderObjectPreview, composer, buildMachine,
  machine: () => machineObjects,
  // A GETTER, because `camera` is now a binding that moves between two
  // objects. Captured by value, a probe in an orthographic view would
  // have been handed the perspective camera and quietly measured the
  // wrong frustum.
  get camera() { return camera; },
  perspectiveCamera, orthographicCamera, setProjection, snapCameraTo,
  // The atmosphere's shared uniforms and its one fog object, so a probe
  // can read what the shaders are being given rather than guess it.
  atmosphere, get atmosphereFog() { return atmosphereFog; },
  // The shaft pass itself, so a probe can read whether it is running and
  // at what size rather than inferring it from pixels.
  get shaftsPass() { return shaftsPass; },
  // The clock, so a probe can photograph a named hour through the same
  // path the day track takes.
  setSunMinutes };
// The page's boot-fault banner (index.html) stands down once evaluation has
// made it to here: from this line on, a stray rejection is an incident for
// the diagnostics log, not a "half-built panel" alarm.
window.__studioReady = true;

export { state, buildScene, setLayer, applyCut, applyTimeline, timelineDuration, rebuildTimeline };
