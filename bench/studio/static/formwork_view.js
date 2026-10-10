// The Formwork tab's drawing (spec 2026-10-10 formwork tab, section 8): its
// own objects in one group, built from the capture document, moved from the
// captures, removed when the tab closes. The studio's objects are not reused.
// THREE is handed in rather than imported, so the drawing runs under node in
// the tests as it does in the page.

import { colourOf, holdForce, holdRod, jackedAt, placedFaces, targetPoint } from "./formwork_model.js";

const WIRE_STUB_M = 0.3;        // each rim wire drawn 300 mm along the way it runs in
const MARK_M = 0.05;            // an anchor's mark, and twice a ground contact's
const HEAD_M = 0.08;            // a head's mark
const PUSH_LONGEST_M = 1.0;     // a push at the run's 95th percentile and over, drawn this long
const TIP_M = 0.08;             // the head on a push, this long
const PROP_M = 0.03;            // a hold's rod, this thick (spec 2026-10-10 formwork holds)
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
      push: lines(heads, new THREE.LineBasicMaterial({ color: 0x3f9e57 }), false),
      tips: marks(new THREE.ConeGeometry(TIP_M / 3, TIP_M, 8), heads,
                  new THREE.MeshBasicMaterial({ color: 0x3f9e57 })),
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
    };
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
  // design}, colour, tolerance }.
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
      if (by === "tension") cu = cv = colourOf("tension", near.tension[e], sim, tolerance);
      if (by === "deviation") {
        cu = colourOf("deviation", near.deviation[u], sim, tolerance);
        cv = colourOf("deviation", near.deviation[v], sim, tolerance);
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

    const push = parts.push.geometry.attributes.position;
    sim.trees.heads.forEach(([netNode, treeNode], h) => {
      matrix.makeTranslation(treeAt[3 * treeNode], treeAt[3 * treeNode + 1], treeAt[3 * treeNode + 2]);
      parts.heads.setMatrixAt(h, matrix);
      const force = near.headPush ? [near.headPush[3 * h], near.headPush[3 * h + 1], near.headPush[3 * h + 2]]
        : [0, 0, 0];
      const touching = Math.hypot(force[0], force[1], force[2]) > 0;
      const tint = touching ? HEAD_TOUCHING : HEAD_CLEAR;
      parts.heads.setColorAt(h, tone(tint));
      const from = node(netNode);
      const size = Math.hypot(force[0], force[1], force[2]);
      const length = sim.scales.push > 0 ? Math.min(1, size / sim.scales.push) * PUSH_LONGEST_M : 0;
      const tip = size > 0 ? from.map((value, k) => value + force[k] / size * length) : from;
      put(push.array, 6 * h, from);
      put(push.array, 6 * h + 3, tip);
      // the head on the push, pointing along it; none where nothing pushes
      if (size > 0) {
        start.set(force[0] / size, force[1] / size, force[2] / size);
        turn.setFromUnitVectors(up, start);
        matrix.compose(middle.set(tip[0], tip[1], tip[2]), turn, stretch.set(1, 1, 1));
      } else {
        matrix.makeScale(0, 0, 0);
      }
      parts.tips.setMatrixAt(h, matrix);
    });
    parts.heads.count = sim.trees.heads.length;
    parts.tips.count = sim.trees.heads.length;
    parts.tips.instanceMatrix.needsUpdate = true;
    parts.heads.instanceMatrix.needsUpdate = true;
    if (parts.heads.instanceColor) parts.heads.instanceColor.needsUpdate = true;
    push.needsUpdate = true;

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
    parts.design.visible = !!on.design;
    parts.trees.visible = !!on.trees;
    parts.heads.visible = !!on.heads;
    parts.push.visible = !!on.heads;
    parts.tips.visible = !!on.heads;
    parts.wires.visible = !!on.wires;
    parts.anchors.visible = !!on.anchors;
    parts.ground.visible = !!on.ground;
    parts.skin.visible = !!on.skin && !!(surface.index && surface.index.count);
    parts.props.visible = !!on.holds && jacked && sim.holds.length > 0;
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
  }

  return { group, build, show, point, project, nearestNode, clear, parts: () => parts };
}
