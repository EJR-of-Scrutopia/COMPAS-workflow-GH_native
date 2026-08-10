import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { segmentFaces, segmentKey } from "/static/binning.js";

// ---------- app state ----------
const state = {
  bundle: null,
  studies: [],
  layers: { wires: true, overlays: true },  // Task 14: layer visibility toggles
  objects: {},         // shell, wires, nodes, falsework, columns, ground, loadArrows, reactionArrows
  timeline: null,      // Task 13
  userDragging: false, // Task 13
  centre: null,        // Task 13: cached orbit centroid, set in rebuildTimeline
  rings: 8,
  segments: null,      // Task 11
  segmentIndex: null,  // Task 11
};

const canvas = document.getElementById("view");
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
    roughness: 0.95, metalness: 0.0, transparent: true, opacity: 1.0,
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
  const wireRadius = 0.02, nodeRadius = 0.045;
  const cylinder = new THREE.CylinderGeometry(wireRadius, wireRadius, 1, 8, 1, true);
  cylinder.translate(0, 0.5, 0);
  const wires = new THREE.InstancedMesh(cylinder, materials.steel.clone(), edges.length);
  const up = new THREE.Vector3(0, 1, 0);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  edges.forEach(([u, v], i) => {
    const a = new THREE.Vector3(...vertices[u]);
    const b = new THREE.Vector3(...vertices[v]);
    const d = b.clone().sub(a);
    q.setFromUnitVectors(up, d.clone().normalize());
    s.set(1, d.length(), 1);
    m.compose(a, q, s);
    wires.setMatrixAt(i, m);
  });
  const sphere = new THREE.SphereGeometry(nodeRadius, 12, 8);
  const nodes = new THREE.InstancedMesh(sphere, materials.steel.clone(), vertices.length);
  vertices.forEach((v, i) => {
    m.makeTranslation(v[0], v[1], v[2]);
    nodes.setMatrixAt(i, m);
  });
  wires.castShadow = nodes.castShadow = true;
  return { wires, nodes };
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
];

function finalStage() {
  const staging = state.bundle && state.bundle.staging;
  if (!staging || !staging.stages || !staging.stages.length) return null;
  const last = staging.stages[staging.stages.length - 1];
  return last.struck_now && last.struck_now.converged ? last.struck_now : null;
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
  if (name === "wires") {
    state.objects.wires.visible = on;
    state.objects.nodes.visible = on;
  }
  if (name === "loads" || name === "reactions") updateVectorLayers();
  if (name === "stress" || name === "deflection") recolourSegments();
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
  // Diverging palette: compression blue, zero pale, tension red.
  const compression = new THREE.Color(0x2255cc), zero = new THREE.Color(0xf2efe8),
        tension = new THREE.Color(0xcc2211);
  return (value, magnitude) => {
    const u = Math.max(-1, Math.min(1, value / magnitude));
    return u < 0 ? zero.clone().lerp(compression, -u) : zero.clone().lerp(tension, u);
  };
})();

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
  // peak magnitude, the same way the stress fallback above does.
  const deflectionPeakOnly = !stage && wantDeflection && v && v.displacement
    ? Math.max(v.displacement.peak_magnitude, 1e-9) : null;
  let deflectionMax = 1e-9;
  if (displacement) for (const d of displacement) {
    deflectionMax = Math.max(deflectionMax, Math.hypot(d[0], d[1], d[2]));
  }
  for (const segment of state.objects.shell.children) {
    const faces = segment.userData.faces;   // render-face indices, set in buildSegmentMeshes
    const positions = segment.geometry.getAttribute("position");
    const colours = new Float32Array(positions.count * 3);
    let corner = 0;
    for (const faceIndex of faces) {
      const parent = mesh.parent_face[faceIndex];
      const quad = mesh.faces[faceIndex];
      const stressPair = stage && stage.stresses[String(parent)];
      const faceColour = wantStress
        ? STRESS_SCALE(stressValue(stressPair, surface, stressMagnitude), stressMagnitude)
        : (deflectionPeakOnly ? STRESS_SCALE(0.3 * deflectionPeakOnly, deflectionPeakOnly) : null);
      for (const cornerIndex of [0, 1, 2, 0, 2, 3]) {
        const vertexId = quad[cornerIndex];
        const base = mesh.vertices[vertexId];
        let colour = faceColour;
        if (!colour && wantDeflection && displacement) {
          const d = displacement[vertexId];
          colour = STRESS_SCALE(Math.hypot(d[0], d[1], d[2]), deflectionMax);
        }
        if (!colour) colour = new THREE.Color(0xffffff);
        colours[3 * corner] = colour.r; colours[3 * corner + 1] = colour.g; colours[3 * corner + 2] = colour.b;
        if (wantDeflection && displacement) {
          const d = displacement[vertexId];
          positions.setXYZ(corner, base[0] + d[0] * exaggeration,
            base[1] + d[1] * exaggeration, base[2] + d[2] * exaggeration);
        } else {
          positions.setXYZ(corner, base[0], base[1], base[2]);
        }
        corner += 1;
      }
    }
    positions.needsUpdate = true;
    segment.geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    segment.geometry.computeVertexNormals();
    segment.material = (wantStress || wantDeflection)
      ? new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.85, side: THREE.DoubleSide })
      : (materials[state.bundle.material] || materials.concrete).clone();
  }
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
      Object.entries(bundle.loads), 0x66aaff, -1);
    scene.add(state.objects.loadArrows);
  }
  if (state.layers.reactions && Object.keys(bundle.reactions).length) {
    // Real TNA reaction vectors from the contract, shipped in the bundle.
    state.objects.reactionArrows = arrowField(
      Object.entries(bundle.reactions), 0x66dd77, 1);
    scene.add(state.objects.reactionArrows);
  }
}

function arrowField(entries, colour, direction) {
  // One LineSegments for every shaft plus one instanced cone set for heads:
  // two draw calls however many nodes there are.
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
    const dir = v.lengthSq() ? v.clone().normalize() : new THREE.Vector3(0, 0, direction);
    const from = new THREE.Vector3(...at);
    const to = from.clone().addScaledVector(dir, length * direction);
    positions.push(from.x, from.y, from.z, to.x, to.y, to.z);
    q.setFromUnitVectors(up, dir.clone().multiplyScalar(direction));
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
  const good = stage.struck_now && stage.struck_now.converged;
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
  const lines = [state.bundle.export + "  (" + state.bundle.material + ", " + state.bundle.rings + " rings)"];
  if (v && v.stress) {
    lines.push("peak compression " + (v.stress.peak_compression / 1e6).toFixed(2) + " MPa, utilisation " + (100 * v.stress.utilisation).toFixed(1) + "%");
    lines.push("peak deflection " + (v.displacement.peak_magnitude * 1000).toFixed(2) + " mm");
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
  }
  hud.textContent = lines.join("\n");
}

function showBanner(text) {
  const banner = document.getElementById("banner");
  banner.textContent = text;
  banner.classList.remove("hidden");
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
    "/bundle?material=" + material + "&rings=" + state.rings;
  try {
    buildScene(await fetchJson(url));
  } catch (error) {
    showBanner("Failed to load study: " + error.message);
  }
}

async function boot() {
  applyEnvironment();
  try {
    const payload = await fetchJson("/api/studies");
    state.studies = payload.studies;
    const select = document.getElementById("study-select");
    select.innerHTML = "";
    for (const study of payload.studies) {
      const option = document.createElement("option");
      option.value = study.export;
      option.textContent = study.export + (study.has_verification ? " (verified)" : "");
      select.appendChild(option);
    }
    if (payload.studies.length) await loadStudy(payload.studies[0].export);
    if (payload.columns.length) {
      state.objects.columns = await loadColumns(payload.columns);
      scene.add(state.objects.columns);
    }
  } catch (error) {
    showBanner("Server not reachable: " + error.message);
  }
}

// ---------- UI wiring ----------
document.getElementById("study-select").addEventListener("change", (e) => loadStudy(e.target.value));
document.getElementById("material-select").addEventListener("change", () => {
  const select = document.getElementById("study-select");
  if (select.value) loadStudy(select.value);
});
document.getElementById("rings-slider").addEventListener("input", (e) => rebinSegments(+e.target.value));
for (const id of ["sun-azimuth", "sun-elevation", "background-tone"]) {
  document.getElementById(id).addEventListener("input", applyEnvironment);
}
document.getElementById("exaggeration").addEventListener("input", () => recolourSegments());
document.getElementById("stress-surface").addEventListener("change", () => recolourSegments());
document.getElementById("data-button").addEventListener("click", () => {
  const panel = document.getElementById("data-panel");
  document.getElementById("data-content").textContent =
    JSON.stringify(state.bundle ? state.bundle.verification : null, null, 2);
  panel.classList.toggle("hidden");
});
document.getElementById("data-close").addEventListener("click", () =>
  document.getElementById("data-panel").classList.add("hidden"));
document.getElementById("run-button").addEventListener("click", startRun);

async function startRun() {
  const status = document.getElementById("run-status");
  const exportName = document.getElementById("study-select").value;
  const material = document.getElementById("material-select").value;
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ export: exportName, material, rings: state.rings }),
    });
    const body = await response.json();
    if (response.status === 409) { status.textContent = "a run is already live"; return; }
    const poll = setInterval(async () => {
      const run = await fetchJson("/api/runs/" + body.run);
      status.textContent = run.state + " (stage " + run.stage + "/" + run.of + ") " + run.message;
      if (run.state === "done") { clearInterval(poll); await loadStudy(exportName); }
      if (run.state === "failed") clearInterval(poll);
    }, 1000);
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
  buildSegmentMeshes();
  applyTimeline(0);
  recolourSegments();
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
  const byKey = new Map();
  mesh.parent_face.forEach((parent, faceIndex) => {
    const key = segmentKey(assignment[parent][0], assignment[parent][1]);
    if (!byKey.has(key)) byKey.set(key, { faces: [], indices: [] });
    const bucket = byKey.get(key);
    bucket.faces.push(mesh.faces[faceIndex]);
    bucket.indices.push(faceIndex);
  });
  const material = materials[state.bundle.material] || materials.concrete;
  for (const [key, { faces, indices }] of byKey) {
    const positions = [], uvs = [];
    for (const face of faces) {
      const quad = face.map((i) => mesh.vertices[i]);
      for (const corner of [quad[0], quad[1], quad[2], quad[0], quad[2], quad[3]]) {
        positions.push(corner[0], corner[1], corner[2]);
        uvs.push(corner[0] * 0.15, corner[1] * 0.15);
      }
    }
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
    segment.userData.faces = indices;
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

function applyTimeline(t) {
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
  const falsework = state.objects.falsework;
  if (t <= buildEnd) {
    falsework.visible = true;
    falsework.material.opacity = 1;
    falsework.position.z = -0.02;
  } else {
    const u = Math.min(1, (t - buildEnd) / STRIKE_SECONDS);
    falsework.material.opacity = 1 - u;
    falsework.position.z = -0.02 - 1.5 * u;
    falsework.visible = u < 1;
  }
  if (state.timeline.autoSpin && !state.userDragging) {
    const centre = state.centre;
    const angle = state.timeline.orbitSpeed * t;
    const r = state.timeline.orbitDistance;
    camera.position.set(centre.x + r * Math.cos(angle), centre.y + r * Math.sin(angle), 0.55 * r);
    camera.lookAt(centre);
  }
  applyPulse();
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
for (const [id, prop] of [["drop-speed", "dropSeconds"], ["orbit-speed", "orbitSpeed"], ["orbit-distance", "orbitDistance"]]) {
  document.getElementById(id).addEventListener("input", (e) => {
    if (state.timeline) { state.timeline[prop] = +e.target.value; applyTimeline(state.timeline.t); }
  });
}

let lastTime = performance.now();
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
  }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

boot();
requestAnimationFrame(frame);

export { state, buildScene, setLayer, rebinSegments, applyTimeline, timelineDuration, rebuildTimeline };
