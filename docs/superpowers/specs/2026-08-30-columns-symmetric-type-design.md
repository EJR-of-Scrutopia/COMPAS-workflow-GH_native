# Columns stand symmetric and uniform, and Type gathers them

Date: 2026-08-30. Sub-project 7, the first of two from Param's review of
the installed rework on 2026-08-30 (the second, the surface: RES first
everywhere, Export one JSON, Display without outputs, the Frame
component, six panels and one icon family, is sub-project 8 and is out
of scope here). Branch feature/columns-symmetric-type off plugin main
a022b31. Amends docs/superpowers/specs/2026-08-28-columns-two-sliders-design.md
(sections 2, 3.4, 3.5, 3.7 and 4) as section 8 records; everything in
that spec not amended here stands.

## 1. Why

The engine of sub-project 3 mirrors the notch GROUPING about each span's
midpoint but places the FEET from each tree's own resultant force, and a
solved net's forces are never mirrored to the last digit and differ from
bar to bar. On the review arch the columns came out unmirrored, the
centre one leaned, and neighbouring lines disagreed with one another.
Three more rules made it worse: any two feet closer than the clearance
were merged, so leaning neighbours became accidental V's and X's; Ground
1 was refused whole when one flank trunk passed the 60 degree lean cap,
so it fell back to Ground 0 and the slider seemed dead; and the word
Ground did not say what the slider does. Param's rulings of 2026-08-26
already said it: mirroring is unconditional about the bar's midpoint,
the centre column stands outside the pairing, and the slider is Type,
how the columns meet the ground. This spec carries those rulings into
the feet.

## 2. Ports (binding)

| Slot | Name | Nick | Type | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| 0 | Result | RES | ResultParam item | required | The solved form finder. |
| 1 | Branching | B | integer item | 1 | Notches per tree: 1, 2 or 3. Clamped. |
| 2 | Type | T | integer item | 0 | How the trees meet the ground: 0 each on its own foot; 1 to 4 gathered onto that many mirrored feet per span; -1 Auto. 5 and above clamp to 4 with a warning. |

Slot 2 is RENAMED from Ground to Type and keeps its slot, so a saved
wire survives; the suggested value list is `0 · own feet`, `1 · one
central foot`, `2 · two feet`, `3 · three feet`, `4 · four feet`,
`Auto` (value -1), and an old list labelled Ground keeps working because
the values are unchanged. GUID, name and output unchanged. The block's
wire fields `GroundAsked` and `GroundPlaced` keep their names (the
contract is not reshaped for a label); every port, message, tooltip and
diagnostic says Type.

## 3. The engine (binding)

All of it in `ColumnPlacement`, pure arithmetic on arrays, harness
driven. Sections 3.1 to 3.3, 3.6 and 3.8 of the columns spec stand.

### 3.4 Loads and aims, symmetrised

A tree's resultant is the vector sum of its notches' transverse pulls,
as today. Before any foot is placed the resultants are symmetrised:

- Span frame. `c` is the unit plan vector from the span's first node to
  its last, `n` is `c` turned a quarter turn in plan (`(-c.y, c.x)`),
  the mirror plane is the vertical plane through the chord's midpoint
  normal to `c`. A resultant `R` reads as `(a, x, z) = (R.c, R.n, R.z)`.
- Symmetric spans. A span is SYMMETRIC when its free notches' chord
  parameters pair off about the midpoint: sorted ascending, `s_i +
  s_(n-1-i) = 1` for every `i`, within a QUARTER OF THE NOTCH SPACING,
  which in chord parameter is `0.25 x medianPlanEdge / chordLength`. The
  tolerance is on POSITION, not on the parameter: the same parameter
  bound is microns on a long span and centimetres on a short one, and
  the positions being compared come out of the SOLVE rather than off the
  curve the author drew, so a solved or relaxed net never mirrors its
  notches to the last digit. A quarter of the spacing is far tighter
  than the failures this test exists to catch, which move a notch by a
  whole spacing or more, and far looser than the millimetres a solver
  moves a node it meant to leave alone. Only a symmetric span is
  mirror-paired, family-averaged, banded per pair (3.5) and
  centre-merged (3.5). A span that is not (a crossing took an interior
  notch, or a bar end that is neither anchor nor rim put a notch at
  parameter 0) keeps every resultant it came in with, subject to the
  dead band below, takes each tree's band from that tree's own
  projection with no pair rule, merges nothing, and is counted in
  `Placement.AsymmetricSpans`; its trees' `Partner` is -1. Index `i` and
  index `m-1-i` of such a free list are not geometric mirrors, and
  pairing them would force equal and opposite along-chord pulls onto
  trees that do not straddle the mirror plane.
- Mirror pairs. The span's trees in grouping order (3.3) are indexed
  `0..m-1`; tree `i` pairs with tree `m-1-i`; with `m` odd the centre
  tree pairs with itself. For a pair `(t, t')`: `a_t := (a_t - a_t')/2`,
  `a_t' := -a_t`, and `x` and `z` are each replaced by the pair's mean.
  The centre tree's `a` is 0.
- Families. Spans alike in free-notch count, in Branching (one slider, so
  alike by construction) and in chord LENGTH within 10 percent of the
  family LEAD's form a FAMILY; a span matching no family is its own
  family. Length is in the key because a family shares an AIM, and a
  short steep span handed a long flat one's aim can stand its foot
  beyond its own anchors. Measuring each candidate against the lead
  rather than pairwise makes the bucketing order dependent and
  non-transitive (10, 10.9 and 11.8 fall into two families, and a
  different span order gives one); that is deliberate, because this is a
  cheap grouping of like with like and not an equivalence relation.
- What a family shares. The ALONG profile `a` and the VERTICAL profile
  `z`, at index `i`, and NOTHING ELSE. Tree `i` of every span of the
  family takes the family's mean `a[i]` and `z[i]`; the across-chord `x`
  stays the span's own, already mirrored within the span by the pair
  step above.
  The reason is that the span frame has one arbitrary choice in it,
  which end of the bar Pattern traced first, and only `a` and `z` are
  free of it. After the pair step `a` is antisymmetric and `z`
  symmetric, so reading a span from either end gives the same `a[i]` and
  `z[i]`, and tree `i` of one span is tree `i` of the family whichever
  way either bar was traced. `x` comes out NEGATED, so sharing it would
  need a rule for which way round a span is, and every such rule has a
  null: a rib lying IN the structure's own mirror plane, pulled equally
  from both sides, has no opinion, and would take the family's `x` in a
  frame that exists only because a curve was drawn left to right. It
  would lean out of the plane it lies in, and to the other side if the
  same curve were redrawn. Leaving `x` alone also makes both congruences
  hold by construction: bars congruent by TRANSLATION (a barrel whose
  bars are traced in mixed directions) and by ROTATION (opposite ribs of
  a dome, chord and pull turned together) carry the same columns in the
  world with no test to get wrong.
- Dead band. An aim within `PlumbDegrees = 2` of vertical is vertical.
  This applies to every tree of every span, mirrored or not: a degree of
  residual lean out of a solved net is noise wherever it appears.
- The ring tree (3.2) has no mirror partner and no family; it is not
  symmetrised and keeps its own resultant.
- `Tree.Resultant` holds the symmetrised vector, rebuilt from `(a, x,
  z)` in the span's own frame; `Tree.RawResultant` keeps the original
  for the diagnostics. `Tree.Load` (the per-notch vertical loads that
  set the member forces) is NOT averaged: the forces a tree reports are
  its own; only where it stands is shared.

`ColumnPlacement.Symmetrise(placement, nodes, bars)` does all of this
and returns the largest angle, in degrees, between any tree's raw aim
and its symmetrised aim (the asymmetry removed), measured. It runs once
per `Place` and guards itself: a second call with the same
`Trees.Count` returns the stored answer, and a call after the tree count
changed runs again, so a tree added to a `Placement` is never left
standing on its raw aim in silence.

### 3.5 Feet

- Type 0: each tree's foot is where the ray from its main notch along
  `MouldGeometry.AimFrom(Resultant)` (the symmetrised pull; AimFrom
  negates it itself) meets the ground. Never refused. A tree whose
  main notch projects onto the span midpoint takes this foot at every
  Type (see Type N).
- Type N (1 to 4): the span's chord is cut into N equal bands about its
  midpoint; the band is decided PER MIRROR PAIR: the pair member on the
  first half takes the band its main notch projects into (`floor(s x
  N)` on the chord parameter `s`), its partner takes the mirrored band
  `N-1-band`, so mirrored trees land in mirrored bands whatever the
  band boundaries; a centre tree (its own partner) at an ODD N takes
  the central band and at an EVEN N takes its Type 0 foot, which is in
  the mirror plane; each band with a tree gets one foot at the plan
  CENTROID (the plain mean) of its trees' main notches, at ground level.
  The mean, not the centre of their axis-aligned bounding box: a
  reflection about the span's mirror plane is affine but not axis
  aligned, so the box does not commute with it unless the chord runs
  along an axis or the band's X and Y extremes fall on the same two
  notches, and mirrored bands then get feet that are not mirror images.
  Then every tree is checked: a trunk (foot to fork, or the single member
  of a one-notch tree) that would lean past `MaxLeanDegrees` (60) to its
  band foot is PEELED: that tree stands on its Type 0 foot instead, and
  is counted in `Level.Peeled`. A band that loses trees that way REBUILDS
  its foot from the mains of the trees still standing on it, and the cap
  is judged again; the peel only ever takes trees off a band, so this
  settles. A band with no survivors builds no foot. The level is never
  refused for it, and where EVERY non-ring tree peels the level is Type
  0's geometry exactly, which section 4 says in as many words.
- Merging. Feet merge in ONE case only: a mirrored pair (3.4) whose two
  feet lie within the clearance of each other merges onto the plan MEAN
  of the two, at ground, counted in `Level.FeetMerged`. The mean, not the
  span's chord midpoint: a pair's two feet differ only in their
  along-chord part, so the clearance test bounds how far apart they are
  ALONG the chord and says nothing about how far off it they sit, and on
  a bar that curves in plan the innermost notches sit off the chord by
  the plan sagitta. Merging onto the chord midpoint moved such a pair
  sideways by that sagitta, out from under its own bar. On symmetric
  geometry the mean is in the mirror plane, which is where the pair's own
  symmetry puts it. Any other
  two feet (different pairs, different spans, the ring foot) closer than
  the clearance stay two and are counted in `Level.FeetClose`. Feet at
  the SAME point (two band feet built from the same mains, as at a
  crossing) are one node, which is neither a merge nor a close pair.
  The ring tree's foot is fixed by 3.2 and never merges.

### 3.7 Judged, never refused

For every level the engine measures, as today: the worst trunk lean, the
worst per-foot alignment (3.7 of the columns spec), the member and net
collisions (3.7 of the columns spec, unchanged tests). None of them
refuses a level. `Level.Feasible` now means `Collisions == 0`, and Auto
READS that field rather than recomputing the test; `Level.Rule` and
`Level.Value` name the worst measure for the diagnostics (`"lean"`,
`"alignment"`, `"collision"`, or `"none"`).

The lean is at most 60 by construction with one narrow caveat: the peel
of 3.5 runs BEFORE the centre merge and is not re-run after it, while
the lean is measured after. A merge moves each of the pair's two feet by
half the gap between them, which the clearance bounds at half a
clearance, so a trunk sitting just under the cap can be reported a
fraction past it and `Level.Rule` can then read `"lean"`. The move is
toward the pair's own centre and is bounded; re-running the peel after
the merge would trade that for a foot the merge had already welded
walking away again.

Type N asked: level N alone is built and placed; `GroundPlaced ==
GroundAsked`. Auto (`GroundAsked = -1`): levels 4 down to 0 are all
built; the one with the shortest load path (`sum over members of axial
force x length`) among those with no collision is placed; when every
level collides, the shortest load path of all; ties go to the higher
level.

## 4. Diagnostics (binding)

Source "Columns". Renamed and reworded:

- `columns.type` replaces `columns.ground`. Info: `Type asked N, placed
  N: each span's trees gather onto up to N feet about its midpoint; F
  feet built` (or, for 0, `every tree stands on its own foot; F feet`).
  With `Peeled > 0`, still INFO, and `... ; P trunk(s) stand on their own
  feet because a trunk to the shared foot would lean past 60 degrees`: a
  peel is the rule working, not a fault, and the canvas carries it as a
  Remark. Where EVERY non-ring tree peeled the gathering clause is
  replaced by `nothing gathered: every trunk to the shared feet would
  lean past 60 degrees; the columns stand as Type 0`, because the
  geometry that comes back is Type 0's and saying the trees gathered
  would say the opposite of what the author is looking at. Context:
  asked, placed, peeled, feet.
- `columns.symmetry` (info, new): `S spans with trees in K families; feet
  mirrored about each span's midpoint and shared across each family; the
  largest aim moved D degrees; C centre tree(s) standing in the mirror
  plane`, and, when `AsymmetricSpans` is nonzero, `; S spans placed
  unmirrored: a crossing or a free end breaks their symmetry`. Spans WITH
  TREES, not every span: one whose free notches were all claimed by a
  crossing or by the ring tree joins no family. Only a centre tree's
  along-chord pull is zeroed, so it stands in the mirror plane rather
  than plumb. Context: spans, families, moved, centres, unmirrored.
- `columns.feet_merged` (info) now counts centre-pair merges only, says
  so, and says the pair stands at the mean of its own two feet, in its
  span's mirror plane.
- `columns.feet_close` (warning, new): `F pairs of feet closer than the
  clearance stand separately; raise Type to gather them, or space the
  principal lines`.
- `columns.alignment` (warning, new): when the worst per-foot alignment
  exceeds `AlignmentDegrees` (30): `a foot's push is A degrees off the
  thrust its trees ask for; the foundation sees that as thrust`.
- `columns.collision` (warning) at any level, not only 0: text as today
  with "even standing alone" removed.
- `columns.load_path` as today; with Auto the scored levels list every
  level with its load path and a `collides` mark.

Diagnose's cross-checks that read `columns.ground` read `columns.type`.
Every mention of Ground in ColumnsComponent's messages, tooltips and
value list says Type. Counts read as counts: `1 foot`, `1 family`, `1
span`, `1 pair`. The component carries a `Message`, `Type N, F feet`,
with `, P peeled` when trunks peeled and `, unmirrored S` when spans were
placed unmirrored, prefixed `Auto: ` under Auto, so the slider's answer
is legible without opening Diagnose.

## 5. Files (binding)

- `plugin/native_v02/Components/ColumnPlacement.cs`: `Symmetrise`,
  `Tree.RawResultant`, `Level.Peeled`, `Level.FeetClose`, the Type N
  peel, the one-case merge, judged-not-refused, Auto's preference.
- `plugin/native_v02/Components/ColumnsComponent.cs`: the port, the
  value list, the diagnostics of section 4.
- `tests/native_smoke/Program.cs`: section 6.
- `plugin/native_v02/Contracts/MouldContracts.cs`: the `GroundPlaced`
  comment, which still described a fallback.
- `docs/component-taxonomy.md`: the Columns row.
- `docs/superpowers/specs/2026-08-28-columns-two-sliders-design.md` is
  NOT edited; section 8 here is the amendment record.

## 6. Testing (binding)

`ValidateColumnPlacement` gains these cases, every one pure and every
one failing against the engine as it stands today (the implementer
names the wrong behaviour each fails against):

- Mirrored feet: a parabolic arch of 11 notches, span 10, rise 2.5,
  across pulls mirrored in shape but the left flank scaled by 1.1 and a
  1 degree along-chord skew on every notch. Type 0. For every mirrored
  pair the feet satisfy `foot_i + foot_(m-1-i) = 2 x midpoint` in plan
  to 1e-9; the centre foot is on the midpoint to 1e-9 and its member is
  vertical; `Symmetrise` reports the asymmetry removed above half a
  degree, the skew on every notch being a whole one.
- One family: the same arch four times, offset in Y by 0, 1, 2 and 3, the
  second with every pull scaled by 1.05, the third with its nodes in
  REVERSED bar order, the fourth turned through 180 degrees in plan with
  its pull turned with it. Type 0. Read in each span's own frame, foot
  `i` of every bar has the same along-chord offset from its span's
  midpoint to 1e-9 and the across-chord offset negated where that span's
  own frame reads the world pull negative; and the across-chord FORCE
  each span carries is the hand-derived `lateral` with its own sign. The
  backwards bar and the rotated bar hold TRIVIALLY now, which is the
  point of the rule they are here for: what they measure is that the
  shared `a` and `z` profiles land at the right index, and that each
  span's own `x` reaches the world unchanged. The case that distinguishes
  sharing `x` from not sharing it is the crown bar below, not this one,
  since all four of these bars carry the same across.
  The same fixture runs again at Type 2, where each span's band feet must
  be mirror images in its own frame and its centre tree must stand in the
  mirror plane. That run drives the band path on a span traced backwards
  and on a rotated one, which nothing else does; it does NOT distinguish
  the smaller-chord-parameter rule from the grouping index, because on a
  plan-monotone bar the chord parameter rises with the grouping order
  whichever way the bar was traced. Only a bar that is not plan monotone
  would separate them, and no fixture builds one.
- A rib in the structure's own mirror plane: three congruent bars, ten
  wide, at y = -2, 0 and +2, one family. The flanks are pulled sideways
  toward the middle by +0.5 and -0.5 and the crown, lying in the mirror
  plane, has no across-chord pull at all; the along bends are 0.2, 0.5
  and 0.2 and the down magnitudes 1.0, 1.2 and 1.0, so the shared
  profiles are `a = side x 0.3` and `z = -16/15`. Type 0. Every tree
  carries `(side x 0.3, its own span's across, -16/15)` and stands
  `side x 0.28125 z` along its chord and `(across x 15/16) z` across it;
  the crown bar's feet stand exactly under their own notches ACROSS the
  chord, to 1e-9. Any rule that pooled `x` over the family hands the
  crown 1/3 and leans it `0.3125 z` out of the plane it lies in, to
  whichever side its node order picked.
- Families are not notch counts: a ten metre shallow span whose pulls
  lean outward beside a three metre steep span of the same free-notch
  count whose pulls hang plumb. `Families` is 2, and every foot of the
  short span stands within its own chord, plumb under its own main
  notch. Keyed on the count alone the short span's outermost foot lands
  at -0.78, beyond its own anchor.
- A span placed unmirrored: an eleven-notch arch crossed at its position
  3 by a lower-indexed bar, so its free notches are 0.1, 0.2, 0.4, 0.5,
  0.6, 0.7, 0.8, 0.9 and 0.7 has no partner. `AsymmetricSpans` is 1, the
  level is placed, every tree of that span keeps its raw resultant and
  takes `Partner` -1, and the crossing bar's own span, symmetric at
  parameter 0.5, IS mirrored (its 0.3 along-chord pull comes back
  zeroed). The same arch untouched reports `AsymmetricSpans` 0.
- A bar that curves IN PLAN, chord along `(1, 2)/sqrt(5)`, ten nodes on a
  plan parabola of sagitta 2 with the anchors on the chord, pulls leaning
  inward. Three cases on it: at Type 2 the two band feet are the exact
  mirror images `(-2, 40/27)` and `(2, 40/27)` in the chord frame, where
  the bounding-box centre gives `(-2.0185, 1.4198)` against `(2,
  1.3827)`; at Type 0 the centre pair merges onto `(0, 160/81)`, the mean
  of its two feet, where the chord midpoint is `(0, 0)`, two units away;
  at Type 1 two trunks peel and the band foot rebuilds from the six
  survivors at `(0, 832/486)` rather than staying at the eight-main
  `(0, 40/27)`.
- Type 1 placed, not refused: the wide arch (rise 2.5 on span 10) at
  Type 1 gives `GroundPlaced == 1`, `Peeled >= 2` (the flank trunks),
  every trunk's lean at most 60 + 1e-9, no level with `Rule == "lean"`
  in `Tried`, and the centre trees on the midpoint foot.
- Neighbours stay apart: a narrow bay (span 4, 7 notches, strong
  inward across pulls) at Type 0 where two neighbouring raw feet fall
  within the clearance: the feet count equals the tree count (no
  merge) and `FeetClose >= 1`.
- The centre pair merges: an even-count arch (10 notches) with node 4
  nudged two hundredths off the mirror, so the pair's own mean (4.49) is
  not the span's chord midpoint (4.5). Its two innermost mirrored feet
  fall within the clearance of each other and give one foot at the MEAN
  of the two, 4.49, with `FeetMerged == 1`. The nudge is a fiftieth of
  the notch spacing, well inside the quarter-spacing tolerance of 3.4, so
  the span is still mirrored; that it is also measures the tolerance
  against the exact-coincidence bound it replaced, under which this span
  reverts to unmirrored and nothing merges at all.
- Auto prefers no collision: on the wide arch at Auto, `GroundPlaced`
  equals the level the check itself recomputes from `Tried` by the
  section 3.7 rule (shortest load path among collision-free levels,
  ties to the higher).
- Existing cases: the sub-project 3 case that expected Ground 1 to be
  REFUSED on a wide arch (if present) is rewritten to expect it placed
  with peeled trunks; every other case keeps passing unchanged.
- The idempotence guard, both halves: a second `Symmetrise` on the same
  trees returns the stored answer and touches nothing, and a call after a
  tree has been ADDED runs again. The added tree holds the arch's centre
  notch, so the free notches stay symmetric and the span goes from nine
  trees with a centre to ten in five pairs: `Partner` is rebuilt ten
  long, `CentreTrees` falls to 0, and the added tree's `RawResultant` is
  captured.
- Component pins: the Columns nicknames in `SpineComponentContracts`
  become `RES, B, T`; the persistent parameter count stays 12 and the
  component count 19, both ENFORCED as failures.
- Margins: the asymmetry removed is asserted above half a degree, the
  fixture's own skew being one degree, rather than merely above zero; and
  the cross fixture's two coincident feet are called a WELD, with
  `FeetMerged == 0` asserted there, rather than a merge.

## 7. What breaks on the canvas

Nothing rewires: slot 2 keeps its slot and values; the label reads
Type; an old Ground value list still drives it. Definitions that showed
Ground 0 after asking for 1 now show Type 1 with peeled flank trunks,
and their feet move to mirrored positions.

Three things an author does meet:

- The old value list is a separate canvas object and is not relabelled on
  load. A list still titled **Ground**, whose first item still reads `0 ·
  standalone`, hangs off a port now labelled **Type** and still drives
  it; nothing replaces it, and placing the new list from the component
  menu does nothing while the old one is wired, because a suggested list
  skips any input that already has a source. Deleting the old list first
  is the whole fix, and the clamp warning says so.
- The diagnostic code `columns.ground` is now `columns.type`, so a
  downstream filter on Diagnose's `Code` output stops matching.
- A definition that was CLEAN can now show warnings, and one that showed
  warnings can now show fewer. `columns.collision` fires at every level
  where it used to fire at Ground 0 alone, and `columns.feet_close` and
  `columns.alignment` are both new warnings, so Diagnose's own Message
  line can flip from clean to N warnings on reopening a working file;
  the other way, the refusal warning is gone and `columns.type` is INFO
  even where trunks peel, so a file that was warned at about a refused
  level comes back quiet. Nothing about the geometry got worse either
  way; the measures are simply being reported where they were silent,
  and not reported where there is no fault.

## 8. Amendments to the columns spec of 2026-08-28

- Section 2: slot 2 is Type, as section 2 here.
- Section 3.4: resultants are symmetrised per mirror pair and per
  family before placement, as 3.4 here.
- Section 3.5: Type N peels trunks past the lean cap onto their own
  feet instead of refusing; merging happens for centre pairs only, as
  3.5 here.
- Section 3.7: levels are judged, never refused; Auto prefers
  collision-free levels, as 3.7 here.
- Section 4: `columns.ground` is `columns.type`; `columns.symmetry`,
  `columns.feet_close` and `columns.alignment` added; `columns.feet_merged`
  narrowed to centre pairs; `columns.collision` at every level.

## 9. Out of scope

Animate and the Frame component, Deconstruct, Monitor, the RES-first
port order, Export, Display, panels and icons (sub-project 8). The
fork rule, the ring tree, the loads, the block and its validation. Any
change to `MouldGeometry.AimFrom` or the 60 degree cap.

## 10. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino. Check for OneDrive name-clash
files before every build and commit. git add by explicit path only.
