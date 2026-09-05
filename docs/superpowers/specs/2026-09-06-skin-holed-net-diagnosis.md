
# The holed net: diagnosis of the interior-hole-rim defect class, measured against 88e170f

Diagnosis-only report, written 2026-09-06 against the scratch archive of the installed
commit 88e170f (round two's build, the same tree round three's own diagnosis measured).
Scope is live witness 1 of
`docs/superpowers/specs/2026-09-05-skin-round-three-findings.md`: Param's real six-lobe
net carries DESIGN HOLES near the crown, round two closed the synthetic (hole-free)
lobed fixtures to 0.0000 m2, and the live model still shows thin radial seam gaps in the
lobe valleys and a ring of rectangular openings around the crown. The question is
whether an interior hole rim is a genuinely NEW defect class, or the same G1-G4
mechanisms round three already named, just relocated.

Method: `SkinPatterns.cs` from the scratch archive
`...\scratchpad\r3-88e170f` (already carrying round three's own disposable probe hooks,
fenced `TEMPORARY DIAGNOSTIC PROBE ... NEVER MERGE`, nothing added or removed here) was
compiled into the existing round-three probe project
(`...\scratchpad\r3p\{Probe.csproj, ProbeMain.cs, ContractShims.cs}`), extended with the
hole-rimmed fixture builder below, and run over SEVEN fixtures: the asymmetric six-lobe
dome with no holes (the control, identical to round three's own `6asym`), and six
hole-rimmed variants crossing {one hole off any seam, six holes forming a ring off-seam,
six holes centred on the valley seams} x {rim unanchored (free edge only), rim anchored
(a new support ring, one seed family per hole)}. Built with
`dotnet build r3p/Probe.csproj -c Release -o hb` (the short `-o` dodges the path-length
trap) from the scratchpad root; run `hb/SkinProbe3.exe <fixture>`. All file:line
references are to the PRISTINE 88e170f `plugin/native_v02/Components/SkinPatterns.cs`.

Raw probe outputs: `...\scratchpad\holed-6asym-control.txt` (control),
`holed-6holeoff-free.txt`, `holed-6holeoff-anchor.txt`, `holed-6holering-free.txt`,
`holed-6holering-anchor.txt`, `holed-6holevalley-free.txt`,
`holed-6holevalley-anchor.txt`.

---

## 1. How nets reach the harness, and whether any fixture already carries a hole

`tests/native_smoke/Program.cs` builds every synthetic net as `(Vertices, Faces, Rim)`
and hands it straight to `SkinNet`'s constructor, which calls `SkinPatterns.BuildNet`
(SkinPatterns.cs:733). The `Rim` array is not the mesh boundary; it is rule 1.3.1's
ANCHOR SET, stated explicitly in the ONE place the harness builds a net from a real
solved diagram (`ReadNet`, SkinPatterns.cs:524-531): "the mesh boundary... includes an
oculus, a free edge and every hole, none of which is a support and none of which a
course should be measured from." `RimDistanceFieldWithSeeds` (958) partitions the RIM
alone into connected components via the net's own edges (`SeedGroupsOf`, 1092) and
marches from those seeds; an interior opening that is not in `Rim` contributes no seed
at all and is invisible to the seed count, but its faces are still absent from the mesh
graph the marching walks, so it is a real geometric obstacle to every geodesic path that
would otherwise cross it.

Searching the harness's fixture builders (`SkinLobedNet` at Program.cs:23215,
`SkinBarrelNet`, `SkinWalledVaultNet`, `SkinDomeNet`, `SkinRingVaultNet` at 18093 and its
three siblings, `SkinAnnularVaultNet` at 18456, `SkinTwoPeakNet`, `SkinLShapedNet`, and
the round-three barrel/fan builders) for any that already carries a genuine INTERIOR
hole: none does. `SkinRingVaultNet` and `SkinAnnularVaultNet` are ANNULAR (an outer rim
and an inner oculus ring), which comes closest, but both are called with NO explicit
`Rim` argument at every call site found (Program.cs:25692, 26056-26063, 28008) — the
two-argument `SkinNet(vertices, faces)` overload — so their entire outer AND inner
boundary is whatever that overload's default rim rule produces (uniformly one boundary
treatment, not "anchored outside, open hole inside"), and in any case the oculus there
is CONCENTRIC with the crown, not an off-centre opening beside an otherwise ordinary
lobed field. No existing fixture models "a hole punched somewhere in the middle of an
otherwise solid dome, near but not at the summit," which is exactly Param's witness.
Real net data ships as exactly one file, `tests/native_smoke/assets/
param-crown-arch-contract.json` (the crown arch used by `ValidateParamCrownContract`
and round three's `crown`/`crown375` fixtures); it is a two-family arch with no
interior holes. So: no fixture in the harness exercises this class today, and the
harness carries no holed real-net data either — a hole-rimmed lobed fixture had to be
built from scratch, which is item 2 below.

---

## 2 and 3. The fixture, and what was measured

`HoledLobedNet` reuses round two's `LobedNet` verbatim (the asymmetric six-lobe dome,
`lobes=6, n=120, m=24, r0=5.0, amp=0.22, h=3.0, rimCols=13, asym1=0.10, asym2=0.07`,
`S=0.6, CH=0.35`, the exact fixture round three's own headline table anchors as
"six-lobe asym... 0.0000 m2") and removes one or more small rectangular patches of
quads from a low-`t` (near-apex) radial band, leaving the apex fan (t 0-1) always
intact — the holes sit AROUND the crown, matching Param's own wording. The hole's rim
is found by comparing the mesh's own boundary-edge set before and after removal, so the
method needs no foreknowledge of where the outer free edges are. `anchorHoleRims`
switches between the two variants the task asks for: `false` leaves the rim a FREE EDGE
ONLY (an opening cut into a supported shell with no ring beam); `true` appends every
hole-rim vertex to `Rim`, so each hole's rim becomes its OWN connected component of the
anchor set — a NEW seed family per hole, "how Param sometimes builds them."

```csharp
// tests/native_smoke would host this as a fixture builder; the probe carries it
// verbatim (scratchpad r3p/ProbeMain.cs). Reuses LobedNet (round two, already in the
// harness at Program.cs:23215) unmodified.

/// <summary>
/// HOLE-RIMMED LOBED FIXTURE (holed-net diagnosis, 2026-09-06): the
/// asymmetric six-lobe dome of the round-two/round-three diagnoses,
/// verbatim, with one or more DESIGN HOLES punched near the crown: small
/// rectangular patches of quads removed from a low-t (near-apex) radial
/// band, each hole specified in mesh INDEX space as (tLow, tHigh
/// exclusive, iCentre, iHalfWidth). The apex fan (t 0-1) is never
/// touched, so a solid disc always survives at the true summit; the
/// holes sit AROUND it, matching Param's "ring of rectangular openings
/// around the crown".
///
/// Each hole's rim is found by comparing the mesh's OWN boundary-edge
/// set (edges used by exactly one remaining face) before and after
/// removal: vertices boundary-only AFTER removal that were NOT
/// boundary-only before are the hole's rim, so the method is agnostic
/// to where the hole sits relative to the outer free edges between the
/// six rim arcs.
///
/// anchorHoleRims false: the hole rim is a FREE EDGE ONLY, exactly like
/// an interior opening cut into a supported shell with no ring beam --
/// it contributes no seed. anchorHoleRims true: every hole-rim vertex is
/// appended to Rim, so each hole's rim becomes its OWN new connected
/// component of the anchor set -- a NEW seed family the synthetic
/// fixtures before this wave never carried, one per hole -- exactly how
/// Param sometimes builds them (a support ring cast around an oculus).
/// </summary>
internal static (double[][] V, int[][] F, int[] Rim, int[] HoleRim)
    HoledLobedNet(
        int lobes, int n, int m, double r0, double amp, double h,
        int rimCols, double asym1, double asym2,
        IReadOnlyList<(int TLow, int THigh, int ICentre, int IHalf)> holes,
        bool anchorHoleRims)
{
    (double[][] v, int[][] fAll, int[] outerRim) =
        LobedNet(lobes, n, m, r0, amp, h, rimCols, asym1, asym2);

    // Reproduce LobedNet's own face emission order exactly, so the hole
    // rectangles (given in (t, i) ring-cell coordinates) land on the
    // faces they name: n apex-fan triangles first, then (m-1) * n
    // ring quads, t outer then i inner, matching LobedNet verbatim.
    var removed = new bool[fAll.Length];
    int faceIdx = n; // skip the n apex-fan triangles: never a hole site
    for (int t = 1; t < m; t++)
    {
        for (int i = 0; i < n; i++)
        {
            foreach (var hole in holes)
            {
                if (t < hole.TLow || t >= hole.THigh)
                    continue;
                int rel = (((i - hole.ICentre) % n) + n) % n;
                if (rel <= hole.IHalf || rel >= n - hole.IHalf)
                {
                    removed[faceIdx] = true;
                    break;
                }
            }
            faceIdx++;
        }
    }

    var kept = new List<int[]>();
    for (int k = 0; k < fAll.Length; k++)
        if (!removed[k])
            kept.Add(fAll[k]);

    static HashSet<int> BoundaryVertices(IReadOnlyList<int[]> faces)
    {
        var edgeCount = new Dictionary<(int, int), int>();
        foreach (int[] face in faces)
        {
            for (int c = 0; c < face.Length; c++)
            {
                int a = face[c], b = face[(c + 1) % face.Length];
                var key = a < b ? (a, b) : (b, a);
                edgeCount[key] =
                    edgeCount.TryGetValue(key, out int n0) ? n0 + 1 : 1;
            }
        }
        var boundary = new HashSet<int>();
        foreach (var kv in edgeCount)
        {
            if (kv.Value == 1)
            {
                boundary.Add(kv.Key.Item1);
                boundary.Add(kv.Key.Item2);
            }
        }
        return boundary;
    }

    HashSet<int> originalBoundary = BoundaryVertices(fAll);
    HashSet<int> newBoundary = BoundaryVertices(kept);
    int[] holeRim = newBoundary.Where(x => !originalBoundary.Contains(x))
        .OrderBy(x => x)
        .ToArray();

    int[] rimFinal = anchorHoleRims
        ? outerRim.Concat(holeRim).Distinct().OrderBy(x => x).ToArray()
        : outerRim;

    return (v, kept.ToArray(), rimFinal, holeRim);
}

// ---- the six fixtures measured -----------------------------------------

// ONE hole, OFF-SEAM (inside lobe 0's own wedge, i centred at 5, well
// clear of the valley seams at i = 10 and i = -10 = 110), t = 2..4 (a
// band close to the apex but never touching it), rim UNANCHORED.
HoledLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07,
    new[] { (TLow: 2, THigh: 5, ICentre: 5, IHalf: 2) },
    anchorHoleRims: false);   // "6holeoff-free"

// Same single off-seam hole, rim ANCHORED: one new seed family.
HoledLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07,
    new[] { (TLow: 2, THigh: 5, ICentre: 5, IHalf: 2) },
    anchorHoleRims: true);    // "6holeoff-anchor"

// SIX holes, one per lobe, centred off-seam (i = k*20+5): the "ring of
// rectangular openings around the crown" witness. Rims UNANCHORED.
HoledLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07,
    Enumerable.Range(0, 6)
        .Select(k => (TLow: 2, THigh: 5, ICentre: (k * 20) + 5, IHalf: 2))
        .ToArray(),
    anchorHoleRims: false);   // "6holering-free"

// Same six-hole ring, rims ANCHORED: six NEW seed families (twelve
// total with the six lobe arcs) -- a support ring cast around each
// oculus, how Param sometimes builds them.
HoledLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07,
    Enumerable.Range(0, 6)
        .Select(k => (TLow: 2, THigh: 5, ICentre: (k * 20) + 5, IHalf: 2))
        .ToArray(),
    anchorHoleRims: true);    // "6holering-anchor"

// SIX holes centred ON the valley seam lines (i = k*20+10), straddling
// the existing seam curves, rims UNANCHORED.
HoledLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07,
    Enumerable.Range(0, 6)
        .Select(k => (TLow: 2, THigh: 5, ICentre: (k * 20) + 10, IHalf: 2))
        .ToArray(),
    anchorHoleRims: false);   // "6holevalley-free"

// Same six on-seam holes, rims ANCHORED.
HoledLobedNet(6, 120, 24, 5.0, 0.22, 3.0, 13, 0.10, 0.07,
    Enumerable.Range(0, 6)
        .Select(k => (TLow: 2, THigh: 5, ICentre: (k * 20) + 10, IHalf: 2))
        .ToArray(),
    anchorHoleRims: true);    // "6holevalley-anchor"
```

### Headline table (all at S=0.6, CH=0.35; control is round three's own `6asym`)

| fixture | seed groups | seams | field max (CH) | courses | cells | plan-overlap dropped | cap | sampler void | engine Plan coverage |
|---|---|---|---|---|---|---|---|---|---|
| control (no holes) | 6 | 5 | 5.5314 (15.80) | 16 | 639 | 0 | 1, girth 3.69 m, KEPT | 0.18 m2 (pre-existing G3 residue) | 100.040% |
| 1 hole, off-seam, FREE | 6 (unchanged) | 6 | 5.5314 (15.80, unchanged) | 16 | 631 | 17 (+1 self-cross) | 1 emitted (girth 0.97) then DROPPED self-crossing | 0.0056 m2 (masks a real ~2.76 m2 cascade, see G6) | 100.437% |
| 1 hole, off-seam, ANCHORED | **7** (+1) | 6 | **3.2097 (9.17)** | **9** | 670 | 13 | 2 emitted, wrong location (girths 18.19, 1.98) | 2.82 m2 | 96.811% |
| 6 holes, ring, off-seam, FREE | 6 (unchanged) | 9 | 5.5314 (15.80, unchanged) | 16 | 667 | 2 | **0** — ridge-gate refusal x3 | 0.34 m2 | 100.109% |
| 6 holes, ring, off-seam, ANCHORED | **12** (+6) | 11 | **2.7821 (7.95)** | **8** | 730 | 27 | 1 emitted, wrong location (girth 2.72) | **6.23 m2** | 92.815% |
| 6 holes, on valley seams, FREE | 6 (unchanged) | 10 | 5.5349 (15.81, unchanged) | 16 | 651 | 1 | **0** — ridge-gate refusal x1 | 0.86 m2 | 99.331% |
| 6 holes, on valley seams, ANCHORED | **12** (+6) | 11 | **2.8809 (8.23)** | **8** | 794 | 19 | 1 emitted, wrong location (girth 1.96) | **6.92 m2** | 91.789% |

The single clearest number in the table: anchoring a hole rim always makes coverage
WORSE than leaving the identical hole as a free edge, by roughly 30-500x measured here
(0.0056 to 2.82 m2 for the single hole; 0.34 to 6.23 m2 for the ring). Building a
support ring around an oculus, which Param says he sometimes does, is measured to be
the worse of his two real practices on this engine, not the safer one.

---

## 4. Per-mechanism attribution, in the G1-G4 vocabulary plus what is new

**G1 (guide pinch-out), reused but MULTIPLIED.** Every hole-rimmed variant's "REFUSED"
list carries many more small CH/64-scale refusals than the control (the control has 5,
in courses 2-3 only, the six-fold merge already known; the ring/valley variants carry
20-30, scattered from course 11 to course 15). Each hole, even one that never touches an
existing seam, is enough of a geometric obstacle to the mesh graph that the geodesic
field's level curves fold locally in its lee exactly the way a real second family
would — measured directly: the unanchored single off-seam hole still recovers a SIXTH
seam curve where the hole-free control recovers five (`SeamCurves`, SkinPatterns.cs:1185,
confirmed working correctly — it traces whatever the field hands it), even though
`net.SeedGroups` at every hole-rim vertex still reads as one of the SIX EXISTING lobe
families (measured: `seed-group ids at rim = [2,1,0]`), never a new one. So G1's
mechanism (a guide curve ending short, at a free edge with nobody past it) needs no new
anchor to fire beside a hole; the hole's own silhouette is enough. This is the answer to
"whether seam curves are recovered around rims": yes, `SeamCurves` and `Trace`
(SkinPatterns.cs:1547) both generalise correctly to an interior opening with no code
change; it is the DOWNSTREAM consumers (`CloserBand`, `CapQualifies`, `KeepValidPlans`,
`TryExtendCloser`) that mishandle what those correctly-recovered curves imply.

**G3 (cap-lens crescents), reused, unaffected here.** The control's own 0.18 m2 residue
(the same class round three measured at 0.09-0.59 m2 on other forms) is present and
unchanged in every FREE variant that still emits a cap; the hole rim neither helps nor
hurts this specific mechanism.

**G5 — NEW — ANCHOR-PROXIMITY FIELD CAPTURE.** `RimDistanceFieldWithSeeds`
(SkinPatterns.cs:958) computes, at every vertex, the geodesic distance to the NEAREST
anchor; courses are cut from that field, so "the crown" is, by construction, wherever is
geodesically FARTHEST from every anchor. Anchoring a hole rim near the summit (rule
1.3.1's own definition — an anchor is an anchor regardless of where it sits) places a
brand-new, very close anchor almost at the architectural apex. Measured directly: the
field's own maximum COLLAPSES from 5.53 to 3.21 (single hole) or 2.78/2.88 (six-hole
ring/valley) — course count roughly halves (16 to 8-9) on every anchored variant, and
the resulting "crown" (wherever the collapsed field's own maximum now sits) is not the
architectural summit at all: the anchored single-hole variant emits TWO caps at girths
18.19 m and 1.98 m (against the true summit's own 3.69 m), and the six-hole ring/valley
anchored variants emit one cap each at 1.96-2.72 m, all at plan locations far from the
mesh centroid (0.03, -0.02) — e.g. (3.93, -0.10) and (3.76, 0.03), out near the flank.
This is not a local seam defect; it is a GLOBAL redefinition of the vault's own coursing
datum by whichever anchor happens to sit closest to the summit, and it owns the worst
coverage numbers measured (2.82-6.92 m2, up to 8% of the net uncovered). No G1-G4
mechanism describes this: G1-G4 are all about what happens AT a correspondence failure
band; this is about the FIELD ITSELF being redefined before any band logic runs. Owner:
`RimDistanceFieldWithSeeds`/`SeedGroupsOf` treating every rim vertex as an equally
weighted coursing datum regardless of its role (main springing line vs. a small support
ring near the crown).

**G6 — NEW — HOLE-ADJACENT CROWN CASCADE (measured on the single unanchored off-seam
hole).** The hole's local obstacle effect (G1, above) produces two NEW slabs the
control does not have, at courses 13 and 15, immediately below and immediately above
the hole. Course 13's `CloserBand` call reports `lows 1 highs 1` — by that height the
six lobe families have already merged into essentially one shared boundary, so the
"guide" curve is very close to the FULL remaining crown-ring circumference while
"other" is a small local loop the hole's own obstacle effect creates. `CloserBand`
(SkinPatterns.cs:6401) has no notion that the two sides of a seam might be so
mismatched in scale; it stitches one closer stone the length of the guide curve, and the
gap-filling safety net `TryExtendCloser` (7062, the "one-sided-full" branch at 6733-6746,
doc comment 6692-6710) then extends it further. Measured result: one closer stone at
area 2.1731 m2 against the ordinary-course median of 0.13 m2 — SEVENTEEN TIMES median
size. `KeepValidPlans` (SkinPatterns.cs:2925-2986) keeps cells in emission order with NO
area-based tie-break (line 2962-2980: the first cell processed that does not overlap an
ALREADY-KEPT cell wins; anything later that overlaps it is dropped, whichever is more
sensible); the oversized stone is processed first and evicts, by plan overlap, ALL TEN
of course 14's ordinary cells (~1.98 m2) plus the true crown cap itself, which
independently self-crosses and is dropped (`PlanSelfCrosses`, called inside
`KeepValidPlans` at line 2941) — the crown-cap self-cross/drop bug round two's fix 4
closed for the hole-free case (confirmed: 0 drops on this diagnosis's own control run)
REOPENS beside a hole that never even touches the crown loop. Net effect: roughly 2.76
m2 of legitimate, correctly-shaped geometry (ten course-14 stones, the keystone cap, four
course-15 closers) is silently replaced by one unbuildable 17x-oversized stone, while
BOTH the plan-area accounting (`PlanCoverage`, SkinPatterns.cs:1943, 100.437%) and an
independent grid/`PlanContains` sampler (99.99%) report the fixture as essentially
fully covered. Neither of the two coverage instruments this diagnosis and round three
both rely on would catch this defect; only a per-cell area census (already what this
probe's "KEPT CELL CENSUS BY MECHANISM" table does) shows it. This is the sharpest,
most Param-relevant finding of the whole diagnosis: a screenshot of this fixture would
show one visually wrong slab standing where eleven ordinary stones and a keystone
should be, and the acceptance check as currently specified (plan coverage near 100%)
would call it PASS.

**G7 — NEW — RIDGE-GATE FALSE POSITIVE BESIDE A HOLE-PERFORATED CROWN (measured on
both six-hole-ring variants, unanchored).** `CapQualifies` (SkinPatterns.cs:3277-3292)
refuses immediately, before any of its real tests run, whenever the traced level-curve
component at the candidate crown level is not CLOSED (`!component.Closed`, line
3286-3292) — precisely round three's own ridge gate, reused verbatim, with the identical
message: `"the top course is an OPEN strip, so its crown is a ridge and not a disc..."`.
Measured: it fires 3 times on the off-seam ring and once on the valley ring, even though
the true crown here IS a point apex (the small solid disc at t 0-1 that `HoledLobedNet`
deliberately never touches), not a ridge — six holes crowded closely enough around the
summit are enough to make the specific level-curve component the cap pass tries first
pass near or through a hole's free edge and come back open. No cap is emitted at all
(`Crown caps: 0` on both), and the cap pass never retries at a level nearer the true
apex once refused (matching round three's own finding 2a, "the seam machinery never
triggers" — here it is the CAP machinery that never retries). Coverage nonetheless
holds up reasonably (99.6% and 98.9%, small residues), because ordinary bands fold to a
top cut over the punctured summit much as they do at a genuine ridge, so architecturally
this ships as "no keystone where one should read" rather than as an open hole; the
`Crown caps: 0` line in the engine's own diagnostics string is measurable and is the
correct instrument for this class. Owner: `CapQualifies`'s reuse of `component.Closed`
as a proxy for "this is a ridge" — it is a correct test of THAT component, but the
method needs to try a level closer to the apex (above where the holes end) before
concluding the crown itself is a ridge.

**Interaction with the ON-SEAM variant.** Punching the same six holes ON the valley
seams instead of off them changes the numbers (10 seams recovered instead of 9, a
slightly larger residual void, 0.86 vs 0.34 m2) but not the mechanism census: the same
G1-multiplied refusal pattern, the same G7 ridge-gate refusal, no G6-style single-stone
cascade in either FREE ring variant (that cascade was specific to the ISOLATED single
hole; six holes close enough together apparently trip G7's blanket ridge refusal before
any one hole gets to build a G6-scale monster stone — a mitigating interaction worth
keeping in mind, not a fix).

---

## Verdict: is the hole rim a distinct defect class

Yes, and it is at least three distinct new mechanisms (G5, G6, G7), not a relocation of
G1-G4, plus a multiplication of G1 that is already in scope. Specifically:

- **G1 is confirmed to generalise to hole rims with no code change needed** — the
  pinch-out mechanism, and `SeamCurves`/`Trace`'s recovery of the meeting lines, both
  measured working correctly beside every hole tested, unanchored or anchored, on-seam
  or off. Round three's planned fix 3 (fall back to plan-area coverage for the pinch-out
  residual scan) will very likely close the G1-multiplied residues measured here too,
  since the mechanism is identical, just more frequent; **no eighth fix needed for this
  part**, though it should be RE-VERIFIED on a holed fixture once implemented, because
  today's fix-wave acceptance fixtures (finding 1's own list) do not include one.
- **G3 is unaffected** by a hole rim; no interaction measured.
- **G5 (anchor-proximity field capture) is entirely BLIND to every round-two and
  round-three fix.** None of the seven fixes listed in the findings doc, and none of
  G1-G4's owners, touch `RimDistanceFieldWithSeeds`/`SeedGroupsOf` (SkinPatterns.cs:958,
  1092) or the notion that an anchor's PROXIMITY to the crown should matter to how much
  of the field it is allowed to redefine. This needs new work: an eighth fix (or a
  ninth, since G6 and G7 also need their own) that gives the field construction a way to
  distinguish a MAIN coursing rim from a local support ring near the crown — for example,
  courses continuing to be measured from the outer/main rim's own distance field even
  where a nearer interior anchor exists, or an explicit flag on which rim groups
  participate in the coursing datum versus which merely seed their own local seam.
- **G6 (hole-adjacent crown cascade) is also BLIND to the seven listed fixes.** It lives
  in `CloserBand`/`TryExtendCloser`'s assumption that both sides of a seam are
  comparably scaled, and in `KeepValidPlans`'s order-only tie-break; none of the seven
  fixes touch either. Fix 1 (coalesce adjacent refusals) and finding 1's absorb rework
  might reduce HOW OFTEN a mismatched-scale seam is manufactured in the first place
  (fewer, better-merged slabs near a hole), but they do not address the underlying gap:
  `CloserBand` has no floor or check on the RATIO between its two sides' curve lengths,
  and `KeepValidPlans` has no signal to prefer a well-proportioned partition over an
  oversized one. This needs its own fix, and the acceptance instrument needs to change
  too: plan-area coverage (both the sampler's and `PlanCoverage`'s) is measured to be
  BLIND to this defect (both read ~100% covered here) — round three's own acceptance
  criterion ("closed, at course size") is the right one but must be checked with a
  per-cell size instrument, not an aggregate coverage percentage.
- **G7 (ridge-gate false positive) is a direct sibling of round three's finding 2, same
  code path, same root cause (a non-closed traced component), but the FIX finding 2
  proposes (name the ridge from the field/mesh itself, treat it with cross-ridge
  stones) does not apply here, because there is no ridge — the true crown is a point
  apex the cap pass simply never retries. This needs its own small fix (retry
  `CapQualifies` at a level above where the interior holes stop, before concluding the
  crown is a ridge), which is a natural EXTENSION of finding 2's planned work but is not
  automatically delivered by it; it should be named explicitly in the round-three fix
  plan rather than assumed closed.

In short: three of round three's four gap classes (G1, G3, and by extension the
existing seven fixes) transfer to the hole-rim case with no surprises. The hole rim
itself introduces a genuinely new failure surface the current plan does not reach:
**an eighth fix is needed for the field-capture defect (G5), a ninth for the
mismatched-scale closer cascade and its blind acceptance instrument (G6), and a tenth,
smaller fix for the cap pass's ridge-gate retry (G7)** — three items, not one, and G5 in
particular (field capture from an anchored hole ring) is measured to be the single
worst-covered configuration in this entire diagnosis, worse than doing nothing at all.
Param's own practice of sometimes anchoring a ring around an oculus is, on this engine
today, the actively worse of his two real choices.
