import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { Sky } from "three/addons/objects/Sky.js";
import { GroundedSkybox } from "three/addons/objects/GroundedSkybox.js";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { BrightnessContrastShader } from "three/addons/shaders/BrightnessContrastShader.js";
import {
  boxUVs, segmentUVOffset, smoothStressField, interpolateScalarField,
  sampleScalar, sampleVector, creaseNormals, estimateSunFromEquirect,
  interpolateFormworkFrame,
} from "/static/fields.js";

// ---------- app state ----------
const state = {
  bundle: null,
  source: null,        // deliverable B: null = whatever the study has (Skin wins), else "authored" | "generated"
  formwork: null,      // bench.frames/1 payload for this study, or null: frames, edges, columns.members (see applyFormworkAct)
  studies: [],
  layers: { overlays: true }, // shell and wires are gone: the Show select owns both (applyShowMode)
  showMode: "timeline", // R4: "framework" | "shell" | "both" | "timeline" (see applyShowMode)
  formworkMode: "hidden", // Formwork control: "animation" | "always" | "hidden" (see applySceneAtTime)
  environmentMode: "studio", // E1: "studio" | "sky" | "hdri", each owns background, environment, fog, sun
  weatherPreset: "clear",    // E2: a key of WEATHER
  groundPreset: "dark-studio", // E4: a key of GROUNDS, independent of the environment mode
  props: [],            // E5: [{ type, x, y, rotation, object }], mirrored to localStorage
  armedPropType: null,  // a prop button was clicked; the next ground click places it
  selectedProp: null,   // the record whose object is highlighted and keyboard-driven
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
  jointGap: 0.02,
  taper: 0,
  segmentIndex: null,  // Task 11
  nodeRadius: 0.03,    // Task 6
  wireRadius: 0.02,    // Task 6
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
  appearance: { tint: null, finish: null, skin: "none" },
};

const canvas = document.getElementById("view");
const scrubber = document.getElementById("timeline-scrubber");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;

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
  renderer.toneMappingExposure = state.exposureBase * state.brightness;
  gradePass.uniforms.brightness.value = 0;
  gradePass.uniforms.contrast.value = state.contrast;
}

function renderView() {
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

function applySunFromSliders() {
  applySunAt(+document.getElementById("sun-azimuth").value, +document.getElementById("sun-elevation").value);
}

// S5: the day as a pure function of u in [0,1]. Azimuth sweeps west to
// east through south; elevation is a sine arc to the peak captured at
// start; colour and intensity ramp warm-dim, white-bright, warm-dim.
// Writes the sliders and the colour input so the UI tells the truth.
function applyDayCycle(u) {
  const azimuthDeg = ((270 - 180 * u) % 360 + 360) % 360;
  const elevation = 2 + (state.dayCycle.peakElevation - 2) * Math.sin(Math.PI * u);
  const warmth = 1 - Math.sin(Math.PI * u);
  const colour = new THREE.Color().setHSL(0.08, 0.55 * warmth, 0.5 + 0.3 * (1 - warmth));
  document.getElementById("sun-azimuth").value = Math.round(azimuthDeg);
  // F1: the slider's own min="5" cannot display a lower value, but the
  // sun position below is driven off the unclamped elevation, not this
  // display write -- otherwise a captured peak, or the arc's own 2 degree
  // dawn, would flatten the instant either one touched the floor.
  document.getElementById("sun-elevation").value = Math.round(Math.max(5, elevation));
  document.getElementById("sun-colour").value = "#" + colour.getHexString();
  sun.color.copy(colour);
  sun.intensity = 0.8 + 2.4 * Math.sin(Math.PI * u);
  applySunAt(azimuthDeg, elevation);
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
  document.getElementById("weather-row").classList.toggle("hidden", state.environmentMode !== "sky");
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
}

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
  if (state.hdriProjection === "projected" && state.hdriTexture) {
    const dome = new GroundedSkybox(state.hdriTexture, state.hdriHeight, state.hdriScale);
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
    group.add(dome);
    scene.add(group);
    hdriDome = group;
    scene.background = null;
  } else {
    scene.background = state.hdriTexture; // null paints the clear colour until a file loads
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
  return files;
}

async function loadHdri(name) {
  const status = document.getElementById("hdri-status");
  status.textContent = "loading " + name;
  try {
    const loader = new HDRLoader().setDataType(THREE.FloatType);
    const texture = await loader.loadAsync("/api/hdri/" + encodeURIComponent(name));
    texture.mapping = THREE.EquirectangularReflectionMapping;
    if (state.hdriTexture) state.hdriTexture.dispose();
    state.hdriTexture = texture;
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

const GROUNDS = {
  "dark-studio": () => new THREE.MeshPhysicalMaterial({ color: 0x22242a, roughness: 0.95 }),
  "concrete-slab": () => new THREE.MeshPhysicalMaterial({
    color: 0x8f9094,
    map: noiseTexture(512, 200, 10),
    roughness: 0.93,
    roughnessMap: noiseTexture(512, 215, 30),
  }),
  "patio-pavers": () => {
    const texture = groundJointTexture(4, 4, true, 172);
    texture.repeat.set(120 / (4 * 1.2), 120 / (4 * 0.9)); // 1.2 x 0.9 m pavers
    const material = new THREE.MeshPhysicalMaterial({
      color: 0xb0a698, map: texture, roughness: 0.9,
      bumpMap: texture, bumpScale: 0.35,
    });
    return material;
  },
  "tiles": () => {
    const texture = groundJointTexture(8, 8, false, 168);
    texture.repeat.set(120 / (8 * 0.6), 120 / (8 * 0.6)); // 0.6 m square tiles
    const material = new THREE.MeshPhysicalMaterial({
      color: 0x9aa0a4, map: texture, roughness: 0.55,
      bumpMap: texture, bumpScale: 0.2,
    });
    return material;
  },
};

const groundMaterialCache = {};

function groundMaterial(preset) {
  if (!groundMaterialCache[preset]) groundMaterialCache[preset] = GROUNDS[preset]();
  return groundMaterialCache[preset];
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

function saveProps() {
  const layout = state.props.map((p) => ({ type: p.type, x: p.x, y: p.y, rotation: p.rotation }));
  localStorage.setItem(propsKey(), JSON.stringify(layout));
}

// Mirrors disposeShell's rule: whatever is replaced owns GPU buffers.
function disposeProp(object) {
  object.traverse((child) => {
    if (child.isMesh) {
      child.geometry.dispose();
      child.material.dispose();
    }
  });
}

function restoreProps() {
  for (const record of state.props) { disposeProp(record.object); propsGroup.remove(record.object); }
  state.props = [];
  state.selectedProp = null;
  let layout = [];
  try {
    layout = JSON.parse(localStorage.getItem(propsKey()) || "[]");
  } catch (error) {
    layout = [];
  }
  if (!Array.isArray(layout)) layout = [];
  for (const entry of layout) {
    if (!PROP_BUILDERS[entry.type]) continue;
    placeProp(entry.type, +entry.x || 0, +entry.y || 0, +entry.rotation || 0, false);
  }
}

function placeProp(type, x, y, rotation, save) {
  const object = makeProp(type);
  object.position.set(x, y, 0);
  object.rotation.z = rotation;
  propsGroup.add(object);
  const record = { type, x, y, rotation, object };
  state.props.push(record);
  if (save) saveProps();
  return record;
}

function setPropEmissive(record, on) {
  record.object.traverse((child) => {
    if (child.isMesh) child.material.emissive.set(on ? 0x2a4a66 : 0x000000);
  });
}

function selectProp(record) {
  if (state.selectedProp) setPropEmissive(state.selectedProp, false);
  state.selectedProp = record;
  if (record) setPropEmissive(record, true);
}

function armProp(type) {
  const already = state.armedPropType === type;
  disarmProp();
  if (already) return;
  state.armedPropType = type;
  controls.enabled = false;
  document.getElementById("prop-" + type).classList.add("armed");
}

function disarmProp() {
  if (state.armedPropType) {
    document.getElementById("prop-" + state.armedPropType).classList.remove("armed");
  }
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
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  return propRaycaster.ray.intersectPlane(plane, hit) ? hit : null;
}

function propRecordAt(event) {
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1);
  propRaycaster.setFromCamera(ndc, camera);
  const hits = propRaycaster.intersectObjects(propsGroup.children, true);
  if (!hits.length) return null;
  let node = hits[0].object;
  while (node.parent && node.parent !== propsGroup) node = node.parent;
  return state.props.find((p) => p.object === node) || null;
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

function buildWiresAndNodes(bundle) {
  const { vertices, edges } = bundle.analysis_mesh;
  const wireRadius = state.wireRadius, nodeRadius = state.nodeRadius;
  const cylinder = new THREE.CylinderGeometry(wireRadius, wireRadius, 1, 8, 1, true);
  cylinder.translate(0, 0.5, 0);
  const wireMaterial = materials.steel.clone();
  // Task 6 fix: InstancedMesh.setColorAt writes the instanceColor buffer,
  // but per-instance colour only reaches the fragment shader when the
  // material also opts into the vertex-colour path. vertexColors stays
  // true for the wires' whole lifetime; every instance starts white below
  // so the plain steel look is unchanged until applyWireForces tints it.
  wireMaterial.vertexColors = true;
  wireMaterial.transparent = true;
  const wires = new THREE.InstancedMesh(cylinder, wireMaterial, edges.length);
  const up = new THREE.Vector3(0, 1, 0);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  const white = new THREE.Color(0xffffff);
  const baseMatrices = [];
  edges.forEach(([u, v], i) => {
    const a = new THREE.Vector3(...vertices[u]);
    const b = new THREE.Vector3(...vertices[v]);
    const d = b.clone().sub(a);
    q.setFromUnitVectors(up, d.clone().normalize());
    s.set(1, d.length(), 1);
    m.compose(a, q, s);
    wires.setMatrixAt(i, m);
    wires.setColorAt(i, white);
    baseMatrices.push(m.clone());
  });
  wires.instanceColor.needsUpdate = true;
  // Task 6: the forces layer rebuilds instance matrices (thicker wire =
  // bigger force) and restores them on toggle-off; the base endpoints/
  // orientation/length live here so that restore is exact.
  wires.userData.baseMatrices = baseMatrices;
  const sphere = new THREE.SphereGeometry(nodeRadius, 12, 8);
  const nodeMaterial = materials.steel.clone();
  nodeMaterial.transparent = true;
  const nodes = new THREE.InstancedMesh(sphere, nodeMaterial, vertices.length);
  vertices.forEach((v, i) => {
    m.makeTranslation(v[0], v[1], v[2]);
    nodes.setMatrixAt(i, m);
  });
  // The thrust network is a diagram of the analysis, not a scene object.
  // Once the vault closes, the wires sit hidden inside the shell, and
  // shadow maps ignore both occlusion and opacity, so with castShadow on
  // they projected a grid shadow of an invisible net through the finished
  // vault onto the ground. Overlays cast nothing; castings and columns do.
  wires.castShadow = nodes.castShadow = false;
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

function rebuildWiresAndNodes() {
  if (!state.bundle) return;
  disposeWiresAndNodes();
  const { wires, nodes } = buildWiresAndNodes(state.bundle);
  state.objects.wires = wires;
  state.objects.nodes = nodes;
  scene.add(wires);
  scene.add(nodes);
  applyWireForces();
  // Scene-only recompute: a size-slider rebuild must not move the camera.
  if (state.timeline) applySceneAtTime(state.timeline.t);
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
      const geometry = columnGeometryFrom(await fetchJson("/api/columns/" + encodeURIComponent(name)));
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
async function reloadColumns(names) {
  if (state.objects.columns) {
    scene.remove(state.objects.columns);
    state.objects.columns = null;
  }
  if (names.length) {
    state.objects.columns = await loadColumns(names);
    scene.add(state.objects.columns);
  }
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

  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(60, 64),
    groundMaterial(state.groundPreset)
  );
  ground.receiveShadow = true;
  ground.position.z = -0.03;
  state.objects.ground = ground;
  scene.add(ground);

  applyCut(preserve);
  buildLayerToggles();
  updateVectorLayers();
  updateMaterialControls();
  restoreProps();
  updateHud();
}

// ---------- the cut (Task 8: pieces and their course/size come from the server) ----------
// Mirrors app.py's own SIZE_MIN/SIZE_MAX. The bundle's top level "size" is
// meant to be the requested size (see bundle.py), but a client that trusts
// a server value blindly is exactly how a poisoned value like the old
// authored-cut sentinel reaches the screen; this is the defence in depth
// for that class of bug, not the fix for it.
const SIZE_MIN = 0.3, SIZE_MAX = 3.0;

function applyCut(preserve) {
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
  document.getElementById("size-units").textContent =
    state.bundle.tessellation.source === "imported"
      ? " mm requested, but this cut is authored in Grasshopper and the size control is not used"
      : " mm target";
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
  const select = document.getElementById("source-select");
  const note = document.getElementById("source-note");
  if (row && select) {
    row.classList.toggle("hidden", available.length < 2);
    select.value = state.bundle.source;
    state.source = state.bundle.source;
    if (note) {
      note.textContent = state.bundle.source === "authored"
        ? "cells authored in Grasshopper, with their own courses"
        : "the studio's own cut, from the pattern and size above";
    }
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
  if (!response.ok) throw new Error(url + " -> " + response.status + " " + (await response.text()));
  return response.json();
}

// ---------- pattern control (Task 9) ----------
// generators.PLANNED and generators.MATERIAL_NOTES are the honesty
// mechanism: a pattern named in the spec but not built yet is listed and
// disabled rather than silently absent, and a material whose intended
// pattern is not built yet says so in pattern-note instead of quietly
// drawing bonded courses under the missing pattern's name.
function patternLabel(pattern) {
  return pattern.split("-").map((word) => word[0].toUpperCase() + word.slice(1)).join(" ");
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

async function loadStudy(exportName) {
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
    loaded = true;
    logStudio("loaded " + exportName + " (" + materialLabel + ", "
      + patternLabel(state.pattern) + ", " + state.size + " m) in "
      + ((Date.now() - startedAt) / 1000).toFixed(1) + "s");
  } catch (error) {
    if (sequence !== state.loadSequence) return;
    overlay.classList.add("hidden");
    status.textContent = "";
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
    const select = document.getElementById("study-select");
    select.innerHTML = "";
    const names = [];
    for (const study of payload.studies) {
      const option = document.createElement("option");
      option.value = study.export;
      option.textContent = study.export + (study.has_verification ? " (verified)" : "");
      select.appendChild(option);
      names.push(study.export);
    }
    // M2 fix: after an export-pair import, boot() must land on the export
    // that was just imported, not silently fall back to studies[0]. The
    // preferred name only wins when it actually exists in the fresh list
    // (an incomplete pair, for instance, never appears here at all).
    const toLoad = preferredExport && names.includes(preferredExport)
      ? preferredExport
      : (names.length ? names[0] : null);
    if (toLoad) {
      select.value = toLoad;
      await loadStudy(toLoad);
    }
    await reloadColumns(payload.columns);
  } catch (error) {
    showBanner("Server not reachable: " + error.message, "error");
  }
}

// ---------- browser import: export pairs and columns ----------
async function putFile(url, file) {
  const text = await file.text();
  const response = await fetch(url, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: text,
  });
  if (!response.ok) {
    let detail = response.status;
    try { detail = (await response.json()).detail || detail; } catch (error) { /* body wasn't JSON */ }
    throw new Error(url + " -> " + detail);
  }
  return response.json();
}

async function importExportPair() {
  const status = document.getElementById("import-status");
  const input = document.getElementById("import-export-input");
  const files = Array.from(input.files || []);
  const contractFile = files.find((f) => f.name.endsWith("-contract.json"));
  const compasFile = files.find((f) => f.name.endsWith("-compas.json"));
  if (files.length !== 2 || !contractFile || !compasFile) {
    status.textContent = "pick exactly a *-contract.json and *-compas.json pair";
    return;
  }
  const contractPrefix = contractFile.name.slice(0, -"-contract.json".length);
  const compasPrefix = compasFile.name.slice(0, -"-compas.json".length);
  if (!contractPrefix || contractPrefix !== compasPrefix) {
    status.textContent = "the two files must share the same export name prefix";
    return;
  }
  status.textContent = "uploading " + contractPrefix + "...";
  try {
    await putFile("/api/uploads/exports/" + encodeURIComponent(contractPrefix) + "/contract", contractFile);
    const result = await putFile("/api/uploads/exports/" + encodeURIComponent(contractPrefix) + "/compas", compasFile);
    status.textContent = result.pair_complete
      ? "imported " + contractPrefix
      : "stored " + contractPrefix + "; pair incomplete";
    logStudio(result.pair_complete
      ? "imported export pair " + contractPrefix
      : "stored " + contractPrefix + "; pair incomplete");
    input.value = "";
    // M2 fix: select and load the export that was just imported, instead
    // of leaving boot() to fall back to studies[0].
    await boot(contractPrefix);
  } catch (error) {
    status.textContent = "import failed: " + error.message;
    logStudio("export pair import failed: " + error.message);
  }
}

async function importColumns() {
  const status = document.getElementById("import-status");
  const input = document.getElementById("import-columns-input");
  const file = input.files && input.files[0];
  if (!file) {
    status.textContent = "pick a columns JSON file first";
    return;
  }
  status.textContent = "uploading " + file.name + "...";
  try {
    await putFile("/api/uploads/columns/" + encodeURIComponent(file.name), file);
    status.textContent = "imported " + file.name;
    logStudio("imported columns file " + file.name);
    input.value = "";
    const payload = await fetchJson("/api/studies");
    state.studies = payload.studies;
    await reloadColumns(payload.columns);
  } catch (error) {
    status.textContent = "import failed: " + error.message;
    logStudio("columns import failed: " + error.message);
  }
}

// ---------- UI wiring ----------
document.getElementById("study-select").addEventListener("change", (e) => {
  // A source choice belongs to the study it was made on. Carried across,
  // the previous study's "authored" rode into the next study's request
  // and 400'd every study without a Skin: basic navigation broke after
  // opening one Skin study. Null means "whatever this study has".
  state.source = null;
  loadStudy(e.target.value);
});
document.getElementById("material-select").addEventListener("change", (e) => {
  // Same rule as loadStudy: the incoming material's stored appearance is
  // restored before anything is rebuilt, never after.
  restoreAppearance(e.target.value);
  updatePatternForMaterial(e.target.value);
  const select = document.getElementById("study-select");
  if (select.value && !requestMatchesLoaded(e.target.value)) loadStudy(select.value);
});
document.getElementById("render-skin").addEventListener("change", (e) => {
  state.appearance.skin = e.target.value;
  persistAppearance();
  rebuildAppearance();
});
document.getElementById("material-tint").addEventListener("change", (e) => {
  state.appearance.tint = e.target.value;
  persistAppearance();
  rebuildAppearance();
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
document.getElementById("source-select").addEventListener("change", async (e) => {
  const previous = state.source;
  state.source = e.target.value;
  const study = document.getElementById("study-select");
  if (!study.value) return;
  const loaded = await loadStudy(study.value);
  if (loaded === false) {
    // A source can exist and still be uncuttable: this vault's plan is
    // not star shaped, so the studio's polar generator refuses it by
    // name and only the Skin can cut it. The banner carries that
    // message; the control goes back to the cut still on screen rather
    // than sitting on a source the study never loaded.
    state.source = previous;
    e.target.value = state.bundle ? state.bundle.source : previous;
  }
});
document.getElementById("pattern-select").addEventListener("change", (e) => {
  state.pattern = e.target.value;
  state.patternChosen = true;
  const select = document.getElementById("study-select");
  const material = document.getElementById("material-select").value;
  if (select.value && !requestMatchesLoaded(material)) loadStudy(select.value);
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
});
document.getElementById("thickness-input").addEventListener("change", (e) => {
  state.thickness = +e.target.value;
  scheduleReload();
});
document.getElementById("joint-gap").addEventListener("input", (e) => {
  document.getElementById("joint-gap-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("joint-gap").addEventListener("change", (e) => {
  state.jointGap = +e.target.value;
  if (!state.bundle) return;
  buildPieceMeshes();
  recolourSegments();
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
document.getElementById("taper").addEventListener("input", (e) => {
  document.getElementById("taper-value").textContent = Math.round(+e.target.value * 100);
});
document.getElementById("taper").addEventListener("change", (e) => {
  state.taper = +e.target.value;
  if (!state.bundle) return;
  buildPieceMeshes();
  recolourSegments();
  updateHud();
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
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
document.getElementById("hdri-upload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const status = document.getElementById("hdri-status");
  status.textContent = "uploading " + file.name;
  try {
    const response = await fetch("/api/uploads/hdri/" + encodeURIComponent(file.name), {
      method: "PUT",
      body: file,
    });
    if (!response.ok) throw new Error(await response.text());
    status.textContent = "";
    const files = await refreshHdriList(file.name);
    if (files === null) return; // fetch failed; already bannered
    await loadHdri(file.name);
  } catch (error) {
    status.textContent = "";
    showBanner("Failed to upload " + file.name + ": " + error.message, "error");
  } finally {
    // Always runs, success or failure, so a failed upload never jams the
    // input: without this, choosing the same filename again after a
    // failure does not re-fire "change" (the value never changed), and
    // the picker looks like it silently does nothing on the retry.
    event.target.value = "";
  }
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
document.getElementById("ground-preset").addEventListener("change", (e) => {
  state.groundPreset = e.target.value;
  if (state.objects.ground) state.objects.ground.material = groundMaterial(e.target.value);
});
for (const [id, type] of [["prop-figure", "figure"], ["prop-tree", "tree"],
                          ["prop-pallets", "pallets"], ["prop-barrier", "barrier"],
                          ["prop-cone", "cone"]]) {
  document.getElementById(id).addEventListener("click", () => {
    if (state.bundle) armProp(type);
  });
}
document.getElementById("props-clear").addEventListener("click", () => {
  if (!state.bundle) return;
  for (const record of state.props) { disposeProp(record.object); propsGroup.remove(record.object); }
  state.props = [];
  state.selectedProp = null;
  saveProps();
});
canvas.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || !state.bundle) return;
  if (state.armedPropType) {
    const hit = groundPointAt(event);
    if (hit) selectProp(placeProp(state.armedPropType, hit.x, hit.y, 0, true));
    disarmProp();
    return;
  }
  const record = propRecordAt(event);
  if (record) {
    selectProp(record);
    state.propDrag = true;
    controls.enabled = false;
    canvas.setPointerCapture(event.pointerId);
  } else if (state.selectedProp) {
    selectProp(null);
  }
});
canvas.addEventListener("pointermove", (event) => {
  if (!state.propDrag || !state.selectedProp) return;
  const hit = groundPointAt(event);
  if (!hit) return;
  state.selectedProp.x = hit.x;
  state.selectedProp.y = hit.y;
  state.selectedProp.object.position.set(hit.x, hit.y, 0);
});
function endPropDrag(event) {
  if (canvas.hasPointerCapture && canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  if (!state.propDrag) return;
  state.propDrag = false;
  controls.enabled = true;
  saveProps();
}
canvas.addEventListener("pointerup", endPropDrag);
canvas.addEventListener("pointercancel", endPropDrag);
window.addEventListener("keydown", (event) => {
  const tag = document.activeElement ? document.activeElement.tagName : "";
  if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
  if (!state.selectedProp) return;
  if (event.key === "r" || event.key === "R") {
    state.selectedProp.rotation += Math.PI / 12;
    state.selectedProp.object.rotation.z = state.selectedProp.rotation;
    saveProps();
  } else if (event.key === "Delete" || event.key === "Backspace") {
    disposeProp(state.selectedProp.object);
    propsGroup.remove(state.selectedProp.object);
    state.props = state.props.filter((p) => p !== state.selectedProp);
    state.selectedProp = null;
    saveProps();
  }
});
// "change" (drag release), not "input": the file's own convention for every
// other slider that rebuilds something, and this one re-runs the recolour
// over every casting's geometry. On the real export that is 233 of them per
// event, which a drag fires dozens of.
document.getElementById("exaggeration").addEventListener("change", () => recolourSegments());
document.getElementById("stress-surface").addEventListener("change", () => recolourSegments());
document.getElementById("formwork-mode").addEventListener("change", (e) => {
  state.formworkMode = e.target.value;
  // Scene-only recompute: a mode change must never move the camera.
  if (state.timeline) {
    applySceneAtTime(state.timeline.t);
  } else if (state.objects.falsework) {
    state.objects.falsework.visible = e.target.value !== "hidden";
  }
});
document.getElementById("show-mode").addEventListener("change", (e) => {
  state.showMode = e.target.value;
  if (state.timeline) applySceneAtTime(state.timeline.t);
});
// Same pattern as the thickness slider: "input" only updates the live mm
// label, "change" (drag release) commits the value and rebuilds -- so a
// drag fires one InstancedMesh rebuild, not dozens.
document.getElementById("node-radius").addEventListener("input", (e) => {
  document.getElementById("node-radius-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("node-radius").addEventListener("change", (e) => {
  state.nodeRadius = +e.target.value;
  document.getElementById("node-radius-value").textContent = Math.round(state.nodeRadius * 1000);
  rebuildWiresAndNodes();
});
document.getElementById("wire-radius").addEventListener("input", (e) => {
  document.getElementById("wire-radius-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("wire-radius").addEventListener("change", (e) => {
  state.wireRadius = +e.target.value;
  document.getElementById("wire-radius-value").textContent = Math.round(state.wireRadius * 1000);
  rebuildWiresAndNodes();
});
document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  renderDataPanel(state.bundle ? state.bundle.verification : null);
  panel.classList.toggle("hidden");
});
document.getElementById("data-close").addEventListener("click", () =>
  document.getElementById("data-panel").classList.add("hidden"));
document.getElementById("run-button").addEventListener("click", startRun);
document.getElementById("import-export-button").addEventListener("click", importExportPair);
document.getElementById("import-columns-button").addEventListener("click", importColumns);

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
    inflateSeconds: +document.getElementById("inflate-seconds").value,
    orbitSpeed: +document.getElementById("orbit-speed").value,
    orbitDistance: +document.getElementById("orbit-distance").value,
    autoSpin: true,
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
    document.getElementById("play-button").textContent =
      preserve.playing ? "Pause" : "Play";
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

function timelineDuration() {
  const step = placementStep();
  return openingSeconds() + placementCount() * step
    + DROP_SECONDS + STRIKE_SECONDS;
}

function pieceTint(key) {
  // A deterministic lightness nudge per casting, so no two pieces look
  // identical and the same study always looks the same.
  const offset = segmentUVOffset(key);
  return (offset[0] % 1) * 0.06 - 0.03;
}

// Task 5: render skins. "none" is not a factory: it means "show the
// registry material", which appearanceMaterialBase reads straight from
// materials[]. The three real skins are lazily built and cached like
// groundMaterial caches GROUNDS, since each is a MeshPhysicalMaterial with
// its own procedural map and should not be rebuilt on every piece.
const SKINS = {
  none: null,
  "white-presentation": () => new THREE.MeshPhysicalMaterial({
    color: 0xf4f4f0, side: THREE.DoubleSide,
    map: noiseTexture(256, 245, 8),
    roughness: 0.55, metalness: 0.0,
  }),
  "basalt-dark": () => new THREE.MeshPhysicalMaterial({
    color: 0x2e3236, side: THREE.DoubleSide,
    roughness: 0.85, metalness: 0.0,
  }),
  "timber-ply": () => new THREE.MeshPhysicalMaterial({
    color: 0xc9a86a, side: THREE.DoubleSide,
    map: grainTexture(512),
    roughness: 0.7, metalness: 0.0,
  }),
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
  let offset = 0;
  for (const entry of built) {
    const { piece, positions, weights, surface, centre } = entry;
    const normals = welded
      ? welded.slice(offset, offset + positions.length)
      : creaseNormals(positions);
    offset += positions.length;
    const uvs = boxUVs(positions, centre, segmentUVOffset(piece.key));
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
  return state.bundle && state.bundle.material === "concrete-sprayed";
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
  const sprayed = sprayedMaterial();
  document.getElementById("joint-gap").disabled = !!sprayed;
  document.getElementById("joint-gap-note").textContent =
    sprayed ? " (sprayed concrete is monolithic: no joints to open)" : "";
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
}

// Called from both the material-select change handler and loadStudy, both
// BEFORE the incoming material's pieces are built, so a stored override
// (or the lack of one) is always in state.appearance by the time
// pieceMaterial first reads it for the material being switched to.
function restoreAppearance(material) {
  let appearance = { tint: null, finish: null, skin: "none" };
  const stored = localStorage.getItem(appearanceStorageKey(material));
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      appearance = {
        tint: parsed.tint || null,
        finish: typeof parsed.finish === "number" ? parsed.finish : null,
        skin: typeof parsed.skin === "string" ? parsed.skin : "none",
      };
    } catch (error) { /* corrupt localStorage entry: fall back to the defaults above */ }
  }
  state.appearance = appearance;
  syncAppearanceControls();
}

// The joint-gap handler's exact rebuild shape, reused across the four
// appearance controls: a tint, finish or skin change never touches the
// bundle, so it never needs a server round trip, only a redraw.
function rebuildAppearance() {
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

function rebuildFormworkObjects() {
  if (formworkObjects) {
    scene.remove(formworkObjects.group);
    for (const child of formworkObjects.group.children) {
      child.geometry.dispose();
      child.material.dispose();
    }
    formworkObjects = null;
  }
  const doc = state.formwork;
  if (!doc || !Array.isArray(doc.frames) || !doc.frames.length) return;
  // Line segments, not tubes: cheap enough to rewrite every frame (one
  // Float32 write per endpoint), and the machine reads as scaffolding
  // rather than competing with the shell for weight.
  const group = new THREE.Group();
  const handles = { group, net: null, members: null };
  const first = doc.frames[0];
  const edges = Array.isArray(doc.edges) ? doc.edges : [];
  if (edges.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position", new THREE.BufferAttribute(new Float32Array(edges.length * 6), 3));
    const net = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({ color: 0x9aa4b0, transparent: true, opacity: 0.9 }));
    net.frustumCulled = false;
    handles.net = net;
    group.add(net);
  }
  const members = doc.columns && Array.isArray(doc.columns.members) ? doc.columns.members : [];
  if (members.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position", new THREE.BufferAttribute(new Float32Array(members.length * 6), 3));
    const bars = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({ color: 0x8a6a4a, transparent: true, opacity: 1 }));
    bars.frustumCulled = false;
    handles.members = bars;
    group.add(bars);
  }
  // Seeded with the first frame, not zeros: a zero-filled buffer is a
  // degenerate, invisible net until the first timeline apply, which is
  // exactly the empty viewport the review reproduced.
  if (handles.net) writeSegmentPositions(handles.net, edges, first.vertices);
  if (handles.members) writeSegmentPositions(handles.members, members, first.columnNodes);
  formworkObjects = handles;
  scene.add(group);
}

function writeSegmentPositions(object, pairs, points) {
  const positions = object.geometry.attributes.position;
  for (let i = 0; i < pairs.length; i++) {
    const a = points[pairs[i][0]];
    const b = points[pairs[i][1]];
    positions.setXYZ(i * 2, a[0], a[1], a[2]);
    positions.setXYZ(i * 2 + 1, b[0], b[1], b[2]);
  }
  positions.needsUpdate = true;
}

// The formwork act's whole scene contribution, pure in t like everything
// else on this clock. During the act the machine's net and members follow
// the interpolated frame; at act end the net yields to the instanced
// thrust wires (its final pose IS theirs, the writer's time-100
// guarantee), while the members stand through the build and strike away
// on the same clock as the wires. Early-returns on missing objects for
// the same render-loop reason applySceneAtTime documents.
function applyFormworkAct(t, strikeU) {
  if (!formworkObjects) return;
  const group = formworkObjects.group;
  const doc = state.formwork;
  const seconds = formworkSeconds();
  if (!doc || seconds <= 0 || state.showMode !== "timeline") {
    group.visible = false;
    return;
  }
  group.visible = strikeU < 1;
  const machineTime = Math.min(100, Math.max(0, (t / seconds) * 100));
  const frame = interpolateFormworkFrame(doc.frames, machineTime);
  const net = formworkObjects.net;
  if (net) {
    net.visible = t < seconds;
    if (net.visible) writeSegmentPositions(net, doc.edges, frame.vertices);
  }
  const bars = formworkObjects.members;
  if (bars) {
    bars.material.opacity = 1 - strikeU;
    bars.position.z = -1.5 * strikeU;
    writeSegmentPositions(bars, doc.columns.members, frame.columnNodes);
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
  const clearance = {
    wires: state.bundle.provenance.thickness / 2 + state.wireRadius,
    nodes: state.bundle.provenance.thickness / 2 + state.nodeRadius,
  };
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
  const wireClearance = state.showMode === "both"
    ? state.bundle.provenance.thickness / 2 + state.wireRadius
    : 0;
  const nodeClearance = state.showMode === "both"
    ? state.bundle.provenance.thickness / 2 + state.nodeRadius
    : 0;
  state.objects.wires.position.z = wireClearance;
  state.objects.nodes.position.z = nodeClearance;
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

function applyTimeline(t) {
  applySceneAtTime(t);
  if (state.timeline.autoSpin && !state.userDragging) {
    const centre = state.centre;
    const angle = state.timeline.orbitSpeed * t;
    const r = state.timeline.orbitDistance;
    camera.position.set(centre.x + r * Math.cos(angle), centre.y + r * Math.sin(angle), 0.55 * r);
    camera.lookAt(centre);
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
  status.textContent = "recording " + total + " frames at 1080p (a few MB each on disk)";
  const wasPlaying = state.timeline.playing;
  // F2: a live day cycle must not keep advancing off frame()'s wall clock
  // while the recording also drives it off frameIndex -- two clocks racing
  // the same state would make a recording non-deterministic.
  const wasDayCyclePlaying = state.dayCycle.playing;
  state.timeline.playing = false;
  state.dayCycle.playing = false;
  renderer.setSize(1920, 1080, false);
  composer.setSize(1920, 1080);
  camera.aspect = 1920 / 1080;
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
  }
}
document.getElementById("record-button").addEventListener("click", recordAnimation);

// ---------- day cycle ----------
// S5: frame() is the only wall-clock advancer (see below); this button
// only arms/disarms state.dayCycle.playing and captures the elevation the
// arc peaks at, exactly as play-button arms state.timeline.playing.
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
controls.addEventListener("end", () => { state.userDragging = false; });

document.getElementById("play-button").addEventListener("click", () => {
  if (!state.timeline) return;
  if (state.timeline.t >= timelineDuration()) applyTimeline(0);
  state.timeline.playing = !state.timeline.playing;
  document.getElementById("play-button").textContent = state.timeline.playing ? "Pause" : "Play";
});
document.getElementById("restart-button").addEventListener("click", () => {
  if (!state.timeline) return;
  applyTimeline(0);
  state.timeline.playing = true;
  document.getElementById("play-button").textContent = "Pause";
});

scrubber.addEventListener("input", () => {
  if (!state.timeline) return;
  state.timeline.playing = false;
  document.getElementById("play-button").textContent = "Play";
  applyTimeline((+scrubber.value / 1000) * timelineDuration());
  updateHud();
});
for (const [id, prop] of [["inflate-seconds", "inflateSeconds"], ["orbit-speed", "orbitSpeed"], ["orbit-distance", "orbitDistance"]]) {
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
document.getElementById("inflate-seconds").addEventListener("input", (e) => {
  document.getElementById("inflate-value").textContent = (+e.target.value).toFixed(1);
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
      document.getElementById("play-button").textContent = "Play";
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
  controls.update();
  renderView();
  requestAnimationFrame(frame);
}

boot();
requestAnimationFrame(frame);

// The probe rig reads app state through this hook. Camera and controls are
// exported too so a capture run can frame a detail (the rim, a joint) that
// the default framing, tuned for a full-size vault, leaves illegible.
// applyDayCycle is exposed too (Task 3), so a probe can drive u directly
// through the real pure function instead of re-deriving its formula in
// probe-script JS, which would drift from the function it is meant to check.
window.__studio = { state, scene, camera, controls, applyDayCycle };

export { state, buildScene, setLayer, applyCut, applyTimeline, timelineDuration, rebuildTimeline };
