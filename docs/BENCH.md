# The Bench

The bench is the VS Code half of this repository: everything that happens
to a design after the Grasshopper Export component writes its JSON. It
reads the plugin's exports headlessly, verifies them structurally,
tessellates them into masonry, views them, and writes results back to disk
as JSON. Rhino is never required.

The bench and the plugin never import each other's runtime. They exchange
files, and `tests/test_no_fea_cross_import.py` enforces the boundary in
both directions.

## What arrives from Grasshopper

The Export component writes two files per design, and the bench uses both:

- `<name>-contract.json` (Format=contract) is the whole solved Result:
  member forces, loads, reactions, supports, both diagrams, diagnostics.
  Everything numerical comes from here. Units are metres and kilonewtons
  with tension positive; the bench converts to SI base units exactly once,
  on read.
- `<name>-compas.json` (Format=compas) is `compas.data` geometry: the
  thrust mesh as a real Mesh with faces, plus the form and force graphs.
  Tessellation and shell modelling start from here.

Drop both into `bench/demo/upload from grasshopper/`. Anything that analyses an
export discovers the available pairs at runtime and never hard-codes a
file name; with no argument, the verification demo picks the export whose
own solver residual is smallest.

## The three environments

One interpreter cannot hold this ecosystem: compas_cra needs a pyomo that
needs Python 3.10 and numpy below 2, while the main bench mirrors Rhino
8's pins, and compas_fea2's OpenSees backend needs the core at a specific
git commit. So there are three, each built by a script:

| Environment | Python | Built by | Holds |
| --- | --- | --- | --- |
| `.venv` | 3.12 | `pip install -e ".[...]"` per the root README | numpy 2.0.2, scipy 1.13.1, compas 2.15.1, compas_fd, compas_tna, compas_dem, viewers |
| `.venv-cra` | 3.10 | `bench/scripts/setup_cra_env.sh` | compas_cra, pyomo 6.4.2, IPOPT (installed by hand, see below) |
| `.venv-fea` | 3.12 | `bench/scripts/setup_fea_env.sh` then `bench/scripts/install_opensees.py` | compas_fea2 @ 664ec20, compas_fea2_opensees, OpenSees 3.8 |

You never pick the interpreter yourself: every demo hands itself to the
environment it needs through `bench/demo/_bootstrap.py`, so the VS Code play
button works whatever the editor has selected. The FEA test suite collects
only where the OpenSees backend is installed, so `pytest` in the wrong
environment skips it rather than failing.

The FEA environment also needs a `.env` at the repository root pointing at
the OpenSees executable; `bench/scripts/install_opensees.py` writes it.

## The `ananke` terminal tool

`src/ananke_equilibrium/cli/`, installed with the main environment:

```text
ananke health              which capabilities this environment actually has
ananke check  <study>      validate a study folder before solving
ananke solve  <study>      run the worker headlessly, write the result
ananke describe <result>   solver, units, counts, diagnostics, residuals
ananke plot   <result>     form, force, and elevation diagrams (matplotlib)
ananke view   <result>     interactive 3D scene (compas_viewer)
ananke sweep  <study>      solve a family of load cases, compare
```

`describe` and `check` are the first thing to run on a new export: they
report the solver's own residual and whether loads and reactions cancel,
which tells you how far to trust everything downstream.

## The demos

`bench/demo/` holds nine clickable demos plus a gallery of upstream COMPAS
examples; the [demo runbook](../bench/demo/README.md) documents each one. The
short map:

```text
01 solve the pavilion        FD solve from a study folder, viewed
02 diagrams                  form and force diagrams from a result
03 load cases                sweep and compare
04 masonry blocks            tessellate a thrust surface into bricks
05 robot placing             analytical IK placing the vault's bricks
06 masonry gallery           compas_dem template shapes
07 compas official           upstream examples, run unmodified
08 your vault                read a real export, size it, tessellate it
09 structural verification   the engineer's answer; see below
```

## Structural verification, demo 09

`src/ananke_fea/` is the strand that answers whether the exported design
stands up. It runs only in `.venv-fea`. The demo, in order:

1. Reads the chosen export pair and reports units, supports, applied load,
   and the solver's own residual.
2. Cross-checks the FEA setup: the thrust network solved as a frame of
   deliberately slender beams under the export's exact loads. Reactions
   must balance the applied load; member forces are compared against TNA
   with the honest caveat that a quad network admits self-stress, so
   per-member equality is only expected on determinate fixtures.
3. Solves the shell under export loads plus the declared section's self
   weight (disclosed in the output, switchable), and reports stress
   utilisation and deflection.
4. Sweeps rising load factors for tension onset.
5. Sizes a provisional cable where tension appears, with its caveats
   attached.
6. Attempts the arc-length collapse trace and reports plainly that the
   backend cannot construct it at the current pin, rather than inventing
   a number.
7. Writes `bench/studies/<export-name>/fea-verification.json`.

Every claim in the strand is backed by a measurement one level simpler
than itself: the solver chain is proven against a cantilever's closed
form, member-force extraction against a tripod's statics, and the shell
stress conversion against plate-theory hand values.

The pinned compas_fea2 has several defects that report success while
returning wrong numbers; `src/ananke_fea/compat.py` documents each one and
carries the shims. Read its module docstring before touching anything in
the strand.

## Outputs

Analysis results land in `bench/studies/`, one folder per export name, as plain
JSON the main environment can read without any FEA packages. Every result
carries its own assumptions: material sources and factors, load
provenance, whether self weight was included, and notes on what each
check can and cannot falsify.

## The Studio

`bench/studio/serve.py` (play button or `.venv\Scripts\python.exe bench/studio/serve.py`)
serves http://127.0.0.1:8600: the presentation surface over the bench's
verified analysis. It reads the same export pairs as demo 09, treats the
funicular surface as falsework, and stages precast segments onto it rim to
crown.

- Study, material (concrete, concrete C50, sprayed concrete, timber, brick,
  tile or stone), a pattern control, and a piece size slider (0.3 to 3.0 m;
  the cut is rebuilt server side, not recomputed in the browser).
- Run staged analysis: per stage, the falsework bookkeeping is exact
  arithmetic and the struck-now counterfactual is a real OpenSees solve in
  .venv-fea; stages that find no equilibrium say so, and a material with no
  `ananke_fea` preset (brick, tile, stone) says plainly that no struck-now
  check exists for it rather than reporting a convergence failure that
  never happened.
- FEA layers: stress and deflection heatmaps (full per-element and
  per-node fields), load and reaction vectors, text overlays, the
  integrity pulse, thrust wires with node spheres.
- Placement animation runs to a constant 35 second build whatever the
  piece count: each casting still falls for 0.8 s, but the stagger between
  drops is derived from the count, so castings overlap in flight rather
  than landing one at a time. A timeline speed control scrubs playback
  from 0.25x to 4x; orbit speed and orbit distance sliders set how the
  camera circles the model. The falsework strikes after the last segment
  lands.
- The panel holds six collapsible sections in order: Import, Study,
  Analysis, View, Animation, Scene. Record is a button inside Animation
  that writes 1080p PNG frames through the server and stitches
  `recording.mp4` with ffmpeg.
- Study section: material, pattern and piece size control, thickness,
  joint gap, crown taper. A Render skin select (White presentation, Basalt
  dark, Timber ply) with Tint and Finish (0.3 to 1.0) sliders and Reset
  button; appearance changes are render-only, persisted per material, with
  an on-screen note "render tint only, analysis unchanged".
- Analysis section: Run staged analysis button; heatmap and vector layer
  toggles (stress and deflection per-element and per-node fields, load and
  reaction vectors, text overlays and the integrity pulse); stress surface
  modes (per surface, worst of both, top, bottom); deflection exaggeration
  slider; Data button to inspect the cut's coverage report.
- View section: Show select (Framework renders the bare thrust net, Shell
  the finished masonry, Both shows both, Timeline plays the build animation
  and is the default); Formwork select which defaults to Hidden (Always
  stands the ghost falsework clear of the shell's inner face); Node size
  (0.01 to 0.10 m) and Wire size (0.005 to 0.06 m) sliders. In Both mode
  and Timeline, the thrust net clears the shell by half the built thickness
  plus its own wire/node radius so the crown seam vanishes; Framework mode
  keeps the true mid-surface.
- Scene section: Environment select offers three exclusive modes. Studio
  offers the neutral room as a backdrop (default), with a tone slider for it.
  Sky is a physical scattering shader with five weather presets (Clear, Hazy,
  Overcast, Golden hour, Night); sun azimuth and elevation sliders drive both
  light and sky, staying live across all presets with relighting on slider
  release. A Sun colour picker overrides preset colours until the next preset
  change. HDRI mode uses .hdr files dropped into bench/studio/hdri/ or
  uploaded from the browser (any valid Radiance .hdr, no size cap); the studio
  estimates the sun from the image's brightest region and sets the sliders,
  which remain live to override the estimate. HDRI Projection select: Projected
  stands the image on the ground as a dome with Scale (10 to 300 m), Height
  (0.5 to 20 m, one correct viewpoint per Height), and Rotation sliders;
  Infinite keeps the classic flat backdrop with Rotation only. Shadows track
  Rotation in both modes. Day cycle block: Play button, duration 10 to 120 s,
  During recordings checkbox; Play sweeps the sun across the sky through dawn,
  noon and dusk colours; sky follows in Sky mode; with the checkbox on,
  recordings carry the sweep deterministically.
- Brightness (0.3 to 2) and Contrast (-0.5 to 0.5) sliders grade the exposure;
  these carry into recordings. Analysis colours (heatmaps: stress, deflection)
  are unlit data: no sun, sky or HDRI change them, so they read identically
  under every environment and lighting mode. They are not immune to the
  display grade itself; like everything else on screen they still pass
  through tone mapping, Brightness and Contrast in the EffectComposer chain,
  the same as the old lit rendering did. That grade is a monotone mapping, so
  ordering and sense always hold, and the rendered colours track the legend
  far closer than the old lit rendering did. Load and reaction vectors are
  ordinary lit scene objects, not exempt from lighting or the display grade.
- Ground select offers four procedural presets: Dark studio (default), Concrete
  slab, Patio pavers and Tiles. Props are five placeable objects (Figure, Tree,
  Pallets, Barrier, Cone); arm a prop button, click the ground to place, drag
  to move, press R for 15 degree rotations, Delete removes, clicking empty
  ground deselects. Layouts save per study in the browser and survive a reload;
  props appear in recordings. Clear props empties the layout.
- Column geometry dropped into `bench/studio/columns/*.json` (either
  `{"vertices", "faces"}` or a contract-style export) renders in steel.
- A bottom-right event log holds the last seven timestamped studio events
  (loads, cuts, uploads, analysis runs, HDRI loads, every banner) and fades
  when quiet. Banners self-dismiss in 6 seconds (info) or 12 seconds (errors),
  have a close X button, and pause their countdown while hovered; the event
  log keeps the full history.

Generated outputs live under `bench/studies/<slug>/studio/` and are not
committed. The server never imports the solver stacks; a guard test holds
it to that.

### The cut: tessellation replaces the ring and wedge binning

The studio used to bin whole analysis-mesh faces into concentric ring and
wedge cells (4 to 16 rings, wedge counts following ring radius). A cell's
shape was whatever the binning happened to sweep up, not a real polygon: on
the Trial 2 export, measured before any of this landed,

```text
cell        faces   boundary edges   corner runs
(0, 3)         70               66             4
(0, 4)         35               30             3
(1, 0)         66               86             3
```

A four sided voussoir has four boundary edges; these had thirty to
eighty-six. The 2026-08-12 cutting engine wave replaced the binning with a
real tessellation: a pattern (`bench/studio/generators.py`) or an imported
Grasshopper cut (`bench/studio/tessellation.py`) draws polygon cells
straight from the vault's own star shaped plan, welds them into one
conforming cut with T junctions resolved rather than forbidden, and
`bench/studio/pieces.py` caps each cell with a triangulated, flat jointed
casting lifted onto the thrust surface. `bench/studio/segmentation.py`, the
ring and wedge binning itself, is retired; the studio's own size and pattern
controls, and `bench/scripts/cutting_measurements.py` below, are what now
pin the cut on real geometry.

`bench/scripts/cutting_measurements.py` measures the replacement on the
same Trial 2 export, at 0.9 m, the size the studio opens to by default. It
writes nothing into `studies/`. Run it with
`.venv\Scripts\python.exe bench\scripts\cutting_measurements.py` and it also
checks itself against every figure the wave's own controller had already
measured by hand (the plan's star shape, the default size's coverage, and
the old coverage regression at 1.5 m, now cleared); every check below passed
on the run this table is taken from, 2026-08-13:

| measurement | value |
| --- | --- |
| star shaped | yes (238 of 240 rim steps forward, 2 backward, 0.467 degrees total, winding exactly 2 pi) |
| target size, courses, pieces | 0.9 m, 7 courses, 233 pieces |
| facets per piece | min 5 / median 6 / max 17 (the max belongs to course 0, the rim) |
| boundary points per piece | min 40 / median 48 / max 136 |
| subdivision rounds | 3, limited by rounds (the edge length target, not the chord target, is what the round budget cuts off here) |
| cap chord deviation | 0.960 mm against a 5.0 mm target |
| corner normal residual, 695 corners | median 0.0196, mean 0.0325, p99 0.2428, max 0.3295 (its own worst corner, in courses 0 and 1) |
| clamped cap points | 137 of 41265, reaching 0.0523 m at the worst and 0.0246 m at the median |
| coverage | 0 orphan faces, 0 double faces (of 2400 analysis faces), 0 open facets, 0 slivers, 0 folded, 0 coverage holes, 0 broken boundary entries, 0 missing planes |

The studio polish wave tried tightening the cap subdivision, CAP_EDGE_TARGET
0.30 m to 0.15 m and MAX_ROUNDS 3 to 4, and `cutting_measurements.py
--density` measured that candidate at 13.13 s / 42.53 MB against a 0.9 m
baseline of 3.16 s / 11.26 MB and 68.89 s / 327.61 MB against a 0.3 m
baseline of 26.88 s / 87.46 MB, past the budget (2x seconds, 3x payload) at
both probe sizes. A second rung tried CAP_EDGE_TARGET 0.20 m alone with
MAX_ROUNDS left at 3, and measured 3.02 s / 11.26 MB at 0.9 m and
24.01 s / 87.46 MB at 0.3 m -- identical to the baseline, because
MAX_ROUNDS 3 was already the binding constraint at both probe sizes on
this export (see the subdivision rounds row above): a finer edge target
changes nothing while the round budget cuts the subdivision off first, so
that rung added no real density either. No rung tried this wave passed the
budget gate while actually adding density, so CAP_EDGE_TARGET and
MAX_ROUNDS stay at the values the table above already reports, 0.30 m and
3, unchanged from before the wave.

#### The coverage limit, over the whole slider rather than at one size

This section used to publish a second figure: "at 1.5 m the same export
grows 2 coverage holes, 1 broken boundary entry and 1 orphan face", read
as a real limit of the cut at coarse sizes. It was not a size limit at
all. `generators._arc` emitted the points it inserts ordered by the angle
they came from rather than by the angle actually used, so any span
crossing a seam came out of order and its own outline crossed itself.
That affected 35 of the 55 slider sizes on this export, 53 self-crossing
cells and 183 report entries in total, and it was scattered across the
slider rather than concentrated at the coarse end, which is precisely
what a measurement at one size cannot see. The before and after sweep is
in `.superpowers/sdd/2026-08-12-cutting-engine/final-fix-engine-report.md`.
The fix is in `generators._arc`, and the claim this document makes is now
made across every position of the size slider rather than at one point:

```bash
.venv\Scripts\python.exe bench\scripts\cutting_measurements.py --sweep
```

Measured 2026-08-13 (re-run after the studio polish wave, CAP_EDGE_TARGET
still 0.30 m, unchanged from the 2026-08-12 figures below, because coverage
is a cut-level property and does not move with subdivision density),
bonded courses, all 55 slider positions from 0.30 to 3.00 m in steps of
0.05:

| sizes | orphan faces | double faces | open facets | slivers | coverage holes | broken boundary |
| --- | --- | --- | --- | --- | --- | --- |
| 54 of 55, 0.35 to 3.00 m | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.30 m, the slider's finest | 0 | 2 | 0 | 0 | 0 | 0 |

1.5 m is clean, and so is every size on the slider but the finest. At
0.30 m two analysis faces have centroids inside three cells each: face
268 in c3p108, c4p102 and c5p96, and face 2268 in c3p57, c4p54 and
c5p50. `tessellation.analysis_binding` assigns such a face to the lowest
indexed cell that claims it, so nothing is counted twice downstream, but
cells that overlap in plan are a real defect at that size and the report
names both the face and every cell claiming it. One of the three in each
case (c4p102, c4p54) is also on the folded list below; whether the fold
is the cause of the overlap has not been measured.

What a tolerated rim wobble costs is folded cells, and the sweep names
every one of them:

| size | folded cells |
| --- | --- |
| 0.30 m | 6: c10p34, c10p65, c4p102, c4p54, c5p51, c5p95 |
| 0.35 m | 4: c0p108, c0p58, c9p27, c9p52 |
| 0.45 m | 2: c5p27, c5p52 |
| 0.50 m | 2: c0p40, c0p74 |

14 in total, at 4 of the 55 sizes, none above 0.50 m and none at the
default. `bench/studio/domain.py`'s note on WOBBLE_TOLERANCE traces them
to the rim's own plus or minus 125.4 degree notch, where the boundary
steps in from 10.9136 m to 9.4519 m while a cell's inner boundary is a
straight chord that passes outside it: that is the cost of tolerating a
rim wobble rather than refusing the export outright. The rim's clipped
silhouette and crescent notches are genuine tessellation limits: 137 outline
points are clamped by the cap's outermost-crossing rule, and on the reference
export at 0.9 m they reach a median of 24.6 mm and a maximum of 52.3 mm.
A density increase cannot remove the notches because they are outline points
clamped by the cap's geometry rule, not a subdivision artifact. A folded
cell is still cut, still capped and still drawn, with one lobe of its cap
inside out, and it enters none of the coverage counts above: the sliver
test reads an algebraic area and a fold's two lobes cancel in it, so
`report["folded"]` naming the cell by key is the entire disclosure. The
studio's Data panel lists it beside the coverage line for exactly that
reason. The default size stays at 0.9 m, which is clean on every count.

A single worst-corner number for the residual badly misrepresents the cut,
so `pieces.residual_stats` reports the whole distribution across every
corner rather than only its maximum, and `docs/BENCH.md` and the Data
panel both quote it in full:

| residual | radians (sine of the angle) | degrees | corners over |
| --- | --- | --- | --- |
| median | 0.0196 | 1.1 | -- |
| mean | 0.0325 | 1.9 | -- |
| p99 | 0.2428 | 14.1 | -- |
| max | 0.3295 | 19.2 | -- |
| over 0.01 | -- | over 0.6 | 487 of 695 |
| over 0.05 | -- | over 2.9 | 134 of 695 |
| over 0.10 | -- | over 5.7 | 38 of 695 |
| over 0.20 | -- | over 11.5 | 10 of 695 |
| over 0.30 | -- | over 17.5 | 2 of 695 |

The median is the figure that describes the cut: a typical corner sits at
0.0196 (1.1 degrees), the same order as `bench/studio/pieces.py`'s own test
fixture (a four cell synthetic dome chosen to be a stress case), which
measures 0.0104 (0.598 degrees) at its single worst corner -- roughly half
the real median, not a tight match. The max describes only its own
worst corner, not the cut as a whole, and the worst corners cluster in the
rim course (course 0), where `generators._arc` inserts the mesh's own
boundary corners so the drawn silhouette follows the real, irregular rim
rather than a straight chord: more corners inserted there means facets
meeting at sharper angles, and a sharper angle between two facets
necessarily pushes a stored normal further out of the one it does not
belong to. It is the same cause as the facets-per-piece maximum of 17
above: both are the rim course, not the general cut, so neither number
should be read as typical against the medians beside them.

In plain physical terms: the residual is the sine of the angle between a
corner's stored normal and the plane of the facet that does not own it, so
at the shipped 0.2 m shell thickness (a half thickness of 0.1 m either
side of the mid surface a corner's normal actually offsets along), a
residual of `r` moves that corner roughly `100 * r` millimetres from where
a perfectly flat joint would put it. The median, 0.0196, is about 2 mm;
the worst corner, 0.3295, is about 33 mm. Nothing in the shipped
acceptance tests bounds either figure on real geometry (the `< 0.02` bound
in `tests/studio/test_pieces.py` is pinned to the synthetic fixture only),
so none of this is a failing measurement, but the tail is real and worth a
look, at the rim course specifically, before this reaches a client-facing
drawing. A real fix exists (using the intersection line of the two planes
at a corner where only two facets meet, which would take those corners to
zero) but is deliberately not applied here: that is a change to the
keystone module at the end of a wave, and spending it is the owner's call.

## CRA solver setup (IPOPT)

compas_cra solves through pyomo's ipopt solver, a native binary that pip
does not install. The studio's CRA verdicts need it in the CRA venv:

1. Download the win64 zip of the latest Ipopt 3.14.x release from
   https://github.com/coin-or/Ipopt/releases (asset used here:
   Ipopt-3.14.19-win64-msvs2022-md.zip).
2. Extract it and copy everything in its bin/ directory (ipopt.exe and
   the DLLs beside it) into .venv-cra/Scripts/.
3. Verify:

   ```bash
   .venv-cra/Scripts/python.exe -c "
   import os, sys
   from pathlib import Path
   os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
   import pyomo.environ
   from pyomo.opt import SolverFactory
   print(SolverFactory('ipopt').available(False))
   "
   ```

   must print True. Both the PATH prepend and the `pyomo.environ` import
   are load-bearing here: pyomo's solver lookup only checks the PATH
   environment variable, not the directory holding its own python.exe,
   and importing `pyomo.opt` on its own never registers the ipopt plugin.
   Plain `from pyomo.opt import SolverFactory` with no PATH change prints
   False even with the binary in place.

The binary lives inside the git-ignored venv: nothing lands in the
repository. bench/studio/solve_cra.py prepends its own Scripts directory
to PATH the same way, so no machine-wide configuration is needed. Without
the binary, CRA verdicts report stands: null with a pointer back to this
section.

### Solver parameters: why d_bnd and eps are derived, not defaulted

`cra_penalty_solve` takes `d_bnd`, the bound on the virtual displacement,
and `eps`, the contact overlap parameter. Both are absolute lengths in
metres, and upstream's defaults of 1e-3 and 1e-4 are tuned for
compas_cra's own unit-scale examples. The Trial 2 export is 14.99 by
20.26 by 7.00 m, a bounding box diagonal of 26.2 m, with joints metres
wide. Left at the defaults the verdict became a function of how large the
model happened to be drawn.

The control that shows it is a semicircular arch of five radial
voussoirs at t/R = 0.20, springers fixed as supports, out-of-plane width
0.5 R, concrete at mu = 0.6. Heyman's minimum thickness for a
semicircular arch is about 0.11 R, so this arch certainly stands. At the
defaults it returned three different answers:

| radius | termination |
| --- | --- |
| 1 m | infeasible |
| 2 m | maxIterations |
| 4 m | maxIterations |
| 8 m | Cannot load a SolverResults object with bad status: error |

Rigid-block feasibility under friction is scale invariant, so that spread
is the solver's parameterisation leaking into the verdict.

Both parameters are lengths, so dimensional similarity requires them to
scale with the model: scale the geometry by s, scale d_bnd and eps by s,
and the program maps onto itself. `solve_cra.characteristic_length`
returns the diagonal of the axis aligned bounding box over every block
vertex in the request. The whole assembly's box is used rather than a
representative joint edge because a per-joint measure shrinks as the
segmentation refines: the solver parameters would then depend on the
studio's target piece size rather than on the size of the thing being
analysed.
`eps` keeps upstream's own eps/d_bnd ratio of one tenth, which is
dimensionless and is the parameter the formulation actually cares about.

`D_BND_FRACTION` is measured, not guessed. Sweeping k = d_bnd / length
from 0.001 to 0.5 on that arch at 1, 2, 4 and 8 m, the widest contiguous
band that converges at every radius is 0.045 to 0.08 (0.04 fails at 4 m,
0.09 fails at 8 m); a second band runs from about 0.24 to 0.45. Below
0.03 the solve degrades systematically, which is why upstream's implied k
of around 3e-4 on unit-scale examples never stood a chance here. The
band, not any single value inside it, is the result. The full sweep, at
nine radii, is recorded in
`.superpowers/sdd/2026-08-10-voussoir-blocks/final-fix-report.md`.

Two limits are worth stating plainly. Scale invariance is restored at the
four radii the control asserts, but not everywhere: 6 m fails at almost
every k tried, and 12 and 16 m fail at most. Those are IPOPT numerical
failures rather than infeasibility findings, and they are erratic in
radius rather than monotone in k, which points at conditioning. The
objective is not scale homogeneous even when d_bnd and eps are (the force
terms grow as s^6 and the alpha term as s^4), and the studio passes
density 2400 where upstream uses 1.0, so the squared objective sits
around 5.8e8 against IPOPT's absolute tol of 1e-8. Rescaling density
would be a legitimate conditioning move, since the feasible set maps
linearly and the tension ratio the verdict reads is unchanged by it, but
it has not been done.

### Acceptance measurement: Trial 2 export

`bench/scripts/cra_acceptance.py` runs the real staged CRA gate on the
Trial 2 export, with no stubs: the struck-now FEA solve shells to
.venv-fea and the rigid-block verdict to .venv-cra, exactly as the server
does. It writes its staging document to a temporary directory so a probe
run can never masquerade as a cached study result. Repeat it with:

```bash
./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py bonded-courses 0.9
./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py bonded-courses 3.0
```

The script's arguments are `[pattern] [size]`, the studio's own two cut
controls. They used to be a bare ring count, and the two commands printed
here were `cra_acceptance.py 2` and `cra_acceptance.py 4`, which since the
2026-08-12 cutting wave error out with `ValueError: unknown pattern '2'`.
0.9 m is the size the studio opens to and 3.0 m the coarsest the API
accepts, which is also the fewest blocks this export can be cut into and
so the closest it ever comes to the rigid-block budget.

The two tables that follow are the ones the script prints. The staged CRA
tables further down are not: they were taken under the ring and wedge
binning the cutting wave retired, and they have not been re-run against
the cut. Each says so where it stands.

#### Volume comparison, mesh-following block model vs voussoirs

Re-measured 2026-08-12 against the cut, at the two sizes the commands
above name:

| target size | mesh-following | voussoirs | volume difference |
| --- | --- | --- | --- |
| 0.9 m | 233 blocks, 11676 faces, 38.1737 m3 | 259 blocks, 3764 faces, 36.6983 m3 | -3.9% |
| 3.0 m | 20 blocks, 6832 faces, 38.1737 m3 | 20 blocks, 284 faces, 30.2643 m3 | -20.7% |

The mesh-following volume is identical at both sizes (a partition of the
same closed mesh sums to the same total regardless of how it is cut),
confirming both models see the same underlying export. The voussoir
volume is not: replacing every mesh face on a joint with one planar face
undercounts volume, by a fifth at 3.0 m and by 3.9 percent at the
default, closing because a finer cut makes each joint flatter to begin
with. Zero cells were skipped at either size.

Two things this table used to say are no longer true and are withdrawn
rather than edited. It was keyed on a ring count the studio no longer
has, and it reported block counts identical between the two models
because the ring and wedge segmentation fixed them. At 3.0 m they still
agree, 20 against 20; at 0.9 m they do not, 233 against 259, because a
cell the cut splits into separate patches becomes separate voussoirs
while `blocks.segment_blocks` still builds one prism per cell. Read the
volume difference, which is a property of the joint model, rather than
the block count, which is now a property of which builder ran. This
figure does not change with CRA_BLOCK_BUDGET; it is unaffected by the
recalibration below.

#### Budget recalibration: CRA_BLOCK_BUDGET

The original CRA_BLOCK_BUDGET=8 was set on the theory that block count
drove the rigid-block solve's cost, before the voussoir model existed to
test that theory against. With voussoirs in place, this measurement pass
found that block count does drive real cost, just not the cost the
original guard was written against: the CRA_TIMEOUT_SECONDS wall clock.
Real .venv-cra solves on the Trial 2 export at growing block counts,
2026-08-10, concrete/mu=0.6, all self-contained single-stage solves (not
gated by any budget for this measurement):

| blocks | seconds | result |
| --- | --- | --- |
| 6 | 0.10 | real verdict (every block a support, no solve needed) |
| 8 | 4.3 | real verdict: does not stand |
| 13 | 18.75 | real verdict: does not stand |
| 14 | 46.45 | real verdict: does not stand |
| 15 | 60.55 | solver gave up: maxIterations, no verdict |
| 16 | 55.08 | solver gave up: maxIterations, no verdict |
| 17 | 47.52 | solver gave up: maxIterations, no verdict |
| 19 | 63.21 | solver gave up: maxIterations, no verdict |
| 21 | 80.14 | solver gave up: maxIterations, no verdict |

The cliff is sharp: every attempt at 14 blocks converged, no attempt at
15 or above did. Past 14 the nonlinear IPOPT solve exhausts its own
iteration cap rather than finding an answer, well short of the 600 s
CRA_TIMEOUT_SECONDS backstop in every case measured (worst failure: 80 s).
Raising the timeout would not rescue those stages; they fail on
convergence, not on wall clock. CRA_BLOCK_BUDGET is set to 14, the
largest block count measured to return a real verdict on this export.
This is an empirical ceiling on one geometry, not a proof that every
14-block assembly converges or every 15-block one fails; CRA_TIMEOUT_SECONDS
stays in place as the backstop for whatever a different assembly actually
does. The full measurement, including the script used, is recorded in
`.superpowers/sdd/2026-08-10-voussoir-blocks/task-4-report.md`.

#### Staged CRA gate, per stage (recalibrated budget, CRA_BLOCK_BUDGET=14)

Re-measured 2026-08-12 against the cut. 3.0 m, the coarsest cut the API
accepts, total wall time 9.1 s, mu 0.6, no cell skipped:

| stage | blocks | interfaces | verdict | status | timing |
| --- | --- | --- | --- | --- | --- |
| 1 | 15 | 0 | no verdict (None) | over budget (15 > 14) | reached at 0.4 s |
| 2 | 20 | 0 | no verdict (None) | over budget (20 > 14) | reached at 4.9 s |

0.9 m, the size the studio opens to, total wall time 25.0 s, mu 0.6, no
cell skipped:

| stage | blocks | interfaces | verdict | status | timing |
| --- | --- | --- | --- | --- | --- |
| 1 | 68 | 0 | no verdict (None) | over budget (68 > 14) | reached at 0.6 s |
| 2 | 127 | 0 | no verdict (None) | over budget (127 > 14) | reached at 3.3 s |
| 3 | 173 | 0 | no verdict (None) | over budget (173 > 14) | reached at 6.3 s |
| 4 | 218 | 0 | no verdict (None) | over budget (218 > 14) | reached at 9.7 s |
| 5 | 242 | 0 | no verdict (None) | over budget (242 > 14) | reached at 13.5 s |
| 6 | 255 | 0 | no verdict (None) | over budget (255 > 14) | reached at 17.1 s |
| 7 | 259 | 0 | no verdict (None) | over budget (259 > 14) | reached at 21.1 s |

No stage timed out in either run. An over-budget stage reports 0
interfaces because the solver never runs: interface detection happens
inside the rigid-block solve itself, so a stage that never reaches the
solver has none to count.

**Reading**: this export returns no structural verdict at all, and under
the cut it cannot. The smallest stage the API can produce on this
geometry is 15 blocks, at the coarsest size the slider offers, against a
CRA_BLOCK_BUDGET of 14: one block over, and every finer size is further
over. Every stage at every size is an honest null on that ground alone,
and no solver ever runs. That is not a defect in this script, it is a
property of this export's block count, and `run_staging`'s `include_cra`
defaults to False because of it.

Two earlier results in this section were withdrawn, and the reasoning
stands whatever the cut does. The pass before last reported "does not
stand" on three stages; the pass after it reported a single True, at
rings=4 stage 1, where every placed block was a support and no solve
happened. Neither result survives, the first because it was wrong and the
second because the ring count it was keyed to no longer exists. The two
independent reasons the "does not stand" was withdrawn were found by
control rather than by argument.

First, a solver parameterisation artefact. `d_bnd` and `eps` were left at
upstream's unit-scale defaults, which are absolute lengths in metres, on
a model 26 m across. The control is above: a semicircular arch at
t/R = 0.20, comfortably above Heyman's minimum, returned three different
answers at 1, 2, 4 and 8 m. Whatever the old runs on this vault were
measuring, it was not a scale-invariant property of the assembly.

Second, the "does not stand" was never a finding. It came from reading
IPOPT's "Converged to a locally infeasible point. Problem may be
infeasible." as proof of infeasibility. Under an interior point method on
a nonconvex program that is one solve failing from one starting point,
and upstream's own "may be" says so. Those stages were nulls being
reported as failures.

So the earlier uniform does-not-stand result was a solver
parameterisation artefact on top of a positional modelling error, not a
structural reading of the vault. The positional error is the second thing
that pass measured and the one that had gone undisclosed: the faceted
analysis surface sits up to 2.389 m from the mesh-following block surface
at rings=2 and 1.964 m at rings=4, against a shell half thickness of
0.1 m. Even a converged verdict on this model would be a verdict about
blocks sitting metres from where the studio draws them. Those two figures
were taken under the ring and wedge binning the cutting wave retired, and
have not been re-run against the cut: they are kept as the record of why
the earlier verdicts were withdrawn, not as a current measurement, and
the ring counts naming them no longer correspond to any studio control.

Read that pair for what it is. Both surfaces come from the same analysis
mesh: `voussoirs.segment_voussoirs` against `blocks.segment_blocks`, and
at the time of the measurement the second of those was also what the
viewer drew. It is not any more. The studio now draws `pieces.py`
castings, whose boundaries are projected onto flat joint planes, shrunk
by the joint gap and thinned by the crown taper, so the figures above are
a distance between two analysis models and no longer a distance to what
is on screen. The studio's own disclosure says so in those words rather
than repeating these numbers.

What is left is a tool that refuses rather than misleads, and a vault
that has not been assessed. Two things would move it forward, in order:
the conditioning work noted under the solver parameters above (the
objective is not scale homogeneous and density 2400 pushes the squared
objective to 5.8e8 against an absolute tol of 1e-8), and a voussoir model
whose analysis surface tracks the drawn one within something closer to
the shell thickness. Neither is a tuning exercise on this export.

One measurement should be read as a warning rather than a result. The
same k sweep was run on this export's own stages, twelve values from 0.5
to 0.001, on every stage inside CRA_BLOCK_BUDGET. It was taken under the
ring and wedge binning the cutting wave retired and has not been re-run
against the cut, and it cannot be: the cut's smallest stage at the
coarsest size the API accepts is 15 blocks, so no stage on this export is
inside the budget any more and the sweep has nothing left to run on. It
is kept because what it says about k is a statement about the solver
rather than about the segmentation.

| stage | blocks | k values reaching a verdict | the verdict |
| --- | --- | --- | --- |
| rings=2 stage 1 | 8 | 7 of 12 | does not stand, tension at joints, at all seven |
| rings=2 stage 2 | 13 | 0 of 12 | none |
| rings=4 stage 1 | 6 | 12 of 12 | stands, all supports, no solve |
| rings=4 stage 2 | 13 | 0 of 12 | none |

Two readings follow. At 13 blocks no value of k reaches a verdict, so
those nulls are a property of the problem at that size and not an
artefact of the k chosen. At 8 blocks whether a verdict appears does
depend on k, but its content does not: all seven say the same thing, from
the tension check on a converged solution rather than from a termination
string. The shipped k = 0.05 is not one of the seven.

That value was kept deliberately. It is inside the measured band and ties
for the best robustness across the nine arch radii tested; k = 0.06 is
also inside the band and would return the rings=2 stage 1 verdict, but it
measures worse on the scale invariance this parameter exists to
establish, and choosing the value that makes the real export produce an
answer is the reasoning this whole section exists to correct. An operator
who wants that stage assessed should treat it as a sensitivity study and
say so, not adjust the constant.
