# Bench Studio repairs and reorg wave

Date: 2026-08-15, agreed with Param against his first session with the
merged environment engine (the blown-white sky screenshot). Wave A of
two: repairs and reorganisation now; clouds, grass, buildings and the
prop picker are Wave B, specced separately after this lands.

## The reports, as received

1. The sky is over-exposed: everything washes to white with no
   contrast or brightness control. The sunset preset is liked as is.
2. The stress map "goes white with no colours".
3. The formwork ghost is still visible and Param would rather not see
   it at all; the Formwork "Always" option shows nothing.
4. The View toggles "make no difference"; he wants modes instead:
   framework only, shell only, timeline, and probably a both.
5. Mesh edges are still not clean, particularly at the rim.
6. Re-uploading a different HDRI from the browser fails with an error
   and never replaces the loaded one. The export import must be shown
   not to share that defect.
7. UI reorg: Styling becomes Analysis and gathers everything
   analysis-related; Import moves to the top; Record's button joins
   Animation and its tab dies.
8. A View-tab run-through: fix what is broken, and reconsider what to
   keep at all.

## Decisions

### R1. Diagnose before fixing, with a defect table

- The wave's first task reproduces every report against a live server
  (bench/studio/serve.py in the worktree) before any fix lands:
  stress heatmap under each environment mode, every View control, the
  three formwork states at rest and mid-build, HDRI upload then a
  second different upload, export pair re-import over an existing
  export.
- Output is a defect table written to the wave's workspace (the
  git-ignored SDD directory) and echoed into the ledger: report,
  reproduction result, root cause found in code, fix task it maps to.
  For each View feature the table adds a keep / cut recommendation;
  Param rules on cuts before anything is removed.
- Fixes in later tasks cite the table's root cause, not the symptom.

### R2. Exposure: retuned presets plus Brightness and Contrast

- The five WEATHER preset exposure values are retuned downward against
  the sky so a mid-elevation sun no longer washes the frame; Golden
  hour keeps its current look (explicitly liked). Retuning is by
  stated rule: at elevation 40, Clear must render the ground plane
  unclipped (no channel at 255) with the vault's material tones
  distinguishable; the check is a captured frame inspected during R1's
  rig, not a formula.
- A Brightness slider (0.3 to 2.0, default 1.0) scales
  toneMappingExposure as a multiplier on the active mode or preset
  exposure, so switching presets keeps relative brightness.
- A Contrast slider (-0.5 to 0.5, default 0) requires a post pass:
  vendor three's postprocessing addons (EffectComposer, RenderPass,
  ShaderPass, OutputPass, and BrightnessContrastShader) at the pinned
  0.185.0. The composer's render target uses samples = 4 so the
  existing antialiasing survives. The render loop and recordAnimation
  both draw through the composer; recording needs no special handling
  because it reads the same canvas.
- Both sliders live in Scene, visible in every environment mode, and
  are pure view state: no timeline interaction, no clock reads.
- No auto-exposure. The retuned presets are the sensible default;
  sliders are the manual override. Auto would fight both.

### R3. Heatmaps are data, never scenography

- recolourSegments' heatmap material becomes unlit: vertex colours on
  a material with toneMapped false and no lighting response
  (MeshBasicMaterial with vertexColors, DoubleSide), so stress and
  deflection read identically under Studio, noon sky, sunset or any
  HDRI, and are immune to exposure and contrast settings by
  construction.
- The wire-force colouring keeps its current material; wires are
  scenography and data at once and were not reported broken. If R1's
  table says otherwise, it joins the fix.
- The heatmap legend colours and value mapping are untouched.

### R4. View becomes a Show mode select; formwork defaults hidden

- A select labelled "Show", id `show-mode`, values `framework` |
  `shell` | `both` | `timeline` (default timeline), state in
  `state.showMode`.
  - framework: the inflated thrust net (wires and nodes) only, no
    shell, no castings, at the resting state.
  - shell: the finished shell only, at rest.
  - both: net plus finished shell, at rest.
  - timeline: exactly what the animation shows at the current time
    (today's behaviour).
- The shell and wires layer checkboxes are removed. applySceneAtTime
  keeps ownership: the non-timeline modes are defined as fixed points
  of the same scene function (rest state with the chosen objects), so
  purity in t is unchanged and the scrubber simply has no visible
  effect outside timeline mode until switched back.
- The Formwork select stays three-state but its DEFAULT becomes
  Hidden. The dead Always state is a defect for R1 to diagnose and
  this wave to fix: Always must show the resting ghost at 0.3 opacity
  regardless of build progress, in every Show mode except framework.
- Analysis overlays (heatmaps, vectors, forces, pulse, overlays) leave
  View for the Analysis section (R5) as toggles, unchanged in
  behaviour once R1 confirms or repairs each.

### R5. Panel reorg

- New section order in the side panel: Import, Study, Analysis, View,
  Animation, Scene.
- Import: the existing export-pair and columns upload controls,
  unchanged, now first.
- Study: study select, material, pattern, size, thickness, joint gap,
  taper, run button and status. (The run button is study-shaped, not
  analysis-shaped: it produces the study everything else reads.)
- Analysis (renamed from Styling, now a top-level section): stress and
  deflection heatmap toggles, load and reaction vector toggles, wire
  forces, integrity pulse, text overlays, stress surface select,
  deflection exaggeration, node and wire size sliders, Data button.
- View: the Show select, the Formwork select.
- Animation: play, restart, timeline scrubber, timeline speed,
  inflation, orbit speed and distance, and the Record 1080p button
  with its status line. The Record section dies.
- Scene: environment mode, weather, HDRI row, sun sliders, background
  tone, Brightness, Contrast, ground preset, props row.
- Open-by-default: Study, View, Animation. Others collapsed. The
  six-section static pin is rewritten to the new order and the
  same-summary style.

### R6. Uploads that replace, with errors on the banner

- R1 reproduces the HDRI second-upload failure and names the root
  cause. Whatever it is, the fix must make this true: uploading a
  different valid .hdr while one is loaded replaces the picker
  selection, the background and the lighting, and re-uploading the
  SAME filename overwrites it server-side and reloads it. Two prime
  suspects to check first: the 64 MB cap rejecting larger files with
  only the small status line showing, and disposing the previous
  texture while it is still bound as scene.background.
- HDRI list, fetch and upload failures surface through the studio's
  banner convention (fetchJson / showBanner) instead of bare fetch
  plus a status div; the status line keeps progress text only.
- The export-pair import path gets the same replace-while-loaded test:
  upload a pair, load it, upload a modified pair under the same name,
  and the studio must serve the new geometry (the cut memo is already
  cleared on re-upload; the test proves the whole path).
- Server-side, the Windows drive-relative filename gap noted at the
  environment wave's final review (a name like C:evil.hdr slips the
  guard) is closed with a resolve()-containment check on both hdri
  routes and the columns route it was copied from.

### R7. Mesh edges: diagnose the rim, fix shading here, gate density

- R1 captures rim close-ups under raking light at two sizes and
  compares against the known limits (the rim course follows the mesh
  boundary; corner-normal residual worst at the rim; 137 clamped cap
  points reaching 52 mm).
- If the artefact is shading (normals, z-fighting, seam lighting), it
  is fixed in this wave.
- If it is genuinely tessellation density, this wave does NOT change
  density constants: the finding goes to Param with the measured
  options from the D8 ladder (per-size rounds or a chord-driven
  budget) as a decision, because every density rung measured to date
  blew the payload budget.

## Out of scope

- Clouds, grass geometry, buildings, the prop picker dropdown with
  thumbnails (Wave B).
- Any solver, cut, pattern or contract change.
- Auto-exposure.
- New analysis features; Analysis is a reorg plus repairs only.

## Testing

- Static pins updated for: the Show select and its four modes; the
  formwork default Hidden; the panel section order and open states;
  the Analysis section's contents; Record's button inside Animation
  and the dead Record section; the Brightness and Contrast sliders and
  composer wiring (render through composer in frame() and
  recordAnimation); the unlit heatmap material; banner-routed HDRI
  errors; vendored postprocessing addon files.
- Server tests: resolve()-containment on hdri and columns routes
  (drive-relative names rejected); HDRI same-name re-upload
  overwrites; export re-upload serves new geometry end to end.
- The R1 defect table is the wave's evidence base; fixes without a
  table row naming their root cause do not land.
- Purity pins extended: show-mode changes recompute through
  applySceneAtTime only; Brightness and Contrast read no clock and no
  timeline.
- Suites run from the COMPAS-Workflow-bench worktree. No em dashes,
  no attribution, nothing pushed.
