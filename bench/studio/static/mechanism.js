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
  // Param, 2026-09-09, on seeing every part wearing one flat grey: "the
  // aluminium frames are a anodised aluminium coated, a dark grey if we
  // can, make the frame 2 a lighter grey but not as light as it is now."
  // ONE library set under both frames, because anodising is a coat over
  // the same mill aluminium and the grain should agree across the two;
  // only the darkness of the coat differs, which is what the tint is.
  // The tint MULTIPLIES the albedo map, so the rendered grey is the
  // PRODUCT of the two, not the tint. The first pass at these numbers
  // picked them as though they were the finished colours, and since his
  // metal/aluminium-mill-grey averages 0.3511 linear luminance (measured
  // from the library's own colour.jpg) frame 1 rendered at about sRGB 46
  // -- near black, on a part he had asked to be dark GREY. Param: "the
  // color scheme changed again, needs fixing".
  //
  // These are solved backwards from where he wants them to land:
  //   frame 1  0.3511 * tint -> about sRGB 95,  a dark anodised grey
  //   frame 2  0.3511 * tint -> about sRGB 125, lighter, and still below
  //                             the 0x8d9298 (141) he called too light
  { key: "frame1", kind: "frame1", material: "metal/aluminium-mill-grey",
    tint: 0x9a9da2 },
  { key: "frame2", kind: "frame2", material: "metal/aluminium-mill-grey",
    tint: 0xc8cbcf },
  // "the motors are a deep black like a nema motor": a NEMA case is cast
  // and powder coated, near-black rather than pure black, which would
  // read as a hole punched in the render.
  { key: "motors", kind: "motor", material: "metal/steel-powder-coated-black",
    tint: 0x1c1c1e },
  // "except the the reels are a find grain timber"
  { key: "reels", kind: "reel", material: "timber/birch-pale-fine", spins: true },
  // "the others are metal": the pulleys had been wearing the reels'
  // timber, which is what put birch grain on a sheave.
  { key: "pulleys", kind: "pulley", material: "metal/steel-brushed" },
  // "Shiny ish metalic, like we used for the principle line bars, dark.
  // This is for the anchor / tie." The principal bars wear
  // metal/steel-polished-dark (PRINCIPAL_SKIN in studio.js), so the two
  // permanent works now wear it too. This REPLACES the blackened aged
  // steel he asked for on 08 September; he has seen that name in the
  // panel and asked for the bars' metal instead, so the newer word wins.
  { key: "tensionTie", kind: "tie", material: "metal/steel-polished-dark",
    permanent: true },
  { key: "anchor", kind: "anchor", material: "metal/steel-polished-dark",
    permanent: true },
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
  // Declared by the writer from 2026-09-09 so no consumer has to infer
  // any of them from where frames happen to sit against a drum mesh. The
  // cable is stated TWICE, as a radius and as a thickness; see below.
  "cableRadius", "cableThickness", "routingFrameMeaning",
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
        // The writer now measures each reel's own winding radius (median
        // perpendicular distance of the routing frames it owns from its
        // own axis) rather than sharing one bounding-box figure across
        // four. That is the same quantity the studio measures for itself,
        // so it is trusted first and the measurement stays as the fallback.
        windingRadius: Number.isFinite(+entry.windingRadius)
          ? +entry.windingRadius * scale : null,
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

  // THE ANCHORS, stamped from ONE body. Until 2026-09-09 the anchor was
  // fused into the tension tie and travelled as a single permanent part
  // drawn once, untransformed. The writer now sends the body once under
  // mechanism.anchor and a stamp per machine in the top-level anchors
  // array (plugin 95a31af), so a hundred anchors cost one mesh.
  //
  // `frame` only, never `placement`: this writer uses placement for the
  // LABEL "instance", and reading that as a frame found a string on every
  // anchor and reported them all unreadable.
  const anchors = [];
  for (const entry of Array.isArray(document.anchors) ? document.anchors : []) {
    const matrix = placementMatrix(entry && entry.frame, scale);
    if (!matrix) {
      notes.push("an anchor carried no readable placement frame");
      continue;
    }
    const held = entry && (entry.net_vertices || entry.netVertices);
    anchors.push({
      side: Number.isInteger(entry.side) ? entry.side : 0,
      mechanism: Number.isInteger(entry.mechanism) ? entry.mechanism : 0,
      // The net vertices this anchor's bank holds. Read and carried even
      // though nothing draws to them yet: they are what a cable running
      // down to its anchor would be drawn from, and an unread key is the
      // earliest signal that the layout moved.
      netVertices: Array.isArray(held) ? held.filter(Number.isInteger) : [],
      // null when he has authored no anchor body. The FRAMES still stand
      // in that case, and are worth having on their own: they are a rail
      // a reader holding its own anchor asset can stamp onto.
      ref: typeof entry.ref === "string" ? entry.ref : null,
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

  // Param settled this on 2026-09-09 after asking for all three readings
  // in one evening: "yes i offset and you use it as centerline. only if
  // you need the wire start include it, otherwise i will just use the same
  // wire framing."
  //
  // HE offsets the routing planes in Grasshopper, so what arrives IS the
  // cable's centreline and this reader adds nothing. His "top of the
  // circle" of an hour earlier is superseded, and taking a radius off
  // planes he has already pushed out would land the cable half inside the
  // drum -- the same failure the contact reading produced, reached from
  // the other side.
  //
  // He rules it this way rather than asking the studio to offset because
  // the cable cuts through the FRAME as well as the drums, and away from a
  // drum there is no axis for a reader to offset about. Only his own
  // offsetting fixes it everywhere, which is why "centreline" is both the
  // default and the reading his exporter now declares.
  //
  const meaning = typeof document.routingFrameMeaning === "string"
    ? document.routingFrameMeaning.toLowerCase() : "centreline";
  // THE CABLE, stated TWICE in the document from 2026-09-09: an explicit
  // cableRadius, and a cableThickness that is exactly twice it. That
  // redundancy is deliberate on both sides, because this one number was
  // halved or doubled by somebody three times in a day and a lone figure
  // does not say which convention it follows.
  //
  // He first said 0.01, then corrected himself to 0.02, and 0.02 is
  // ambiguous between a radius and a diameter in a way that decides the
  // drawing by a factor of two. It is settled as a RADIUS, and his own
  // Grasshopper offset proves it without anyone having to be asked: an
  // offset from the contact surface out to the centreline IS the radius,
  // and he offsets by 0.02.
  //
  // The explicit radius wins; a thickness is halved only for a file that
  // predates it; his settled figure stands in for a file with neither,
  // rather than the 0.01 he has since corrected.
  const cableRadius = Number.isFinite(+document.cableRadius)
    ? +document.cableRadius * scale
    : (Number.isFinite(+document.cableThickness)
      ? +document.cableThickness * scale / 2 : DEFAULT_CABLE_RADIUS);
  return { ok: true, scale, parts, instances, wires, anchors, notes,
    routingFrameMeaning: meaning, cableRadius,
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

// ---------- the wire centreline ----------
// Measured on the real document (2026-09-09): every routing frame's
// origin sits ON the drum's contact surface, not on the wire's
// centreline. The spools' frames stand 0.049988 m from their axis against
// a barrel of 0.0500; the pulleys' at exactly 0.170 / 0.200 / 0.300
// against groove bottoms of 0.170 / 0.200 / 0.300. A tube drawn on those
// origins is half inside the drum, which is the "crops through
// everything" Param saw. So the centreline is the contact line pushed out
// by one wire radius, RADIALLY FROM THE DRUM AXIS at every reel-owned
// frame -- never along the frame's own x or y, whose orientation the
// measurement found arbitrary on the spools and sign-inconsistent on the
// pulleys -- and blended linearly across the straight runs between reels,
// ramping from zero at the net end where the wire leaves an anchor.
//
// The same measurement found the spools sampled at 4.9 frames per turn
// (73.6 degrees a step), so a straight loft draws a five-sided polygon
// 10 mm inside the true helix. Reel-owned spans are subdivided by
// ROTATION ABOUT THE DRUM AXIS: the radial direction turned through the
// signed angle between the two frames, the axial coordinate and radius
// lerped. Eight steps on a spool and four on a pulley bring the chord sag
// under 0.2 mm everywhere.
export const SPOOL_STEPS = 8;
export const PULLEY_STEPS = 4;
export const SPOOL_RADIUS_LIMIT = 0.1;   // below this a drum counts as a spool

// His settled cable, for a document that states neither figure. A RADIUS:
// 0.02, which is also the size the studio draws the net's own cables at,
// so the machine's wire meets the net without a step.
export const DEFAULT_CABLE_RADIUS = 0.02;

function originOf(frame) {
  return [frame.matrix[12], frame.matrix[13], frame.matrix[14]];
}

// Where a point stands relative to a drum axis: how far along it, and the
// radial vector square to it.
function aboutAxis(point, axis) {
  const u = axis.direction;
  const dx = point[0] - axis.origin[0];
  const dy = point[1] - axis.origin[1];
  const dz = point[2] - axis.origin[2];
  const along = dx * u[0] + dy * u[1] + dz * u[2];
  const radial = [dx - u[0] * along, dy - u[1] * along, dz - u[2] * along];
  return { along, radial, radius: Math.hypot(radial[0], radial[1], radial[2]) };
}

// The radius a reel actually winds at: the median distance of the route
// frames it owns from its own axis. On the real file that is 0.050 for
// the spools and 0.170 / 0.200 / 0.300 for the pulleys, while the
// document's spoolRadius says 0.030 and matches nothing in it. null when
// no frame names the reel.
export function reelContactRadius(wires, reelIndex, axis) {
  const radii = [];
  for (const wire of wires) {
    for (const frame of wire.route) {
      if (frame.owner !== "reel" || frame.ownerReel !== reelIndex) continue;
      radii.push(aboutAxis(originOf(frame), axis).radius);
    }
  }
  if (!radii.length) return null;
  radii.sort((a, b) => a - b);
  return radii[Math.floor(radii.length / 2)];
}

// Rodrigues: v turned about the unit axis u by angle.
function turn(v, u, angle) {
  const c = Math.cos(angle), s = Math.sin(angle);
  const dot = u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
  const cx = u[1] * v[2] - u[2] * v[1];
  const cy = u[2] * v[0] - u[0] * v[2];
  const cz = u[0] * v[1] - u[1] * v[0];
  return [
    v[0] * c + cx * s + u[0] * dot * (1 - c),
    v[1] * c + cy * s + u[1] * dot * (1 - c),
    v[2] * c + cz * s + u[2] * dot * (1 - c),
  ];
}

// The wire's centreline as a list of [x, y, z] points in the body's own
// space. `reelAxes` maps a reel index to {origin, direction}.
//
// `surfaceOffset` moves each drum-owned frame radially by that much:
// POSITIVE is away from the drum axis, NEGATIVE towards it. The three
// readings a document can declare are
//
//   "top"        the frame is the top of the cable's section, so the
//                centreline is one radius IN   (negative) -- his ruling
//   "centreline" the frame is the centreline, so nothing moves (zero)
//   "contact"    the frame is where the cable touches the drum, so the
//                centreline is one radius OUT  (positive)
//
// The measured evidence (spool frames at 0.049988 against a 0.0500
// barrel) is recorded in the contract; his eye on the wrapped cable
// settles it over the measurement.
export function wireCentreline(route, reelAxes, surfaceOffset) {
  const n = route.length;
  if (!n) return [];
  const offsets = new Array(n).fill(null);
  const known = [];
  for (let i = 0; i < n; i++) {
    const frame = route[i];
    const axis = frame.owner === "reel" ? reelAxes[frame.ownerReel] : null;
    if (!axis) continue;
    const about = aboutAxis(originOf(frame), axis);
    if (about.radius < 1e-9) continue;
    const k = (+surfaceOffset || 0) / about.radius;
    offsets[i] = [about.radial[0] * k, about.radial[1] * k, about.radial[2] * k];
    known.push(i);
  }
  // Straight runs: blend between the offsets at either end. Before the
  // first drum the wire is leaving an anchor, so it ramps from nothing;
  // after the last it holds.
  for (let i = 0; i < n; i++) {
    if (offsets[i]) continue;
    let before = -1, after = -1;
    for (const k of known) {
      if (k < i) before = k;
      else { after = k; break; }
    }
    if (before === -1 && after === -1) {
      offsets[i] = [0, 0, 0];
    } else if (before === -1) {
      const f = i / after;
      offsets[i] = offsets[after].map((c) => c * f);
    } else if (after === -1) {
      offsets[i] = offsets[before].slice();
    } else {
      const f = (i - before) / (after - before);
      offsets[i] = offsets[before].map((c, j) => c + (offsets[after][j] - c) * f);
    }
  }

  const points = [];
  for (let i = 0; i < n; i++) {
    const frame = route[i];
    const o = originOf(frame);
    const here = [o[0] + offsets[i][0], o[1] + offsets[i][1], o[2] + offsets[i][2]];
    points.push(here);
    const next = route[i + 1];
    if (!next || frame.owner !== "reel" || next.owner !== "reel"
        || frame.ownerReel !== next.ownerReel) continue;
    const axis = reelAxes[frame.ownerReel];
    if (!axis) continue;
    // Both ends about the drum axis, each already pushed out by the wire
    // radius, then the arc between them walked in steps.
    const nextO = originOf(next);
    const there = [nextO[0] + offsets[i + 1][0], nextO[1] + offsets[i + 1][1],
      nextO[2] + offsets[i + 1][2]];
    const a = aboutAxis(here, axis);
    const b = aboutAxis(there, axis);
    if (a.radius < 1e-9 || b.radius < 1e-9) continue;
    const ra = a.radial.map((c) => c / a.radius);
    const rb = b.radial.map((c) => c / b.radius);
    const u = axis.direction;
    const cx = ra[1] * rb[2] - ra[2] * rb[1];
    const cy = ra[2] * rb[0] - ra[0] * rb[2];
    const cz = ra[0] * rb[1] - ra[1] * rb[0];
    const angle = Math.atan2(cx * u[0] + cy * u[1] + cz * u[2],
      ra[0] * rb[0] + ra[1] * rb[1] + ra[2] * rb[2]);
    const steps = a.radius < SPOOL_RADIUS_LIMIT ? SPOOL_STEPS : PULLEY_STEPS;
    for (let s = 1; s < steps; s++) {
      const f = s / steps;
      const r = turn(ra, u, angle * f);
      const radius = a.radius + (b.radius - a.radius) * f;
      const along = a.along + (b.along - a.along) * f;
      points.push([
        axis.origin[0] + u[0] * along + r[0] * radius,
        axis.origin[1] + u[1] * along + r[1] * radius,
        axis.origin[2] + u[2] * along + r[2] * radius,
      ]);
    }
  }
  return points;
}

// ---------- the take-up ----------
// The contract measures take-up as the FREE SPAN from the net vertex to
// the wire's first routing frame. On the real file that span is zero at
// every frame: the route's first frame IS the anchor (gap 0.0000 m,
// measured) and the anchors are the net's fixed supports, which do not
// move. Read that way the reels stood still -- Param's "no animation
// either".
//
// What does shorten is the RIB: the run of net cable that leaves the
// anchor and climbs over the vault. Reeling in tightens it, which is what
// "the ribs reel in" means, and its length is in every frame the formwork
// already carries. So the take-up is measured along the rib. Both
// machines pull on one rib, one from each end, so each is credited with
// half.
//
// These two take vertices as TRIPLES, the frames' own convention, so the
// hot path does not flatten 441 points every frame.

// The chain of net vertices a rib runs through, chosen on the FINAL pose
// (topology does not change between frames): from the anchor, step to
// the neighbour that stands highest, then keep the straightest
// continuation until the chain runs out or turns away.
export function ribChain(edges, finalVertices, start) {
  const next = new Map();
  const link = (a, b) => {
    if (!next.has(a)) next.set(a, []);
    next.get(a).push(b);
  };
  for (const edge of edges) {
    const u = edge[0], v = edge[1];
    if (!Number.isInteger(u) || !Number.isInteger(v)) continue;
    link(u, v); link(v, u);
  }
  const at = (i) => finalVertices[i];
  const chain = [start];
  const seen = new Set(chain);
  let candidates = (next.get(start) || []).filter((n) => at(n));
  if (!candidates.length) return chain;
  // Up first: the rim runs level, the rib climbs.
  let current = candidates.reduce((best, n) => (at(n)[2] > at(best)[2] ? n : best));
  chain.push(current);
  seen.add(current);
  let previous = start;
  for (let guard = 0; guard < 2000; guard++) {
    const p = at(previous), c = at(current);
    const dx = c[0] - p[0], dy = c[1] - p[1], dz = c[2] - p[2];
    const dl = Math.hypot(dx, dy, dz) || 1;
    let bestDot = -Infinity, bestNext = -1;
    for (const n of next.get(current) || []) {
      if (seen.has(n) || !at(n)) continue;
      const q = at(n);
      const ex = q[0] - c[0], ey = q[1] - c[1], ez = q[2] - c[2];
      const el = Math.hypot(ex, ey, ez) || 1;
      const dot = (dx * ex + dy * ey + dz * ez) / (dl * el);
      if (dot > bestDot) { bestDot = dot; bestNext = n; }
    }
    // A turn sharper than about 78 degrees is the rib ending at a rim,
    // not continuing.
    if (bestNext === -1 || bestDot < 0.2) break;
    chain.push(bestNext);
    seen.add(bestNext);
    previous = current;
    current = bestNext;
  }
  return chain;
}

export function chainLength(vertices, chain) {
  let length = 0;
  for (let i = 0; i + 1 < chain.length; i++) {
    const a = vertices[chain[i]], b = vertices[chain[i + 1]];
    if (!a || !b) continue;
    length += Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  }
  return length;
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
