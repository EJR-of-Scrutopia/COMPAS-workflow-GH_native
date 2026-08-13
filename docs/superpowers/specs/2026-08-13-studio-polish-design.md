# Bench Studio polish wave

Date: 2026-08-13. Agreed with Param against his first working session with
the cutting engine (the punch list of 2026-08-13, plus the sprayed
concrete screenshot). This wave has no new analysis content: it makes the
studio behave like a finished instrument. The environment engine (HDRI,
weather, ground types, placeable props) is deliberately NOT here; it is
the next wave, and by Param's decision of 2026-08-13 it jumps the queue
ahead of wave 6b's pattern library.

## The problems, as observed

1. Choosing a pattern does not survive changing the material: the
   material change handler force-writes the material's default pattern,
   so timber plus monolithic bands silently becomes timber plus bonded
   courses. The same reload resets the timeline to zero, which reads as
   "it stops".
2. Stepping a slider fires one full server cut per committed step, 10 to
   20 seconds each at small sizes, with no guard against overlapping
   requests. The UI stalls and nothing says why.
3. Nothing on screen indicates a cut is in flight, so every slow buffer
   looks like a hang.
4. The drop animation's total length is piece count times seconds per
   piece: 233 pieces at the fastest setting is 23 seconds of build, and a
   small tile cut runs to minutes. The drop speed slider cannot fix a
   model that is linear in the count.
5. Changing material rebuilds the world: timeline position, play state
   and camera are all thrown away, so comparing materials at the finished
   vault is impossible without re-running the whole animation.
6. The pieces light up banded and faceted. Two causes, measured by
   reading the code: the geometry is unindexed triangle soup, so
   computeVertexNormals gives one flat normal per facet; and the cap
   subdivision stops at 0.30 m edges. (Quads are not the answer: the
   engine already triangulates, and the GPU would triangulate quads
   anyway. The fix is normals plus density, not element shape.)
7. The thrust network casts a grid shadow through the completed shell.
   The wires sit hidden inside the closed vault, but shadow maps ignore
   both occlusion by the shell and material opacity, so the ground shows
   the shadow of an invisible thing. The formwork ghost itself never
   casts (castShadow was never set on it); the grid the screenshot shows
   is the wires and nodes.
8. The falsework toggle exists but is labelled "Falsework ghost" and
   buried in a section called "FEA layers", where Param did not find it.
   There is no toggle at all for the finished shell.
9. Sprayed concrete renders cream (0xd8d2c4), not concrete.
10. A stray "s" (the Inflation slider's seconds unit) wraps onto its own
    line in the panel.
11. The Stop button duplicates what Pause and Restart already cover.
12. The panel's sections group by how the code grew, not by how the
    studio is used.

## Decisions

### D1. Playback timing: constant total build, per piece stagger derived

The per piece stagger stops being a user setting and is derived from the
count, so the build always takes the same time whatever the cut:

- `BUILD_TARGET_SECONDS = 35`. `placementStep()` returns
  `BUILD_TARGET_SECONDS / max(1, placementCount())` for every material.
  The sprayed half-window special case is deleted: with the stagger
  derived, castings overlap in flight for every material and the sprayed
  build-up reading comes free.
- `DROP_SECONDS = 0.8`, a constant: how long one casting falls (or one
  sprayed patch grows). The `drop-speed` slider and `timeline.dropSeconds`
  are removed; every reader of the old value reads the constant.
- `timelineDuration()` becomes
  `inflateSeconds + count * placementStep() + DROP_SECONDS + STRIKE_SECONDS`.
- All three clocks (applySceneAtTime, timelineDuration, currentStageIndex)
  already read placementStep() from one place; they must keep doing so.

### D2. Timeline speed replaces the drop speed slider

A playback rate multiplier, `state.timeline.speed`, range 0.25 to 4.0,
step 0.05, default 1.0, slider id `timeline-speed`, label "Timeline
speed", value shown as "1.00x".

- Interactive play: `frame()` advances by `delta * speed`.
- Record mode: time stays a pure function of frame number with the rate
  folded in: `total = Math.ceil(timelineDuration() / speed * fps)` frames,
  frame k applies `applyTimeline(k * speed / fps)`. A 2x recording is
  half the frames of the same animation, deterministically.
- applyTimeline and applySceneAtTime stay pure functions of t. The rate
  lives only in how fast callers advance t, never inside the functions.
- Orbit speed and orbit distance remain their own controls. Timeline
  speed scales everything computed from t, orbit rotation included; that
  is the accepted meaning of "speed the whole animation up".

### D3. Pattern choice is sticky

- `state.patternChosen` (boolean, starts false). The pattern select's own
  change handler sets it true. Nothing ever resets it short of a page
  reload.
- `updatePatternForMaterial` writes the material's honesty note always,
  but only applies the material's default pattern when `patternChosen` is
  false. With it true, the user's pattern rides through every material
  change.
- Boot behaviour is unchanged (default applied, patternChosen false).
- applyCut's adoption of the loaded bundle's pattern into the select does
  not touch patternChosen: it reflects what loaded, it is not a choice.

### D4. Slider commits settle, requests cannot race, and no-ops are skipped

- Size and thickness commits go through one `scheduleReload()`: a timer
  that fires `loadStudy` 1.5 seconds after the last committed movement,
  resetting on every new one. Stepping a slider five times costs one cut.
- Every bundle request carries a token: `state.loadSequence` increments
  as the request is issued and the response only lands if its token is
  still current. Stale responses are dropped silently. Material, pattern
  and study changes go through the same token (no debounce needed for
  selects; they commit immediately).
- A commit whose requested (material, pattern, size, thickness) equals
  what the loaded bundle already answers (bundle.material,
  bundle.pattern, bundle.size, provenance.thickness) issues no request.

### D5. The cut-in-flight indicator

A status line, `div id="cut-status"`, in the Study section beside the run
status. While a bundle fetch is in flight it reads, for example,
"cutting brick, bonded courses, 900 mm pieces at 200 mm...". It clears
when the bundle lands or the response is dropped as stale. Failures keep
going to the banner as today.

### D6. Material swaps happen in place

When a reload's export name equals the loaded bundle's export, the studio
preserves the viewing state instead of resetting it:

- Capture before rebuild: `f = t / timelineDuration()` and the playing
  flag. After the new bundle builds, apply `t' = f * newDuration` through
  `applySceneAtTime` (never applyTimeline: the camera must not move),
  restore the playing flag and set the scrubber to match.
- `controls.target` and the camera are left untouched on a same-export
  reload. A study switch keeps today's full reset, camera re-aim
  included.
- This covers material, pattern, size and thickness reloads alike: same
  export means preserve, different export means reset. When the new cut
  has a different piece count the fraction is what carries over, which is
  the honest mapping between two different drop sequences.

### D7. Piece shading: crease-angle smooth normals

buildPieceMeshes keeps its unindexed layout (the weights, surface and
per-corner attributes depend on it) and gains a computed `normal`
attribute in place of computeVertexNormals:

- Group triangle corners by exact position key (the engine guarantees
  shared points are bit-identical, so exact keys are safe).
- Each corner's normal is the average of the facet normals at its
  position whose dot product with the corner's own facet normal is at
  least `cos(40 degrees)`. Gently curved caps smooth; the roughly
  90 degree cap-to-side edges stay hard, so silhouettes keep their
  corners.
- Implemented as `creaseNormals(positions)` in fields.js, returning a
  Float32Array, unit length. recolourSegments' deflection path, which
  today calls computeVertexNormals after displacing positions, calls the
  same helper on the displaced positions.

### D8. Cap density: finer target, measured before pinned

- Candidate values: `CAP_EDGE_TARGET` 0.30 to 0.15 and `MAX_ROUNDS` 3 to
  4 in cutting.py. `CHORD_TARGET` stays 0.005.
- Budget, which the implementation must measure on Trial 2 at the 0.9 m
  default and at 0.3 m before the values are pinned: server cut time at
  most 2x today's, bundle JSON size at most 3x today's. If 0.15/4 breaks
  the budget, back off to the finest values that hold it and record the
  numbers.
- BENCH.md's measured cut section is re-measured after the change
  (chord deviation, rounds, limits, sizes).
- While measuring, check the procedural texture scale on pieces: some of
  the screenshot banding may be noise-map moire at glancing angles.
  boxUVs' scale and the 6x6 repeat are the suspects; adjust only if the
  A/B screenshot shows the texture is contributing, and record which it
  was.

### D9. Shadow policy: analysis overlays cast no shadows

- Wires and nodes: `castShadow = false`, always. They are a diagram of
  the thrust network, not scene objects, and their shadow through the
  closed shell is the defect on Param's screenshot. This also removes
  the grid from the inflation phase; accepted.
- The falsework ghost keeps castShadow false (already true today, now
  stated as policy rather than accident).
- Castings and columns keep casting; the ground keeps receiving.

### D10. View toggles: finished shell and formwork, front and centre

- New layer `shell`, label "Finished shell", default on, first in the
  layer list. applySceneAtTime gates every casting's visibility on it
  (`state.layers.shell` false means every segment invisible, whatever the
  timeline says). recolourSegments and the pulse need no change: they
  already skip invisible segments or write state that is invisible
  anyway.
- The `falsework` layer's label becomes "Formwork", second in the list.
  The internal key stays `falsework` (state.layers, setLayer and
  applySceneAtTime keep their names; only the label a user reads
  changes).

### D11. Concrete regrade

More grey, less yellow. Exact values, verified against an A/B screenshot
before the wave closes:

- `concrete` (C30/37): 0x9a958a to 0x939590.
- `concrete-sprayed`: 0xd8d2c4 to 0xcbcbc6.
- `concrete-c50` stays 0x5d646c (already a cool grey).
- Timber, brick, tile, stone, steel untouched.

### D12. Small fixes

- The Inflation slider gets a value span like the mm sliders: "3.0 s" on
  the label line, no bare unit after the input. The stray "s" disappears.
- The Stop button is removed from index.html and studio.js. Pause covers
  halting; Restart covers rewind-and-play; the scrubber covers rewind
  without play.

### D13. The panel regroup

Six sections, in order, each a collapsible details/summary block:

```
STUDY      study select, material, pattern + note, piece size,
           thickness, joint gap, crown taper, run button,
           run status, cut status               (open by default)
VIEW       Finished shell, Formwork, Thrust wires and nodes,
           Stress heatmap, Deflection heatmap, Load vectors,
           Reaction vectors, Text overlays, Integrity pulse,
           Wire forces; then a nested collapsed "Styling" block:
           stress surface, deflection exaggeration, node size,
           wire size; Data button                (open by default)
ANIMATION  Play/Pause, Restart, Timeline scrubber,
           Timeline speed, Inflation, Orbit speed,
           Orbit distance                        (open by default)
SCENE      Sun azimuth, Sun elevation, Background
           (deliberately thin: the environment engine wave
           grows here)                           (collapsed)
IMPORT     export pair, columns                  (collapsed)
RECORD     record button, record status          (collapsed)
```

- Native `<details open>` / `<summary>` elements, summaries styled like
  the current h2 headers in studio.css. No state persistence across
  reloads: the defaults above are the state, and localStorage is scope
  this wave does not need.
- The layer-toggle builder keeps generating the checkboxes; only the
  section that holds them and the order of LAYERS change (shell first,
  falsework second, then the rest in today's order).

## Files

- `bench/studio/static/index.html`: section regroup, details/summary,
  Stop button out, Inflation value span, timeline-speed slider in place
  of drop-speed, cut-status div.
- `bench/studio/static/studio.js`: D1 through D7, D9, D10, D12, D13
  wiring.
- `bench/studio/static/fields.js`: `creaseNormals`.
- `bench/studio/static/studio.css`: summary styling, cut-status styling.
- `bench/studio/cutting.py`: D8 density values, once measured.
- `tests/studio/`: updated pins for cutting.py values; guard and offline
  tests unchanged and must stay green.
- `docs/BENCH.md`: re-measured cut section, renamed controls.

## Error handling

- A stale response is dropped without touching the scene or the
  controls; only the newest request may land.
- The settle timer never fires a request for a study select with no
  value (the empty-studies boot case), same guard the handlers carry
  today.
- creaseNormals on a degenerate facet (zero-area triangle) skips the
  facet's contribution rather than normalising a zero vector; a corner
  whose every contribution was degenerate falls back to the facet
  normal of its own triangle, or +z if that is also degenerate.

## Testing

- The Python suites run from the COMPAS-Workflow-bench worktree and must
  stay green; the studio guard (no solver imports outside solve stages)
  and offline (no http references in static files) tests bind every
  static file this wave touches.
- cutting.py's density change updates whichever tests pin
  CAP_EDGE_TARGET, MAX_ROUNDS or measured outputs, with the new measured
  numbers, never loosened tolerances.
- The viewer has no JS test harness, by standing convention. The plan
  carries a manual verification checklist instead: pattern survives a
  material round-trip; five rapid slider steps cost one cut and show the
  indicator; a material swap at the finished vault keeps camera and
  timeline; the completed shell's ground shadow carries no grid; the
  sprayed vault reads grey and smooth; every section collapses and
  reopens; record mode at 2x produces half the frames.

## Out of scope

- The environment engine wave: HDRI install folder, browser upload and
  picker, sky and weather presets, ground material presets (dark studio,
  concrete slab, patio pavers, tiles), placeable props. Next wave, ahead
  of 6b by Param's decision of 2026-08-13.
- Robots placing pieces (later wave; prior art in bench demo 05's
  analytical IK).
- Wave 6b patterns, wave 6c Armadillo dual, thrust line in section,
  mesh convergence, moulds, the concrete versus timber A/B.
- Any change to the cut itself, the tessellation contract, staging or
  solvers.
