# Round-two diagnosis: gaps, flat stones, and the cap, measured on lobed multi-seam fixtures

Diagnosis-only report for the round-two fix wave, against commit 8b9a44a (the blended
field and full-width seam stones). Scope is the three findings in
`docs/superpowers/specs/2026-09-05-seam-flow-round-two-findings.md` (main tree). Everything
below was MEASURED, not argued: `SkinPatterns.cs` was compiled into a standalone probe
(typed access to the engine's internals, no reflection, no Rhino) and run over three lobed
multi-anchor fixtures. All file:line references are to the PRISTINE 8b9a44a scratch copy at
`C:\Users\Param\AppData\Local\Temp\claude\c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui\0df46ca4-9f90-4938-93e9-c6b9ac56b1c1\scratchpad\seam-8b9a44a`
(line numbers taken before the probe's temporary hooks were inserted; the hooks are fenced
`TEMPORARY DIAGNOSTIC PROBE ... NEVER MERGE` and are disposable).

Raw probe outputs (full numbers behind every claim here):

- `...\scratchpad\probe-6lobe.txt` (symmetric six-lobe)
- `...\scratchpad\probe-6lobe-asym.txt` (asymmetric six-lobe, the one that reproduces his screenshots)
- `...\scratchpad\probe-3lobe.txt` (three-lobe control)

## The fixture

A paraboloid dome (rise 3 m) over a flower plan `r(theta) = 5 (1 + 0.22 cos(6 theta))`,
120 angular x 24 radial quads, with the rim anchored in SIX SEPARATE ARCS of 13 boundary
columns each (free-edge openings of 7 columns between them), so `BuildNet`'s marching sees
six seed groups and recovers 5 seam curves. `S = 0.6`, `CH = 0.35`, `MP = 1/3` (defaults).
Field range 5.63 m = 16.1 course heights. The asymmetric variant adds
`+ 0.10 cos(theta + 0.7) + 0.07 sin(2 theta + 1.3)` to the radius so the six merges happen
at DIFFERENT heights, which is what a real (non-ideal) six-lobe does; the symmetric variant
merges all six seams in one band. The three-lobe control is the same generator with
`lobes = 3`.

```csharp
// tests/native_smoke would host this as a fixture builder; the probe carries it verbatim.
internal static (double[][] V, int[][] F, int[] Rim) LobedNet(
    int lobes, int n, int m, double r0, double amp, double h, int rimCols,
    double asym1 = 0.0, double asym2 = 0.0)
{
    var vertices = new List<double[]> { new[] { 0.0, 0.0, h } };
    for (int t = 1; t <= m; t++)
    {
        double fraction = (double)t / m;
        double z = h * (1.0 - fraction * fraction);
        for (int i = 0; i < n; i++)
        {
            double theta = 2.0 * Math.PI * i / n;
            double rMax = r0 * (1.0 + amp * Math.Cos(lobes * theta) +
                asym1 * Math.Cos(theta + 0.7) +
                asym2 * Math.Sin(2.0 * theta + 1.3));
            double rho = rMax * fraction;
            vertices.Add(new[] { rho * Math.Cos(theta), rho * Math.Sin(theta), z });
        }
    }
    int Idx(int t, int i) => 1 + (t - 1) * n + ((i % n) + n) % n;
    var faces = new List<int[]>();
    for (int i = 0; i < n; i++)
        faces.Add(new[] { 0, Idx(1, i), Idx(1, i + 1) });
    for (int t = 1; t < m; t++)
        for (int i = 0; i < n; i++)
            faces.Add(new[] { Idx(t, i), Idx(t, i + 1), Idx(t + 1, i + 1), Idx(t + 1, i) });
    var rim = new List<int>();
    int perLobe = n / lobes;
    int half = (rimCols - 1) / 2;
    for (int k = 0; k < lobes; k++)
    {
        int centre = k * perLobe;
        for (int d = -half; d <= half; d++)
            rim.Add(Idx(m, centre + d));
    }
    return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
}
// Six-lobe:      LobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13);
// Six-lobe asym: LobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07);
// Three-lobe:    LobedNet(3, 120, 24, 5.0, 0.22, 3.0, 25);
// var net = new SkinNet(v, f, rim, Array.Empty<SkinNetEdge>());
// var result = SkinPatterns.Courses(net, 0.6, 0.35);
```

Headline numbers per fixture:

| fixture | cells | refusals (pre-absorb) | slabs (post-absorb) | closers | plan drops | void area | tiny cells |
|---|---|---|---|---|---|---|---|
| six-lobe symmetric | 564 | 1 (course 3, CH/64) | 1 x 1.00 CH | 60 | 0 | 0.25 m2 (0.31%) | 0 |
| six-lobe asym | 653 | 5 (courses 2-3, CH/64 each) | 1.91 / 0.23 / 0.05 / 0.16 / 1.66 CH | 318 | 2 (1 self-cross, 1 overlap) | 2.78 m2 (3.4%) | 199 of 653 |
| three-lobe | 525 | 1 (course 5) | 1 x 1.00 CH | 54 | 0 | 0.21 m2 (0.26%) | 0 |

The asymmetric six-lobe is the class of form he photographed, and it reproduces every
symptom: stone-sized rectangular voids several per lobe, rows of sliver stones, one
full missing stone (the whole crown), all with mechanisms attributable below.

---

## Finding 1: gaps and tiny pieces — four owners, each measured

The findings doc names three candidate mechanisms (a) refusals no closer serves,
(b) absorb stopping short, (c) plan-filter drops. All three are real, plus a fourth the
absorb rule creates itself. Ownership by void class:

### 1a. Guide pinch-out voids (the "rectangular voids, several per lobe")

**Owner: the closer band's boundary construction, `CloserBand`,
`plugin/native_v02/Components/SkinPatterns.cs:6213-6376`, specifically the stated
"pinch-out price" at 6166-6180.** The closer covers a refused slab by dividing the GUIDE
family's level curves at pitch and closing each span back along the nearest curve of the
other family. Where a guide curve ENDS (on the free boundary over an opening, or short of
the seam meeting point), the region beyond its last head joint has no guide and gets no
stone. The doc comment already names this price; the measurement says it is the dominant
hole class on a lobed form.

Measured (void classification by grid sampling at 7.5 cm, classified against the probe's
slab/band records):

- Symmetric six-lobe: six voids of 0.034-0.045 m2, one per seam, centred ON the seam
  curves (plan distance to nearest seam 0.05-0.12 m), field values inside the slab
  [1.05, 1.40]. Total 0.25 m2. A course stone here is ~0.14 m2 in plan, so each hole is a
  third of a stone.
- Three-lobe: three voids ~0.07 m2, one per seam, same signature (seamDist 0.04-0.10).
- Asymmetric six-lobe: TWELVE voids of 0.14-0.19 m2 each (a full stone and more), two per
  free-edge opening, field values spanning nearly the whole of the over-absorbed
  [0.35, 1.017] slab (see 1b'). Total A-class 2.12 m2.

Two sub-cases, same owner: at a seam tip the guide stops just short of the meeting point
(small triangular void, the symmetric case); when the slab has been absorbed DOWN to a
level whose curves end on the free boundary, the whole ribbon over each opening between
two guides' ends is unserved (stone-sized quads, the asymmetric case). The alternative
suspects were acquitted by measurement: `CloserRefused = 0` and `CloserUndersized = 0` on
every run (no stone was refused into a hole), and the per-stone nearest-other-curve choice
never switched mid-guide (probe's handoff counter: 0 switches on all three fixtures), so
the pair-of-pants handoff is NOT the void maker here.

### 1b. Absorb stopping short of one CH (the pinstripe rows)

**Owner: the absorb loop `SkinPatterns.cs:3957-4009`, whose candidate list is
`tileable` bands only, searched for a band that abuts the slab EXACTLY
(`Math.Abs(band.High - lo) <= 1e-12`, lines 3977-3980), with `break` when neither side
abuts (3982-3983).** Two ways it starves, both measured on the asymmetric six-lobe, where
five CH/64 refusals land in two adjacent courses:

- A refusal's neighbour interval is ANOTHER refusal, which is never in `tileable`, so
  there is nothing to absorb on that side.
- The refusals are processed in list order against ONE shared `tileable` list
  (`tileable.RemoveAt(take)`, line 4006), so the first slab eats the bands the later ones
  needed. First-come stealing.

Measured slabs: `[1.0172, 1.0992] = 0.23 CH`, `[1.0992, 1.1156] = 0.05 CH`,
`[1.1156, 1.1703] = 0.16 CH` — three slabs far short of a course height, wedged between
the two fat slabs that ate everything else. Consequence: those slabs' closer stones are
full pitch LONG (span 0.28-0.63 m, so `MergeShortPieces` and the `CloserUndersized`
counter both see nothing wrong) but ribbon-THIN across: plan areas from 0.0026 m2, medians
0.006-0.018 m2 against the ordinary course median of 0.156 m2. 199 of 653 cells (30 per
cent) are under 30 per cent of median course area, every one a closer in those thin slabs.
This is Param's "rows of tiny pieces" at reduced scale: the pinstripe reborn one level up,
in the closer band instead of the course band. Note for the fix: `CloserUndersized`
measures only the along-seam span (rule 2.4's bound, line 6357-6358), so it is
STRUCTURALLY BLIND to this defect — it read 0 while a third of the pattern shipped as
slivers. The across-course dimension is the one that needs a floor.

### 1b'. Absorb overshooting (whole-band bites), which feeds 1a

**Owner: the same absorb loop — "whole tileable bands, and only whole ones" (comment at
3930-3936, bite at 4001-4006).** The first asymmetric refusal `[1.0117, 1.0172]` had only
downward neighbours; the bisected siblings below it sum to 0.31 CH (still short), so the
loop's next bite was the ENTIRE course-1 band `[0.35, 0.70]`, landing the slab at
`[0.35, 1.0172]` = 1.91 CH. That slab's guide family is the level-0.35 curves, whose strips
end on the free boundary over every opening — which is exactly where the twelve
stone-sized 1a voids sit. The overshoot also makes the flattest stones in the whole
pattern (see finding 2). So over-absorb and under-absorb are one defect with two faces:
the bite granularity is whole bands, while the need is "grow to >= 1 CH, no further, and
share fairly between adjacent refusals".

### 1c. Plan-filter drops (the full missing stone)

**Owner: `KeepValidPlans` (call at 4387-4399) plus the depth gate on the seam-band rescue
at 4302 (`if (folded && band.Depth > 0)`).** Measured on the asymmetric six-lobe: exactly
2 cells dropped, both at the crown, jointly opening a 0.66 m2 hole (the C-class void
cluster at plan centre, field [4.91, 5.50]):

- a course-14 cell whose plan SELF-CROSSES (dropped as plan-degenerate). Its band's upper
  boundary is the wiggly crown loop at 5.25; the proportional arc map folds there. The
  nearest-point rescue of rule 2.5 exists for precisely this fold but is gated to
  `band.Depth > 0` (bisected bands only) — course 14 is depth 0, so the rescue never ran.
- the crown CAP itself (girth 3.69 m, emitted whole+oversized), dropped as plan-OVERLAP:
  the kept course-14 neighbour of that folded cell overreaches in plan into the crown loop,
  the cap sorts after course 14, and the filter keeps the first of the pair. The probe
  confirmed the single kept collider by re-running `PlansOverlapWithInteriors` over the
  kept set. Result: `emitted cap cells: 0` — the crown ships OPEN. On a six-lobe class
  form the "one full missing stone in the close-up" is this chain, or a 1a void.

### What the fix must do (finding 1)

Grounded in the numbers above, a fix that closes his acceptance ("closed, and closing
stones inside the adjacent courses' size range, no tiny fill-in pieces anywhere") must:

1. COALESCE adjacent/overlapping refusals before absorbing: the five CH/64 refusals in
   courses 2-3 are one topological event (the six seams merging in sequence) and should
   become ONE slab, not five competing ones. That alone removes the three thin slabs and
   their 199 pinstripes.
2. Absorb with sub-band granularity to a target of ~1 CH (the bisection has already traced
   levels the absorb can stop at: the level list carries them), instead of whole-band bites
   that measured 1.91 CH. That directly shrinks the 1a voids (the guide family stays near
   the merge, where its curves still run the full ribbon) and caps the closer stones' sag.
3. Close the guide pinch-outs: after laying the closer stones, the residual regions of a
   slab (beyond each guide's last head joint — at seam tips and over openings) need either
   an end-stone cut against the two families' own ends (the construction the CloserBand doc
   comment already sketches at 6177-6180) or an explicit residual-coverage pass. Check 2's
   plan-area coverage fraction is the right acceptance instrument; it measured 96.56 per
   cent on the asymmetric fixture and must be pinned near 100 with a stone-size floor.
4. Un-gate or widen the rule-2.5 nearest-point rescue so a depth-0 band whose cells fold
   (measured: course 14 against the crown loop) gets the same rescue as a bisected band —
   that removes the self-cross drop AND the overlap cascade that killed the cap.

## Finding 2: flat low stones — the engine's cells are NOT flat at level height; the deviants are the thick-slab closers, and the Rhino-side fallback

The findings doc's check ("every emitted cell's top-face corner heights sit within
tolerance of the thickened surface at those plan points") was run in engine terms: for
every emitted cell, every OUTLINE CORNER was compared against the net surface lifted at
that plan point. Worst corner deviation across all cells, all fixtures: **0.0000 m**.
Corners are exact on every route, because every outline point is a traced level-curve
point and the fan apex is `LiftPlanPoint`-ed onto the net (`CellSurface`,
`plugin/native_v02/Components/SkinComponents.cs:913-941`). Two consequences:

- The suspect "the sectionless-cell fan route drawing at level height" is ACQUITTED as
  worded: no route draws at constant height; fan cells interpolate the surface at their
  apex and rim exactly.
- The acceptance check as written in the findings doc would go GREEN on today's build.
  To catch what Param photographed it must sample cell INTERIORS (mid-face), and/or assert
  the component-side slot (below), not corners.

What IS measurably low is the mid-face of cells that chord across too much surface.
Interior sampling (ruled-surface points for loft cells, fan-triangle points for fan cells,
against the lifted net):

| route | built at | n (asym) | max deficit | p90 | median |
|---|---|---|---|---|---|
| closer-loft | SkinPatterns.cs:6359-6372 (sections route (a)) | 318 | **0.0353 m** | 0.0253 | 0.0012 |
| course-loft | BandCell, SkinPatterns.cs:6466-6492 | 335 | 0.0139 | 0.0092 | 0.0046 |
| cap-wedge-loft | ring BandCell, SkinPatterns.cs:4199-4215 | 2 (sym) | 0.0024 | — | — |
| cap-fan (whole/disc) | CellSurface fan, SkinComponents.cs:917-941 | 1 (sym) | 0.0007 | — | — |

The worst closers all sit on the 1.91 CH over-absorbed slab (asym course 2); on the
symmetric fixture's exactly-1.00 CH slab the closer max is 0.0143 m against the ordinary
course p90 of 0.0101. The deficit is a chord sag: proportional to local curvature times
the square of the across-stone width, so a closer spanning ~2 CH sags ~4x an ordinary
stone, and on his real vault (tighter curvature in the seam valleys than this paraboloid)
the same 2-CH closers plausibly sag several centimetres — a visibly flat, low, full-width
stone in a row along the seam, exactly where his screenshots show the flat plates. The
route that produces the deviants is therefore the CLOSER ROUTE ON ABSORBED MULTI-CH SLABS,
not a missing thickening path: 8b9a44a's closers DO carry `Sections` and go through the
standard loft top (`ThickenCellSurface` lofts moved rails, SkinComponents.cs:1371-1377),
which the probe confirmed by route inventory (every non-cap cell carries two rails; zero
rails under 2 points, zero zero-length rails, zero sub-1e-6 duplicate corners across all
three fixtures — the degeneracy audit is in the outputs).

The second, Rhino-side owner (not reproducible without Rhino, named with its code path):
when `ThickenCellSurface` returns null, `SolveNative` EXPORTS THE UN-THICKENED FACE in the
solid's slot (`CellSurfaceSlot.Face`, SkinComponents.cs:417-467 and 574-604) and warns via
`ThickenFailureLine` (663-695: "... could not be THICKENED ... drawn as the un-thickened
face"). Such a cell sits exactly Th below its neighbours' top faces — the literal
"not raising to the right height to match". The thickener's failure modes concentrate on
high-corner-count cells: a whole/oversized cap fans its bottom from ~200-260 outline
corners into as many Brep slivers joined at 1e-9, then joins bottom+top+walls at 1e-6
(SkinComponents.cs:923-940, 1385-1409); the engine-side audit found no degenerate inputs,
so any failure is Rhino join arithmetic, and the confirmation is cheap: his GH file either
shows the ThickenFailureLine warning with a count, or it does not. The round-two check
should assert `slot == Solid` for every cell whenever Th != 0, which makes this fallback
red instead of silent-but-warned.

### What the fix must do (finding 2)

1. Kill the multi-CH closers at the source: finding 1's absorb rework (coalesce + sub-band
   bites toward 1 CH) bounds the closer's across width to ~1 CH, which measured at
   <= 0.0143 m sag — inside the ordinary course family's own envelope (max 0.0139).
2. If a slab genuinely must exceed ~1 CH, the closer needs an intermediate rail (sample
   the traced level curve at the slab's interior levels — they are already in the level
   list — as a third section), so the loft follows the surface instead of chording it.
   Route (b) of rule 5.2.3 already lofts three sections; no new machinery.
3. Make the acceptance check interior-sampling (corner check measures 0.0000 today and
   proves nothing), and add the `slot == Solid` assertion so a thickening refusal is a red
   check, not a warning. Re-flattening one route (e.g. forcing the closer to a two-rail
   chord over a 2-CH slab) measurably re-reds the interior check at 3.5 cm.

## Finding 3: the cap today, and the landing site for the one-polygon cap

### How the cap emits today (all in `plugin/native_v02/Components/SkinPatterns.cs`)

1. **Cap pass** (3774-3843, inside `Courses`): finds the top band `top`, walks its traced
   curves; `CapQualifies` (3287-3464) gates on closed loop / no free edge in crown / not a
   saddle. A qualifying loop under `maximumPiece = S / MP` (3783-3785) gets a whole-cap
   plan; over it, `InnerCapLevel` (3499-3543) bisects for the centre-disc level, W =
   `ceil(girth / maximumPiece)` wedges (3825-3826), and two levels (ring mid + inner) are
   inserted and the whole ladder re-traced (3827-3842).
2. **Emission** (inside the band-tiling loop): plan lookup 4107-4110; the WHOLE cap branch
   4111-4135 (outline = `Dedupe(outer.Points)`, one `SkinCell` with `Cap = true`, U span
   +-girth/2, `Sections = null`); the ROSETTE branch 4137-4238: ring-mid and inner curves
   fetched 4146-4153, correspondence tested 4154-4184 (failure re-emits whole+oversized),
   W wedges emitted as ordinary `BandCell`s with `Cap = true` (4198-4215), the centre DISC
   as a sectionless cell with the keystone's `Lead = 0` sort slot (4216-4235), girth
   bookkeeping 4236-4237.
3. **Sort and filter**: the cap leads its course branch (`ThenBy(item => item.Cell.Cap ? 0 : 1)`,
   4390), the disc leads its rosette (Lead term, 4393), and the cap is NOT exempt from
   `KeepValidPlans` (comment 4075-4084; the asymmetric fixture measured a cap actually
   dying there).
4. **Surfaces downstream**: a sectionless cap cell takes the fan route
   (`CellSurface`, SkinComponents.cs:913-941; top fan `OffsetTopFace` 1559-1597); a wedge
   takes the loft route. Cap girths are excluded from piece-length statistics per rule
   2.3.2a (4400-4402, 4426-4429).

On the symmetric six-lobe the emitted cap is the 3-piece rosette (W=2 + disc) Param wants
gone; on his denser form W is larger and the rosette is "that many pieces".

### What the final traced loop carries at cap time, and corner detectability

The loop the whole-cap branch already emits (`outer = lowers[lowerAt]`, a
`SkinLevelCurve`) carries: `Points` (full 3D trace vertices — 264 on the symmetric
fixture, 181 on the asymmetric), `Closed = true`, `Length` (3.296 m), `Seam`,
`Cumulative` (arc lengths), `Depth`. It is on the surface exactly (z range across the
symmetric loop 12 mm) and it is what the one-polygon cap's outline must be derived from.

Structural-corner detectability, measured:

- Symmetric six-lobe: raw per-vertex turning angles give SIX corners of 66.6 degrees at
  exactly the lobe azimuths (0, +-60, +-120, 180) against a background of <= 18.0 —
  cleanly separable by a single threshold (e.g. 25-30 degrees). Arc-windowed turning
  (signed turn summed over a 0.30 m window, non-max suppressed) gives six peaks of 102.4
  degrees and one spurious -38.4; the six-fold Fourier signature of plan radius reads
  |c6|/mean = 0.147. A lobed form's structure IS in the loop.
- Asymmetric six-lobe: the loop wiggles (coarse crown mesh here, z spread 0.10 m) and raw
  turning is noise up to +-146 degrees; windowed turning still finds peaks but with wrong
  counts/signs. So: NAIVE per-vertex turning is not robust; the simplification must work
  at a length scale, not per vertex — windowed turning with the threshold tied to a
  physical arc (order Min Piece), or Douglas-Peucker at a tolerance of order the trace
  noise, keeping the corner set that survives. On his real solved surfaces the crown is
  smoother than this fixture's centre fan, so the symmetric numbers are the representative
  case; the asymmetric numbers are the robustness bar.

### Landing site for the implementer

- REPLACE the rosette branch 4137-4238 (wedge ring + disc) and simplify the whole-cap
  branch 4111-4135 into ONE emission: a single `SkinCell(band.Course, capOutline, false,
  -outer.Length/2, outer.Length/2, true)` whose `capOutline` is `outer.Points` simplified
  to its structural corners (`SetoutCorners` can carry the corner count). The
  `plan.Wedges/InnerLevel/RingMid` plumbing (SkinCapPlan record 3470-3476, the W and inner
  computation 3812-3832, the two inserted levels and re-trace 3827-3842) becomes dead for
  emission; keep the girth for diagnostics and for rule 2.6.6's oversized WARNING if the
  ruling keeps naming it, but nothing splits any more. `CapGirths`/`CapWedgeCounts` and
  the diagnostics cap line (4403-4422) need their wording moved from "wedges" to "sides".
- KEEP the gates untouched, per the ruling: `CapQualifies` (3287-3464), the cap-band
  identification (4054-4057), the cap-leads-branch sort term (4390) and the Lead slot
  (keystone ordering keeps one keystone: the single polygon IS the keystone now, Lead 0).
- TWO measured hazards the new cap must survive:
  1. `KeepValidPlans` — the asymmetric fixture killed today's whole cap by overlap with a
     folded depth-0 neighbour band (see finding 1c). Simplifying the outline to a few
     corners CUTS INSIDE the traced loop (a convex-ish polygon inscribed in the loop), so
     overlap with the band below becomes MORE likely at the corners' chords unless the
     neighbour fold is fixed (finding 1c item 4) or the simplification stays within a
     tolerance of the loop. State the interaction in the plan; do not exempt the cap from
     the filter (the standing rule at 4082-4084).
  2. The one-polygon cap is a SECTIONLESS cell: it takes the fan route, whose bottom/top
     are chord fans from the lifted interior point (SkinComponents.cs:917-941, 1559-1597).
     Fan sag on the symmetric fixture's small cap measured 0.7 mm, but a six-lobe polygon
     cap spans the whole crown: sag grows with the crown's rise inside the loop (order
     kappa r^2 / 2 — for his forms plausibly centimetres). If the polygon cap renders flat
     and low, that is finding 2 arriving through finding 3's door: the fan apex is the
     summit, so the BOTTOM fan actually follows the dome down from the apex (measured
     small), but the fewer the outline corners, the longer the rim chords — keep enough
     corners (the structural set, not 3) and the measured sag stays in the millimetre
     class. Simplification tolerance is therefore ALSO a surface-fidelity knob; say so in
     the spec.
- The cap emission's data need is already satisfied: everything the polygon needs
  (`outer.Points`, `Length`, `Seam`) is in hand at 4113 at cap time; no new tracing and no
  new levels are required for the unsplit cap (the two cap levels stop being inserted,
  which also removes their re-trace cost, 2 levels + 1 pass on the symmetric fixture).

---

## Probe and reproduction (disposable)

- Probe project: `...\scratchpad\probe\{Probe.csproj, ProbeMain.cs, ContractShims.cs}` —
  compiles the scratch copy's `SkinPatterns.cs` + `SkinFlowField.cs` directly (contract
  DTOs shimmed; `ReadNet` inert). Build:
  `dotnet build probe/Probe.csproj -c Release -o b2`; run `b2/SkinProbe.exe 6`,
  `b2/SkinProbe.exe 6 asym`, `b2/SkinProbe.exe 3` from the scratchpad root.
- Temporary hooks in the SCRATCH copy's `SkinPatterns.cs` only, each fenced with
  `TEMPORARY DIAGNOSTIC PROBE ... NEVER MERGE`: a `SkinCoursesProbe` collector type +
  static `Probe` field at end of file; hook 1 after the cap pass (levels, bands, refusals,
  traced counts, cap plans); hook 2 after the absorb loop (post-absorb bands, slabs);
  hook 3 at cap emission (outer loop points); hook 4 around `KeepValidPlans` (pre/post
  filter cell lists); hook 5 in `CloserBand` (per-stone guide/other identities). Nothing
  in the main tree was touched; nothing was committed anywhere.
- Method notes: void classification samples a 7.5 cm plan grid against kept-cell plan
  containment (engine's own `PlanContains` via a probe wrapper); surface deficit samples
  ruled/fan interiors against `LiftPlanPoint`; the per-slab closer counts use a +-0.02
  field slack, so abutting thin slabs double-count a little at their borders (magnitudes,
  not identities); all engine arithmetic (containment, overlap, interior points, level
  lookup) is the engine's own, not re-derived.
