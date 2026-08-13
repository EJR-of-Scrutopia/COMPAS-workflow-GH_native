# Bench Studio fix-up wave

Date: 2026-08-13, agreed with Param against his first session with the
merged polish wave (the two screenshots: load arrows hanging under the
shell, and the sprayed close-up with tonal steps and ripples). Five
decisions, then the environment engine wave opens.

## The problems, as observed

1. Load vectors hang underneath the shell. arrowField anchors the tail
   at the node and extends the shaft along the load direction, which for
   a downward load reads as suction pulling the vault down.
2. The Formwork checkbox does nothing at the finished vault: the strike
   has already faded the formwork to zero opacity and dropped it below
   ground, and a checkbox can only hide, never resurrect. A two-state
   control cannot express what Param wants; he asked for three states in
   as many words: animation, always, hidden.
3. The sprayed close-up shows two artefacts. Tonal steps at every course
   joint: normals are welded within each piece but neighbouring pieces
   compute theirs independently, so lighting steps at the joints even
   though sprayed concrete is one continuous surface with a zero joint
   gap and bit-identical shared boundary points. And fine wavy ripples
   at grazing angles: the procedural textures render at anisotropy 1,
   which is textbook texture moire.
4. Changing material (or the cut) shows no obvious sign that a
   computation is running; the small status line was not enough. And the
   wait itself is longer than it needs to be: the server re-runs the
   whole cut for every material although the tessellation and the pieces
   depend only on pattern and size, never on material or thickness.

## Decisions

### F1. Load arrows arrive from above, tip at the surface

- arrowField gains an anchor argument: "tail" (today's behaviour, the
  shaft leaves the node along the vector) or "tip" (the shaft stands
  before the node so the head lands at the node, the point of
  application).
- Loads render tip-anchored; reactions stay tail-anchored, they
  genuinely emerge from the supports.
- The arrow still draws exactly along the shipped vector; only the
  anchor changes. The existing pin that forbids a direction multiplier
  stays satisfied.

### F2. Formwork becomes a three-state control

- The falsework entry leaves the layer checkbox list. A select labelled
  "Formwork" joins the View section, id `formwork-mode`, options
  Animation (default), Always, Hidden; state lives in
  `state.formworkMode` ("animation" | "always" | "hidden").
- Animation: today's behaviour exactly. The ghost fades in with the
  inflation, stands through the build, strikes away at the end.
- Always: pinned for inspection. Visible at the resting position with
  the full ghost opacity (0.3) regardless of inflation or strike, so it
  can be examined at the finished vault.
- Hidden: never drawn, build phase included. This is the "always remove
  the ghost shell" ask.
- applySceneAtTime keeps ownership of the formwork's visible, opacity
  and position; it reads state.formworkMode the same way it already
  reads state.layers. Purity in t is unchanged (no clock reads).
- state.layers.falsework and setLayer's falsework branch are removed;
  the change handler for the select recomputes the scene through
  applySceneAtTime, never applyTimeline, so it cannot move the camera.

### F3. Monolithic surfaces shade as one surface, and textures stop shimmering

- In buildPieceMeshes, when the material is sprayed (joint gap forced to
  zero, shrink factor exactly 1, shared boundary points therefore
  bit-identical across pieces), the crease normals are computed over the
  CONCATENATION of every piece's positions in one call and sliced back
  per piece, so course joints stop stepping in the light. Jointed
  materials keep per-piece normals: their pieces are genuinely separate
  and the step is honest.
- recolourSegments' displaced-normals path stays per piece. Under a
  deflection heatmap the colouring dominates and the cross-piece seam
  there is accepted; the spec says so rather than hiding it.
- noiseTexture and grainTexture set
  `texture.anisotropy = renderer.capabilities.getMaxAnisotropy()`,
  which is the standard fix for grazing-angle moire. No texture content
  changes.
- The faint hairlines in the close-up are re-checked by eye after these
  two land; no further change is specced for them yet.

### F4. A loading overlay while a cut is in flight

- A centred overlay, id `cut-overlay`, hidden by default, containing the
  existing `cut-status` line (which moves inside it) plus a small CSS
  spinner. Shown by loadStudy while a bundle fetch is in flight, hidden
  when the response lands or is dropped as stale, in the same token
  discipline the status line already follows. Failures keep going to the
  banner.
- The overlay dims nothing and blocks no clicks (pointer-events none):
  it is a signal, not a modal lock.

### F5. The server reuses the cut across material and thickness

- The expensive step of a bundle build is the tessellation plus
  segment_pieces, and its inputs are export geometry, pattern and size
  only. bundle.py gains a small in-process memo keyed by
  (export, pattern, size) holding the cut products, with a 4-entry LRU
  cap because a single small-size cut can run to tens of megabytes.
- A bundle request that misses the JSON cache but hits the memo reuses
  the cut and only assembles the material- and thickness-dependent rest,
  so switching material at any already-cut size stops re-cutting at all.
- Invalidation: the memo is cleared wherever the studio JSON cache is
  invalidated today (an export re-upload), so a stale cut can never
  outlive its export.
- The JSON cache on disk keeps its existing full key and behaviour; the
  memo sits in front of the cut step only. A pytest covers the reuse by
  counting cut calls across two materials at the same pattern and size.

## Out of scope

- The environment engine wave (HDRI, weather, ground presets, props):
  next, immediately after this.
- Any change to cap density (D8 stands as merged), patterns, staging,
  solvers, or the tessellation contract.
- Cross-piece welded normals for jointed materials or under deflection
  displacement.

## Testing

- Static pins in tests/studio/test_static.py updated where they name the
  falsework layer, and added for: the loads anchor, the formwork-mode
  select and its three states, the anisotropy lines, the sprayed
  concatenated-normals branch, and the overlay wiring.
- A server-side test pins the cut memo (two materials, one cut).
- Suites run from the COMPAS-Workflow-bench worktree; the offline and
  guard tests bind every touched static file. No em dashes, no
  attribution, nothing pushed.
