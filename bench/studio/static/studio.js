import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import {
  boxUVs, segmentUVOffset, smoothStressField, interpolateScalarField,
  sampleScalar, sampleVector,
} from "/static/fields.js";

// ---------- app state ----------
const state = {
  bundle: null,
  studies: [],
  layers: { wires: true, overlays: true, falsework: true },  // Task 14: layer visibility toggles
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

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const sun = new THREE.DirectionalLight(0xffffff, 3.0);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -30; sun.shadow.camera.right = 30;
sun.shadow.camera.top = 30; sun.shadow.camera.bottom = -30;
scene.add(sun);
scene.add(new THREE.HemisphereLight(0xbfd4e6, 0x30271f, 0.5));

function applyEnvironment() {
  const az = THREE.MathUtils.degToRad(+document.getElementById("sun-azimuth").value);
  const el = THREE.MathUtils.degToRad(+document.getElementById("sun-elevation").value);
  const r = 60;
  sun.position.set(r * Math.cos(el) * Math.cos(az), r * Math.cos(el) * Math.sin(az), r * Math.sin(el));
  const tone = +document.getElementById("background-tone").value / 100;
  scene.background = new THREE.Color().setHSL(0.6, 0.08, 0.06 + 0.5 * tone);
  // Light concretes were clipping to white under the room environment plus
  // filmic tone mapping, which made three different presets look identical.
  renderer.toneMappingExposure = 0.85;
  scene.environmentIntensity = 0.6;
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
  return texture;
}

const materials = {
  concrete: new THREE.MeshPhysicalMaterial({
    color: 0x9a958a, side: THREE.DoubleSide,      // warm mid grey
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
    color: 0xd8d2c4, side: THREE.DoubleSide,      // lighter, coarsest
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
  wires.castShadow = nodes.castShadow = true;
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
      showBanner("Column file " + name + " failed to load: " + error.message);
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

function buildScene(bundle) {
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
    new THREE.MeshPhysicalMaterial({ color: 0x22242a, roughness: 0.95 })
  );
  ground.receiveShadow = true;
  ground.position.z = -0.03;
  state.objects.ground = ground;
  scene.add(ground);

  applyCut();
  buildLayerToggles();
  updateVectorLayers();
  updateMaterialControls();
  updateHud();
}

// ---------- the cut (Task 8: pieces and their course/size come from the server) ----------
// Mirrors app.py's own SIZE_MIN/SIZE_MAX. The bundle's top level "size" is
// meant to be the requested size (see bundle.py), but a client that trusts
// a server value blindly is exactly how a poisoned value like the old
// authored-cut sentinel reaches the screen; this is the defence in depth
// for that class of bug, not the fix for it.
const SIZE_MIN = 0.3, SIZE_MAX = 3.0;

function applyCut() {
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
  rebuildTimeline();
}

// ---------- FEA layers ----------
const LAYERS = [
  ["stress", "Stress heatmap"],
  ["deflection", "Deflection heatmap"],
  ["loads", "Load vectors"],
  ["reactions", "Reaction vectors"],
  ["overlays", "Text overlays"],
  ["pulse", "Integrity pulse"],
  ["wires", "Thrust wires and nodes"],
  ["forces", "Wire forces"],
  ["falsework", "Falsework ghost"],
];

function finalStage() {
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return null;
  const last = staging.stages[staging.stages.length - 1];
  return last.struck_now && last.struck_now.converged ? last.struck_now : null;
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
  if (name === "wires" || name === "falsework") {
    // Visibility during and after the strike is the timeline's call, so
    // recompute from t instead of forcing visible here. This calls the
    // scene-only helper, not applyTimeline itself -- a layer checkbox must
    // never reposition a user-orbited camera.
    if (state.timeline) {
      applySceneAtTime(state.timeline.t);
    } else if (name === "wires") {
      state.objects.wires.visible = on;
      state.objects.nodes.visible = on;
    } else if (state.objects.falsework) {
      state.objects.falsework.visible = on;
    }
  }
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
  let topField = null, bottomField = null, worstField = null, pickedField = null;
  if (stage && wantStress) {
    const analysis = state.bundle.analysis_mesh;
    const sources = mesh.vertex_sources;
    const smooth = (which) => interpolateScalarField(
      smoothStressField(analysis.faces, analysis.vertices.length, stage.stresses, which),
      sources);
    if (surface === "per") {
      topField = smooth("top");
      bottomField = smooth("bottom");
      worstField = smooth("worst");
    } else {
      pickedField = smooth(surface);
    }
  }
  const white = new THREE.Color(0xffffff);
  for (const segment of state.objects.shell.children) {
    const weights = segment.userData.weights;
    const surfaceOf = segment.userData.surface;
    const base = segment.userData.basePositions;
    const positions = segment.geometry.getAttribute("position");
    const colours = new Float32Array(weights.length * 3);
    for (let i = 0; i < weights.length; i++) {
      const cornerSurface = surfaceOf[i] === 1 ? "top" : surfaceOf[i] === -1 ? "bottom" : "worst";
      let colour = null;
      if (wantStress) {
        if (pickedField || topField) {
          const field = pickedField || (
            cornerSurface === "top" ? topField
              : cornerSurface === "bottom" ? bottomField : worstField);
          // A cut piece vertex is not a mesh vertex, so the field is read
          // through the weights the cut recorded for it rather than a bare
          // index. A null component in the weighted sum keeps this white,
          // same as the old missing-index branch.
          const value = sampleScalar(field, weights[i]);
          colour = value === null ? white : STRESS_SCALE(value, stressMagnitude);
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
      if (!colour) colour = white;
      colours[3 * i] = colour.r;
      colours[3 * i + 1] = colour.g;
      colours[3 * i + 2] = colour.b;
      if (wantDeflection && d) {
        positions.setXYZ(i,
          base[3 * i] + d[0] * exaggeration,
          base[3 * i + 1] + d[1] * exaggeration,
          base[3 * i + 2] + d[2] * exaggeration);
      } else {
        positions.setXYZ(i, base[3 * i], base[3 * i + 1], base[3 * i + 2]);
      }
    }
    positions.needsUpdate = true;
    segment.geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    segment.geometry.computeVertexNormals();
    // Off the heatmaps, the piece goes back to the material it was built
    // with, tint and all: pieceMaterial recomputes it from the key rather
    // than handing back a bare registry clone, which used to discard the
    // per casting tint before the first frame was ever drawn.
    const previous = segment.material;
    segment.material = (wantStress || wantDeflection)
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
      Object.entries(bundle.loads), 0x66aaff);
    scene.add(state.objects.loadArrows);
  }
  if (state.layers.reactions && Object.keys(bundle.reactions).length) {
    // Real TNA reaction vectors from the contract, shipped in the bundle.
    state.objects.reactionArrows = arrowField(
      Object.entries(bundle.reactions), 0x66dd77);
    scene.add(state.objects.reactionArrows);
  }
}

function arrowField(entries, colour) {
  // One LineSegments for every shaft plus one instanced cone set for heads:
  // two draw calls however many nodes there are. Arrows draw exactly along
  // the shipped vector: loads arrive pointing down, reactions as exported.
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
    const from = new THREE.Vector3(...at);
    const to = from.clone().addScaledVector(dir, length);
    positions.push(from.x, from.y, from.z, to.x, to.y, to.z);
    q.setFromUnitVectors(up, dir);
    m.compose(to, q, new THREE.Vector3(1, 1, 1));
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
  // placementStep, not dropSeconds: the HUD's stage line and the integrity
  // pulse both hang off this number, and reading the picture at half its
  // real rate had a finished sprayed vault quoting a stage still halfway
  // down the drop order and pulsing that stage's verdict over it.
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
  const lines = [state.bundle.export + "  (" + state.bundle.material + ", " +
    Math.round(state.bundle.size * 1000) + " mm target, " +
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
    const build = Math.max(0, state.timeline.t - state.timeline.inflateSeconds);
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

function showBanner(text) {
  const banner = document.getElementById("banner");
  banner.textContent = text;
  banner.classList.remove("hidden");
}

// ---------- data panel ----------
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
    const stats = tess.corner_residual_stats;
    const residualWhat = document.createElement("p");
    residualWhat.textContent = "corner normal residual, over " + stats.count
      + " corners: the sine of the angle between a corner's one stored "
      + "normal and the plane of the facet that does not own it, since a "
      + "corner belongs to two joints and one normal cannot lie in both";
    content.appendChild(residualWhat);
    const residualDistribution = document.createElement("p");
    residualDistribution.textContent = "median " + stats.median.toFixed(4)
      + ", mean " + stats.mean.toFixed(4) + ", p99 " + stats.p99.toFixed(4)
      + ", max " + stats.max.toFixed(4) + " (its own worst corner, in "
      + "course(s) " + stats.worst_corner_courses.join(", ") + "). The "
      + "median describes the cut; the max describes only its worst "
      + "corner, which clusters with the rest of the tail in the rim course, "
      + "where the cut follows the mesh's own irregular boundary rather "
      + "than a straight chord.";
    content.appendChild(residualDistribution);
    const residualCounts = document.createElement("p");
    residualCounts.textContent = "corners over threshold: " + stats.over.map(
      function (entry) {
        return entry.count + " over " + entry.threshold;
      }
    ).join(", ");
    content.appendChild(residualCounts);

    const clampedLine = document.createElement("p");
    clampedLine.textContent = tess.clamped_points + " cap point(s) clamped to the "
      + "nearest render mesh face, " + tess.missing_planes
      + " boundary facet(s) with no joint plane to project onto";
    content.appendChild(clampedLine);

    const coverage = tess.report;
    const coverageLine = document.createElement("p");
    coverageLine.textContent = "coverage: " + coverage.orphan_faces.length
      + " orphan face(s), " + coverage.double_faces.length + " double face(s), "
      + coverage.open_facets.length + " open facet(s), " + coverage.slivers.length
      + " sliver(s), " + coverage.coverage_holes.length + " coverage hole(s), "
      + coverage.broken_boundary.length + " broken boundary entrie(s)";
    content.appendChild(coverageLine);

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

// Changing the material sets the pattern to that material's own default
// (concrete-sprayed's is monolithic-bands, everything else's is
// bonded-courses) and writes the material's honesty note, if it has one,
// into pattern-note. Tile and stone are the only materials with a note
// today: their intended patterns (Guastavino herringbone, the Armadillo
// dual) are not built, so the note says which wave they arrive in rather
// than let the pattern control claim one is drawing while another is.
function updatePatternForMaterial(material) {
  const pattern = state.patternDefaults[material] || state.pattern;
  state.pattern = pattern;
  document.getElementById("pattern-select").value = pattern;
  document.getElementById("pattern-note").textContent = state.patternNotes[material] || "";
}

async function loadStudy(exportName) {
  const material = document.getElementById("material-select").value;
  const url = "/api/studies/" + encodeURIComponent(exportName) +
    "/bundle?material=" + material + "&pattern=" + encodeURIComponent(state.pattern) +
    "&size=" + state.size + "&thickness=" + state.thickness;
  try {
    buildScene(await fetchJson(url));
  } catch (error) {
    showBanner("Failed to load study: " + error.message);
  }
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
    showBanner("Server not reachable: " + error.message);
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
    input.value = "";
    // M2 fix: select and load the export that was just imported, instead
    // of leaving boot() to fall back to studies[0].
    await boot(contractPrefix);
  } catch (error) {
    status.textContent = "import failed: " + error.message;
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
    input.value = "";
    const payload = await fetchJson("/api/studies");
    state.studies = payload.studies;
    await reloadColumns(payload.columns);
  } catch (error) {
    status.textContent = "import failed: " + error.message;
  }
}

// ---------- UI wiring ----------
document.getElementById("study-select").addEventListener("change", (e) => loadStudy(e.target.value));
document.getElementById("material-select").addEventListener("change", (e) => {
  updatePatternForMaterial(e.target.value);
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
});
document.getElementById("pattern-select").addEventListener("change", (e) => {
  state.pattern = e.target.value;
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
});
// Exactly the thickness slider's shape, and for the same reason: the piece
// size is a property of the BUNDLE, not of the client. "input" only moves
// the live label, "change" (drag release) commits the value and asks the
// server for a bundle whose pieces are cut at that size. Re-cutting
// client-side while the drawn pieces stay at the old size is what used to
// orphan piece keys and stop the render loop.
document.getElementById("size-slider").addEventListener("input", (e) => {
  document.getElementById("size-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("size-slider").addEventListener("change", (e) => {
  state.size = +e.target.value;
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
});
document.getElementById("thickness-input").addEventListener("input", (e) => {
  document.getElementById("thickness-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("thickness-input").addEventListener("change", (e) => {
  state.thickness = +e.target.value;
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
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
for (const id of ["sun-azimuth", "sun-elevation", "background-tone"]) {
  document.getElementById(id).addEventListener("input", applyEnvironment);
}
document.getElementById("exaggeration").addEventListener("input", () => recolourSegments());
document.getElementById("stress-surface").addEventListener("change", () => recolourSegments());
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
      status.textContent = run.state + " (stage " + run.stage + "/" + run.of + ") " + run.message;
      if (run.state === "done") {
        clearInterval(poll);
        applyRunParamsToControls(params);
        await loadStudy(exportName);
      }
      if (run.state === "failed") clearInterval(poll);
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
      }),
    });
    const body = await response.json();
    if (response.status === 409) {
      status.textContent = "watching the live run";
      watchRun(body.run, exportName, status, params);
      return;
    }
    watchRun(body.run, exportName, status, params);
  } catch (error) {
    status.textContent = "run failed to start: " + error.message;
  }
}

// ---------- placement timeline ----------
const DROP_HEIGHT = 12, STRIKE_SECONDS = 2;

function easeOutCubic(u) { return 1 - Math.pow(1 - u, 3); }

// How far apart two castings start, derived in exactly one place. Three
// clocks read the drop order and all three have to read it the same way:
// applySceneAtTime (what the picture does), timelineDuration (the scrubber
// and the recorded frame count) and currentStageIndex (the HUD's stage
// line and the integrity pulse). Sprayed concrete is not placed but built
// up, so its castings overlap by half a window; while only two of the
// three knew that, the picture ran at twice the rate of the readout.
function placementStep() {
  return sprayedMaterial() ? state.timeline.dropSeconds / 2 : state.timeline.dropSeconds;
}

function rebuildTimeline() {
  const dropSeconds = +document.getElementById("drop-speed").value;
  state.timeline = {
    playing: false, t: 0,
    dropSeconds,
    inflateSeconds: +document.getElementById("inflate-seconds").value,
    orbitSpeed: +document.getElementById("orbit-speed").value,
    orbitDistance: +document.getElementById("orbit-distance").value,
    autoSpin: true,
  };
  state.centre = sceneCentroid();
  // applyTimeline's autoSpin camera.lookAt(state.centre) and controls'
  // damped approach toward controls.target must aim at the same point, or
  // live orbit, drag-release and the recorded camera each settle on a
  // different seam. Sync once here, outside applyTimeline, so applyTimeline
  // stays a pure function of t.
  controls.target.copy(state.centre);
  controls.update();
  buildPieceMeshes();
  applyTimeline(0);
  recolourSegments();
  scrubber.value = 0;
}

// How many castings drop, which is the number of PIECES and not the number
// of cells: a cell split into two patches ships two of them.
function placementCount() {
  return state.bundle && state.bundle.pieces ? state.bundle.pieces.length : 0;
}

function timelineDuration() {
  const count = placementCount();
  const step = placementStep();
  return state.timeline.inflateSeconds + count * step
    + state.timeline.dropSeconds + STRIKE_SECONDS;
}

function pieceTint(key) {
  // A deterministic lightness nudge per casting, so no two pieces look
  // identical and the same study always looks the same.
  const offset = segmentUVOffset(key);
  return (offset[0] % 1) * 0.06 - 0.03;
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
  const own = (materials[state.bundle.material] || materials.concrete).clone();
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
          positions.push(
            centre[0] + (p[0] - centre[0]) * shrink,
            centre[1] + (p[1] - centre[1]) * shrink,
            centre[2] + (p[2] - centre[2]) * shrink);
          weights.push(piece.sources[index % count]);
          surface.push(index < count ? 1 : -1);
        }
      }
    }
    const uvs = boxUVs(positions, centre, segmentUVOffset(piece.key));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.computeVertexNormals();
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
  const inflate = inflationFactor(t);
  applyInflation(inflate);
  // The timeline opens with the net inflating into form; everything after
  // it (drop, strike, pulse) runs on build time, which only starts once
  // inflation is complete.
  const build = Math.max(0, t - state.timeline.inflateSeconds);
  const dropSeconds = state.timeline.dropSeconds;
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
    // Sprayed concrete is not precast: pieces overlap by half a window so
    // the shell reads as continuous build up over the formwork rather than
    // as arrivals. placementStep owns that halving for every clock at once.
    const start = position * step;
    if (build < start) {
      segment.visible = false;
      continue;
    }
    const u = Math.min(1, (build - start) / dropSeconds);
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
  const buildEnd = placementCount() * step + dropSeconds;
  const strikeU = build <= buildEnd ? 0 : Math.min(1, (build - buildEnd) / STRIKE_SECONDS);
  const falsework = state.objects.falsework;
  falsework.visible = !!state.layers.falsework && strikeU < 1;
  // The falsework fades in with the inflation as well as out with the
  // strike, so it never appears before the net has any form to support.
  falsework.material.opacity = 0.3 * inflate * (1 - strikeU);
  falsework.position.z = -0.02 - 1.5 * strikeU;
  // The strike takes the thrust network with it: wires and nodes fade,
  // drop and vanish on the same clock, and scrubbing back restores them
  // because everything here is computed from t (by way of build).
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (!object) continue;
    object.visible = !!state.layers.wires && strikeU < 1;
    object.material.opacity = 1 - strikeU;
    object.position.z = -1.5 * strikeU;
  }
  applyPulse(build);
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
  const target = "study-" + state.bundle.slug;
  const fps = 60;
  const total = Math.ceil(timelineDuration() * fps);
  status.textContent = "recording " + total + " frames at 1080p (a few MB each on disk)";
  const wasPlaying = state.timeline.playing;
  state.timeline.playing = false;
  renderer.setSize(1920, 1080, false);
  camera.aspect = 1920 / 1080;
  camera.updateProjectionMatrix();
  state.recording = true;   // resize() must skip while this is set
  try {
    for (let frameIndex = 0; frameIndex < total; frameIndex++) {
      applyTimeline(frameIndex / fps);
      renderer.render(scene, camera);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      const response = await fetch(
        "/api/frames/" + target + "?frame=" + (frameIndex + 1),
        { method: "POST", body: blob });
      if (!response.ok) throw new Error("frame upload failed: " + response.status);
      if (frameIndex % 30 === 0) status.textContent = "frame " + frameIndex + " / " + total;
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
    state.recording = false;
    state.timeline.playing = wasPlaying;
  }
}
document.getElementById("record-button").addEventListener("click", recordAnimation);

// ---------- render loop ----------
function resize() {
  if (state.recording) return;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w || canvas.height !== h) {
    renderer.setSize(w, h, false);
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
document.getElementById("stop-button").addEventListener("click", () => {
  if (!state.timeline) return;
  state.timeline.playing = false;
  applyTimeline(0);
  scrubber.value = 0;
  document.getElementById("play-button").textContent = "Play";
  updateHud();
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
for (const [id, prop] of [["drop-speed", "dropSeconds"], ["inflate-seconds", "inflateSeconds"], ["orbit-speed", "orbitSpeed"], ["orbit-distance", "orbitDistance"]]) {
  document.getElementById(id).addEventListener("input", (e) => {
    if (state.timeline) { state.timeline[prop] = +e.target.value; applyTimeline(state.timeline.t); }
  });
}

let lastTime = performance.now();
let playingFrameCount = 0;
function frame(now) {
  const delta = Math.min(0.1, (now - lastTime) / 1000);
  lastTime = now;
  resize();
  if (state.timeline && state.timeline.playing) {
    applyTimeline(Math.min(state.timeline.t + delta, timelineDuration()));
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
  if (state.timeline && document.activeElement !== scrubber) {
    scrubber.value = Math.round(1000 * state.timeline.t / timelineDuration());
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

boot();
requestAnimationFrame(frame);

export { state, buildScene, setLayer, applyCut, applyTimeline, timelineDuration, rebuildTimeline };
