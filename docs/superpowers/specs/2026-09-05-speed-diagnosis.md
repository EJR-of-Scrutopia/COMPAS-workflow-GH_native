# Skin pipeline speed diagnosis (profiling only, no fixes)

Date: 2026-09-05. Tree measured: scratch git-archive of cdd85d3 (seam-complete state) at
C:\Users\Param\AppData\Local\Temp\claude\c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui\0df46ca4-9f90-4938-93e9-c6b9ac56b1c1\scratchpad\perf-cdd85d3

Machine: Param's desktop, Release build, .NET 8, headless (no Rhino native core).
All numbers are ms per solve, mean over 5 repeats after a JIT warm run
(run file: scratchpad\pb\probe-run2.txt; a second 7-repeat run, probe-run3.txt,
was taken for variance — see section 7).

## 0. Headline

On a Skin slider move (S, CH, Gaps, Th) Grasshopper re-runs ONLY the Skin
component and what hangs off it (Export, preview). The measured, pure-C#
part of that solve on the six-lobe fixture is:

    SkinNet rebuild (ReadNet)        ~22 ms   (6-lobe, 5640 tris)
    Courses pattern                  ~166 ms
    thickening's pure prelude        ~563 ms  (CornerNormals + MovedSections)
    ---------------------------------------------
    measured pure C#                 ~0.75 s

and on a mesh 2.27x denser (12,780 tris, the more likely density of the
real canvas form):

    SkinNet rebuild                  ~19 ms
    Courses pattern                  ~635 ms
    thickening's pure prelude        ~1,920 ms
    ---------------------------------------------
    measured pure C#                 ~2.6 s

The rest of the observed ~6 s is the part this process cannot run (no
native core): about 21,600 (fixture) to 33,000 (dense) native Brep
constructions + JoinBreps + IsValid/SolidOrientation per solve, the GH
data-tree assembly, Rhino's preview meshing of 650-750 closed solids, and
Export's live build. Those must be split with a stopwatch INSIDE Rhino
(scripts/rhino_skin_surface.py already reaches ThickenCellSurface there).

The single largest MEASURED cost is `SkinPatterns.NormalAt`: a LINEAR SCAN
of every net face per queried point (`FaceUnder`), paid once per cell
corner in `CornerNormals` and then A SECOND TIME for every section-rail
point in `MovedSections`. It is O(corners x faces) and it is 60-75% of the
measured pure time. The second largest is `ResolveBands` re-tracing the
ENTIRE level ladder on every bisection pass (7 passes per solve on every
net with a seam - the depth-6 bisection always runs to its floor there).

## 1. THE SKIN BUDGET (question 1)

Stage names below are the probe marks compiled into `Courses`
(see section 6). `courses.04_resolve_bands` CONTAINS `resolve.trace_all`,
which itself is split into the `trace_all.*` rows; `trace_all.*` also
accumulates the cap pass's re-trace, so the nested rows overlap the
outer ones deliberately.

### 1a. Param's own net (441 vertices, 800 tris, rim 42, 2 seed families)

Loaded from tests/native_smoke/assets/param-crown-arch-contract.json
(1,004 KB of JSON).

    ContractJson.Deserialize<ResultDto>        13.0
    ReadNet (DTO walk + full net build)         4.1
      net.d1_march (RimDistanceFieldWithSeeds)  0.6
      net.d2_march (SecondFamilyField)          1.0
      net.normals (OrientedVertexNormals)       0.03
      net.ctor (whole SkinNet build)            2.0

    scenario                    S 0.17/CH 0.375  S 0.10/CH 0.30  S 0.05/CH 0.15
    cells / courses                  875 / 27       1822 / 33       7256 / 67
    Courses TOTAL                      97.4            51.6           113.8
      01_blend                          0.02            0.02            0.01
      02_seam_curves                    0.9             0.1             0.05
      04_resolve_bands                 52.8            34.9            58.1
        resolve.trace_all              45.8            32.8            54.4
          trace_all.cut                27.5            28.5            45.6
          trace_all.directions         24.5*            7.9            14.6
          trace_all.nesting             0.03            0.04            0.04
          trace_all.seams               1.1             0.4             0.7
      05_cap_pass                       9.7             4.4             6.9
      06_component_ranks                3.4             1.1             1.9
      07_closer_band                    0.3             0.3             0.2
      08_tiling                         9.1             3.7             9.0
      09_sort_plan_filter              20.7             6.7            36.4
      10_diagnostics                    0.5             0.4             1.2
    resolve passes / levels traced      7 / 427         7 / 511         7 / 987
    downstream (pure half of SolveNative):
      cellsurface_prelude               0.07            0.02            0.02
      corner_normals (NormalAt)        36.3            23.4            70.3
      offset_arithmetic                 0.3             0.3             1.1
      moved_sections (rails)           36.6            23.9            71.0
    cell corners                      7,448          12,178          38,954
    Brep-native calls a thickened
    solve would then make            ~16,600         ~28,000         ~92,400

    (* trace_all.directions exceeds its parent slightly in one cell of the
    table because the S 0.17 numbers carry a run-order warm-up wobble;
    see variance, section 7.)

### 1b. Asymmetric six-lobe (2,881 vertices, 5,640 tris, rim 78, 6 seed families)

`SkinLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07)` - the round-two
diagnosis fixture, lifted verbatim from the REAL tree's harness at 31ec98a
(cdd85d3, this scratch tree, does not carry it yet).

    net.d1_march                        3.5
    net.d2_march (6 families!)         19.2
    net.normals                         0.25
    net.ctor (whole SkinNet build)     22.6

    scenario                    S 0.6/CH 0.35   S 0.42/CH 0.245  S 0.30/CH 0.175
    cells / courses / closers      652/16/317      1390/23/503     2607/32/837
    Courses TOTAL                     165.7            280.5           329.3
      01_blend                          0.16             0.05            0.07
      02_seam_curves                    1.2              0.6             0.7
      04_resolve_bands                130.7            217.1           246.9
        resolve.trace_all             111.3            187.1           213.6
          trace_all.cut                64.6            114.9           127.5
          trace_all.directions         19.7             23.1            30.3
          trace_all.nesting             0.03             3.1             3.9
          trace_all.seams              27.0             45.9            52.0
      05_cap_pass                       1.6              1.4             2.6
      06_component_ranks               10.6             15.0            16.6
      07_closer_band                    1.6              4.2             3.8
      08_tiling                         7.0              9.7            15.9
      09_sort_plan_filter              12.1             32.0            41.4
      10_diagnostics                    0.8              0.6             1.5
    resolve passes / levels traced     7 / 343          7 / 587         7 / 705
    downstream (pure half):
      corner_normals (NormalAt)       281.9            482.6           ~721
      moved_sections (rails)          281.2            481.1           ~722
      offset_arithmetic                 0.2              0.5             0.7
    cell corners                     10,140           17,580          26,816
    Brep-native calls next          ~21,600          ~37,900         ~58,800

### 1c. Six-lobe, DENSE MESH (6,481 vertices, 12,780 tris, rim 114, 6 families)

Same form, same S 0.6 / CH 0.35, mesh 2.27x finer - the axis Param's real
canvas mesh sits on.

    net.ctor                           19.3
    Courses TOTAL                     634.8     (cells 735, closers 411, transitions 16)
      04_resolve_bands                336.5
        resolve.trace_all             285.3  (cut 173.9, directions 41.4, seams 65.9, nesting 4.2)
      06_component_ranks               25.3
      09_sort_plan_filter             252.2   <- jumps 20x vs the coarser mesh
      08_tiling                        11.5
    resolve passes / levels traced     7 / 507
    downstream:
      corner_normals                  960.4
      moved_sections                  960.1
    cell corners                     15,769
    Brep-native calls next          ~33,000

### 1d. Scaling read-off

- `corner_normals` is O(corners x faces), measured: 5,640 tris -> 27.8 us
  per corner; 12,780 tris -> 60.9 us per corner (about 5 ns per face
  tested, a pure linear scan). `moved_sections` pays the SAME cost again
  for the section rails (every loft-route cell), so thickening's pure
  prelude is 2 x corners x O(faces). This is the stage that grows
  fastest along BOTH axes (pattern density x mesh density).
- `trace_all.cut` is O(faces x levels x passes): 64.6 -> 173.9 ms for
  2.27x faces at the same S/CH, and grows linearly with the ladder as CH
  shrinks. `resolve.passes` is 7 (= initial + depth-6 bisection) on EVERY
  scenario measured, on both fixtures: any net with a seam bisects to the
  CH/64 floor, so the whole ladder is traced ~5x more than once
  (343 level-traces for a final ladder of ~90 levels on the six-lobe).
- `09_sort_plan_filter` is benign on Param's net (7-36 ms) but 252 ms on
  the dense six-lobe: the degenerate tests (PlanSelfCrosses,
  PlanVertexOnEdge, both O(corners^2) per cell) hit the 411 closer cells,
  whose outlines carry every trace vertex of a dense guide curve.
- `06_component_ranks`, `05_cap_pass`, `07_closer_band`, `08_tiling`,
  blend, seam curves, diagnostics: all second-order (< 30 ms everywhere).
- The blend itself (`01_blend`) is 0.02-0.16 ms - free.
- Net build: d2 (SecondFamilyField) is one EXTRA full march per seed
  family - 19 ms of the six-lobe's 22 ms net build is d2 over 6 families.

### 1e. What could NOT be measured headless

`CellSurface` (loft/fan Breps) and `ThickenCellSurface`'s Brep half throw
DllNotFoundException without Rhino's native core - the harness's own
design (rule 5.2.4 split; ValidateSkinThickenReach depends on it). The
probe counts what a thickened solve would ask of the native core:
per cell, one bottom (loft of ~2 rails, or a fan of N corner-point Breps
+ JoinBreps), one top (same again), N wall quads (CreateFromCornerPoints),
one JoinBreps over N+2 pieces, IsValid, SolidOrientation, possibly a
Flip - ~21,600 native constructions at the six-lobe's canonical setting,
~33,000 on the dense mesh, ~92,400 at Param's densest crown-arch setting.
At a conservative 0.05-0.15 ms per native construction+join amortised,
that bounds the Rhino-only share at roughly 1-5 s, which brackets the
observed 6 s once preview meshing of hundreds of closed solids and GH
tree assembly are added. Split it in Rhino with stopwatches in
SolveNative around CellSurface / ThickenCellSurface / SetDataTree (the
component builds in the scratch tree; scripts/rhino_skin_surface.py is
the in-Rhino harness that already reaches these methods).

Also unmeasured: Export downstream of Skin. Its file write is gated on
the Write button, but with Live enabled each Skin change rebuilds and
debounces an upload, and its thrust-mesh goes through a worker
`export.compas` round trip. Worth a stopwatch in Rhino too.

## 2. REDUNDANT WORK (question 2)

Read from SkinComponents.cs SolveNative (line ~297) and SkinPatterns.cs.
There is NO caching anywhere in the skin path: every SolveInstance does
ReadNet (which rebuilds triangulation + d1 march + d2 marches + normals),
the full pattern, and every Brep from scratch.

What each input ACTUALLY determines:

- The net (triangulation, d1, d2, seed groups, vertex normals) depends
  ONLY on the Result. Not on S, CH, MP, Th, Gaps.
- The BLEND depends on net + CH (radius defaults to one Course Height) -
  but it is 0.02-0.16 ms.
- Seam curves depend only on the net.
- The ladder, tracing, bands, cap pass depend on net + CH (+ S and MP
  only through the cap's maximum-piece split levels).
- Tiling, closer, merge, sort, plan filter depend on net + S + CH + MP.
- CellSurface (bottom Breps) depends on the cells alone - not Th, not Gaps.
- Thickening depends on cells + Th + Gaps.

Dependency table - stages that MUST rerun vs what reruns TODAY (all of it):

    input moved   must rerun                                        reruns today
    ------------  ------------------------------------------------  ------------
    Result        everything                                        everything
    CH            blend, ladder, resolve, cap, tiling, closer,      + ReadNet /
                  sort/filter, surfaces, thicken                    net rebuild
    S             cap split levels, tiling, merge, closer pitch,    + ReadNet, blend,
                  sort/filter, surfaces, thicken                    seams, resolve (full)
    MP            cap plans, merge, closer, sort/filter, surfaces,  + everything
                  thicken
    Th            thicken ONLY (bottom faces, cells, pattern all    + everything
                  unchanged; Th=0 fast path proves the seam)
    Gaps          thicken ONLY (ignored while Th=0)                 + everything

So a Gaps or Th slider drag - the exact gesture Param described - today
pays ReadNet + Courses + all bottom Breps again for stages whose inputs
did not move. On the dense six-lobe that is ~650 ms of measured pure C#
plus roughly half of the native Brep work (bottoms + pattern-driven
curves) that could be keyed away, per tick of the drag.

An S move similarly re-pays the net build and nearly all of
resolve_bands (the ladder depends on CH; S only inserts the cap's two
levels), i.e. ~350 ms of the dense solve's 635 ms Courses time.

Keying: the ResultDto reference (or its TopologyHash + solve stamp)
identifies the net; (net, S, CH, MP) identifies the pattern;
(pattern, Th, Gaps) identifies the thickening. All three are pure
functions of those keys - the code states as much throughout.

## 3. THE WORKER SIDE (question 3)

The real worker (ananke_equilibrium.worker over framed JSON pipes) was
not launched here; the numbers below are the module driven directly, in
a scratch venv (python 3.13, compas 2.15.1, compas_tna 0.9.0), through
the same tree_forest_compas.tna entry points the worker dispatches to
(tna.prepare / tna.equilibrate / tna.solve). Script: scratchpad\worker_probe.py.

Six-lobe plan, vertices+faces registration, boundary supports:

    mesh                     721 v / 720 f      2881 v / 2880 f
    register                     10.8 ms             52.0 ms
    prepare (relax)              37.6 ms            152.3 ms
    equilibrate (move 100)    1,415.7 ms          7,880.8 ms
    solve (horiz iterative
      kmax 100 + vertical)       244.0 ms           992.6 ms
    solve (horiz ALGEBRAIC
      + vertical)                340.6 ms          1,723.5 ms

    worker cold start: import compas+compas_tna ~130 ms
    (tree_forest_compas first-import ~600 ms; the worker process is
    persistent, so this is once per session, not per solve)

Notes:
- These stages are UPSTREAM of Skin: a Skin/Th/Gaps slider move does NOT
  re-enter the worker. They matter for Relax/Horizontal/Solve slider
  moves, where TNA Horizontal at canvas mesh density is ~8 s by itself.
- The roadmap's "direct linear horizontal solve" already exists as
  horizontal_method="algebraic"; measured SLOWER than the iterative path
  at these sizes when the plan is already near equilibrium (1.72 s vs
  0.99 s at 2,881 vertices). Its value is bounded-error, not speed; it is
  not the cheap win.
- THE WIRE (the orjson idea), measured on the 1,004 KB
  param-crown-arch-contract.json: python json.loads 9.0 ms / json.dumps
  9.5 ms; orjson 4.1 / 1.4 ms; C# ContractJson.Deserialize 13.0 ms.
  Total possible saving per exchange ~13 ms - NEGLIGIBLE against the
  6 s. orjson is not worth its dependency for this problem.

## 4. CHEAP WINS, RANKED (question 4)

Ranked by measured impact on the slider-move gesture, quality identical.

1. SPATIAL INDEX FOR FaceUnder/FaceFor (NormalAt, LevelAt, LiftPlanPoint).
   Cost today: corner_normals + moved_sections = 563 ms (six-lobe) to
   1,920 ms (dense mesh) per solve, plus FaceUnder work hidden in the
   cap pass and tiling. A uniform plan grid over triangle bboxes (built
   once per net, ~1 ms) turns 28-61 us per query into <1 us.
   Expected saving: ~0.5 s (fixture) to ~1.9 s (dense) per solve - the
   largest single measured cut, and it also shrinks with cut 2.
   Bit-identity: ACHIEVABLE BY CONSTRUCTION - FaceUnder returns the
   LOWEST-INDEXED face containing the point; iterate grid candidates in
   ascending face index and keep the exact same containment test, and
   keep the nearest-centroid fallback scanning ALL faces with strict `<`
   (lowest index wins ties). Same answers, but re-run the NormalAt/LevelAt
   SHA pin (86F5A147...) and the blended-field pins as due diligence.

2. CACHE THE PATTERN ACROSS Th/Gaps MOVES (and the bottom Breps with it).
   Cost today: a Th or Gaps tick re-runs ReadNet + Courses + bottom
   surfaces: measured pure C# 188 ms (six-lobe) / 654 ms (dense) plus
   roughly half the native Brep work. Key: (Result identity, pattern id,
   S, CH, MP) -> SkinPatternResult + per-cell bottom Breps (duplicated on
   handout, since JoinBreps consumes its inputs).
   Expected saving: the whole Courses + CellSurface share of a Th/Gaps
   drag - likely 2-3 s of the observed 6 s on the real canvas.
   Bit-identity: BY CONSTRUCTION (the same objects are handed back; the
   Th=0 "same Brep reference" ruling already proves the pattern is
   Th-independent).

3. CACHE THE SkinNet ACROSS ALL SKIN SLIDER MOVES.
   Cost today: ReadNet rebuilds triangulation + d1 + d2 (one march per
   seed family!) + normals on every solve: 4.1 ms (Param's net), 22.6 ms
   (six-lobe), 19.3 ms (dense; d2 is 6 extra marches = 16-19 ms of it).
   Key: ResultDto reference equality (the goo holds the same DTO between
   solves) with TopologyHash as fallback. Also the precondition for cut 2.
   Expected saving: ~20 ms per move plus enabling 2.
   Bit-identity: BY CONSTRUCTION - same object, no arithmetic.

4. STOP RE-TRACING THE WHOLE LADDER EVERY BISECTION PASS (ResolveBands).
   Cost today: 7 passes per solve on every seamed net; ~5x redundant
   level tracing (343 traces for a ~90-level ladder). trace_all totals
   111 ms (six-lobe) / 285 ms (dense), of which cut alone is 65/174 ms.
   Memoise `Trace(net, level)` results per level across passes (the cut
   is per-level independent); AssignNestingDepths / NormaliseDirections /
   AssignSeams still run over the full list each pass (they are the
   bottom-up invariant rule 8.2.9 protects).
   Expected saving: ~80 ms (fixture) to ~230 ms (dense) per solve.
   Bit-identity: NEEDS CARE + RE-PINNING - NormaliseDirections and
   AssignSeams MUTATE the traced curves in place (Reverse, Seam, Depth),
   so the memo must hand back pristine copies (or re-Finish clones); the
   final state is deterministic, so values should be identical, but this
   one must be proven against the R=0 pins and the seam fixtures, not
   argued.

5. PRUNE THE DEGENERATE TESTS IN KeepValidPlans FOR CLOSER-HEAVY SOLVES.
   Cost today: 09_sort_plan_filter is 12-41 ms normally but 252 ms on
   the dense six-lobe (16 transitions, 411 closers): PlanSelfCrosses and
   PlanVertexOnEdge are O(corners^2) per cell and closer outlines carry
   every vertex of a dense guide curve. A sweep-line or bbox-bucketed
   segment-pair prune inside those two predicates (or a coarse
   bounding-box early-out per segment pair) preserves exact answers.
   Expected saving: ~200 ms on dense seamed solves; ~0 elsewhere.
   Bit-identity: BY CONSTRUCTION if the prune only skips pairs whose
   bboxes cannot intersect (the predicate's answer is unchanged); the
   cell order and first-kept-wins semantics stay untouched.

Not ranked but flagged for the in-Rhino follow-up: (a) the native Brep
half itself (the biggest absolute block of the 6 s - if JoinBreps
dominates, building each cell's shell as one Brep via a single loft with
caps, or deferring IsValid, would need a quality ruling, so it is NOT
claimed here); (b) preview meshing - toggling Skin's preview off during
drags costs nothing and would isolate its share immediately; (c) Export
Live's per-change rebuild + worker round trip.

The rejected axes (GPU, multicore) were respected: every cut above is
single-threaded and allocation-light.

## 5. Where the 6 seconds go (best supported split)

For a six-lobe-class form at canvas density (nearer the 12.8k-tri dense
fixture than the 5.6k one), per Skin slider move:

    ~0.02 s  net rebuild (ReadNet)                       [measured]
    ~0.6 s   Courses pattern                             [measured]
    ~1.9 s   NormalAt walks in thickening's pure half    [measured]
    ~2-4 s   native Brep construction + joins + preview  [bounded, not split:
             + GH tree + Export live                      needs in-Rhino stopwatch]

Cuts 1-3 above remove the first three rows almost entirely for Th/Gaps
moves (~2.5 s measured) and cut the S/CH move cost roughly in half;
the remaining seconds live in Rhino native code and must be measured
there next.

## 6. The probe machinery (lift-ready)

All instrumentation lives in the scratch tree only. Build and run:

    cd <scratch>\perf-cdd85d3
    dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -c Release
    dotnet build tests/native_smoke/Ananke.COMPAS.NativeSmoke.csproj -c Release -o <scratchroot>\pb
    cd <scratchroot>\pb
    .\Ananke.COMPAS.NativeSmoke.exe --probe ..\perf-cdd85d3\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha 5

(The -o short path avoids the "filename or extension too long" trap.)

### 6a. New file: plugin/native_v02/Components/SkinProbe.cs

    // TEMPORARY PROFILING INSTRUMENTATION - never to be committed.
    using System;
    using System.Collections.Generic;
    using System.Diagnostics;
    using System.Globalization;
    using System.Linq;
    using System.Text;

    namespace Ananke.COMPAS.Native.Components;

    internal static class SkinProbe
    {
        public static bool Enabled;
        public static readonly Dictionary<string, double> Milliseconds =
            new(StringComparer.Ordinal);
        public static readonly Dictionary<string, long> Counters =
            new(StringComparer.Ordinal);

        public static void Reset()
        {
            Milliseconds.Clear();
            Counters.Clear();
        }

        public static long Tick() => Enabled ? Stopwatch.GetTimestamp() : 0L;

        public static void Note(string stage, ref long tick)
        {
            if (!Enabled) return;
            long now = Stopwatch.GetTimestamp();
            double ms = (now - tick) * 1000.0 / Stopwatch.Frequency;
            Milliseconds[stage] =
                Milliseconds.TryGetValue(stage, out double have) ? have + ms : ms;
            tick = now;
        }

        public static void Count(string counter, long add = 1)
        {
            if (!Enabled) return;
            Counters[counter] =
                Counters.TryGetValue(counter, out long have) ? have + add : add;
        }

        public static string Dump(int divide = 1)
        {
            var text = new StringBuilder();
            foreach (var stage in Milliseconds.OrderBy(p => p.Key, StringComparer.Ordinal))
                text.AppendLine(string.Format(CultureInfo.InvariantCulture,
                    "    {0,-34} {1,10:F2} ms", stage.Key,
                    stage.Value / Math.Max(1, divide)));
            foreach (var counter in Counters.OrderBy(p => p.Key, StringComparer.Ordinal))
                text.AppendLine(string.Format(CultureInfo.InvariantCulture,
                    "    {0,-34} {1,10} (count over all reps)",
                    counter.Key, counter.Value));
            return text.ToString();
        }
    }

### 6b. Marks inserted in SkinPatterns.cs (all tagged `// TEMP PROBE`)

In `Courses(net, size, courseHeight, minPiece)` (the 4-arg overload), a
single running tick partitions the body:

    long __probe = SkinProbe.Tick();                    // after RequireSizes
    net = Blended(net, courseHeight);
    SkinProbe.Note("courses.01_blend", ref __probe);
    ... SeamCurves(net);
    SkinProbe.Note("courses.02_seam_curves", ref __probe);
    ... (ladder built)
    SkinProbe.Note("courses.03_ladder", ref __probe);
    SkinBandResolution resolved = ResolveBands(net, levels, intervals);
    SkinProbe.Note("courses.04_resolve_bands", ref __probe);
    SkinProbe.Count("courses.bands", bands);
    ... (cap pass, incl. its re-trace)
    SkinProbe.Note("courses.05_cap_pass", ref __probe);  // before levelIndex
    ... ComponentRanks(...);
    SkinProbe.Note("courses.06_component_ranks", ref __probe);
    ... (absorb loop + CloserBand loop over slabs)
    SkinProbe.Note("courses.07_closer_band", ref __probe); // before transitionBands
    ... (tiling foreach over tileable)
    SkinProbe.Note("courses.08_tiling", ref __probe);    // before KeepValidPlans
    List<SkinCell> cells = KeepValidPlans(...);
    SkinProbe.Note("courses.09_sort_plan_filter", ref __probe);
    SkinProbe.Count("courses.cells_kept", cells.Count);
    SkinProbe.Count("courses.cells_keyed", keyed.Count);
    SkinPatternResult __result = new SkinPatternResult(...) { ... }; // was: return new
    SkinProbe.Note("courses.10_diagnostics", ref __probe);
    return __result;

In `ResolveBands`, around the per-pass trace:

    long __rb = SkinProbe.Tick();
    traced = TraceAll(net, levels);
    SkinProbe.Note("resolve.trace_all", ref __rb);
    SkinProbe.Count("resolve.passes");
    SkinProbe.Count("resolve.levels_traced", levels.Count);

In `TraceAll`:

    long __ta = SkinProbe.Tick();
    foreach (double level in levels) working.Add(Trace(net, level));
    SkinProbe.Note("trace_all.cut", ref __ta);
    AssignNestingDepths(working);
    SkinProbe.Note("trace_all.nesting", ref __ta);
    NormaliseDirections(working);
    SkinProbe.Note("trace_all.directions", ref __ta);
    AssignSeams(working);
    SkinProbe.Note("trace_all.seams", ref __ta);

### 6c. New file: plugin/native_v02/Components/PerfProbe.cs

The full driver (fixtures, net-build split, scenario runner, downstream
emulation, and the lobed fixture builder lifted from the real tree's
harness at 31ec98a). Verbatim copy of the scratch file - lift as-is:

    (see <scratch>\perf-cdd85d3\plugin\native_v02\Components\PerfProbe.cs;
    the load-bearing pieces:)

    // scenario runner
    SkinProbe.Enabled = false;
    SkinPatternResult made = SkinPatterns.Courses(net, size, ch, minPiece); // warm
    SkinProbe.Enabled = true; SkinProbe.Reset();
    var swTotal = Stopwatch.StartNew();
    for (int i = 0; i < repeats; i++)
        made = SkinPatterns.Courses(net, size, ch, minPiece);
    swTotal.Stop(); SkinProbe.Enabled = false;
    // print swTotal/repeats + SkinProbe.Dump(repeats)

    // net-build split (public statics, run per stage)
    SkinPatterns.Triangulate(vertices, faces);
    (var levels, var seeds) = SkinPatterns.RimDistanceFieldWithSeeds(vertices, tri, rim);
    SkinPatterns.SecondFamilyField(vertices, tri, rim, seeds);
    SkinPatterns.OrientedVertexNormals(vertices, tri);
    new SkinNet(vertices, faces, rim, Array.Empty<SkinNetEdge>());

    // downstream pure emulation, per cell of `made`
    if (!SkinComponent.TopTakesLoft(cell.Sections)) {
        double[]? inside = SkinPatterns.PlanInteriorPoint(cell.Outline);
        if (inside is not null) SkinPatterns.LiftPlanPoint(net, inside[0], inside[1]);
    }
    var normals = SkinComponent.CornerNormals(net, cell.Outline);      // <- NormalAt walks
    double[] cellNormal = SkinComponent.CellNormalFrom(cell.Outline, normals);
    SkinComponent.OffsetPointsFrom(cell.Outline, normals, cellNormal, th, gaps);
    SkinComponent.MovedSections(net, cell.Sections, cellNormal, th, gaps); // <- walks again

    // Param's net
    ResultDto result = ContractJson.Deserialize<ResultDto>(File.ReadAllText(assetPath));
    SkinNet net = SkinPatterns.ReadNet(result)!;

    // six-lobe fixture (from the real tree's harness at 31ec98a)
    SkinLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07)   // round-two fixture
    SkinLobedNet(6, 180, 36, 5.0, 0.22, 3.0, 19, 0.10, 0.07)   // dense-mesh variant

### 6d. Harness hook (tests/native_smoke/Program.cs, top of Main)

    if (args.Length > 1 && string.Equals(args[0], "--probe", StringComparison.Ordinal))
        return RunPerfProbe(args.Skip(1).ToArray());

`RunPerfProbe` duplicates Run's assembly loading (ResolveRhinoRoot ->
RhinoCommon/GH_IO/Grasshopper -> plugin), then reflects
`Ananke.COMPAS.Native.Components.PerfProbe.Main`, prepending the
harness's own assets/param-crown-arch-contract.json path.

### 6e. Worker probe (scratchroot\worker_probe.py)

Times register / prepare / equilibrate / solve on the six-lobe plan at
two densities through tree_forest_compas.tna, plus stdlib-vs-orjson wire
cost on the 1 MB contract. Venv: scratchroot\wenv (compas 2.15.1,
compas_tna 0.9.0, orjson). Note the triangle-fan winding must OPPOSE the
quad ring's shared edge or register_tna_pattern refuses the mesh.

## 7. Caveats

- Run-to-run variance on the SMALL scenarios is up to 2x (heap state and
  desktop noise; this box's OneDrive sync was live): Param's S 0.10
  scenario read 122 / 52 / 43 ms Courses total across the three runs.
  The LARGE scenarios were stable within ~2-10% across all three runs
  (six-lobe canonical 165.7 vs 163.3 ms; dense 634.8 vs 640.5 ms;
  corner_normals dense 960.4 vs 957.0 ms), and every ranking above
  survives the variance. probe-run1/2/3.txt in scratchroot\pb hold the
  raw runs (3, 5 and 7 repeats).
- The full smoke suite was run against the instrumented build (probes
  compiled in, Enabled=false): "Native component smoke test passed;
  Rhino was not launched", exit 0, with only the pre-existing DEFER
  entry (the coarse-net foot convergence deferral). The instrumentation
  is inert when off. See scratchroot\pb\suite-run.txt.
- The six-lobe fixture is 5,640 tris; Param's canvas mesh density is
  unknown. The dense variant (12,780 tris) shows every leading cost is
  at least linear in face count, so the real numbers likely sit at or
  beyond the dense column.
- The Rhino-native half is bounded, not split. First action for the
  speed implementer after the caches: stopwatch SolveNative inside Rhino
  (CellSurface vs ThickenCellSurface vs SetDataTree vs preview) on the
  real definition.
