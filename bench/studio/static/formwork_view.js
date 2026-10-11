// The Formwork tab's drawing (spec 2026-10-10 formwork tab, section 8): its
// own objects in one group, built from the capture document, moved from the
// captures, removed when the tab closes. The studio's objects are not reused.
// THREE is handed in rather than imported, so the drawing runs under node in
// the tests as it does in the page.

import {
  bandColour, colourOf, holdForce, holdRod, jackedAt, memberColour, placedFaces, targetPoint,
} from "./formwork_model.js";

const WIRE_STUB_M = 0.3;        // each rim wire drawn 300 mm along the way it runs in
const MARK_M = 0.05;            // an anchor's mark, and twice a ground contact's
const HEAD_M = 0.08;            // a head's mark
const PROP_M = 0.03;            // a hold's rod, this thick (spec 2026-10-10 formwork holds)
const RING_M = 0.12;            // the ring round a weakest part (spec 2026-10-11 section 5.3)
const RING_TUBE_M = 0.015;
// the Tendons chip (spec 2026-10-11 across tendons, section 6): each tendon
// drawn this far above its net, and a reel this big this far out along it from
// its column head, so the reels of a head's two sides stand apart
const TENDON_PROUD_M = 0.02;
const REEL_M = 0.04;
const REEL_WIDTH_M = 0.03;
const REEL_ALONG_M = 0.06;
const TENDON_PLAIN = [1, 1, 1];
const OVER = [0xc2 / 255, 0x49 / 255, 0x36 / 255];
const CLOSE = [0xc9 / 255, 0x9a / 255, 0x2e / 255];
const DESIGN_FACE = 0x9cc4ff;   // Compare's design: pale blue formwork, seen through
const DESIGN_FACE_OPACITY = 0.25;
const PLAIN = [0.86, 0.86, 0.86];
const TREE_PLAIN = [0.72, 0.74, 0.78];
const HEAD_TOUCHING = [0x3f / 255, 0x9e / 255, 0x57 / 255];
const HEAD_CLEAR = [0x9a / 255, 0xa4 / 255, 0xb2 / 255];
const TIE = [0x2f / 255, 0x6f / 255, 0xd0 / 255];
const SKIN_COLOUR = 0xc8b49a;
const DESIGN_COLOUR = 0x9aa4b2;
const ANCHOR = [0x66 / 255, 0xaa / 255, 0xff / 255];

export function createFormworkView(THREE) {
  const group = new THREE.Group();
  group.name = "formwork";
  let sim = null;
  let parts = null;
  let at = null;            // the blended node positions on screen, metres
  let treeAt = null;        // the blended tree nodes, metres
  let skinFor = -1;         // the capture whose placed faces the skin carries
  let edgeIndex = null;     // each member by its two nodes, made when first asked
  const matrix = new THREE.Matrix4();
  const turn = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  const start = new THREE.Vector3();
  const end = new THREE.Vector3();
  const middle = new THREE.Vector3();
  const stretch = new THREE.Vector3();
  const colour = new THREE.Color();
  const projected = new THREE.Vector3();

  function lines(count, material, coloured) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
    if (coloured) {
      geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(count * 6), 3));
    }
    const object = new THREE.LineSegments(geometry, material);
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  function marks(geometry, count, material) {
    const object = new THREE.InstancedMesh(geometry, material, Math.max(1, count));
    object.count = 0;
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  function skin() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(sim.nodes * 3), 3));
    geometry.setIndex([]);
    const object = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
      color: SKIN_COLOUR, side: THREE.DoubleSide, roughness: 0.9, transparent: true, opacity: 0.9 }));
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  // Compare's design (spec 2026-10-11 section 5.4): the designed form drawn as
  // translucent formwork, the cut mesh's faces at their designed points.
  function designFaces() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(sim.design), 3));
    const triangles = [];
    for (const corners of sim.faces || []) {
      for (let k = 1; k + 1 < corners.length; k++) triangles.push(corners[0], corners[k], corners[k + 1]);
    }
    geometry.setIndex(triangles);
    const object = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color: DESIGN_FACE, side: THREE.DoubleSide, transparent: true, opacity: DESIGN_FACE_OPACITY,
      depthWrite: false }));
    object.frustumCulled = false;
    group.add(object);
    return object;
  }

  // Everything the document draws, once; the design and the anchors stand
  // still, the rest moves with the captures.
  function build(next) {
    clear();
    sim = next;
    if (!sim) return;
    const rim = sim.rim.nodes.length;
    const heads = sim.trees.heads.length;
    const radius = sim.trees.diameter / 2000;
    parts = {
      net: lines(sim.edges.length, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      design: lines(sim.edges.length, new THREE.LineBasicMaterial({
        color: DESIGN_COLOUR, transparent: true, opacity: 0.45 }), false),
      wires: lines(rim, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      trees: marks(new THREE.CylinderGeometry(radius, radius, 1, 12), sim.trees.members.length,
                   new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6, metalness: 0.3 })),
      heads: marks(new THREE.SphereGeometry(HEAD_M, 12, 8), heads,
                   new THREE.MeshBasicMaterial({ color: 0xffffff })),
      anchors: marks(new THREE.BoxGeometry(2 * MARK_M, 2 * MARK_M, 2 * MARK_M), rim,
                     new THREE.MeshBasicMaterial({ color: 0xffffff })),
      ground: marks(new THREE.SphereGeometry(MARK_M / 2, 8, 6), sim.nodes,
                    new THREE.MeshBasicMaterial({ color: 0xc99a2e })),
      skin: skin(),
      props: marks(new THREE.CylinderGeometry(PROP_M / 2, PROP_M / 2, 1, 8), sim.holds.length,
                   new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6 })),
      rings: marks(new THREE.TorusGeometry(RING_M, RING_TUBE_M, 8, 24),
                   sim.nodes + sim.edges.length + rim + sim.trees.members.length,
                   new THREE.MeshBasicMaterial({ color: 0xffffff })),
      designFaces: designFaces(),
      offsets: lines(sim.nodes, new THREE.LineBasicMaterial({ vertexColors: true }), true),
      tendons: lines(tendonSegments(), new THREE.LineBasicMaterial({ vertexColors: true }), true),
      reels: marks(new THREE.CylinderGeometry(REEL_M, REEL_M, REEL_WIDTH_M, 16),
                   sim.tendons ? sim.tendons.lines.length : 0,
                   new THREE.MeshBasicMaterial({ color: 0xffffff })),
    };
    parts.tendons.geometry.setDrawRange(0, 2 * tendonSegments());
    const design = parts.design.geometry.attributes.position;
    sim.edges.forEach(([u, v], e) => {
      for (let k = 0; k < 3; k++) {
        design.array[6 * e + k] = sim.design[3 * u + k];
        design.array[6 * e + 3 + k] = sim.design[3 * v + k];
      }
    });
    design.needsUpdate = true;
    for (let w = 0; w < rim; w++) {
      const a = sim.rim.anchors;
      matrix.makeTranslation(a[3 * w], a[3 * w + 1], a[3 * w + 2]);
      parts.anchors.setMatrixAt(w, matrix);
    }
    parts.anchors.count = rim;
    parts.anchors.instanceMatrix.needsUpdate = true;
    at = new Float32Array(sim.nodes * 3);
    treeAt = new Float32Array(sim.captures[0].treeX ? sim.captures[0].treeX.length : 0);
    skinFor = -1;
  }

  // every segment of every tendon, in its lines' order
  function tendonSegments() {
    const lines = sim && sim.tendons ? sim.tendons.lines : [];
    return lines.reduce((sum, line) => sum + Math.max(0, (line.path || []).length - 1), 0);
  }

  function put(array, offset, values) {
    array[offset] = values[0];
    array[offset + 1] = values[1];
    array[offset + 2] = values[2];
  }

  // A key's colour, sRGB from 0 to 1, as three wants a vertex or an instance
  // colour: in the linear working space, so the model wears its key's colours
  // (found on screen: the net drew orange where the key says red).
  function tone(rgb) {
    return colour.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
  }

  function putColour(array, offset, rgb) {
    const c = tone(rgb);
    put(array, offset, [c.r, c.g, c.b]);
  }

  function node(i) {
    return [at[3 * i], at[3 * i + 1], at[3 * i + 2]];
  }

  // The capture the player is at: positions blended between the two either
  // side for the drawing, every colour from the nearer one (spec section 7).
  // settings: { show: {net, trees, heads, wires, anchors, ground, skin,
  // design, holds}, colour, tolerance, weakest (weakestAt's parts), compare,
  // skinOpacity (0 to 0.5; 0 hides the skin) }.
  function show(head, settings) {
    if (!sim || !parts || !head) return;
    const a = sim.captures[head.from];
    const b = sim.captures[head.to];
    const near = sim.captures[head.nearer];
    const f = head.blend;
    const by = settings.colour;
    const tolerance = settings.tolerance;
    for (let i = 0; i < at.length; i++) at[i] = a.x[i] + (b.x[i] - a.x[i]) * f;
    for (let i = 0; i < treeAt.length; i++) treeAt[i] = a.treeX[i] + (b.treeX[i] - a.treeX[i]) * f;

    const net = parts.net.geometry.attributes;
    sim.edges.forEach(([u, v], e) => {
      put(net.position.array, 6 * e, node(u));
      put(net.position.array, 6 * e + 3, node(v));
      let cu = null;
      let cv = null;
      if (by === "deviation") {
        cu = colourOf("deviation", near.deviation[u], sim, tolerance);
        cv = colourOf("deviation", near.deviation[v], sim, tolerance);
      } else {
        // Along, Across and Both, the other family grey (spec 2026-10-11
        // across tendons, section 6)
        cu = cv = memberColour(by, sim, near, e);
      }
      putColour(net.color.array, 6 * e, cu || PLAIN);
      putColour(net.color.array, 6 * e + 3, cv || PLAIN);
    });
    net.position.needsUpdate = true;
    net.color.needsUpdate = true;

    sim.trees.members.forEach(([p, q], k) => {
      start.set(treeAt[3 * p], treeAt[3 * p + 1], treeAt[3 * p + 2]);
      end.set(treeAt[3 * q], treeAt[3 * q + 1], treeAt[3 * q + 2]);
      middle.addVectors(start, end).multiplyScalar(0.5);
      const length = end.distanceTo(start);
      if (length > 0) turn.setFromUnitVectors(up, end.sub(start).divideScalar(length));
      else turn.identity();
      matrix.compose(middle, turn, stretch.set(1, Math.max(length, 1e-6), 1));
      parts.trees.setMatrixAt(k, matrix);
      const tint = by === "utilisation"
        ? colourOf("utilisation", near.treeUtilisation[k], sim, tolerance) : TREE_PLAIN;
      parts.trees.setColorAt(k, tone(tint));
    });
    parts.trees.count = sim.trees.members.length;
    parts.trees.instanceMatrix.needsUpdate = true;
    if (parts.trees.instanceColor) parts.trees.instanceColor.needsUpdate = true;

    // each head marked green while it pushes its node, clear once it has let
    // go; its push is a value, never an arrow (spec 2026-10-11 section 5.2)
    sim.trees.heads.forEach(([, treeNode], h) => {
      matrix.makeTranslation(treeAt[3 * treeNode], treeAt[3 * treeNode + 1], treeAt[3 * treeNode + 2]);
      parts.heads.setMatrixAt(h, matrix);
      const force = near.headPush ? [near.headPush[3 * h], near.headPush[3 * h + 1], near.headPush[3 * h + 2]]
        : [0, 0, 0];
      const touching = Math.hypot(force[0], force[1], force[2]) > 0;
      parts.heads.setColorAt(h, tone(touching ? HEAD_TOUCHING : HEAD_CLEAR));
    });
    parts.heads.count = sim.trees.heads.length;
    parts.heads.instanceMatrix.needsUpdate = true;
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;

    // the tendons, proud of the net, in their across members' colours under
    // Across and Both and white otherwise, each with its reel by its head
    const tendons = parts.tendons.geometry.attributes;
    const proud = (i) => { const p = node(i); p[2] += TENDON_PROUD_M; return p; };
    let segment = 0;
    (sim.tendons ? sim.tendons.lines : []).forEach((line, t) => {
      const path = line.path || [];
      let first = null;
      for (let k = 1; k < path.length; k++) {
        put(tendons.position.array, 6 * segment, proud(path[k - 1]));
        put(tendons.position.array, 6 * segment + 3, proud(path[k]));
        const e = edgeOf(path[k - 1], path[k]);
        const tint = (by === "across" || by === "both") && e >= 0
          ? memberColour(by, sim, near, e) || TENDON_PLAIN : TENDON_PLAIN;
        putColour(tendons.color.array, 6 * segment, tint);
        putColour(tendons.color.array, 6 * segment + 3, tint);
        if (first === null) first = tint;
        segment += 1;
      }
      const head = proud(path[0]);
      const next = path.length > 1 ? proud(path[1]) : head;
      const along = Math.hypot(next[0] - head[0], next[1] - head[1], next[2] - head[2]) || 1;
      matrix.makeTranslation(...head.map((value, k) => value + (next[k] - value) / along * REEL_ALONG_M));
      parts.reels.setMatrixAt(t, matrix);
      parts.reels.setColorAt(t, tone(first || TENDON_PLAIN));
    });
    tendons.position.needsUpdate = true;
    tendons.color.needsUpdate = true;
    parts.reels.count = sim.tendons ? sim.tendons.lines.length : 0;
    parts.reels.instanceMatrix.needsUpdate = true;
    if (parts.reels.instanceColor) parts.reels.instanceColor.needsUpdate = true;

    const wires = parts.wires.geometry.attributes;
    sim.rim.nodes.forEach((rimNode, w) => {
      const from = node(rimNode);
      put(wires.position.array, 6 * w, from);
      put(wires.position.array, 6 * w + 3,
          from.map((value, k) => value + sim.rim.into[3 * w + k] * WIRE_STUB_M));
      const tint = (by === "wire" ? colourOf("wire", near.wireTension[w], sim, tolerance) : null) || PLAIN;
      putColour(wires.color.array, 6 * w, tint);
      putColour(wires.color.array, 6 * w + 3, tint);
      // a wire runs straight down into its anchor, so its stub is hidden in
      // the rim beam: the anchor's mark wears the wire's colour (found on screen)
      parts.anchors.setColorAt(w, tone(by === "wire" ? tint : ANCHOR));
    });
    wires.position.needsUpdate = true;
    wires.color.needsUpdate = true;
    if (parts.anchors.instanceColor) parts.anchors.instanceColor.needsUpdate = true;

    const ground = near.ground || [];
    ground.forEach((groundNode, k) => {
      const p = node(groundNode);
      matrix.makeTranslation(p[0], p[1], p[2]);
      parts.ground.setMatrixAt(k, matrix);
    });
    parts.ground.count = ground.length;
    parts.ground.instanceMatrix.needsUpdate = true;

    const surface = parts.skin.geometry;
    if (head.nearer !== skinFor) {
      const triangles = [];
      for (const face of placedFaces(sim, head.nearer)) {
        const corners = sim.faces ? sim.faces[face] : null;
        if (!corners) continue;
        for (let k = 1; k + 1 < corners.length; k++) triangles.push(corners[0], corners[k], corners[k + 1]);
      }
      surface.setIndex(triangles);
      skinFor = head.nearer;
    }
    surface.attributes.position.array.set(at);
    surface.attributes.position.needsUpdate = true;
    if (surface.index && surface.index.count) surface.computeVertexNormals();
    // the skin's slider (spec 2026-10-11 section 5.5): how opaque, 0 hiding it
    const opacity = settings.skinOpacity;
    if (opacity != null) parts.skin.material.opacity = Math.min(0.5, Math.max(0, Number(opacity)));

    // the weakest parts (section 5.3): a ring round each, red over its limit,
    // amber the closest when none is over
    let ringed = 0;
    for (const item of settings.weakest || []) {
      const p = point({ kind: item.kind, index: item.index });
      if (!p) continue;
      matrix.makeTranslation(p[0], p[1], p[2]);
      parts.rings.setMatrixAt(ringed, matrix);
      parts.rings.setColorAt(ringed, tone(item.over ? OVER : CLOSE));
      ringed += 1;
    }
    parts.rings.count = ringed;
    parts.rings.instanceMatrix.needsUpdate = true;
    if (parts.rings.instanceColor) parts.rings.instanceColor.needsUpdate = true;

    // Compare (section 5.4): each node's line from where it should be to where
    // it is, in the nearer capture's band against the tolerance
    const compare = !!settings.compare;
    if (compare) {
      const offsets = parts.offsets.geometry.attributes;
      for (let i = 0; i < sim.nodes; i++) {
        put(offsets.position.array, 6 * i, [sim.design[3 * i], sim.design[3 * i + 1], sim.design[3 * i + 2]]);
        put(offsets.position.array, 6 * i + 3, node(i));
        const band = bandColour(near.deviation[i], tolerance);
        putColour(offsets.color.array, 6 * i, band);
        putColour(offsets.color.array, 6 * i + 3, band);
      }
      offsets.position.needsUpdate = true;
      offsets.color.needsUpdate = true;
    }

    // the holds' rods (his ruling of 10 October 2026: a hold is a gripped rod
    // along its own force): from the jacking on, each set at the angle of its
    // force at the capture after the jacking, from its foot on the ground up
    // to its node's design point; green while it pushes, blue while it pulls,
    // grey while it carries nothing
    const jacked = near.phase === "holds" || near.phase === "tiling";
    const set = sim.captures[jackedAt(sim)];
    sim.holds.forEach((holdNode, h) => {
      const top = [sim.design[3 * holdNode], sim.design[3 * holdNode + 1], sim.design[3 * holdNode + 2]];
      const u = holdRod(holdForce(set, h)).u;
      const length = Math.max(top[2], 1e-6) / u[2];
      // a cylinder stands along y: turned along the rod, then made as long as it
      turn.setFromUnitVectors(up, start.set(u[0], u[1], u[2]));
      matrix.compose(middle.set(top[0] - u[0] * length / 2, top[1] - u[1] * length / 2,
                                top[2] - u[2] * length / 2), turn, stretch.set(1, length, 1));
      parts.props.setMatrixAt(h, matrix);
      const kind = holdRod(holdForce(near, h)).kind;
      parts.props.setColorAt(h, tone(kind === "strut" ? HEAD_TOUCHING : kind === "tie" ? TIE : HEAD_CLEAR));
    });
    parts.props.count = sim.holds.length;
    parts.props.instanceMatrix.needsUpdate = true;
    if (parts.props.instanceColor) parts.props.instanceColor.needsUpdate = true;

    const on = settings.show || {};
    parts.net.visible = !!on.net;
    parts.design.visible = compare || !!on.design;
    parts.designFaces.visible = compare && !!(parts.designFaces.geometry.index
      && parts.designFaces.geometry.index.count);
    parts.offsets.visible = compare;
    parts.rings.visible = ringed > 0;
    parts.trees.visible = !!on.trees;
    parts.heads.visible = !!on.heads;
    parts.wires.visible = !!on.wires;
    parts.anchors.visible = !!on.anchors;
    parts.ground.visible = !!on.ground;
    parts.skin.visible = (opacity != null ? Number(opacity) > 0 : !!on.skin)
      && !!(surface.index && surface.index.count);
    parts.props.visible = !!on.holds && jacked && sim.holds.length > 0;
    parts.tendons.visible = !!on.tendons && segment > 0;
    parts.reels.visible = parts.tendons.visible;
  }

  // The net member joining two nodes, or -1.
  function edgeOf(a, b) {
    if (!edgeIndex) {
      edgeIndex = new Map(sim.edges.map(([u, v], e) => [Math.min(u, v) + "," + Math.max(u, v), e]));
    }
    const e = edgeIndex.get(Math.min(a, b) + "," + Math.max(a, b));
    return e == null ? -1 : e;
  }

  // Where a part is on screen now, in metres (targetPoint on the blended
  // positions), so a label rides the drawing.
  function point(target) {
    if (!sim || !at) return null;
    return targetPoint({ ...sim, captures: [{ x: at, treeX: treeAt }] }, 0, target);
  }

  // A point in metres to the page, or null behind the eye or off the canvas.
  function project(p, camera, rect) {
    if (!p) return null;
    projected.set(p[0], p[1], p[2]).project(camera);
    if (projected.z > 1) return null;
    const x = rect.left + (projected.x * 0.5 + 0.5) * rect.width;
    const y = rect.top + (-projected.y * 0.5 + 0.5) * rect.height;
    if (x < rect.left || x > rect.left + rect.width || y < rect.top || y > rect.top + rect.height) {
      return null;
    }
    return [x, y];
  }

  // The node nearest a click, within reach pixels, or null.
  function nearestNode(camera, rect, x, y, reach = 14) {
    if (!sim || !at) return null;
    let best = null;
    let nearest = reach;
    for (let i = 0; i < sim.nodes; i++) {
      const p = project(node(i), camera, rect);
      if (!p) continue;
      const distance = Math.hypot(p[0] - x, p[1] - y);
      if (distance < nearest) { nearest = distance; best = i; }
    }
    return best;
  }

  function clear() {
    for (const child of [...group.children]) {
      group.remove(child);
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
      if (child.dispose) child.dispose();
    }
    parts = null;
    sim = null;
    at = null;
    treeAt = null;
    skinFor = -1;
    edgeIndex = null;
  }

  return { group, build, show, point, project, nearestNode, clear, parts: () => parts };
}
