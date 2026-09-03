# Skin defects and the free edge: implementation plan

> **For agentic workers:** each task below is dispatched to a fresh implementer with this file's
> task text as its brief. Steps use checkbox syntax for tracking.

**Goal:** make the Skin component stop discarding geometry it has already built, stop reporting
numbers that are not true, stop building cells that close with chords across a topology change,
and terminate its courses on the form's own free edge instead of a straight chord.

**Architecture:** four tasks, one writer on the tree at a time. Tasks 1 and 2 are defect fixes
against rules the code already claims to follow. Tasks 3 and 4 add the free edge as data and then
use it. Nothing here builds the ridge closer; that is Param's ruling of record for the next wave.

**Spec:** docs/superpowers/specs/2026-09-01-skin-buildability-design.md governs. Where this plan
departs from it, the departure is named in the task and an erratum is written in the same commit.

## The measurements this plan is built on

Taken from Param's own export,
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench\demo\upload from grasshopper\Arch test-contract.json

- 441 vertices, 400 faces, a regular 21 by 21 grid. 80 boundary edges, 80 boundary vertices.
- 42 anchors, ALL on the boundary, in two rows of 21 at the two ends.
- The free boundary is 40 edges in TWO chains of 21 points. Each chain spans 16.000 m end to end,
  rises 4.766 m, and bows 1.072 m in plan. A pattern-drawn rectangle bows zero, so form-finding
  shaped these edges: they are the funicular free edge, and terminating on them is worth doing.
  At 21 points over 16 m the result is faceted at 0.8 m and cannot be finer than the mesh.
- The rim-distance field (Dijkstra proxy over the same seeds) has a SINGLE INTERIOR MAXIMUM of
  10.4538 m at vertex 110, at (0.00, 0.00, 5.70). There is no ridge and no plateau.
- Traced level-curve components: TWO OPEN STRIPS from 0.05 m up to 9.72 m, then ONE CLOSED LOOP
  from 9.72 m to the apex. Exactly one topology event, a MERGE, at course 19 of 21 at CH 0.5.
  That is the single refused band and the ring of gaps below his crown.
- Consequence: every level curve below 9.72 m is an open strip with both ends on the free edges,
  so EVERY course is chorded at both sides. The flat crop is not an end effect.

## Global constraints

- No em dashes in any prose written by this plan's work, including code comments.
- No AI attribution in any commit, file or comment. Commit locally after every working fix, adding
  by explicit path only. NEVER push.
- Before every test run and every commit, scan for BOTH OneDrive markers, including bin/ and obj/:
  `find . \( -name "*Name clash*" -o -name "*Edit conflict*" \) -not -path "./.git/*"`
- Every new check MUST be proved able to fail: break the code it covers, see the harness go RED,
  restore, and say so in the report with the exact failure text.
- Nothing in SkinPatterns.cs may reference RhinoCommon.
- Build and test, verbatim, from the repo root
  C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow :

```
dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -c Release
dotnet run --project tests/native_smoke/Ananke.COMPAS.NativeSmoke.csproj -c Release -- "plugin/native_v02/bin/Release/net8.0-windows/Ananke.COMPAS.gha"
```

  Grep the build output for `error`, `Warning(s)` and `Error(s)`: warnings are errors here and a
  tailed build hides them, which has let a stale exe run green twice. Baseline before this plan:
  build 0 warnings 0 errors, harness exit 0 with exactly one DEFER (the coarse-net foot
  convergence, owned by spec sections 8.2 to 8.4, which nothing here touches).

---

### Task 1: the messages tell the truth, and a face is never thrown away

**Files:**
- Modify: `plugin/native_v02/Components/SkinComponents.cs` (lines 352-362, 435-466, 492-516)
- Modify: `plugin/native_v02/Components/SkinPatterns.cs` (record at 215-244; force-aligned counter
  at 3761-3764; the force-aligned result construction near 3820-3850)
- Test: `tests/native_smoke/Program.cs`

**Interfaces:**
- Produces: `SkinPatternResult.ThreeSidedCells`, appended as the LAST positional parameter with a
  default of 0, so no existing construction site moves. Later tasks may read it.

- [ ] **Step 1: a face the engine built is never discarded.**
  At SkinComponents.cs:441-452 the thickened solid REPLACES the face, and when
  `ThickenCellSurface` returns null the slot carries a null even though `CellSurface` succeeded.
  Keep the face: assign the thickened solid only when it is not null, and count the thickening
  failures in their own counter. This is the single change most likely to restore Param's missing
  geometry, because at Thickness 0.29 the thickener is a leading suspect for all 148 of his nulls.

- [ ] **Step 2: split the warning that misattributed them.**
  SkinComponents.cs:455-466 currently says "N cells would not close into a surface". Emit two
  distinct messages instead: one naming cells whose FACE would not close, one naming faces that
  would not close into a SOLID at the thickness in force, stating plainly that those cells are
  still exported and are drawn as the un-thickened face. Spec 5.3.1 and the thickness spec both
  say a NULL means the FACE failed, so today's message sends the reader to the wrong function.

- [ ] **Step 3: the three-sided cells stop being reported as seven-sided.**
  SkinPatterns.cs:3763-3764 increments `sevenSided` when `setout == 3`; the engine's own
  diagnostics string at 3814 correctly words it "three-sided" while SkinComponents.cs:509-510
  prints the same field as "seven-sided". Add `int ThreeSidedCells = 0` as the last positional
  parameter of `SkinPatternResult` (after `WeldCollapsedDropped`), have the force-aligned engine
  count three-cornered closers there, and report all three counts in the Remark. The honeycomb's
  genuine seven-sided cells (SkinPatterns.cs:5183) keep the seven-sided field.

- [ ] **Step 4: name the heights the warning already promises.**
  SkinComponents.cs:360 tells the reader "Diagnostics names the heights" and nothing does: the
  intervals live on `SkinPatternResult.TransitionIntervals` and inside the engine's Diagnostics
  string, and no component reads either since the D port went. Append the intervals to the
  transition warning, formatted the way `TransitionLine` at SkinPatterns.cs:4494-4499 already
  formats them. No engine code moves.

- [ ] **Step 5: prove each check can fail.**
  Add harness assertions for: a cell whose thickening fails keeps its face; the two messages are
  distinct; a force-aligned three-cornered cell lands in ThreeSidedCells and not in
  SevenSidedCells; the transition warning carries an interval. Then break each covered line in
  turn, run the harness, record the RED text, restore, and re-run green.

- [ ] **Step 6: build clean, harness green at exit 0 with one DEFER, clash scan, commit by path.**

---

### Task 2: the force-aligned pattern stops building cells across the merge

**Files:**
- Modify: `plugin/native_v02/Components/SkinPatterns.cs` (3509-3568, 3611-3615, 3987-4011, and the
  force-aligned diagnostics near 3828-3846)
- Test: `tests/native_smoke/Program.cs`

**Interfaces:**
- Consumes: nothing from Task 1 except that the record now ends with `ThreeSidedCells`.

- [ ] **Step 1: a streamline retires ABOVE its bed, not everywhere.**
  `retired` is a global `HashSet<int>` created at SkinPatterns.cs:3511, added to at 3532 when a gap
  is under half the target, consulted during the ladder walk at 3524 and again in the CELL loop at
  3613. The walk runs bottom-up and so sees a line on every bed below its termination; the cell
  loop runs afterwards against the FINAL set and so does not. The line vanishes retroactively from
  courses it was a head joint on, its neighbours' spans merge, and that is where Param's 7.52 m
  piece against a 0.5 m Size comes from. Replace the set with a per-line bed index (line to the bed
  it was terminated at), exclude a line only where `r` is greater than that bed at BOTH 3524 and
  3613, and keep the existing behaviour that a line terminated while bed r is being processed is
  still present on bed r itself. Spec rule 3.3.3 says "TERMINATE the later of the two AT BED k" and
  rule 3.3.5 says "No cell elsewhere along the bed changes its side count", so this is the code
  being made to obey its own rules, not a rule change.

- [ ] **Step 2: a chain stops at the band it belongs to.**
  `ChainBetween` at SkinPatterns.cs:3987-4011, in its `to is null` branch (3993-4001), walks the
  streamline to its own END. On Param's net a joint that reaches the merge keeps walking, and the
  cell closes with an implicit chord across it: that is the source of the 21 self-crossing and 33
  overlapping cells the plan filter then deletes. Pass the band's upper bed level in and stop the
  walk at the first polyline point whose field level exceeds it. Where the chain still leaves the
  band, REFUSE the cell: count it in its own counter and report it, rather than emitting a cell
  that a downstream filter will delete. Rule 3.3.5 sanctions a three-sided closer, so a closer that
  stays inside its band is still emitted; only the ones that escape are refused.

- [ ] **Step 3: stop claiming a band was skipped when none was.**
  The force-aligned engine computes `ResolveBands` and reports `resolved.Refused.Count`, but its
  band loop at SkinPatterns.cs:3581 iterates every band unconditionally and never reads
  `resolved.Tileable` (the courses engine does, at 3016). So on pattern 2 the warning Param read is
  FALSE: nothing was skipped, the band was tiled straight across the merge.
  RULING, recorded here rather than assumed: do NOT gate the loop in this task. Gating it alone
  converts the damage into a visible hole at the crown, and Param has ruled that the merge is to be
  COVERED by a closer band in the next wave, which makes the gate moot. Instead make the report
  honest: pattern 2 must not raise the "band was skipped" warning, and must say plainly that it
  does not test correspondence between beds. Steps 1 and 2 remove most of the bad cells that
  crossing the merge produced.

- [ ] **Step 4: prove each check can fail.**
  Assertions: a line terminated at bed k is still a head joint on bed k-1; a closer's chain never
  leaves its band; the refused-cell counter rises on a net where a chain would escape; pattern 2
  raises no transition warning. Break, run RED, record, restore, re-run green.

- [ ] **Step 5: re-measure the force-aligned pins.**
  Every pinned force-aligned count in the harness will move. Re-MEASURE them and write the reason
  beside each; do not relax an assertion to make it pass. Report the before and after for the
  piece-length range in particular, which is the number Param is watching.

- [ ] **Step 6: build clean, harness green, clash scan, commit by path.**

---

### Task 3: the free edge becomes data

**Files:**
- Modify: `plugin/native_v02/Components/SkinPatterns.cs` (`ReadNet`, 267-390; the `SkinNet` record
  and its init properties near 86-90; `FacesOnBoundary` at 2546 for the shared arithmetic)
- Test: `tests/native_smoke/Program.cs`

**Interfaces:**
- Produces: on `SkinNet`, the boundary split. Carry it as INIT PROPERTIES in the style of
  `RimDropped` and `EdgesDropped` near lines 86-90 so no constructor signature moves and every
  existing fixture keeps binding. Name them so a reader can tell them from `Rim`.

- [ ] **Step 1: derive the mesh boundary.**
  An edge belonging to exactly one face is a boundary edge. `FacesOnBoundary` at 2546-2582 already
  does half this arithmetic; share it rather than writing it twice.

- [ ] **Step 2: split supported from free, by a stated rule.**
  An edge is SUPPORTED when BOTH its ends are in `net.Rim`, and FREE otherwise. State that rule in
  the doc comment: a boundary vertex that is an anchor whose neighbour is not is the case that
  needs the rule written down rather than left to the reader. Chain the free edges into polylines.

- [ ] **Step 3: nothing else changes.**
  This task alters NO output. The Cells, the Surface, every count and every message stay exactly as
  they were. Prove it: run the harness before and after and confirm every number is identical.

- [ ] **Step 4: check it on the shipped fixtures and prove the check can fail.**
  On the harness's barrel fixture the free boundary is two chains; on a rimmed hemisphere it is
  empty. Assert both. Then break the both-ends rule (make it either-end) and show the hemisphere
  assertion go RED, restore, re-run green.

- [ ] **Step 5: build clean, harness green, clash scan, commit by path.**

---

### Task 4: a course terminates on the free edge instead of chording across it

**Files:**
- Modify: `plugin/native_v02/Components/SkinPatterns.cs` (`BandCell` at 4424-4450; the `Clipped`
  sites at 3223, 3664 and 5126-5127; `PatternDiagnostics` at 4553)
- Modify: `plugin/native_v02/Components/SkinComponents.cs` (the Remark at 500)
- Test: `tests/native_smoke/Program.cs`, and `scripts/rhino_skin_surface.py` for the Rhino-side check

- [ ] **Step 1: the end cell's ring runs along the free edge.**
  `BandCell` at 4438-4442 concatenates the lower run with the reversed upper run, so the two end
  edges of an open strip are implicit STRAIGHT CHORDS. For a cell whose end lies on the free
  boundary, replace that chord with a RUN along the free-edge polyline between the lower and upper
  level curves' endpoints: lower run, free-edge run up, reversed upper run, free-edge run down.

- [ ] **Step 2: accept what it costs and say so.**
  The end cells stop being four-cornered, so they leave the loft route and take the fan. The odd
  cell counts and the clipped counts will move. Re-measure the pins; do not relax them. Note in the
  commit that the result can be no smoother than the mesh boundary: 21 points over 16 m on Param's
  net is a 0.8 m facet, and that is a property of his mesh, not of this code.

- [ ] **Step 3: `Clipped` means one thing.**
  Define it as "this cell's outline touches the FREE boundary" and set it from Task 3's free-edge
  set in all three patterns, replacing the pitch comparison at 3223, the literal `false` at 3664
  and the clamp test at 5126-5127. Report it as such at 4553 and in SkinComponents.cs:500. Every
  pinned clipped count moves and must be re-measured with a reason written beside it.

- [ ] **Step 4: prove the checks can fail, build clean, harness green, clash scan, commit.**

## Ledger

Ledger for this plan lives at `.superpowers/sdd/2026-09-03-skin-defects-and-free-edge/progress.md`.

## Carried rulings and deferrals

- RIDGE/MERGE CLOSER: Param's ruling of record is the closer band (cover the refused interval by
  direct tessellation of the strip between the two levels, no correspondence needed). NOT in this
  wave, by his scope ruling. It settles spec section 13.2 item 3, which has been open since the
  buildability spec was written and which recorded its own refusal as "a DEPARTURE FROM HIS
  WORDING". Write that answer into the spec when the closer is built.
- CROWN CAP: no shrink gate. Measured on his own net, his crown is a genuine interior maximum, so
  the cap is right in kind. What is wrong with it is separate and NOT in this wave: a cap carries
  no section rails, so `CellSurface` draws it as a fan of straight triangles from one lifted apex
  (SkinComponents.cs:635-652), and it comes out whole rather than in wedges because the split fires
  only above `Size / MinPiece`, which at his Min Piece of 0.10 is a ceiling of 5.0 m. Min Piece is
  a FRACTION clamped to [0, 0.5], not a length.
- EXPORT'S `CO` PORT: vestigial for a canvas wired from Skin, since Skin has no Courses output and
  the course is the Cells tree's branch path. It is NOT dead: it is the escape hatch for a flat
  cell list from another source. Leave it. Removing input 2 slides every archived wire up one,
  which is the exact hazard the Live hold at DeliveryComponents.cs:205-222 exists for.
