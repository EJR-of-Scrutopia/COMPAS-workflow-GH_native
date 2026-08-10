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

- Study, material (C30/37 or GL24h), and a segmentation slider (4 to 16
  rings; wedge counts follow ring radius, staggered ring to ring).
- Run staged analysis: per stage, the falsework bookkeeping is exact
  arithmetic and the struck-now counterfactual is a real OpenSees solve in
  .venv-fea; stages that find no equilibrium say so.
- FEA layers: stress and deflection heatmaps (full per-element and
  per-node fields), load and reaction vectors, text overlays, the
  integrity pulse, thrust wires with node spheres.
- Placement animation with drop, orbit speed, and orbit distance sliders;
  the falsework strikes after the last segment lands.
- Record 1080p writes PNG frames through the server and stitches
  `recording.mp4` with ffmpeg.
- Column geometry dropped into `bench/studio/columns/*.json` (either
  `{"vertices", "faces"}` or a contract-style export) renders in steel.

Generated outputs live under `bench/studies/<slug>/studio/` and are not
committed. The server never imports the solver stacks; a guard test holds
it to that.

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
studio's ring count rather than on the size of the thing being analysed.
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
./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py 2
./.venv/Scripts/python.exe bench/scripts/cra_acceptance.py 4
```

Both runs re-measured 2026-08-10 after the solver-parameter fix above and
the epistemics fix below, and these are the numbers an operator repeating
the two commands gets today. The earlier pass in this section reported
"does not stand" on three stages; those results are withdrawn, and the
Reading paragraph at the end of this section explains why.

#### Volume comparison, mesh-following block model vs voussoirs

| rings | mesh-following | voussoirs | volume difference |
| --- | --- | --- | --- |
| 2 | 13 blocks, 6408 faces (492.9/block), 38.1737 m3 | 13 blocks, 164 faces (12.6/block), 26.9065 m3 | -29.5% |
| 4 | 21 blocks, 7188 faces (342.3/block), 38.1737 m3 | 21 blocks, 308 faces (14.7/block), 31.4984 m3 | -17.5% |

The mesh-following volume is identical at both ring counts (a partition
of the same closed mesh sums to the same total regardless of how it is
cut), confirming both models see the same underlying export. The voussoir
volume is not: replacing every mesh face on a joint with one planar face
undercounts volume, by nearly a third at rings=2 and by a sixth at
rings=4, closing only because finer segmentation makes each joint flatter
to begin with. Zero cells were skipped at either ring count. Block count
is identical between the two models at both ring counts: it is fixed by
the ring/wedge segmentation, not by which block-building method runs on
top of it. This figure does not change with CRA_BLOCK_BUDGET; it is
unaffected by the recalibration below.

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

rings=2, total wall time 47.2 s then 44.8 s on a repeat run with
identical verdicts:

| stage | blocks | interfaces | verdict | status | timing |
| --- | --- | --- | --- | --- | --- |
| 1 | 8 | 2 | no verdict (None) | maxIterations | reached at 0.1 s |
| 2 | 13 | 17 | no verdict (None) | infeasible | reached at 9.1 s |

rings=4 (the studio's minimum), total wall time 21.9 s then 22.1 s on a
repeat run with identical verdicts:

| stage | blocks | interfaces | verdict | status | timing |
| --- | --- | --- | --- | --- | --- |
| 1 | 6 | 0 | stands (True) | all blocks are supports (trivial case) | reached at 0.1 s |
| 2 | 13 | 10 | no verdict (None) | Cannot load a SolverResults object with bad status: error | reached at 2.7 s |
| 3 | 19 | 0 | no verdict (None) | over budget (19 > 14) | reached at 14.1 s |
| 4 | 21 | 0 | no verdict (None) | over budget (21 > 14) | reached at 17.7 s |

No stage timed out in either run, and no cell was skipped at either ring
count. An over-budget or all-supports stage reports 0 interfaces because
the solver never runs (over budget) or has nothing to check (every block
already grounded): interface detection happens inside the rigid-block
solve itself, so a stage that never reaches the solver has none to count.

**Reading**: this export now returns no structural verdict at all. The
only True is stage 1 at rings=4, where every placed block is a support
and no solve happens; every other stage is an honest null. That is a
worse-looking result than the previous pass, which reported "does not
stand" on three stages, and it is the correct one. Those earlier results
were withdrawn for two independent reasons found by control rather than
by argument.

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
this pass measured and the one that had gone undisclosed: the faceted
analysis surface sits up to 2.389 m from the drawn surface at rings=2 and
1.964 m at rings=4, against a shell half thickness of 0.1 m. Even a
converged verdict on this model would be a verdict about blocks sitting
metres from where the studio draws them.

What is left is a tool that refuses rather than misleads, and a vault
that has not been assessed. Two things would move it forward, in order:
the conditioning work noted under the solver parameters above (the
objective is not scale homogeneous and density 2400 pushes the squared
objective to 5.8e8 against an absolute tol of 1e-8), and a voussoir model
whose analysis surface tracks the drawn one within something closer to
the shell thickness. Neither is a tuning exercise on this export.

One measurement should be read as a warning rather than a result. The
same k sweep was run on this export's own stages, twelve values from 0.5
to 0.001, on every stage inside CRA_BLOCK_BUDGET:

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
