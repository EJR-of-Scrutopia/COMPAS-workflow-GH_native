// Reading bench.mechanism/1 into something the studio can draw.
//
// This module is PURE: plain data in, plain data out, no three.js and no
// DOM, so it runs under node and its rules are tested as arithmetic. It
// exists as its own file for one reason: the document's key layout is
// expected to move again (five parts rather than the shape first agreed,
// ten reels of which seven move as one group, placement derived from the
// first wire frame). Every one of those changes lands HERE, in named
// functions with tests around them, instead of being threaded through
// the renderer.
//
// The posture throughout is the one the contract settles on repeatedly:
// READ a value, never a rule for finding one, and where the writer
// derives something, check it and REPORT rather than quietly correct.
// A wire drawn to a plausible vertex is worse than a wire drawn wrong
// and named, because only one of the two can be noticed.

export const SCHEMA = "bench.mechanism/1";

// The parts, in the order they should be built and drawn. The kind of a
// part is THE ARRAY IT SITS IN, not a tag on it -- Param asked for one
// port per kind, so a kind authored by construction cannot fall out of
// step with the thing it names. This table is therefore both the list of
// ports to look in and the material mapping, in one place.
//
// `world` marks the parts that arrive pre-placed in world coordinates
// rather than in the authored body's local space: the permanent works.
// `permanent` marks what REMAINS when the machine is struck (Param: "it
// goes away with the columns and formwork. the tension tie / anchor
// stays").
export const PART_KINDS = [
  { key: "frame1", kind: "frame1", material: "metal/steel-mill-grey" },
  { key: "frame2", kind: "frame2", material: "metal/steel-mill-grey" },
  { key: "motors", kind: "motor", material: "metal/steel-powder-coated-black" },
  { key: "reels", kind: "reel", material: "timber/birch-pale-fine", spins: true },
  { key: "pulleys", kind: "pulley", material: "timber/birch-pale-fine" },
  { key: "tensionTie", kind: "tie", material: "metal/aluminium-mill-grey",
    tint: "#3a3d42", permanent: true },
  { key: "anchor", kind: "anchor", material: "metal/aluminium-mill-grey",
    tint: "#3a3d42", permanent: true },
];

// Keys the writer has used for the same part under another spelling.
// Listed rather than guessed at, so an unknown key is still reported as
// unknown instead of being absorbed by a fuzzy match.
const KEY_ALIASES = {
  frame1: ["frames1", "frameOne"],
  frame2: ["frames2", "frameTwo"],
  motors: ["motor", "drives"],
  reels: ["reel", "drums", "spools"],
  pulleys: ["pulley", "pulleyBodies", "bodies"],
  tensionTie: ["tensionTies", "tie", "ties"],
  anchor: ["anchors", "foundationAnchor"],
};

// A part key holds EITHER one part or a list of them -- frame1 is a
// single body and frame2 is three -- so both are read and the caller
// never has to know which this document used.
function partsUnder(body, key) {
  const names = [key].concat(KEY_ALIASES[key] || []);
  for (const name of names) {
    const value = body[name];
    if (Array.isArray(value)) return { name, entries: value };
    if (value && typeof value === "object") return { name, entries: [value] };
  }
  return null;
}

// Every key this reader knows how to use, so anything else in the
// document can be listed as unread rather than passing unnoticed. An
// unread key is the earliest signal that the layout moved.
const KNOWN_KEYS = new Set([
  "schema", "units", "lengthUnitToMetres", "numbering", "rotation",
  "principalRows", "mechanism", "instances", "wires", "study", "generated",
  "vertexCount", "columnNodeCount", "anchors", "tensionTies",
  "notes", "warnings", "provenance",
]);

// ---------- geometry ----------
// The bench.columns/1 convention: a flat or nested vertices array, a
// faces array of mixed triangles and quads, and the document's own
// length scale. Returned as flat typed-array-ready lists of TRIANGLES,
// because that is what a renderer wants and fan-splitting a quad is
// the one thing every caller would otherwise repeat.
export function readGeometry(source, scale = 1) {
  if (!source || typeof source !== "object") return null;
  const rawVertices = source.vertices || source.points || null;
  const rawFaces = source.faces || null;
  if (!Array.isArray(rawVertices) || !rawVertices.length) return null;
  const vertices = [];
  if (Array.isArray(rawVertices[0])) {
    for (const v of rawVertices) {
      vertices.push(+v[0] * scale, +v[1] * scale, +v[2] * scale);
    }
  } else if (typeof rawVertices[0] === "object") {
    for (const v of rawVertices) {
      vertices.push(+v.x * scale, +v.y * scale, +v.z * scale);
    }
  } else {
    for (let i = 0; i + 2 < rawVertices.length; i += 3) {
      vertices.push(+rawVertices[i] * scale, +rawVertices[i + 1] * scale,
        +rawVertices[i + 2] * scale);
    }
  }
  const count = vertices.length / 3;
  const triangles = [];
  for (const face of Array.isArray(rawFaces) ? rawFaces : []) {
    const loop = Array.isArray(face) ? face : (face && face.vertices) || null;
    if (!Array.isArray(loop) || loop.length < 3) continue;
    // A fan, which is right for the triangles and quads this convention
    // carries and harmless for a convex n-gon.
    for (let i = 1; i < loop.length - 1; i++) {
      const a = loop[0], b = loop[i], c = loop[i + 1];
      if (!inRange(a, count) || !inRange(b, count) || !inRange(c, count)) continue;
      triangles.push(a, b, c);
    }
  }
  return { vertices, triangles, vertexCount: count };
}

function inRange(index, count) {
  return Number.isInteger(index) && index >= 0 && index < count;
}

// ---------- placement ----------
// A frame is origin plus x and y axes, with z derived -- EXCEPT that the
// writer reports side 1 as a genuine reflection, determinant -1, and a
// derived z cannot express one. z = x cross y is right-handed by
// construction, always, so deriving it silently converts a mirrored
// instance into a rotation and the mirrored half comes back turned the
// wrong way rather than mirrored.
//
// So an explicit z is read and USED VERBATIM when the document sends
// one, reflection and all, and only derived when it does not. If a
// document ever needs to mirror without sending z, that is unsayable in
// this schema and the writer has to be told rather than the reader
// guessing. (Raised with the plugin session 2026-09-08.)
//
// Returned column-major, the order THREE.Matrix4.fromArray wants.
export function placementMatrix(frame, scale = 1) {
  if (!frame || typeof frame !== "object") return null;
  const origin = readVector(frame.origin || frame.o || frame.point);
  const xAxis = readVector(frame.xAxis || frame.x || frame.xaxis);
  const yAxis = readVector(frame.yAxis || frame.y || frame.yaxis);
  if (!origin || !xAxis || !yAxis) return null;
  const x = normalise(xAxis);
  const y = normalise(yAxis);
  if (!x || !y) return null;
  const derived = cross(x, y);
  const length = Math.hypot(derived[0], derived[1], derived[2]);
  if (length < 1e-9) return null;          // x and y parallel: no frame
  const sent = normalise(readVector(frame.zAxis || frame.z || frame.zaxis) || [0, 0, 0]);
  const z = sent || derived;
  return [
    x[0], x[1], x[2], 0,
    y[0], y[1], y[2], 0,
    z[0], z[1], z[2], 0,
    origin[0] * scale, origin[1] * scale, origin[2] * scale, 1,
  ];
}

// True when this placement mirrors rather than rotates. Worth knowing
// out loud: a mirrored instance needs its triangle winding flipped or it
// lights from the inside.
export function isReflection(matrix) {
  if (!matrix) return false;
  const x = [matrix[0], matrix[1], matrix[2]];
  const y = [matrix[4], matrix[5], matrix[6]];
  const z = [matrix[8], matrix[9], matrix[10]];
  const c = cross(x, y);
  return (c[0] * z[0] + c[1] * z[1] + c[2] * z[2]) < 0;
}

function readVector(value) {
  if (Array.isArray(value) && value.length >= 3) {
    return [+value[0], +value[1], +value[2]];
  }
  if (value && typeof value === "object"
      && typeof value.x === "number") {
    return [+value.x, +value.y, +value.z];
  }
  return null;
}

function normalise(v) {
  const length = Math.hypot(v[0], v[1], v[2]);
  if (!(length > 1e-12)) return null;
  return [v[0] / length, v[1] / length, v[2] / length];
}

function cross(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

// ---------- the spin ----------
// The contract's formula, with its sign fixed at plugin 29da394:
//
//   turns = (length_at(frame0) - length_at(t)) * reeveFactor
//           / (2 * pi * spoolRadius)
//
// Positive turns take up wire. length_at(t) is the wire's FREE SPAN --
// net vertex to where it first meets the machine -- because the wrapped
// portion is constant and is the quantity the studio computes anyway in
// order to draw that span.
//
// Referenced to frame 0 rather than accumulated per frame, which is the
// load-bearing part: the studio's timeline is a pure function of t, so
// an incremental delta would drift on scrub and be wrong on every
// recorded frame not played in order.
export function turnsFor(freeAtFrame0, freeNow, reeveFactor, spoolRadius) {
  const radius = +spoolRadius;
  if (!(radius > 1e-6)) return 0;
  const reeve = Number.isFinite(+reeveFactor) ? +reeveFactor : 1;
  return (freeAtFrame0 - freeNow) * reeve / (2 * Math.PI * radius);
}

// ---------- reading the document ----------
// Never throws. A document it cannot read comes back with `ok: false`
// and a reason a person can act on, because the alternative is a studio
// that goes blank when an exporter changes its mind.
export function readMechanism(document) {
  if (!document || typeof document !== "object") {
    return { ok: false, reason: "the mechanism document is not an object" };
  }
  if (document.schema !== SCHEMA) {
    return { ok: false,
      reason: "mechanism schema " + JSON.stringify(document.schema)
        + " is not " + JSON.stringify(SCHEMA) };
  }
  const scale = Number.isFinite(+document.lengthUnitToMetres)
    && +document.lengthUnitToMetres > 0 ? +document.lengthUnitToMetres : 1;

  const notes = [];
  const parts = [];
  // The parts live INSIDE the authored body, under named keys, and each
  // key holds either one part or a list of them: frame1 is a single body
  // and frame2 is three. They are in the body's LOCAL space, so every one
  // of them is stamped with each instance's placement -- the tension tie
  // included, which is why "permanent" here means "survives the strike"
  // and not "arrives pre-placed".
  const body = document.mechanism && typeof document.mechanism === "object"
    ? document.mechanism : {};
  for (const spec of PART_KINDS) {
    const found = partsUnder(body, spec.key);
    if (!found) continue;
    if (found.name !== spec.key) {
      notes.push("the " + spec.kind + " parts arrived under \""
        + found.name + "\", not \"" + spec.key + "\"");
    }
    let index = 0;
    for (const entry of found.entries) {
      // A reel carries its mesh under `mesh` and its spin axis beside it;
      // the simpler parts are the geometry themselves.
      const geometry = readGeometry(
        entry && (entry.mesh || entry.geometry) ? (entry.mesh || entry.geometry) : entry,
        scale);
      if (!geometry) {
        notes.push("a " + spec.kind + " carried no readable geometry");
        index += 1;
        continue;
      }
      // Permanence is DECLARED on the part, so it is read rather than
      // inferred from which key it arrived under. The table's own value
      // stands in only when the document is silent.
      const declared = typeof entry.permanence === "string"
        ? entry.permanence.toLowerCase() : null;
      parts.push({
        kind: spec.kind,
        // A reel states its own number, which is what route frames point
        // at through ownerReel; position in the list is not that number.
        index: Number.isInteger(entry.reel) ? entry.reel : index,
        geometry,
        material: spec.material, tint: spec.tint || null,
        world: false,
        permanent: declared ? declared === "permanent" : !!spec.permanent,
        spins: !!spec.spins,
        driven: entry.driven !== false,
        axis: readAxis(entry, scale),
      });
      index += 1;
    }
  }

  // The whole-body fallback: the earliest shape shipped ONE mesh under
  // `mechanism` with no named parts inside it.
  if (!parts.length) {
    const whole = readGeometry(
      document.mechanism && document.mechanism.geometry
        ? document.mechanism.geometry : document.mechanism, scale);
    if (whole) {
      parts.push({ kind: "body", index: 0, geometry: whole,
        material: "metal/steel-mill-grey", tint: null,
        world: false, permanent: false, spins: false, driven: false, axis: null });
      notes.push("this document carries one authored body rather than "
        + "named parts, so the whole machine wears one material");
    }
  }

  const instances = [];
  for (const entry of Array.isArray(document.instances) ? document.instances : []) {
    // `frame` first: this writer uses `placement` for a LABEL, and
    // reading that first found a string and reported six unreadable
    // placements on a document whose placements are all present.
    const matrix = placementMatrix(
      entry && (entry.frame || entry.placement), scale);
    if (!matrix) {
      notes.push("an instance carried no readable placement frame");
      continue;
    }
    instances.push({
      side: Number.isInteger(entry.side) ? entry.side : 0,
      mechanism: Number.isInteger(entry.mechanism) ? entry.mechanism : 0,
      // The instance NAMES the wires it carries, which is an exact
      // mapping and beats matching a wire's path back to a side and a
      // mechanism number.
      wireIds: Array.isArray(entry.wireIds) ? entry.wireIds.slice() : [],
      matrix, mirrored: isReflection(matrix),
    });
  }

  const wires = [];
  for (const entry of Array.isArray(document.wires) ? document.wires : []) {
    const route = [];
    for (const plane of Array.isArray(entry.route) ? entry.route : []) {
      const matrix = placementMatrix(plane, scale);
      if (!matrix) continue;
      route.push({
        matrix,
        owner: plane.owner === "reel" ? "reel" : "body",
        ownerReel: Number.isInteger(plane.ownerReel) ? plane.ownerReel : -1,
      });
    }
    wires.push({
      id: entry.id,
      // Explicit, never inferred from ordinal position: grouping says
      // which mechanism a wire belongs to and nothing about which vertex
      // it pulls. A missing one is reported, not guessed.
      netVertex: Number.isInteger(entry.net_vertex) ? entry.net_vertex
        : (Number.isInteger(entry.netVertex) ? entry.netVertex : null),
      columnNode: Number.isInteger(entry.column_node) ? entry.column_node
        : (Number.isInteger(entry.columnNode) ? entry.columnNode : null),
      path: Array.isArray(entry.path) ? entry.path : [],
      route,
      // Resolved on every wire by contract, so the reader never inherits
      // and never needs to know a default exists.
      reeveFactor: Number.isFinite(+entry.reeveFactor) ? +entry.reeveFactor
        : (Number.isFinite(+body.reeveFactor) ? +body.reeveFactor : null),
      // Per wire by contract; this writer carries it once on the body,
      // so the body's value stands in rather than the reader inheriting
      // a rule. The studio measures each reel anyway (see
      // measureSpoolRadius), and the measured one wins.
      spoolRadius: Number.isFinite(+entry.spoolRadius)
        ? +entry.spoolRadius * scale
        : (Number.isFinite(+body.spoolRadius) ? +body.spoolRadius * scale : null),
    });
    if (wires[wires.length - 1].netVertex === null) {
      notes.push("wire " + JSON.stringify(entry.id)
        + " carries no net_vertex, so it cannot be drawn to the net");
    }
  }

  for (const key of Object.keys(document)) {
    if (KNOWN_KEYS.has(key)) continue;
    if (PART_KINDS.some((spec) => spec.key === key)) continue;
    if (Object.values(KEY_ALIASES).some((list) => list.includes(key))) continue;
    notes.push("this reader does not use the key \"" + key + "\"");
  }

  return { ok: true, scale, parts, instances, wires, notes,
    rotation: document.rotation || null,
    numbering: document.numbering || null };
}

function readAxis(entry, scale) {
  if (!entry || typeof entry !== "object") return null;
  const frame = entry.axis || entry.spinAxis || entry.frame || null;
  if (!frame) return null;
  const origin = readVector(frame.origin || frame.point || frame.o);
  const direction = normalise(
    readVector(frame.direction || frame.zAxis || frame.axis) || [0, 0, 1]);
  if (!origin || !direction) return null;
  return { origin: origin.map((v) => v * scale), direction };
}

// ---------- the checks the contract asks for ----------
// Both derived values the writer sends are re-checked here and REPORTED,
// never corrected. The writer derives net_vertex by matching wire order
// to anchor order, and derives a route frame's owner by distance to each
// reel's axis; either can be wrong, and a wire drawn to a plausible but
// wrong vertex is the one failure nobody would notice.
export function checkNetVertices(wires, vertices, placed) {
  const complaints = [];
  for (const wire of wires) {
    if (wire.netVertex === null || !wire.route.length) continue;
    const head = placed ? placed(wire) : firstOrigin(wire);
    if (!head) continue;
    const declared = vertexAt(vertices, wire.netVertex);
    if (!declared) {
      complaints.push({ id: wire.id, reason: "net_vertex "
        + wire.netVertex + " is outside the net" });
      continue;
    }
    const declaredDistance = distance(head, declared);
    let bestIndex = -1, best = Infinity;
    for (let i = 0; i < vertices.length / 3; i++) {
      const d = distance(head, vertexAt(vertices, i));
      if (d < best) { best = d; bestIndex = i; }
    }
    // Dramatically closer, not merely closer: the wire genuinely leaves
    // from a point near several vertices, and a 10 cm difference proves
    // nothing. A factor of three does.
    if (bestIndex !== wire.netVertex && best * 3 < declaredDistance) {
      complaints.push({ id: wire.id, declared: wire.netVertex,
        nearest: bestIndex,
        declaredDistance, nearestDistance: best,
        reason: "wire " + wire.id + " says net vertex " + wire.netVertex
          + " (" + declaredDistance.toFixed(2) + " m away) but vertex "
          + bestIndex + " is " + best.toFixed(2) + " m away" });
    }
  }
  return complaints;
}

function firstOrigin(wire) {
  const first = wire.route[0];
  if (!first) return null;
  return [first.matrix[12], first.matrix[13], first.matrix[14]];
}

function vertexAt(vertices, index) {
  if (!inRange(index, vertices.length / 3)) return null;
  return [vertices[index * 3], vertices[index * 3 + 1], vertices[index * 3 + 2]];
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

// planes[0] is the net end by contract, so the list reads in the
// direction the wire is drawn. Checked rather than trusted: the first
// plane must sit nearer its net vertex than the last does.
export function checkRouteDirection(wires, vertices) {
  const reversed = [];
  for (const wire of wires) {
    if (wire.netVertex === null || wire.route.length < 2) continue;
    const vertex = vertexAt(vertices, wire.netVertex);
    if (!vertex) continue;
    const first = firstOrigin(wire);
    const last = wire.route[wire.route.length - 1];
    const tail = [last.matrix[12], last.matrix[13], last.matrix[14]];
    if (distance(first, vertex) > distance(tail, vertex)) {
      reversed.push(wire.id);
    }
  }
  return reversed;
}
