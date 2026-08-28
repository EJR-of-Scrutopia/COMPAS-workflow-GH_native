# Columns with two sliders: every notch held, grouped into trees, footed by rule

Date: 2026-08-28. Sub-project 3 of 6 from the mould rework brainstorm of
2026-08-27. Branch feature/columns-two-sliders off plugin main 4bf1d9d.
Implements section 9 of docs/superpowers/specs/2026-08-27-res-spine-design.md,
which is binding except where section 8 below amends it with Param's
approval of 2026-08-28.

## 1. Why

The Columns component still chose WHERE arms stand by solving each bar as
a beam and searching arrangements. Under the machine as Param describes
it every notch of every principal line is a joint with two steppers and a
column head; there is nothing to choose. What remains to decide is how
the heads group into trees (Branching) and how the trees reach the ground
(Ground), and both of those are the author's sliders. Everything the
search produced, the symmetry gates, the centre trigger, the mirrored
pool, existed to repair the choice it should never have made.

Three faults from Param's screenshots are the acceptance cases: kinked
forks (the fork sat on the main column's aim line, not between its foot
and its notch), trunks past seventy degrees to one foot (nothing refused
an infeasible Ground), and a single foot off the centre of a symmetric
arch (mirroring was about the bar, not the span, and the beam search put
an odd number of arms on one side).

## 2. Ports (binding)

| Slot | Name | Nick | Type | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| 0 | Result | RES | ResultParam item | required | The solved form finder. |
| 1 | Branching | B | integer item | 1 | Notches per tree: 1, 2 or 3. Clamped. |
| 2 | Ground | G | integer item | 0 | 0 standalone; 1 to 4 shared feet per span; -1 Auto. 5 and above clamp to 4 with a warning (an old Type wire). |

Columns Per Line, Type, Fork and Branches are removed. Slot 0 is
unchanged so the Result wire survives. One suggested value list, on slot
2, items `0 · standalone`, `1 · one central foot`, `2 · two feet`,
`3 · three feet`, `4 · four feet`, `Auto` (value -1). The output is one
Result, as now. The component class is renamed `ColumnsComponent`; its
GUID `b1f4c7a2`-family value and display name "Columns" are unchanged.

## 3. The engine (binding)

All of this lives in `ColumnPlacement`, a static class of pure arithmetic
on arrays (Point3d, Vector3d, int[], double[]; no Curve, no Mesh, no
Unitize), so the smoke harness drives every rule.

### 3.1 Spans

A bar (a principal run of net vertex indices) is cut into spans at:

- every anchor on the bar (the usual case: one span, anchor to anchor;
  a HELD RING, anchors mid-bar, gives two half-spans and the ring gets
  no column because an anchor is never a head);
- a ring-tree head (3.2), so a bar ending on a free rim runs anchor to
  rim notch.

A plain crossing of two bars does NOT split a span (amendment, section
8). The crossing notch is held once: it belongs to the lower-indexed bar
and the other bar skips it as already held.

### 3.2 The ring tree

A bar END is a free-rim end when its last node is not an anchor and lies
on a perimeter loop that contains no anchor. When at least two bars have
a free-rim end, the ring tree is placed first: one foot at the plan point
minimising the sum of squared distances to the end tangent lines (each
bar's last two nodes in plan; the least-squares intersection), one
branch from that foot's fork to each bar's rim notch, where the fork
sits on the segment from the foot to the rim notch nearest the foot in
plan at the fork fraction. The rim notches are then held and end their
spans. If the least-squares system is singular (parallel tangents) the
foot is the plan centre of the rim notches.

### 3.3 Grouping, per span

Free notches of the span (anchors and held notches excluded, in bar
order) split into a LEFT half, a CENTRE notch when the count is odd, and
a RIGHT half. Each half is grouped from the centre outward into trees of
Branching consecutive notches; the remainder, fewer than Branching,
forms one smaller tree at the anchor end. The right half is the mirror
of the left. The centre notch is a single-column tree. Every notch is in
exactly one tree.

The MAIN notch of a tree is its innermost notch (nearest the span
midpoint by index); mirrored trees therefore have mirrored mains.

### 3.4 Loads

Unchanged from today: `MouldGeometry.BarLoads` (infill pull per notch,
magnitude, excluding the bar's own edges) and `BarTransverse` (the
across-bar remainder) per bar. A tree's resultant is the vector sum of
its notches' transverse pulls; each member carries the vertical load of
the notches above it; axial force = carried vertical / cos(lean).

### 3.5 Feet

- Ground 0: each tree's foot is where the ray from the main notch along
  `MouldGeometry.AimFrom(-resultant)` meets the ground; AimFrom caps the
  lean at `MaxLeanDegrees`. Never refused.
- Ground N (1 to 4): the span's chord in plan (first node to last node)
  is cut into N equal bands about its midpoint; a tree belongs to the
  band its main notch projects into; each band with at least one tree
  gets one foot at the plan centre (midpoint of the extremes) of its
  trees' main notches, at ground level. An empty band gets no foot; the
  count placed is the count built.
- Feet from different spans or bars closer in plan than the clearance
  (3.7) merge into one foot at their plan centre.
- The ring tree's foot is fixed by 3.2 and takes part in merging.

### 3.6 Fork and members

For a tree with more than one notch the fork lies ON THE SEGMENT from
its foot to its main notch, at height `ground + ForkFraction x (mainZ -
ground)`, `ForkFraction = 0.65`, a constant. Members: foot to fork
(trunk), fork to main notch (main branch, collinear with the trunk by
construction), fork to every other notch of the tree (branches). A
single-notch tree is one member foot to notch. Every member is emitted
lower end first. Two trees on one foot share the foot node exactly.

There is no fork raising. `ForksRaised` is always 0 (amendment, section
8).

### 3.7 Rejection

A candidate Ground level is REFUSED when any of these holds, and the
diagnostic names the level, the rule and the measured value:

- lean: a trunk (foot to fork, or a single-notch member) leans past
  `MaxLeanDegrees` (60) from vertical, measured foot to upper end;
- alignment: judged PER FOOT. The vector sum of the axial forces of the
  trunks leaving a foot is more than `AlignmentDegrees` (30) off the
  vector sum of the pushes its trees ask for (each tree's `AimFrom`
  direction times its total load). Two mirrored trunks under plumb loads
  sum to a vertical push and pass; judging each trunk alone refused a
  central foot on every ordinary arch, since every trunk to a shared
  foot leans by construction. Branches are exempt; their off-thrust
  angle is reported;
- member collision: two members that share no end come closer than
  `Clearance = 0.05 x MedianPlanEdge` (segment-to-segment distance);
- net collision: a member's interior (samples at 1/8 .. 7/8 of its
  length) rises above the net, tested as sample Z greater than the Z of
  the nearest net vertex in plan plus the clearance.

Ground 0 is never refused for lean or alignment (AimFrom guarantees
both); a collision at Ground 0 is placed anyway and reported as a
warning, because a Result with no columns breaks the chain.

Ground N asked: levels N, N-1, ..., 0 are tried in order and the first
feasible one is placed. `GroundAsked = N`, `GroundPlaced` = the level
built. Auto (`GroundAsked = -1`): levels 4 down to 0 are all evaluated,
every feasible one is scored by LOAD PATH, `sum over members of axial
force x length`, and the minimum is placed; ties go to the higher level.

### 3.8 The block

`MouldColumnsDto` as today, with: `HeadNode[i]` resolved by
`ColumnsBlock`'s plan match, which is exact here because every head IS
a net vertex;
`Branching` = the slider; `GroundAsked` as above (-1 allowed, the one
contract validation change); `GroundPlaced` >= 0; `ForkFraction =
0.65`; `ForksRaised = 0`. `Trees`, `Heads`, `Forks`, `Feet` from
`MouldGeometry.ColumnsBlock` as now. `Frame = null` as now.

## 4. Diagnostics (binding)

Source "Columns". Kept from today: `columns.no_principal_runs` (error),
`columns.overlap`, `columns.bar_shape`, `columns.load_split`,
`columns.principal_source`, `columns.arm_load_total` renamed
`columns.head_load_total`, `columns.arm_load` renamed
`columns.head_load`, `columns.force_max`, `columns.lean`,
`columns.plumb_fallback`, `columns.demand_only`. Removed:
`columns.symmetry`, `columns.centre_added`, `columns.placement`,
`columns.settings`, `columns.branches`, `columns.forks_raised`,
`columns.foot_drift`, `columns.trunk_lean_exceeded`. New:

- `columns.spans` (info, one per bar): span count and the kind of each
  cut (anchor, ring, rim), notch count per span.
- `columns.grouping` (info): Branching, tree count, single-column
  count, remainder trees.
- `columns.ring_tree` (info) when a ring tree was placed: bars joined,
  foot position.
- `columns.ground` (info, or warning when placed < asked): asked, placed,
  and for every refused level the rule and value that refused it.
- `columns.load_path` (info): the placed arrangement's load path in
  N x model units; for Auto, every feasible level's score in context.
- `columns.feet_merged` (info) when any feet merged.
- `columns.branch_off_thrust` (info): worst branch angle off its notch's
  pull, the joint bending the machine takes.
- `columns.collision` (warning) at Ground 0 only, when placed with a
  collision.

Diagnose's `diagnose.forks_raised` cross-check is removed, and its
harness sub-check with it.

## 5. Files (binding)

- `plugin/native_v02/Components/ColumnsComponent.cs` (renamed from
  ColumnFinderComponents.cs): the component only: ports, value list,
  preview (unchanged look), reading the Result, calling the engine,
  writing the block, diagnostics.
- `plugin/native_v02/Components/ColumnPlacement.cs` (new): the engine,
  sections 3.1 to 3.7, arithmetic only.
- `plugin/native_v02/Components/BeamSolver.cs` (new, extracted): only
  `Response` and `SolveDense`, which Monitor uses for bar sag. Everything
  else of BeamSolver is deleted.
- `MouldComponents.cs`: `LeanFromVertical` moves into `MouldGeometry`;
  `ForkPoint`, `Solve3`, `BuildColumnTree` deleted (no production
  caller); `ForkOnLine` stays for Animate.
- `Contracts/MouldContracts.cs`: `GroundAsked >= -1`.
- `DiagnoseComponents.cs`: `forks_raised` cross-check removed.
- `tests/native_smoke/Program.cs`: section 6.
- `docs/component-taxonomy.md`: the Columns row.

Animate is untouched: it reads only `Nodes` and `Members`, needs members
lower-first and forks shared exactly, both kept.

## 6. Testing (binding)

Deleted: `ValidateBeamPlacement`, `ValidateForkPoint`,
`ValidateColumnTree`, `ValidateSharedFoot`, the `ArmsForBar` half of
`ValidateStiffnessSeparation` (its `LeanFromVertical` half moves to a
check on `MouldGeometry.LeanFromVertical`), the `forks_raised` sub-check
of `ValidateDiagnoseRules`. Kept: `ValidateColumnAim`,
`ValidateColumnsBlock`, `ValidateDeconstructColumnTrees`,
`ValidateMouldContract` (fixture gains `GroundAsked = -1` accepted and
`-2` refused).

New, every one driving `ColumnPlacement` by reflection on hand-built
arrays:

- Grouping: 9 free notches at Branching 2 give a centre single and four
  mirrored pairs with mirrored mains; 8 at Branching 3 give two triples
  and a single at each end; 5 at Branching 1 give five singles.
- Fork: on a hand-built tree the fork lies on the foot-to-main segment
  at 65% height, trunk and main branch collinear within 0.5 degrees.
- Wide arch: a shallow arch 12 wide and 2 high, Branching 1, Ground 1
  asked; the outer trunks lean past 60 degrees, so placed is 0 and the
  diagnostic names the lean that refused level 1.
- Centred foot: a symmetric arch with an odd notch count, Ground 1; the
  foot lies on the span's plan centre within a hundredth of the span;
  the same with an even count.
- Held ring: a bar with anchors at both ends and two mid-bar anchors
  gives three spans and no head on the anchors.
- Free rim: two bars ending on an anchor-free loop give one ring tree
  whose foot is the plan intersection of their end tangents within a
  hundredth of the span, and their rim notches are held once.
- Collision: two parallel members at half the clearance collide, at
  twice the clearance do not; a member whose midpoint rises above the
  nearest net vertex collides with the net.
- Auto: a case where Ground 1 and Ground 0 are both feasible and Ground 1
  has the shorter load path places 1 with `GroundAsked = -1`.
- Crossing: two bars sharing a node give that node one head, on the
  lower-indexed bar.

## 7. What breaks on the canvas

Columns' four old inputs are gone; a wire into Columns Per Line (slot 1)
now feeds Branching and one into Type (slot 2) feeds Ground, so an old
canvas keeps working with those values reinterpreted; Fork and Branches
wires are dropped on load. The old seven-item Type value list stays
wired to Ground; its 5 and 6 clamp to 4 with a warning; place the new
list from the component menu to get Auto. Deconstruct, Monitor, Animate
and Diagnose need no rewire.

## 8. Amendments to section 9 of the RES spine spec (approved 2026-08-28)

1. Fork raising is gone. With the fork on the foot-to-main-notch segment,
   the trunk's lean is the segment's lean and moving the fork cannot
   change it, so "no fork left to raise" never applies; lean past the cap
   refuses the level at once. Minimum load path cannot place the fork
   either (on a fixed segment its derivative runs the fork to the foot),
   so the fraction is a constant, 0.65, not a third slider.
2. A column head on a crossing bar is not an interior support and does
   not split a span; only anchors and ring-tree heads do. This is what
   makes Ground 1 on a cross one merged central foot.
3. The alignment bound (30 degrees) binds trunks only; branches report
   their off-thrust angle.
4. Ground N means N feet PER SPAN with coincident feet merged, not N feet
   for the whole form.

## 9. Out of scope

Animate's frame-zero columns and rigid rotation (sub-project 4).
Monitor's document 07 output set (sub-project 5). Any change to the
Python worker or wire. The tools/tree_forest Python twin, which keeps
its own algorithms.

## 10. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino. Check for OneDrive name-clash
files before every build and commit. Another session holds an
uncommitted edit to plugin/native_v02/Components/DeliveryComponents.cs:
never stage it; git add by explicit path only.
