# Bench Studio environment engine

Date: 2026-08-14, agreed with Param. The wave he moved ahead of the
pattern library: the studio stops being a grey room and becomes a place.
Six decisions. Robots placing pieces stay a later wave (prior art: bench
demo 05's analytical IK).

## Where the scene stands today

One hardcoded look: a PMREM'd RoomEnvironment for image lighting, one
directional sun on azimuth/elevation sliders, a hemisphere fill, an HSL
background-tone slider, and a single dark 60 m receive-shadow disc for
ground. Only OrbitControls and RoomEnvironment are vendored. The
procedural-texture idiom (noiseTexture, grainTexture: canvas-drawn,
repeat-wrapped, max anisotropy) is established and the offline rule
scans the four authored static files only.

## Decisions

### E1. One Environment select, three exclusive modes

- A select labelled "Environment", id `environment-mode`, in the Scene
  section: Studio (default) | Sky | HDRI. State in
  `state.environmentMode` ("studio" | "sky" | "hdri").
- Each mode fully owns scene.background, scene.environment, scene.fog
  and the sun defaults. No half-mixed states: switching modes swaps
  them together (Studio and HDRI set fog to null) and never touches
  the camera, the timeline or the cut.
- Studio is today's look exactly: RoomEnvironment lighting, the
  background-tone slider, the current exposure and intensity values.
- The background-tone slider is visible in Studio mode only; in Sky and
  HDRI modes the sky or the image owns the backdrop and the slider row
  hides.

### E2. Sky mode is a physical sky

- Vendor three.js's Sky addon (the Rayleigh/Mie scattering shader,
  self-contained, sits beside RoomEnvironment under vendor/addons).
- The existing sun azimuth/elevation sliders drive BOTH the shader's
  sun position and the directional light, so lowering elevation sweeps
  noon through golden hour into dusk and the shadows always agree with
  the sky.
- The sky is PMREM'd into scene.environment so it lights the vault.
  Regeneration happens on slider release (the change event), not per
  input event: PMREM is far too heavy for 60 fps scrubbing. During a
  drag the directional light moves live; the ambient catches up on
  release.
- Weather presets are parameter bundles on that one shader, in a select
  id `weather-preset`: Clear (default) | Hazy | Overcast | Golden hour
  | Night. Each preset sets turbidity, rayleigh, mieCoefficient,
  mieDirectionalG, sun intensity and colour, shadow radius (softness),
  toneMappingExposure, hemisphere intensity, and a matching THREE.Fog
  colour and range. Golden hour and Night also move the elevation
  slider to a fitting default; the sliders remain live afterwards.
- No precipitation particles. Weather here is light and atmosphere.
- applySceneAtTime stays pure in t: nothing in the environment reads
  the clock or the timeline.

### E3. HDRI mode: server folder, upload, picker, estimated sun

- Server folder `bench/studio/hdri/` holds Radiance .hdr files. Three
  routes in app.py following the columns pattern:
  - `GET /api/hdri` returns the sorted list of stored names.
  - `GET /api/hdri/{name}` serves one file (path-traversal guard, 404
    when absent).
  - `PUT /api/uploads/hdri/{filename}` stores the body. Guards:
    path-traversal rejection, the filename must end in .hdr, the body
    must begin with the Radiance magic bytes (`#?RADIANCE` or
    `#?RGBE`), and the body is capped at 64 MB so a mistyped upload
    cannot fill the disk. Responses mirror the columns route shape.
- The client picker: a select id `hdri-select` refreshed from
  `GET /api/hdri`, plus a file input id `hdri-upload` that PUTs and
  then refreshes the list and selects the new file. Both sit in the
  Scene section and only show in HDRI mode.
- Loading: RGBELoader (newly vendored, a small self-contained addon)
  decodes the file; PMREM turns it into scene.environment; the
  equirectangular texture becomes scene.background.
- Sun auto-estimate: on load, scan the decoded equirectangular pixels
  for the brightest region (a coarse downsampled pass is enough), place
  the directional sun at that direction, and scale its intensity to how
  peaked the highlight is, so a clear-sky map gets a hard bright sun
  and an overcast map gets a soft dim one. The azimuth/elevation
  sliders stay live to override, and moving them in HDRI mode moves
  only the light, never the image. The estimator is a pure function of
  the pixel data (positions and intensity out, no scene access) so it
  pins under test with a synthetic image.
- The chosen HDRI name persists in localStorage and is re-selected on
  the next visit when it still exists on the server.
- No HDRI files ship in the repo. The folder starts empty and the
  picker says so; Param installs or uploads his own.

### E4. Ground presets, independent of environment mode

- A select labelled "Ground", id `ground-preset`, in the Scene section:
  Dark studio (default) | Concrete slab | Patio pavers | Tiles. State
  in `state.groundPreset`.
- The 60 m receive-shadow disc stays; only its material swaps. All four
  materials are procedural canvas textures in the existing noiseTexture
  idiom: no image assets, repeat-wrapped, max anisotropy.
- Dark studio is today's plain dark material. Concrete slab is a
  neutral grey noise with faint broad tonal patches. Patio pavers and
  Tiles draw their joint grids into the colour map, the roughness map
  and a slight bump map, so raking sun catches the joints; pavers are
  large-format with staggered courses, tiles a finer square grid.
- Ground materials are built once each, lazily on first selection, and
  cached for the session.

### E5. Placeable props with saved layouts

- A procedural low-poly prop set, built in code like the textures:
  standing figure (1.75 m), tree, pallet stack, barrier, traffic cone.
  All cast shadows, none receive analysis recolouring, none are
  pickable by any analysis interaction.
- A Props row in the Scene section: one button per prop type. Pick a
  prop, click the ground to place it at the raycast hit on the disc.
  Clicking a placed prop selects it; dragging moves it along the
  ground; R rotates it in 15 degree steps; Delete removes it; clicking
  empty ground deselects. Placement interactions are pointer events on
  the canvas and never fight OrbitControls: while a prop is armed or
  selected-and-dragging, controls are paused, and released after.
- Layouts persist per study in localStorage under a stable key
  (study slug, prop type, x, y, rotation), restored on load when that
  study opens. A "Clear props" button empties the layout for the
  current study.
- Props are ordinary scene objects: they appear in recordings, and
  nothing about them reads the clock, so the purity contract stands.

### E6. What each mode costs and when work happens

- Mode switches, preset switches, HDRI loads and ground swaps are all
  user-initiated, one-shot work. Nothing environmental runs per frame
  beyond what three.js already does with a static scene.
- PMREM regeneration points: entering a mode, changing a weather
  preset, releasing a sun slider in Sky mode, and finishing an HDRI
  load. Never during a slider drag, never per frame.

## Out of scope

- Robots and any animated site machinery (later wave, demo 05 prior
  art).
- Precipitation, clouds as geometry, animated water.
- .exr support (RGBELoader and .hdr only; every major HDRI library
  ships .hdr).
- Shipping HDRI files in the repo.
- Any change to the cut, the timeline model, materials of the vault
  itself, or the analysis layers.

## Testing

- Static pins in tests/studio/test_static.py: the environment-mode
  select and its three options; the weather-preset select and its five
  options; the ground-preset select and its four options; the vendored
  Sky and RGBELoader imports; the tone-slider visibility wiring; the
  props row and Clear-props button; the localStorage keys for HDRI
  choice and prop layouts; purity pins extended so no environment
  function reads the clock or timeline speed.
- The sun estimator is exercised in node (tests/studio/test_fields.py
  pattern) with synthetic equirectangular data: a single hot pixel
  lands the sun at the expected azimuth/elevation; a uniform grey map
  yields the soft-sun intensity floor.
- Server tests for the three HDRI routes: list empty and non-empty,
  fetch present and absent, upload happy path, traversal rejection,
  wrong extension, wrong magic bytes, oversize body.
- Suites run from the COMPAS-Workflow-bench worktree. No em dashes, no
  attribution, nothing pushed.
