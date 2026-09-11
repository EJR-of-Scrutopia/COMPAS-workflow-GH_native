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
  },
  "morning-mist": {
    label: "Morning mist", density: 0.8, height: 40, base: 0, start: 0,
    maxOpacity: 95, sunGlow: 120, sunLobe: 6, sunStart: 0, mist: 20, mistHeight: 1.7,
  },
  haze: {
    label: "Haze", density: 6, height: 25, base: 0, start: 0,
    maxOpacity: 80, sunGlow: 150, sunLobe: 12, sunStart: 10, mist: 0, mistHeight: 2,
  },
  "valley-fog": {
    label: "Valley fog", density: 1.2, height: 30, base: 0, start: 0,
    maxOpacity: 97, sunGlow: 80, sunLobe: 8, sunStart: 0, mist: 50, mistHeight: 1.5,
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
