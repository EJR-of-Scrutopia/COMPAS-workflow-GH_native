// The atmosphere: an exponential height fog in the manner of Unreal's
// ExponentialHeightFog, for three r185's WebGL renderer.
//
// Param: "in the sky category we can add atmosphere, so add in a fog but
// super detailed nice fog we might find in the likes of unreal engine to
// get super clean renders". The fog three ships is linear in distance and
// blind to height, so a vault crown eight metres up fogged exactly like the
// ground at the same distance, and nothing glowed toward the sun.
//
// This module is pure: it imports nothing, and three is handed in by the
// caller. That is what lets node run the arithmetic below against its own
// limits (tests/studio/test_atmosphere.py) while the page runs the same
// arithmetic, written again in GLSL, on every fogged fragment.
//
// THE MODEL. Two layers of density, each falling off exponentially with
// height above a base: density(z) = k * exp(-f * (z - base)), with k in
// per metre and f = 1 / (the layer's e-fold height). Along a ray from the
// eye the optical depth has a closed form (no marching), the fog's opacity
// is 1 - exp(-depth), capped at a maximum, and the light it adds is the
// ambient colour (the scene's horizon) plus a lobe toward the sun,
// pow(cos, exponent), which begins at its own start distance. Distances
// and heights are metres; the scene is Z up.

// The picker's presets, in the dials' own units: /km, metres, per cent.
// First-pass numbers, tuned by eye in the live probe, not calibrated to
// Unreal's units (which are not metres).
export const ATMOSPHERE_PRESETS = {
  none: { label: "None" },
  "clear-air": {
    label: "Clear air", density: 1.5, height: 60, base: 0, start: 30,
    maxOpacity: 50, sunGlow: 40, sunLobe: 8, sunStart: 30, mist: 0, mistHeight: 2,
    shafts: 0,
  },
  "morning-mist": {
    label: "Morning mist", density: 0.8, height: 40, base: 0, start: 0,
    maxOpacity: 95, sunGlow: 120, sunLobe: 6, sunStart: 0, mist: 20, mistHeight: 1.7,
    shafts: 0,
  },
  haze: {
    label: "Haze", density: 6, height: 25, base: 0, start: 0,
    maxOpacity: 80, sunGlow: 150, sunLobe: 12, sunStart: 10, mist: 0, mistHeight: 2,
    shafts: 0,
  },
  "valley-fog": {
    label: "Valley fog", density: 1.2, height: 30, base: 0, start: 0,
    maxOpacity: 97, sunGlow: 80, sunLobe: 8, sunStart: 0, mist: 50, mistHeight: 1.5,
    shafts: 0,
  },
};

// Every tunable number, with the range its dial allows. The page's dials
// carry the same min and max (a test holds the two together), and a saved
// scene is clamped into them on the way back in.
export const ATMOSPHERE_RANGES = {
  density: [0, 50],       // /km, the main layer at its base
  height: [0.5, 200],     // m, the main layer's e-fold height
  base: [-5, 50],         // m above the floor where both layers are densest
  start: [0, 100],        // m from the eye before any fog begins
  maxOpacity: [0, 100],   // per cent, the most the fog may ever hide
  sunGlow: [0, 200],      // per cent of the sun's own light, scattered toward the eye
  sunLobe: [1, 64],       // x, the lobe's exponent: higher is a tighter glow
  sunStart: [0, 200],     // m from the eye before the sun's glow begins
  mist: [0, 100],         // /km, the ground mist at its base
  mistHeight: [0.2, 20],  // m, the ground mist's e-fold height
  shafts: [0, 100],       // per cent, the light shafts through the fog (desktop only)
};

export const ATMOSPHERE_KEYS = Object.keys(ATMOSPHERE_RANGES);

// How far away the sky is, for the fog laid over it. The Sky mesh sits at
// the far plane, so it has no distance of its own; two kilometres is where
// the ground would be if the floor went on, and it saturates every preset
// but Clear air, which is capped well short of hiding the sky anyway.
export const ATMOSPHERE_SKY_DISTANCE = 2000;

// The distance the old linear fog is pushed to when the atmosphere owns
// the fog: smoothstep(near, far, d) is then zero for anything on screen.
export const ATMOSPHERE_LINEAR_OFF = 1e7;

// A preset's settings, as the object state.atmosphere holds. None keeps the
// Clear air numbers underneath, so the dials have values to show the
// moment another preset is chosen.
export function atmosphereFromPreset(key) {
  const chosen = ATMOSPHERE_PRESETS[key] && key !== "none" ? key : "none";
  const values = ATMOSPHERE_PRESETS[chosen === "none" ? "clear-air" : chosen];
  const settings = { preset: chosen };
  for (const name of ATMOSPHERE_KEYS) settings[name] = values[name];
  return settings;
}

// A saved scene's atmosphere, made safe: an unknown preset, a missing key
// or a number out of range falls back rather than reaching a shader. A
// scene saved before the atmosphere existed has none, and loads as None.
export function adoptAtmosphere(saved) {
  if (!saved || typeof saved !== "object" || !ATMOSPHERE_PRESETS[saved.preset]) {
    return atmosphereFromPreset("none");
  }
  const settings = atmosphereFromPreset(saved.preset);
  for (const name of ATMOSPHERE_KEYS) {
    const value = saved[name];
    if (typeof value !== "number" || !Number.isFinite(value)) continue;
    const [low, high] = ATMOSPHERE_RANGES[name];
    settings[name] = Math.min(high, Math.max(low, value));
  }
  return settings;
}

export function atmosphereIsOn(settings) {
  return !!settings && settings.preset !== "none" && !!ATMOSPHERE_PRESETS[settings.preset];
}

// The dial units turned into the shader's: per metre, per metre, metres,
// fractions. floor is the scene's floor height, which the base sits on.
export function atmosphereLayers(settings, floor = 0) {
  return {
    density: [settings.density / 1000, settings.mist / 1000],
    falloff: [1 / Math.max(1e-3, settings.height), 1 / Math.max(1e-3, settings.mistHeight)],
    base: floor + settings.base,
    start: settings.start,
    maxOpacity: settings.maxOpacity / 100,
    sunStart: settings.sunStart,
    sunExponent: settings.sunLobe,
    sunGlow: settings.sunGlow / 100,
  };
}

// ---------- the integral, in JS (the twin of the GLSL below) ----------
// One layer's optical depth over a ray segment of length d that starts at
// height h0 above the base and climbs dz per metre. The closed form is
// density * (exp(-f h0) - exp(-f h1)) / (f dz), written here as
// density * exp(-f h0) * d * (1 - exp(-f dz d)) / (f dz d): the density
// where the segment starts, times its length, times how much of that the
// segment keeps as it climbs (or gains as it falls). Wherever f dz d is
// tiny its Taylor series stands in, which is also the exact answer when
// f = 0 (plain exponential distance fog). Each exponent is capped, as in
// the shader, where 32-bit floats would otherwise overflow deep in the fog.
// The two capped factors multiply and never subtract: written as a
// difference, a ray starting and ending deep under the base had both terms
// capped to the same number and came out with no fog at all, so thinning
// the mist there turned a whiteout clear. Multiplied, the deepest answer
// is at most 0.05 * e^40 * d * e^40 / 40, far inside a float for any d.
const EXPONENT_CAP = 40;

export function layerOpticalDepth(density, falloff, h0, dz, d) {
  if (density <= 0 || d <= 0) return 0;
  const fall = falloff * dz * d;
  const e0 = Math.exp(Math.min(-falloff * h0, EXPONENT_CAP));
  if (Math.abs(fall) > 1e-3) {
    const through = (1 - Math.exp(Math.min(-fall, EXPONENT_CAP))) / fall;
    return density * e0 * d * through;
  }
  return density * e0 * d * (1 - 0.5 * fall);
}

// Both layers, from the eye at cameraZ along a unit ray whose vertical
// component is dirZ, over length metres, beginning start metres out.
export function atmosphereOpticalDepth(layers, cameraZ, dirZ, length, start) {
  const d = Math.max(length - start, 0);
  const h0 = cameraZ + dirZ * Math.min(start, length) - layers.base;
  return layerOpticalDepth(layers.density[0], layers.falloff[0], h0, dirZ, d)
    + layerOpticalDepth(layers.density[1], layers.falloff[1], h0, dirZ, d);
}

// [how much the fog hides, how much of the sun's glow it carries].
export function atmosphereAmounts(layers, cameraZ, dirZ, length) {
  const veil = Math.min(1 - Math.exp(-atmosphereOpticalDepth(
    layers, cameraZ, dirZ, length, layers.start)), layers.maxOpacity);
  const glow = Math.min(1 - Math.exp(-atmosphereOpticalDepth(
    layers, cameraZ, dirZ, length, layers.sunStart)), layers.maxOpacity);
  return [veil, glow];
}

// ---------- the tile preview ----------
// Each preset's tile is drawn by the same integral, per pixel: an eye at
// head height looking at the horizon, the sun low and to the right, and
// three arches standing at 25, 70 and 180 metres: far enough that each
// takes some of the fog, so a tile shows both what a preset does to
// distance and how it lies on the ground under a crown it spares. Nothing
// here touches WebGL, so it costs no context and draws identically
// everywhere.
const PREVIEW_EYE = 1.7;
const PREVIEW_ARCHES = [
  { distance: 25, centre: -6, half: 5, rise: 8 },
  { distance: 70, centre: 15, half: 10, rise: 13 },
  { distance: 180, centre: -34, half: 22, rise: 26 },
];
const PREVIEW_SUN = (() => {
  const az = 22 * Math.PI / 180, el = 7 * Math.PI / 180;
  return [Math.sin(az) * Math.cos(el), Math.cos(az) * Math.cos(el), Math.sin(el)];
})();

function srgbByte(linear) {
  const mapped = linear / (1 + linear);  // Reinhard: a tile has no exposure dial
  const encoded = mapped <= 0.0031308 ? 12.92 * mapped : 1.055 * Math.pow(mapped, 1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(encoded * 255)));
}

export function atmospherePreviewPixels(width, height, settings) {
  const pixels = new Uint8ClampedArray(width * height * 4);
  const on = atmosphereIsOn(settings);
  const layers = on ? atmosphereLayers(settings, 0) : null;
  const halfWide = Math.tan(34 * Math.PI / 180);
  const halfTall = halfWide * height / width;
  const ambient = [0.78, 0.84, 0.92];
  const sunLight = [2.2, 1.75, 1.2];
  for (let row = 0; row < height; row++) {
    // The horizon a third of the way up, where a picture of the ground
    // with a sky over it puts it.
    const v = (0.62 - (row + 0.5) / height) * 2 * halfTall;
    for (let column = 0; column < width; column++) {
      const u = ((column + 0.5) / width * 2 - 1) * halfWide;
      const norm = Math.hypot(u, 1, v);
      const dir = [u / norm, 1 / norm, v / norm];
      let colour;
      let length = ATMOSPHERE_SKY_DISTANCE;
      const cosSun = dir[0] * PREVIEW_SUN[0] + dir[1] * PREVIEW_SUN[1] + dir[2] * PREVIEW_SUN[2];
      if (dir[2] >= 0) {
        const up = Math.min(1, dir[2] * 3);
        colour = [0.62 - 0.38 * up, 0.72 - 0.34 * up, 0.9 - 0.2 * up];
        if (cosSun > 0.9994) colour = [40, 36, 30];
      } else {
        length = Math.min(ATMOSPHERE_SKY_DISTANCE, PREVIEW_EYE / -dir[2]);
        colour = [0.07, 0.075, 0.07];
      }
      for (const arch of PREVIEW_ARCHES) {
        const t = arch.distance / dir[1];
        if (t >= length) continue;
        const x = t * dir[0] - arch.centre;
        const z = PREVIEW_EYE + t * dir[2];
        const across = x / arch.half;
        if (Math.abs(across) >= 1 || z < 0) continue;
        const crown = arch.rise * Math.sqrt(1 - across * across);
        const soffit = (arch.rise - 1.4) * Math.sqrt(Math.max(0, 1 - (across / 0.72) ** 2));
        if (z > crown || z < soffit) continue;
        length = t;
        colour = [0.2, 0.18, 0.15];
        break;
      }
      if (on) {
        const [veil, glow] = atmosphereAmounts(layers, PREVIEW_EYE, dir[2], length);
        const lobe = Math.pow(Math.max(cosSun, 0), layers.sunExponent) * layers.sunGlow * glow;
        colour = colour.map((c, i) => c * (1 - veil) + ambient[i] * veil + sunLight[i] * 0.35 * lobe);
      }
      const at = (row * width + column) * 4;
      pixels[at] = srgbByte(colour[0]);
      pixels[at + 1] = srgbByte(colour[1]);
      pixels[at + 2] = srgbByte(colour[2]);
      pixels[at + 3] = 255;
    }
  }
  return pixels;
}

// ---------- the integral, in GLSL ----------
// The same functions as above, line for line: atmosphereLayer is
// layerOpticalDepth, atmosphereDepth is atmosphereOpticalDepth and
// atmosphereAmounts is atmosphereAmounts. A test translates this GLSL into
// JS and runs it against those twins over many rays, so the two cannot
// drift apart. Declared once and shared by the fog chunks (every fogged
// material) and the Sky's own patch (the sky is a ShaderMaterial, which
// three never fogs), so the ground and the sky are veiled by one law and
// meet at the horizon without a seam.
export const ATMOSPHERE_GLSL = `
uniform vec2 atmoDensity;
uniform vec2 atmoFalloff;
uniform float atmoBase;
uniform float atmoStart;
uniform float atmoMaxOpacity;
uniform float atmoSunStart;
uniform float atmoSunExponent;
uniform vec3 atmoSunColour;
uniform vec3 atmoSunDir;
float atmosphereLayer( float density, float falloff, float h0, float dz, float d ) {
	if ( density <= 0.0 || d <= 0.0 ) return 0.0;
	float fall = falloff * dz * d;
	float e0 = exp( min( - falloff * h0, 40.0 ) );
	if ( abs( fall ) > 1e-3 ) {
		float through = ( 1.0 - exp( min( - fall, 40.0 ) ) ) / fall;
		return density * e0 * d * through;
	}
	return density * e0 * d * ( 1.0 - 0.5 * fall );
}
float atmosphereDepth( vec3 dir, float L, float start ) {
	float d = max( L - start, 0.0 );
	float h0 = cameraPosition.z + dir.z * min( start, L ) - atmoBase;
	return atmosphereLayer( atmoDensity.x, atmoFalloff.x, h0, dir.z, d )
		+ atmosphereLayer( atmoDensity.y, atmoFalloff.y, h0, dir.z, d );
}
vec2 atmosphereAmounts( vec3 dir, float L ) {
	float veil = min( 1.0 - exp( - atmosphereDepth( dir, L, atmoStart ) ), atmoMaxOpacity );
	float glow = min( 1.0 - exp( - atmosphereDepth( dir, L, atmoSunStart ) ), atmoMaxOpacity );
	return vec2( veil, glow );
}
vec3 atmosphereApply( vec3 colour, vec3 ambient, vec3 dir, float L ) {
	vec2 amounts = atmosphereAmounts( dir, L );
	float lobe = pow( max( dot( dir, atmoSunDir ), 0.0 ), atmoSunExponent );
	return colour * ( 1.0 - amounts.x ) + ambient * amounts.x + atmoSunColour * ( lobe * amounts.y );
}
`;

// The Sky's extra: its ambient colour is handed over explicitly (the sky
// has no fogColor), and its distance is fixed.
export const ATMOSPHERE_SKY_GLSL = ATMOSPHERE_GLSL + `
uniform vec3 atmoSkyColour;
uniform float atmoSkyDistance;
vec3 atmosphereSky( vec3 colour, vec3 dir ) {
	return atmosphereApply( colour, atmoSkyColour, dir, atmoSkyDistance );
}
`;

// The four fog chunks. Three's own declarations stay (fogColor, fogNear,
// fogFar, fogDensity), because refreshFogUniforms writes them, and so does
// three's linear term: with the atmosphere at None the depths are zero and
// the colour that comes out is bit for bit the colour three's chunk gave.
// The view-space position rides along with the old depth varying, and the
// world-space ray is rebuilt from it with the view matrix's transpose,
// which inverts a camera's rotation (a camera carries no scale).
export const FOG_CHUNKS = {
  fog_pars_vertex: "#ifdef USE_FOG\n\tvarying float vFogDepth;\n\tvarying vec3 vFogView;\n#endif",
  fog_vertex: "#ifdef USE_FOG\n\tvFogDepth = - mvPosition.z;\n\tvFogView = mvPosition.xyz;\n#endif",
  fog_pars_fragment: "#ifdef USE_FOG\n\tuniform vec3 fogColor;\n\tvarying float vFogDepth;\n"
    + "\tvarying vec3 vFogView;\n\t#ifdef FOG_EXP2\n\t\tuniform float fogDensity;\n\t#else\n"
    + "\t\tuniform float fogNear;\n\t\tuniform float fogFar;\n\t#endif\n"
    + ATMOSPHERE_GLSL + "#endif",
  fog_fragment: "#ifdef USE_FOG\n\t#ifdef FOG_EXP2\n"
    + "\t\tfloat fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );\n"
    + "\t#else\n\t\tfloat fogFactor = smoothstep( fogNear, fogFar, vFogDepth );\n\t#endif\n"
    + "\tgl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );\n"
    + "\tvec3 atmoRay = ( vec4( vFogView, 0.0 ) * viewMatrix ).xyz;\n"
    + "\tfloat atmoLength = length( atmoRay );\n"
    + "\tgl_FragColor.rgb = atmosphereApply( gl_FragColor.rgb, fogColor, "
    + "atmoRay / max( atmoLength, 1e-6 ), atmoLength );\n#endif",
};

// The shared uniforms, as {value} objects every fogged program holds by
// reference: writing one moves every material at once, with no recompile.
export function createAtmosphere(THREE) {
  const uniforms = {
    atmoDensity: { value: new THREE.Vector2(0, 0) },
    atmoFalloff: { value: new THREE.Vector2(0, 0) },
    atmoBase: { value: 0 },
    atmoStart: { value: 0 },
    atmoMaxOpacity: { value: 0 },
    atmoSunStart: { value: 0 },
    atmoSunExponent: { value: 8 },
    atmoSunColour: { value: new THREE.Color(0, 0, 0) },
    atmoSunDir: { value: new THREE.Vector3(0, 0, 1) },
    atmoSkyColour: { value: new THREE.Color(0, 0, 0) },
    atmoSkyDistance: { value: ATMOSPHERE_SKY_DISTANCE },
  };
  // Any material with an onBeforeCompile of its own shadows the one on
  // the prototype and must call this itself (the outline ribbon does).
  const inject = (shader) => { Object.assign(shader.uniforms, uniforms); };
  return { uniforms, inject };
}

// Installs the chunks and the uniform injector. Must run before the first
// program is built WITH fog: a program compiled under the stock chunks is
// cached under the same key and would never pick these up. Answers false
// when the vendored chunks no longer have the shape this replaces, so a
// three upgrade that moves them is loud rather than a quietly stock fog.
export function installAtmosphere(THREE, inject) {
  const chunks = THREE.ShaderChunk;
  const known = typeof chunks.fog_fragment === "string"
    && chunks.fog_fragment.includes("smoothstep( fogNear, fogFar, vFogDepth )")
    && typeof chunks.fog_vertex === "string"
    && chunks.fog_vertex.includes("vFogDepth = - mvPosition.z;");
  for (const [name, source] of Object.entries(FOG_CHUNKS)) chunks[name] = source;
  THREE.Material.prototype.onBeforeCompile = function atmosphereUniforms(shader) {
    inject(shader);
  };
  return known;
}

// Writes one set of layers into the shared uniforms; null switches the
// atmosphere off by zeroing its densities, which is all the shaders need.
export function writeAtmosphere(uniforms, layers) {
  if (!layers) {
    uniforms.atmoDensity.value.set(0, 0);
    uniforms.atmoMaxOpacity.value = 0;
    return;
  }
  uniforms.atmoDensity.value.set(layers.density[0], layers.density[1]);
  uniforms.atmoFalloff.value.set(layers.falloff[0], layers.falloff[1]);
  uniforms.atmoBase.value = layers.base;
  uniforms.atmoStart.value = layers.start;
  uniforms.atmoMaxOpacity.value = layers.maxOpacity;
  uniforms.atmoSunStart.value = layers.sunStart;
  uniforms.atmoSunExponent.value = layers.sunExponent;
}
// ---------- the light shafts ----------
// The volumetric half of the look. The height fog above is analytic: it
// answers "how much air is between the eye and this pixel" in closed
// form, and it cannot know that the vault stands between that air and the
// sun. So air in the vault's shadow glows exactly as brightly as air
// beside it, and a low sun through a cable net reads as a flat wash.
//
// This marches. From the eye toward each pixel's own depth it takes
// SHAFT_STEPS samples, asks the sun's shadow map at each whether the sun
// reaches THAT point, and weights the answer by the same two-layer height
// fog and the same sun lobe the analytic fog uses, so the shafts are made
// of the same air.
//
// IT SPLITS THE GLOW, and that is what the first version, withdrawn on
// 11 September (ec7fe73), did not do. It only ever added the lit air on
// top of the analytic glow, which the analytic fog had already put there,
// so on every pixel the sun reached it was a second Sun glow dial: 97 per
// cent of what it did was blind to shadow. Now one loop sums the air the
// sun reaches and the air it does not, in the same steps, and the two
// sums PARTITION the analytic glow exactly. The pass takes the shaded
// share away and lays SHAFT_GAIN times the lit share on, so shadowed air
// loses precisely the glow the fog gave it -- never more, so no black
// fringe at a silhouette -- and lit air carries the sun.
//
// Param, 2026-09-13, over a golden-hour beech wood of his own: "I think we
// are just missing light rays from this." The withdrawal left the look to
// him because rays need the air lit harder than the analytic fog lights
// it; that is this dial, and every preset and every saved scene rests at
// nought, so nothing already made changes until he turns it up.
//
// THE ACCUMULATION TELESCOPES, and that is what makes it testable. Each
// step adds transmittance * (1 - exp(-tau)) and then multiplies the
// transmittance by exp(-tau), so the lit and shaded sums together
// collapse to 1 - exp(-sum of tau), which is exactly the analytic glow
// (atmosphereAmounts' second answer) for ANY number of steps and ANY
// shadow. A test holds the marcher to that identity, so a wrong h0, a
// wrong segment length or a dropped transmittance cannot hide behind
// "it is a coarse approximation anyway".
export const SHAFT_STEPS = 32;
// How far the march reaches, in metres. The camera's far plane is 500 m
// and a sky pixel reconstructs to it; marching that with 32 steps gives
// 15 m between samples, which steps straight over a vault. The fog is
// saturated long before this in every preset that shows shafts at all.
export const SHAFT_MAX_DISTANCE = 240;
// How hard the lit air is driven at a hundred per cent, as a multiple of
// the glow the analytic fog gives it. MEASURED, in his own beech wood at
// golden hour under Haze, looking toward a sun 2.5 degrees up: at 4 (the
// withdrawn value) and at 16 the wood only glowed a little more; at 48
// distinct beams stood between the trunks. atmoSunColour is the sun
// through ATMOSPHERE_SUN_GAIN, about 0.054, tuned for a glow spread over
// the whole sky, which is why the rays need this much authority of their
// own; the withdrawal measured that ten times was the first multiple to
// read as a shaft at all.
export const SHAFT_GAIN = 48;

// The march, in JS: the twin of the GLSL below. visibility answers how
// much of the sun reaches a point that many metres along the ray (the
// shadow map's job in the shader), and jitter is where inside each
// segment that question is asked, which the shader dithers per pixel.
// Answers the air the sun reaches and the air it does not, separately.
export function shaftSums(layers, cameraZ, dirZ, length, visibility, jitter = 0.5) {
  const reach = Math.min(length, SHAFT_MAX_DISTANCE);
  const begin = Math.min(layers.sunStart, reach);
  const span = reach - begin;
  if (span <= 0) return { lit: 0, shade: 0 };
  const ds = span / SHAFT_STEPS;
  let transmittance = 1;
  let lit = 0;
  let shade = 0;
  for (let step = 0; step < SHAFT_STEPS; step++) {
    const at = begin + step * ds;
    const h0 = cameraZ + dirZ * at - layers.base;
    // The segment's own optical depth, from its START, which is what
    // makes the sum exact: the jitter moves only where the SUN is asked
    // about, never how much air the segment holds.
    const tau = layerOpticalDepth(layers.density[0], layers.falloff[0], h0, dirZ, ds)
      + layerOpticalDepth(layers.density[1], layers.falloff[1], h0, dirZ, ds);
    const through = Math.exp(-tau);
    const reached = visibility(at + jitter * ds);
    lit += transmittance * (1 - through) * reached;
    shade += transmittance * (1 - through) * (1 - reached);
    transmittance *= through;
  }
  return { lit, shade };
}

// What the pass lays on one pixel, before the sun's colour, its lobe and
// the dial: the glow, capped as the analytic fog caps it, split by how
// much of it the sun reaches -- the lit share raised by SHAFT_GAIN and the
// shaded share taken away. Between minus the glow (all in shadow) and
// SHAFT_GAIN times the glow (all lit), whatever the shadow does.
export function shaftLight(layers, cameraZ, dirZ, length, visibility, jitter = 0.5) {
  const { lit, shade } = shaftSums(layers, cameraZ, dirZ, length, visibility, jitter);
  const total = lit + shade;
  if (total <= 0) return 0;
  const glow = Math.min(total, layers.maxOpacity);
  const share = lit / total;
  return glow * (SHAFT_GAIN * share - (1 - share));
}

// The dial as a fraction, and the one place that says shafts need fog:
// with the atmosphere at None there is no air to light, so the pass does
// not run whatever the dial says.
export function shaftsStrength(settings) {
  if (!atmosphereIsOn(settings)) return 0;
  const per = typeof settings.shafts === "number" && Number.isFinite(settings.shafts)
    ? settings.shafts : 0;
  return Math.max(0, Math.min(1, per / 100));
}

// The march, in GLSL: the twin of shaftInscatter above, on the same
// atmosphere functions (ATMOSPHERE_GLSL is prepended, so atmosphereLayer
// here IS layerOpticalDepth there). SHAFT_STEPS arrives as a define.
//
// The shadow map is r185's directional PCF map, which is a DepthTexture
// carrying a compare function, so it is sampled as a sampler2DShadow
// through the shadow camera's own matrix. Outside that camera's slab the
// answer is 1: the slab is fitted to the casters, so there is nothing out
// there to block the sun, and clamping to the edge instead would smear
// the vault's silhouette across the whole horizon.
export const SHAFTS_GLSL = ATMOSPHERE_GLSL + `
uniform sampler2D tDepth;
uniform sampler2DShadow shaftShadowMap;
uniform mat4 shaftShadowMatrix;
uniform mat4 shaftProjectionInverse;
uniform mat4 shaftCameraWorld;
uniform vec3 shaftEye;
uniform float shaftStrength;
uniform float shaftBias;
uniform float shaftMaxDistance;
uniform vec2 shaftPixelOrigin;
varying vec2 vUv;
vec3 shaftWorld( vec2 uv, float depth ) {
  vec4 clip = vec4( uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0 );
  vec4 view = shaftProjectionInverse * clip;
  return ( shaftCameraWorld * vec4( view.xyz / view.w, 1.0 ) ).xyz;
}
float shaftVisibility( vec3 at ) {
  vec4 coord = shaftShadowMatrix * vec4( at, 1.0 );
  coord.xyz /= coord.w;
  if ( coord.x < 0.0 || coord.x > 1.0 || coord.y < 0.0 || coord.y > 1.0 || coord.z > 1.0 ) return 1.0;
  return texture( shaftShadowMap, vec3( coord.xy, coord.z - shaftBias ) );
}
// Interleaved gradient noise, the same hash r185's own PCF uses, over the
// pixel's place in the WHOLE frame. Seeded by the pixel and by nothing
// else: no wall clock, so a take is reproducible frame for frame, and no
// take clock either, so a still rendered in tiles gets the identical
// dither in a tile that it would have had in the whole plate.
float shaftDither( vec2 pixel ) {
  return fract( 52.9829189 * fract( dot( pixel, vec2( 0.06711056, 0.00583715 ) ) ) );
}
vec3 shaftLight( vec2 uv, vec2 pixel ) {
  float depth = texture2D( tDepth, uv ).x;
  vec3 ray = shaftWorld( uv, depth ) - shaftEye;
  float travel = length( ray );
  vec3 dir = ray / max( travel, 1e-6 );
  float reach = min( travel, shaftMaxDistance );
  float begin = min( atmoSunStart, reach );
  float span = reach - begin;
  if ( span <= 0.0 ) return vec3( 0.0 );
  float ds = span / float( SHAFT_STEPS );
  float jitter = shaftDither( pixel );
  float transmittance = 1.0;
  float lit = 0.0;
  float shade = 0.0;
  for ( int stepIndex = 0; stepIndex < SHAFT_STEPS; stepIndex ++ ) {
    float at = begin + float( stepIndex ) * ds;
    float h0 = shaftEye.z + dir.z * at - atmoBase;
    float tau = atmosphereLayer( atmoDensity.x, atmoFalloff.x, h0, dir.z, ds )
      + atmosphereLayer( atmoDensity.y, atmoFalloff.y, h0, dir.z, ds );
    float through = exp( - tau );
    float reached = shaftVisibility( shaftEye + dir * ( at + jitter * ds ) );
    lit += transmittance * ( 1.0 - through ) * reached;
    shade += transmittance * ( 1.0 - through ) * ( 1.0 - reached );
    transmittance *= through;
  }
  float total = lit + shade;
  if ( total <= 0.0 ) return vec3( 0.0 );
  float glow = min( total, atmoMaxOpacity );
  float share = lit / total;
  float lobe = pow( max( dot( dir, atmoSunDir ), 0.0 ), atmoSunExponent );
  return atmoSunColour * ( lobe * shaftStrength * glow
    * ( float( SHAFT_GAIN ) * share - ( 1.0 - share ) ) );
}
void main() {
  gl_FragColor = vec4( shaftLight( vUv, gl_FragCoord.xy + shaftPixelOrigin ), 1.0 );
}
`;

// Laying the marched light over the frame. At full resolution the shaft
// buffer is the frame's own size and each pixel takes its own texel, by
// texelFetch, so a still rendered in tiles gets bit for bit what the
// whole plate would have given it. At half resolution (the live view
// only) the four nearest texels are blended by distance as well as by
// position: a plain bilinear upsample drags the bright fog in front of a
// pier across the pier's edge, and a halo around every silhouette is
// exactly what a half-resolution effect is accused of.
export const SHAFTS_COMPOSITE_GLSL = `
uniform sampler2D tDiffuse;
uniform sampler2D tShafts;
uniform sampler2D tDepth;
uniform mat4 shaftProjectionInverse;
uniform vec2 shaftLowResolution;
uniform float shaftUpsample;
varying vec2 vUv;
float shaftViewDistance( vec2 uv ) {
  float depth = texture2D( tDepth, uv ).x;
  vec4 clip = vec4( uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0 );
  vec4 view = shaftProjectionInverse * clip;
  return length( view.xyz / view.w );
}
vec3 shaftUpsampled() {
  if ( shaftUpsample < 0.5 ) return texelFetch( tShafts, ivec2( gl_FragCoord.xy ), 0 ).rgb;
  vec2 texel = 1.0 / shaftLowResolution;
  vec2 at = vUv * shaftLowResolution - 0.5;
  vec2 base = floor( at );
  vec2 part = at - base;
  float here = shaftViewDistance( vUv );
  vec3 sum = vec3( 0.0 );
  float weightSum = 0.0;
  for ( int y = 0; y < 2; y ++ ) {
    for ( int x = 0; x < 2; x ++ ) {
      vec2 uv = ( base + vec2( float( x ), float( y ) ) + 0.5 ) * texel;
      float bilinear = ( x == 0 ? 1.0 - part.x : part.x ) * ( y == 0 ? 1.0 - part.y : part.y );
      float apart = abs( shaftViewDistance( uv ) - here );
      float weight = bilinear / ( 0.05 + apart );
      sum += texture2D( tShafts, uv ).rgb * weight;
      weightSum += weight;
    }
  }
  return sum / max( weightSum, 1e-6 );
}
void main() {
  vec4 base = texture2D( tDiffuse, vUv );
  gl_FragColor = vec4( base.rgb + shaftUpsampled(), base.a );
}
`;

// Both passes draw the one full-screen triangle, so they share a vertex
// shader; vUv is what the fragment shaders above read.
export const SHAFTS_VERTEX = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}
`;
