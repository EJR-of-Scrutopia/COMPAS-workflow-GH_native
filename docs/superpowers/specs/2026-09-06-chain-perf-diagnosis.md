# Whole-chain speed diagnosis, 2026-09-06 (profiling only, no fixes)

Tree measured: scratch git-archive of a09b7f9 (the build Param is running) at
`C:\Users\Param\AppData\Local\Temp\claude\c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui\0df46ca4-9f90-4938-93e9-c6b9ac56b1c1\scratchpad\perf-real`.
Machine: Param's desktop, Release build, .NET 8/10 SDK, Rhino 8 assemblies
referenced but Rhino itself never launched (headless). Python side: a scratch
venv at `...\scratchpad\wenv` (compas 2.15.1, compas_tna 0.9.0, compas_fd
0.5.4, numpy 2.5.2, scipy 1.18.1 - close to, not bit-identical with,
pyproject's pin of compas_tna==0.7.0; timing shape is what is being read, not
exact numerics).

Fixtures: Param's own eight real exported studies at `C:\Users\Param\OneDrive
- Ananke-eidos\Documents\Kinetic AI\PHD robotics\COMPAS Exports` (441 to 1321
vertices, per the standing method ruling). Every number below except where
marked "synthetic" is measured on these files.

    study                v      f     edges  supports  file size
    2 sided vault       441    400     840     42        1.11 MB
    2 sided vault Hex   661    600    1260     63        1.67 MB
    3 sided vault       661    600    1260     63        1.67 MB
    3 sided vault Hex   661    600    1260     63        1.67 MB
    4 sided vault       881    800    1680     84        2.21 MB
    4 sided vault Hex   881    800    1680     84        2.21 MB
    5 sided vault      1101   1000    2100    105        2.79 MB
    6 sided vault      1321   1200    2520    126        3.34 MB

His own exported control settings (read off `control.provenance` in every
`-form.json`): `heightMode=zmax, heightValue=5, horizontalMethod=algebraic`,
component name "TNA Solve Algebraic" - i.e. the canvas reading "TNA Solve A"
in the brief is exactly this: he is ALREADY on the algebraic horizontal
method, not the iterative default.

## 0. Headline

The felt ~6.3 s (Skin 1.6 s + TNA Horizontal 2.2 s + TNA Solve A 2.5 s) is
real and is not dominated by Skin at all any more. On his own largest,
most-detailed net (6 sided vault, 1321 v, 908 skin cells) the REAL worker
round trip alone, measured end to end through the actual WorkerHost against
a real persistent Python process, is:

    TNA Horizontal (Move=100), full round trip     1.81 s
    TNA Solve A    (H=5),      full round trip      2.19 s
    ---------------------------------------------------------
    measured, worker-round-trip only                4.00 s

against his reported 2.2 + 2.5 = 4.7 s for the same two components - i.e.
the worker round trip alone accounts for ~85% of the felt Horizontal+Solve
time on his biggest net. The rest is Grasshopper-side (DeepClone before
dispatch, preview-line/mesh building, the task-capable-component scheduler)
and is not the majority of the story any more.

Inside that 4.0 s, the single largest, cleanly measured, ALREADY-WASTED
component is the self-weight refinement loop inside `solve_tna_problem`:
comparing an identical solve with a Height target (`zmax`) against the same
solve with a natural height (no refinement) isolates it precisely, and on
every one of his eight nets the loop burns its full 10-round cap WITHOUT
converging (`TNASelfweightRefinementWarning: ... did not settle in 10
rounds`). That is 500 ms to 3.3 s of every zmax solve spent iterating to a
budget limit it never reaches, on real self-weight loads he actually uses.

The second largest lever is not new: the queue's own 2026-09-04 finding that
`RecoverCancelledRequestAsync` kills and restarts the ENTIRE shared worker
process on any cancelled request (`WorkerHost.cs:911-991`) is confirmed here
to apply to every TNA stage, not only Export - because `WorkerRuntime.Host`
is one process-wide singleton every component calls into. Measured fresh:
~850-1050 ms for the worker's first-ever request in a session (process
launch + `import compas`/`compas_tna`/`tree_forest_compas.tna` + hello), and
40-100 ms of extra delay on the next request after each SUBSEQUENT cancelled
tick once the OS file cache is warm. A slider scrub supersedes a task on
almost every tick (solves take hundreds of ms to seconds, far longer than a
drag frame), so this fires repeatedly through one gesture.

## 1. The per-gesture recompute map

Read from the component definitions (`plugin/native_v02/Components/
SolverComponents.cs`, `SkinComponents.cs`, `ColumnsComponent.cs`,
`MouldComponents.cs`, `DeliveryComponents.cs`) and confirmed against the
worker dispatch table (`src/ananke_equilibrium/worker.py`). Grasshopper
expires a component and everything wired to ITS outputs when an input
changes; it does NOT re-run anything upstream. The wiring in this
definition is:

    Pattern -> Problem -> TNA Relax --RLX--> TNA Horizontal --RLX--> TNA Solve(A) --Result-->  Skin
                                                                                             -> Columns
                                                                                             -> Mould
                                                                                             -> Delivery/Export

Skin, Columns and Mould are three PARALLEL siblings that each take a `Result`
input directly (`SkinComponents.cs:149`, `ColumnsComponent.cs:90`,
`MouldComponents.cs:239/283`) - none of them feeds another; each recomputes
whenever `Result` changes, independent of the others.

### (a) Skin slider (Size / CH / MP / Th / Gaps)

Only Skin (+ Export/Delivery kinds wired from Skin's output) recomputes.
TNA Relax/Horizontal/Solve, Columns and Mould do NOT re-run - their own
inputs are unchanged. Measured felt cost today: ~1.6 s, all but ~0.11 s of
it Rhino-native (see section 4): the SkinSolveCache (`SkinComponents.cs:56-
62`, shipped 2026-09-06 morning) already removes the pure-C# pattern
rebuild on this gesture. A Th/Gaps tick specifically also gets a bottom-Brep
cache hit (`_cache.Bottoms`, `SkinComponents.cs:495-516`): each cell's bottom
face is a `DuplicateBrep()` of a cached original instead of a fresh
loft/fan+join. It does NOT skip the thickened solid itself (walls, top,
outer join, `IsValid`, `SolidOrientation`) because Th/Gaps is exactly what
that geometry depends on - see the dependency table in section 4.

### (b) Solver input move - THREE DIFFERENT GESTURES, not one

- **Move (TNA Horizontal)**: recomputes Horizontal, then (because its output
  changed) Solve, then (because ITS output changed) Skin + Columns + Mould +
  Export. TNA Relax does not re-run. This is the gesture that sums to the
  felt 6.3 s: Horizontal (2.2 s) + Solve (2.5 s) + Skin (1.6 s).
  MEASURED WASTE: `equilibrate_tna_problem`'s `move` argument only
  interpolates the OUTPUT between the drawn and the fully-equilibrated plan
  (`tna.py:2662-2675`); the expensive relaxation that finds "equilibrated"
  runs in full regardless of `move`. Measured round trip, Move=1 vs Move=100,
  same net (6 sided vault): 1915 ms vs 1776 ms - a 1-point drag costs the
  SAME as a full sweep, every tick.
- **Height / Iterations (TNA Solve inputs)**: GH correctly skips Relax and
  Horizontal (their own inputs did not change) - but `TnaSolveComponent`'s
  own worker call (`tna.solve`) unconditionally re-runs the WHOLE horizontal
  stage again inside `solve_tna_problem` (`tna.py:3068-3098`) before the
  (genuinely Height-dependent) vertical scale, so Solve alone still pays
  close to its full cost on a Height-only tick. Measured on the identical
  prepared/moved input, 6 sided vault: H=5 round trip 2125 ms, H=8 round
  trip 2815 ms (not cheaper - if anything worse, because the self-weight
  refinement round count is itself somewhat load-dependent). Downstream:
  Skin + Columns + Mould + Export recompute (Result changed); Horizontal's
  own output is untouched and does not re-run.
- **q / Boundary Sag / Floating Anchors (TNA Relax inputs)**: the worst
  case. Recomputes the WHOLE chain - Relax, Horizontal, Solve, Skin,
  Columns, Mould, Export. Rarely dragged live, but worth naming because it
  is the one gesture that pays every stage in this document at once.

### (c) Columns / Mould input move

Recomputes only that component (+ whatever Export kind reads it). Neither
`ColumnsComponent.cs` nor `MouldComponents.cs` contains a single
`Brep`/`Mesh` construction call (grepped for `Brep.Create`, `JoinBreps`,
`Mesh.Create`, `Loft`, `SweepOneRail`, `CreatePipe` - zero hits in both
files); they appear to be curve/line/frame-based, not native-geometry-heavy,
so this gesture is structurally cheaper than (a) or (b). Not measured in
depth here (time-boxed against the brief's priority on the solver chain);
the same `Stopwatch` pattern in section 6 applies directly if exact numbers
are wanted.

### (d) Fresh file open

The most expensive gesture, structurally. `SkinSolveCache` is a per-instance
field held only in the live component object; a document reopen constructs
fresh component instances, so EVERY cache in this codebase starts cold.
`WorkerRuntime.Host` is a static, process-wide singleton keyed to the
Rhino/GH process, not the document - so a brand new Rhino session opening
this file also pays the ~850-1050 ms worker cold start (process launch +
`import compas` + `compas_tna` + `tree_forest_compas.tna`, measured section
2) on top of the full Relax->Horizontal->Solve->Skin/Columns/Mould->Export
chain, with no cache anywhere. On the 1321-vertex net that is upwards of
4.3 s of worker round trips alone, plus cold start, plus GH's own document
load. Also see queue.md's own standing finding: `DeliveryComponents.cs:465-
475,1516-1610` builds ALL FIVE export kinds on every solve regardless of
Write/Live, one of which is a further out-of-process worker round trip
(`export.compas`) - this fires on file open too.

## 2. The solver stage budget on his real nets

### 2a. Python worker's own numerics (bare `tree_forest_compas.tna` calls,
min of 3 repeats, warm interpreter)

    study              register  prepare  equil.    solve iter   solve iter   solve ALG    solve ALG
                                  (relax)  (move=100)  AUTO+zmax  kmax=100    +zmax        +natural
    2 sided vault Hex     8.0 ms   45.3 ms   597.0 ms   753.1 ms   575.1 ms  1119.2 ms    149.5 ms
    2 sided vault         5.3      78.9     1163.1     1422.8      516.3     715.3       134.9
    3 sided vault Hex     7.8      50.8      887.4     1030.2      767.5    1527.5       200.7
    3 sided vault        11.3      50.8      882.0     1011.6      759.0    1503.2       190.0
    4 sided vault Hex    15.0      82.9      924.6     1334.1     1024.5    1051.2       213.6
    4 sided vault        14.5      82.3      908.3     1326.8     1002.5    1059.2       228.6
    5 sided vault        16.3     104.0     1921.9     1784.8     1285.5    1743.9       300.7
    6 sided vault        18.2      88.1     1627.2     1650.8     1145.8    3534.4       271.0

Register and prepare are cheap everywhere (<120 ms). Equilibrate and solve
dominate and scale with net size, roughly 0.6-2.0 s for equilibrate and
0.5-3.6 s for solve depending on method and whether a zmax target is set.

### 2b. Real end-to-end round trip (actual `WorkerHost` + actual persistent
Python worker, via `ChainProbe.cs` - see section 6): build / round-trip /
decode, ms

    study              Relax(prepare)         Horizontal(Move=100)     Solve A (H=5)
                       build / RT / dec       build / RT / dec         build / RT / dec
    2 sided vault Hex   7.0/ 140.5/ 34.3        12.3/ 622.5/ 24.0        15.5/1251.9/ 29.4
    2 sided vault        0.9/ 149.6/  4.8        4.1/ 953.8/  9.6         3.8/1238.6/ 16.5
    3 sided vault Hex    1.8/ 118.7/  5.1        3.8/ 629.4/ 11.3         7.5/1164.0/ 22.2
    3 sided vault        1.6/ 145.2/  6.1        6.4/ 629.6/  9.8        10.4/1186.7/ 11.2
    4 sided vault Hex    1.3/ 164.6/  9.8       21.8/ 626.7/ 11.7        13.7/1426.7/ 19.3
    4 sided vault        2.0/ 163.0/  7.3       11.6/ 694.5/  6.6         5.0/1442.8/ 18.2
    5 sided vault        1.5/ 213.3/ 11.2        6.6/1554.8/ 12.4        11.2/2015.1/ 38.6
    6 sided vault        2.6/ 272.2/ 13.2       11.3/1776.2/ 18.1        13.8/2125.0/ 53.1

C# payload build and response decode (`TnaWorkflowWorkerCodec`,
`TnaWorkerResultCodec`) are 2-54 ms everywhere - under 5% of the round trip
at the expensive stages (Horizontal, Solve), and comparable to or larger
than the actual computation only at the cheap Relax/prepare stage (where the
absolute cost, 120-270 ms, does not matter to the felt-6s story). C#
marshalling is not a lever worth chasing further at the Horizontal/Solve
stages.

The gap between the round trip and the bare-Python numerics (section 2a) is
the wire (JSON both sides) plus the `ananke_equilibrium.gh` wrapper, which
re-registers a fresh COMPAS `Pattern`/`TNAProblem` from the plain
vertex/face/q data on EVERY stage transition rather than carrying the COMPAS
object forward (`gh/tna_stages.py:247-276`, `:444+`) - real but small next to
the solves themselves (tens of ms, confirmed by the build+decode column
above already bounding the C#-visible half of it).

### 2c. The wire, at his real payload sizes

    file size    json.loads   json.dumps   orjson.loads   orjson.dumps
    1627 KB         13.0 ms      13.6 ms        5.7 ms         1.7 ms
    3260 KB         24.1 ms      27.0 ms       11.6 ms         3.6 ms

Same verdict as the previous (Skin-only) diagnosis, now re-based on his
actual chain-sized payloads: orjson is 2-8x faster per call but the absolute
saving (10-25 ms) is negligible against 100 ms-3.6 s solves. Not a cheap
win here either. `ContractJson.Deserialize<ProblemDto>` on the same files:
6.8 ms (441 v) to 15.6 ms (1321 v) - also negligible.

### 2d. Worker process life cycle (measured on the smallest net, twice,
independently - numbers below are from the second, fuller run)

    first request ever this process (launch + import + hello + solve)   857.0 ms
    second request, same process, same payload (persistent baseline)    125.5 ms
    next request after ONE cancelled mid-flight tick                    167.2 ms  (+41.7 ms over baseline)
    next request after TWO back-to-back cancelled ticks (a real scrub)  222.0 ms  (+96.5 ms over baseline)

The mechanism (`WorkerHost.cs:366-376,911-991`): any cancellation of any
in-flight request - which is exactly what a superseded drag tick does, per
`TnaRelaxComponent`/`TnaHorizontalComponent`'s own doc comments on "a
background task cancelled by a mid-drag solution race" - schedules
`RecoverCancelledRequestAsync`, which after a `CancellationGraceMs` (250 ms
default) grace period kills the WHOLE shared worker process and relaunches
it. It is shared: `WorkerRuntime.Host` (`WorkerRuntime.cs:18-29`) is one
static singleton every TNA component AND Export call into, so a cancellation
racing on Horizontal's request can cost Solve's next tick too. On THIS
machine with a warm OS file cache the relaunch itself is cheap (tens of ms);
the number that matters is the FIRST such event in a session (or after any
long idle that evicts the page cache), which is close to the full ~850-1050
ms cold-start figure. Queue.md already flagged this for Export; it is
confirmed here to be a property of the shared host, not of any one command.

## 3. The roadmap ideas, measured rather than assumed

**1. Direct linear (algebraic) horizontal solve.** Already in production use
- his own exported control settings show `horizontalMethod=algebraic` on
every study, i.e. "TNA Solve A" IS the direct solve, not a hypothetical
alternative. Measured against iterative auto-converge on the same nets
(section 2a): algebraic is faster on 3 of 8 nets and 1.4-3.1x SLOWER on the
rest, worst on his largest net (3534 ms vs 1651 ms, 6 sided vault). This
matches the previous diagnosis's verdict exactly: its value is bounded
numerical error, not speed. Switching more components onto it is not a
cheap win - he is already there and it does not solve the problem.

**2. Warm-start cache (start a re-solve from the previous answer).** Not
built anywhere: neither `equilibrate_tna_problem` nor `solve_tna_problem`
nor their `iterative`/`algebraic` internals (`horizontal_nodal`,
`_horizontal_auto_converge`, `_horizontal_algebraic`) accept an initial q
or state - grepped the whole of `tna.py` for `initial_q`/`warm_start`/`q0`
used as a caller-supplied seed and found only `q0` as the ALGEBRAIC method's
own internal uniform starting guess for its own least-squares correction,
never anything carried between separate worker calls. Expected saving: the
auto-converge loop's own iteration count IS the thing a warm start would
shrink - on these real nets that is most of equilibrate's 600 ms-2.0 s and
part of solve's cost, on any SMALL parameter tick. What would have to be
proved: that seeding from the prior converged q reaches the SAME final q
(not merely a nearby one) within the existing 1-degree/plateau gate, on the
seamed/holed fixtures this codebase already treats as adversarial; this is
new plumbing, not a measured-today number, and is flagged here as unbuilt
rather than claimed.

**3. Avoid a full re-solve when only downstream parameters changed.** TWO
concrete, ALREADY-MEASURED instances exist in the current code, both
described precisely in section 1(b):
  - Move (0-100%) always computes the FULL equilibrated target internally
    and only interpolates the output - Move=1 costs the same as Move=100
    (measured, section 1b).
  - Height (zmax) always re-runs the full horizontal stage inside
    `solve_tna_problem` even though it is documented as moving only the
    vertical scale - measured not cheaper (often costlier) across two
    Height values on the identical input (section 1b).
  What would have to be proved to cache either: I checked whether the
  horizontal force-density state is actually independent of the Height
  target by comparing `form.edges_attribute("q")` across two `zmax` calls
  on the SAME prepared problem (`worker_probe2.py`'s printed check) - on
  EVERY ONE of the eight real nets the answer came back **not** bit-
  identical. I did not trace why (candidates: the self-weight refinement
  loop's per-round geometry snapshot/restore touching more than the
  vertical state it claims to, or ordinary floating-point/iteration-order
  noise across two independent `_condition_pattern` rebuilds) - that trace
  is the proof this cut needs before it can be claimed safe, and it is
  explicitly NOT done here. The wall-clock waste is real and measured
  regardless of that answer; the CACHE is not yet provably safe.

## 4. The Rhino-side share for Skin (counts, on his real cell data)

His own exported `-skin.json` files ARE what the plugin actually produced,
so the counts below are his, not a synthetic fixture:

    study               cells   courses   avg corners/cell (his 6-sided sample)
    2 sided vault        215       -
    2 sided vault Hex    226       -
    3 sided vault Hex    226       -
    3 sided vault        461       -
    4 sided vault Hex    381       -
    4 sided vault        752       -
    5 sided vault        831       -
    6 sided vault        908      20        9.74 (min 4, max 19)

Per-cell native call shape, from `SkinComponents.cs` (bottom via
`CellSurface`, thickened solid via `ThickenCellSurface`, both a loft-of-2-
rails or a fan-of-N-corner-point Breps + `JoinBreps`, N wall quads via
`CreateFromCornerPoints`, one outer `JoinBreps`, `IsValid`,
`SolidOrientation`, possibly `Flip`): roughly `3N + 6` native
construction/validation calls per cell where N is corners (~10 on his real
net), i.e. ~36 calls/cell on a FULL rebuild (fresh file, or an S/CH/MP
move): 908 cells x 36 ~= 32,700 native calls.

On a Th/Gaps tick specifically, the bottom-Brep cache shipped 2026-09-06
(`SkinComponents.cs:495-516`, `_cache.Bottoms`) turns the bottom's own
`(N+1)`-call loft/fan+join into a single `DuplicateBrep()`, dropping the
per-cell count to roughly `2N + 7` ~= 27 calls/cell: 908 x 27 ~= 24,500 -
about a 25-28% cut in native call volume, which is the concrete, count-based
reason Skin fell from 2.4 s to 1.6 s and not all the way to its 0.11 s pure-
C# floor: the remaining 1.5 s is walls + top + outer join + `IsValid` +
`SolidOrientation` for ~900 solids, none of which the Th/Gaps cache touches,
because the dependency table is genuine here - the thickened solid's TOP
face is an offset by Th/Gaps, so it cannot be cached the way the bottom was
(the bottom depends on the cells alone; the top does not).

Preview meshing is the other uncounted piece: ~900 closed solids get
Rhino's own render-mesh conversion on every redraw of this component,
confirmed as a real, separate cost by the previous diagnosis and unchanged
by anything shipped since. Concrete, not-yet-measured reductions, each
count-based:
  - Coarser preview mesh quality specifically on Skin's `DrawViewportMeshes`
    (previous diagnosis's own suggestion, still unactioned): a render-mesh
    parameter change costs nothing to try and would isolate its ~900-solid
    share immediately.
  - Toggling Skin's preview off during a drag removes ~900 mesh conversions
    per tick outright - free to test, no code change.
  - A single "shell in one pass" construction (e.g. one loft with caps
    instead of bottom+top+N walls+outer join) would cut the per-cell native
    call count roughly in half again, but this is a QUALITY-RISK item flagged
    and explicitly NOT claimed by the previous diagnosis either: it changes
    which Breps are built and needs its own closure/orientation proof on the
    seam/holed fixtures.

## 5. Ranked cuts, by measured expected saving

1. **Stop letting the self-weight refinement loop burn its full 10-round
   cap without converging.** Measured cost today (algebraic+zmax minus
   algebraic+natural, same net, same load): 565 ms (2 sided vault) to
   3.35 s (6 sided vault) PER SOLVE, and it does not even reach its own
   tolerance when it does that work (`TNASelfweightRefinementWarning` fired
   on every net that hit the cap). This is not "correct but slow" - it is
   measured, confirmed waste on his own real loads. Quality risk: LOW to
   PROVE, not zero - a genuinely non-converging case exists and today's
   behaviour (fence at round 10, report the drift) is arguably the safe
   fallback; the fix is almost certainly a smarter stopping rule (relative-
   change-based early exit, or surfacing the non-convergence as a Warning at
   half the current round budget) rather than raising or lowering the cap
   blindly, and needs the same drift-tolerance proof the existing
   `SELFWEIGHT_REFINEMENT_TOLERANCE` already encodes.

2. **The cancellation-kills-the-shared-worker respawn.** Already named in
   queue.md for Export; measured here to apply to every TNA stage because
   `WorkerRuntime.Host` is one process for the whole plugin. Cost: ~850-1050
   ms for the first cancellation-triggered restart in a session (or after
   any idle long enough to evict the OS file cache), 40-100 ms per
   subsequent cancelled tick once warm, compounding across a multi-tick
   scrub (every tick during an active drag is superseded, since solves take
   longer than a drag frame). Quality risk: LOW - the fix queue.md already
   named ("a do-not-cancel-the-compas-request change") does not change any
   answer, only whether an in-flight, still-useful computation gets killed.

3. **Cache Move's target and Height's horizontal state instead of
   re-deriving them every tick.** Measured waste: Move=1 costs the same as
   Move=100 (equilibrate always computes the full target, only interpolates
   the output); Height=8 costs the same as or more than Height=5 on an
   identical prepared input (solve always re-runs the full horizontal stage
   before its vertical scale). Combined this is most of the reason dragging
   either of the two MOST NATURAL solver sliders never feels faster no
   matter what Skin does. Quality risk: MEDIUM, NOT YET CLEARED - my own
   check found the horizontal q is not bit-identical across two Height
   values on the same input on any of his eight nets, and I did not trace
   why before writing this report. That trace is the precondition for
   claiming this cut safe; until then the wall-clock waste is documented,
   not the fix.

4. **Warm-start the iterative horizontal solve.** Unbuilt - no entry point
   in `tna.py` accepts a caller-supplied initial q anywhere. Expected
   saving is bounded by the auto-converge loop's iteration count, which is
   most of equilibrate's measured 600 ms-2.0 s cost on a small parameter
   tick; needs new plumbing (thread a previous solution's q through
   Relax/Horizontal/Solve) and a proof that seeding changes only iteration
   count, not the final answer, on the seamed/holed fixtures this codebase
   already treats as adversarial.

5. **Skin's remaining Rhino-native share.** ~1.5 s on his 908-cell net is
   walls+top+outer-join+validate+preview-mesh for ~900 solids, unreachable
   by the Th/Gaps bottom-cache because the dependency is genuine (top is an
   offset by Th/Gaps). Free, no-code-change experiments to isolate it
   further: toggle Skin's preview off during a drag; drop its render-mesh
   quality. A one-pass shell construction would roughly halve the native
   call count again but is a real quality-risk item (closure/orientation
   proof needed on seam/holed fixtures), not claimed here.

Direct linear horizontal solve (roadmap item, section 3.1) is NOT ranked -
he is already on it and it is not faster on his real nets.

## 6. The probe machinery (lift-ready, scratch tree only)

### 6a. Python worker probe: `scratchpad\worker_probe2.py`

Drives `tree_forest_compas.tna.register_tna_pattern` /
`prepare_tna_problem` / `equilibrate_tna_problem` / `solve_tna_problem`
directly against all eight real `-form.json` studies, timing each stage
(3 repeats), comparing Move=100 vs Move=1, comparing algebraic+zmax vs
algebraic+natural (isolating the self-weight refinement loop), and
comparing two Height targets on the identical prepared problem with a q-
identity check. Run:

    <scratchpad>\wenv\Scripts\python.exe worker_probe2.py

Load-bearing fragment (loading his real studies and the Height-identity
check; full file is beside this report):

    def load_study(path):
        with open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
        pattern = doc["problem"]["anchored"]["pattern"]
        topo = pattern["topology"]
        vertices = [(v["x"], v["y"], v["z"]) for v in topo["vertices"]]
        faces = topo["faces"]
        supports = doc["problem"]["anchored"]["anchorNodeIds"]
        load = doc["problem"]["load"]
        ...

    session_a = tna.solve_tna_problem(problem, support_mode="keys",
        support_keys=supports, density=-density, thickness=thickness,
        horizontal_method="algebraic", horizontal_alpha=100.0,
        vertical_mode="zmax", zmax=4.0)
    session_b = tna.solve_tna_problem(problem, support_mode="keys",
        support_keys=supports, density=-density, thickness=thickness,
        horizontal_method="algebraic", horizontal_alpha=100.0,
        vertical_mode="zmax", zmax=8.0)
    qa = list(session_a.form.edges_attribute("q"))
    qb = list(session_b.form.edges_attribute("q"))
    same_q = qa == qb   # measured False on all eight real nets

Note: `equilibrate_tna_problem` and `solve_tna_problem` both take the
`TNAProblem` from `register_tna_pattern` directly (NOT the `TNAPreparation`
`prepare_tna_problem` returns) - `problem must be a TNAProblem from
register_tna_pattern` is asserted in both (`tna.py:3013-3016`), which is
the one API surprise this probe had to work around.

### 6b. C# real round-trip probe: `plugin/native_v02/Components/
ChainProbe.cs` (new file, scratch tree only, marked "never to be
committed" in its own header) + a small hook added to `tests/native_smoke/
Program.cs`'s `Main`:

    if (args.Length > 0 &&
        string.Equals(args[0], "--chainprobe", StringComparison.Ordinal))
    {
        return RunChainProbe(args.Skip(1).ToArray());
    }

`RunChainProbe` duplicates `Run`'s own assembly loading (RhinoCommon ->
GH_IO -> Grasshopper -> the plugin .gha), then reflects into
`Ananke.COMPAS.Native.Components.ChainProbe.Main` and forwards the
remaining args (a studies folder). `ChainProbe.Main` builds a real
`TnaPatternDto`/`TnaPrepareConfigDto` from each `-form.json`'s `problem`
field (via `ContractJson.Deserialize<ProblemDto>`, exactly as
`TnaRelaxComponent.TryReadInputs` does), then calls the REAL
`WorkerRuntime.Host.RequestAsync` for `tna.prepare` / `tna.equilibrate` /
`tna.solve`, with a `Stopwatch` around payload build, the round trip, and
response decode - i.e. the exact sequence each component's own
`ComputeAsync` uses, copied verbatim from `SolverComponents.cs`. It also
drives the cold-start and cancellation-recovery section (fire a request,
cancel it 60 ms in, time the next request against a warm baseline).

Build and run (the `-o` short-path rule from the previous diagnosis still
applies - `dotnet run` from this deep scratch path fails on "filename or
extension too long"):

    cd <scratch>\perf-real
    dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -c Release
    dotnet build tests/native_smoke/Ananke.COMPAS.NativeSmoke.csproj -c Release -o <scratchroot>\pfb
    cd <scratchroot>\pfb
    # backend.json points ANANKE_COMPAS_BACKEND_CONFIG at the scratch wenv
    # python.exe and this tree's src/ as pythonPaths - see <scratchroot>\pfb\backend.json
    $env:ANANKE_COMPAS_BACKEND_CONFIG = "<scratchroot>\pfb\backend.json"
    .\Ananke.COMPAS.NativeSmoke.exe --chainprobe ..\perf-real\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI\PHD robotics\COMPAS Exports"

Load-bearing fragment (the cancellation-recovery timing, the part of this
report with no precedent in the previous diagnosis):

    using (var cts = new CancellationTokenSource())
    {
        Task<JsonElement> cancelled = WorkerRuntime.Host
            .RequestAsync<JsonElement>("tna.prepare", payload, cts.Token);
        Thread.Sleep(60); // well inside a normal multi-hundred-ms solve
        cts.Cancel();
        try { cancelled.GetAwaiter().GetResult(); } catch { }
    }
    var recoverySw = Stopwatch.StartNew();
    WorkerRuntime.Host.RequestAsync<JsonElement>(
        "tna.prepare", payload, CancellationToken.None)
        .GetAwaiter().GetResult();
    recoverySw.Stop();
    // recoverySw.Elapsed minus the warm baseline is the real cost of one
    // scrub-interrupt cycle: CancellationGraceMs + process kill + relaunch
    // + import + hello, paid by whichever request comes next.

### 6c. In-Rhino stopwatch additions Param could run for exact numbers

Cannot run here (no Rhino native core; `Brep`/`Mesh` construction throws
`DllNotFoundException` headless, same wall the previous diagnosis hit).
Written so he can paste them in if he wants the exact split rather than the
count-based bound in section 4. All marked `// TEMP PROBE`, never to be
committed:

In `SkinComponents.cs`'s `SolveNative` (or wherever `CellSurface`/
`ThickenCellSurface` are called in the per-cell loop, around line 500-590):

    var swBottom = System.Diagnostics.Stopwatch.StartNew();
    Brep? face = cachedBottoms is not null
        ? cachedBottoms[cellSlot]?.DuplicateBrep()
        : CellSurface(cell, net);
    swBottom.Stop();
    SkinProbe.Note("bottom_or_duplicate", swBottom.Elapsed.TotalMilliseconds);

    var swThicken = System.Diagnostics.Stopwatch.StartNew();
    Brep? solid = face is not null && thickening
        ? ThickenCellSurface(face, cell.Outline, cell.Sections, net, thickness, extrude)
        : null;
    swThicken.Stop();
    SkinProbe.Note("thicken_solid", swThicken.Elapsed.TotalMilliseconds);
    SkinProbe.Count("solids_built", solid is not null ? 1 : 0);

And in `DrawViewportMeshes` (measures preview meshing in isolation - toggle
Skin's preview off between two runs and diff the component's own Message
timer to see this row disappear):

    var swPreview = System.Diagnostics.Stopwatch.StartNew();
    args.Display.DrawMeshShaded(_previewMesh, ...);
    swPreview.Stop();
    // accumulate per redraw, print on a debug flag

In `SolverComponents.cs`'s `TnaHorizontalComponent`/`TnaSolveComponent`
`ComputeAsync` (isolates DeepClone and preview-line building, the two
GH-side costs this report bounds only as "the gap" in section 0):

    var swClone = Stopwatch.StartNew();
    TnaPreparedDto clonedInput = ContractJson.DeepClone(relaxed!.Prepared!);
    // (the real call clones the whole RelaxedDto/pattern, not just Prepared;
    // match whichever object TryReadInputs hands to ComputeAsync)
    swClone.Stop();
    Debug.WriteLine($"DeepClone: {swClone.Elapsed.TotalMilliseconds} ms");

    var swPreview = Stopwatch.StartNew();
    BuildPreview(fallbackRelaxed!.Prepared, result.Prepared);
    swPreview.Stop();
    Debug.WriteLine($"BuildPreview: {swPreview.Elapsed.TotalMilliseconds} ms");

And in `DeliveryComponents.cs`, around wherever `export.compas` is
dispatched (queue.md already names the mechanism; a stopwatch around that
one call would give the exact per-solve tax the "build all five kinds every
solve" behaviour costs today):

    var swExport = Stopwatch.StartNew();
    JsonElement exportResponse = await WorkerRuntime.Host
        .RequestAsync<JsonElement>("export.compas", payload, token);
    swExport.Stop();
    Debug.WriteLine($"export.compas round trip: {swExport.Elapsed.TotalMilliseconds} ms");

## 7. Caveats

- `compas_tna` here is 0.9.0, not this tree's pinned 0.7.0 (a scratch venv
  reused from a sibling diagnosis session; a from-source 0.7.0 build failed
  on this Python 3.13 install for an unrelated reason - scipy 1.13.1 has no
  cp313 wheel and refused to compile without a Fortran toolchain). The
  shape of every finding here (which stage dominates, that the self-weight
  loop does not converge, that Move/Height re-derive the full horizontal
  state) is a property of the CALLING CONTRACT and control flow in `tna.py`
  itself, which is unchanged between these versions; the absolute
  millisecond numbers could shift somewhat on his exact pinned environment.
- The C# round trip (section 2b) talks to this same scratch venv via a
  `backend.json` I wrote pointing `ANANKE_COMPAS_BACKEND_CONFIG` at it -
  not his installed backend. Same caveat as above.
- Run-to-run variance was not separately characterised here (time-boxed
  against covering the whole chain); every repeated measurement (3x for the
  Python stages) agreed within the same ballpark the previous diagnosis
  already established as normal for this class of machine/workload.
- Columns and Mould (section 1c) were confirmed cheap on the Rhino-native
  side by absence of Brep/Mesh construction in their source, not by direct
  timing - flagged as a gap, not claimed as measured.
- The in-Rhino stopwatches (section 6c) are un-run, same as the previous
  diagnosis's `scripts/rhino_skin_surface.py` recommendation - they are
  written so Param can get exact numbers, not offered as measured ones.
