# What Vaulted should grow next

*Overnight report, 10 September 2026. Two independent reviews, reconciled and ruled on. Everything below is costed in working days for one person on this codebase.*

---

## 1. THE SHORT ANSWER

1. **Geographic sun.** Latitude, longitude, date and a north offset dial. Half a day, and it turns every shadow you have ever rendered from arbitrary into true.
2. **Orthographic camera** with snapped plan, section and the four elevations, a view width in metres and a printed scale. Two days, and it is the plate that goes opposite the equilibrium proof.
3. **Print-resolution still export**: tiled rendering with jittered sample accumulation, an alpha channel and a burned-in frame stamp. Four days, and it ends the era of every thesis figure being an upscale.
4. **Move the grade into linear, before the tone map**, and express it in stops with a white balance and a .cube LUT slot. Two days, and it retrospectively improves every image the studio is capable of making.
5. **Section plane with a filled cut face.** An afternoon for the cheap cap, and it is the single most valuable image Vaulted currently cannot make.

Those five are three weeks. Do them in that order and stop reading the rest of this until they are done.

---

## 2. THE CASE FOR EACH

### 2.1 Geographic sun

**What it is.** A typed latitude and longitude with saved site presets, a date field, and a north offset dial reading 0 to 360 degrees. The NOAA solar position routine is about sixty lines of arithmetic: Julian day, equation of time, declination, hour angle, then altitude and azimuth. North offset is a single Y rotation applied to the derived azimuth before the light is aimed.

**What it changes.** Hardcoded London and whatever today happens to be is not a missing feature, it is a factual defect in a thesis. A Welsh site is roughly 1.5 degrees of latitude and 3 of longitude off London, and the solstice-to-solstice altitude swing there is over 45 degrees, which changes every shadow on a curved soffit and decides whether an oculus shaft lands on the floor or on the wall. North offset is the more urgent half, because Grasshopper models never arrive with Y pointing north, so every shadow in every image you have produced so far is arbitrary. A solstice pair from one fixed camera is a standard plate in this field and you cannot currently produce it.

**Where it lives.** Scene, in a new Site block directly above the existing sun compass. The day track re-bakes off it.

**Cost.** Half a day. The hard part is already done, because the compass sets the time and lets the solar model derive elevation rather than inventing two independent angles. You are plugging a better model into an interface that already assumes one.

**Ruling.** Judge 1 put the orthographic camera first and this third; Judge 2 reversed them. Judge 2 is right. This is half a day against two, it corrects a statement of fact rather than adding a capability, and it makes the day track and the day cycle honest instead of decorative. Do it before breakfast on Monday.

### 2.2 Orthographic camera

**What it is.** A projection switch beside the frame-ratio control, six snapped view buttons (Plan, North, South, East, West, Section), the 35mm-equivalent readout swapped for view width in metres, and 1:20 / 1:50 / 1:100 / 1:200 snap presets with a ground-plane scale bar.

**What it changes.** A perspective photograph of a funicular vault is evidence of nothing measurable. The entire claim of the work is that a thrust line has been made solid, and a reader cannot measure rise-to-span off a converging image, cannot overlay it on a Grasshopper section, and cannot set it beside a graphic-statics diagram at the same scale. Note that both Twinmotion and Lumion file this under *Architectural* rather than under *Camera*, which tells you how architects actually reach for it.

**Where it lives.** Camera, in a new Projection block above FOV.

**Cost.** Two days, of which the camera itself is half a day. The rest is downstream and will bite if you do not plan for it: the directional light's shadow camera needs reframing to the new view volume, the gumball's constant-screen-size trick is computed from FOV and needs an ortho branch on (top - bottom) / zoom, and the grounded skybox dome reads as a painted wall under a parallel projection, so swap it for a flat backdrop in ortho mode. Print the scale bar and the scale, or the output is a picture rather than a drawing.

### 2.3 Print-resolution still export

**What it is.** One wave, not three. `camera.setViewOffset(fullW, fullH, x, y, tileW, tileH)` gives you the tile frustum and the sub-pixel jitter from the same call, so tiling and accumulation ship together: render 2048-pixel tiles, jitter each N times into a half-float target, accumulate, divide, POST each finished tile, stitch server-side with Pillow. Resolution presets should be named for the page (2K, 4K, 8K, A3 at 300dpi, A2 at 300dpi, custom), because 4961 x 3508 means something to you and "8K" does not. Alpha rides along in the same wave: `setClearAlpha(0)` with sky and fog suppressed, watching premultiplication through the copy pass. So does the frame stamp, drawn with Pillow after stitching so it lands at output resolution. Region re-render is the same call with one tile and costs half a day more.

**What it changes.** An A3 plate at 300dpi is 4961 x 3508 and the recorder stops at 1920, so every figure in the thesis currently goes to press as an upscale, and a 1500-voussoir vault at 1920 wide gives each piece about forty pixels, which is not enough to see a joint. This is the feature that separates a presentation tool from a screen-recording tool. Alpha matters nearly as much: a vault on a transparent background drops onto a white page with no sky and no horizon line, which is how nine out of ten structural figures ought to be presented and is currently impossible.

**Where it lives.** A new seventh panel section, Output. See section 3.

**Cost.** Four days including the stamp and the region tool. Two traps that will otherwise be blamed on the renderer. First, the inked outline ribbon takes its width as a screen-space uniform, so at 8K it thins to a hairline unless you scale the uniform by the supersample factor -- and the ribbon is the best thing in the studio, so do not let it die at the moment it finally has the resolution to be seen. Second, any pass reading resolution must be handed the *full* frame size, not the tile size, or you get seams. Tile only the beauty pass and grade the stitched image server-side, which is better practice anyway.

**Rulings.** Judge 2 split tiling and accumulation into separate items. Overruled: shipping tiles alone gives you an 8K plate whose joint lines alias worse than the 1080p one did, because a lattice of thousands of small quadrilaterals with a hard outline on each is the worst possible subject for single-sample rasterisation. Judge 1 ranked the frame stamp as its own item at 89. Overruled the other way: it is an afternoon of Pillow work inside this wave, and a stamp reading "study 07, t = 180 mm, limestone, 1412 voussoirs, q = 4.6 kN/m2, sun 21 Jun 13:20, EV 13.3" turns a picture into evidence and answers exactly the questions a viva panel will ask. Default it off for figures and on for appendix plates.

Both judges also rejected `BokehPass` as the export depth of field, and they are right. Once the accumulation buffer exists, jittering the eye across an aperture disc of radius focalLength / (2 * fStop) about a fixed focal plane gives ground-truth defocus with correct foreground occlusion and real polygonal bokeh, for about twenty extra lines. Do not build two depth-of-field systems.

### 2.4 The grade, moved into linear

**What it is.** Today the composer runs RenderPass, then OutputPass, then BrightnessContrastShader, so both dials are pushing already tone-mapped sRGB values about. Reorder to RenderPass, grade in linear, tone map, OutputPass, then LUTPass. Replace Brightness and Contrast with Exposure in EV, White balance in kelvin, Tint, Contrast, Saturation, Highlight and Shadow, plus a .cube chooser and an intensity dial.

**What it changes.** This is why bright skies clip instead of rolling off, and it is why the two dials make a bright sky over a dark soffit worse rather than better -- which is your single most common shot. Expressing exposure as EV100 = log2(N^2 / t) - log2(S / 100) collapses exposure base, sky brightness percentage and brightness percentage into one honest number you can put in a caption, so a chapter of fifteen plates reads as one study instead of fifteen attempts. The LUT is the same argument at a larger scale: forty figures graded by eye over six months will look like forty projects, and one .cube applied to all of them is how it is actually done. `LUTPass` and `LUTCubeLoader` ship in the r185 addons and read the same files Lightroom and Resolve write.

**Where it lives.** Camera, as an Image block replacing the Brightness and Contrast pair.

**Cost.** Half a day for the reorder, two days for the full stack. White balance is a Bradford chromatic adaptation matrix, which is four constants. This is also prerequisite to bloom ever working, and it is the cheapest item on the list per image improved, because it improves all of them at once and retrospectively.

### 2.5 Section plane with a filled cut

**What it is.** `renderer.localClippingEnabled = true` with planes on `material.clippingPlanes` is three lines and works today. The cut face is the work. Ship the cheap cap first: draw a coloured plane a millimetre behind the cut so the shell reads solid from the camera side. Place and turn the plane with the gumball you already built.

**What it changes.** The argument is inside the shell. Voussoir joint geometry, shell thickness varying with thrust, the net sitting under the masonry, the interface between permanent works and plant -- none of it is visible from outside. A section through the crown in parallel projection, cut faces filled, inked outline on and the intrados stress lens still painted, is not a render at all. It is a drawing, and it is the money figure of the whole project.

**Where it lives.** Scene, in a new Section block (Off / Plane / Box, axis, offset, fill colour, and a toggle for whether the machine is cut too). A Section snap button appears in Camera beside the ortho views.

**Cost.** An afternoon for the clip plus the cheap cap, which is visually indistinguishable in a still. The proper stencil two-pass cap is three days and gets slower across 1500 separate closed solids, so schedule it later. One sequencing note both judges made independently: build the section before GTAO, not after, because it interacts with post-processing depth.

### 2.6 Immediately behind these

Six items that should be started the week the five above land, in this order and for these reasons.

- **Object ID buffer** (two to three days). One override material writing a per-piece colour into an offscreen target plus a JSON legend. It gives you voussoir picking, per-piece stress readout, course isolation, exploder targets and a compositing matte, which is four features blocked by one missing capability. Judge 1 ranked it 88 and Judge 2 85; the only reason it is not in the top five is that it is a foundation rather than a plate.
- **GTAO** (two days). Props currently meet the ground with no darkening whatever, which is the clearest tell that reads as computer image from across a room, and every bed joint gains a crevice shadow for free. Give each tile 64 pixels of overscan in a tiled render or it leaks at every boundary.
- **Cascaded shadow maps** (two days). One 2048 map over a fixed 60m square gives roughly 3cm texels, so every bed joint casts a stepped blocky line. Three or four logarithmic cascades over 200m gives about 5mm in the near cascade. The joint shadow is structural information here, not decoration.
- **Soffit bounce** (an afternoon). Render one CubeCamera from just under the crown, run it through PMREMGenerator, use it as `scene.environment`. Judge 1 scored this 67 and Judge 2 scored it 83. Judge 2 wins on the thirty-line version and Judge 1 wins on the week-long probe grid: do the cheap one this week, look at it, and only then decide. A concave soffit lit by a flat hemisphere constant is flattening exactly the curvature the PhD is about.
- **Clay and white-model mode** (one day). `scene.overrideMaterial` with an exemption list. Half your figures argue geometry, not limestone, and this matters structurally because the skin also decides which of the seven analysis classes the run uses, so comparing four cutting patterns with four skins confounds the comparison.
- **Shots and a server-side queue** (five days). A shot is a sparse diff over the scene document plus frame range, resolution and channels; the queue is your existing deterministic frame loop driven from a list. Do not fight requestAnimationFrame throttling in a background tab -- run it through headless Chrome on the 4090 with a real GPU through ANGLE, never SwiftShader.

---

## 3. NEW MENUS

**One new panel section: Output.** It becomes the seventh tab. It holds Render still (the resolution ladder, samples 1 to 64, format, the channel tick boxes, the stamp toggle with an editable token string, the output folder through the existing native dialog, a Render button and a Region re-render), and it takes the whole Record block out of Animation, output folder included, so "Record 1080p" becomes "Record" against the same resolution ladder. Queue progress sits at its foot. The reason for a new tab rather than a Camera block is that Camera is already your busiest section and a lens control is not an output control -- and the still and the video are the same job document, so they belong together rather than two tabs apart.

**One new drawer: Shots.** It sits in the footer rail beside Scenes. Each tile is a sparse override on the live scene plus a camera, a frame range and its output settings, with variant chips along the bottom of the tile and a re-take pip in the corner. Tick several, press Render all. Keep the Scenes drawer exactly as it is: heavy, full restore, `loadStudy` included, correct for "this is a different project". A shot is the light thing that applies with no reload, which is what makes a four-up comparison plate provably the same camera. Attach variants to the shot rather than making them a global mode, which is the one design decision Twinmotion got right and everybody copies wrongly.

**Camera gains two blocks.** Projection, above FOV, holding the perspective/orthographic switch, the six named views, view width in metres and the scale presets. Image, replacing Brightness and Contrast, holding Exposure in EV, White balance, Tint, Contrast, Saturation, Highlight, Shadow, the LUT chooser and intensity, and Vignette.

**Scene gains three blocks.** Site, above the sun compass, holding latitude, longitude, saved site presets, date and the North offset dial. Section, holding Off / Plane / Box, axis, offset, cut fill colour and a "cut the machine too" toggle. Render quality, holding GTAO radius and intensity, shadow cascade count, split lambda and far distance, the soffit bounce toggle with a Rebake button, and Wind strength and direction.

**Skin gains a Render mode segmented control** at the very top, above the library picker: Rendered / Clay / White model. It sits above rather than inside the picker because it overrides the skin rather than being one of them, and because the skin choice carries the density and the structural class with it.

**Analysis gains a Selected piece block**, appearing in the Overview tab when a voussoir is clicked, printing piece index, course number and MPa -- and, where no member forces shipped, saying so in exactly the register your disabled-lens tooltips already use.

**The Props drawer gains a Measure group** beside the model chips: Dimension, Scale bar, Label, Callout. Placed items become ordinary prop records, so the gumball, Layers, undo and the scene round-trip all work on them, exactly as scattered items already do. Use troika-three-text and not CSS2DRenderer, because DOM labels vanish silently from a WebGL readback and your recorder and still export would drop every annotation without telling you.

Nothing else moves. Record and its output folder leave Animation; Brightness and Contrast leave Camera. That is the whole migration.

---

## 4. WHAT NOT TO BUILD

**Weather theatre.** Volumetric clouds are three to four weeks of raymarched Worley noise for the part of the frame a thesis plate crops out. Rain and snow particles read as sensor noise in a still. Puddles are the worst of the family, because a puddle only convinces when it reflects what stands above it, and with nothing but the environment probe yours will mirror the sky rather than the vault, which reads worse than dry stone. Keep two things from this entire branch: a Wet dial in Skin (albedo down, roughness towards 0.05 through `onBeforeCompile`, thirty lines) because wet limestone reveals double curvature through highlight roll-off in a way dry matte stone never does; and, if a take needs to look alive, a scrolling coverage texture modulating the sun's intensity and shadow, which buys drifting cloud shadow in two days with no volumetrics at all. Reject the season slider outright -- without autumn and bare-branch variants in the manifest it can only shift foliage hue, which reads as an Instagram filter and undermines an otherwise careful image.

**The second renderer.** In-browser path tracing works and the 4090 is ample, and it is still wrong for you, because it is a renderer with its own material model and none of your visual language crosses it: not the ribbon outline with its width uniform, not the stress and deflection heatmaps painted as vertex attributes, not the sky shader, not the additive halo sprites, not the depth-test-off thrust arrows. You would re-author the whole studio against a BVH for one plate. Export glTF and path-trace in Blender Cycles on the same machine for a tenth of the effort. Denoising leaves with it -- there is no noise in a rasteriser to remove. Real-time GI of any Lumen or SSGI shape goes too: your vault is static and re-cuts on a settle timer, which is exactly the case that wants a baked answer.

**The WebGPU migration, for now.** It genuinely unlocks SSGI, god ray nodes, velocity-buffer motion blur and near-free AOVs. It also deletes the EffectComposer, RenderPass and ShaderPass stack and forces every custom shader you own to be rewritten in TSL. One developer, no JavaScript test harness, and a month in which every image is broken in order to obtain things you have not yet needed. Revisit only if raymarched volumetrics becomes a genuine must-have.

**Optics cosplay.** Lens flare, lens dirt, chromatic aberration, barrel distortion, film grain and motion blur all model a camera that does not exist, in order to hint that the image is a photograph. A viva panel reads that as decoration on a claim about equilibrium. Motion blur is worse than pointless here: a falling voussoir rendered crisp is not a defect in a research animation, because blur smears the one thing the frame exists to show, which is where the piece is at that instant relative to the course below it. Vignette is harmless and is five lines inside the grade shader you are rebuilding anyway.

**Bloom is the one exception, and only conditionally.** Judge 1 rejected the family with a caveat and Judge 2 ranked a retry at 77. The ruling: retry it as a half day, after the grade moves into linear, and only when a night plate actually appears on the storyboard. You withdrew it as unproven and I think the diagnosis was wrong rather than the decision -- thresholded after the tone map it smears already-clipped whites into grey mush, and thresholded on the linear buffer above 1.0 with a soft knee and strength under 0.4 it behaves. Check the emitters actually exceed the threshold, because a 3000-lumen fixture inside a bright HDRI may not.

**The site that is not there.** Terrain sculpting with blended materials is three weeks minimum, and the six-material blend needs eighteen samplers against WebGL2's guaranteed sixteen, so it becomes a DataArrayTexture splat rewrite of the ground material for a feature that changes no argument. A vault on a plinth is the honest presentation of a structural claim and it is how the canon presents them. If a real site ever matters, import the survey as a .3dm mesh. Screen-space and planar reflections go with it. So do animated characters and vehicle path systems: the code is easy and the assets are the blocker, a bad 3D person destroys a good render faster than any lighting error, and what you actually need is scale reference, which is two carefully chosen static figures placed with the carry-to-place interaction you already have.

**Instanced scatter.** Judge 2 ranked this at 71; Judge 1 did not rank it at all and noted that wind needs no instancing first. Judge 1 wins. It is two weeks of refactoring that breaks the identity that makes your scattered items ordinary prop records -- which is precisely why the gumball, Layers, undo and the scene round-trip work on them today -- in order to lift a cap you are not hitting on a vault on a plinth. Take the wind now instead: half a day of vertex displacement weighted by height above the instance origin, driven from the recorder's frame index and not `performance.now()`, exactly as the day cycle already is, or a re-render will not match the take it replaces.

**Lights, split ruling.** Judge 1 rejected the whole IES, barn door and area-light family; Judge 2 ranked a light lister with spots and IES at 73. Take the light lister with solo -- one day, pure interface over records you already keep, and lighting a night shot is a sequence of solos, so without it you will end with everything at maximum, which is what every over-lit render has in common. Take one shadow-casting spot per fixture with a cookie texture, which is a better 2m strip than a point light at its middle pretending. Reject IES, because a measured photometric distribution is a claim about a specified luminaire and you are not specifying luminaires. Reject RectAreaLight, because its shading is an analytic integral over an unshadowed rectangle and cannot cast a shadow in WebGL at all, so it commits you to maintaining a cheating point light beside every emitter forever.

**Specifications with cheap substitutes.** Real Cryptomatte is a hashed, coverage-weighted, ranked multi-layer EXR standard; an integer object-ID pass plus a JSON legend gives ninety-five per cent of the use at five per cent of the work, and it is the same buffer that gives you picking. OpenColorIO has no browser build worth shipping, so bake AgX and ACES to .cube, load them through LUTCubeLoader, and tag the exported file's ICC profile server-side with Pillow, because a canvas readback will never carry a profile however you ask -- and be plain that the remaining ten per cent is unavailable here at any price. Parallax occlusion mapping and tessellated displacement belong at cut time on the server for render jobs only, not in a viewport shader that must then survive tint, variation and grain matching.

**An illuminance lens in lux.** Direct sun plus sky is computable per fragment and defensible; indirect is not available without global illumination, so any unqualified lux or daylight-factor figure will be broken by a building-physics examiner in one question. The tooltip discipline that refuses to print a scale you cannot justify is the best thing in the studio. Do not spend a fortnight building the one lens that would violate it.

**Multi-material and per-face painting on the vault.** This is the strongest no on the list and it deserves its reason stated fully. One skin dressing every voussoir is not a limitation, it is a property of the model: the skin supplies the density behind the live weight readout in kN/m2 and it decides which of the seven structural classes the analysis runs as. A per-face override would silently break the correspondence between what is drawn and what was solved, which is the correspondence the whole studio is built to protect. If one course must be differently finished in a figure, recolour it through the material-ID pass in Affinity, which for a figure set revised every time the analysis changes is the better workflow anyway.

---

## 5. THE UNREAL SHOPPING LIST

**Read this first.** Every pack below must be added to the **UE 5.4** project at A:\unreal engine\UE_5.4, project Trees_Downloaded, and not to the 5.7 project. This is not a preference. The 5.7 Megaplant packs are Nanite-assembly skeletal meshes with empty classic sections, and **both** glTF export paths -- direct asset export and spawned-actor export -- crash the engine outright, even with r.Nanite.AllowAssemblies=1. They cannot be extracted at all, by any route, at any effort. The unlock is that Fab serves engine-appropriate formats: add the identical pack to the 5.4 project and it arrives as classic static meshes. The European Beech pack proved this, with all seventeen assets exported and ingested cleanly.

Two mechanical reminders while you are in there. Launch the commandlet from PowerShell, never Git Bash, because Bash mangles any env value starting "/Game/..." into a Program Files path. And `GLTFExportOptions.default_level_of_detail` is ignored on direct asset export, so call `EditorStaticMeshLibrary.set_lod_from_static_mesh(mesh, 0, mesh, 1, True)` in memory and never save the asset. Never call the 5.7 StaticMeshEditorSubsystem LOD probes on a Nanite mesh.

In priority order, grass first, because the scatter cap is not your problem -- the species list is.

1. **temperate Vegetation: Optimized Grass Library** (free). Twelve grass types in 110 clusters. This is the one to fetch tonight. Clusters rather than single blades is exactly right for your scatter, because each placement carries its own internal variation and you reach a convincing field at a few hundred items instead of six thousand.
2. **Megascans - Meadow Pack** (Quixel, on Fab). Clovers, grass and weeds from real scan data. This is what stops a lawn reading as a lawn and starts it reading as ground.
3. **temperate Vegetation: Meadow Flowers** (free). Twenty flower species in 96 clusters. A handful of these scattered at low weight through items 1 and 2 is the difference between grass and a meadow.
4. **Megascans - Rocky Grassland** (Quixel, on Fab). Mossy rock with grass, for the plinth edge and anywhere the ground has to look like it was excavated rather than mown.
5. **Megaplants: European Hornbeam** (27 assets: 10 forest trees, 4 field trees, 8 saplings, 5 seedlings). Added to the **5.4** project. A field tree at the edge of frame is the second-best scale reference you can put in an image.
6. **Twinmotion Posed Humans** -- the Casual set (paid, around ten to forty pounds). Buy one set, extract two figures, and stop. A human figure is the only unambiguous scale reference in an image of a curved surface with no windows, no doors and no floor plates, and without one a reader cannot tell whether your span is three metres or thirteen. Static and posed, placed with carry-to-place. No walk cycles.
7. **Twinmotion Construction Vehicles Pack 1** (free, 22 models). For the build narrative. A delivery lorry and a telehandler parked at the edge of a formwork-free site is an argument about buildability that costs you nothing.
8. **temperate Vegetation: Foliage Collection** (free, 277 clusters). Only if items 1 and 3 come up short. It overlaps them heavily and it is a large ingest.
9. **Twinmotion Materials Pack** (free, about 8GB). Take the source textures for ground and plinth surfaces, not the UE materials, which are built around parallax occlusion and triplanar projection that will not cross into your ground shader. Low priority, and only when you actually need a surface the curated ground library lacks.

Sources: [temperate Vegetation: optimized Grass Library](https://www.unrealengine.com/marketplace/en-US/item/b6925a7479114f18b3f9793f10d84ddf), [temperate Vegetation: Meadow Flowers](https://www.fab.com/listings/e648b1bd-11f6-4895-bd43-15e399c80297), [temperate Vegetation: Foliage Collection](https://www.fab.com/listings/6a5ae8db-d80f-4b23-b276-87da390cfe56), [Megascans - Meadow Pack](https://www.unrealengine.com/marketplace/en-US/product/megascans-meadow-pack), [Megascans - Rocky Grassland](https://www.unrealengine.com/marketplace/en-US/product/megascans-rocky-grassland), [Megaplants: European Hornbeam](https://www.fab.com/listings/43679e75-6ed0-4b03-9288-9e2bc49376d2), [Megaplants: European Beech](https://www.fab.com/listings/cefe5722-9c31-4aa2-9ee2-e5426610d5e6), [Twinmotion on Fab](https://www.fab.com/sellers/Twinmotion), [Twinmotion Construction Vehicles Pack 1](https://www.unrealengine.com/marketplace/en-US/product/twinmotion-construction-vehicles), [Twinmotion Materials Pack](https://www.fab.com/listings/a04e4f4e-f659-450a-8ec8-1d9cb234fe0a), [Fab free content](https://www.unrealengine.com/fabfreecontent).

---

## 6. DECALS

**The recommendation: yes, and only on the ground, the plinth, the permanent works and the props. Never on the voussoirs.**

The reason for the exclusion is the one given in section 4, and it is worth repeating because it is the sentence that decides the whole feature. The skin supplies the density behind the live weight readout and selects which of the seven structural classes the analysis runs as, so anything that lets one voussoir be dressed differently from its neighbours quietly severs the correspondence between the image and the solution. If you want a stain on the extrados in a figure, take it from the material-ID pass in Affinity. Everything below the springing is fair game, because nothing down there is load-bearing on the argument.

**The three.js approach.** `DecalGeometry`, from three/examples/jsm/geometries/DecalGeometry.js. You give it a target mesh, a world position, an orientation and a size box, and it clips the target's triangles against that box and hands back a new BufferGeometry with its own UVs, correctly wrapped over whatever it landed on. Dress it with a MeshStandardMaterial carrying map, normalMap and either an alphaMap or a transparent PNG. Three settings do all the work: `transparent: true`, `depthWrite: false`, and `polygonOffset: true` with `polygonOffsetFactor: -4` to win the z-fight against the surface underneath. On the ground disc the projection is trivial and costs nothing, because the target is one flat mesh; on a prop or on the machine's rail it works against the geometry you already have loaded.

**Where it lives.** The Props drawer gains a Decals category chip beside the model chips. Placement reuses carry-to-place exactly: choose a decal, it rides the cursor and projects live onto whatever is beneath it so you can see it land, click to put it down, Escape to cancel, and the shelf deliberately stays open so you can lay six in a row. Each placed decal becomes an ordinary prop record, so the gumball moves it and turns it -- rotation about the projection axis is the one that matters, and R for a 15-degree nudge is already the right gesture -- Layers holds it, undo removes it, and the scene round-trip restores it. Add a Randomise pip that re-rolls rotation and scale, because a decal placed twice at the same angle reads as a sticker instantly.

**Where the assets come from.** ambientCG's Decals category, at ambientcg.com/list?category=Decals, everything CC0, PNG with alpha, and no licence question to answer in a thesis appendix. Poly Haven for anything else CC0. After that, make your own: you have a 4090 and a ComfyUI stack sitting idle overnight, and a seamless alpha-cut chalk line or a lime stain generated to your own site is more truthful than any stock puddle, and takes a minute.

**What to actually place.** The robot's rail footprint and its anchor bolt pattern on the plinth. Chalk setting-out lines at the springing, which is the single most convincing detail available to you because it is the one mark a formwork-free process genuinely leaves. Lime staining running down from a weep. Tyre tracks and mud on the delivery route. A painted scale rule along the plinth edge, which does the scale bar's job inside the picture rather than over it. Resist the temptation to place dark contact patches under props as a stand-in for occlusion -- GTAO lands two weeks from now and then you will have to go and delete them all.

A decal is the cheapest way to make a construction site look used, and a site that looks used is the quiet argument that the process is real.",
