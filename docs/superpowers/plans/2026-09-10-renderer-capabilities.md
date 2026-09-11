# Renderer capabilities implementation plan

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans to work this task by task. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** turn Vaulted from a tool that photographs a vault into one that
draws it -- sectioned, measurable, and printable at plate resolution.

**Spec:** `docs/renderer-feature-research-2026-09-10.md`, approved by
Param on 2026-09-10 ("i am completely on board with all of this"), with
two corrections recorded below that the spec itself does not carry.

**Architecture:** everything here is additive to the existing three.js
composer stack. No renderer replacement, no WebGPU migration, no second
material model. The one structural change is a seventh panel section,
Output, which takes the Record block out of Animation so the still and
the video sit in one job document.

**Tech stack:** three.js r185 (EffectComposer, RenderPass, OutputPass,
ShaderPass), FastAPI, Pillow server-side, vanilla ES modules.

---

## Corrections to the spec, binding on this plan

The overnight research was produced by a ten-agent fan-out whose
inventory agent read `studio.js` and never opened `fields.js`. Two of its
five headline items were therefore wrong about the codebase. Both are
settled; neither is open for re-litigation by a task.

1. **The geographic sun already existed** and is already accurate:
   `fields.js:619` runs the NOAA/Meeus position with the equation of
   time and Bennett's refraction, validated in its own comment to 0.13
   degrees worst case. Only the CONTROLS were missing, and they shipped
   in `120054c` along with a clock fix the controls exposed. Spec section
   2.1 is closed.
2. **The grade sits after the tone mapper deliberately.**
   `studio.js:339` states the reason: contrast pivots around mid grey,
   which is only meaningful in display space. Spec section 2.4 proposes
   reordering without noticing it overturns a reasoned choice. The EV,
   white balance and LUT half stands on its own; THE REORDER IS GATED ON
   A MEASUREMENT (Task 9a) and may be rejected.

3. **BOTH of the spec's Wave 2 traps are false for this codebase.**
   Measured 2026-09-10, before building anything:
   - "The inked outline ribbon takes its width as a screen-space uniform, so
     at 8K it thins to a hairline." It does not. `studio.js:10204` is
     `transformed += outlineSide * outlineWidth` in the VERTEX shader, in
     object space, and the dial is `min="0" max="0.025"` metres shown as
     millimetres. The ribbon is a WORLD-space width, so a 4961 px plate gives
     it 2.6 times MORE pixels than 1920 does, which is correct for a physical
     line on stone. No supersample scaling is needed and adding one would make
     it wrong.
   - "Any pass reading resolution must be handed the full frame size, not the
     tile size, or you get seams." There are no such passes. The whole
     composer is three: `RenderPass`, `OutputPass`, and
     `ShaderPass(BrightnessContrastShader)` (`studio.js:369-373`), and a
     search for `resolution`, `texelSize` and `pixelSize` uniforms across all
     12,700 lines returns nothing. Every one of the three is per-pixel or
     whole-scene, so tiling cannot seam from this cause and the grade does not
     have to move server-side.

4. **A real blocker the spec did not have.** `studio.js:274` builds the
   renderer as `{ canvas, antialias: true, preserveDrawingBuffer: true }`,
   with NO `alpha: true`. Alpha is a context-creation flag and cannot be
   turned on afterwards, so Task 6 needs either that flag added at
   construction or the still rendered into an offscreen target rather than
   read off the canvas. The recorder reads the canvas today
   (`canvas.toBlob`, `studio.js:12188`), which is why `preserveDrawingBuffer`
   is set.

Also already shipped, ahead of this plan: the orthographic camera, six
snapped views and the scale bar (`b1b3feb`), and the section plane
(`4bf4d46`).

---

## Global Constraints

Copied verbatim in force for every task below.

- **The interface language governs every control.**
  `docs/studio-interface-language.md`, enforced by tests. A dial is four
  things in one order inside a `.dial-block`: `<span>name</span>`, the
  range input, `<b id="<slider-id>-value">`, `<em>unit</em>`. `data-unit`
  turns on where the dial RESTS, not on its `min`.
- **The folder is the authority for props**, not `props.json`. See
  `docs/` and the prop-library memory before touching either.
- **Run the suite with the worktree venv**: `./.venv/Scripts/python.exe -m
  pytest tests -q`. PATH python is the comfyui venv and importing
  `serve.py` under it starts a real studio on port 8600.
- **Every new test must be proved able to fail** by mutation, and every
  mutation target must be unique in its file.
- **Never let a backslash reach the shell.** Build one with `chr(92)` or
  use the Write tool. A `\b` written through a heredoc becomes a literal
  backspace byte and silently makes a regex-based test vacuous.
- **Commit after every task**, `git add` BY EXPLICIT PATH only. No AI
  attribution in commit messages.
- **No em dashes** anywhere, in code, comments, docs or commits.
- **Scan for OneDrive name-clash files** before any test run or commit.
- Browser-verify anything visual with a puppeteer probe against the live
  studio on 8600. A test that reads source text is not evidence that a
  pixel changed.

---

# WAVE 1 -- THE DRAWING

The two items that make an orthographic plate a drawing rather than a
picture. Both small, both blocking nothing, both high value.

## Task 1: Section plane with a filled cut -- DONE (4bf4d46)

> **What the cut face turned out to need: nothing.** The cheap cap in
> step 5 below was built, photographed and deleted. A section is viewed
> FACE ON, so a plane whose normal points at the camera fills the frame
> as a backdrop rather than reading as a cut face; to read as one it
> would have to be trimmed to the outline of the cut, which is the work
> the cheap version existed to avoid. And it is not needed here: every
> vault material in this studio is already `THREE.DoubleSide`, so a
> clipped closed solid draws its own interior and the cut caps itself.
> The folklore assumes single-sided materials. A flat POCHE still wants
> the stencil two-pass, and the cut-fill colour belongs to that wave.
>
> Two faults the browser found that the plan did not predict: the offset
> dial ran -30 to 30 over a barrel 3.2 m deep, so it now takes its range
> from the shell; and `buildScene` had to re-apply the section, because
> a clipping plane lives on a material and every mesh a rebuild makes
> arrives uncut.

**Files:**
- Modify: `bench/studio/static/studio.js` (clipping setup, Section block
  wiring, scene save and restore)
- Modify: `bench/studio/static/index.html` (Scene panel, new Section block)
- Modify: `bench/studio/static/studio.css` (the block)
- Test: `tests/studio/test_remote_access.py`

**Interfaces:**
- Consumes: `renderer`, `scene`, `state`, the existing prop gumball, and
  `applyCameraFrustum` from `b1b3feb`.
- Produces: `state.section = {mode, axis, offset, colour, cutMachine}`,
  `applySection()`, and a `section` block in the saved scene document.

Why it is first: the argument is inside the shell. Voussoir joint
geometry, shell thickness varying with thrust, the net under the
masonry, the interface between permanent works and plant -- none of it
is visible from outside. Both judges independently said build the
section BEFORE GTAO, because it interacts with post-processing depth.

- [ ] **Step 1: Write the failing test**

```python
def test_a_section_shows_a_filled_cut_and_not_a_hollow_shell():
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "renderer.localClippingEnabled = true;" in js
    section = _js_function(js, "function applySection()")
    assert "material.clippingPlanes" in section or "clippingPlanes =" in section
    # The cap is the point. A clipped shell with no cap reads as a
    # hollow eggshell, which is the opposite of the claim being made.
    assert "sectionCap" in js, "the cut face is drawn, not left open"
```

- [ ] **Step 2: Run it and watch it fail**

`./.venv/Scripts/python.exe -m pytest tests/studio/test_remote_access.py -k section -q`
Expected: FAIL, `renderer.localClippingEnabled` absent.

- [ ] **Step 3: Turn on local clipping and add the state**

In `studio.js`, beside the renderer setup:

```js
// Local, not global: a clipping plane on the renderer would cut the
// gumball, the thrust arrows and the sun widget's own helpers along
// with the vault. Per-material is what lets the section cut the shell
// while the machine stays whole, which is a toggle Param asked for.
renderer.localClippingEnabled = true;
```

State, beside `projection`:

```js
  section: { mode: "off", axis: "y", offset: 0, colour: "#b8b0a4",
             cutMachine: false },
```

- [ ] **Step 4: Write `applySection`**

One plane, built from axis and offset, assigned to every material that
should be cut. The plane's constant is negated offset because
`THREE.Plane` keeps signed distance from the origin along its normal.
Walk `scene` once and set `clippingPlanes` on shell, voussoir and net
materials; skip machine materials unless `cutMachine`.

- [ ] **Step 5: Draw the cheap cap**

A coloured plane one millimetre behind the cut, sized to the scene's
bounding sphere, oriented to the cut normal, added and removed with the
mode. Visually indistinguishable from a stencil cap in a still, and the
stencil two-pass version is three days and gets slower across 1500
separate closed solids.

- [ ] **Step 6: Wire the Section block**

Off / Plane / Box segmented control (Box refuses for now and says so),
axis segmented control, an offset dial in metres, a cut-fill colour, and
a "cut the machine too" checkbox. Dial obeys the interface language.

- [ ] **Step 7: Save and restore `state.section` with the scene**

- [ ] **Step 8: Run the tests, then browser-probe it**

A probe that switches to orthographic, snaps to front, turns the section
on, sweeps the offset, and screenshots at three offsets. Assert the
images differ and that no frame is empty.

- [ ] **Step 9: Mutation round, then commit**

At least: the cap disappears; the plane's constant loses its sign; the
machine is cut when it should not be; clipping is global not local.

## Task 2: The orthographic remainder -- DONE (60665d7, cfd35d1)

> **One of the four was built, one became something better, two were
> refused.** All four were measured before anything was written.
>
> - **View width in metres: BUILT.** Reading verified against geometry
>   (46.39 against 46.39), and a typed 12 m gives a frame exactly 12.00 m
>   across. Typing writes `zoom`, not `orthoFrameHeight`, so a wheel notch
>   carries on from it.
> - **Shadow camera: the reframe was a phantom, the fit was not.** It was
>   framed for neither the view nor the model but a hard-coded 60 m
>   square, so the projection never touched it. Fitting it to the casters
>   took texels from 29.3 mm to 11 to 16 mm across all four studies.
> - **Backdrop: REFUSED.** Photographed in three environment modes and
>   both projections. The dome does not read as a painted wall under a
>   parallel projection; it reads as a nearly uniform sky, which is
>   correct and is closer to a usable plate than the perspective version.
> - **Scale-ratio presets: DEFERRED to Wave 2.** A 1:50 button is a claim
>   about the printed page and cannot be kept without the output size,
>   which the resolution ladder brings. One of its two blocking faults,
>   that the scale could not survive a reload, is already fixed by the
>   restore repair in `cd56ad0`.



**Files:**
- Modify: `bench/studio/static/studio.js`, `index.html`, `studio.css`
- Test: `tests/studio/test_remote_access.py`

Four items the spec asked for in 2.2 that `b1b3feb` did not ship.

- [ ] **Step 1: View width in metres, replacing the mm readout in ortho**

The 35mm-equivalent figure is meaningless under a parallel projection.
Swap the `camera-mm` readout for `orthoFrameHeight / zoom * aspect` when
orthographic, and put the unit back when not.

- [ ] **Step 2: Scale-ratio presets**

1:20 / 1:50 / 1:100 / 1:200 as buttons that set the zoom so that one
metre of model is the right number of millimetres on the printed page.
This needs the OUTPUT size, not the viewport, so it depends on the
Output panel's resolution and page size -- so the buttons set a
`state.printScale` and the true snap lands in Task 3. Until then they
solve against A3 at 300dpi and say so in the title.

- [ ] **Step 3: Reframe the sun's shadow camera to the ortho view volume**

The directional light's shadow camera is framed for the perspective
view. Under a wide parallel projection the shadow map covers a fraction
of what is visible and everything outside it is unshadowed.

- [ ] **Step 4: The backdrop under a parallel projection**

A grounded skybox dome reads as a painted wall in ortho, because a
parallel projection has no vanishing point for it to recede to. Swap for
a flat backdrop while orthographic.

- [ ] **Step 5: Tests, mutation, commit**

---

# WAVE 2 -- THE PLATE

## Verified before building, 2026-09-10

A 25-agent recon read the export subsystem and three refuting lenses tried
to break each finding. It confirmed both of the corrections above
independently, and found three traps the spec did not have. All five are
checked against the code by hand.

1. **Reusing `/api/frames` would DELETE the user's take.** `post_frame`
   unlinks every `frame-*.png` and `frame-*.jpg` in the study's frames
   directory whenever `frame == 1` (`app.py:2073-2082`), deliberately, so
   a shorter re-recording cannot inherit the previous take's tail. A still
   export POSTing tile 1 to that endpoint destroys a recording. The still
   needs its OWN endpoint and its own directory.
2. **Alpha is not one flag.** Beyond the missing `alpha: true`, in sky
   mode the backdrop is a scene MESH, not `scene.background`
   (`studio.js:601-603`), so a transparent plate needs the sky mesh, the
   grounded dome and the ground disc all hidden, not just a clear alpha.
3. **Everything lands in OneDrive.** Frames go to
   `STUDIES_DIR/<slug>/studio/frames`, inside this repo, and the finished
   take is delivered to a OneDrive Animation folder (`app.py:61-64`).
   OneDrive churn is what once throttled a 935-frame take to a crawl.
   Twelve tiles is not 935 frames, but the still's directory should be
   chosen deliberately rather than inherited.
4. **A3 cannot be composed in the viewport at all.** `camera-aspect`
   offers fill, 16:9, 4:3, 1:1, 4:5 and 9:16 (`index.html:404-412`), and
   A3 landscape is 1.4142, which is not among them. `applyCameraAspect`
   only letterboxes those six, so the frame Param would be rendering
   cannot currently be seen. A page-shaped ratio has to arrive with the
   resolution ladder.
5. **Trap 2 is not wrong, it is EARLY.** There are no resolution uniforms
   today, so tiling is seam-free and the grade can stay client-side. It
   becomes real the moment GTAO, bloom or FXAA lands, all of which are in
   the queue. Record it as a constraint on those items rather than as
   work here.



The four-day feature the whole report is really about. An A3 plate at
300dpi is 4961 x 3508 and the recorder stops at 1920, so every figure in
the thesis currently goes to press as an upscale.

## Verified overnight, 2026-09-11: the scatter

Param asked for the scattering to be understood before it was thickened.
Three findings, each measured before acting.

1. **The variants were never fused by Poly Haven.** grass_medium_01
   arrives as SEVENTEEN named nodes (tiny_a..large_c), grass_bermuda_01
   as 21, dandelion_01 as 5. It was fetch.mjs's own join() (default
   keepNamed: false) that welded them into one primitive, and the
   connected-component sweep in split.mjs then reverse-engineered
   boundaries the file already had, finding 8 of 17. The fetch now
   keeps named nodes and split.mjs cuts on them first; the sweep is the
   fallback for a file that truly is one primitive (shrub_01, shrub_04).
   A node whose plan footprint sits 80% inside another is a PART, not a
   variant (pachira_aquatica_01 = bark_a..d + leaves_a..d = four trees).
   32 rows became 201 variants in 32 families.
2. **The vault kept out by one disc of half its diagonal**, a 12 m
   circle round a 23 x 4 m vault, so nothing could stand along either
   long side and the readout said "nothing fitted" as often as the
   spacing did. It is a capsule now: discs the width of the short side,
   stepped along the long one.
3. **A placed prop kept out by a fixed 0.6 of its footprint**, blind to
   the spacing dial and to its own scale, so a second stroke could never
   touch a first however low the dial went. It keeps out by
   footprint x scale x spacing now.

Measured with the same 3 m brush, seed 7, grass_medium_01 + dandelion_01:
about 1 item per stroke before the split, 15.9 per m2 after it, 28.7
per m2 after the keep-out fixes. Dart throwing jams at about 0.547 area
fraction (random sequential adsorption), so Bridson Poisson-disc growth
is the next step if he wants denser still; it is not built.

Poly Haven is exhausted for grass (three grasses exist there in total).
More grass, meadow flowers and every tree come from Fab into the UE 5.4
project, through tools/props/ingest.mjs, and that list is his.

## Verified 2026-09-11, morning: the field's frame rate

Param's readout over a 25,375-prop field: 48,078 draw calls, 88.5 M
triangles, 2 fps, GPU 6%, CPU 8% (one core of sixteen flat out). The
bottleneck was draw submission on the main thread, not the GPU.

1. **Instancing.** A placed library prop is one instance of its
   variant's batch. The record and record.object survive; the object is
   a proxy outside the scene graph, and settlePropInstances copies what
   changed into per-variant, per-mesh, per-tier InstancedMeshes once a
   frame. Picking maps the hit's instanceId back to its record; the
   outline, the gumball, the carry, the stamp, the layer eye and every
   undo work unchanged.
2. **Distance tiers.** tools/props/lod.mjs cuts geometry-only sidecars at
   0.35 and 0.12 of LOD0, borrowing LOD0's materials. The first cut
   pruned the UVs with the textures and was caught before any client
   read it. A Detail control (Draft, Balanced, Full) sets how soon
   distant props drop a tier; stills and takes always render Full.
3. **Per-instance culling** of whatever casts no shadow; casters are
   never culled, because a tree behind the camera still shades the frame.
4. **The stroke.** Left button paints and drags, middle orbits, right
   pans; the keep-out is a uniform grid (4,000 darts against 25,000
   discs: 353 ms to 2.6 ms) and one index serves a whole stroke.
5. **The undo that failed** was browser storage: five megabytes of
   layout written per gesture, and once per prop by an undone stroke.
   Layouts are compact rows now, written once the gestures stop, with a
   server copy beside the study.

Measured on the 4090 in the studio's own readout, 25,000 props: 476 draw
calls, 15.9 M triangles at Balanced (88.4 M at Full), 129 fps still, 75
fps orbiting; a dragged stroke of 7,080 props in 363 ms; its undo in one
press; the layout 953 KB in the browser and whole on the server.

## Task 3: The Output panel

A seventh panel section. It holds the still-render controls and it TAKES
the Record block out of Animation, output folder included, so "Record
1080p" becomes "Record" against the same resolution ladder. Nothing else
moves.

Resolution presets are named for the page -- 2K, 4K, 8K, A3 at 300dpi,
A2 at 300dpi, custom -- because 4961 x 3508 means something to Param and
"8K" does not.

## Task 4: Tiled rendering

`camera.setViewOffset(fullW, fullH, x, y, tileW, tileH)` gives the tile
frustum. 2048-pixel tiles, POSTed as they finish, stitched server-side
with Pillow.

**The trap, recorded before it bites:** any pass reading resolution must
be handed the FULL frame size, not the tile size, or there are seams.
Tile only the beauty pass and grade the stitched image server-side.

## Task 5: Jittered accumulation

The same `setViewOffset` call supplies the sub-pixel jitter, which is
why tiling and accumulation ship together rather than as two waves.
Jitter each tile N times into a half-float target, accumulate, divide.

**Why not separately:** tiles alone give an 8K plate whose joint lines
alias worse than the 1080p one did, because a lattice of thousands of
small quadrilaterals each carrying a hard outline is the worst possible
subject for single-sample rasterisation.

**The second trap:** the inked outline ribbon takes its width as a
screen-space uniform, so at 8K it thins to a hairline unless the uniform
is scaled by the supersample factor. The ribbon is the best thing in the
studio; it must not die at the moment it finally has the resolution to
be seen.

## Task 6: Alpha

`setClearAlpha(0)` with sky and fog suppressed, watching premultiplication
through the copy pass. A vault on a transparent background drops onto a
white page with no sky and no horizon line, which is how most structural
figures ought to be presented and is currently impossible.

## Task 7: The frame stamp

Drawn with Pillow AFTER stitching, so it lands at output resolution. A
stamp reading `study 07, t = 180 mm, limestone, 1412 voussoirs,
q = 4.6 kN/m2, sun 21 Jun 13:20, EV 13.3` turns a picture into evidence
and answers what a viva panel asks. Default off for figures, on for
appendix plates. Token string editable.

## Task 8: Region re-render

The same `setViewOffset` call with one tile. Half a day.

---

# WAVE 3 -- THE IMAGE

## Task 9: Exposure, white balance and a LUT slot

Replace Brightness and Contrast with Exposure in EV, White balance in
kelvin, Tint, Contrast, Saturation, Highlight, Shadow, plus a `.cube`
chooser and an intensity dial. `LUTPass` and `LUTCubeLoader` ship in the
r185 addons and read the files Lightroom and Resolve write.

`EV100 = log2(N^2 / t) - log2(S / 100)` collapses exposure base, sky
brightness and brightness into one number that can go in a caption.

White balance is a Bradford chromatic adaptation matrix: four constants.

### Task 9a: MEASURE before reordering the grade

Gated, per the correction above. Produce the same plate through both
orders -- grade-after-tonemap as today, and grade-in-linear-then-tonemap
-- on a bright-sky-over-dark-soffit shot, which is Param's most common
and the case the spec says is broken. Compare. Only reorder if the
measurement shows it. If it does not, record the rejection in the
research document beside the shadow-map one.

---

# THE QUEUE BEHIND THESE

Not yet planned in task detail. Rulings from the spec are recorded so
they are not re-argued when each is reached.

1. **Object ID buffer** (2-3 days). One override material writing a
   per-piece colour to an offscreen target plus a JSON legend. Unblocks
   voussoir picking, per-piece stress readout, course isolation,
   exploder targets and a compositing matte: four features behind one
   capability.
2. **GTAO** (2 days). AFTER the section plane, not before. 64 pixels of
   overscan per tile in a tiled render or it leaks at every boundary.
3. **Cascaded shadow maps** (2 days). One 2048 map over 60 m is roughly
   3 cm texels, so every bed joint casts a stepped line. The joint
   shadow is structural information here.
4. **Soffit bounce** (an afternoon for the cheap version). CubeCamera
   under the crown through PMREMGenerator as `scene.environment`. Do the
   thirty-line version, look at it, then decide about the probe grid.
5. **Clay and white-model mode** (1 day). `scene.overrideMaterial` with
   an exemption list. Structurally significant: the skin decides which
   of the seven analysis classes the run uses.
6. **Light lister with solo** (1 day) and one shadow-casting spot per
   fixture with a cookie texture. REJECT IES and RectAreaLight, for the
   reasons in spec section 4.
7. **Wind** (half a day). Vertex displacement weighted by height above
   the instance origin, driven from the recorder's FRAME INDEX and never
   `performance.now()`, or a re-render will not match the take it
   replaces.
8. **Wet dial** in Skin (thirty lines). Wet limestone reveals double
   curvature through highlight roll-off in a way dry matte stone never
   does.
9. **Measure group** in Props: Dimension, Scale bar, Label, Callout, as
   ordinary prop records. Use troika-three-text, NOT CSS2DRenderer: DOM
   labels vanish silently from a WebGL readback, so the recorder and the
   still export would drop every annotation without saying so.
10. **Shots and a server-side queue** (5 days). A shot is a sparse diff
    over the scene document plus frame range, resolution and channels.
11. **Analysis: selected-piece block**, in the register the disabled-lens
    tooltips already use.
12. **Skin: Rendered / Clay / White model** segmented control, above the
    picker rather than inside it.

## Explicitly not being built

Recorded so nobody proposes them again: volumetric clouds, rain, snow,
puddles, the season slider; a second renderer or in-browser path
tracing; the WebGPU migration; lens flare, dirt, chromatic aberration,
barrel distortion, film grain, motion blur; terrain sculpting and
screen-space reflections; animated characters and vehicle paths;
instanced scatter; IES profiles and RectAreaLight; real Cryptomatte;
OpenColorIO; an illuminance lens in lux; and per-face material painting
on the vault. Bloom is conditional: retry as a half day AFTER the grade
work, and only when a night plate appears on the storyboard.
