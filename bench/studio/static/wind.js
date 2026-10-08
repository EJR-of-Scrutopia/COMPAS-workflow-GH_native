// ---------- wind ----------
// Param, 2026-09-13: "add in wind and movement of the objects ... getting
// shadows right with that is the key to sell it."
//
// WHERE THE MOVEMENT HAPPENS decides whether the shadows move with it. A
// prop is an instance of a baked model, drawn once for the picture and once
// more for every light's shadow map, and those are different materials: the
// picture wears the model's own, the shadow a depth material three picks.
// Sway written into only the first leaves every shadow standing still under
// a moving tree, which is exactly what gives a fake wind away. So the sway
// lives here, once, and the SAME function is spliced into both: the prop's
// own materials, and a depth material the studio hands each batch as its
// customDepthMaterial (three uses that one directly, copying each part's
// map and alpha test onto it per draw, so leaf cards still cut their
// shadows out as they move).
//
// THE MOTION, in the manner of Unreal's simple grass wind and a SpeedTree
// without its branch hierarchy, which a baked model does not carry:
//
//   a LEAN downwind, growing with the square of height above the model's
//   feet, so the base stays planted and the tip travels furthest;
//   a SWAY about that lean at the model's own frequency, slow for a tall
//   tree and quick for a blade of grass, each instance a little out of step
//   with its neighbours;
//   GUSTS, fronts of stronger wind that sweep across the site downwind, so
//   a field moves in waves rather than in unison;
//   FLUTTER on the alpha-tested cards only -- leaves and blades -- small
//   and fast, which bark and trunks never get;
//   and the tip comes DOWN as it leans, so a bent stem does not grow longer.
//
// It imports nothing, so node runs the arithmetic in tests/studio/test_wind.py.

// How far a model's tip leans at full strength, as a share of its height:
// a blade of grass a fifth of itself, a thirty metre beech a fiftieth.
export const WIND_BEND_SHORT = 0.22;
export const WIND_BEND_TALL = 0.02;
// And how often it sways, in cycles a second.
export const WIND_FREQUENCY_SHORT = 1.4;
export const WIND_FREQUENCY_TALL = 0.22;
// The side-to-side wobble, as a share of the lean.
export const WIND_ACROSS = 0.22;
// Leaf flutter at full strength, metres, before the model's own scale, and
// never more than this share of the model's height.
export const WIND_FLUTTER_METRES = 0.04;
export const WIND_FLUTTER_SHARE = 0.15;

function smoothstep(edge0, edge1, x) {
  const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

// A model's own wind, from how tall it stands.
export function windParameters(heightMetres) {
  const h = Math.max(0.01, +heightMetres || 1);
  const tall = smoothstep(0.5, 12, h);
  return {
    height: h,
    bend: WIND_BEND_SHORT + (WIND_BEND_TALL - WIND_BEND_SHORT) * tall,
    frequency: WIND_FREQUENCY_SHORT
      + (WIND_FREQUENCY_TALL - WIND_FREQUENCY_SHORT) * smoothstep(0.5, 15, h),
  };
}

// The dials as the shader's numbers: strength and gusts as fractions, and
// the direction the air MOVES as a unit vector. The dial names where the
// wind comes FROM, measured as the sun's azimuth is, from +x toward +y.
export function windUniformsFrom(settings) {
  const strength = Math.max(0, Math.min(1, (+settings.strength || 0) / 100));
  const gusts = Math.max(0, Math.min(1, (+settings.gusts || 0) / 100));
  const from = ((+settings.from || 0) * Math.PI) / 180;
  return { strength, gusts, direction: [-Math.cos(from), -Math.sin(from)] };
}

// A light breeze by default. Param, 2026-09-14: "have the wind on as
// default set to like 10%". A scene saved before the wind existed comes back
// in the same breeze.
export const WIND_DEFAULTS = { strength: 10, from: 225, gusts: 50 };
export const WIND_RANGES = { strength: [0, 100], from: [0, 360], gusts: [0, 100] };

// A saved scene's wind, clamped, and still a calm for a scene from before.
export function adoptWind(saved) {
  const wind = { ...WIND_DEFAULTS };
  if (!saved || typeof saved !== "object") return wind;
  for (const [key, [low, high]] of Object.entries(WIND_RANGES)) {
    const value = saved[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      wind[key] = Math.min(high, Math.max(low, value));
    }
  }
  return wind;
}

function hash(x, y) {
  let p0 = (x * 0.1031) % 1, p1 = (y * 0.1031) % 1, p2 = (x * 0.1031) % 1;
  if (p0 < 0) p0 += 1;
  if (p1 < 0) p1 += 1;
  if (p2 < 0) p2 += 1;
  const d = p0 * (p1 + 33.33) + p1 * (p2 + 33.33) + p2 * (p0 + 33.33);
  p0 += d; p1 += d; p2 += d;
  const v = ((p0 + p1) * p2) % 1;
  return v < 0 ? v + 1 : v;
}

// The offset of one vertex, in the JS twin of windOffset below. `local` is
// the vertex in the baked model's own metres (feet at z 0), `origin` where
// the instance stands, `scale` its uniform scale, `model` windParameters,
// `air` the wind at this instant: { time, strength, gusts, direction }.
export function windOffset(local, origin, scale, model, air, flutter = false) {
  if (air.strength <= 0) return [0, 0, 0];
  const [dx, dy] = air.direction;
  const height = Math.max(model.height * scale, 0.05);
  const above = Math.max(0, Math.min(1, (local[2] * scale) / height));
  const weight = above * above;
  const ax = -dy, ay = dx;
  const seed = hash(origin[0], origin[1]) * 2 * Math.PI;
  const front = origin[0] * dx + origin[1] * dy;
  const gust = 1 - air.gusts * (0.5 - 0.5 * Math.sin(front * 0.09 - air.time * 1.3
    + 2 * Math.sin((origin[0] * ax + origin[1] * ay) * 0.035 + air.time * 0.21)));
  const sway = 0.7 + 0.3 * Math.sin(air.time * model.frequency * 2 * Math.PI + seed);
  const reach = air.strength * model.bend * height * weight;
  const lean = reach * gust * sway;
  const wobble = reach * WIND_ACROSS * Math.sin(air.time * model.frequency * 4.7 + seed * 1.7);
  const out = [dx * lean + ax * wobble, dy * lean + ay * wobble, 0];
  // The tip comes down as it leans: a stem of height h bent sideways by s
  // drops by about s squared over 2h, never by more than half of itself.
  const up = Math.max(local[2] * scale, 0.05);
  out[2] = -Math.min((out[0] * out[0] + out[1] * out[1]) / (2 * up), 0.5 * up);
  if (flutter) {
    const amount = air.strength * gust * above
      * Math.min(WIND_FLUTTER_METRES * scale, WIND_FLUTTER_SHARE * height);
    out[0] += amount * Math.sin(air.time * 9.1 + local[0] * 7.1 + local[1] * 3.3 + local[2] * 5.7 + seed);
    out[1] += amount * Math.sin(air.time * 8.3 + local[0] * 2.9 + local[1] * 6.1 + local[2] * 4.3);
    out[2] += amount * 0.5 * Math.sin(air.time * 10.7 + local[0] * 5.3 + local[1] * 2.1 + local[2] * 7.9);
  }
  return out;
}

// The same, in GLSL, for the vertex stage of every material a prop is drawn
// with. `placing` is the instance matrix; the offset is added after it, in
// the props' own space, which is where the wind's direction is written.
export const WIND_GLSL = `
uniform float windTime;
uniform float windStrength;
uniform float windGusts;
uniform vec2 windDirection;
uniform float windHeight;
uniform float windBend;
uniform float windFrequency;
float windHash( vec2 p ) {
  vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
  p3 += dot( p3, p3.yzx + 33.33 );
  return fract( ( p3.x + p3.y ) * p3.z );
}
vec3 windOffset( vec3 local, mat4 placing ) {
  if ( windStrength <= 0.0 ) return vec3( 0.0 );
  vec3 origin = placing[ 3 ].xyz;
  float scale = length( placing[ 2 ].xyz );
  float height = max( windHeight * scale, 0.05 );
  float above = clamp( local.z * scale / height, 0.0, 1.0 );
  float weight = above * above;
  vec2 across = vec2( - windDirection.y, windDirection.x );
  float seed = windHash( origin.xy ) * 6.283185307;
  float front = dot( origin.xy, windDirection );
  float gust = 1.0 - windGusts * ( 0.5 - 0.5 * sin( front * 0.09 - windTime * 1.3
    + 2.0 * sin( dot( origin.xy, across ) * 0.035 + windTime * 0.21 ) ) );
  float sway = 0.7 + 0.3 * sin( windTime * windFrequency * 6.283185307 + seed );
  float reach = windStrength * windBend * height * weight;
  float lean = reach * gust * sway;
  float wobble = reach * WIND_ACROSS * sin( windTime * windFrequency * 4.7 + seed * 1.7 );
  vec3 offset = vec3( windDirection * lean + across * wobble, 0.0 );
  float up = max( local.z * scale, 0.05 );
  offset.z = - min( dot( offset.xy, offset.xy ) / ( 2.0 * up ), 0.5 * up );
  #ifdef WIND_FLUTTER
    float amount = windStrength * gust * above
      * min( WIND_FLUTTER_METRES * scale, WIND_FLUTTER_SHARE * height );
    offset += amount * vec3(
      sin( windTime * 9.1 + dot( local, vec3( 7.1, 3.3, 5.7 ) ) + seed ),
      sin( windTime * 8.3 + dot( local, vec3( 2.9, 6.1, 4.3 ) ) ),
      0.5 * sin( windTime * 10.7 + dot( local, vec3( 5.3, 2.1, 7.9 ) ) ) );
  #endif
  return offset;
}
`;

// The two places three moves a vertex by its instance: where it is drawn
// (project_vertex) and where its shadow coordinates and reflections are
// taken from (worldpos_vertex). Both get the offset, or a leaf is drawn in
// one place and shadowed as though it stood in another.
const PROJECT_AT = "mvPosition = instanceMatrix * mvPosition;";
const WORLD_AT = "worldPosition = instanceMatrix * worldPosition;";

// Splice the wind into a material's shader, in onBeforeCompile. `chunks` is
// THREE.ShaderChunk (passed in, so node can test this without three);
// `uniforms` the shared air and this model's own numbers, by reference.
// Answers how many of the two places it reached: a three that has moved
// either line is loud rather than quietly still.
export function applyWind(shader, chunks, uniforms) {
  Object.assign(shader.uniforms, uniforms);
  let reached = 0;
  const splice = (name, at) => {
    const include = "#include <" + name + ">";
    const source = chunks[name];
    if (!source || !source.includes(at) || !shader.vertexShader.includes(include)) return;
    shader.vertexShader = shader.vertexShader.replace(include,
      source.replace(at, at + "\n\t" + at.split(" = ")[0]
        + ".xyz += windOffset( transformed, instanceMatrix );"));
    reached += 1;
  };
  splice("project_vertex", PROJECT_AT);
  splice("worldpos_vertex", WORLD_AT);
  if (!reached) return 0;
  const defines = "#define WIND_ACROSS " + WIND_ACROSS.toFixed(4) + "\n"
    + "#define WIND_FLUTTER_METRES " + WIND_FLUTTER_METRES.toFixed(4) + "\n"
    + "#define WIND_FLUTTER_SHARE " + WIND_FLUTTER_SHARE.toFixed(4) + "\n"
    // Leaves and blades are alpha-tested cards; bark is not. The alpha test
    // is part of three's program key, so a card and a trunk get their own
    // programs and this is decided per program.
    + (shader.alphaTest ? "#define WIND_FLUTTER\n" : "");
  shader.vertexShader = shader.vertexShader.replace("void main() {",
    defines + WIND_GLSL + "\nvoid main() {");
  return reached;
}
