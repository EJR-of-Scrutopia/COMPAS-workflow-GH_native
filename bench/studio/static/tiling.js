// ---------- breaking the repeat ----------
// Param, 2026-09-12: "at the moment randomise uv just rotates all uv to
// a random orientation. but what it should mean is every instance
// randomises, so that the repeating is different throughout and it
// helps to hide some of the errors where repetition is too noticable on
// surfaces."
//
// He is right, and the distinction is the whole of this file. Turning
// the floor's UVs re-lays the sheet: the same picture arrives at a
// different angle, and every repeat of it within the sheet is still the
// same repeat. A floor sixty metres across showing a two metre picture
// is thirty copies each way, and the eye finds that grid at once -- one
// bright pebble, or one crack, printed nine hundred times in rows.
//
// WHAT ACTUALLY FIXES IT is reading the picture from a different place
// per tile and blending the joins away. This is Heitz and Neyret's
// by-example noise (2018): lay a triangular lattice over the surface,
// give every lattice vertex its own random offset into the picture, and
// at any point blend the three vertices whose triangle it falls in,
// weighted by how near it is to each. No point on the floor is more than
// one triangle from a completely different part of the picture, and
// there is no seam anywhere, because the weights are continuous.
//
// OFFSETS ONLY, NOT ROTATIONS. Turning each tile as well hides more, and
// it is what the technique is usually shown doing on gravel -- but it
// destroys any picture with a direction in it. Wood grain turned 37
// degrees per tile is not wood, and a herringbone is not a herringbone.
// An offset cannot do that to any picture, so this works on the whole
// library rather than on the stony half of it. It also means a normal
// map's taps can be blended directly: a tangent-space normal is only
// wrong under a rotation, and there is none here.
//
// THE BLEND HAS TO KEEP THE CONTRAST. Three pictures averaged together
// have two thirds less variance than one, so a naive blend makes the
// floor go soft and grey in the middle of every triangle -- the standard
// complaint about this technique. Each tap's difference from the
// picture's own MEAN is blended instead, and the sum divided by the
// length of the weight vector rather than by its total. At a lattice
// vertex that is exactly the tap itself; in the middle of a triangle it
// restores the variance that averaging took out. The mean costs nothing
// to know: it is the one texel of the smallest mip, which every one of
// these textures has (pbr.js leaves minFilter alone precisely so that
// anisotropy works).
//
// The lattice and the hash are written twice, once here in JS and once
// in the GLSL below, because a GPU cannot be asked what it did. The JS
// is the testable twin -- the same arrangement atmosphere.js uses for
// the fog integral, and for the same reason.

// A lattice cell is about one repeat of the picture across. Finer and
// the blend regions overlap into mush; coarser and the grid being hidden
// starts to show through the lattice's own.
export const LATTICE_SCALE = 1.0;

// How hard the weights favour the nearest vertex before the variance is
// restored. One is the raw barycentric blend, which is what the paper
// uses; a little above one narrows the band that is blending at all,
// which costs nothing and leaves more of the floor showing one tap
// exactly. Past about four the bands become narrow enough to read as
// ribbons, which is the fault this is avoiding.
export const BLEND_SHARPNESS = 2.0;

// The skew that turns a square grid into a triangular one: the second
// axis leans by 30 degrees and stretches by 2/sqrt(3), so the unit cell
// becomes two equilateral triangles.
const SKEW_UV = -0.5773502691896258;   // -1/sqrt(3)
const SKEW_VV = 1.1547005383792517;    //  2/sqrt(3)

/**
 * Which three lattice vertices a point falls between, and how much of
 * each. The exact twin of tilingWeights() in the GLSL below.
 *
 * The unit cell of the skewed lattice is a rhombus split by its own
 * diagonal into a lower and an upper triangle, and which one a point is
 * in is decided by whether its two fractional coordinates sum past one.
 * Both branches are written so that a point ON the diagonal gets the
 * same answer either way, which is what makes the blend continuous
 * rather than merely smooth-looking.
 *
 * @param {number} u
 * @param {number} v
 * @returns {{cells: number[][], weights: number[]}} three integer cells
 *   and three weights that sum to one and are never negative.
 */
export function hexWeights(u, v) {
  const su = u + SKEW_UV * v;
  const sv = SKEW_VV * v;
  const bu = Math.floor(su);
  const bv = Math.floor(sv);
  const fu = su - bu;
  const fv = sv - bv;
  if (fu + fv < 1.0) {
    return { cells: [[bu, bv], [bu, bv + 1], [bu + 1, bv]],
      weights: [1.0 - fu - fv, fv, fu] };
  }
  return { cells: [[bu + 1, bv + 1], [bu + 1, bv], [bu, bv + 1]],
    weights: [fu + fv - 1.0, 1.0 - fv, 1.0 - fu] };
}

/**
 * A lattice vertex's own offset into the picture, in [0, 1) of one
 * repeat. The twin of tilingHash2() in the GLSL.
 *
 * Dave Hoskins' hash22, and NOT the sine-and-fract hash every shader
 * reaches for first. A GPU computes in 32 bit floats, and sin() of a
 * large argument in 32 bits has lost most of its meaning: measured here,
 * the sine hash put adjacent cells within a hundredth of a repeat of one
 * another often enough to leave the repetition visible in patches. This
 * one uses no trigonometry and was built for 32 bit floats.
 *
 * The JS is a model of the arithmetic, not a bit-for-bit copy of it: the
 * GPU works in single precision and this in double, so the two offsets
 * differ in the last few bits. That is a hair's difference in where one
 * tile reads from, which is exactly the quantity this function is
 * choosing at random in the first place.
 */
export function tileOffset(cellU, cellV, seedU = 0, seedV = 0) {
  const fract = (x) => x - Math.floor(x);
  const u = cellU + seedU;
  const v = cellV + seedV;
  let p0 = fract(u * 0.1031);
  let p1 = fract(v * 0.1030);
  let p2 = fract(u * 0.0973);
  const d = p0 * (p1 + 33.33) + p1 * (p2 + 33.33) + p2 * (p0 + 33.33);
  p0 += d;
  p1 += d;
  p2 += d;
  return [fract((p0 + p1) * p2), fract((p0 + p2) * p1)];
}

/**
 * The blend weights, sharpened and renormalised. A weight of zero stays
 * zero and a weight of one stays one, so a point at a vertex still shows
 * that vertex and nothing else.
 */
export function sharpenWeights(weights, sharpness = BLEND_SHARPNESS) {
  const raised = weights.map((w) => Math.pow(Math.max(0, w), sharpness));
  const total = raised[0] + raised[1] + raised[2];
  if (!(total > 0)) return [1, 0, 0];
  return raised.map((w) => w / total);
}

/**
 * What the shader shows at one point, given a function saying what the
 * picture holds at a UV and the picture's own mean. The twin of
 * tilingSample(), used by the tests to hold the arithmetic and by
 * nothing at runtime.
 */
export function blendAt(u, v, sample, mean, seed = [0, 0],
                        sharpness = BLEND_SHARPNESS) {
  const { cells, weights } = hexWeights(u * LATTICE_SCALE, v * LATTICE_SCALE);
  const w = sharpenWeights(weights, sharpness);
  let sum = 0;
  for (let i = 0; i < 3; i++) {
    const [du, dv] = tileOffset(cells[i][0], cells[i][1], seed[0], seed[1]);
    sum += w[i] * (sample(u + du, v + dv) - mean);
  }
  const length = Math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]);
  return mean + sum / Math.max(length, 1e-6);
}

// The GLSL twin, injected once per material that wants it, above the
// first chunk that could call it.
//
// texture2DGradEXT, not texture2D: three's WebGL2 prefix defines it as
// textureGrad, and the gradients handed in are the ORIGINAL uv's. The
// hardware picks a mip level from the rate of change of the coordinate
// it is given, and this coordinate jumps by a whole random offset at
// every triangle edge -- so left to itself the hardware sees an enormous
// rate of change there and drops to the blurriest mip in a line along
// every edge in the lattice. The smooth coordinate's own gradients are
// what keep the floor sharp.
//
// LOD 20 is past the last mip of any texture that will ever be loaded
// here, and sampling past the last mip clamps to it: one texel holding
// the average of the whole picture.
export const TILING_GLSL = /* glsl */ `
uniform vec2 tileSeed;
uniform float tileLattice;
uniform float tileSharpness;

vec2 tilingHash2( vec2 p ) {
  vec3 q = fract( vec3( p.xyx ) * vec3( 0.1031, 0.1030, 0.0973 ) );
  q += dot( q, q.yzx + 33.33 );
  return fract( ( q.xx + q.yz ) * q.zy );
}

void tilingWeights( vec2 uv, out vec2 c0, out vec2 c1, out vec2 c2, out vec3 w ) {
  vec2 s = vec2( uv.x - 0.5773502691896258 * uv.y, 1.1547005383792517 * uv.y );
  vec2 base = floor( s );
  vec2 f = s - base;
  if ( f.x + f.y < 1.0 ) {
    c0 = base;
    c1 = base + vec2( 0.0, 1.0 );
    c2 = base + vec2( 1.0, 0.0 );
    w = vec3( 1.0 - f.x - f.y, f.y, f.x );
  } else {
    c0 = base + vec2( 1.0, 1.0 );
    c1 = base + vec2( 1.0, 0.0 );
    c2 = base + vec2( 0.0, 1.0 );
    w = vec3( f.x + f.y - 1.0, 1.0 - f.y, 1.0 - f.x );
  }
  w = pow( max( w, vec3( 0.0 ) ), vec3( tileSharpness ) );
  w /= max( w.x + w.y + w.z, 1e-6 );
}

vec4 tilingSample( sampler2D picture, vec2 uv ) {
  vec2 dx = dFdx( uv );
  vec2 dy = dFdy( uv );
  vec2 c0, c1, c2;
  vec3 w;
  tilingWeights( uv * tileLattice, c0, c1, c2, w );
  vec4 mean = texture2DLodEXT( picture, vec2( 0.5 ), 20.0 );
  vec4 sum =
      w.x * ( texture2DGradEXT( picture, uv + tilingHash2( c0 + tileSeed ), dx, dy ) - mean )
    + w.y * ( texture2DGradEXT( picture, uv + tilingHash2( c1 + tileSeed ), dx, dy ) - mean )
    + w.z * ( texture2DGradEXT( picture, uv + tilingHash2( c2 + tileSeed ), dx, dy ) - mean );
  // Divided by the LENGTH of the weight vector, not by its total, which
  // is what restores the variance that averaging took out. Clamped,
  // because restoring variance can push a value that was already near
  // the end of its range past it.
  return clamp( mean + sum * inversesqrt( max( dot( w, w ), 1e-6 ) ),
                vec4( 0.0 ), vec4( 1.0 ) );
}
`;

// Every chunk that samples one of the floor's maps, and the call that
// replaces it.
//
// bumpMap is deliberately absent. three reads it three times to take its
// own finite difference (dHdxy_fwd), and a difference taken across a
// lattice edge is a difference between two unrelated parts of the
// picture, which would draw a ridge along every edge in the lattice. The
// library's floors carry normal maps; a floor carrying only a height map
// would keep its repeat in the relief alone, and installTiling says so
// out loud rather than quietly looking wrong.
export const TILED_CHUNKS = [
  ["map_fragment", "texture2D( map, vMapUv )", "tilingSample( map, vMapUv )"],
  ["roughnessmap_fragment", "texture2D( roughnessMap, vRoughnessMapUv )",
    "tilingSample( roughnessMap, vRoughnessMapUv )"],
  ["metalnessmap_fragment", "texture2D( metalnessMap, vMetalnessMapUv )",
    "tilingSample( metalnessMap, vMetalnessMapUv )"],
  ["aomap_fragment", "texture2D( aoMap, vAoMapUv )",
    "tilingSample( aoMap, vAoMapUv )"],
  ["normal_fragment_maps", "texture2D( normalMap, vNormalMapUv )",
    "tilingSample( normalMap, vNormalMapUv )"],
];

/**
 * Rewrite one shader so its map reads go through the lattice.
 *
 * onBeforeCompile hands over the source with its `#include <...>` lines
 * STILL UNRESOLVED -- three expands them afterwards -- so the chunk text
 * is not in the string yet and cannot be edited in place. Each include
 * is replaced by its own chunk with the sampling swapped, which is also
 * why the chunk table is handed in: THREE.ShaderChunk is the only place
 * that text exists, and this file takes three as an argument rather than
 * importing it, exactly as atmosphere.js does.
 *
 * Returns how many chunks were actually rewritten, so a caller can say
 * something out loud when a three upgrade moves one out from under this,
 * rather than quietly going back to a repeating floor.
 */
export function applyTiling(shader, chunks, uniforms) {
  Object.assign(shader.uniforms, uniforms);
  shader.fragmentShader = shader.fragmentShader.replace(
    "void main() {", TILING_GLSL + "\nvoid main() {");
  let rewritten = 0;
  for (const [name, from, to] of TILED_CHUNKS) {
    const include = "#include <" + name + ">";
    const source = chunks[name];
    if (!source || !source.includes(from)) continue;
    if (!shader.fragmentShader.includes(include)) continue;
    // split/join, not replace: normal_fragment_maps samples the map
    // twice, once per branch, and replace would take only the first.
    shader.fragmentShader = shader.fragmentShader.replace(
      include, source.split(from).join(to));
    rewritten += 1;
  }
  return rewritten;
}
