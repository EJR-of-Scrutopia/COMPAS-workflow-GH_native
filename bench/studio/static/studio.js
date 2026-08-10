import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { segmentFaces, segmentKey } from "/static/binning.js";
import {
  vertexNormals, extrudeSegment, boxUVs, segmentUVOffset,
  smoothStressField, interpolateScalarField,
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
  rings: 8,
  thickness: 0.2,
  segments: null,      // Task 11
  segmentIndex: null,  // Task 11
  nodeRadius: 0.03,    // Task 6
  wireRadius: 0.02,    // Task 6
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
    color: 0xc4c0b6, side: THREE.DoubleSide,
    map: noiseTexture(256, 205, 14),
    roughness: 0.9, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  "concrete-c50": new THREE.MeshPhysicalMaterial({
    color: 0xbdbec0, side: THREE.DoubleSide,  // Cooler grey for higher-strength concrete
    map: noiseTexture(256, 205, 14),
    roughness: 0.9, roughnessMap: noiseTexture(256, 215, 40),
    metalness: 0.0,
  }),
  "concrete-sprayed": new THREE.MeshPhysicalMaterial({
    color: 0xc9c3b6, side: THREE.DoubleSide,
    map: noiseTexture(256, 195, 34),
    roughness: 0.97, roughnessMap: noiseTexture(256, 225, 30),
    metalness: 0.0,
  }),
  timber: new THREE.MeshPhysicalMaterial({
    color: 0xffffff, side: THREE.DoubleSide,
    map: grainTexture(512),
    roughness: 0.55, metalness: 0.0, sheen: 0.15, sheenColor: 0xd9b98a,
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

function rebuildWiresAndNodes() {
  if (!state.bundle) return;
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
    }
  }
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

  rebinSegments(state.rings);
  buildLayerToggles();
  updateVectorLayers();
  updateHud();
  updateCraBadge();
}

// ---------- segmentation (Task 11 replaces the body of rebinSegments) ----------
function faceCentroids(meshData) {
  return meshData.faces.map((face) => {
    let x = 0, y = 0, z = 0;
    for (const i of face) { x += meshData.vertices[i][0]; y += meshData.vertices[i][1]; z += meshData.vertices[i][2]; }
    const n = face.length;
    return [x / n, y / n, z / n];
  });
}

function rebinSegments(rings) {
  state.rings = rings;
  document.getElementById("rings-value").textContent = rings;
  if (!state.bundle) return;
  const centroids = faceCentroids(state.bundle.analysis_mesh);
  const local = segmentFaces(centroids, rings);
  if (rings === state.bundle.segments.rings) {
    // Python is canonical: verify the mirror, then defer to the shipped copy.
    const shipped = state.bundle.segments;
    const agrees =
      JSON.stringify(local.assignment) === JSON.stringify(shipped.assignment) &&
      JSON.stringify(local.wedge_counts) === JSON.stringify(shipped.wedge_counts);
    if (!agrees) {
      showBanner("Segmentation mirror disagrees with Python; showing the Python binning. Fix binning.js before trusting the slider.");
    }
    state.segments = shipped;
  } else {
    state.segments = local;
  }
  state.segmentIndex = new Map();
  state.segments.order.forEach(([r, w], position) => {
    state.segmentIndex.set(segmentKey(r, w), { faces: [], order: position });
  });
  state.segments.assignment.forEach((pair, face) => {
    const entry = state.segmentIndex.get(segmentKey(pair[0], pair[1]));
    if (entry) entry.faces.push(face);
  });
  document.getElementById("segment-count").textContent = state.segments.order.length;
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

const FRICTION_PROVENANCE = {
  "0.6": "mu 0.60: EN 1992-1-1 clause 6.2.5, smooth precast concrete joint",
  "0.4": "mu 0.40: literature value for dry timber on timber contact (Eurocode 5 gives none)",
};

// The badge and the HUD are what a user reads during playback; the Data
// panel, which carries the measured figures in full, is a separate view
// they may never open. So the same caveat rides along here, short enough
// to sit on one line: the analysis surface is up to 2.389 m from the
// drawn one, twenty times the shell's own half thickness, and that is a
// larger error than the volume gap the disclosure used to lead with.
const FACETED_CAVEAT = "on a faceted model up to 2.4 m off the drawn surface";

function updateCraBadge() {
  const badge = document.getElementById("cra-badge");
  if (!state.bundle) { badge.classList.add("hidden"); return; }
  badge.classList.remove("hidden", "cra-stands", "cra-fails", "cra-unknown");
  const verdict = craVerdict();
  if (!verdict) {
    badge.classList.add("cra-unknown");
    badge.textContent = "CRA: no run yet";
  } else if (verdict.stands === true) {
    badge.classList.add("cra-stands");
    badge.textContent = "CRA: stands (mu " + (+verdict.mu).toFixed(2) + ")";
  } else if (verdict.stands === false) {
    badge.classList.add("cra-fails");
    badge.textContent = "CRA: does not stand";
  } else {
    badge.classList.add("cra-unknown");
    badge.textContent = "CRA: not run (" + (verdict.message || verdict.status || "unknown") + ")";
  }
  if (verdict && (verdict.stands === true || verdict.stands === false)) {
    // Appended after the three-state branch above, so it rides on every
    // badge that makes a claim without touching which class or which
    // words that branch chose. A null verdict makes no claim about the
    // structure, so it needs no caveat about the model the claim would
    // have been made on, and its message is long enough already.
    badge.textContent += " " + FACETED_CAVEAT;
  }
  const skipped = state.bundle.staging && state.bundle.staging.cra_skipped;
  if (skipped && skipped.length) {
    badge.textContent += " (" + skipped.length + " piece(s) not modelled)";
  }
}

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
    const corners = segment.userData.corners;
    const base = segment.userData.basePositions;
    const positions = segment.geometry.getAttribute("position");
    const colours = new Float32Array(corners.length * 3);
    corners.forEach((corner, i) => {
      let colour = null;
      if (wantStress) {
        if (pickedField || topField) {
          const field = pickedField || (
            corner.surface === "top" ? topField
              : corner.surface === "bottom" ? bottomField : worstField);
          const value = field[corner.v];
          colour = value === null ? white : STRESS_SCALE(value, stressMagnitude);
        } else {
          // Verification peaks only: the flat honest tint, as before.
          colour = STRESS_SCALE(stressValue(null, surface, stressMagnitude), stressMagnitude);
        }
      } else if (deflectionPeakOnly) {
        colour = STRESS_SCALE(0.3 * deflectionPeakOnly, deflectionPeakOnly);
      }
      const d = displacement ? displacement[corner.v] : null;
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
    });
    positions.needsUpdate = true;
    segment.geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    segment.geometry.computeVertexNormals();
    segment.material = (wantStress || wantDeflection)
      ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })
      : (materials[state.bundle.material] || materials.concrete).clone();
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
function currentStageIndex() {
  // Which build stage the timeline is inside: stages are rings, and a ring's
  // segments occupy a contiguous run of the drop order.
  if (!state.bundle.staging || !state.timeline) return null;
  const stages = state.bundle.staging.stages;
  if (!stages || !stages.length) return null;
  const dropSeconds = state.timeline.dropSeconds;
  const placed = Math.floor(state.timeline.t / dropSeconds);
  let ringsDone = 0, count = 0;
  for (const [r] of state.segments.order) {
    count += 1;
    if (count > placed) break;
    ringsDone = Math.max(ringsDone, r + 1);
  }
  return Math.max(0, Math.min(stages.length - 1, ringsDone - 1));
}

function applyPulse() {
  if (!state.layers.pulse || !state.bundle || !state.objects.shell) return;
  const index = currentStageIndex();
  if (index === null) return;
  const stage = state.bundle.staging.stages[index];
  const cra = stage.cra;
  // Green now means BOTH lenses pass: the struck-now FEA solve converged
  // and the rigid-block verdict stands. A missing cra entry (old cache)
  // reads as not passing; the HUD's "CRA: not run" line explains the red.
  const good = !!(stage.struck_now && stage.struck_now.converged
    && cra && cra.stands === true);
  const tint = good ? 0x1a3a1a : 0x3a1a1a;
  const pulse = 0.5 + 0.5 * Math.sin(state.timeline.t * 4);
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
  const lines = [state.bundle.export + "  (" + state.bundle.material + ", " + state.bundle.rings + " rings)"];
  const thicknessMm = Math.round(provenanceThickness * 1000);
  let thicknessLine = "shell thickness " + thicknessMm + " mm";
  if (v && v.thickness && Math.abs(v.thickness - provenanceThickness) > 1e-9) {
    const verifiedMm = Math.round(v.thickness * 1000);
    thicknessLine += " (verified run used " + verifiedMm + " mm)";
  }
  lines.push(thicknessLine);
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
    const index = currentStageIndex();
    const stage = staging.stages[index === null ? staging.stages.length - 1 : index];
    lines.push("stage " + stage.stage + " of " + staging.stages.length);
    lines.push("formwork carries " + (stage.formwork_carries_newtons / 1000).toFixed(1) + " kN");
    const struck = stage.struck_now;
    lines.push(struck && struck.converged
      ? "struck now: stands (peak tension " + (struck.peak_tension / 1e6).toFixed(2) +
        " MPa, peak compression " + (struck.peak_compression / 1e6).toFixed(2) + " MPa)"
      : "struck now: no equilibrium found -- " + (struck && struck.message ? struck.message : "no solve result"));
    const cra = stage.cra;
    if (cra && cra.stands === true) {
      lines.push("CRA: stands, " + FACETED_CAVEAT);
    } else if (cra && cra.stands === false) {
      lines.push("CRA: does not stand, " + FACETED_CAVEAT);
    } else {
      lines.push("CRA: not run" + (cra && cra.message ? " (" + cra.message + ")" : ""));
    }
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

  // Render CRA section FIRST, before verification early-out, so it appears
  // even on staged-but-unverified studies.
  const craHeading = document.createElement("h3");
  craHeading.textContent = "CRA rigid-block verdict";
  content.appendChild(craHeading);
  const verdict = craVerdict();
  if (!verdict) {
    const none = document.createElement("p");
    none.textContent = "no CRA run yet: run a staged analysis";
    content.appendChild(none);
  } else {
    const line = document.createElement("p");
    line.textContent = verdict.stands === true
      ? "stands as rigid blocks under friction, self-weight only"
      : verdict.stands === false
        ? "does not stand as rigid blocks (" + verdict.status + ")"
        : "not run: " + (verdict.message || verdict.status);
    content.appendChild(line);
    const mu = document.createElement("p");
    mu.textContent = FRICTION_PROVENANCE[String(verdict.mu)]
      || ("mu " + verdict.mu);
    content.appendChild(mu);
    const counts = document.createElement("p");
    counts.textContent = verdict.blocks + " blocks, "
      + verdict.interfaces + " contact interfaces";
    content.appendChild(counts);
    const faceted = document.createElement("p");
    faceted.textContent = "the verdict is computed on a faceted model, not on "
      + "the surface drawn here. Position is the larger error: replacing each "
      + "curved piece with planar joints moves the analysis surface up to "
      + "2.389 m from the drawn one at 2 rings and 1.964 m at 4 rings, "
      + "against a shell half thickness of 0.1 m, so the solver weighs blocks "
      + "sitting metres from where they are shown. Volume is the smaller one: "
      + "per piece it runs 51.3 to 17.3 percent light at 2 rings, and 63.7 "
      + "percent light to 12.9 percent heavy at 4 rings, where 5 of 21 pieces "
      + "come out heavier than drawn rather than lighter. A higher "
      + "ring count improves the position error and the total volume (29.5 "
      + "percent light at 2 rings, 17.5 at 4) because finer segmentation "
      + "makes each joint flatter to begin with, but it widens the spread "
      + "between individual pieces (measured on the Trial 2 export, "
      + "docs/BENCH.md)";
    content.appendChild(faceted);
    const skipped = state.bundle.staging && state.bundle.staging.cra_skipped;
    if (skipped && skipped.length) {
      const missing = document.createElement("p");
      missing.textContent = skipped.length + " piece(s) could not be modelled "
        + "as a voussoir and are absent from the rigid-block model, so this "
        + "verdict describes less than the whole vault: "
        + skipped.map(function (entry) {
            return "ring " + entry.ring + " wedge " + entry.wedge
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

async function loadStudy(exportName) {
  const material = document.getElementById("material-select").value;
  const url = "/api/studies/" + encodeURIComponent(exportName) +
    "/bundle?material=" + material + "&rings=" + state.rings + "&thickness=" + state.thickness;
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
document.getElementById("material-select").addEventListener("change", () => {
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
});
document.getElementById("rings-slider").addEventListener("input", (e) => rebinSegments(+e.target.value));
document.getElementById("thickness-input").addEventListener("input", (e) => {
  document.getElementById("thickness-value").textContent = Math.round(+e.target.value * 1000);
});
document.getElementById("thickness-input").addEventListener("change", (e) => {
  state.thickness = +e.target.value;
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
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

// M5 fix: reload with the material/rings/thickness the run actually solved
// with, not whatever the controls read when the run happens to finish. A
// slider nudge mid-run must not orphan the run's own result -- it must show
// up, and the controls must be set back to match so the display stays
// honest about what's on screen.
function applyRunParamsToControls({ material, rings, thickness }) {
  document.getElementById("material-select").value = material;
  document.getElementById("rings-slider").value = rings;
  document.getElementById("rings-value").textContent = rings;
  document.getElementById("thickness-input").value = thickness;
  document.getElementById("thickness-value").textContent = Math.round(thickness * 1000);
  state.rings = rings;
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
  const params = { material, rings: state.rings, thickness: state.thickness };
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ export: exportName, material, rings: params.rings, thickness: params.thickness }),
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

function rebuildTimeline() {
  const dropSeconds = +document.getElementById("drop-speed").value;
  state.timeline = {
    playing: false, t: 0,
    dropSeconds,
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
  buildSegmentMeshes();
  applyTimeline(0);
  recolourSegments();
  scrubber.value = 0;
}

function timelineDuration() {
  const count = state.segments ? state.segments.order.length : 0;
  return count * state.timeline.dropSeconds + state.timeline.dropSeconds + STRIKE_SECONDS;
}

function buildSegmentMeshes() {
  if (state.objects.shell) scene.remove(state.objects.shell);
  const group = new THREE.Group();
  const mesh = state.bundle.render_mesh;
  const assignment = state.segments.assignment;
  // The thickness on screen is the thickness the bundle was solved at,
  // never the live slider value, which can drift while a bundle loads.
  const thickness = state.bundle.provenance.thickness;
  const normals = vertexNormals(mesh.vertices, mesh.faces);
  const byKey = new Map();
  mesh.parent_face.forEach((parent, faceIndex) => {
    const key = segmentKey(assignment[parent][0], assignment[parent][1]);
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(faceIndex);
  });
  const material = materials[state.bundle.material] || materials.concrete;
  for (const [key, faceIndices] of byKey) {
    const { positions, corners } = extrudeSegment(
      mesh.vertices, mesh.faces, faceIndices, normals, thickness);
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < positions.length; i += 3) {
      cx += positions[i]; cy += positions[i + 1]; cz += positions[i + 2];
    }
    const cornerCount = positions.length / 3;
    const centroid = [cx / cornerCount, cy / cornerCount, cz / cornerCount];
    const uvs = boxUVs(positions, centroid, segmentUVOffset(key));
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(uvs), 2));
    geometry.computeVertexNormals();
    // Each segment owns its own material instance (a clone of the shared
    // registry entry) so the integrity pulse can write emissive per segment
    // without tinting other segments, the falsework, the columns, or the
    // canonical materials.concrete/materials.timber objects other code
    // reads from. recolourSegments keeps this invariant on every rebuild.
    const segment = new THREE.Mesh(geometry, material.clone());
    segment.castShadow = segment.receiveShadow = true;
    segment.userData.key = key;
    segment.userData.faces = faceIndices;
    segment.userData.corners = corners;
    segment.userData.basePositions = new Float32Array(positions);
    group.add(segment);
  }
  state.objects.shell = group;
  scene.add(group);
}

function sceneCentroid() {
  const vertices = state.bundle.analysis_mesh.vertices;
  let x = 0, y = 0;
  for (const v of vertices) { x += v[0]; y += v[1]; }
  return new THREE.Vector3(x / vertices.length, y / vertices.length, 2);
}

// Everything that depends on the build/strike clock but not on the camera:
// segment drop/visibility, falsework, wires/nodes strike state, and the
// integrity pulse. setLayer's wires/falsework toggle and rebuildWiresAndNodes
// both need to recompute this scene state after the objects they touch
// change, but neither one should be allowed to move the camera -- only
// applyTimeline's own scrubber/play/record callers get to do that. Kept
// pure in t, same as applyTimeline: no clock reads here either.
function applySceneAtTime(t) {
  state.timeline.t = t;
  const dropSeconds = state.timeline.dropSeconds;
  for (const segment of state.objects.shell.children) {
    const position = state.segmentIndex.get(segment.userData.key).order;
    const start = position * dropSeconds;
    if (t < start) {
      segment.visible = false;
    } else if (t < start + dropSeconds) {
      const u = (t - start) / dropSeconds;
      segment.visible = true;
      segment.position.z = DROP_HEIGHT * (1 - easeOutCubic(u));
    } else {
      segment.visible = true;
      segment.position.z = 0;
    }
  }
  const buildEnd = state.segments.order.length * dropSeconds + dropSeconds;
  const strikeU = t <= buildEnd ? 0 : Math.min(1, (t - buildEnd) / STRIKE_SECONDS);
  const falsework = state.objects.falsework;
  falsework.visible = !!state.layers.falsework && strikeU < 1;
  falsework.material.opacity = 0.3 * (1 - strikeU);
  falsework.position.z = -0.02 - 1.5 * strikeU;
  // The strike takes the thrust network with it: wires and nodes fade,
  // drop and vanish on the same clock, and scrubbing back restores them
  // because everything here is computed from t.
  for (const key of ["wires", "nodes"]) {
    const object = state.objects[key];
    if (!object) continue;
    object.visible = !!state.layers.wires && strikeU < 1;
    object.material.opacity = 1 - strikeU;
    object.position.z = -1.5 * strikeU;
  }
  applyPulse();
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
for (const [id, prop] of [["drop-speed", "dropSeconds"], ["orbit-speed", "orbitSpeed"], ["orbit-distance", "orbitDistance"]]) {
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

export { state, buildScene, setLayer, rebinSegments, applyTimeline, timelineDuration, rebuildTimeline };
