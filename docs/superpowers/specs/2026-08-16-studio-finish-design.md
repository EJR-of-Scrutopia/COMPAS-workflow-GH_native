# Bench Studio finish wave

Date: 2026-08-16, agreed with Param against his session with the merged
repairs wave. Seven decisions. His standing instruction recorded here:
after this wave the queue is FEATURES first (rim geometry fix + wave 6b
patterns, then Wave B richness, then 6c, then the ROS brainstorm);
polish items batch into feature waves from now on instead of earning
their own rounds.

## The asks, as received

1. Run staged analysis belongs in the Analysis tab.
2. A small terminal logger, bottom right of the viewport, white overlay
   text.
3. A seam at the crown: a black line with regularly spaced white dots
   along the ridge (screenshot), read by Param as a thickness or
   placement issue of the shell on the formwork.
4. Wire size and node size belong in the View tab.
5. The 200 MB HDRI cap rejects his real files (300 to 400 MB): remove
   the limit. And scale the HDRI to sit believably against the model.
6. Better sun controls: sun colour, and a west-to-east
   sunrise-to-sunset animation.
7. Error banners never disappear.
8. More material appearance range: extra presets and colour control,
   for presentation-grade rendering.

## Decisions

### S1. Panel moves

- The run button and its status line move from Study to the TOP of the
  Analysis section. (An earlier ruling called the run button
  study-shaped; Param overrode it, his call, and Analysis is where he
  looks for it.)
- Node size and wire size move from Analysis to View, under the Show
  select: they style the net that Show displays.
- Nothing else moves.

### S2. The terminal logger

- A fixed overlay, id `event-log`, bottom right of the viewport, in the
  text-overlay style: small white monospace text, no background box,
  pointer-events none.
- Shows the last 7 events, one line each, prefixed with a HH:MM:SS
  timestamp: study loads (with export name), cut started and cut landed
  (with elapsed seconds), uploads (name and outcome), analysis run
  started and finished, HDRI loads, and every banner message.
- One helper `logStudio(message)` appends, trims to 7, and stamps the
  time. Every existing status-write site calls it alongside its current
  behaviour; the banner helper calls it on every banner.
- The overlay fades to invisible after 8 quiet seconds (CSS transition
  driven by a timer that the next event resets) and reappears
  instantly on the next event. The fade timer is UI state, not scene
  state: no purity implications.

### S3. Banners that dismiss

- Info banners self-dismiss after 6 seconds, error banners after 12.
- Every banner gets a close X. Hovering the banner pauses the
  countdown; leaving resumes it.
- The logger (S2) records every banner, so dismissal loses nothing.

### S4. HDRI uncapped, ground-projected, rotatable

- The upload size cap is REMOVED: no HDRI_MAX_BYTES check. The
  Radiance magic-byte check and the filename guards stay. (Localhost,
  Param's own disk; the cap only ever rejected his real files.)
- Vendor three's GroundedSkybox addon (0.185). In HDRI mode a
  Projection select, id `hdri-projection`: Projected (default) |
  Infinite.
  - Projected: the HDRI stands on the ground plane as a dome. Sliders:
    Scale (dome radius, 10 to 300 m, default 60), Height (camera
    height in the image, 0.5 to 20 m, default 2), Rotation (0 to 360
    deg, default 0). The dome mesh replaces scene.background as the
    backdrop; scene.environment (lighting) keeps coming from the same
    equirect via PMREM as today, so lighting does not change with
    projection.
  - Infinite: today's behaviour, plus the same Rotation slider applied
    to backgroundRotation's spin about the vertical.
- The sun estimate keeps working in both projections (it reads the
  pixels, not the backdrop object). Rotation rotates the estimated sun
  with the image: the applied azimuth adds the rotation angle so
  shadows track the backdrop as it spins.
- The controls live in the hdri-row and show only in HDRI mode;
  Scale and Height show only when Projected.

### S5. Sun colour and the day cycle

- A sun colour input, id `sun-colour`, in Scene beside the sun sliders,
  live in every environment mode. Weather presets and the HDRI
  estimate write it (so it always shows the current truth); the user
  overrides it any time; overriding sets a flag that stops presets
  clobbering it until the next preset change (a preset change is an
  explicit "restyle everything" action and resets the override).
- The day cycle block in Scene: a Play/Pause button id
  `day-cycle-button`, a duration slider id `day-cycle-seconds` (10 to
  120 s, default 30), and a checkbox id `day-cycle-record` labelled
  "During recordings".
- Semantics: applyDayCycle(u) with u in [0,1] is a pure function that
  sets sun azimuth (west to east: azimuth sweeps 270 through 180 to 90
  degrees), elevation (a sine arc from 2 deg up to a noon peak and
  back), colour and intensity (a sunrise-noon-sunset ramp: warm dim,
  white bright, warm dim), writing the sliders and colour input so the
  UI always tells the truth. The noon peak is captured ONCE from the
  elevation slider when the cycle starts (state.dayCycle.peakElevation)
  so the function never reads the slider it writes.
- The clock lives in frame() exactly like the build timeline:
  state.dayCycle = { playing, t, seconds }. frame() advances t by
  delta while playing and calls applyDayCycle(t / seconds). At u = 1
  it stops (no loop).
- Sky mode: the sky follows the sun live; PMREM relighting is
  throttled to at most one regeneration per 0.5 s of day-cycle
  playback (a frame-count throttle inside the day-cycle branch of
  frame(), not a clock read inside any apply function), with one final
  regeneration when the cycle stops.
- Recording: when the checkbox is on, recordAnimation advances the day
  cycle deterministically per frame (u = frameIndex / totalFrames when
  recording the day cycle alone; when layered over a build recording,
  u tracks the build timeline's own fraction), calling applyDayCycle
  before each frame render. Purity holds: recording never reads the
  wall clock for the day cycle.
- The day cycle runs in every environment mode (in Studio and HDRI it
  moves the light only; in Sky it also drives the sky).

### S6. The crown seam: diagnose, then fix by cause

- The probe reproduces Param's screenshot: a study at rest with the
  net visible (Both or Timeline mode at strike), close on the crown
  ridge, captured. Hypothesis to test first: the thrust net (black
  wires, white nodes) lies on the MID-surface, so it slices through
  the shell's top wherever the extrados curves below the mid-surface
  line between courses: correct geometry, terrible reading.
- If confirmed: in Both and Framework modes WITH the shell visible
  (Both), the net display offsets outward along the local normal by
  half the bundle thickness plus one wire radius, so it drapes ON the
  shell instead of through it; Framework mode (net alone) keeps the
  true mid-surface position, and the offset is display-only (a group
  position/geometry transform at applyShowMode time), never touching
  analysis data. If the diagnosis lands elsewhere (formwork z, piece
  placement, a real thickness bug), fix that cause; the wave does not
  ship the hypothesis without the capture.

### S7. Material appearance controls

- Per-material render overrides in Study, under the material select: a
  Tint colour input id `material-tint`, a Finish slider id
  `material-finish` (roughness 0.3 to 1.0), and a Reset button id
  `material-reset`. Applying a tint or finish updates the piece
  materials in place (colour and roughness only; maps stay).
- Overrides persist per material name in localStorage and re-apply on
  load. The HUD and Data panel keep reporting the true analysis
  material; a one-line note under the controls says "render tint only,
  analysis unchanged" so the honesty rule holds on screen.
- Three new render skins in their own select, id `render-skin`, next
  to the tint controls: None (default), White presentation concrete,
  Basalt dark, Timber ply. A skin is a CLIENT-side appearance
  (colour, roughness, texture) layered over whatever analysis
  material is selected; it never travels to the server, so the
  material select, the bundle, staging and the honesty notes are
  untouched. Skin choice persists with the tint overrides. Real
  analysis-grade materials are queued work, not this wave.

## Out of scope

- The rim geometry fix and wave 6b patterns (next wave, already
  ordered), 6c, Wave B (props dropdown, extra props, grass, buildings,
  clouds), ROS (own brainstorm).
- Precipitation, cut cancellation (queued), any solver or contract
  change.

## Testing

- Static pins: the moved controls' new sections; event-log element and
  logStudio wiring from the named sites; banner dismiss timers and
  close control; the absence of HDRI_MAX_BYTES; GroundedSkybox vendor
  file and projection controls; sun-colour input and override flag;
  day-cycle controls, state shape, applyDayCycle purity (no clock
  reads; frame() is the only advancer) and the recording branch;
  show-mode net offset (post-diagnosis, per the confirmed cause);
  material override controls, persistence keys, and the render-only
  note; the three render presets and their honesty note path.
- The probe re-runs for: the crown capture before and after the fix;
  a day-cycle sweep screenshot triplet (sunrise, noon, sunset); the
  ground-projected HDRI at two scales.
- Server tests updated for the removed cap (oversize test deleted;
  magic and containment tests stand).
- Suites from the COMPAS-Workflow-bench worktree. No em dashes, no
  attribution, nothing pushed.
