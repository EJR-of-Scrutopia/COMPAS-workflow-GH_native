# Bench Studio asset libraries wave

Date: 2026-09-04, agreed with Param. The studio stops carrying its assets
and starts reading them. Four folders replace three hard-coded tables and
one bundled sky collection: vaults (already done), materials, skies and
props. Materials come from the library Param has already curated inside QS
Intelligence. The panel adopts a published schema instead of being invented
a control at a time.

Research behind every number here: six readers, 2026-09-04, notes kept at
C:\Users\Param\AppData\Local\Temp\claude\c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui\eef1adad-d09f-4ae7-8695-89370827e60b\scratchpad\research

## The ask, as received

1. Find a UI schema relevant to what we have, most likely a rendering
   software's, that settles how to show HDRIs, how to make material
   thumbnails and how to make prop thumbnails.
2. Look at QS Intelligence, which holds useful work on material
   displacement, rendering and texturing, because the material textures,
   the ground and the props are about to be overhauled deeply.
3. Use legitimate high quality free sources such as Poly Haven, bringing in
   their maps as well, to get good rendering quality cheaply.
4. HDRIs work off a folder selection, like the vault import: the studio
   looks at every HDRI inside a folder rather than having them chosen by
   hand one at a time. This also stops the studio holding every sky in
   memory, freeing that space for scene integration.
5. Props work the same way: the studio looks to a library.

Three decisions taken on 2026-09-04 before this document was written:
materials come from Param's QS Library by folder pick; material thumbnails
are square with a preview object that varies by family; the whole overhaul
lands in one go after this spec is read.

## What the research settled

These are the facts the design rests on. Each was verified rather than
recalled.

**M1.** Param's QS Library is a finished material stack: 158 materials at
`Library/materials/<family>/<name>/` holding fixed file names `colour.jpg`,
`normal.png`, `height.png`, `roughness.png`, `ao.png`, `material.json` and
a `lod/` folder. Maps are linked by living in the same folder, never by
filename. All 158 carry colour, normal, height and roughness; 108 carry AO.
Eleven populated families out of fourteen seeded, under the rule that a
category names what a thing is made of.

**M2.** `lod/` is named `<kind>-<px>.<ext>`, px in (1024, 256), `.jpg` for
colour and `.png` for every other kind, because a JPEG artefact is
invisible in colour and becomes false relief in a normal map. A tier exists
only when the master's long edge exceeds it, and nothing is ever upscaled,
so a missing tier means falling through to the master.

**M3.** The QS plugin runs every calculation on 8-bit sRGB bytes with
Rec.601 luma weights. That is right for a GDI+ preview and wrong in a PBR
renderer, so the colour discipline is the one thing not inherited.

**M4.** QS records no physical tile size, and did not need one: the image
is one unit's face, and the element's own millimetres supply the scale. A
three.js scene has no element, so the studio must supply the number for any
continuous surface.

**M5.** Poly Haven publishes real-world texture size in millimetres in a
`dimensions` field (`gravel_floor_02` is `[2000, 2000]`, confirmed by the
page reading "Wide 2m" and "px/cm 41"). ambientCG publishes it in
centimetres as a `dimensions` object (`PavingStones151` is 540 by 540,
rendered on the site as "ca. 5.4 m x 5.4 m"). ambientCG reports 0 for older
procedural assets, which means unknown, not zero.

**M6.** three.js derives the PMREM cube size from the source width divided
by four and keeps an identically sized ping-pong target, so peak VRAM to
prefilter a sky is about 16 MiB at 1k, 64 MiB at 2k, 256 MiB at 4k and
1,024 MiB at 8k. r185 also replaced the Gaussian chain with 256-sample GGX
importance sampling, so it is slower as well as larger. three.js's own note
says the ideal input is 1024 by 512.

**M7.** Handing a raw equirect to `scene.environment` makes three.js attach
a dispose listener to it, so disposing the source destroys the cached
environment map and forces both to stay resident. Building the PMREM by
hand attaches no listener and lets the source be freed.

**M8.** In r185 `aoMap` does not need a second UV set: `aoMap.channel`
defaults to 0. The jsdoc still says otherwise and contradicts its own code.
When a second set is genuinely wanted the attribute is `uv1`, not `uv2`.

**M9.** `PCFSoftShadowMap` is deprecated in r185 and silently downgraded to
`PCFShadowMap` with a console warning, because PCF was rewritten to a
hardware-comparison five-tap Vogel disk. `shadow.radius` now controls
softness for real.

**M10.** `ACESFilmicToneMapping` multiplies exposure by 1/0.6 without
saying so, then saturates midtones and hue-shifts strong colours.
`NeutralToneMapping` is a straight pass-through below a peak of 0.76. For a
material library judged against a real sample, Neutral is correct.

**M11.** `repeat` is per texture and every map slot has its own transform
uniform, so setting repeat on the albedo alone leaves the other five at
1:1. `RepeatWrapping` is not the default. Anisotropy is silently ignored
unless `minFilter` is a mipmap-linear filter.

**M12.** `texture.clone()` shares the source, and the WebGL cache key does
not include repeat, offset, centre or rotation. So many differently tiled
clones of one material cost exactly one GPU upload.

**M13.** Poly Haven models are film assets with no LODs and no packed
`.glb`: `tree_small_02` is 4.65 million polygons with a 208 MB buffer, and
the shared `.bin` is served from the 8k path even inside the 1k entry, so a
download URL must never be built by string substitution.

**M14.** Poly Haven has no human figures at all. Renderpeople have
published nine photoscanned figures on Sketchfab under CC Attribution.

## The schema

Adopted: **Adobe Spectrum**, in the form of its published token data rather
than its brand look. It is the only candidate that ships exact numbers for
every quantity in the brief, it is dark-native, and it is the system behind
Substance 3D Painter and Sampler, whose asset panels are the nearest
existing thing to what this studio needs.

- https://spectrum.adobe.com/page/design-tokens/
- https://opensource.adobe.com/spectrum-design-data/tokens/card/
- https://opensource.adobe.com/spectrum-design-data/tokens/standard-panel/
- https://opensource.adobe.com/spectrum-design-data/tokens/swatch/

Read before writing thumbnail code. These are the only published written
specifications of thumbnail content and asset-grid behaviour found in the
whole survey, and they are short:

- https://developer.blender.org/docs/features/interface/asset_thumbnails/
- https://developer.blender.org/docs/features/asset_system/user_interface/asset_shelf/

Behavioural precedents, quoted in the decisions below:

- Twinmotion library and its sky taxonomy:
  https://dev.epicgames.com/documentation/en-us/twinmotion/overview-of-the-twinmotion-library
- Substance 3D Painter assets panel, for size steps and search:
  https://experienceleague.adobe.com/en/docs/substance-3d-painter/using/interface/assets/navigation
- Radix Themes, if the tokens ever need a CSS substrate:
  https://www.radix-ui.com/themes/docs/theme/color

## Decisions

### L1. Four folders, one settings file

The studio remembers four roots in `bench/studio/settings.json`:
`upload_folder` (exists), `material_folder`, `hdri_folder`, `props_folder`.

Each gets the vault folder's exact pattern, which is already proven and
already tested: a `POST /api/<kind>/folder/browse` route that calls the
existing `ask_for_folder` in a subprocess and returns a path without
setting it; a `POST /api/<kind>/folder` route that strips quotes, refuses
anything that is not a directory with a 400 naming the path, assigns the
module-level root, calls a remember helper that swallows `OSError`, and
returns a row; a `GET /api/<kind>/folder` returning that row; and an
`apply_saved_*` called by `serve.py` at startup and never by `create_app`,
so tests that monkeypatch a root are not defeated.

Each row carries `{"path", "exists", "count"}` where count is what the
folder holds: vaults, materials, skies or props.

A folder that is missing or empty is not an error. The library shows
"no materials in this folder" and the studio keeps working on its built-in
fallbacks.

### L2. The material library is read, never written

The material root is expected to be
`C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\QS intelligence\Library\materials`
or any folder in the same shape. The studio never writes a byte into it.
Any studio-only fact about a material lives in
`bench/studio/materials.json`, keyed by `"<family>/<name>"`, so it survives
the library being moved, regenerated or renamed.

Scanning: two levels of directory. A folder is a material when it contains
`colour.jpg`. Family folders are the first level. Directory listings are
cached by the folder's own write time, which Windows moves when an entry is
added, removed or renamed and leaves alone when a file's content changes,
which is exactly the line a listing cares about. The `colour.jpg` test runs
fresh on every read, because a material folder created empty and filled
later moves its own time and not its family's.

`material.json` is read for `maps` and `tiers` only. `maps` is authoritative
for which maps exist, not the rarely written `absent` array. Everything
else in it is provenance and the studio ignores it, exactly as the plugin
does.

The index route returns, per material:

```json
{
  "key": "brick/stock-red",
  "family": "brick",
  "name": "stock-red",
  "label": "Stock red",
  "maps": {"colour": [457, 129], "normal": [457, 129],
           "height": [229, 64], "roughness": [229, 64]},
  "tiers": [256],
  "tileMetres": null,
  "preview": "panel"
}
```

`label` is the folder name with hyphens turned to spaces and the first
letter capitalised. `preview` is derived from the family by L7.

### L3. Physical scale, and the two ways a material is laid on

This is the one field QS never needed and three.js cannot do without.

`tileMetres` is `[width, height]` in metres, meaning the real-world size of
the one unit the image shows. It is null until known. It is supplied from
three places, in this order: a `tileMetres` entry in
`bench/studio/materials.json`; a `dimensions` field carried over by the
fetch scripts of L11 when the material came from Poly Haven or ambientCG;
or by hand, through a field in the material panel that writes to
`materials.json`.

A material is laid on in one of two ways, and which one is used depends on
the geometry, not on the material:

- **On cut pieces**, one repeat per piece face, which is the QS one-unit
  rule exactly: the image is one unit's face, and one brick's picture on
  one brick's face is correct at any size. `tileMetres` is not consulted.
  Box projection follows QS's own face indexing and axis rules, so a piece
  textured in the studio and the same piece textured in Grasshopper agree.
- **On a continuous surface** (the uncut shell, and the ground), tiling is
  computed: `repeat = surfaceExtentMetres / tileMetres`. Where `tileMetres`
  is null the studio falls back to 0.6 m square and says so in the event
  log once, rather than silently inventing a scale.

Repeat is set on **every** map in the set, not the albedo alone (M11), and
`wrapS`/`wrapT` are set to `RepeatWrapping` because `ClampToEdgeWrapping`
is the default and would smear the edge pixel instead of tiling.

Where two surfaces want the same material at different scales, the second
gets `texture.clone()` of every map with its own repeat, which costs one
extra JavaScript object and zero extra GPU upload (M12).

### L4. Loading a material set

Colour space, and only this (M3, and the three.js colour-data list):

- `colour.jpg` -> `THREE.SRGBColorSpace`
- `normal.png`, `roughness.png`, `ao.png`, `height.png` -> left at
  `NoColorSpace`

Setting sRGB on a normal map corrupts it in hardware, not merely in the
shader, because the internal format becomes `SRGB8_ALPHA8`.

Material construction, with the scalars that make the maps work:

```js
new THREE.MeshPhysicalMaterial({
  map: colour,                       // SRGBColorSpace
  normalMap: normal,                 // OpenGL green-up, no flip needed
  normalScale: new THREE.Vector2(1, 1),
  roughnessMap: roughness, roughness: 1.0,   // the scalar MULTIPLIES the map
  aoMap: ao, aoMapIntensity: 1.0,            // channel 0, no uv1 needed (M8)
  metalness: family === "metal" ? 1.0 : 0.0,
  side: THREE.DoubleSide,
  envMapIntensity: 1.0,
});
```

`roughness: 1.0` is not a style choice. The scalar multiplies the map, so
leaving it at anything else darkens or lightens every roughness value in
the library at once. The same trap kills a metalness map at the default 0,
which is why the metal family is the only one that raises it.

Anisotropy 8 on every map, which requires `minFilter` to stay at its
default `LinearMipmapLinearFilter` or it is silently ignored (M11). Grazing
views of a vault ground are exactly where it earns its keep, and 16 costs
measurable bandwidth for little more.

Level of detail, using the tiers QS writes and the plugin barely reads
(M2):

- Picker tiles: `lod/colour-256.jpg`, served as an ordinary image and drawn
  into a canvas. Never through WebGL.
- Viewport: the 1024 tier of every map where it exists, the master where it
  does not.
- A `Full detail` toggle in the material panel switches the viewport to
  masters for a still. Off by default.

Nothing decodes a whole library. The index resolves paths and stops, which
is QS's own rule and the reason its picker is fast.

Memory: a bounded cache of at most eight decoded material sets, least
recently used evicted. On eviction the set is disposed only if no live
material references it, tracked by a small use count. Disposal walks every
map slot and calls `dispose()` on each texture, then on the material.
`renderer.info.memory.textures` returning to baseline after a swap is the
test.

### L5. Displacement

Normal mapping is the default and the only thing the viewport does. The
height field is used for two other purposes:

- The material tile's relief, in the offline preview render, so a brick
  reads as a brick at 180px.
- An opt-in `Relief` toggle that builds genuinely displaced geometry on the
  CPU for the cut pieces, following QS's three-pass order exactly, because
  the order is load-bearing: fill raw mean-centred offsets, one separable
  1-2-1 fairing pass, then the rim taper over the outer three per cent.
  Fairing after the taper pulls the rim off zero and opens the arris.

Amplitude follows QS: a Relief value of 1 means 10 mm, applied about the
field's own mean rather than about mid-grey, so a map's bias does not
change a piece's volume. Sampling flips v (sample at `1 - v`) so the relief
lands where the draped colour shows it.

Parallax occlusion is rejected. It does not exist in the WebGPU build, so
it would permanently fork the renderer paths, and it fails at exactly the
grazing angles from which a vault is judged.

Frankot-Chellappa integration is not ported in this wave. All 158 QS
materials ship a height map, so the fallback has nothing to do. It is
recorded here as the known answer if a hand-dropped normal ever arrives
without one: 256 square, `nz` clamped at 0.1, `p = -nx/nz`, `q = -ny/nz`,
DC bin left at zero, one normalisation over the field's own range.

### L6. The ground becomes a material

`GROUNDS` stops being a four-entry table of procedural canvases. The ground
takes any material from the library, tiled by `tileMetres` (L3), plus two
built-in presets that need no library: `dark-studio` (a flat dark
`MeshPhysicalMaterial`, the current default, kept because it is the right
background for a structural study) and `none`.

The disc, the radius slider, `groundLevel()` and `HDRI_DROP = 0.05` all
stay as they are. `groundRepeat` in `fields.js` is already the right
function and keeps its tests.

This fixes a defect on the way: `concrete-slab` today has no
`groundTileMetres`, so its noise repeat stays at a hard-coded 6 by 6 and
the grain therefore changes size with the disc. With a real material and a
real tile size that cannot happen.

### L7. Material thumbnails

Square, 180px by default, label underneath, corner radius 3px, a 1px border
of white at 10 per cent opacity. Three sizes, 120 / 180 / 240, chosen by a
Small / Medium / Large control in the library footer, Medium default. The
grid snaps to whole rows and never shows a partial one.

The preview object varies by family, because a brick is best seen as a wall
and not as a ball. Chaos states the principle outright and KeyShot makes it
a per-material property; this makes it a per-family default with a
per-material override stored in `materials.json`:

| Family | Preview object |
| --- | --- |
| brick, clay, stone, slate, concrete, aggregate, mortar | curved panel |
| timber | flat plank, fitted not stretched |
| plaster, paint, plastic, mineral-wool | flat plane |
| metal, glass | sphere |

Every swatch renders under one fixed environment at 512px square and is
cached. The existing preview rig does this work; it gains the four objects
and keeps its try/catch and its flat-colour fallback.

Legibility devices carried over from the QS picker, because they are cheap
and they are what makes 158 near-identical bricks browsable:

- Fit, never stretch, on a dark neutral ground, so a tall crop such as a
  cedar plank letterboxes rather than distorting.
- The chosen tile is marked. Without it the grid is sixty identical squares
  and there is no way to see which one is in play.
- Search matches `family/name` as one string across the whole library, and
  the caption names the family while a search is active.

### L8. The sky library

The root is a folder Param picks. Every `.hdr` in it is a sky. `.exr` is
not supported, and the list says so rather than showing a file that will
fail to load.

Three derived files per sky, all built by the server on first sight and
cached in a `.thumbnails` folder beside the source, which already exists:

1. `thumbnail` -- 384 by 192 tone-mapped JPEG. A 2:1 strip, never a square
   and never a sphere.
2. `light` -- 1024 by 512 flat RGBE `.hdr`, about 2 MB, used for lighting.
3. `background` -- 2048 by 1024 tone-mapped JPEG, used for the visible sky.

`hdri_preview.py` already decodes Radiance with the standard library alone
and already writes PNG by hand; it gains a downsampler and a flat RGBE
writer. This is the change that makes the whole wave affordable. Param's
327 MB sunset currently costs about 512 MB of float plus a 1 GB peak to
prefilter (M6); after this it costs 4 MB of float, a 16 MiB PMREM peak and
a 2k JPEG for the background. Two cheap textures doing one job each beat
one expensive texture doing both badly.

Exactly one sky is resident. The PMREM is built by hand so no dispose
listener is attached to the source (M7), and the swap order is: build the
new one first, detach, dispose the old, attach. Detaching before disposing
stops the renderer touching a freed framebuffer mid-frame; building before
freeing avoids a frame with no lighting. The transient two-PMREM peak at 1k
is about 12 MiB and is not worth optimising away.

```js
async function buildSky(name) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();          // overlap compile with the fetch
  const src = await new HDRLoader().setDataType(THREE.FloatType)
    .loadAsync("/api/hdri/" + encodeURIComponent(name) + "/light");
  const target = pmrem.fromEquirectangular(src);
  const estimate = estimateSunFromEquirect(src.image.data, src.image.width, src.image.height);
  src.dispose();                                  // safe: no listener was attached
  pmrem.dispose();
  return { target, estimate };
}
```

`setDataType(THREE.FloatType)` stays, because `estimateSunFromEquirect`
wants Float32 and at 1024 by 512 the cost is 4 MB. The existing test that
pins it therefore stands unchanged.

Browsing follows Twinmotion's taxonomy, derived from the filename and
stored per sky in `bench/studio/skies.json` once classified: Low sun,
Morning and afternoon, Noon, each split Clear / Cloudy / Overcast, then
Indoor, Outdoor, Studio. A sky that cannot be classified sits in
Unsorted, which is a category and not an error.

`refreshHdriList` is called once at boot so the Sky trigger shows a
thumbnail rather than the placeholder word. This is a current defect: today
the list is reachable only by entering HDRI mode.

### L9. The sun on the strip

The selected sky's 2:1 strip becomes a live canvas carrying a draggable sun
handle, with azimuth and elevation printed beside it. This is KeyShot's
HDRI Editor, and it is the right instrument because the sun in an HDRI is
visible in the image: you drag the bright spot, not an abstract angle.

Under it, a compass and a north offset, which is D5's Geo Sky.

The existing solar model in `fields.js` stays exactly as it is and keeps
its tests. It drives the procedural sky mode. In HDRI mode the strip drives
`scene.environmentRotation` and `scene.backgroundRotation` together, which
must be set to the same Euler or the reflections disagree with the visible
sky. There is no single property that does both.

### L10. The prop library

The root is a folder Param picks. The manifest is `props.json` in that
folder, in the shape it already has. A `.glb` with no manifest entry is
still offered: the label comes from the filename, and the model is trusted
to be in metres rather than being scaled.

That last point is a change. Today every prop is scaled to a declared
`heightMetres`. Poly Haven models are authored in metres and correct
already, so scaling them to a guessed height would be wrong. The rule
becomes: scale only when the manifest says `heightMetres`, otherwise trust
the file.

Thumbnails follow Blender's written rules: transparent PNG, no lighting rig
beyond a single matcap, the subject inside a 0.16 margin on all sides, a
bottom-left to top-right flow, and silhouettes left deliberately varied so
tiles stay distinguishable at 120px. Scale is communicated as printed text
under the label, the real bounding size in metres, not by a scale figure.
A `thumbs/<key>.png` in the library folder is used when present; otherwise
the preview rig renders one and caches it.

Budget, enforced by the fetch script rather than hoped for:

| Class | Triangles | Bytes |
| --- | --- | --- |
| Hero | 40k to 80k | 1.5 to 2.5 MB |
| Mid | 8k to 25k | 300 to 800 KB |
| Clutter | 1k to 4k | 50 to 150 KB |

Whole folder under 60 MB; entourage on screen under 1.2M triangles. A prop
that misses its budget fails the build rather than quietly bloating the
scene.

`meshopt_decoder.module.js` is vendored, one file, and wired beside the
existing `GLTFLoader`. KTX2 is not, in this wave: it needs seven files and
a `detectSupport` against the renderer, and it deserves its own change.

`castShadow` goes off for grass, flowers and ground litter, set from the
manifest `group`. Draw calls become the bottleneck before triangles do, and
nobody will miss those shadows.

The `group` field, which the client ignores today, becomes the grid's
grouping.

### L11. The fetch scripts

Two Python scripts under `tools/`, written to run on Param's machine
because the sandbox this is built in has no shell network:

`tools/fetch_polyhaven.py` reads `https://api.polyhaven.com/assets?t=textures`
once for the whole catalogue, `/files/<slug>` for URLs, and writes into a
target folder in the QS stack layout: `<family>/<name>/colour.jpg`,
`normal.png` from `nor_gl`, `roughness.png`, `ao.png`, `height.png` from
`disp`, a `material.json` in QS's own shape with `site`, `source`,
`licence` and the md5s the API supplies, and the `lod/` tiers by QS's rule.
`dimensions` in millimetres becomes `tileMetres` in metres.

`tools/fetch_ambientcg.py` does the same against
`https://ambientcg.com/api/v3/assets`, whose `dimensions` object is in
centimetres and whose 0 means unknown, not zero. ambientCG is preferred for
construction materials: Tiles 164, Paving Stones 155, Ground 126, Bricks
115, against Poly Haven's whole 856-asset texture library, and its tiles run
physically larger, which suppresses visible repeat across a vault span.

`tools/fetch_props.py` reads `/assets?t=models`, downloads the `.gltf`, its
`.bin` and its textures using the exact URLs the API returns and never a
substituted one (M13), then runs a `gltf-transform` pass (copy, weld,
simplify, resize 1024, prune, dedup, meshopt) to emit one self-contained
`.glb`, because the prop route rejects any filename containing a path
separator and there is no way to serve a sidecar.

All three send a User-Agent naming the studio, which Poly Haven's terms
require, and all three verify every file against the md5 the API supplies.
A "Powered by Poly Haven" line goes in the library panel, which their API
terms ask for and which costs nothing.

None of the three can be tested against the live API from here. They are
written carefully, they check what they fetch, and Param runs them. The
material library needs none of this on day one, because his QS library is
already 158 materials deep.

### L12. The panel, to Spectrum

Numbers, all from the published token data:

- Panel 260px wide, resizable 200 to 400. It is 300px today.
- Controls 32px tall; 24px for list rows and filter chips.
- Spacing unit 4px, steps 4, 8, 12, 16, 24, 32.
- Type: 11px tile labels and metadata, 12px secondary, 14px body and
  controls and panel titles, 16px section headings, 18px rare. Line heights
  14 / 16 / 18 / 20 / 22, letter-spacing 0.
- Four surfaces and no more: viewport rgb(17,17,17), panel rgb(27,27,27),
  elevated and popover rgb(34,34,34), inset well behind a grid rgb(44,44,44).
  Borders rgb(57,57,57). Disabled rgb(68,68,68). Focus ring rgb(64,105,253)
  at 2px. Shadows rgba(0,0,0,0.24) ambient and rgba(0,0,0,0.36) key, which
  is about three times their light-theme opacity.

Behaviour, from the cross-cutting patterns every serious tool shares:

- A library opens as a section with a grid, closes to a picker row showing
  what is chosen. One control opens it, one closes it.
- Search matches name, family and tag at once, across the whole library and
  not only the open category.
- Size is a small set of named steps, never a free slider.
- The grid never shows a partial row.
- Placement keeps both gestures: click a tile to carry, click the viewport
  to drop, which is already built and which is what makes placing twenty
  trees bearable.

`panel-proof.html` gains a boundary check per rule, so a violation is
caught locally rather than by Param.

### L13. Renderer corrections

- `shadowMap.type` becomes `PCFShadowMap`. `PCFSoftShadowMap` is
  deprecated and silently downgraded anyway (M9), so the current setting
  buys a console warning and nothing else. Quality then comes from a shadow
  camera fitted to the model bounds, `mapSize` 2048, `normalBias` about
  0.02 and `radius` 3 to 6, which now genuinely controls softness.
- `toneMapping` becomes `NeutralToneMapping` with exposure 1.0 (M10), and
  AgX is offered as a second preset for a dramatic sun view. Brightness is
  driven by light intensities and `scene.environmentIntensity`, so the
  numbers stay physically meaningful.
- `renderer.shadowMap.autoUpdate = false` with `needsUpdate = true` on
  change, so an orbit-only view skips the shadow pass.
- The preview rig's tone mapping is set to match the viewport's, so a
  material swatch is the colour the material will be.

### L14. Defects fixed on the way

Each was found by reading the code during this research and each is cheap:

1. `restoreProps` guards on `PROP_BUILDERS[entry.type]`, which never holds
   a library prop, so every library prop is silently discarded when a study
   is loaded. The guard must accept a template too.
2. `setPropEmissive` writes emissive on materials shared with the template,
   so selecting one tree lights every tree. Selection draws an outline
   instead.
3. `applyScene` writes to `control("joint-gap")` and `control("taper")`,
   both removed from the page, and throws on any scene carrying those
   numbers.
4. `refreshHdriList` is never called at boot, so the Sky picker shows a
   placeholder until HDRI mode is entered (L8).
5. `concrete-slab` ground grain scales with disc size (L6).
6. `vendor/three.core.js` is 1,443,056 bytes against a reported 1,443,059
   for three@0.185.0. Every other vendored file matches byte for byte.
   Given this machine's history of OneDrive name-clash files splitting
   content, this gets one checksum before anything is built on it.

## Not in this wave

- KTX2 and Basis compressed textures. Seven files and a `detectSupport`
  call, and a second renderer in the preview rig that may or may not
  transcode. Its own change.
- Draco. Rejected outright: the geometry here is backend-generated, not
  shipped as authored glTF.
- Frankot-Chellappa in JavaScript. Nothing needs it while every QS material
  ships a height map.
- The WebGPU switch. The probe stands; three.js has no Lumen equivalent and
  claiming otherwise would be dishonest.
- People and cars. They are CC-BY, not CC0, and they need a credit surface
  in the UI and a dated record of the licence on file. Worth doing, after
  the CC0 spine is in.
- Writing anything into the QS Library. The studio reads it and nothing
  more.

## Testing

Every new test must be proved able to fail by mutation before it counts.

- `hdri_preview.py`: the downsampler and the RGBE writer get a fixture with
  two different exponents four steps apart, so a decoder that ignores the
  exponent cannot pass.
- The material index: a temporary tree in the QS layout, including a
  material with no AO and one with an empty `tiers`, pinned against the
  route's output.
- `tileMetres` conversion: Poly Haven millimetres and ambientCG
  centimetres both to metres, and ambientCG's 0 to null.
- The tiling formula, in `fields.js` where `groundRepeat` already lives, so
  it is pure and testable.
- The sky swap: that the source is disposed and the target is not, by
  counting.
- Every element id the script asks for still exists on the page. This test
  already exists and has already caught a shipped fault; it runs first
  after every markup edit.
- The panel proof sheet reports no boundary faults.

## Global constraints

- Never touch the main worktree at "VS code\COMPAS Workflow".
- Never edit anything under `plugin\`.
- Never run `git worktree` commands.
- Never write into the QS Intelligence library.
- No em dashes anywhere. Use "--".
- No Co-Authored-By and no AI attribution in any commit or file.
- Commit locally after every fix. Never push.
- `git add` by explicit path only.
- Run the OneDrive clash scan before every test run and every commit.
- Exporter-side requests go to REQUESTS-for-plugin-session.md.
