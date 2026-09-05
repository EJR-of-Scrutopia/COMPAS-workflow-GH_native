# Round-three diagnosis: duplication, the ridge, and the remaining gaps, measured on barrel-class and four-corner fixtures

Diagnosis-only report for the round-three fix wave, against the INSTALLED commit
88e170f (the round-two build Param photographed). Scope is the three findings of
`docs/superpowers/specs/2026-09-05-skin-round-three-findings.md`. Everything below
was MEASURED: `SkinPatterns.cs` from the scratch archive
`...\scratchpad\r3-88e170f` was compiled into a standalone probe (typed access, no
reflection, no Rhino) and run over ELEVEN fixture runs: a uniform open barrel
(ridge on a vertex row), the same barrel with the ridge BETWEEN vertex rows, a
wavy barrel (rise varying along the length, the form-found case), a jittered wavy
barrel, a square four-corner fan, a jittered fan, a rectangular four-corner fan
(merges at three heights), a jittered rectangular fan, Param's own exported crown
arch (the harness asset `param-crown-arch-contract.json`, at both CH 0.30 and CH
0.375), and the three round-two lobed fixtures as the regression anchor.

All file:line references are to the PRISTINE 88e170f `plugin/native_v02/Components/
SkinPatterns.cs` (line numbers taken before the probe's fenced `TEMPORARY
DIAGNOSTIC PROBE ... NEVER MERGE` hooks were inserted into the scratch copy; the
hooks are disposable and nothing outside the scratch tree was touched).

Raw probe outputs (full numbers behind every claim):
`...\scratchpad\r3-barrel.txt`, `r3-barreleven.txt`, `r3-barrelwavy.txt`,
`r3-barreljitter.txt`, `r3-fan.txt`, `r3-fanjitter.txt`, `r3-fanrect.txt`,
`r3-fanrectjitter.txt`, `r3-crown.txt` (CH 0.30), `r3-crown375.txt`,
`r3-6.txt`, `r3-6asym.txt`, `r3-3.txt`.
Probe project: `...\scratchpad\r3p\{Probe.csproj, ProbeMain.cs, ContractShims.cs}`;
build `dotnet build r3p/Probe.csproj -c Release -o r3b` from the scratchpad root
(the short `-o` dodges the path-length trap), run `r3b/SkinProbe3.exe <fixture>`.

Method for finding 1, stated up front because the verdict rests on it: every kept
cell was tagged with its EMITTING MECHANISM at the emission site (ordinary band
tiling with band low/high/depth, closer staged stone with guide and other levels
and the extension flag, closer end-stone with its gap, cap), the whole plan was
sampled on a 0.03-0.075 m grid (0.04 m on the round-three fixtures), and every
sample point was tested against every kept cell whose bucketed bounding box holds
it, using the engine's own `PlanContains`. A point inside TWO OR MORE cells is a
double-cover sample; a pair of cells sharing two or more samples is an overlap
witness, its area the sample count times the cell area; witnesses above 0.001 m2
(well beyond the 1e-6 corner weld) are the "strong" class the finding asks for.

---

## Headline table

| fixture | cells | refusals | slabs | closers | drops | overlap witnesses | double-covered area | uncovered (non-rim) |
|---|---|---|---|---|---|---|---|---|
| barrel (uniform, ridge on row) | 298 | 0 | 0 | 0 | 0 | **0** | **0.0000 m2** | ~0 (hairline crest line) |
| barrel (ridge BETWEEN rows) | 298 | 0 | 0 | 0 | 0 | **0** | **0.0000 m2** | **1.60 m2 crest ribbon** |
| barrel wavy | 291 | 3 | 2 (1.00 / 0.44 CH) | 31 | 0 | **0** | **0.0000 m2** | **1.92 m2** (crest) |
| barrel wavy + jitter | 310 | — | — | 32 | 0 | **0** | **0.0000 m2** | 2.12 m2 (crest) |
| fan (square 4-corner) | 375 | 1 | 1 (1.00 CH) | 40 | 0 | **0** | **0.0000 m2** | 0.32 m2 |
| fan + jitter | 387 | — | — | 40 | 0 | **0** | **0.0000 m2** | 0.29 m2 |
| fan rect (3 merge heights) | 334 | 2 | 2 (1.00 CH each) | 54 | 0 | **0** | **0.0000 m2** | 0.47 m2 |
| fan rect + jitter | 340 | — | — | 56 | 0 | **0** | **0.0000 m2** | 1.02 m2 (0.62 cap) |
| Param's crown arch CH 0.30 | 1815 | 1 | 1 (1.00 CH) | 68 | 0 | **0** | **0.0000 m2** | 0.09 m2 (cap lenses) |
| Param's crown arch CH 0.375 | 1475 | 1 | 1 (1.00 CH) | 62 | 0 | **0** | **0.0000 m2** | 0.05 m2 |
| six-lobe sym / asym / three-lobe | 568/639/519 | 1/5/1 | 1×1.00 CH each | 66/70/51 | 0 | **0** | **0.0000 m2** | round-two adjudicated |

Round-two anchor: the asymmetric six-lobe reads EXACTLY the round-two fix-wave
numbers on this build (one slab [0.8750, 1.2250] = 1.000 CH, 70 closers, 0 drops,
slab uncovered 0.0000 m2, 8 non-closer slivers, one cap of 33 sides; sym 66
closers / cap 114 sides; three-lobe 51 / cap 240). No regression: the round-three
defects are class-specific, not a round-two backslide.

---

## Finding 1: duplication — the engine is ACQUITTED; the witness count is ZERO everywhere, and the look-alikes are named

### The measurement

Across all eleven runs, including Param's own solved crown arch and the jittered
(form-found-like) meshes: **zero overlap witnesses, zero double-covered samples,
zero plan-filter drops.** The strong-witness census is empty on every fixture, so
`PlansOverlapWithInteriors` (SkinPatterns.cs:2849) was never even given a miss to
make. This is not luck; it is the design working:

- `KeepValidPlans` (SkinPatterns.cs:2925-2986) runs over the full sorted emission
  and drops any cell overlapping a survivor, so two kept same-pattern cells can
  only overlap if the detector misses. The detector (proper crossing at 1e-9
  perpendicular, SkinPatterns.cs:2507-2529, plus interior-point containment)
  found nothing to miss on these forms, and the independent grid measure agrees.
- THE SPEC'S SPECIFIC SUSPICIONS, each checked directly with the probe's band
  bookkeeping (post-absorb tileable list captured at SkinPatterns.cs:4097 and
  compared against slabs and emissions):
  1. "absorbed intervals not excluded from ordinary course tiling" — EXCLUDED,
     verified: on every slab fixture the post-absorb tileable list carries no
     interval intersecting a slab (e.g. 6asym: slab [0.875, 1.225], tileable
     jumps course 2 [0.700, 0.875] -> course 3 [1.225, 1.400]; fanrect: courses
     5 and 10 wholly absent from tileable). Whole-band bites remove the band
     (`tileable.RemoveAt`, SkinPatterns.cs:4015), sub-band bites replace it with
     the remainder only (4056-4081). Zero double-cover confirms it end to end.
  2. "flank extensions re-cover flanks the courses still tile" — NO: every
     extension event was logged (6 on fanrect, 5 on fanrectjitter, 3 on wavy
     barrel; `TryExtendCloser` SkinPatterns.cs:6943) and every extended stone
     stayed inside its slab's own interval; zero double-cover again.
  3. "a band both absorbed into the closer and emitted as its own course" — the
     interval arithmetic forbids it and the measurement confirms it; what IS
     true is the same COURSE INDEX legitimately carrying both species in
     adjacent intervals (rule 8.2.4), which is look-alike (b) below.

So on barrel-class and four-corner geometry the tessellation the engine hands
over CANNOT contain the doubled stones; his photograph is of something these
mechanisms did not emit twice.

### The measured look-alikes that read as "courses appearing twice"

(a) **HALF-BAND PAIRS BESIDE A SLAB** — the strongest candidate for the "doubled
banding near crowns", and it is a real, measured, shipping behaviour. On the
asymmetric six-lobe, the bisection + absorb leave course 2 = [0.700, 0.875] and
course 3 = [1.225, 1.400], each 0.50 CH deep, each tiled with its OWN pitch and
origin off its own mid curve: course 2 carries 60 cells of median area 0.0562 m2
and course 3 carries 60 of 0.0630, against the ordinary course 4's 56 cells of
median 0.1300. Two bands of TWICE the stone count at HALF the height, joints
offset from every neighbour (each sub-band's mid curve has its own arc origin),
with a third species (70 closer stones) interleaved between them. From above,
around a merge, that is exactly "whole courses appearing twice, interleaved and
offset". Owner: `ResolveBands`' bisection halves surviving as tileable sub-bands
(SkinPatterns.cs:3157-3218, rules 8.2.2-8.2.5) beside the absorb (3937-4095),
which grows the slab to 1 CH and NO FURTHER, deliberately leaving the halves.
Same signature on the wavy barrel: course 10 = 16 ordinary cells in [3.500,
3.6534] (0.44 CH) PLUS closer stones in [3.6534, 3.8068] at the same course
index.

(b) **ONE COURSE, TWO SPECIES**: a partially-absorbed course tiles its remainder
ordinarily and covers its slab with closers at the SAME course number
(SkinPatterns.cs:4173-4237 emits closers at `refusedCourse`), so a stage in the
studio contains two interleaved stone families. Legal, but it reads doubled.

(c) **THE COMPONENT-SIDE TRANSLUCENT DOUBLE** (not reproducible without Rhino,
named with its code path): a cell whose thickening fails ships the TOP FACE AT
TOP HEIGHT in the Face slot (`SolveNative`, SkinComponents.cs:459-473, fix 4's
`CellTopFaceAtHeight`) while its neighbours ship solids. A translucent top-height
face over the coursing, amid closed solids, is a literal translucent double image
one thickness above the surface. His chin on the photographed model either shows
the `ThickenFailureLine` warning with a count or it does not; that one line
adjudicates (c) for free, and the round-two live pull already measured 32 such
faces on the six-lobe at 8b9a44a.

### What the fix must do (finding 1)

Grounded in the zero: do NOT hunt a double-emission bug in the courses engine on
these classes; the emission bookkeeping is measured sound. Close the LOOK-ALIKES:
1. Merge or re-ladder the half-band pairs beside a slab: two 0.50 CH sub-bands
   flanking a 1.00 CH slab should read as courses of the field's own rhythm, not
   as two extra thin courses (candidates, for the fix wave to weigh: re-anchor
   the ladder through the slab so the flanking bands return to ~1 CH, or absorb
   symmetric halves into their outer neighbours). The acceptance instrument is
   the per-course cell-count/median-area profile: today 60 @ 0.056 / 60 @ 0.063
   against neighbours' 56 @ 0.130 on 6asym; after the fix no course's median
   area may sit at half its neighbours' without a named reason.
2. Get Param's chin text for the photographed models: if `ThickenFailureLine`
   fires there, (c) is confirmed as the translucent double and the thickening
   rescue (not the pattern) owns the visual; the round-two `slot == Solid`
   check in `rhino_skin_surface.py` part four is the standing instrument.
3. Keep the overlap-witness harness check (the grid double-cover count pinned at
   ZERO on the barrel and four-corner fixtures) so any future emission defect of
   this class fails loudly; it is cheap and it is the finding's own sentence.

---

## Finding 2: the barrel crown — what actually fires at a ridge, measured

The spec's expectation is confirmed HALF-WAY: `CapQualifies` DOES refuse the
ridge (SkinPatterns.cs:3286-3292, "the top course is an OPEN strip, so its crown
is a ridge and not a disc" — recorded twice, once per side, on every barrel run),
so no cap fires and his "two half pieces" is not a split cap. What covers the
top instead is three different things depending on geometry, and two of them are
defective:

### 2a. The uniform ridge: two ordinary half-vaults, and a crest the ladder never covers

On a barrel whose field tops out along a ridge, correspondence 2<->2 holds all
the way up (traced counts: 2 open strips at every level), so there are NO
refusals, NO slab, NO closer — the seam machinery NEVER TRIGGERS at all, because
its only trigger is a correspondence failure (`ResolveBands`, 3188). Both sides
get ordinary top bands folding to the ladder's top cut at dMax - epsilon
(3835-3840). Then the mesh decides everything:

- Ridge ON a vertex row (odd-row fixture): the strip between the two top curves
  is the epsilon ribbon, micrometres wide. Coverage 98.67 per cent with only
  line-sampling artefacts. CLEAN — this is why the engine's own fixtures never
  saw the problem.
- Ridge BETWEEN vertex rows (even-row fixture, the generic quad-mesh case): the
  field attains dMax on TWO whole vertex rows and the faces between them (a
  PLATEAU, not a point), the top cut at dMax - epsilon lands OUTSIDE that
  plateau, and the entire crest strip ships uncovered: **1.60 m2, a ribbon 8 m
  long by ~0.2 m wide along the whole crown, with zero refusals, zero drops and
  zero warnings** (probe: void class crown-epsilon 1000 samples, one cluster
  spanning the full length at y = 3.0). Nothing owns this hole today; the
  epsilon rule (3820, rule 1.5.2) assumes the set above dMax - epsilon has no
  area, and a ridge plateau breaks that assumption. On a REAL solved mesh the
  crest values dither by mesh noise, so the top cut MEANDERS in and out along
  the crest and the top band's cells are cut against a zigzag — the "chaos of
  triangles" is this ribbon's ragged edge, plus 2b's carcasses where a slab
  did form.

### 2b. The form-found ridge: the closer fires and starves against a degenerate family

On the wavy barrel (rise varying 15 per cent along the length — a solved arch is
never prismatic) the ridge's own field VARIES along the crest (3.4371 at the dip,
3.8068 at the summit). Consequences, all measured:

- Level curves near the top stop spanning the barrel (total traced length falls
  16.30 -> 5.6 m), the 2-strip family becomes 1 open curve then 1 CLOSED loop
  around the summit (levels 3.7013-3.7061), correspondence fails, and refusals
  land at courses 9 and 10 (0.02 CH each).
- The absorb builds slab 9 = [3.1500, 3.5000] = 1.00 CH and slab 10 = [3.6534,
  3.8068] = 0.44 CH (short: the cap-band protection at 3976-3981 stops it biting
  the tileable band [3.500, 3.6534] below, and above it there is nothing).
- **Slab 10 starves against a DEGENERATE other family**: its high boundary is
  the ladder's top cut, whose trace is one closed loop of length 0.00 m ringing
  the summit vertex. `CloserBand` picks guides = the two 3.6534 strips (lows 2
  >= highs 1, 6390) and other = that point-loop; the head-joint bound
  `max(S, 4 x thickness)` = 0.61 m (6389) refuses every stone whose span sits
  more than 0.61 m from the summit: **10 of 12 stones refused (probe events
  `stone-joint-bound` x10, `stone-folds` x1), ONE stone laid**, and the crest
  ribbon ships open: 1.04 m2 at the summit stretch plus 0.03 m2 at the far end
  (void class A-in-slab, field [3.6536, 3.8066]).
- **The pinch-out pass is structurally blind here**: coverage is read as ARCS OF
  THE OTHER CURVE (6523-6631), and the other curve has ~zero arc, so a 1.04 m2
  hole registers as no gap at all — zero end-stones were even attempted
  (events: 0). The round-two instrument measures in the wrong currency on a
  ridge.
- **Slab 9 leaves the dip crest open the same way**: its other family (the 3.50
  strips) simply DOES NOT EXIST over the dip (ridge tops out at 3.4371 < 3.50
  there), the guide stones near the dip lay skewed back runs to the other
  curves' distant ends (joint bound 1.40 m lets them through), and the crest
  region between the two sides' stones — 0.85 m2, field [3.165, 3.499], centred
  exactly on the ridge at the dip — belongs to nobody. Again zero refusal
  events: the machinery does not know it failed.

### 2c. What his real crown arch does (and why his fan-vault crown got a quadrilateral)

Param's own solved crown arch tops out in a genuinely CLOSED summit loop (girth
3.68 m at CH 0.30), so there `CapQualifies` accepts, the 2->1 merge below is a
proper slab ([9.300, 9.600], 68 closers, clean), and ONE cap fires — but
`CapPolygonOutline` (3501-3616) simplifies that smooth four-fold loop to
**exactly 4 corners** (windowed turning threshold 45 deg finds the four
structural peaks; the inscribed refinement 3588-3614 tests only whether trace
vertices lie on the polygon-INTERIOR side of a chord, i.e. it guards OUTWARD
transgression into the course below and never fires on a CONVEX arc), so the cap
ships as an inscribed quadrilateral of 0.417 m2 inside a loop enclosing ~0.5 m2:
**four crescent voids, 0.09 m2 total, at the crown — five course-stones' worth
of hole at his S = 0.10** (probe: void class CAP-band-shortfall, 100 samples in
four symmetric clusters hugging the loop). The same class measured 0.070 m2 on
the square fan (cap 4 sides on a 1.69 m loop), 0.023 m2 at CH 0.375, and blew up
to **0.59 m2 on the jittered rectangular fan** (turning noise left 4 corners on
a 4.53 m loop — half a square metre of open crown). His "two half pieces"
reading of the barrel crown photograph is thus answered by mechanism: what he
saw is a 4-cornered inscribed cap plus its crescent holes (and/or 2a's ragged
ribbon), not a split cap — the engine never emits two cap halves anywhere
(caps in cells: exactly 0 on ridges, exactly 1 where a loop qualifies, all
fixtures).

### The seam IS recovered on a ridge with free ends

Verified explicitly, because the design answer (the closer running along the
ridge) depends on it: on every barrel `SeamCurves` (1185-1305) returns ONE open
polyline running the FULL crest, endpoints ON the free edges (uniform barrel:
119 points, 10.67 m, (0.00, 2.92) -> (8.00, 3.08); wavy: 8.75 m end to end).
The spine for ridge stones exists today; nothing consumes it (the closer
divides GUIDE LEVEL CURVES, by design — comment at 3807-3816 — and at a ridge
the guide family's opposite number degenerates).

### What the fix must do (finding 2)

1. NAME THE RIDGE and give it a treatment that does not depend on a
   correspondence failure to trigger: on the uniform barrel NOTHING fires today
   and the crest ribbon (up to 1.60 m2 measured) ships silently. The trigger
   must come from the field/mesh itself: the set of faces whose vertices all sit
   above the top cut (the dMax plateau), or the recovered seam curve, both in
   hand already.
2. The ridge closure the spec names — full-width stones ALONG the crest — needs
   a cross-ridge construction the closer does not have: pair the TWO SIDES' own
   curves (side A's run and side B's run back, paired via the seam or via
   second-family identity), instead of guide-family -> other-family within one
   interval, because at a crest the "other family" is measured degenerate (a
   0.00 m loop) or absent (the dip). The head joints of such a stone are the
   crest crossings, which obey the joint bound naturally (the two sides are a
   band apart, not metres).
3. Change the closer's residue currency from other-curve ARC to SLAB PLAN AREA
   (check-2's own instrument): the 1.04 + 0.85 m2 wavy-barrel holes produced
   ZERO gap events because the arcs they project to are degenerate or already
   covered. A slab must know its own uncovered area before it returns.
4. Keep `CapQualifies` exactly as is (its ridge refusal is measured correct,
   both sides, every barrel), and keep the ladder's epsilon for true point
   crowns; the plateau case needs the ribbon assigned to the ridge treatment of
   (1), not a bigger epsilon (a bigger epsilon just moves the ragged cut down).

---

## Finding 3: the remaining gaps, classified with owners

Beyond the adjudicated sub-sliver residues (six-lobe seam-tip wedges 0.14-0.20
m2 per lobed fixture, unchanged from round two), the round-three fixtures open
FOUR classes, two of them new:

| # | class | owner (code path) | measured |
|---|---|---|---|
| G1 | **ridge-plateau ribbon** (NEW ridge class) | band ladder top cut, SkinPatterns.cs:3835-3840 + epsilon rule 3820; no mechanism triggers (no refusal, no slab) | 1.60 m2 (even barrel, full crest); ~0 on odd barrel — mesh parity decides |
| G2 | **ridge-crest closer starve** (NEW ridge class) | CloserBand vs degenerate/absent other family: joint bound 6389 + arc-coverage blindness 6523-6631; refusal events measured (`stone-joint-bound` x10) | wavy barrel 1.04 + 0.85 + 0.03 m2; jittered wavy 2.12 m2 |
| G3 | **cap-lens crescents** (NEW, round two's own cap) | `CapPolygonOutline` refinement guards only outward transgression, 3588-3614; cap emission suppresses the band's ordinary tiling, 4310-4348 | crown arch CH 0.30: 0.09 m2 (4 lenses, girth 3.68 -> 4 sides); fanrectjitter 0.59 m2; fan 0.07 m2; crown375 0.023 m2 |
| G4 | **shadowed free-edge wedge** (round-two 1a's surviving sibling) | pinch-out pass reads other-curve arcs; the wedge over an opening projects onto arcs ALREADY covered by neighbouring guides' stones, so no gap is seen (0 events); 6506-6631 | fan: 4 wedges, 0.21 m2 (2 x 0.072 + 2 x 0.051); fanrect: 0.20 + 0.17 + 0.05 + 0.05 m2 — full-stone-size holes at every free-edge merge point |
| — | round-two classes for reference | guide pinch-out / absorb starve / plan drop | plan drops 0 everywhere; absorb starve only as the cap-protected 0.44 CH slab (wavy barrel); classic pinch-outs closed (extensions fired 3-6 per fixture) |

G4 detail, since it is the "couple which are getting gaps" on a four-corner
form: at each free-edge midline where two corner families merge, the slab wedge
between the two guide arcs' boundary ends is uncovered, field range reaching
BELOW the slab low (fan: [2.483, 3.130] against slab [2.800, 3.150] — the wedge
hangs below the slab into the course under it, where that course's own strip was
boundary-clipped). The round-two end-stone machinery scans the ONE central loop
for uncovered arcs; stones from BOTH corners already cover the arcs nearest the
opening, so the wedge is in their plan SHADOW and no end-stone is attempted.

### What the fix must do (finding 3)

1. G1/G2 are finding 2's fix (ridge treatment + plan-area residue accounting);
   their acceptance is the crest ribbon pinned covered on BOTH barrel parities
   and on the wavy barrel, at course size, no slivers.
2. G3: the cap polygon must stop leaving convex lenses beyond the sliver floor:
   either refine INWARD too (add the worst outward-lying trace vertex where the
   lens area beyond a chord exceeds the sliver floor — the symmetric clause of
   the existing rule at 3601-3607, measured cheap: the lobed caps already carry
   33-240 corners), or keep the 4-corner polygon and let the cap band's
   ordinary tiling lay the crescents. Acceptance: cap-band uncovered area under
   the sliver floor on fan, fanrectjitter (0.59 m2 today) and crown arch.
3. G4: the pinch-out residue scan must fall back to PLAN coverage of the slab
   (same instrument as (2) above): a wedge whose arcs are shadowed is invisible
   to arc bookkeeping by construction, so no arc-side patch can reach it. The
   end-stone construction itself (cut against the two families' own ends,
   6678-6785) is the right stone for it once the wedge is SEEN — the flanking
   corners exist on both sides of every measured wedge.
4. Adjudicate the half-band pairs (finding 1's look-alike (a)) in the same
   wave: they are within-spec today but they are what "the banding is where
   most problems are" looks like from above.

---

## The fixtures (lift into tests/native_smoke verbatim)

`SkinLobedNet` is already in the harness (Program.cs:23216). The new ones:

```csharp
/// <summary>Open barrel arch: cylindrical-arch vault over a rectangular
/// plan, SUPPORTED along the two long edges (two rim seed groups), FREE at
/// both short ends, so the field tops out along a RIDGE LINE whose meeting
/// line ends at free edges. waveAmp varies the rise along the length (a
/// form-found arch is never prismatic). ny ODD puts a vertex row exactly on
/// the ridge (the engine's clean case); ny EVEN puts the ridge BETWEEN rows
/// (the generic case, the 1.60 m2 plateau ribbon).</summary>
static (double[][] V, int[][] F, int[] Rim) BarrelNet(
    int nx, int ny, double length, double width, double rise, double waveAmp)
{
    var vertices = new List<double[]>();
    for (int iy = 0; iy < ny; iy++)
    {
        double y = width * iy / (ny - 1.0);
        for (int ix = 0; ix < nx; ix++)
        {
            double x = length * ix / (nx - 1.0);
            double r = rise * (1.0 + waveAmp *
                Math.Sin(2.0 * Math.PI * x / length + 0.5));
            vertices.Add(new[] { x, y, r * Math.Sin(Math.PI * y / width) });
        }
    }
    int Idx(int ix, int iy) => iy * nx + ix;
    var faces = new List<int[]>();
    for (int iy = 0; iy + 1 < ny; iy++)
        for (int ix = 0; ix + 1 < nx; ix++)
            faces.Add(new[] { Idx(ix, iy), Idx(ix + 1, iy),
                Idx(ix + 1, iy + 1), Idx(ix, iy + 1) });
    var rim = new List<int>();
    for (int ix = 0; ix < nx; ix++) rim.Add(Idx(ix, 0));
    for (int ix = 0; ix < nx; ix++) rim.Add(Idx(ix, ny - 1));
    return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
}
// uniform:      BarrelNet(49, 37, 8.0, 6.0, 2.0, 0.00)   ridge on a row
// plateau:      BarrelNet(49, 36, 8.0, 6.0, 2.0, 0.00)   ridge between rows
// form-found:   BarrelNet(49, 37, 8.0, 6.0, 2.0, 0.15)   ridge field varies
// run: new SkinNet(v, f, rim, Array.Empty<SkinNetEdge>()); Courses(net, 0.6, 0.35)

/// <summary>Four-corner fan vault: doubly-curved surface over a rectangular
/// plan, SUPPORTED at the four corners (each an L-run of cornerRun vertices
/// along both adjacent edges: four seed groups), FREE along the edge middles.
/// Square plan: one merge height. Rectangular: short-edge merges, long-edge
/// merges and the centre cross land at three different heights.</summary>
static (double[][] V, int[][] F, int[] Rim) FanRectNet(
    int nx, int ny, double lx, double ly, double h, int cornerRun)
{
    var vertices = new List<double[]>();
    for (int iy = 0; iy < ny; iy++)
    {
        double y = ly * iy / (ny - 1.0);
        for (int ix = 0; ix < nx; ix++)
        {
            double x = lx * ix / (nx - 1.0);
            double u = 2.0 * x / lx - 1.0;
            double vv = 2.0 * y / ly - 1.0;
            vertices.Add(new[] { x, y, h * (1.0 - (u * u + vv * vv) / 2.0) });
        }
    }
    int Idx(int ix, int iy) => iy * nx + ix;
    var faces = new List<int[]>();
    for (int iy = 0; iy + 1 < ny; iy++)
        for (int ix = 0; ix + 1 < nx; ix++)
            faces.Add(new[] { Idx(ix, iy), Idx(ix + 1, iy),
                Idx(ix + 1, iy + 1), Idx(ix, iy + 1) });
    var rim = new List<int>();
    foreach ((int cx, int cy, int dx, int dy) in new[]
    {
        (0, 0, 1, 1), (nx - 1, 0, -1, 1),
        (nx - 1, ny - 1, -1, -1), (0, ny - 1, 1, -1)
    })
    {
        rim.Add(Idx(cx, cy));
        for (int k = 1; k <= cornerRun; k++)
        {
            rim.Add(Idx(cx + k * dx, cy));
            rim.Add(Idx(cx, cy + k * dy));
        }
    }
    return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
}
// square fan:   FanRectNet(41, 41, 8.0, 8.0, 3.0, 6)
// rect fan:     FanRectNet(51, 31, 10.0, 6.0, 2.5, 6)

/// <summary>Deterministic plan jitter (interior vertices only; rim and mesh
/// boundary held), so a grid fixture reads like a solved net. amp ~ 0.3 of
/// the mesh spacing. Used at 0.05-0.06 on the fixtures above; the jittered
/// rectangular fan is the 0.59 m2 cap-lens case (its crown loop simplifies
/// to 4 corners under trace noise).</summary>
static double[][] Jitter(double[][] v, int[][] f, int[] rim, double amp)
{ /* hash-nudge x,y of every non-rim, non-boundary vertex: see
     scratchpad r3p/ProbeMain.cs, Jitter(), verbatim */ }
```

Param's crown arch runs off the harness's own asset exactly as
`ValidateSkinCrownCap` already loads it (`assets/param-crown-arch-contract.json`
through `ReadNet`); the probe's standalone JSON walk is in
`r3p/ProbeMain.cs, CrownArchNet()` if a no-reflection loader is wanted.

## Probe mechanics (disposable)

Hooks in the SCRATCH copy's `SkinPatterns.cs` only, each fenced `TEMPORARY
DIAGNOSTIC PROBE ... NEVER MERGE`: hook 1 after the level index (levels, traced
counts with per-level curve totals, pre/post-absorb tileable, refusals, slabs,
cap plans/refusals); mechanism tags at every emission site (ordinary cell with
band identity, staged closer with guide/other levels + extension flag, end-stone
with its gap, cap cell); hook 4 around `KeepValidPlans` (pre/post lists); named
refusal-event hooks at all seven CloserBand refusal sites; extension events in
the gap pass and `TryExtendCloser`. `ProbePlanContains` shims the private
containment test. Nothing outside the scratch tree was touched; nothing was
committed anywhere.
