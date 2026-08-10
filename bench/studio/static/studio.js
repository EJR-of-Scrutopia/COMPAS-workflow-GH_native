import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { segmentFaces, segmentKey } from "/static/binning.js";

// ---------- app state ----------
const state = {
  bundle: null,
  studies: [],
  layers: {},          // Task 14 registers layer objects here
  objects: {},         // shell, wires, nodes, falsework, columns, ground
  timeline: null,      // Task 13
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

  const shell = new THREE.Mesh(meshGeometry(bundle.render_mesh), materials[bundle.material] || materials.concrete);
  shell.castShadow = shell.receiveShadow = true;
  state.objects.shell = shell;
  scene.add(shell);

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
}

// ---------- layers (Task 14 fills this registry) ----------
function setLayer(name, on) {
  state.layers[name] = on;
  updateHud();
}

function updateHud() {
  const hud = document.getElementById("hud");
  if (!state.bundle) { hud.textContent = ""; return; }
  const v = state.bundle.verification;
  const lines = [state.bundle.export + "  (" + state.bundle.material + ", " + state.bundle.rings + " rings)"];
  if (v && v.stress) {
    lines.push("peak compression " + (v.stress.peak_compression / 1e6).toFixed(2) + " MPa, utilisation " + (100 * v.stress.utilisation).toFixed(1) + "%");
    lines.push("peak deflection " + (v.displacement.peak_magnitude * 1000).toFixed(2) + " mm");
  } else {
    lines.push("no verification run embedded yet");
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

// ---------- render loop (Task 13 adds timeline stepping here) ----------
function resize() {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== w || canvas.height !== h) {
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}

function frame() {
  resize();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

boot();
requestAnimationFrame(frame);

export { state, buildScene, setLayer, rebinSegments };
