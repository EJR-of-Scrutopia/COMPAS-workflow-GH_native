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

Both runs measured here, 2026-08-10. The CRA_BLOCK_BUDGET recalibration
below happened between the first and second measurement pass; the numbers
in this section are from the second pass, with the recalibrated budget in
place, and are what an operator repeating the two commands above gets
today.

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

rings=2, total wall time 46.5 s:

| stage | blocks | interfaces | verdict | status | timing |
| --- | --- | --- | --- | --- | --- |
| 1 | 8 | 2 | does not stand (False) | infeasible, no rigid-block equilibrium under friction | reached at 0.1 s |
| 2 | 13 | 17 | does not stand (False) | infeasible, no rigid-block equilibrium under friction | reached at 4.5 s |

rings=4 (the studio's minimum), total wall time 34.2 s:

| stage | blocks | interfaces | verdict | status | timing |
| --- | --- | --- | --- | --- | --- |
| 1 | 6 | 0 | stands (True) | all blocks are supports (trivial case) | reached at 0.1 s |
| 2 | 13 | 10 | does not stand (False) | infeasible, no rigid-block equilibrium under friction | reached at 2.5 s |
| 3 | 19 | 0 | no verdict | over budget (19 > 14) | reached at 25.9 s |
| 4 | 21 | 0 | no verdict | over budget (21 > 14) | reached at 30.1 s |

No stage timed out in either run. An over-budget or all-supports stage
reports 0 interfaces because the solver never runs (over budget) or has
nothing to check (every block already grounded): interface detection
happens inside the rigid-block solve itself, so a stage that never
reaches the solver has none to count.

**Reading**: recalibrating the budget on measurement, not on the original
guess, buys real verdicts where the old budget refused untried: rings=2
now reaches a verdict on both of its stages instead of one, and rings=4
(the studio's minimum) reaches a verdict on two of its four stages
instead of one. Stages 3 and 4 at rings=4 are still refused, honestly,
because 19 and 21 blocks are past the measured convergence cliff at 14;
raising the budget further would not buy a verdict there, only tens of
seconds spent reaching the same null. A real study on this export still
does not get a verdict end to end at the studio's minimum ring count, but
it now gets two verdicts and two honest refusals instead of one and
three. Every non-trivial real verdict obtained so far on this export,
across every block count from 8 to 14, has been the same answer: the
assembly does not stand. That consistency is itself worth flagging
rather than explaining away: it may be a genuine structural reading of
this vault staged this way, or it may be an artefact of the voussoir
model's own volume undercount (17.5 to 29.5 percent below the drawn
segment, see the volume comparison above) changing the weight and
contact geometry the solver sees. This measurement does not distinguish
between those two explanations; it only reports that every stage large
enough to solve, and small enough to converge, has said no.
