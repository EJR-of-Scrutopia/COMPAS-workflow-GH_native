# Bench Studio: staged precast simulation and presentation animation

Date: 2026-08-09
Status: approved in conversation, written for review
Branch: feature/bench-studio (off development at e7b4b53)

## Purpose

A local web studio that turns the bench's verified analysis into a presentation.
It loads the Grasshopper thrust-network exports, treats the funicular surface as
temporary falsework, places precast segments onto it from the rim to the crown,
runs the staged structural story through the existing OpenSees pipeline, and
renders all of it at genuine visual quality: PBR materials, a lit environment,
a placement animation, toggleable FEA layers, and a record mode that produces
video frames for the presentation.

The presentation is days away. The build order in this spec is chosen so the
studio is on screen against real study data on day one, with staged analysis
data arriving behind it.

## What exists already

- Exports in `bench/demo/upload from grasshopper/`: four `*-contract.json`
  files (about 5.8 MB each) carrying `equilibrium.vertices` (2521),
  `equilibrium.edges` (4800), `formGraph.faces` (2400 quads), per-node
  `loads`, per-support `reactions`, `edgeStates` with axial forces, and
  `lengthUnit` metres. `src/ananke_fea/mesh.py` already reads this contract.
- Verified results in `bench/studies/<name>/fea-verification.json` for
  `trial-2` and `algebraic-tna-method`: material assumptions text,
  cross-check verdicts, peak displacement, reactions, stress summary,
  tension sweep. These are the day-one data.
- `src/ananke_fea/` (fea venv): model building, self-weight, static runs,
  stress summaries, all six backend defects shimmed. A full solve on this
  mesh takes about 2 seconds.
- `bench/demo/_bootstrap.py`: the pattern for handing a script to the right
  interpreter (`.venv`, `.venv-cra`, `.venv-fea`).
- Materials in `src/ananke_fea/materials.py`: concrete C30/37 unreinforced
  (EN 1992-1-1 clause 12: 16.0 MPa compression, 1.07 MPa tension) and timber
  GL24h (EN 14080:2013: 15.36 MPa, 12.288 MPa).

## Concept

The GH-exported funicular surface is falsework, not the finished structure.
Precast segments are cast off site, then placed onto the falsework ring by
ring, outer rim first, sweeping around by angle, closing at the crown. While
the falsework stands it carries everything. Only when the shell is complete
is the falsework struck and the shell works as a compression structure. The
studio tells that story twice at each stage: the real case (falsework
carries) and the counterfactual (struck now), where early partial rings have
no equilibrium and the completed shell does. That contrast is the point of
the animation.

## Architecture

Everything lives in `bench/studio/`:

```text
bench/studio/
  app.py               FastAPI application (main .venv)
  bundle.py            study bundle builder: mesh, fields, subdivision
  segmentation.py      canonical ring/wedge binning (mirrored in JS)
  staging.py           staged twin-solve orchestration (shells to .venv-fea)
  solve_stage.py       runs inside .venv-fea: one partial-shell solve
  columns/             drop-in folder for column geometry JSONs
  static/
    index.html
    studio.js          scene, layers, animation, UI
    binning.js         the JS mirror of segmentation.py
    studio.css
    vendor/            three.module.js + addons, pinned and committed
```

Rules that hold throughout:

- The server runs in the main `.venv` and never imports `compas_fea2` or
  `ananke_fea`. All solving happens by shelling `solve_stage.py` to
  `.venv-fea\Scripts\python.exe`, the `_bootstrap` pattern. A guard test
  mirrors `tests/test_no_fea_cross_import.py` over `bench/studio/`.
- The browser never computes analysis results. It re-bins segmentation for
  display and animates, nothing more. Python numbers are canonical.
- No CDN, no network assets. Three.js and its addons are vendored under
  `static/vendor/` at a pinned version.
- FastAPI and uvicorn arrive as a new `studio` extra in `pyproject.toml`,
  installed into the main venv. Neither touches numpy, scipy, or compas;
  the existing pin-guard test catches any accidental movement.

## Server API

- `GET /api/studies`: list study names with available exports and cached
  bundles. Study names are slugified export names (Trial 2 becomes
  trial-2), the same mapping demo 09 uses; a run on a fresh export creates
  its study folder.
- `GET /api/studies/{study}/bundle?material=...&rings=...`: return the
  bundle JSON, built and cached on disk under
  `bench/studies/<study>/studio/`. Bundles are keyed by export, material,
  and ring count; an existing file is served without recomputation.
- `POST /api/runs` with `{export, material, rings}`: start a staged run in
  a background thread, return a run id. One run at a time per study;
  a second request while one is live returns 409 with the live run id.
- `GET /api/runs/{id}`: `{state, stage, of, message, bundle_url}` where
  state is queued, running, done, or failed. The UI polls this.
- `POST /api/frames/{run}` and `POST /api/frames/{run}/stitch`: record
  mode, described below.
- `GET /`: the studio page, plus static files.

## Study bundle

One JSON the page loads per (export, material, ring count):

- `analysis_mesh`: vertices, quad faces, edges, straight from the contract.
- `render_mesh`: one Catmull-Clark-style subdivision pass, 2400 to 9600
  faces, with a parent-face index per subdivided face and interpolated
  vertex positions. Built once in Python; the browser never subdivides.
- `fields` per stage: full per-node displacement vectors and per-element
  stress (top and bottom surface principal values), not just peaks. Fields
  ship once at analysis resolution; the render mesh carries a
  vertex-sources map, and the page applies the same averaging rule the
  Python subdivision defines (tested to preserve values at original
  vertices), so vertex fields carry over without duplicating every field
  at render resolution per stage. Face fields inherit from the parent
  face.
- `segments`: the canonical Python assignment (face index to segment id)
  for the requested ring count, plus placement order.
- `staging`: the per-stage twin-solve results (next section).
- `verification`: the existing `fea-verification.json` content, embedded,
  so the Data button needs no second request.
- `provenance`: export name, material preset text, thickness, solver
  timings, generation timestamp.

Size estimate: fields for eight stages on this mesh are on the order of
one to two MB. Acceptable for localhost; bundles are cached, not rebuilt.

## Segmentation

One slider controls ring count R (range 4 to 16, default 8). The binning
rule is deliberately trivial so it can live twice, once in
`segmentation.py` (canonical, used for every analysis partition) and once
in `binning.js` (display only, so the slider re-bins instantly from
shipped face centroids without a server round trip):

- Axis: the vertical line through the mean (x, y) of all mesh vertices.
- Per face: centroid, radial distance rho from the axis, angle theta.
- Ring index: R equal-width bins over [rho_min, rho_max] of face
  centroids, ring 0 outermost (the rim), ring R-1 the crown.
- Wedges per ring: `W_r = max(1, round(12 * rho_mid_r / rho_mid_0))`,
  so the rim ring splits into 12 pieces and rings shrink toward a single
  crown cap. A segment is one (ring, wedge) cell.
- Stagger: odd rings get an angular offset of half a wedge, so joints do
  not align ring to ring. Explicitly: wedge index is
  `floor(((theta + offset_r) mod 2pi) / (2pi / W_r))` with
  `offset_r = (r mod 2) * pi / W_r`.
- Placement order: ring 0 first, wedges in increasing theta, then ring 1,
  and so on to the crown. This is the build sequence and the drop order.

Parity: the bundle ships the Python assignment for its ring count. On
load, the page recomputes with `binning.js` and compares. A mismatch shows
a visible warning banner and the page defers to the shipped assignment.
A committed fixture (Python assignments for R in {4, 8, 12} on the Trial 2
centroids) documents the rule and pins it in tests.

## Staged twin-solve

For each stage s from 1 to R, rings 0 through s-1 are placed:

- With falsework (the real case): no FEA solve. The falsework carries the
  placed weight; the studio reports exact bookkeeping: cumulative placed
  self-weight (face areas, thickness, material density, the existing
  `self_weight_loads` constants), the formwork load curve stage by stage.
- Struck now (the counterfactual): a real solve in the fea venv on the
  placed submesh alone, supported only at the export's support nodes that
  fall inside placed faces, loaded with its own self-weight plus the
  export's nodal loads restricted to placed nodes. Early stages will not
  find equilibrium, or find it with absurd deflections; that is reported
  honestly as `{converged: false, message}` or as the numbers themselves.
  The completed stage R is the real verification case and must agree with
  demo 09's output for the same export and material.

R solves at roughly 2 seconds each keeps a full staged run under a minute,
including bundle writing. Runs are per material; switching material in the
UI triggers a new run (or serves the cached bundle).

## Materials

A selector with the two EN presets: concrete C30/37 unreinforced and
timber GL24h, both already in `materials.py` with their derivations in the
docstrings and reconstruction tests. Switching re-runs staging because
stiffness and density change every number. The verification panel always
displays the preset's assumptions text.

`compas_timber` remains out: it models joinery, not shell continua. A
timber rib variant stays in the backlog.

Steel appears only as a scene material for the columns; columns are not
part of any solve.

## Scene and rendering

Quality is a requirement, not a nicety. Concretely:

- Renderer: ACES filmic tone mapping, physically based lighting, soft
  shadows (PCFSoft), sRGB output.
- Environment: PMREM-processed RoomEnvironment (vendored addon) for
  reflections, a ground plane that receives soft shadows, a background
  tone control, a directional sun with azimuth and elevation sliders, and
  a hemisphere fill so shadow sides stay readable.
- Concrete: MeshPhysicalMaterial, light warm grey, procedural
  canvas-generated noise for albedo and roughness variation so faces do
  not read as flat plastic.
- Timber (GL24h): procedural grain texture, warm tone, low sheen.
- Steel (columns): metalness 1.0, roughness about 0.35, environment
  reflections doing the work.
- Falsework: a distinct dark matte tone so segments read against it while
  it stands; it fades out at the strike moment.
- Thrust network layer: the 4800 analysis-mesh edges as instanced thin
  cylinders (wires) with instanced small spheres at all 2521 vertices
  (nodes). Toggleable. Instancing keeps this one draw call each.
- Columns: a loader for a second JSON that Param will export. Accepted
  format: either the same contract style (a mesh with vertices and faces)
  or a plain `{"vertices": [[x,y,z],...], "faces": [[a,b,c,d],...]}`.
  Files dropped into `bench/studio/columns/` are listed by the server and
  baked into the scene with the steel material. Until the file arrives the
  studio simply has no columns; nothing else depends on them.

## Placement animation

- Each segment drops from a fixed height above its final position and
  settles with an ease-out curve: crane placement, no bounce. Segments
  start hidden and appear at their drop time.
- Timeline order is the placement order from segmentation: rim ring
  sweeping around, then inward, crown last. At the final stage the
  falsework strikes (fades and lowers) and the shell stands with the
  thrust wires.
- Sliders: drop speed (seconds per segment), orbit speed, and orbit
  distance for the auto-spinning camera. Dragging the camera pauses
  auto-spin; releasing resumes it.
- The same timeline drives interactive play and record mode; time is a
  pure function of frame number so recording is deterministic.

## Analysis mode: FEA layers

A panel of independently toggleable layers, all reading bundle fields:

- Stress heatmap: per-face colouring on a diverging palette, compression
  toward blue, tension toward red, with a surface picker (top, bottom, or
  worst of both).
- Deflection heatmap: displacement magnitude colouring, plus an
  exaggeration slider that displaces the render mesh geometry by the
  field times the factor.
- Load vectors: arrows at loaded nodes, scaled and legended.
- Reaction vectors: arrows at supports.
- Text overlays: peak stress and utilisation, peak deflection and span
  ratio, current stage, formwork load carried, material name. Rendered as
  a HUD, not floating 3D text, so it stays legible in recordings.
- Integrity pulse: a per-stage verdict from the struck-now solve, a green
  or red glow on the placed shell, with the honest "no equilibrium found"
  wording when the solver said so.
- Data button: a side panel rendering the embedded verification JSON in
  readable form: assumptions text, cross-check verdicts including the
  self-stress member note, tension sweep table.

Layers with missing data (an older bundle, a failed stage) disable
themselves with a visible reason instead of rendering nothing silently.

## Record mode

- A record button runs the timeline at a fixed timestep (60 frames per
  second of timeline time), with the scripted orbit camera, and captures
  the canvas to PNG per frame (`canvas.toBlob`), POSTing each to
  `POST /api/frames/{run}`. The server writes
  `bench/studies/<study>/studio/frames/frame-%06d.png`.
- `POST /api/frames/{run}/stitch` runs ffmpeg (`-framerate`, `yuv420p`)
  to an mp4 next to the frames. The server checks for ffmpeg on PATH at
  startup and the stitch endpoint returns an instructive error if it is
  missing; frames are always written regardless.
- Resolution follows the canvas; the studio offers a 1920x1080 canvas
  preset for recording.

## Error handling

- A failed or non-convergent stage is data, not an error page: the bundle
  records `{converged: false, message}` and the UI shows the honest state.
- Solver stderr from `.venv-fea` is captured into the run's `message` on
  failure, so the browser shows why, not just that.
- Segmentation parity mismatch: warning banner, Python assignment wins.
- Concurrent run requests: 409 with the live run id; the UI offers to
  watch the live run.
- Missing study, export, or bundle: 404 with the list of what exists.

## Testing

- `segmentation.py`: every face assigned exactly once; ring 0 contains
  the outermost centroid and ring R-1 the innermost; wedge counts follow
  the rule; stagger alternates; placement order is rim to crown and
  sweeps by angle; determinism across calls. The R in {4, 8, 12} fixture
  on real Trial 2 centroids is committed and asserted.
- `staging.py`: final-stage placed weight equals total shell self-weight;
  the formwork load curve is monotone; stage R struck-now equals the
  demo 09 result for the same inputs (gated fea test).
- `bundle.py`: schema keys present; render mesh has four times the faces;
  parent-face map covers every subdivided face; vertex field
  interpolation preserves values at original vertices.
- API: FastAPI TestClient with a stub stage runner injected so CI needs
  no fea venv; run lifecycle (queued, running, done, failed, 409);
  bundle caching; frames endpoint writes files; stitch without ffmpeg
  returns the instructive error.
- Guard: `bench/studio/` never imports `compas_fea2` or `ananke_fea`
  (same pattern as `tests/test_no_fea_cross_import.py`).
- The JS mirror is exercised by the runtime parity check against the
  shipped assignment; `binning.js` stays a small pure module to keep that
  check meaningful.

## Build order

The presentation deadline drives this. Each step leaves something usable.

1. Studio on screen against existing data: server, page, vendored
   Three.js, PBR materials, environment and lighting panel, thrust wires
   and nodes, the analysis mesh rendered directly (the subdivided render
   mesh arrives with bundles in step 2), segmentation slider re-binning
   client-side, stress and deflection layers wired up against the existing
   `fea-verification.json` summaries (peaks as uniform colour scale
   anchors until full fields arrive).
2. Full bundles: `bundle.py` with subdivision and full final-state fields
   from a fresh solve, layer panel switched to real per-element data,
   Data button.
3. Staging: `staging.py` and `solve_stage.py`, twin-solve per stage,
   placement animation with its three sliders, integrity pulse, falsework
   strike moment.
4. Record mode and polish: frames, stitch, 1080p preset, columns loader
   when the JSON arrives, material switch re-runs.

## Backlog, ranked

If time remains before the presentation, in order:

1. Final-state CRA stability badge (demo 04 machinery).
2. Concrete versus timber A/B comparison panel.
3. Per-stage CRA.
4. Robot placement choreography (demo 05 IK synced to the timeline).
5. Mould-count clustering (how few distinct moulds cast all segments).
6. Falsework spring-stiffness decentering study.

## Out of scope

- `compas_timber` joinery modelling.
- GPU or multicore solver work.
- Editing geometry in the browser; the studio consumes exports.
- Deployment beyond localhost; this is a single-user presentation tool.
- Segment thickness variation, joint detailing, reinforcement: segments
  are constant-thickness shell pieces cut from the analysis mesh.
