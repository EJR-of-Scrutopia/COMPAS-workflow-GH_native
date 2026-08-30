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
- Mirror pairs. The span's trees in grouping order (3.3) are indexed
  `0..m-1`; tree `i` pairs with tree `m-1-i`; with `m` odd the centre
  tree pairs with itself. For a pair `(t, t')`: `a_t := (a_t - a_t')/2`,
  `a_t' := -a_t`, and `x` and `z` are each replaced by the pair's mean.
  The centre tree's `a` is 0.
- Families. Spans with the same free-notch count and the same
  Branching (hence the same tree count and layout) form a FAMILY. Every
  span of a family is read in the frame of the family's first span: a
  span whose chord points against that span's chord (`c.c_first < 0`)
  is read REVERSED, its tree index `i` reading as `m-1-i` and its `a`
  and `x` negated. Tree `i` of every span in the family then takes the
  family's mean `(a, x, z)` at index `i`. Every principal line of a
  family therefore has the same columns in its own frame.
- Dead band. An aim within `PlumbDegrees = 2` of vertical is vertical.
- The ring tree (3.2) has no mirror partner and no family; it is not
  symmetrised and keeps its own resultant.
- `Tree.Resultant` holds the symmetrised vector, rebuilt from `(a, x,
  z)` in the span's own frame; `Tree.RawResultant` keeps the original
  for the diagnostics. `Tree.Load` (the per-notch vertical loads that
  set the member forces) is NOT averaged: the forces a tree reports are
  its own; only where it stands is shared.

`ColumnPlacement.Symmetrise(placement, nodes, bars)` does all of this
and returns the largest angle, in degrees, between any tree's raw aim
and its symmetrised aim (the asymmetry removed), measured.

### 3.5 Feet

- Type 0: each tree's foot is where the ray from its main notch along
  `MouldGeometry.AimFrom(-Resultant)` (symmetrised) meets the ground.
  Never refused.
- Type N (1 to 4): the span's chord is cut into N equal bands about its
  midpoint; a tree belongs to the band its main notch projects into;
  each band with a tree gets one foot at the plan centre (midpoint of
  the extremes) of its trees' main notches, at ground level; mirrored
  trees land in mirrored bands by construction. Then every tree is
  checked: a trunk (foot to fork, or the single member of a one-notch
  tree) that would lean past `MaxLeanDegrees` (60) to its band foot is
  PEELED: that tree stands on its Type 0 foot instead, and is counted
  in `Level.Peeled`. A band whose trees were all peeled builds no foot.
  The level is never refused for it.
- Merging. Feet merge in ONE case only: a mirrored pair (3.4) whose two
  feet lie within the clearance of each other merges onto the chord
  midpoint in plan, at ground, counted in `Level.FeetMerged`. Any other
  two feet (different pairs, different spans, the ring foot) closer than
  the clearance stay two and are counted in `Level.FeetClose`. The
  ring tree's foot is fixed by 3.2 and never merges.

### 3.7 Judged, never refused

For every level the engine measures, as today: the worst trunk lean
(which is at most 60 by construction now), the worst per-foot alignment
(3.7 of the columns spec), the member and net collisions (3.7 of the
columns spec, unchanged tests). None of them refuses a level.
`Level.Feasible` now means `Collisions == 0` and is used by Auto alone;
`Level.Rule` and `Level.Value` name the worst measure for the
diagnostics (`"lean"`, `"alignment"`, `"collision"`, or `"none"`).

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
  Warning when `Peeled > 0`: `... ; P trunk(s) stand on their own feet
  because a trunk to the shared foot would lean past 60 degrees`.
  Context: asked, placed, peeled, feet.
- `columns.symmetry` (info, new): `S spans in K families; feet mirrored
  about each span's midpoint and shared across each family; the largest
  aim moved D degrees; C centre tree(s) plumb`. Context: spans,
  families, moved, centres.
- `columns.feet_merged` (info) now counts centre-pair merges only, and
  says so.
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
value list says Type.

## 5. Files (binding)

- `plugin/native_v02/Components/ColumnPlacement.cs`: `Symmetrise`,
  `Tree.RawResultant`, `Level.Peeled`, `Level.FeetClose`, the Type N
  peel, the one-case merge, judged-not-refused, Auto's preference.
- `plugin/native_v02/Components/ColumnsComponent.cs`: the port, the
  value list, the diagnostics of section 4.
- `plugin/native_v02/Components/DiagnoseComponents.cs`: the code rename.
- `tests/native_smoke/Program.cs`: section 6.
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
  vertical; `Symmetrise` reports the asymmetry removed greater than 0.
- One family: the same arch three times, offset in Y by 0, 1 and 2, the
  second with every pull scaled by 1.05, the third with its nodes in
  REVERSED bar order. Type 0. Read in each span's own frame, foot `i`
  of every bar has the same along-chord and across-chord offset from
  its span's midpoint to 1e-9; the reversed bar's feet mirror correctly
  (its index mapping is exercised).
- Type 1 placed, not refused: the wide arch (rise 2.5 on span 10) at
  Type 1 gives `GroundPlaced == 1`, `Peeled >= 2` (the flank trunks),
  every trunk's lean at most 60 + 1e-9, no level with `Rule == "lean"`
  in `Tried`, and the centre trees on the midpoint foot.
- Neighbours stay apart: a narrow bay (span 4, 7 notches, strong
  inward across pulls) at Type 0 where two neighbouring raw feet fall
  within the clearance: the feet count equals the tree count (no
  merge) and `FeetClose >= 1`.
- The centre pair merges: an even-count arch (10 notches) whose two
  innermost mirrored feet fall within the clearance of each other gives
  one foot on the midpoint and `FeetMerged == 1`.
- Auto prefers no collision: on the wide arch at Auto, `GroundPlaced`
  equals the level the check itself recomputes from `Tried` by the
  section 3.7 rule (shortest load path among collision-free levels,
  ties to the higher).
- Existing cases: the sub-project 3 case that expected Ground 1 to be
  REFUSED on a wide arch (if present) is rewritten to expect it placed
  with peeled trunks; every other case keeps passing unchanged.
- Component pins: the Columns nicknames in `SpineComponentContracts`
  become `RES, B, T`; the persistent parameter count stays 12 and the
  component count 19.

## 7. What breaks on the canvas

Nothing rewires: slot 2 keeps its slot and values; the label reads
Type; an old Ground value list still drives it. Definitions that showed
Ground 0 after asking for 1 now show Type 1 with peeled flank trunks,
and their feet move to mirrored positions.

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
