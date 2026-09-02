# Columns: one ladder of symmetry, and the feet decided first

Date: 2026-09-01. Status: approved design, RULED ON BY PARAM ON 2026-09-01 and amended to his
rulings. He answered the three questions section 18 put to him, and the answers are now rules in
the body of this spec rather than annotations against it.

    ONE. The central column at an even Type STANDS STRAIGHT. A span with an odd number of tree
    groups at an even Type shows N gathered feet plus one further column standing alone and plumb
    on the mirror plane. Sections 5, 7 and 8.6 keep it, and the ground is now a quotation of his
    and no longer the engine's present behaviour.

    TWO. The Branching 3 layout criterion is FEWEST STRAYS, not fewest remainder trees. Section 6
    is re-derived to it and its tables are re-pinned.

    THREE. The load at a shared node is FIXED PROPERLY. The untransversed per-bar pull and the
    per-node whole pull are threaded through to the engine, and the head load is counted exactly
    once and in full. Sections 10, 16 and 17 carry it.

The controller ruled on the four questions Param left untouched, and those rulings are marked as
the controller's in section 18: the cross-line merge mirror gate is kept, the collision clearance
and the feet-close scale change as proposed, the shared-node ownership rule stands as written, and
section 13's account of the forces at Types 1 to 4 is accepted and closed. Two items remain open
for Param in section 18, the Type value list's item text and the even group's foot standing
between two notches rather than on one, and the rest of that section is now a record of the costs
this design accepts.

One consequence of his second ruling must be read before the plan is written, because it
contradicts the expectation the ruling arrived with. Fewest strays changes FOUR layouts at
Branching 3, m = 3, m = 7, m = 9 and m = 13, and not the two that were expected. m = 5 and m = 11
are preserved as expected; m = 7 is not, and m = 13 moves with it. Section 6 derives it in full
and section 18.1 records it. Every one of the four LOWERS the stray count, so the ruling's own
purpose is served; the arithmetic was not bent to fit the expectation.

Written from docs/superpowers/specs/2026-09-01-columns-design-input.md, which quotes his rulings
verbatim. That document governs this one wherever the two disagree, save where his rulings of
2026-09-01 above are later than it. This spec replaces the draft that stood at this path earlier
on 2026-09-01, whose foot targets at k / (N + 1) are superseded by section 5 below. That draft's
central foot at an even Type is NOT superseded: it is what the engine builds today, it is what the
harness pins, section 7 keeps it, and Param has now ruled for it. It amends
docs/superpowers/specs/2026-08-30-columns-symmetric-type-design.md (sections 3.3, 3.4, 3.5 and
3.7) and, through it, docs/superpowers/specs/2026-08-28-columns-two-sliders-design.md (sections
3.5 and 3.7). Everything in those two specs not amended here stands, and section 2 lists what
may not move at all.

Every number quoted below as a measurement was measured on 2026-09-01 against the built
plugin, by driving ColumnPlacement.Place and MouldGeometry.ColumnsBlock by reflection on
hand-built nets. Those numbers are facts about the engine as it stands, not estimates, and
section 17 requires each of them either to be reproduced by the new rule or to be replaced in
the record by the number the new rule gives.

## 1. Purpose

Param's review of the installed plugin, on a single-span vault, reported three things: the
columns are not symmetrical or uniform, the middle one should be straight and is not, and the
off-centre ones look randomly placed, with branching making it worse. That sentence is a
PARAPHRASE of the review conversation and appears nowhere in the design input, so no rule below
rests on its wording. What the central column now rests on instead is a quotation, given in
section 7 and recorded in section 18: he objected to "just moving the standing coloumn for
symmetry reasons away from center when it shold obviously default to center". That is a ruling of
his, the paraphrase is still only a paraphrase, and the two are kept apart throughout.
His quoted rulings, which do bind, are that the stray columns must be placed by a stated
priority of symmetry, that a column branching from one point must be centred by converging the
principal lines inward rather than by taking anyone's centre, and that two principal lines
touching must not throw the symmetry off. The design input adds four numbered changes of its
own, measured rather than argued, and this spec carries all four: the common mode is removed
explicitly and not by pairing (section 9), the mirror plane is derived from the structure and
not from the anchors (sections 4 and 9), a crossing takes no line's interior notch (section 10),
and the diagnostic reports the RESIDUAL so that it cannot read clean when the rule was skipped
(sections 9, 16 and 17).

The investigation that preceded this spec established what the engine actually does, and it
changes what has to be written. Five findings bind.

- The symmetry decision is taken once, in Symmetrise, before any Type level is built, and it is
  all or nothing per span. A span whose free notches do not pair off about its chord midpoint
  to within a quarter of one notch spacing loses every partner on the span, and with them the
  per-pair banding, the mirrored feet, the foot merging and the family averaging together.
  AsymmetricSpans is identical at Types 0, 1, 2, 3 and 4, so no Type escapes it and no
  Type-level rule can repair it.
- The measured cost on a ten metre span of nine notches is a foot mirror defect of 1.0, 2.0,
  3.0, 3.0 and 2.0 metres at Types 0 to 4, which is 10, 20, 30, 30 and 20 per cent of the span,
  of which only 1.0 metre is the missing notch itself. On a three arch fixture the same trigger
  drops AsymmetryRemoved from 3 degrees to 0 and leaves one arch's feet disagreeing with the two
  identical arches beside it.
- A crossing is a real trigger and not the only one, and not a reliable one. A free bar end, a
  crest 8.4 per cent of the span off centre on a nine notch rib at rise over span 0.25, a lone
  notch 6.25 per cent off the chord midpoint, or simply refining the mesh from five notches to
  nine on unchanged geometry, each reaches the same cliff with no crossing anywhere. A crossing
  at the span's own centre does not trip it, and a symmetric pair of crossings does not trip it.
- Which line loses a shared notch is decided by bar order alone. The same net, the same
  crossing and the same geometry give AsymmetricSpans 1 and Families 1 with the rib handed over
  first, and AsymmetricSpans 0 and Families 2 with the arch handed over first. Nothing in the
  model tells the author which order Pattern traced.
- Param's hypothesis is right about the mechanism that matters and wrong in one detail.
  Nothing is ever cancelled out and there are never two connections on one node: the held set
  already refuses a duplicate, exactly one head stands at a shared node, no member is dropped
  and every free net vertex gets a head. What is lost is the hole the claim leaves in the loser's
  free list, the other bar's vertical load at that node, which went uncounted (seventeen units
  where eighteen were applied), and, where the claim takes a span's only free notch, that span's
  trees entirely.

Four causes therefore have to be answered, and each has a numbered rule below.

- The whole-span symmetry gate. Section 9 removes each span's mean along-chord pull FIRST, with
  no pairing, no tolerance and no test, so the rigid-body tilt that walked every foot down one
  rib's chord is gone whatever the notch list looks like; it then keeps a pairing test, per
  tree, but confines it to what is left of the AIM. Section 7 makes the FEET symmetric by
  counting rather than by measuring, so no test can disengage them. There is no longer any state
  in which a span is placed unmirrored, and no state in which a span keeps a common mode.
- Band arithmetic. A band is chosen by floor(s * N) against a boundary, which flips on a solve
  change of no consequence, and a band's foot is the centroid of whichever mains landed in it.
  Sections 7 and 8 remove bands entirely. Which trees share a foot is decided by counting the
  span's own trees, which cannot flip; where that foot stands is a continuous function of the
  notch positions, which cannot jump.
- The remainder at the anchors. Grouping puts every leftover notch at the anchor ends, and a
  lone centre notch at the centre when the count is odd. It must be said plainly that this is
  ALREADY LADDER COMPLIANT, at Branching 1 and 2 and at every Branching 3 count: the strays it
  leaves stand at the two ends, or at the centre, or at both, which is exactly what his ladder
  asks for. Sections 5 and 6 therefore make the rule TOTAL and EXPLICIT rather than repairing a
  defect, and the ladder must not be cited to him as the cure for the columns he complained
  about. What does move a column at Branching 3 is the choice of CENTRE TREE SIZE, on which he
  has now ruled: the admissible centre size leaving the FEWEST STRAY TREES wins, and section 6 is
  derived to that rule and re-pinned to it. The symptom he reported is answered
  by the feet being decided first, by the common mode being removed, by the structural mirror
  and by the shared-node rule.
- The centre. N equal bands have a boundary on the mirror plane whenever N is even, so no foot
  was ever central and the centre tree fell back to a leaning thrust-line foot. Sections 7 and 8
  give the centre tree a foot on the mirror plane at every Type, placed by his convergence rule.

One structural change makes all of it possible, and it is his: the FEET ARE DECIDED FIRST, from
the span alone, and the trees are then assigned to them, inverting the present order in which
each tree projects into a band and the feet fall out of where the trees happen to be.

## 2. What is preserved, and may not move

This spec changes where the feet are, how trees reach them, and what happens where two lines
touch. It changes nothing below, and the harness pins each one.

- Type keeps its name, its nickname T, its slot (input 2), its default of 0 and its value list
  exactly: 0 own feet, 1 one central foot, 2 two feet, 3 three feet, 4 four feet, and Auto at
  -1. MaxGround stays 4 and a higher value still clamps with the existing warning about
  seven-item value lists from before the two-slider rework. The ITEM TEXT is kept verbatim even
  though it names a count the engine will not always deliver: a span of odd tree count at an
  even Type shows one further central column, and a span holding fewer trees than the Type asks
  for shows fewer feet. That inaccuracy is left standing knowingly, because the brief preserves
  the list, and section 18 puts it to Param with the wording that would fix it.
- Branching keeps its name, its nickname B, its slot (input 1), its clamp to 1 through 3 and its
  MEANING: notches per tree, neighbouring notches grouped into trees of that size, every notch
  held, the main notch of a tree its innermost. What section 6 changes is only where the
  remainder sits, which is the thing Param ruled on.
- Levels are JUDGED, NEVER REFUSED. Level.Feasible remains Collisions == 0, Auto reads that
  field and nothing else, and Level.Rule and Level.Value name the worst measure in the order
  collision, lean, alignment, none.
- The ring tree is untouched: the least-squares intersection of the bars' end tangents in plan,
  the fallback to the rim centre when that system is singular, the rim notches held so the spans
  end at them, and a FIXED FOOT that takes part in no pairing, no grouping, no convergence and
  no merge.
- Every member leaves the engine LOWER END FIRST, settled in AddMember rather than trusted from
  the caller, because Animate and the block's tree both depend on it.
- The fork lies ON THE SEGMENT from the foot to the main notch, at ForkFraction = 0.65 of the
  main notch's height, so trunk and main branch are one straight line and a trunk cannot kink;
  and where that height would sit at or above the tree's LOWEST notch, the fork is lowered on
  the same segment to ForkFraction of that notch's height. The second clause records a fixed
  defect, a fork above one of its own heads being read by TreeFromPairs as a foot in mid-air,
  and it must not be lost. Where a tree's main notch is BORROWED at a shared node (section 10)
  no member is built there, so the segment ends instead at the tree's innermost OWNED notch, its
  HEAD MAIN, and every clause above is read against that notch. On any tree that owns its main,
  which is every tree on a net with no crossing, the head main IS the main and nothing changes.
- MouldGeometry.AimFrom, its sixty degree cap, MaxLeanDegrees, PlumbDegrees = 2,
  AlignmentDegrees = 30 and the per-FOOT alignment measure are unchanged. Alignment is judged on
  the vector sum at a foot and never on one trunk, because two mirrored trunks sum to a vertical
  push and judging them singly refused an ordinary arch.
- The two collision tests keep their shape: two members that share no end and come closer than
  the clearance, and a member whose interior sampled at 1/8 to 7/8 of its length rises more than
  the clearance above the Z of the nearest NON-ANCHOR net vertex in plan. The narrowings that
  were removed once (an edge-proximity rule, a half-median radius on the height test, and
  skipping the member's own notch) stay removed, and anchors stay excluded for the reason
  recorded in the file. Only the clearance itself changes, in section 4, and only because the
  brief forbids a net-median tolerance.
- The diagnostics keep the columns. prefix and the source name Columns, so Diagnose reads them
  without change, and the block written into Mould.Columns keeps its shape, including
  GroundAsked, GroundPlaced, ForkFraction and ForksRaised = 0.
- The engine stays PURE ARITHMETIC on arrays: Point3d, Vector3d, int[] and double[] only, no
  Curve, no Mesh, no Unitize and nothing else that calls into Rhino's native core, so the smoke
  harness drives every rule without launching Rhino. Vector3d.Unitize in particular is a native
  P/Invoke and throws outside Rhino; neither the engine nor the harness may call it.
- Symmetrise keeps its idempotence guard, keyed on the flag AND on the tree count, so a second
  call is a no-op and a call after a tree was added runs again.
- A crossing does not split a span. It never did, and under section 10 it does not remove a
  notch from a span either.

## 3. Order of operations

For one Result, in this order.

1. Read the net: nodes, bars, anchors, transverse pulls per bar and bar position, perimeter
   loops, the ground level, and from this wave three more things: the net's edge list
   (section 12), the UNTRANSVERSED pull per bar and bar position, and the whole incident pull
   per NODE, which together are what makes the load at a shared node countable exactly once
   (section 10).
2. Place the ring tree, if any, and hold its rim notches.
3. Cut every bar into spans at its anchors and at held rim notches. The free notches of a span
   are every position it holds that the ring tree has not taken. A notch shared with another
   bar is NOT taken away from either span (section 10).
4. Decide the OWNER of every shared notch, by the span-level rule of section 10.
5. Group each span's free notches into trees by the ladder (sections 5 and 6), the notches taken
   in BAR ORDER along the span. The layout is a function of the notch count and Branching alone.
6. REMOVE THE COMMON MODE. For every span, subtract its own mean along-chord component from
   every one of its trees' resultants, unconditionally (section 9). Nothing gates this step: no
   pairing, no tolerance, no test, no exemption for an unpaired tree and no exemption for a span
   that fails anything.
7. Locate each span's AIM MIRROR from the residual that step 6 leaves (section 9), pair the
   trees about it by chord parameter, symmetrise over the accepted pairs and over the families,
   subtract the span mean once more so the invariant holds by construction, and apply the dead
   band. This decides the AIM, and it decides a position only at Type 0.
8. For each Type level to be built, and for each span: cut the span's trees into FOOT GROUPS by
   the same ladder (section 7), then place each group's foot by convergence and snapping
   (section 8).
9. Peel, per mirror pair, where the lean cap cannot be met (section 11).
10. Weld coincident feet, merge the CENTRAL PAIR of an even tree row, merge feet across adjacent
    lines by re-converging them, and count what stands close but apart (section 12). Then judge
    the peel AGAIN, over the trees still standing on a shared or merged foot, because a merge
    moves a foot and can put a trunk that was inside the cap outside it (section 11).
11. Build the members, judge the level, and either place it or, under Auto, score it.

Step 8 is the inversion. No tree's aim, load or resultant is consulted anywhere in it: a foot's
position is a function of the span's own notch positions, the span's tree count and the Type.
That is what makes a foot stable under a solve change, and it is why the old rule that rebuilt a
band's foot from its surviving trees is gone along with the bands. Steps 9 and 10 do read the
aim, because a peel lands a tree on its own thrust line and a merge answers a ruling about feet
that have already landed together; neither of them moves a foot that no tree left.

## 4. The span's own terms, and every tolerance

Every tolerance in this spec is a formula in the terms of the span, or the pair of spans, it
applies to. Nothing reads the net's median plan edge, and the medianPlanEdge argument is REMOVED
from ColumnPlacement.Place so that it cannot be read by accident. That is not a stylistic
preference. A shipped bug was exactly a tolerance scaled by the net's median plan edge, which is
a median over every edge in both mesh directions and stands in no fixed ratio to the notch
spacing along any one bar: on a mesh refined along its principal lines the bound became several
whole notch spacings and stopped discriminating, and on one refined across them it collapsed to
exact coincidence. The median was still live in two places at the time of the investigation,
which measured FeetClose going 0, 0, 0 and then 4 on identical geometry as the median went 0.2,
1, 5 and 20 model units, while the same shape scaled by ten with its median scaled with it gave
FeetClose 0. Both places are restated below in span terms.

For a span S, write:

- P0 and P1 for the plan positions of its first and last node, L = |P1 - P0| for its CHORD
  LENGTH in plan, c = (P1 - P0) / L for the unit chord direction, n = (-c.y, c.x) for the plan
  normal, and M = (P0 + P1) / 2 for the chord midpoint. M is a coordinate origin and nothing
  more: no rule below places a foot at it or measures a symmetry about it.
- For any plan point Q, the CHORD PARAMETER sigma(Q) = ((Q - P0) . c) / L. A threshold stated on
  a chord parameter is already a fraction of the span's own chord, so a bare number there IS in
  the span's own terms; that is the one place a plain figure is allowed below.
- The span's free notches, m of them, IN BAR ORDER along the span, at plan positions Q_1 to Q_m
  with chord parameters s_1 to s_m. Bar order is the order the notches stand along the bar, and
  it is the order that governs the layout, the trees, the mains and the foot groups, because
  Branching's preserved meaning is NEIGHBOURING notches grouped into trees. The chord parameters
  are NOT assumed to rise with bar order: a bar that is not plan-monotone disagrees, which the
  engine's own comment already records, and nothing below reads an index where a parameter is
  meant or a parameter where an index is meant. Write s_min and s_max for the smallest and
  largest of the parameters.
- The ROW CENTRE has two readings and both are named so that neither is guessed. The ROW CENTRE
  BY INDEX is position (m - 1) / 2 in bar order, and it is what the ladder of section 5 divides
  about; it reads no geometry at all. The ROW CENTRE BY PARAMETER is (s_min + s_max) / 2, the
  middle of the stretch of chord the notches actually occupy, and it is what section 8's group
  centre and section 9's fallback read.
- The AIM MIRROR of a span, written s_mirror, is a chord parameter located in section 9 from the
  span's own along-chord pull, NOT from its cuts. The design input's second numbered change is
  explicit that the span's first and last node are an artefact of where the anchor cluster
  stops, and that the physical mirror is where the along-chord pull changes sign, which is what
  fixes the unequal anchor cluster and the off-centre crest together. The reflection about it
  sends sigma to 2 * s_mirror - sigma. It is used for the pairing of trees, for the self-pairing
  of a tree, and nowhere else; in particular NO FOOT READS IT, so adopting it does not put a
  force back in charge of a position at Types 1 to 4.
- The SPAN SPACING h, in chord parameter: h = (s_max - s_min) / (m - 1) when m >= 2 and
  (s_max - s_min) > 1e-9; and h = 1 / (m + 1) otherwise, which covers m <= 1 and a span whose
  notches all fall at one parameter. The measured form is preferred because a crossing, a free
  end or a crest that crowds its neighbours leaves the notches unevenly spread, and the measured
  mean is then the span's own answer rather than an assumption about it.
- The same spacing as a LENGTH, g = h * L.

THE SPACING FORMULA HAS CHANGED and the spec says so rather than claiming it has not. The engine
computes the bound as 0.25 / (count + 1), which assumes the notches are evenly spread inside
their cuts; the form above measures the spread instead. The two agree exactly wherever the
notches are uniform between the cuts, which is why the off-centre-crest fixture's bound stays at
0.025 either way, and they differ where they should: on the free-bar-end fixture, ten notches
from parameter 0 to 0.9, the old formula gives 0.25 / 11 = 0.0227 and the new one gives
0.25 * 0.1 = 0.025. Section 17 quotes both numbers side by side for every fixture whose
tolerance it pins, so the harness pins the right one.

The MIRROR MISMATCH of two chord parameters is |s_a + s_b - 2 * s_mirror|, which is zero exactly
when the two are mirror images about the aim mirror. The mismatch of a parameter with ITSELF is
|2 * (s_a - s_mirror)|, which is zero exactly when it lies on that plane. Two parameters are
MIRRORED when their mismatch is at most h / 4, and a parameter is CENTRAL when its self-mismatch
is at most h / 4. One predicate serves the pairing of trees and the self-pairing of a tree.

A quarter of the span's own spacing is the right bound in both directions and by the same factor
of four. A genuinely mirrored pair of notches out of a solved net misses by the millimetres a
solver moves a node it meant to leave alone, orders below h / 4 in chord parameter. A partner
that is missing leaves the nearest candidate a whole spacing out, mismatch h, four times the
bound. A node that is central because it lies on the crown misses by that same solver noise, and
one that is merely the nearest to the centre of an EVEN row sits half a spacing off the plane,
mismatch h, four times the bound again. The investigation measured the consequence of that
bound precisely: on a nine notch rib the test trips when the worst notch is 2.51 per cent of the
span off its mirror, which is a quarter of a notch spacing, and in crest terms 8.4 per cent of
the span off centre at rise over span 0.25. The bound is unchanged by this spec. What changes is
what failing it costs: not a span's every foot, as today, and not even its common mode, which
section 9 removes before any pairing runs, but only the sharing of what is left of one tree's
across and down with one partner.

The other tolerances, all likewise in the terms of the span or spans concerned:

- TAU_snap = 1e-6 * h, the chord parameter within which two candidate notches count as
  equidistant from a target.
- TAU_weld = 1e-9 * L for two feet of one span, and 1e-9 * min(L_A, L_B) for feet of two spans:
  the plan distance within which two feet are the SAME point and become one node. The RING TREE
  has no span and no L, so for a weld between a span foot and the ring foot TAU_weld is
  1e-9 * min(L_S, R), with R the ring tree's own scale defined under the collision clearance
  below; where a net somehow gives two ring trees, which no rim can, it is 1e-9 * R.
- The CONVERGENCE GUARD is g, or min(g) over the spans taking part: how far a converged point
  may lie from the convex hull of the points it was converged from before the mean is used
  instead (section 8). For a MERGED foot the guard is tightened to the merge clearance that
  justified the merge, 0.25 * min(g), because feet declared to have already landed together at a
  quarter of a spacing may not then be allowed to converge a whole spacing away from them.
- The CROSS-LINE MERGE CLEARANCE between spans A and B is 0.25 * min(g_A, g_B), a quarter of the
  tighter span's own notch spacing as a length. Two feet nearer than that had, for practical
  purposes, already landed together. The CENTRAL-PAIR CLEARANCE, for the two innermost feet of
  one span's EVEN tree row, is 0.25 * g of that span, by the same reading.
- The FEET-CLOSE CLEARANCE, which decides what columns.feet_close warns about, is the merge
  clearance of the pair concerned: 0.25 * min(g_A, g_B) for feet of two spans and 0.25 * g for
  two feet of one span. It is named separately because until now it shared a number with the
  collision clearance, 0.05 * medianPlanEdge, and the two now differ by a factor of five. That
  is a knowing change of scale on a warning, it will raise FeetClose counts, and section 17
  requires the before and after counts on the existing fixtures.
- The COLLISION CLEARANCE, which used to be 0.05 * medianPlanEdge, becomes 0.05 * g of the tree
  whose member is being judged, and 0.05 * min(g_A, g_B) where two members of different spans
  are judged against one another. A tree's g is its span's g. The RING TREE has no span, so its
  scale R is the smallest plan distance between two of its own rim notches, and its clearance is
  0.05 * R, which is in its own terms and needs no net median. This is a knowing change to a
  measure that is not a placement rule, it will move collision counts and with them Auto's
  choice on some nets, and section 17 requires the before and after counts to be recorded rather
  than argued, and names the one existing fixture the change destroys.
- The least-squares system of section 8 is accepted when |det| > 1e-9 * max(trace * trace,
  1e-12), which is the ring tree's own scale-free conditioning test, reused verbatim.

Three degenerate tests need thresholds of their own, and none of them may be left to the
implementer to invent, because the engine's present 1.0e-12 absolutes are exactly the kind of
number this section exists to remove. Write D for the span's own PLAN BOUNDING BOX DIAGONAL over
its two cut nodes and all its free notches, which is a length the span always has even when its
chord has none.

- A span's CHORD LENGTH IS ZERO when L <= 1e-9 * D. Where D is itself zero, so that every one of
  the span's nodes stands at one plan point, the span is degenerate by the same rule and takes
  the same answer, in section 15.
- A plan TANGENT IS NOT DEFINED at a notch when the plan separation of the two points it is
  taken between is at most 1e-9 * L, or at most 1e-9 * D where L is zero. The bound applies to
  the centred difference between the bar positions either side and, at a bar end, to the single
  one-sided segment, which is renormalised the same way and falls back the same way. Exact
  coincidence never occurs in a solved net, so a clause stated as exact coincidence never fires
  and normalises a near-zero vector instead, which is the failure the clause exists to prevent.
- The h fallback fires when m <= 1 or when s_max - s_min <= 1e-9, that last being a threshold on
  a chord parameter and therefore already in the span's own terms.

## 5. The ladder: one rule of symmetric placement

Param's ruling, quoted:

    "So yes the idea that only 1 or two columns get left stranded, but they also need to be
    placed symmetrically and we need to build a priority placement into it. If one column it
    should defer directly to the center node where then the rest of the columns will all be
    symmetrical, then two stray columns will be the 2 end nodes and nothing in the center, three
    stray columns the two end nodes plus the center. This should be clear enough not to describe
    the symmetry I am getting at."

The rule taken from it, and applied everywhere this engine divides a span, is THE LADDER.

    A span's stations, in priority order, are: the CENTRE, then the outermost MIRRORED PAIR,
    then the next pair inward, and so on. When n things are placed, the centre station is
    occupied IF AND ONLY IF n is odd, and the remaining things fill mirrored pairs from the
    outside inward. Nothing is ever placed at a station without its mirror being placed too.

Reading his three cases off the ladder, exactly:

- ONE stray. One is odd, so the centre station is occupied and no pair is. The stray is the
  span's centre notch, and every other notch then lies in a mirrored pair of trees. That is
  "it should defer directly to the center node where then the rest of the columns will all be
  symmetrical".
- TWO strays. Two is even, so the centre station is EMPTY and one pair is occupied, the
  outermost. The two strays are the two end notches. That is "the 2 end nodes and nothing in the
  center".
- THREE strays. Three is odd, so the centre is occupied and one pair as well, the outermost. The
  strays are the two end notches and the centre notch. That is "the two end nodes plus the
  center".

He declined to enumerate further, so the ladder states it. FOUR strays occupy the two end
notches and the two notches immediately inside them, with nothing at the centre. FIVE occupy
those four and the centre. The reason the pairs work inward from the ends rather than outward
from the centre is his own: a stray is a lone column, the ends are where the load is smallest and
where a lone column is shortest, and the centre is reserved for the odd one out because that is
the only station a single thing can occupy without choosing a side.

Section 6's construction cannot reach four or five, and the spec says so plainly rather than
claiming a future-proofing it does not have. That construction yields at most one remainder tree
per half, at the anchor end, and one at the centre, so three is its ceiling at any Branching
whatever, and at a Branching of four it would give three remainder trees and never the ladder's
four adjacent ones. The higher rungs therefore describe an arrangement THIS ENGINE DOES NOT
BUILD. They are stated so that the ladder is a complete rule rather than a list of three cases,
and above three remainder trees the construction governs; anyone raising Branching past three
must revisit section 6, not lean on the ladder's fourth rung.

The ladder governs BOTH divisions this engine makes, and both divisions are taken by INDEX, on
the row centre by index of section 4, with no geometry read.

- Notches into trees, in section 6: the trees of a span are a palindrome about the row centre by
  index, and the remainder is placed at the ladder's stations.
- Trees into foot groups, in section 7: the groups of a span are a palindrome about the same
  centre, and the extra trees are placed at the ladder's stations.

This is what supersedes the earlier draft's foot targets at k / (N + 1). Those targets satisfied
the ladder's first two clauses, since they are a mirrored set and give a central target exactly
when N is odd, but they fixed the feet at parameters chosen by arithmetic rather than by the
span. That is the whole of what is condemned here, and the clause is worded narrowly on purpose,
because the earlier draft's OTHER change is not condemned with it. Where the ladder and the old
targets disagree, the ladder governs, and section 7 shows that on a clean nine notch arch the
ladder reproduces the feet the engine measurably places today at Types 2, 3 and 4, which
k / (N + 1) did not.

THE CENTRE TREE'S OWN COLUMN IS NOT ONE OF THE FEET THE TYPE PLACES, and the ladder's "nothing
in the center" therefore does not forbid it. The ladder counts the GATHERED feet, the feet onto
which several trees are drawn; a tree that is not gathered at all, because there is no side it
could join without a coin toss, stands on its own column exactly as it does at Type 0. That is
what section 7 builds, it is what the engine builds today, and the harness pins it at three feet
on a nine tree span at Type 2. PARAM RULED FOR IT ON 2026-09-01, so it is no longer a reading
offered for his decision: the centre column stands straight, and section 18 records the rejected
alternative rather than deleting it.

## 6. Notches into trees: the layout, and where the strays sit

ColumnPlacement.Group is replaced. Its inputs stay the same, a notch count and a Branching, and
so does the shape of its answer, the groups in span order with each group's main notch; its
pinned outputs change, and section 17 requires the new table to be pinned in full.

Two properties constrain the layout before any counting begins. Both are stated about the ROW
CENTRE BY INDEX of section 4, in bar order, and neither reads a coordinate.

- The sequence of tree sizes along the span must be a PALINDROME about the row centre by index,
  so that tree i and tree T - 1 - i hold the same number of notches and stand as mirror images.
- A tree that STRADDLES the row centre must have ODD size. A tree's main notch is its innermost,
  the notch its trunk runs to and the notch the fork's segment ends at; a straddling tree of
  even size has two equally inner notches, and the choice between them is a coin toss that puts
  the fork off the centre and breaks the tree's own symmetry. A straddling tree of odd size has
  its middle notch at the centre and no such choice. Groups of trees in section 7 carry no such
  restriction, because a group's foot is a convergence and is defined for any count, which is
  why the two divisions differ in exactly this one respect.

The layout is then decided by counting, with no geometry read at all.

    Let m be the free notch count and B the Branching, clamped to 1 through 3.

    If B == 1 every notch is a tree of one, there is no remainder and no notch is a stray, since
    a stray is a REMAINDER tree of one notch and not merely a tree of one notch.

    Otherwise, consider each admissible CENTRE TREE size k: k = 0 when m is even, k = 1 when m
    is odd, and k = 3 when m is odd, B >= 3 and m >= 3. For each, the half length is
    hlf = (m - k) / 2 and the half remainder is rem = hlf mod B. Each half is tiled from the
    CENTRE OUTWARD with trees of size B, and the leftover rem notches at the ANCHOR END form one
    tree of size rem, which is a STRAY when rem is 1. The REMAINDER TREE COUNT of that choice is
    one when a centre tree EXISTS and is smaller than B, that is when 0 < k < B, plus two when
    rem is not zero. A choice with k = 0 has no centre tree at all and contributes nothing on
    that count, so an even count carries two remainder trees when rem is not zero and none when
    it is.

    The STRAY COUNT of a choice is therefore

        strays(k) = (1 if k == 1 else 0) + (2 if rem == 1 else 0)

    the centre tree being a stray exactly when it holds one notch, and the two anchor-end trees
    being strays exactly when the half remainder is one. TAKE THE k WITH THE FEWEST STRAYS.

    Where two admissible k leave EQUALLY FEW strays, take the SMALLER k. That tie-break is the
    AUTHOR'S and not Param's, it is chosen because the smaller k is always what the shipped
    engine picks, so on a tie no column moves at all, and it reverses the earlier draft's
    "take the larger", which belonged to the retired criterion. The tie is unreachable for B up
    to 3, and the derivation below proves it rather than asserting it; the clause is stated so
    that the rule is total.

FEWEST STRAYS IS PARAM'S RULING OF 2026-09-01, and it replaces this spec's own earlier criterion
of fewest REMAINDER TREES. His reason is his own currency. He wrote "only 1 or two columns get
left stranded", and fewest remainder trees RAISED the stray count from one to two at m = 5 and at
m = 11, which is movement in the wrong direction on a definition he had already given. The
retired criterion, its layout at every odd count, and the two rows where it raised the stray
count, are recorded in section 18 rather than deleted.

The ladder itself says WHERE strays sit, not how many there should be, and the engine's present
layout already satisfies it at every count: a stray at each anchor end, a stray at the centre
when the count is odd, both when there are three. So the criterion and the ladder answer two
different questions, and neither is evidence for the other.

THE DERIVATION, in full, so that a checker reproduces it without guessing. At B = 1 there is no
remainder and no choice, so the criterion never runs and no notch is ever a stray: a tree of one
notch at Branching 1 is the whole meaning of Branching 1 and not a leftover. At B = 2 exactly one
k is admissible at every m, k = 0 for even m and k = 1 for odd, so again the criterion never
chooses and the layout is forced. Only at B = 3 with m ODD AND AT LEAST THREE are there two
admissible k, k = 1 and k = 3; at B = 3 with m = 1 only k = 1 is admissible and the layout is
[1], forced. Where both are admissible the two differ by exactly one in half length:
hlf(k = 3) = hlf(k = 1) - 1. Write r for hlf(k = 1) mod 3, so that hlf(k = 3) mod 3 is
(r - 1) mod 3. The three cases are exhaustive.

    r = 0:  k = 1 gives rem 0, one stray, the centre.   k = 3 gives rem 2, no stray.  k = 3 WINS.
    r = 1:  k = 1 gives rem 1, three strays.            k = 3 gives rem 0, no stray.  k = 3 WINS.
    r = 2:  k = 1 gives rem 2, one stray, the centre.   k = 3 gives rem 1, two strays. k = 1 WINS.

The stray counts differ in every case, by one, three and one respectively, so NO TIE EVER ARISES
AT B UP TO 3 and the tie-break above is unreachable. That is the proof the earlier draft asserted
without giving. Reading the three cases back as counts, and setting m = 1 aside as forced, k = 3
wins at m = 7, 13, 19 and so on (r = 0) and at m = 3, 9, 15 and so on (r = 1); k = 1 wins at
m = 5, 11, 17 and so on (r = 2).

The remainder trees land on the ladder's stations by construction: the centre tree when k is 1,
and the two anchor-end trees when rem is not zero. There are at most three of them, one per half
and one at the centre, which is why the ladder is never asked for four.

The main notch of a tree is its INNERMOST, unchanged: the notch nearest the row centre by index,
which for the centre tree is its middle notch and which for a mirrored pair gives mirrored
mains. Where that notch is BORROWED at a shared node the tree still HOLDS it, still pairs on its
parameter and still counts it in the layout, and the member it does not build runs instead to
the tree's head main, by section 10.

THE PINNED TABLES, re-derived under fewest strays, which the harness pins verbatim for B = 1, 2
and 3 and m = 1 to 13. Sizes are read along the span from one anchor to the other. A size of 1 is
a stray at B = 2 and B = 3, where it is a remainder; at B = 1 it is the whole tree the slider
asked for and is not counted as one.

    B = 1:  m = 1 to 13    every layout is 1 repeated m times, no remainder and no stray ever.

    B = 2:  m = 1   [1]                    one stray, at the centre
            m = 2   [1,1]                  two strays, at the ends
            m = 3   [1,1,1]                three strays, ends and centre
            m = 4   [2,2]                  none
            m = 5   [2,1,2]                one stray, at the centre
            m = 6   [1,2,2,1]              two strays, at the ends
            m = 7   [1,2,1,2,1]            three strays, ends and centre
            m = 8   [2,2,2,2]              none
            m = 9   [2,2,1,2,2]            one stray, at the centre
            m = 10  [1,2,2,2,2,1]          two strays, at the ends
            m = 11  [1,2,2,1,2,2,1]        three strays, ends and centre
            m = 12  [2,2,2,2,2,2]          none
            m = 13  [2,2,2,1,2,2,2]        one stray, at the centre

    B = 3:  m = 1   [1]              k=1  hlf 0  rem 0   one stray, at the centre
            m = 2   [1,1]            k=0  hlf 1  rem 1   two strays, at the ends
            m = 3   [3]              k=3  hlf 0  rem 0   none
            m = 4   [2,2]            k=0  hlf 2  rem 2   no stray; two remainder trees of two
            m = 5   [2,1,2]          k=1  hlf 2  rem 2   one stray, at the centre
            m = 6   [3,3]            k=0  hlf 3  rem 0   none
            m = 7   [2,3,2]          k=3  hlf 2  rem 2   no stray; two remainder trees of two
            m = 8   [1,3,3,1]        k=0  hlf 4  rem 1   two strays, at the ends
            m = 9   [3,3,3]          k=3  hlf 3  rem 0   none
            m = 10  [2,3,3,2]        k=0  hlf 5  rem 2   no stray; two remainder trees of two
            m = 11  [2,3,1,3,2]      k=1  hlf 5  rem 2   one stray, at the centre
            m = 12  [3,3,3,3]        k=0  hlf 6  rem 0   none
            m = 13  [2,3,3,3,2]      k=3  hlf 5  rem 2   no stray; two remainder trees of two

THE CLAIM THAT ONLY TWO CELLS MOVE DID NOT HOLD, AND THE SPEC SAYS SO PLAINLY RATHER THAN BENDING
THE ARITHMETIC. The ruling was passed down with the expectation that fewest strays would change
the layout at m = 3 and m = 9 alone, leaving m = 5, m = 7 and m = 11 as the shipped engine lays
them out. Two of those three hold: m = 5 and m = 11 are preserved exactly. m = 7 is NOT. At m = 7
the engine builds [3,1,3], which leaves one stray at the centre, while k = 3 builds [2,3,2],
which leaves none, so fewest strays takes k = 3 and the row moves. The same arithmetic moves
m = 13 for the same reason, r = 0 in the derivation above. FOUR cells change at Branching 3, not
two: m = 3, m = 7, m = 9 and m = 13.

The compensation is that the direction of every one of them is the direction his currency asks
for. The retired criterion moved a DIFFERENT four rows against the engine, m = 3, m = 5, m = 9
and m = 11, and two of those RAISED the stray count from one to two: m = 5, where the engine's
[2,1,2] became [1,3,1], and m = 11, where [2,3,1,3,2] became [1,3,3,3,1]. At m = 7 and m = 13 it
kept the engine's own [3,1,3] and [3,3,1,3,3] and moved nothing at all. Of the four rows his
ruling moves, not one raises the count.

    m       engine layout      strays   new layout      strays   verdict
    B = 1   every m            0        unchanged       0        PRESERVED, all thirteen rows
    B = 2   every m            as above unchanged       as above PRESERVED, all thirteen rows
    B = 3, m = 1   [1]                 1   [1]                 1   preserved
    B = 3, m = 2   [1,1]               2   [1,1]               2   preserved
    B = 3, m = 3   [1,1,1]             3   [3]                 0   CHANGED, strays 3 to 0
    B = 3, m = 4   [2,2]               0   [2,2]               0   preserved
    B = 3, m = 5   [2,1,2]             1   [2,1,2]             1   preserved
    B = 3, m = 6   [3,3]               0   [3,3]               0   preserved
    B = 3, m = 7   [3,1,3]             1   [2,3,2]             0   CHANGED, strays 1 to 0
    B = 3, m = 8   [1,3,3,1]           2   [1,3,3,1]           2   preserved
    B = 3, m = 9   [1,3,1,3,1]         3   [3,3,3]             0   CHANGED, strays 3 to 0
    B = 3, m = 10  [2,3,3,2]           0   [2,3,3,2]           0   preserved
    B = 3, m = 11  [2,3,1,3,2]         1   [2,3,1,3,2]         1   preserved
    B = 3, m = 12  [3,3,3,3]           0   [3,3,3,3]           0   preserved
    B = 3, m = 13  [3,3,1,3,3]         1   [2,3,3,3,2]         0   CHANGED, strays 1 to 0

That table is the engine's actual behaviour and not a reading of its comment. It was taken from
plugin/native_v02/Components/ColumnPlacement.cs, whose Group tiles each half from the centre
outward at size min(B, notches left) and always makes the odd count's centre notch a singleton
tree, so the shipped engine never builds a centre tree of three at all: in the terms of this
section it is the rule "always take the smallest admissible k". Every preserved row above is a
row where fewest strays picks that same k.

WHAT MOVES INSIDE THE FOUR CHANGED ROWS, since a changed layout is not the same as a changed
column count. At m = 3 the tree count falls from three to one and the three separate columns
become one tree of three branches. At m = 9 it falls from five to three. At m = 7 and m = 13 the
TREE COUNT IS UNCHANGED, three and five, and what moves is which notches belong to which tree and
therefore where the mains stand: at m = 7 the mains go from 2, 3, 4 to 1, 3, 5, and at m = 13
from 2, 5, 6, 7, 10 to 1, 4, 6, 8, 11. Those are real column moves on a saved definition and the
harness records them count by count.

THE COST, stated in the same currency as the benefit. At m = 7 and m = 13 the number of REMAINDER
trees rises from one to two: a single lone column at the centre is traded for two trees of two at
the anchor ends. Fewest strays says that trade is right, because a tree of two is a tree and a
tree of one is a stranded column, and it is strays he counted. At m = 3 and m = 9 both counts
fall to zero and there is no trade at all.

The change therefore moves columns on saved definitions at Branching 3, at four counts and not
two. It moves none at Branching 1 or Branching 2. That is his ruling's doing and not the ladder's,
since the present answer satisfies the ladder too, and section 18 records both the ruling and the
criterion it retired.

## 7. Trees into foot groups: what Type means now

Type 0 is unchanged and is described in section 14: every tree stands on its own foot, on the
line of the force it carries.

For Type N in 1 to 4, the span's T trees, IN BAR ORDER along the span, are cut into contiguous
FOOT GROUPS by the ladder. Every tree of a group stands on that group's one foot. Nothing about
a tree except its position in the row is read, and the row is the same row section 6 built, so
on a bar that is not plan-monotone the groups follow the bar and not the chord parameter.

    If T is at most N, every tree is a group of one. A span with fewer trees than the Type asks
    for places one foot per tree and no more; a foot with no tree is not built.

    If T is ODD and N is EVEN, the middle tree BY INDEX is taken out as a group of ONE and
    stands on its own foot, which is its own group's central notch by section 8 and which lies
    on the span's plane of symmetry exactly when that notch does. Let T2 be T - 1. Otherwise T2
    is T.

    Let q be T2 divided by N and s be T2 mod N. If s is 0 every group holds q trees. If s is 1,
    which can only happen when N is odd, the CENTRE group holds q + 1. If s is 2 the two END
    groups hold q + 1 each. No other s can arise, because s is below N, N is at most 4, and T2
    is even whenever N is even.

That is the ladder again, in as many words: the odd extra goes to the centre station and a pair
of extras goes to the outermost pair of stations. The group sizes are a palindrome by
construction, so group j and group N - 1 - j hold the same number of trees and, by section 8,
take mirror-image feet.

The centre tree of an odd row at an even Type is the one place where the two readings of the
ladder touch, and it is worth being exact about it. PARAM RULED ON IT ON 2026-09-01: THE CENTRAL
COLUMN STANDS STRAIGHT. His words in the review that opened this round were that the fault was
"just moving the standing coloumn for symmetry reasons away from center when it shold obviously
default to center", so the column that stands alone belongs at the centre, plumb, and is not to
be folded into a flank.

The construction that delivers it is the one already written. The Type places N mirrored shared
feet and NOTHING at the centre, which is the ladder's own rule for an even count, and the centre
tree's own column is not one of them, as section 5 states. It cannot join either flank group
without choosing a side that nothing decides, which is the defect this wave exists to remove, so
it stands alone on its own foot. That foot is its own group's central notch, which lies on the
span's plane of symmetry exactly when the span's notch row is symmetric about it and otherwise
stands where its own notch stands, as section 8.6 says; the spec does not claim more, and no
step projects the foot onto any plane. A span of odd tree count at Type 2 therefore shows two
shared feet and one central column, three feet in all, which is what the engine builds today and
what the harness pins. Type still names the number of GATHERED feet per span, and the
diagnostics report the central column separately so that the count is never a surprise.

The rejected alternative is recorded rather than deleted, in section 18: the centre tree could
have joined the flank group whose foot is nearer, ties going to the lower chord parameter, and
the middle column would then lean to a side. That is exactly the move he named and refused.

Worked against the fixture the investigation measured, and the fixture is named in full because
its numbers are quoted as a control: a ten metre arch of ELEVEN nodes, rise 2.5, anchored at
both ends, unit downward pull at every node, Branching 1, so nine free notches at chord
parameters 0.1 to 0.9 and T is 9. Feet are quoted in metres from the span's plan midpoint.

- Type 1. One group of nine. Its foot is the group's central notch, parameter 0.5, so 0.0. Four
  trees then peel, not two: at rise 2.5 the notch at x = 1 stands 0.9 above ground and 4 metres
  in plan from the foot, a lean of 77.3 degrees, and the notch at x = 2 stands 1.6 above ground
  and 3 metres out, a lean of 61.9 degrees, both past the sixty degree cap, while the notch at
  x = 3 leans 43.6 degrees and stays. The feet are therefore -4, -3, 0, 0, 0, 0, 0, 3, 4, five
  distinct feet, with Peeled 4. Those are the engine's own measured numbers, pinned in the smoke
  harness today, and the new rule reproduces every one of them; the two-peel answer belongs to
  an arch of rise 5 and is not this fixture. The peel now takes each pair together, by section
  11.
- Type 2. Nine is odd and two is even, so the centre tree stands alone at 0.0 and the remaining
  eight split four and four. The left group holds the notches at 0.1 to 0.4, an even count, so
  its foot is the mean of its two central notches, parameter 0.25, which is 2.5 metres from the
  midpoint. Feet at -2.5, -2.5, -2.5, -2.5, 0, 2.5, 2.5, 2.5, 2.5. That is the measured control
  to the last digit.
- Type 3. Three groups of three. Each flank group's central notch is at 0.2 and at 0.8, and the
  centre group's is at 0.5. Feet at -3, -3, -3, 0, 0, 0, 3, 3, 3. The measured control exactly.
- Type 4. The centre tree stands alone and the other eight split two, two, two and two. The
  groups' central pairs mean to 0.15, 0.35, 0.65 and 0.85. Feet at -3.5, -3.5, -1.5, -1.5, 0,
  1.5, 1.5, 3.5, 3.5. The measured control exactly.

So on a clean symmetric span the redesign does not move one column. What changes is that those
same numbers now come out on a span that has an off-centre crest, a crossing, a free end or a
coarse mesh, where the engine as it stands hands back a foot set 10 to 30 per cent of the span
away from mirrored. That is the whole claim of this spec, and section 17 makes it a measurement
rather than an argument.

Two further consequences are worth stating. A group's membership is decided by counting trees,
so no solve change can move a tree from one group to another, which is the direct answer to the
band arithmetic that flipped on floor(s * N) at a boundary. And the feet of two ribs alike in
notch count and spacing come out at the same parameters because the counting is the same and the
nodes are the same, so matching ribs match without any family averaging of positions at all.

## 8. Where a foot stands: the candidates, the convergence, and the snap

Param's ruling, quoted:

    "the columns if branching from one point, seriously struggle to ever be centered correctly.
    this i think is because for some reason taking the center of the object doesnt give the
    center of the principle lines, and even taking the center of them also doesnt always (I
    actually dont know why maybe a bug), so best is to take the closest points to center from the
    principle lines and then get them to all point inwards where they touch, maybe this will give
    the exact placement for that all branching from center point."

So no centre and no centroid is taken. The construction below is his, stated as arithmetic, and
it is used for every foot on every span, not only the central one, because a group's foot is the
same question asked of a shorter stretch of the same line.

### 8.1 The candidates

A foot serves one GROUP of trees on one span, or, after section 12, several groups on several
spans. Each participating group contributes its CANDIDATE POINTS, which are the closest points
to that group's own centre on that group's own line. Param's phrase is "the closest points to
center from the principle lines", so the rule below is a genuine NEAREST search and not a
middle-by-index rule wearing its name; on an evenly spaced row the two agree, and on a row of
notches placed at equal ARC LENGTH, which is what a relaxed net gives, they do not.

- THE GROUP'S CENTRE is a chord parameter, and it is defined here because three readings of the
  phrase are possible and they differ on any unevenly spaced group. It is
  (t_min + t_max) / 2, the midpoint of the stretch of chord the group's own notches occupy,
  where t_min and t_max are the smallest and largest chord parameters among them. It is not the
  mean of all the group's parameters, not the middle index, and not any plane of the span. The
  midpoint of the stretch is chosen because it is the centre of the group's own piece of the
  principal line, which is what his phrase names, and because it commutes with the mirror.
- List the group's free notches. There is always at least one. Every notch of the group is
  listed, whether it is owned or borrowed at a shared node, because a borrowed notch is still a
  point on this line.
- The CANDIDATES are the notches whose chord parameter is nearest the group's centre. One notch
  is the candidate where it is nearer than every other by more than TAU_snap. Where two or more
  are within TAU_snap of the nearest distance, every one of them is a candidate, and the foot is
  their plan mean. There is no further tie-break: the mean of any set of tied candidates is
  well defined, is independent of the order they are listed in, and commutes with the mirror.
- On an evenly spaced row this reduces to the familiar answer, and the reduction is stated so
  that it can be checked: an ODD count gives one candidate, the middle notch; an EVEN count
  gives two, the two middle notches, tied to the last bit.

Notches, not tree mains, because the notches are the points on the principal line, which is what
Param's rule names, and because a group's notch row is a mirror image of its partner group's
notch row exactly when the span's notch row is symmetric. Taking mains instead would give the
same answer on every symmetric span and a slightly different one on an asymmetric one, and there
is no reason to prefer it.

A foot is a plan point taken at the GROUND LEVEL read in section 3 step 1, and every foot in
this spec stands at that level. Nothing below moves a foot in Z, so the height clause in section
12's weld is trivial for two span feet and has something to compare only where the ring tree's
fixed foot, which is also at ground, is involved.

### 8.2 Pointing inward

Each candidate point p on span S contributes a LINE in plan: the line through p along the span's
own plan tangent at p, which is the unit plan vector from the bar position before p to the bar
position after p, normalised. At a bar end only one neighbour exists and that single segment is
used. Where the tangent is NOT DEFINED by the bound of section 4, that is where the plan
separation of the two points it is taken between is at most 1e-9 * L, the span's chord direction
c is used instead. That bound applies to the centred difference and to the one-sided segment at
a bar end alike, and it is a bound rather than an exact-coincidence test because exact
coincidence never occurs in a solved net, so a test for it would never fire and would leave a
near-zero vector to be normalised, which is the failure the clause exists to prevent.

POINTING INWARD IS THE GUARD, AND NOTHING ELSE. It is worth saying flatly, because the obvious
reading of Param's phrase is an oriented solve and that reading is arithmetically empty here. A
line has no direction; the least-squares form of 8.3 is built from the projector (I - d d^T),
which is identical for d and for -d, exactly as the ring tree's own solve is. Orienting each
tangent toward the company would therefore be a step no later step reads, and no fixture could
be written that fails when it is dropped. So there is no orientation step. Inwardness is
expressed once, as a stated proximity rule: the converged point must lie within the convergence
guard of the CONVEX HULL of the candidate points it was converged from, and otherwise the mean
is used instead. That is a rule a fixture can catch, and 8.4 states it.

### 8.3 The convergence

Where the candidates come from MORE THAN ONE SPAN, the foot is the plan point nearest all their
lines at once, the same least-squares intersection the ring tree already uses for the bars' end
tangents:

    minimise, over x in plan, the sum over candidates of |(I - d d^T) (x - p)|^2

with d the unit tangent and p the candidate point. The sign of d is immaterial, since it enters
only through the projector. The normal equations are a two by two system, A x = b with A the sum
of (I - d d^T) and b the sum of (I - d d^T) p, solved when |det A| > 1e-9 * max(trace(A)^2,
1e-12) and otherwise declared SINGULAR.

Where the candidates come from ONE span only, the foot is the plan MEAN of the candidate points,
and the least-squares system is not solved at all. This is a deliberate restriction of his rule
to the case he was describing, which is several principal lines branching from one point, and it
is there to stop a defect the harness would otherwise find: on a bar that curves gently in plan
the two central notches' tangents are nearly parallel and meet hundreds of metres away toward
the centre of curvature, and on a bar that curves sharply they meet within the guard but off the
bar by up to one notch spacing. A single line does not need to be intersected with itself to
find its own middle. With one candidate the mean is that notch, which is Param's "defer directly
to the center node"; with two it is their midpoint, which is dead centre and under the bar.

### 8.4 The guard, and what happens when the directions do not meet

The inward directions will not meet at one point in general, and three outcomes are stated so
that none of them is discovered in the field.

- SINGULAR. The system fails the determinant test, which is what parallel tangents give: a
  planar arch, whose plan tangents all run along the chord, or two parallel ribs. The foot is
  the plan MEAN of the candidate points. This is the ring tree's own fallback, and it is the
  common case for a barrel vault, where it lands exactly where the mean would have put it
  anyway.
- OUT OF REACH. The system solves, but the solution lies further than the convergence guard from
  the convex hull of the candidate points, the guard being g of the span, or min(g) over the
  spans taking part, and 0.25 * min(g) for a MERGED foot by section 4. The foot is the plan
  MEAN, and the level counts it in Level.ConvergenceFallback. This is the near-parallel case,
  where a small change of tangent moves the intersection a long way, and taking it would be
  following noise a hundred metres out.
- ACCEPTED. The solution lies within the guard of the hull. The foot is that point. This is the
  case Param described: several ribs whose central notches genuinely converge, meeting where they
  touch.

The mean is the fallback everywhere because the mean commutes with any reflection, whatever the
chords' directions, which the centre of an axis-aligned bounding box does not. That defect was
found and fixed once in this file already, for band feet, and the same reasoning binds here.

### 8.5 The snap

Param's ruling is that a foot SNAPS to the plan position of the nearest principal node to its
target, so a column stands plumb under a notch and the feet of matching ribs line up because the
nodes do. The construction above satisfies it in the ordinary case and states the one exception.

- A group whose nearest notch is nearer than every other by more than TAU_snap has ONE candidate,
  the foot is that candidate, and the column stands plumb under a real notch. On an evenly
  spaced row that is every group of odd count. On a row that is not evenly spaced an odd group
  can still tie two notches within TAU_snap, in which case it takes the even answer below, and
  the guarantee is stated in that form rather than by count so that it is true as written.
- A group with two tied candidates has its foot at their midpoint, which is not a node. It is
  NOT snapped to either of them. Snapping would move the foot half a notch
  spacing to a side chosen by nothing, and on the centre group it would move the one column
  the review asked to be straight. The two candidate notches are equidistant from the foot, the
  foot is exactly on the group's own centre, and on a span whose notch row is symmetric it is
  exactly on that row's plane of symmetry. This is the single stated departure from the letter of
  the snap ruling and it is recorded in section 18 for his ruling.
- A group with THREE OR MORE tied candidates stands at their plan mean by the same reasoning,
  which on coincident candidates is that one point and is therefore a node after all.
- A MERGED foot, from section 12, stands at the convergence point, and it snaps to a node only
  in one case: where the merging spans share a net node and the convergence point lies within the
  merge clearance of it, the foot is that node's plan position. That is the crossing case, and
  standing the column exactly on the shared node is both tidier and what the author drew.

The SNAP DISTANCE of a foot is the plan distance from the foot to the nearest candidate notch,
reported as a fraction of the span's own g and as a length, so that a coarse bar shows up as a
coarse bar rather than as a surprise.

### 8.6 Mirrored feet, by construction

Group j and group N - 1 - j hold the same number of trees and, on a span whose notch row is
symmetric, mirror-image notch rows. Their candidate sets are therefore mirror images, the mean
commutes with the mirror, the least-squares construction commutes with the mirror because it is
built from the candidates and their tangents, and the two feet come out exact mirror images. No
test decides this and nothing can disengage it.

Where the notch row is NOT symmetric, because of a free bar end, an off-centre crest or a genuine
lopsided solve, the two feet are symmetric in the span's own indexing rather than in space: each
group's foot sits at its own group's centre, and the feet are as mirrored as the notches are.
That is the honest answer, it degrades continuously rather than at a cliff, and it is what makes
the whole class of triggers in section 1 stop mattering.

Two consequences of that honesty are stated here so that no later section can overclaim them.
The centre tree of an odd row at an even Type stands on its own group's central notch, and that
notch lies on the span's plane of symmetry exactly when the notch row is symmetric about it; on
the off-centre-crest fixture it measurably does not, and the foot is off the plane by however
far the notch is. And where one tree of a mirror pair holds a BORROWED main notch and its
partner does not, section 10 gives the two different head mains, so their Type 0 feet differ by
up to one notch spacing. Neither is a defect to be corrected by projecting a foot onto a plane;
projecting would move a column nothing asked to move.

## 9. The common mode, the structural mirror, the pairing and the families

Five things happen to a span's resultants, in the order of the subsections below, and the FIRST
of them is what actually cures the one-sided lean. Mirror pairing survives, but it decides far
less than it did, and that is the point. It no longer decides a foot, a band or a merge, and,
above all, it no longer decides whether the common mode goes.

### 9.1 The common mode goes first, by subtraction, not by pairing

The design input's first numbered change, measured rather than argued, is that what must go is
the span's MEAN along-chord pull, a rigid-body tilt no column should follow; that subtracting
that mean is defined for any notch list whatever, needs no pairing, no tolerance and no test,
and is continuous in the node positions, so it cannot cliff; and that pairing then only refines
what is left, so an unpartnered notch costs nothing. This spec does exactly that.

    Read every non-ring tree's resultant in its own span's frame as (along, across, down), along
    the chord from the span's first node to its last, across it in plan, and down. For each
    span, let A be the MEAN of the along parts over the span's trees that carry a resultant at
    all. Subtract A from every one of them. Do this unconditionally: for a span of one tree, for
    a span with a free end, for a span whose every tree is unpaired, for a span with a crossing,
    for a closed span where it will make no difference, and for every other span. There is no
    test to fail and no state in which the step is skipped.

    Trees that carry NO resultant take no part in the mean and are not moved by it. A tree all
    of whose notches are borrowed at shared nodes (section 10) is such a tree: it has no load and
    a zero resultant, and averaging it in would drag a whole span's aim toward zero.

    The RING TREE is not in this at all. It has no span and no chord, its foot is fixed, and it
    is not symmetrised.

This is what the engine does not do today. Its Symmetrise hands a span that failed its pairing
test its RAW resultants entire, common along-chord component included, and every foot on that
rib then walks the same way down the chord: the investigation measured a mean foot shift of
+0.663 and a worst mirror error of 2.171 on a net whose only fault was a crossing near a
springing, and it measured the cliff at about a centimetre wide, one notch nudged from 0.20 to
0.21 taking every column on every rib from perfectly mirrored to displaced most of a metre in
one direction. Subtraction has no cliff because it has no threshold.

### 9.2 The mirror plane comes from the structure, not from the anchors

The design input's second numbered change is that the span's first and last node are an artefact
of where the anchor cluster stops, and that the physical mirror is where the along-chord pull
changes sign, which fixes the unequal anchor cluster and the off-centre crest in one move and
degrades gracefully on a genuinely asymmetric vault instead of forcing a symmetry onto it. The
AIM MIRROR named in section 4 is located as follows, and it is located on the RESIDUAL that 9.1
leaves, because a common mode can hold a whole span's along parts to one sign and hide the
crossing entirely.

    Take the span's trees SORTED BY THEIR MAIN NOTCH'S CHORD PARAMETER, which is the one place
    in this spec that reads parameter order rather than bar order, and rightly so: a sign change
    is a fact about the chord and not about the node numbering, and on a bar that is not
    plan-monotone the two orders differ. Ties in parameter are ordered by the lower bar position,
    which cannot change the located plane because the two trees stand at one parameter. Each tree
    carries its residual along part a. Let A_mag be the mean of |resultant| over those trees. A
    residual is DEEMED ZERO when |a| <= 1e-9 * A_mag; where A_mag is itself zero, every residual
    is deemed zero.

    A SIGN CHANGE stands between two trees consecutive in that order whose residuals are deemed
    non-zero and have opposite signs, and its parameter is found by linear interpolation on the
    two residuals between the two parameters. A tree whose residual is deemed zero is itself a
    sign change, at its own parameter; that is the exact limit of the interpolation, so the
    located plane moves continuously as a residual passes through zero.

    Where there is exactly one sign change, s_mirror is its parameter. Where there are SEVERAL,
    s_mirror is the one nearest the ROW CENTRE BY PARAMETER of section 4; ties go to the smaller
    parameter, which can only happen on a row symmetric about that centre, where the two answers
    differ by nothing that matters. Where there is NONE, which is a span whose residual alongs
    are all deemed zero, and a span of fewer than two trees, s_mirror is the row centre by
    parameter itself.

    s_mirror is not clamped to the chord. A span whose pull changes sign outside its own cuts is
    telling the truth about itself and the pairing below will simply refuse most of its trees,
    which now costs them only the sharing of one partner's across and down.

The fallback deserves its justification, because it is the case the unequal anchor cluster
reaches on a plumb-loaded net. Where every residual along is zero the aim is plumb everywhere,
there is no lean to get wrong, and the plane decides nothing but which trees share an across and
a down. Where the along parts are real, the sign change is the crest, and it is the crest that
the input measured being made to lean 7.4 degrees while the chord midpoint was made plumb. Under
this rule the crest tree is the one that is CENTRAL, so it is the one whose along part is
zeroed, and it is the one that stands plumb.

It is worth being explicit about what this does NOT do. No foot reads s_mirror. The layout of
section 6, the foot groups of section 7, the candidates and the convergence of section 8, and
the mirror test of section 12 are all taken by INDEX on the row centre by index. So deriving the
plane from the pull does not put a force back in charge of a position at Types 1 to 4, and the
fixture that scales one flank's pulls by 1.1 and asserts that no unpeeled foot moves still
holds. At Type 0 the aim decides the position by definition, and there the change is the point.

### 9.3 The pairing, per tree, by parameter

The pairing is PER TREE and within one span, and it is by CHORD PARAMETER REFLECTION, which is
his carried ruling in as many words: a tree at parameter s pairs with whichever tree sits
nearest its reflection within a stated tolerance, and an unpartnered tree simply stands alone.
An index rule was considered and is not used, because on a row of notches at equal ARC LENGTH,
which is what a relaxed net gives, the tree nearest the reflection of tree i can be T - 2 - i
rather than T - 1 - i, and the index rule would then refuse a pair his rule accepts.

- The REFLECTION of tree i is r_i = 2 * s_mirror - s_i, with s_i its main notch's chord
  parameter. Its candidate partner is the tree j whose main notch parameter is nearest r_i. Ties
  are broken in favour of j = T - 1 - i, then in favour of the lower index in bar order.
- The pair is ACCEPTED when three things hold: the mismatch |s_i + s_j - 2 * s_mirror| is at
  most h / 4; the pairing is MUTUAL, so that i is also j's nearest; and the two trees hold the
  SAME NUMBER of notches. The layout of section 6 is a palindrome, so the count condition is
  satisfied by construction whenever j is T - 1 - i, and it bites only where the parameter
  search reaches across a size boundary. No tree is taken by more than one partner.
- A tree is SELF-PAIRED when it is its own nearest, which happens when it is CENTRAL in the
  sense of section 4, its self-mismatch |2 * (s_i - s_mirror)| being at most h / 4.
- Everything else is UNPAIRED. An unpaired tree keeps what 9.1 left it and stands alone; it is
  not refused anything else, and its span is not touched. Because the common mode has already
  gone, an unpaired tree no longer carries one, which is the whole difference from today.
- A tree with NO OWNED NOTCH takes no part: it is unpaired, its candidate partner is unpaired
  too and keeps its own across and down, and it joins no family. Pairing a loaded tree with an
  unloaded one would hand the loaded tree half its own down component.

Placement.Partner keeps its name and its three values: the partner's index, the tree's own index
for a self-paired tree, and -1 for an unpaired tree and for the ring tree. Placement.CentreTrees
keeps its name and counts self-paired trees. Placement.AsymmetricSpans is RETIRED, because no
span is placed unmirrored any more, and Placement.UnpairedTrees replaces it.

### 9.4 Symmetrise, and the invariant it must leave behind

Symmetrise keeps its arithmetic, with 9.1 in front of it and one repetition behind it. Each
tree's resultant is read in its span's frame as along, across and down; 9.1's mean subtraction
has already run; an accepted pair has its along parts made equal and opposite about their mean
difference and its across and down parts replaced by the pair's means; a self-paired tree has
its along part set to zero; an unpaired tree is left as 9.1 left it; the family averaging of 9.5
then runs; THE SPAN MEAN IS SUBTRACTED ONCE MORE; and only then does the dead band apply, so
that an aim within PlumbDegrees of vertical is vertical. The ring tree is not symmetrised at
all. The idempotence guard, keyed on the flag and on the tree count, stays.

The second subtraction is not a new rule but the enforcement of the first one, and it is needed
because the pair step can put a common mode back. An accepted pair sums to zero along the chord
and a self-paired tree is zero, so on a span where every tree is paired the second subtraction
is exactly zero and changes nothing. On a span holding unpaired trees it is not: with residuals
1, -2 and 1, pairing the outer two to zero leaves a mean of -2/3 that was not there before. The
invariant this spec asserts is therefore stated once and enforced by construction: AFTER
PLACEMENT, EVERY SPAN'S MEAN ALONG-CHORD COMPONENT IS ZERO.

The dead band is the one thing that can disturb it, because it rounds a near-plumb aim to
exactly vertical per tree. That is deliberate and it is not a common mode, so the residual
measure below simply does not read those trees.

### 9.5 The residual, which is the number that must be reported

The design input's fourth numbered change is that the diagnostic reports the RESIDUAL, so that
it cannot read clean when the rule was skipped. The reason is measured: AsymmetryRemoved FELL
from 75.40 degrees to 1.81 the moment the mirror rule stopped running, because an unmirrored
span's aim is never moved, so the number reads most reassuringly exactly when the machinery has
been bypassed. AsymmetryRemoved keeps its name and its meaning, because it answers a different
question, but it is no longer the number a reviewer should look at.

    Placement.CommonModeResidual is added. For each span, take the along parts of its non-ring
    trees AS PLACED, excluding trees the dead band moved and excluding trees with no owned
    notch; let their mean be A_S and let the mean of their |resultant| be A_mag. The span's
    residual is |A_S| / A_mag, a pure ratio in the span's own frame, and zero where the set is
    empty or A_mag is zero. CommonModeResidual is the LARGEST of them over the net.

It reads zero when the rule worked, and it reads large exactly when it did not: on the measured
broken net the surviving common mode was a fifth of the pull. It is reported in columns.symmetry
beside AsymmetryRemoved, and section 17 requires it to be zero on every fixture and requires a
fixture on which it goes RED with the subtraction removed.

FAMILIES keep their rule and gain one condition. A family is the spans alike in free notch count,
in Branching, which is one slider and therefore alike by construction, and in chord length within
a tenth of the family LEAD's, and a family shares the ALONG and DOWN profiles by tree index while
every span keeps its OWN across. The reasoning recorded in the file stands and is not repeated
here beyond its conclusion: along and down are node-order invariant after the pair step, along by
being antisymmetric and down by being symmetric, so tree i of one span is the same tree of the
family whichever way either bar was traced, while across comes out negated and there is no rule
for which way round a span is that does not fail on a rib lying in the structure's own mirror
plane.

The new condition is that only a CLOSED span may join a family, a closed span being one in which
every tree is paired or self-paired. The invariance that lets profiles be shared by index holds
for a set of trees that pairs off completely and fails as soon as one tree is unpaired, because
reversing the bar then moves the unpaired tree to a different index. A span holding an unpaired
tree is its own family and keeps its own aims. The existing guard that drops a family whose spans
disagree on tree count stays.

The family average cannot reintroduce a common mode: it averages zero-mean along profiles by
index, and the mean of zero-mean profiles is zero-mean.

One whole-span gate therefore survives, and only one: the family average of the aim. It is worth
being plain about the cost, and about what it is NOT. An asymmetric span no longer takes its
neighbours' along and down profiles. At Types 1 to 4 that costs nothing visible, because the aim
decides no position there. At Type 0 it costs a small disagreement of aim between a lopsided span
and its neighbours, which is the truth about that span. What it does not cost, and this is the
difference from the engine as it stands, is the common mode: that has already gone by 9.1,
unconditionally, on the family-less span as on every other. The alternative is a silently wrong
average, and the investigation measured what a silently wrong answer looks like on this
component.

## 10. Where two principal lines touch

Param's ruling, quoted:

    "Also on this the two principle lines can be touching eachother and so we need to make sure
    we arent placing duplicate points over each other then one of them gets cancelled out becuase
    cant have two connections on one node which then throws off the symmetry algorithm. this
    might be what is getting it to go wrong often."

The investigation settled what actually happens, and the answer is worth stating before the rule,
because it moves the target. At a shared node today there is no duplicate point and nothing is
cancelled: the block comes back with exactly one head at the shared node, every free net vertex
carrying a head, no member dropped and no net node carrying two heads. The held set already
refuses the duplicate. What goes wrong is the HOLE the claim leaves: the losing span's free list
is no longer symmetric about its own chord midpoint, so it fails the pairing test by a factor of
3.6 on the measured fixture, and the whole span falls back to unmirrored placement, moving its
feet 10 to 30 per cent of the span. Two further losses were measured: the other bar's vertical
pull at that node is never counted, so eighteen units applied came back as seventeen; and where
the claim takes a span's only free notch, that span reports "declared free 1, notches held 0" and
contributes no columns at all. And which line loses is decided by bar order alone, so the answer
flips when Pattern traces the other curve first.

The rule, in four parts.

- BOTH LINES HOLD THE NOTCH. A notch shared by two bars stays in the free list of BOTH their
  spans. It is grouped, counted, paired and used as a candidate by both, exactly as if the other
  line were not there. Neither span acquires a hole, so neither span's symmetry can be broken by
  a crossing, and the bar order cannot change any layout. The held set keeps its OTHER job
  unchanged, which is the ring tree's: a rim notch held by the ring tree still cuts the spans and
  is still no span's free notch.
- ONE HEAD, ONE MEMBER, AND THREE LISTS THAT ARE NOT THE SAME LIST. The node is one point in
  space and carries exactly one column head, as it does today. Its OWNER is the span that builds
  the member to it. Because the difference between holding a notch and building to it is where
  an implementer would otherwise guess, the three lists are stated separately.
      Which notches enter the LAYOUT, the pairing, the group construction and the candidate set
      of section 8.1: ALL of them, owned and borrowed alike. A borrowed notch stays in
      Tree.Nodes, in bar order, so the palindrome stands and the row is the row section 6 built.
      Which notches enter Tree.Load and Tree.Resultant: the OWNED ones only. A borrowed notch
      enters Tree.Load with a load of zero and contributes nothing to Tree.Resultant, because its
      head is not that tree's to carry. Tree gains a parallel Owned flag per node so that this
      is readable rather than inferred.
      Which notches RECEIVE A MEMBER: the owned ones only.
  A tree all of whose notches are borrowed builds no member and no foot at all, carries no load,
  has a zero resultant, takes no part in pairing or in any family, and is still counted in its
  span's layout so that the palindrome stands.
- THE MAIN NOTCH STAYS; THE TRUNK RUNS TO THE HEAD MAIN. A tree's MAIN notch is its innermost,
  unchanged, and it is the notch whose parameter the pairing of section 9 reads, because that is
  what keeps the layout's symmetry legible. Where the main is BORROWED no member is built to it,
  so the tree's trunk, its fork and its Type 0 foot are taken against its HEAD MAIN, the tree's
  innermost OWNED notch, ties going to the lower bar position. The peel of section 11 measures
  the trunk that is actually built, foot to head main. Where the tree owns its main, which is
  every tree on a net with no crossing, the head main IS the main and every number is unchanged.
  A tree with no owned notch has no head main and builds nothing.
- THE OWNER IS DECIDED BY THE SPANS, NOT BY THE TRACE, AND THE RULE MUST NOT END IN BAR ORDER.
  The tie-break below is stated in full because the natural fixture for this rule reaches it: a
  regularly ribbed vault, a cross vault, a dome of equal ribs and hoops, all give two spans of
  equal notch count and equal chord, and ending the order on the bar index would make the answer
  depend on which curve Pattern traced first, which is the very finding this section answers.
  For a span S, write its ENDPOINT PAIR as its two cut nodes' plan positions sorted
  lexicographically by X then Y, which is a node-order invariant. The owner is decided by the
  first of these that separates the spans, each compared within 1e-9 * min(L_A, L_B) except the
  last:
      the greater FREE NOTCH COUNT;
      then the longer CHORD LENGTH;
      then the lower X of the endpoint pair's first point, then its lower Y;
      then the lower X of the endpoint pair's second point, then its lower Y;
      then the lower mean Z of the span's free notches;
      then, and only then, the lower bar index and the lower span index, which is reached only
      when the two spans are the same segment in space to within a billionth of their own
      length, where no choice between them can be seen.
  Every key is a property of the SPAN and not of the node, so every notch shared between the
  same two spans resolves the same way, which is what keeps a symmetric pair of crossings
  symmetric. The more central notch was considered and rejected for exactly that reason: it
  reads the node, and it can hand two mirrored shared notches to different owners.
- THE LOAD IS COUNTED ONCE, IN FULL, AND THE ARITHMETIC IS STATED BECAUSE THE OBVIOUS FORM IS
  WRONG. PARAM RULED ON 2026-09-01 THAT THIS IS TO BE FIXED PROPERLY: the two new arguments are
  threaded through and the head load at a shared node is counted exactly once and in full. The
  alternative of leaving it undercounted, which is what the engine does today, is rejected and is
  recorded as rejected in section 18. The naive sum of both bars' transverse pulls remains off
  the table for the reason immediately below. Summing the bars' transverse pulls at a shared node
  DOUBLE COUNTS. MouldGeometry.
  BarLoads sums every member incident on a node except the edges running ALONG that bar, on the
  ground that a beam does not load itself; so at a node shared by bars A and B, pull_A is the
  infill plus B's along-bar edges and pull_B is the infill plus A's along-bar edges, and their
  sum is the infill TWICE. On any real vault the infill dominates, so the head load at a crossing
  would come out close to double, and with it the axial force, the load path and Auto's choice.
  The measurement that eighteen units applied came back as seventeen was taken on hand-built
  transverse arrays, where each bar declares its own pull independently, and it does not license
  the sum on production data.
      Let the node be held by k DISTINCT bars. Two bars are the same run at a node when they
      reach it through the same two neighbouring net vertices, in either order; a run traced
      twice therefore counts once, which is what keeps columns.overlap true. Let total be the
      node's whole incident pull, taken once, and pull_1 to pull_k the bars' untransversed pulls
      there. The HEAD PULL is
          headPull = (pull_1 + ... + pull_k) - (k - 1) * total
      which is the node's infill pull exactly once, since each pull_i is total minus that bar's
      own along-bar contribution. For k = 1 it is pull_1 and nothing changes anywhere.
      The head pull is then projected off every distinct bar tangent at the node in turn, by
      Gram-Schmidt, a tangent being dropped when its residual norm falls to 1e-9 of its own
      length because it is parallel to one already taken. For k = 1 that is BarTransverse
      exactly, so every single-bar number in the harness is untouched. Where the surviving
      tangents span all three dimensions the residue is zero, AimFrom returns vertical, and the
      column stands plumb, which is the honest answer for a node whose every direction is
      already carried to an anchor.
      Tree.Load at the notch is the magnitude of the vertical component of that projected head
      pull, and Tree.Resultant sums it with the tree's other owned notches'.
  THE TWO NEW ARGUMENTS, CONCRETELY, because this is where an implementer would otherwise guess.

      WHERE THEY COME FROM. Both are already computable inside ColumnsComponent from the incident
      lists it builds at
      plugin/native_v02/Components/ColumnsComponent.cs, which walk the valid edges and carry each
      edge's member force. The first is the UNTRANSVERSED PULL, which is exactly what
      MouldGeometry.BarLoads returns today, per bar and per bar position: the sum over the node's
      incident edges, EXCLUDING the edges running along that bar, of the edge's absolute force
      divided by its length times the step to the far node. The component already calls it, at
      the line that reads MouldGeometry.BarLoads(bars[b], nodes, incident), and then throws it
      away after passing it to BarTransverse. It is now kept and passed on. The second is the
      PER-NODE WHOLE PULL, a new MouldGeometry.NodeLoads over the same incident lists with NO
      exclusions at all: the same sum, over every incident edge without exception. It is a
      function beside BarLoads and not a change to it, which is what keeps BarLoads out of scope
      by section 19.

      WHAT CARRIES THEM. The untransversed pull is a Vector3d[][], indexed by bar and then by bar
      position, the same shape as the transverse array the engine already takes. The per-node
      whole pull is a Vector3d[], indexed by net node, one entry for every node whether or not any
      bar reaches it. Neither is optional and neither has a default: a null or short array is a
      programming error and not a fallback, because the arithmetic below has no answer without
      them.

      WHAT THE SIGNATURE BECOMES. ColumnPlacement.Place today reads

          Place(Point3d[] nodes, int[][] bars, int[] anchors, Vector3d[][] across,
                int[][] perimeterLoops, double ground, double medianPlanEdge,
                int branching, int groundAsked)

      and becomes

          Place(Point3d[] nodes, int[][] bars, (int, int)[] edges, int[] anchors,
                Vector3d[][] across, Vector3d[][] pull, Vector3d[] nodePull,
                int[][] perimeterLoops, double ground,
                int branching, int groundAsked)

      with medianPlanEdge GONE by section 4, edges placed after bars so the call reads net first
      by section 12, and pull and nodePull placed immediately after across because they are the
      same measurement at three levels of exclusion. ColumnsComponent passes ValidEdges' output,
      keeps the BarLoads array it already computes rather than discarding it, calls the new
      NodeLoads, and stops calling MouldGeometry.MedianEdgeLength for this component. Nothing else
      in the signature changes and no other caller exists.

  Section 16 restates the same three additions from the diagnostics' side.

Four measured consequences follow, and section 17 requires all four.

- THE EIGHTEEN UNITS COME BACK AS EIGHTEEN. The investigation applied eighteen units of vertical
  pull to a net whose two bars share one node and measured seventeen counted, the missing unit
  being the other bar's share at the crossing. Under the rule above head_load_total reads
  EIGHTEEN on that fixture, and it is the measured case that must now come out right. It is not
  an approximate improvement and the harness asserts equality, not a bound.

- The crossed arch places the same LAYOUT, the same groups, the same pairing and the same feet
  at Types 1 to 4 as the uncrossed control, because none of that arithmetic reads a force. It
  does NOT place the same feet at Type 0, and the spec will not pretend it does: a Type 0 foot
  is where the ray from a notch along its aim meets the ground, the aim at the shared node now
  carries the rib's infill, and the pair step spreads the changed across and down over the mirror
  pair. Section 17 asserts the difference against the contribution the check computes itself.
- The answer is identical with the bars handed over in either order.
- A crossing at the span's own centre, and a symmetric pair of crossings, both continue to place
  mirrored feet, which they already do today and which any new rule had to reproduce.

### AMENDMENT, PARAM'S RULING OF 2026-09-02: A SIDE NEVER TAKES THE LEFTOVER CENTRE

Param reviewed the installed build on his own arch and on a three-way vault. This rule is added
on top of the owner rule above rather than in place of it. His words:

    "no the symmetry isnt the angle its the amount of branches per side on an equal form. One
    branch always reaches to the center while the other side doesnt ebcause we rule that only one
    branch can touch the central node, this is where an additional branch is introduced on one
    side. it is visible in the 3-4 screenshots. even in the 3 sided and beyond same problem. So i
    am suggesting keep everything as it is, but when there is a center node that is left over and
    a side want to connect to it, just put a central column in and keep the nodes connections the
    same"

THE DEFECT IS A COUNT AND NOT AN ANGLE. Where two principal lines MEET, the crown is a bar END
and so a free notch of both spans, and the owner rule above hands it to one of them. That span's
crown-end tree then builds one more branch than its mirror on the other line: four against three
on a form that is otherwise symmetric. MEASURED before the rule, over Types 0 to 4 and Branching
1 to 3: two lines meeting at a crown read [4, 5] at five free notches a side and [3, 4] at four,
at Branching 2 and 3 and at every Type; the three-way vault reads [4, 4, 5] and [3, 3, 4] on the
same grid. Fifty configurations in all. Branching 1 is already right, because the ladder gives
the crown a tree of its own there, which is the answer this rule generalises.

THE RULE. A shared notch is LEFT OVER when the group that owns it is not BALANCED about it: a
group is a contiguous run of free indices, so it is balanced about the notch at the mean of its
two ends, which is a notch at all only where the group's size is odd. A left-over notch is NOT
built to by the side that owns it. It is taken out and stands on a CENTRE COLUMN of its own: one
tree, one notch, its own foot directly beneath it, standing plumb at every Type.

WHAT DOES NOT MOVE, and this is the whole of "keep the nodes connections the same".

- THE NOTCH STAYS IN EVERY SPAN'S Tree.Nodes, borrowed on all of them. Group, Layout, the
  pairing, the foot groups and the ladder therefore see the identical row.
- NO GROUP FOOT MOVES. A Type 1 to 4 foot is a function of notch POSITIONS and the Type alone;
  GroupFoot's candidates are gathered whether a notch is owned or borrowed, so ownership never
  enters it. MEASURED across every crown fixture at every Type and Branching: not one existing
  foot moves, and the only change is one tree added on one foot.
- THE ARITHMETIC IS A MOVE, NOT AN ADDITION. The head pull leaves the annexing tree's Load and
  Resultant entire and arrives entire on the centre column, so the total load is unchanged; the
  annexing tree builds one member fewer and the centre column builds one, so the total member
  count is unchanged. Feet gain one per extracted notch, unless the new foot welds.
- A GENUINELY CENTRAL NOTCH IS LEFT ALONE. Where two lines CROSS rather than meet, the crossing
  is interior and lands in a straddling tree that is balanced about it, so nothing is extracted
  and the engine is untouched. That is the case whose branch counts were already equal.

THE CENTRE COLUMN CARRIES Span = -1 AND Bar = -1, and this is the trap. BuildLevel's row already
skips a tree with a fixed foot and the cross-line merge of section 12 already refuses Span < 0,
but the CENTRAL-PAIR merge builds its row from Ring and Span alone and does not consult the fixed
foot: filing this column under the owner's span would flip that row's parity from odd to even,
fire that merge and move two feet. It carries the owner span's FRAME instead, so that its
collision clearance and its weld and close tolerances are in that span's own terms; without it
the ring tree's fallback would return the hardcoded 1.0, which on a model in metres would
mis-scale a clearance, and a collision gates Feasible, which gates which Type Auto places.

WHERE THE RULE REACHES FURTHEST, recorded because it is wider than the forms Param photographed.
On a regularly ribbed grid the same predicate fires at off-centre crossings: on a 3 by 3 grid of
nine-node lines, six of nine crossings at Branching 2 and 3, carrying 11.532 of vertical load.
The branch counts either side were already equal there, because the annexations pair up about the
plane, so this is the rule generalising rather than a fault being repaired. MEASURED consequence
on that net: at Types 2, 3 and 4 nothing moves at all; at Type 0 six feet move, because a Type 0
foot IS the tree's own force ray and that tree's force genuinely changed; and at Type 1 and
Branching 2 six feet move because a tree that has lost a notch now leans past the cap from the
shared foot and peels, taking its mirror with it. Every one of those movements is mirror-
symmetric, and none of them is on a form of lines meeting.

## 11. The peel

A trunk may not lean past MaxLeanDegrees, which is sixty degrees and is a limit of the machine's
sliding joint rather than a preference. The peel is what the engine does when a shared foot is
out of reach, and it stays, with one change: it acts on a MIRROR PAIR.

- After the feet are placed, a tree whose trunk from its assigned foot to its HEAD MAIN leans
  past the cap PEELS: it stands instead on its Type 0 foot, where the ray from its head main
  along its symmetrised aim meets the ground. The head main rather than the main, because the
  peel exists to keep the trunk that is actually built inside the machine's joint, and on a tree
  whose main is borrowed no trunk runs to the main at all.
- A tree that peels takes its mirror PARTNER with it, whether or not the partner is over the cap.
  Both feet are then Type 0 feet, and they are mirror images wherever the two head mains are
  mirror images, because section 9 made the two aims mirror images; where one of the pair holds a
  borrowed main and the other does not, the two head mains are not mirror images and the two
  feet differ by up to one notch spacing, which 8.6 already records. Both members count in
  Level.Peeled. An unpaired tree peels alone. A self-paired tree peels onto its own Type 0 foot,
  which has no along-chord component because the pair step set its along aim to zero, so it
  stands directly under its own head main along the chord; it lies on the span's plane of
  symmetry exactly when that notch does, and no step projects it there.
- A peel NEVER MOVES A FOOT. A foot's position does not depend on the trees standing on it, so
  the rebuild-and-rejudge loop that the band rule needed is gone with the bands. A foot left with
  no trees is not built. That holds after a merge too: a tree that peels off a merged foot does
  not cause the merged foot to be re-converged.
- THE PEEL IS JUDGED TWICE, not once, and the earlier draft's reasoning for judging it once was
  wrong. It said that nothing the peel does can put another tree over the cap, which is true of
  the peel. It is not true of the MERGE that follows it in section 12: a merged foot is a fresh
  convergence and it moves, so a trunk sitting just inside sixty degrees before the merge can
  stand past it afterwards. So the test runs again over the trees standing on a shared or merged
  foot, after step 10. The second pass cannot cascade, because peeling is one-way, a peeled tree
  never rejoins a shared foot, and no foot moves on account of a peel; a tree that peels in the
  second pass takes its partner with it exactly as in the first. Section 12 also forbids a merge
  whose converged foot would put a participating trunk over the cap, so in practice the second
  pass finds nothing, and the harness is required to demonstrate that rather than to assume it.

### ERRATUM, 2026-09-02: three sentences of this section are superseded

Recorded here rather than by rewriting the paragraphs above, so the reasoning that produced them
stays legible. Where this erratum and the text above disagree, the erratum governs.

1. "A tree that peels takes its mirror PARTNER with it" and "An unpaired tree peels alone" are
   SUPERSEDED BY PARAM'S RULING OF 2026-09-02. The peel now takes its mirror by the same GROUP-INDEX
   rule the feet use, read off the span's own row, and no longer consults the pairing at all. The
   reason is that this wave moved foot position off the pairing and onto the group ladder, so a peel
   that still read the pairing left ONE unmirrored flank column while every other foot was symmetric
   by construction, which made the orphan conspicuous rather than lost in the noise. Measured before
   the fix on the seventeen-notch Type 1 net: trees 3 and 13 are mutual nearest partners but their
   positional mismatch of 0.0182 exceeds h/4 of 0.0142 by 28 per cent, so they went unpaired, tree 3
   crossed the cap and peeled alone, and the foot mirror error was 2.7715 against a baseline spread
   of 0.2465 to 0.2925. The tolerance h/4 was NOT widened; the peel simply stopped depending on the
   pairing, as the feet already had.

2. "In practice the second pass finds nothing, and the harness is required to demonstrate that
   rather than to assume it" is MEASURED FALSE in both halves. The reason the sentence gives, that
   section 12 forbids a merge whose converged foot would put a trunk over the cap, holds for RULE 3,
   the cross-line merge, alone. RULE 2, the central pair of an even tree row, moves its two feet onto
   their mean with no lean test anywhere, and where the pair's two Type 0 feet stand uncrossed and
   inside the central-pair clearance that mean lies OUTWARD of both, so both trunks can finish past
   the cap. At Type 0 the first pass does not run at all, which leaves the second pass as the only
   thing standing between rule 2 and an unbuildable trunk. It is now demonstrated rather than
   assumed: a fixture stands two trunks at 63.316 and 63.562 degrees and the second pass catches
   both, and disabling the pass turns the harness red. Before that fixture existed the entire pass
   could be deleted with the suite staying green and its output byte-identical.

3. "A foot left with no trees is not built" is NOT YET TRUE OF THE ENGINE. This is an open defect
   rather than a correction. Every node is added to Level.Feet unconditionally, so after a
   second-pass peel the abandoned merged foot remains in Level.Nodes and Level.Feet with no tree
   standing on it. It was unreachable until the fixture above first made the second pass fire.

When can it still fire, once the feet are decided first? Exactly when a tree's assigned foot
stands further from its head main in plan than 1.732 times that notch's height above the ground,
which is tan of sixty degrees. In practice that is a low anchor-end notch on a wide flat span at
a low Type, which is precisely the measured control at Type 1, where FOUR trees of the nine notch
rise-2.5 arch peel to their own feet, the flank trunks leaning 77.3 and 61.9 degrees. A tree
whose head main is at or below ground cannot satisfy the cap from any foot and always peels.

The peel rate under the new rule is not asserted here, because the earlier draft asserted it and
was arguing rather than measuring. Section 17 requires the peel count at each of Types 1 to 4 to
be recorded on the review arch and on the plan-curved bar, before and after, so the change is a
number in the record.

## 12. Welding, merging across lines, and standing close

FOUR distinct things happen to feet once they are placed, and they are not the same thing. The
third of them, the same-span central pair, is in the engine today and is kept; the earlier draft
of this section deleted it without a word, which would have broken two green fixtures and
returned two columns to the middle of every even tree row at Type 0.

WELDING. Two feet whose plan distance is at most TAU_weld, and whose heights agree to the same
bound, are ONE node. This is positional identity and not a decision: two groups of one span that
converged to the same notch, two spans whose feet landed on a shared crossing notch, the ring
tree's foot coinciding with a span foot. It is not counted as a merge and it moves nothing.
Since every foot stands at the ground level of section 3 step 1, the height clause is trivial
between two span feet and is live only where the ring tree's fixed foot is one of the two.

THE CENTRAL PAIR OF AN EVEN TREE ROW. Where a span's tree count is EVEN there is no centre tree,
so its two innermost trees are a mirror pair straddling the middle of the row with nothing
between them. When their two feet lie within the CENTRAL-PAIR CLEARANCE of section 4, a quarter
of that span's own notch spacing, they stand on ONE foot at the MEAN of the two. That is the
engine's present rule restated in the span's own terms, and the reason it is kept rather than
retired is that it is what gives an even row the single central column an odd row gets for free.
The mean of the two feet and not the span's chord midpoint: a pair's two feet differ only in
their along-chord part, so the clearance says nothing about how far off the chord they sit, and
on a bar that curves in plan merging onto the chord midpoint moved the pair sideways by the plan
sagitta, out from under its own bar. No OTHER pair of one span merges, and an odd row merges
nothing, which is why a span whose centre tree stands on the plane with its neighbours leaning
in toward it keeps three columns and not one; welding those was what turned leaning neighbours
into accidental V's and X's on the review arch. The clearance has changed scale, from
0.05 * medianPlanEdge to 0.25 * g, and section 17 requires the before and after on the fixtures
that pin it.

CROSS-LINE MERGING is Param's ruling that feet on ADJACENT principal lines become one column
where they already fall within a clearance of each other, never always and never not at all.

- Two spans are ADJACENT when a free notch of one is joined by a net EDGE to a free notch of the
  other, or when they share a notch. That test needs the net's edge list, which the engine does
  not receive today, so ColumnPlacement.Place takes it as a new argument; ColumnsComponent
  already computes it through MouldGeometry.ValidEdges. Adjacency by edge is exact, it is
  invariant under a rotation of the model and under any remesh that does not change the topology,
  and it needs no distance scale of its own.
- Two feet of adjacent spans A and B are a MERGE CANDIDATE when their plan distance is at most
  0.25 * min(g_A, g_B).
- A candidate is ACCEPTED only if its MIRROR is also a candidate. THE MIRROR IS TAKEN BY GROUP
  INDEX and never by reflecting a point and searching, because two spans have two different
  planes and "their mirror-image feet" would otherwise name no actual foot: the mirror of the
  candidate joining group j of span A to group j' of span B is the candidate joining group
  N_A - 1 - j of A to group N_B - 1 - j' of B, with N_A and N_B those spans' own group counts.
  Where the two spans carry different group counts, which they do whenever their tree counts
  fall either side of the Type's own arithmetic, the mirror candidate is the one the same
  reflection names on each span separately, and where either span has no group at that index the
  candidate is REFUSED. A candidate is also accepted where BOTH its feet are the central foot of
  their own span, that is the foot of the middle group of an odd group count or the centre
  tree's own foot; and where one is central and the other is not, which is what a rib meeting an
  arch at the crown gives, the mirror of the candidate is the candidate joining the same central
  foot to the flank group's mirror, and the ordinary rule decides. Otherwise the candidate is
  REFUSED and counted in Level.MergeRefused. Accepting one of a mirrored pair of merges and not
  the other is exactly how two matching columns stop matching.
- The mirror test READS THE FEET AS STEP 8 PLACED THEM, never a foot that another merge in the
  same pass has already moved. Reading moved feet would make the answer depend on the order the
  candidates were considered in, which is the order dependence the connected-component rule
  below exists to remove.
- A candidate is also REFUSED where the foot it would converge to puts any trunk that would
  stand on it past MaxLeanDegrees. A merge that hands a tree a foot it cannot reach has bought
  tidiness with a peel, and the peel would then undo the merge. Such a refusal is counted in
  Level.MergeRefused like any other.
- Accepted candidates are resolved as CONNECTED COMPONENTS and not pairwise in sequence, so a
  run of three adjacent ribs whose feet all fall inside the clearance becomes one column, taken
  once. Pairwise sequential merging is order dependent; this is not.
- The merged foot is the CONVERGENCE of section 8 over all the candidate points of all the
  merging groups, with their own tangents, its guard at 0.25 * min(g) over the spans taking part,
  which is the merge clearance that declared the feet to be together in the first place and not
  the whole spacing an unmerged foot is allowed, and the plan mean as its fallback. This is the
  case Param's rule was written for, several
  principal lines branching from one point, and it is the one place the least-squares
  intersection is used for a span foot. Where the merging spans share a net node and the
  convergence lands within the merge clearance of it, the merged foot snaps to that node.
- The ring tree's foot never merges. It is fixed by the ring rule and it is not on a span.
- Merging is bounded rather than exact, and the spec says so. When two spans' mirror planes do
  not coincide, a merged foot cannot lie on both, and each span's own pair symmetry is disturbed
  by at most the merged group's radius, which is at most a quarter of the tighter span's notch
  spacing. That is inside the tolerance that declared the feet to be together in the first place.
- HOW OFTEN THIS ACTUALLY FIRES IS A MEASUREMENT, NOT AN ASSUMPTION, and the spec says plainly
  that it expects the answer to be seldom. Two spans are adjacent when a free notch of one is
  joined by a net edge to a free notch of the other, so their corresponding feet typically stand
  about one notch spacing apart, while the clearance is a quarter of that. On a net whose lines
  meet AT a crown node the two feet coincide instead and are WELDED, which is a different rule
  reaching the same picture, and that is the case Param's convergence language actually
  describes on his own model. Section 17 therefore requires the count of cross-line merges that
  fire on the review net, and the count of feet that stand close but apart, to be recorded as
  numbers in the check's message.

STANDING CLOSE BUT APART. Any two built feet within the FEET-CLOSE CLEARANCE of section 4 that
did not merge, whether because their spans are not adjacent, or because the mirror refused it,
or because they are two feet of one span that are not its central pair, are counted in
Level.FeetClose and reported. That clearance is 0.25 * min(g_A, g_B) between spans and 0.25 * g
within one span. It is the second of the two places the net median was still live, and its
scale has changed by a factor of five against the collision clearance it used to share a number
with, so section 17 records the before and after counts.

## 13. What the forces decide, and what they no longer decide

Param's ruling is that the columns are symmetric and uniform, force-informed, and that the forces
inform the LEAN and no longer decide the POSITION. Honoured properly that means the following,
and the spec would rather state the limit than claim more.

- The forces make the AIM: a tree's resultant, symmetrised over its mirror pair and its family,
  passed through AimFrom with its sixty degree cap and its plain vertical answer for a net that
  pulls a notch down onto its column.
- The aim decides a POSITION at Type 0 and nowhere else. Type 0 means each tree on its own foot
  on the line of the force it carries; that is what the level IS, and an author who asks for it
  is asking for the thrust line. Because the pairing is per tree, Type 0 is mirrored wherever a
  pair exists, which is most of a span even when its crest is off centre.
- At Types 1 to 4 the aim decides NOTHING about where a foot stands. The foot comes from the
  span's own notches and the Type. The trunk's lean is then geometry, foot to notch, and the
  spec will not pretend otherwise: with the foot fixed and the fork bound to the foot-to-notch
  segment, there is no free variable left for a force to set. What the aim still does at those
  levels is to be the thing the built column is MEASURED against, in the per-foot alignment
  measure and in the branch off-thrust measure, and to decide which trees peel together and
  where a peeled tree lands. It does NOT steer Animate. Animate re-aims nothing: the columns are
  rigid and stand where their feet and their notches put them, and Animate computes a thrust
  direction per node on each frame's own geometry only so that animate.column_alignment can
  MEASURE each trunk against it. That is what the file says in as many words, and the earlier
  draft of this sentence claimed the opposite, which would have invited an implementer either to
  change Animate or to assume a dependency that does not exist. One real interaction is worth
  recording rather than hiding: Animate's per-node live aim is written bar by bar, so at a shared
  node the LAST bar traced wins, which will not equal the engine's summed head aim under section
  10. Animate is out of scope by section 19, so this spec leaves that disagreement standing and
  names it for whoever takes Animate next.
- Under Auto the forces choose the arrangement, since the score is the load path, the sum over
  members of axial force times length, among the levels that do not collide.

If Param wants force back into the lean at Types 1 to 4 there are only two levers, and both are
worse than what they buy: letting the fork leave the foot-to-notch segment, which reintroduces
the kinked trunk that section 2 preserves against, or letting the force move the foot, which is
the position.

THIS ACCOUNT IS SETTLED AND NOT OPEN. It was listed for Param's confirmation on the suspicion
that it departed from his ruling, and section 18.2 records the controller's ruling that it does
not: his ruling is that the forces inform the lean and no longer decide the position, and with
the foot fixed by the ladder and the fork bound to the foot-to-notch segment there is no free
variable left for a force to set. So the honest statement, which is the one above, is the
consequence of his ruling rather than a departure from it, and the plan may be written against
it.

## 14. Type 0 and Auto

Type 0 is unchanged in rule. Each tree's foot is where the ray from its main notch along
AimFrom(Resultant) meets the ground, and AimFrom caps the lean, so the level is never refused for
lean or for alignment. Its feet take part in welding and in cross-line merging under section 12,
which is a change only in that the merge test is now the span-term clearance and that the
adjacency and mirror conditions apply. Its trees pair per tree, so its feet are mirrored wherever
the old whole-span gate would have abandoned the span.

Auto is unchanged. Every level from 4 down to 0 is built, Level.Feasible is Collisions == 0, the
shortest load path among the collision-free levels is placed, a tie goes to the higher level, and
when every level collides the shortest of them is placed anyway because a Result with no columns
breaks the chain. Auto's choice can move on nets where the collision clearance of section 4
changes the collision count, and section 17 requires that to be recorded.

GroundAsked and GroundPlaced keep their contract: with a Type asked, GroundPlaced equals
GroundAsked; under Auto, GroundPlaced is the level chosen. Neither reports the number of feet
actually built, which may be fewer than the Type where a span holds fewer trees than the Type
asks for, and is one more where an odd tree row at an even Type leaves a central column standing
alone. The diagnostics report both counts.

## 15. Degenerate spans, in full

Every case below is a rule, not an exception to be discovered in the field. Each one is a harness
fixture in section 17.

- A span with NO free notch holds no tree. It places no group and no foot, it is not counted in
  SpansWithTrees, and no symmetry rule touches it. Under section 10 this can now only happen
  where the ring tree took every notch, since a crossing no longer takes any.
- A span with ONE free notch holds one tree, whose layout is [1] by section 6, at the centre
  station because one is odd, and a stray there at Branching 2 and 3 but not at Branching 1,
  where a tree of one notch is what the slider asked for. Its h is the fallback 1 / (m + 1) = 0.5. Two things now
  happen to it that did not before, and they make its old boundary case vanish. Its common mode
  is its own along part, since the mean of one number is that number, so 9.1 zeroes it
  unconditionally: a lone notch off centre no longer leans down the chord at all. And its
  s_mirror falls back to the row centre by parameter, which for one notch IS that notch, so it
  is self-paired by construction. The investigation measured the old boundary on the engine as
  it stands, at parameter 0.44 passing the self-pairing test and 0.43 failing it, with 0.43
  dropping Families to 0 and disabling the whole span. Under this spec THE TWO PARAMETERS GIVE
  THE SAME ANSWER IN EVERY RESPECT, which is the strongest form the fixture can take and the
  form section 17 requires. At every Type from 1 to 4 the span places exactly ONE foot, at that
  notch, because T is 1 and T is at most N, so the tree is a group of one and its single
  candidate is its own notch. An even Type on a span of one tree therefore places one foot, not
  two and not three.
- A span with TWO free notches at Branching 1 has two trees, T = 2. At Type 1 they form one
  group of two, whose two candidates are its two notches, so the foot is their midpoint. At
  Types 2 to 4, T is at most N and each tree is a group of one standing under its own notch.
- A span whose notches ALL fall at one chord parameter, which is a bar that doubles back in plan,
  takes h from the fallback 1 / (m + 1) by the bound of section 4, and is otherwise an ordinary
  span: its layout, its trees and its mains come from section 6 by INDEX in bar order, which
  needs no parameter at all, and its feet come from section 8, whose group centre is then one
  parameter and whose candidates are therefore every notch of the group, tied, so the foot is
  their plan mean. Its s_mirror is the row centre by parameter, that same one value, so every
  tree is central and every along part is zero, which is the right answer for a bar with no plan
  extent to lean along. It raises columns.span_degenerate at warning. Nothing refuses the level.
- A span whose CHORD LENGTH is zero by the bound of section 4, which is a bar whose two cut nodes
  coincide in plan, has no chord direction and no parameter. It still gets its LAYOUT and its
  MAINS from section 6, which read only the bar order and the count, so it still builds trees and
  members; that must be said, because a span with no layout could build nothing at all. It is
  every tree of it treated as unpaired, no common mode to remove because there is no chord to
  read one along, ONE foot at the plan mean of its free notches whatever the Type, and
  columns.span_degenerate raised. This is a stated answer rather than a division by zero. Where
  the span's plan bounding box diagonal D is also zero, so that every node stands at one plan
  point, the same answer holds and the one foot is that point.
- A tree whose HEAD MAIN is at or below GROUND cannot meet the lean cap from any foot. It peels,
  with its partner, and its Type 0 foot lies directly under that notch because the aim ray has no
  rise to travel.
- A TREE whose MAIN notch is borrowed but which owns others keeps the main for the layout and
  the pairing and runs its trunk to its head main, by section 10. A TREE with no owned notch
  builds no member and no foot, carries no load, has a zero resultant, is unpaired, leaves its
  candidate partner unpaired, joins no family, takes no part in the common-mode mean or the
  residual, and is still counted in its span's layout so that the palindrome stands.
- A GROUP whose trees are all borrowed at shared nodes builds no member and no foot. Its notches
  are held by the other line, which is the correct outcome and not an omission. Its span's other
  groups are unaffected, and the group is still counted in the group table so that the mirror by
  group index of section 12 keeps its indices.
- The RING TREE is in none of this. It has no span, no chord, no parameter, no pairing, no group,
  no convergence, no peel and no merge, and its foot is fixed.

## 16. Engine surface, diagnostics and the component

ColumnPlacement.Place LOSES the medianPlanEdge argument and GAINS three things: the net's edge
list as (int, int)[], placed after bars so that the call reads net first; the UNTRANSVERSED pull
per bar and bar position, the array MouldGeometry.BarLoads already returns; and the whole
incident pull per NODE, which is a new MouldGeometry.NodeLoads over the same incident lists with
no exclusions at all. Nothing else in the signature changes, and section 10 writes the old and
new signatures out in full so that the plan copies rather than reconstructs them. The last two
are Param's ruling of 2026-09-01 made arithmetic, and they add a function beside BarLoads rather
than changing it, which section 19 keeps out of scope. ColumnsComponent passes ValidEdges'
output, keeps the BarLoads array it already computes instead of discarding it after BarTransverse,
calls NodeLoads, and stops computing MouldGeometry.MedianEdgeLength for this component.

On Placement: Partner, CentreTrees, Families, SpansWithTrees, AsymmetryRemoved, Symmetrised and
SymmetrisedTrees keep their names and meanings, with CentreTrees now counting self-paired trees.
AsymmetricSpans is REPLACED by UnpairedTrees. ClosedSpans is added, the spans every tree of which
is paired or self-paired. SharedNotches is added, the notches held by two spans at once.
CentresExtracted is added by the amendment to section 10, the shared notches taken out of the
group that would have annexed them and stood on a column of their own; it is reported inside
columns.shared_nodes with a `centres` context key, and it is deliberately NOT folded into
Level.CentralColumns, which counts the standing column an odd tree row takes at an even Type and
nothing else. One is a property of the LAYOUT and differs per level; the other is a property of
the NET and is the same at every level, and a reader who cannot tell them apart cannot tell why a
column is where it is. CommonModeResidual is added, defined in 9.5, the largest along-chord
common mode still standing
after placement as a fraction of its own span's mean pull, which reads zero when the rule ran.
Clearance is RETIRED: it reported one number for the whole net, taken from the median, and there
is no longer one number to report, since every clearance in this spec belongs to a span or to a
pair of spans. Nothing reads it and nothing replaces it; a summary that meant anything would have
to name which span it came from, and the per-span numbers are already in columns.snap and
columns.feet_close.

On Tree: Owned is added, a flag per node saying whether this tree builds a member to that notch,
so that section 10's three lists are readable rather than inferred. HeadMain is added, the index
into Nodes of the tree's innermost OWNED notch, which is 0 on every tree that owns its main.

On Level: Peeled, FeetMerged, FeetClose, Feet, WorstLean, WorstAlignment, WorstBranchOff,
Collisions, PlumbTrees, LoadPath, Feasible, Rule and Value keep their names and meanings. Banded
is RENAMED Gathered, and it counts the trees a level ASSIGNED to a shared foot, BEFORE the peel
runs, which is exactly what Banded counts today. That is not a quibble: the component reads
nothingGathered as Gathered > 0 and Peeled >= Gathered to say "nothing gathered: every trunk
would lean past the cap; the columns stand as Type 0", and counting the trees still standing on
a shared foot after the peel would make that test degenerate and the state unreachable. The
harness pins both readings, Gathered 9 with four peeled at Type 1 on the review arch and
Gathered 8 at Type 2 where the centre tree takes no shared foot. CentralColumns is added and is
defined BY CONSTRUCTION, as the trees section 7 extracts by its "T is ODD and N is EVEN" clause,
never by testing a distance to a plane, because on an asymmetric notch row that foot is not on
the plane and a positional test would need a bound nothing has given it. ConvergenceFallback,
MergeRefused and SnapWorst, the largest snap distance as a fraction of its own span's g, are
added. FeetMerged counts accepted merge GROUPS of both kinds, the same-span central pair and the
cross-line component.

The diagnostics all keep the columns. prefix and the source name Columns, so Diagnose reads them
without change.

- columns.grouping keeps its code and reports the layout: the trees, the notches held, the
  strays and where the ladder put them, and the remainder trees smaller than Branching. The
  phrase about the remainder sitting at the anchors is replaced by the ladder's own words.
- columns.type keeps its code and its context keys and reports the Type asked and placed, the
  groups, the feet built, the central columns and the peels. Where every non-ring tree peeled it
  still says that the columns stand as Type 0.
- columns.symmetry keeps its code and reports the trees paired, the self-paired trees, the
  unpaired trees, the closed spans, the families, the largest angle an aim moved through, and
  the COMMON MODE RESIDUAL beside it. The phrase about spans placed unmirrored goes, because no
  span is placed unmirrored. AsymmetryRemoved is kept but is no longer the number to read: the
  investigation measured it FALLING from 75.40 degrees to 1.81 the moment the rule stopped
  running, so the entry names the residual as the number that reads zero when the rule worked
  and says so in as many words. It rises to warning when the residual is above 1e-9.
- columns.feet is new, at info: the groups, the convergences accepted, the convergences that
  fell back to the mean, the welds and the distinct feet built.
- columns.snap is new, at info, and at warning when the worst snap exceeds half its span's own
  spacing: how far the furthest foot stands from the nearest notch, as a fraction of that span's
  spacing and as a length, so that a coarse bar is visible as a coarse bar.
- columns.shared_nodes is new, at info: how many notches two principal lines share, that both
  spans hold them for layout and symmetry, which span owns each head, and that the load at each
  is counted once and in full.
- columns.feet_merged keeps its code and reports both kinds of merge group, the same-span
  central pair and the cross-line component, naming adjacency by net edge and the clearance in
  the spans' own terms.
- columns.feet_close keeps its code and its warning, on the FEET-CLOSE CLEARANCE of section 4,
  and names whether a merge was refused by the mirror rule or by the lean cap. The entry says
  that the clearance has changed scale, so an author comparing a saved definition's warnings
  before and after this wave is not left guessing.
- columns.span_degenerate is new, at warning, for the two degenerate spans of section 15.
- columns.alignment, columns.collision, columns.lean, columns.load_path,
  columns.branch_off_thrust, columns.head_load, columns.head_load_total, columns.load_split,
  columns.plumb_fallback, columns.spans, columns.ring_tree, columns.bar_shape,
  columns.principal_source, columns.no_principal_runs and columns.demand_only are unchanged in
  code and in content, save that head_load_total now reports the full load because section 10
  counts each shared node once and in full.
- columns.overlap keeps its code and its warning but its SENTENCE changes. It says today that
  the second trace "finds its notches already held and builds nothing of its own, so the columns
  are right"; under section 10 both traces hold the notch, the owner rule decides which builds,
  and the doubly traced run is deduplicated in the head-pull arithmetic so that its along-bar
  contribution is not subtracted twice. The entry says that instead.

The component keeps its GUID, its name, its three ports, its preview and its colour. Its Message
becomes "Type N, F feet" with ", C central" where central columns stand alone, ", P peeled" where
trunks peeled and ", U unpaired" where trees stood unpaired, prefixed "Auto: " under Auto. The
Type VALUE LIST ITEMS are unchanged, by section 2, so the canvas still reads "2 two feet" on a
span that will show three; the TOOLTIP is what carries the truth, and it is rewritten to say
that Type N gathers each span's trees onto N mirrored feet, that a foot stands where its group's
own central notches converge, and that a tree standing alone in the middle of an odd row at an
even Type keeps its own straight column, so the foot count can be one more than the Type or,
on a span of fewer trees, fewer. The Branching tooltip is
rewritten to the ladder: trees of B neighbouring notches, mirrored about the middle of each span,
with one stray at the centre, two at the ends, and three at the ends and the centre.

## 17. Harness: what must be measured

The Skin sub-project that has just finished is the reason this section is written the way it is.
Six adversarial rounds found six blocking defects there, and three of them were rules that
sounded right in a spec and were disproved only by building the thing and feeding it hostile
input: a match rule that was not invariant under a rotation of the model, a distance measure that
could not read nesting, and a classification that was one category short. Every one of them
survived review because the fixtures were tidy.

So the standard for this wave is that A FIXTURE THAT WOULD PASS WHETHER OR NOT THE RULE HELD IS
NOT A FIXTURE, and the fixtures that matter are the DELIBERATELY ASYMMETRIC ones. Every check
below must be demonstrated RED against the engine as it stands before the change, or, where the
check is a preservation pin, GREEN before and after; the implementer names in the plan the wrong
behaviour each one catches. Fixtures are hand-built arrays driven through ColumnPlacement by
reflection in tests/native_smoke/Program.cs, as ValidateColumnPlacement already does, and none of
them launches Rhino or calls Vector3d.Unitize.

The five hostile fixtures the investigation named come first, because each of them reaches the
present cliff and each must now be quiet.

- AN OFF-CENTRE CREST. A single arch of nine notches placed at equal ARC LENGTH along an arch
  whose crest sits at chord parameter 0.584 at rise over span 0.25, which is the measured first
  failing crest for that notch count and the geometry a relaxed cable net actually gives. The
  present engine reports AsymmetricSpans 1 on it, a notch defect of 0.0251 against a tolerance of
  0.025, and unmirrored feet at every Type. The tolerance is 0.025 under the old formula and
  0.025 under the new one as well, because these notches span 0.1 to 0.9 whichever way it is
  read; the check prints both. Assert: the layout is the section 6 table's row for m = 9 at each
  Branching; the feet at Types 1 to 4 are at the parameters the group construction predicts,
  computed in the check from the notch row and not copied from the engine, and computed by the
  NEAREST-TO-CENTRE rule of 8.1, which on this unevenly spaced row differs from the middle notch
  by index and would go green under either if the row were uniform; every group and its mirror
  hold the same number of trees; UnpairedTrees is the hand-computed count rather than a whole
  span disabled; and CommonModeResidual is zero to 1e-12. Assert that the tree at the CREST is
  the self-paired one and stands plumb along the chord, and that the tree at the chord midpoint
  does NOT, which is the direct test of section 9.2 and the exact inversion of the 7.4 degree
  defect the input measured.
      Then scale the pull vectors by 1.1 on ONE FLANK alone and assert that no foot of a tree
      that did NOT peel moves at all. The assertion is restricted to unpeeled trees on purpose:
      a peeled tree's foot IS aim-derived by section 11, so scaling a flank moves it, and the
      earlier draft's unrestricted form would have failed on its own control, where the Type 1
      row has four peels in range. Assert as well that the PEEL SET is unchanged by the scaling
      on both flanks together, and that both members of every peeling pair peel, which is the
      property section 11 actually claims.
      Then sweep the crest from 0.5 to 0.75 in steps of 0.0005 and assert that no foot of an
      UNPEELED tree jumps by more than one notch spacing between two consecutive steps, which is
      the continuity claim of section 7 and which band arithmetic fails by construction. Again
      the restriction is deliberate: the sixty degree cap is a hard switch from the group foot to
      the Type 0 foot, four metres away on this arch, so a tree crossing the cap during the sweep
      jumps by far more than a spacing and always will. Assert instead, for the peel, that the
      set of peeled trees changes by at most one mirror PAIR between consecutive steps and that
      it is mirror-symmetric at every step.
- A SPAN WHOSE NOTCH IS CLAIMED BY A CROSSING. The investigation's own fixture: a pillow surface
  ten metres square, an arch of eleven nodes along X at y = 5 and a rib of eleven nodes along Y
  at x = 3, both anchored at their ends, meeting at ONE shared node at the arch's position 3,
  which is off centre. Both spans therefore hold nine free notches AND equal chords, which is
  deliberate: it drives the owner rule of section 10 past both of its first two clauses and onto
  the geometric keys, where the arch's endpoint pair begins at (0, 5) and the rib's at (3, 0), so
  the ARCH owns by the lower X. Every regularly ribbed vault, cross vault and dome of equal ribs
  and hoops reaches that tie, so the fixture is the normal case and not a contrivance.
      Assert: the arch's free notch count is 9, not 8; its layout, its groups, its pairing and
      its feet at TYPES 1 TO 4 are IDENTICAL to the uncrossed control's, which the same check
      computes by running the control net in the same call; UnpairedTrees is 0;
      CommonModeResidual is zero; exactly one member ends at the shared node; no net node carries
      two heads; every free net vertex carries exactly one head; and SpansWithTrees counts both
      spans. Count heads and members from the BUILT MEMBER SET and the block's heads, never from
      Tree.Nodes, because under section 10 both spans' trees list the shared node and only one
      builds to it; the existing check counts through Tree.Nodes and must be rewritten.
      Do NOT assert that the Type 0 feet match the control's. They cannot: a Type 0 foot is
      aim-derived, the owning tree's resultant now carries the rib's infill by section 10, and
      the pair step spreads the changed across and down over its mirror pair. Assert instead
      that the Type 0 feet equal the positions the check itself computes from the summed head
      pull, and that their difference from the control is exactly the rib's contribution.
      Assert the head load rule on geometry that has REAL INCIDENT INFILL and not only on
      hand-built transverse arrays, because the arrays are what made the naive sum look right:
      build the net's incident members, take the node's own pull once, and assert head_load_total
      equals the applied total, both with and without the rib. A second fixture drives the same
      node with a rib carrying a deliberately large along-bar tension and asserts the head load
      does NOT rise with it, which is the check that catches the double count.
      THE MEASURED CASE MUST NOW COME OUT RIGHT, and it is the one the investigation recorded:
      eighteen units of vertical pull applied to a net whose two bars share one node came back as
      SEVENTEEN counted. Under Param's ruling of 2026-09-01 and the arithmetic of section 10 the
      check asserts EIGHTEEN APPLIED, EIGHTEEN COUNTED, as an equality to 1e-12 and not as a
      bound, and it prints the seventeen beside it so the fix is a number in the record. The check
      also drives the arithmetic at k = 1, an ordinary unshared notch, and asserts the head pull is
      that bar's own untransversed pull unchanged, so that the (k - 1) term is demonstrated to
      vanish rather than assumed to; and at k = 3, three bars through one node, where the head
      pull is the three pulls summed less twice the node's whole pull, so that the general form is
      exercised and not only the two-bar case.
      Then run the SAME net with the two bars handed over in the other order and assert the two
      placements are identical to 1e-12 in every foot, every member and every diagnostic count.
      That assertion is the one the present engine fails most alarmingly, giving AsymmetricSpans
      1 and Families 1 one way round and 0 and 2 the other, and it is also the assertion a
      tie-break ending in the bar index could never satisfy on this net.
- TWO PRINCIPAL LINES THAT TOUCH. The same two bars arranged so that they share one node WITHOUT
  crossing, the rib running up to the arch and stopping on it, so the shared node is the rib's
  END and is neither an anchor nor a rim notch. The expected owner is computed FROM THE RULE and
  not assumed: the rib is anchored at one end only, its free end is a free notch by the free-bar-
  end case below, so it holds TEN free notches against the arch's nine and THE RIB OWNS by the
  first clause. The earlier draft of this item asserted the arch, which is the rule read
  backwards, and an implementer following it would have coded the owner rule backwards or
  written a check that fails against a correct engine. Assert: the rib's span carries the shared
  node as a free notch of kind end, the arch carries it too, the RIB owns the head, the ARCH
  builds no member to it, the load at it is the node's own pull taken once, and the arch's
  layout, groups and Types 1 to 4 feet are again identical to the control's.
      Then add a SECOND case where the counts are deliberately unequal the other way, the rib
      shortened to five nodes, so that the count clause is exercised on its own and the arch
      owns; and a THIRD where the counts are equal and the chords are equal, so that the
      geometric keys decide, with the expected owner computed from the endpoint pairs in the
      check.
      Then move the rib so that it touches at the arch's CENTRE notch and assert the same. Then
      place TWO ribs touching at mirrored positions and assert the arch's feet are exactly
      mirrored and that both shared nodes resolve to the same owner, which is what keeps a
      regularly ribbed vault symmetric. Then assert the borrowing tree's own answer: where the
      borrowed notch is that tree's MAIN, its trunk runs to its head main and its fork lies on
      that segment; where every notch of a tree is borrowed, it builds nothing, carries no load,
      is unpaired, leaves its partner unpaired, and its span's palindrome still stands.
- EQUAL BRANCH COUNTS EITHER SIDE OF THE MIRROR, which is the amendment to section 10 and which
  NOTHING IN THE HARNESS MEASURED, which is why the defect shipped past every check above. A
  BRANCH is a member built to a net notch; on a form of lines MEETING, each line is one side of
  the mirror; and a column whose tree owns the centre notch and nothing else belongs to no side
  and is counted apart, because that is a column in the middle rather than a branch of a flank.
  Fixtures: a SINGLE-SPAN arch of nine free notches, one bar anchored both ends and no shared
  node anywhere, the control; and lines MEETING at one crown, two arms and three, at five free
  notches a side and at four, since the ladder lays an odd count out differently from an even
  one. Every one of them at every Type 0 to 4 and every Branching 1 to 3, because Param's own
  words are "even in the 3 sided and beyond same problem" and he did not confine it to a Type.
      Assert on the single-span arch that four branches stand either side of its mirror plane and
      one on it, and that every free notch carries exactly one head. Assert on the meeting forms
      that the crown carries EXACTLY ONE head whoever builds it; that every arm builds the same
      number of branches, which is its own free notch count less the crown; that exactly one
      column stands apart from the arms; and, stating the rule rather than inferring it, that NO
      TREE OWNS THE CROWN TOGETHER WITH NOTCHES OF ITS OWN FLANK.
      Assert the arithmetic invariants beside the counts, since a fix that gets the count right
      by creating or losing load would pass a count test: the total of every tree's Load equals
      the load the fixture applies, the crown's own head pull being zero where the meeting
      tangents span the vertical; and CentresExtracted reads ONE at Branching 2 and 3 and ZERO at
      Branching 1, where the ladder already stands the crown alone and the ruling must therefore
      change nothing at all. Where a centre column is made, assert its foot stands on the form's
      own axis directly beneath the crown at every Type, and that the tree carries no bar and no
      span, since filing it under the annexing span would fire the central-pair merge.
- A COARSE NET WHOSE NODES ARE FAR APART. One geometry, a crest at 0.60 at rise over span 0.25,
  sampled at 3, 5, 9 and 17 notches. The present engine passes its symmetry test at 3 and 5 and
  fails it at 9 and 17, because the geometric defect barely moves from 0.0284 to 0.0300 while the
  tolerance falls from 0.0625 to 0.0139: refining a mesh on unchanged geometry pushes the span
  over the cliff. Assert that at all four densities the layout is the table's row, the feet are at
  the group centres, no span is ever placed unmirrored, and the foot positions converge as the
  density rises rather than jumping between them. Assert also that the 3 notch case at Type 4
  places THREE feet and not four, and that the check names the reason.
  DEFERRAL, recorded 2026-09-01 against Task 4 and awaiting Param's sign-off, ledger item D1.
  Two of those four claims are written into the harness and RUN but not enforced, because Task 4
  neither owns nor can reach the defects they measure. "No span is ever placed unmirrored" throws
  at Type 1 with 9 notches, AsymmetricSpans reading 1, which is Symmetrise's own pre-existing
  quarter-spacing mechanism and exactly the regression this bullet already names in prose; it is
  owned by whichever task rewrites the pairing, where UnpairedTrees replaces AsymmetricSpans.
  "The foot positions converge as the density rises" throws at Type 2 with the outermost foot
  moving from 2.4088 to 0.9115 between two densities; it is owned by the multi-span least-squares
  smoothing of sections 8.2 to 8.4, which the single-span rule of 8.1 does not have. Both run on
  every harness pass and the suite reports them under DEFER with those measurements, and either
  turns the run RED the moment it starts passing, so the gap cannot outlive its cause.
- A SPAN OF ONE TREE. One free notch, at chord parameter 0.44 and again at 0.43, which is the
  measured boundary of the self-pairing test on the engine as it stands. Assert at both
  parameters and at Types 0, 1, 2, 3, 4 and Auto: exactly one foot, at that notch's plan
  position; no central foot added anywhere; no division by zero; the m <= 1 branch of h
  exercised; and the placements at 0.44 and 0.43 IDENTICAL in every foot, every member and every
  diagnostic count, including Partner, Families and CommonModeResidual. That is stronger than
  the earlier draft's "the only difference is whether the tree is self-paired", and it is what
  sections 9.1 and 9.2 now give: the mean of one along part is that along part, so subtracting
  it zeroes the tree unconditionally, and s_mirror falls back to the row centre by parameter,
  which for one notch is that notch, so the tree is self-paired either way. Today the 0.43 case
  drops Families to 0 and disables the span, so the check is red before and green after.

Three more fixtures come from the design input's own measurements and were missing from the
earlier draft entirely. Each of them is a net on which every present diagnostic reads clean.

- AN UNEQUAL ANCHOR CLUSTER. One bar of thirteen nodes with THREE anchors at one end and ONE at
  the other, so the span is cut at the innermost anchor and its chord no longer runs between the
  springings. The input records what happens today: the span still PASSES the symmetry test, its
  chord runs from the innermost anchor, the mirror plane sits off the crown, the pairing is off
  by one, and the column that should stand plumb stands half a notch from the crest. Assert: the
  span's s_mirror sits at the CREST, located from the sign change of the residual along-chord
  pull, and not at the chord midpoint; the self-paired tree is the crest tree; that tree's
  along-chord aim is zero and its Type 0 foot stands directly under its own notch along the
  chord; CommonModeResidual is zero; and the layout, the groups and the Types 1 to 4 feet are
  the ones the group construction predicts from the notch row. Then assert that MOVING one
  anchor, so that the cluster becomes equal, moves no foot by more than the notch it moved.
- A RAISED SPRINGING. The same bar with one springing raised above the other, which the input
  records as doing the same thing as an off-centre crest. Assert the same list, and assert in
  particular that the plumb column stands at the crest and NOT at the chord midpoint, which is
  the assertion that fails against a mirror taken from the cuts.
- THE RESIDUAL ITSELF. A span whose pulls carry a genuine along-chord COMMON MODE and not merely
  a mirrored bend, which the existing SkewArch fixture already provides through its skew
  parameter, driven with skew non-zero on a span holding at least one unpaired tree. Assert
  CommonModeResidual is zero to 1e-12 after placement; assert every foot is mirrored to 1e-9;
  then, with the mean subtraction of 9.1 disabled in the check's own copy of the arithmetic,
  assert the residual is above 0.1 and the feet are not mirrored, so the number is demonstrated
  to move rather than asserted to. Assert also that AsymmetryRemoved FALLS on the disabled run
  while the residual rises, which is the trap the input names and the reason the residual exists.

Then the rest, each of which catches a rule this spec states.

- THE CONTROL NUMBERS, and the control arch stated in full wherever they are quoted, because the
  earlier draft quoted them against an arch it never named and got the Type 1 row wrong. THE
  CONTROL ARCH IS ELEVEN NODES, TEN METRES WIDE, RISE 2.5, ANCHORED AT BOTH ENDS, UNIT DOWNWARD
  PULL AT EVERY NODE, BRANCHING 1: nine free notches one metre apart at chord parameters 0.1 to
  0.9. It must place feet, in metres from the plan midpoint, of -4 -3 -2 -1 0 1 2 3 4 at Type 0;
  -4 -3 0 0 0 0 0 3 4 at Type 1, five distinct feet with Peeled 4 and Gathered 9, the flank
  trunks leaning 77.3 and 61.9 degrees to the central foot while the next one in leans 43.6;
  -2.5 four times, 0, and 2.5 four times at Type 2, three distinct feet with Gathered 8 and
  CentralColumns 1; -3 -3 -3 0 0 0 3 3 3 at Type 3; and -3.5 -3.5 -1.5 -1.5 0 1.5 1.5 3.5 3.5 at
  Type 4. Those are the measured numbers of the engine as it stands, pinned in the harness today,
  and the redesign must reproduce every one of them. The two-peel answer belongs to an arch of
  rise 5 and must not be written against this one. Any deviation is a change to a clean span and
  must be argued before it is accepted.
- THE MIRROR DEFECT IS ZERO. On every fixture above, compute the worst mirror defect of the
  sorted foot list about the NOTCH ROW'S OWN centre, which on a symmetric row is the chord
  midpoint and on a lopsided one is not, and assert it is zero to 1e-9 wherever the notch row is
  symmetric, and no worse than the notch row's own defect wherever it is not. The present engine
  gives 1.0, 2.0, 3.0, 3.0 and 2.0 metres on the crossed span at Types 0 to 4. At Type 0 on a
  crossed span the bound is the notch row's defect plus the contribution of the other bar's pull,
  which the check computes rather than assumes.
- THE RESIDUE IS STILL REMOVED. The three arch fixture, three identical arches with a three
  degree solver residue on the middle one and one family. Assert AsymmetryRemoved is 3 both with
  and without a rib crossing the middle arch, that CommonModeResidual is zero in both runs, and
  that the middle arch's layout, groups and Types 1 to 4 feet match its two neighbours'. The
  present engine drops AsymmetryRemoved to 0 and moves that arch's feet off its neighbours' when
  the crossing is added. AsymmetryRemoved is pinned here as a preservation and NOT as evidence
  that the rule ran; the residual is the number that carries that claim, and section 16 says so.
- THE LADDER TABLES. Group's full table from section 6 pinned for B = 1, 2 and 3 and m = 1 to 13,
  layout by layout, and the foot group table of section 7 pinned for every T from 1 to 13 against
  every N from 1 to 4, sizes and centre column by centre column. These are pure counting and cost
  nothing to check, and they are what a future change to either rule will trip over. The B = 3
  rows are pinned to FEWEST STRAYS, which is Param's ruling of 2026-09-01, and the check must
  print the ENGINE's present row beside the spec's row for every count, so that the rows that
  move are numbers in the record and not a claim. FOUR rows move at Branching 3, m = 3, m = 7,
  m = 9 and m = 13, and NONE moves at Branching 1 or Branching 2; the check asserts that count
  as well as the rows, so that a future criterion change cannot quietly move a fifth. Assert also
  the stray count of every row, and assert that no changed row's stray count RISES, which is the
  property his ruling was chosen for and which the retired criterion failed at m = 5 and m = 11.
  Pin the MAINS as well as the sizes at m = 7 and m = 13 at Branching 3, 1, 3, 5 and 1, 4, 6, 8,
  11 against the engine's 2, 3, 4 and 2, 5, 6, 7, 10, because at those two counts the tree count
  does not change and the mains are the whole of what moves.
- HIS THREE CASES BY NAME. Three checks named for the ruling: a span whose layout leaves ONE
  stray asserts it at the centre notch and nowhere else; a span whose layout leaves TWO asserts
  them at the two end notches and asserts that nothing sits at the centre; a span whose layout
  leaves THREE asserts the two ends and the centre. Concretely, at Branching 2 those are m = 5,
  m = 6 and m = 7. At Branching 3, under fewest strays, they are m = 5 for one stray, which is
  [2,1,2] with the stray at the centre, and m = 8 for two, which is [1,3,3,1] with the strays at
  the ends and nothing at the centre; the three-stray case remains UNREACHABLE at Branching 3 and
  the check asserts that and says why, which is that three strays needs k = 1 with a half
  remainder of one, and at every such count k = 3 leaves none and wins. Note for the implementer
  that the m values at Branching 3 have MOVED with the criterion: m = 7 no longer leaves one
  stray, it leaves none, and m = 5 leaves one and not two.
- THE CENTRAL COLUMN STANDS STRAIGHT, which is his ruling of 2026-09-01 and needs a check of its
  own rather than riding on the control arch's foot list. On a span of ODD tree count at Types 2
  and 4, assert that the middle tree by index is extracted as a group of one, that CentralColumns
  counts it, that its foot is its own group's central notch and not the nearer flank group's
  foot, and that its trunk stands PLUMB, within PlumbDegrees of vertical, wherever the notch row
  is symmetric. Then assert the rejected alternative is not what the engine does: compute, in the
  check, the foot the centre tree would take if it joined the nearer flank group, assert it
  differs from the placed foot by the flank group's own offset, and assert the placed foot is the
  central one. On the off-centre-crest fixture assert instead the honest weaker claim of 8.6,
  that the central foot stands at its own notch and is off the plane by exactly however far that
  notch is, and that no step projects it onto the plane.
- A FREE BAR END. A bar anchored at one end only, eleven nodes, so the span is of kind end to
  anchor, its first notch sits at chord parameter 0 and it holds TEN free notches. The present
  engine reports AsymmetricSpans 1, a defect of 0.1 against a tolerance of 0.0227, and Families
  0, so the span joins no family at all. THE TOLERANCE MOVES HERE and the check prints both: the
  old formula 0.25 / (m + 1) gives 0.0227 and the new measured one, 0.25 * (0.9 - 0) / 9, gives
  0.025. Assert: the span places its full layout, its groups are palindromic, its feet sit at its
  own group centres, UnpairedTrees is the hand-computed count and not every tree,
  CommonModeResidual is zero, and the span is placed at every Type without any fallback.
- THE PLAN-CURVED BAR, reusing the existing PlanCurved fixture, WHICH HAS TEN NODES AND EIGHT
  FREE NOTCHES, an EVEN count. The earlier draft asked this fixture for an odd-count assertion
  it cannot carry, so the item is restated to the geometry that exists. At Type 1 the one group
  of eight has two tied candidates, the notches at chord u = -0.5 and 0.5, so its foot is their
  plan midpoint, chord (0, 160/81): assert the across part is the plan sagitta at those notches
  and not zero, which is the same claim the draft wanted and is true of this fixture. At Type 2
  assert the two feet are exact mirror images in the chord frame, each the midpoint of its own
  group's two central notches, chord (-2, 128/81) and (2, 128/81). Assert also that the single
  span convergence never solves a least-squares system, by asserting the foot equals the mean of
  its candidates exactly, which is the rule of 8.3 and which a version that intersected a curved
  bar's own tangents would fail by up to one notch spacing. A separate ODD-count case, the same
  bar with one node added so that nine free notches remain, carries the crown-notch assertion the
  draft wanted: at Type 1 the foot is the crown notch's own plan position.
- THE CONVERGENCE ITSELF. Three ribs of a dome whose central notches are distinct points and
  whose plan tangents genuinely meet: assert the merged foot is the least-squares point, computed
  independently in the check, and that it lies within the guard of the hull. Then flatten the
  ribs until the tangents are parallel to 1e-7 and assert the foot falls back to the plan mean
  and ConvergenceFallback counts it, rather than flying off to the far intersection. Then place
  two ribs crossing at a shared node and assert the merged foot is that node exactly.
- TOLERANCES ARE SPAN-LOCAL. One net holding two spans of very different notch density, five
  notches over ten metres and twenty-one over ten metres. Assert each span's layout, feet, pairing
  and unpaired count are bit-identical to the same span placed alone. Assert the engine's
  signature no longer accepts a median at all, which is the strongest possible form of this
  check, and additionally that scaling the entire net by 1000 scales every foot by 1000 to 1e-9
  relative, so that no absolute number has crept in.
- STABILITY UNDER NOISE. Take a symmetric arch, place it, then displace every node by a
  pseudo-random offset of 1e-6 times the chord length and place it again. Assert every tree keeps
  the same group, that no foot moves by more than 1e-5 times the chord, and that no diagnostic
  count changes. Band arithmetic fails this whenever a main notch sits near a boundary, which is
  what the centre notch of a uniform arch does at every even Type.
  CORRECTION, recorded 2026-09-01 against Task 4 and awaiting Param's sign-off, ledger item D3.
  Those two magnitudes collide with this spec's own section 8.1. In chord parameter a
  displacement of 1e-6 times the chord IS TAU_snap = 1e-6 * h, so the noise as written sits on
  the exact-tie boundary section 8.1 draws and crosses it by construction. Measured on the built
  engine, the literal pair throws at Type 2 with a foot moving 0.500002036, half a notch spacing,
  which is an exact-tie flip in the candidate selection on a perfectly symmetric arch at an even
  Type and not an instability in the placement. The offset should read 1e-9 times the chord
  against a bound of 1e-7 times the chord, three orders inside TAU_snap, which is what the
  harness now uses. The claim itself is unchanged; only the magnitudes are.
- NODE ORDER AND ROTATION INVARIANCE. Four congruent ribs, one traced backwards, one turned
  through 180 degrees in plan with its pulls turned with it, and one translated. Assert identical
  feet in the world to 1e-9 at Types 0, 2 and 3, and identical member sets.
- FAMILIES. A family of closed spans shares along and down profiles as before; a span holding one
  unpaired tree is its own family and does NOT take another's profile; and the crown rib lying in
  the structure's own mirror plane keeps its own across and its feet stand under its own notches
  across the chord, which is the existing fixture and must stay green.
- THE PEEL, AS A PAIR, AND JUDGED TWICE. A wide flat span at Type 1 where the flank trunks
  cannot reach: assert both members of each peeling pair peel, that their two feet are exact
  mirror images, that no foot moved as a consequence of any peel, and that a foot left with no
  trees is not built. Then a MERGE-THEN-PEEL case, built so that a trunk stands just inside sixty
  degrees before a cross-line merge and outside it after: assert either that the merge is refused
  and counted in MergeRefused, or that the second peel pass catches the trunk, and assert that a
  third pass changes nothing. Then RECORD, as a measured number in the check's message, the peel
  count at each of Types 1 to 4 on the control arch and on the plan-curved bar, before and after
  the change.
- NOT PLAN-MONOTONE. A bar whose chord parameter does NOT rise with its node order, which the
  engine's own comment records as a real case: assert the layout, the trees, the mains and the
  foot groups follow BAR ORDER, so that Branching still means neighbouring notches, while the
  pairing, the self-pairing and s_mirror read the chord PARAMETER. The check computes both
  answers and asserts they differ on this bar, so that a version reading the index where the
  parameter is meant, or the parameter where the index is meant, goes red rather than green.
  Include the tie case, two notches at one chord parameter, and assert the layout is unchanged by
  the order they are listed in.
  NOTE, recorded 2026-09-01 against Task 4, ledger item D2. Which two bar positions the fixture
  swaps is not free. Task 4's brief named positions 3 and 4, and both of those sit inside the one
  Branching-3 chunk [3,4,5], so the bar-order and parameter-order readings coincide and the
  fixture's own must-differ guard throws "on this bar they agree, so nothing is being tested".
  The swap must STRADDLE a chunk boundary. The harness swaps positions 2 and 3, on the boundary
  between the [1,2] and [3,4,5] trees, which is what makes the two readings differ.
- CROSS-LINE SHARING. Three parallel ribs joined by net edges: with the outer two moved so that
  their feet fall inside a quarter of the tighter spacing of the middle rib's, one column at the
  convergence of all three taken once as a connected component and not pairwise; with them moved
  apart, three columns and FeetClose counting the near pairs. Two ribs with NO net edge between
  them whose feet coincide within the clearance must NOT merge. A mirror-refused case: two
  adjacent ribs converging at one end so that one mirrored merge is inside the clearance and its
  mirror is not, where nothing merges and MergeRefused counts it, with the MIRROR TAKEN BY GROUP
  INDEX and the check computing the mirror candidate itself. A mixed case where one foot is
  central on its span and the other is not, which is what a rib meeting an arch at the crown
  gives, asserting the ruling of section 12 rather than leaving it to be guessed. A lean-refused
  case, where the converged foot would put one participating trunk past sixty degrees, asserting
  the merge is refused and counted. And an ORDER case: run the same net with the candidate pairs
  offered in three different orders and assert the merged set is identical, which is what reading
  the step 8 feet rather than already-merged ones buys.
- HOW OFTEN MERGING ACTUALLY FIRES. On the review net, record as numbers in the check's message
  the count of accepted cross-line merges, the count of accepted same-span central pairs, the
  count of welds, and the count of feet standing close but apart. The spec's own expectation is
  that cross-line merging is rare on a net whose lines meet at a shared node, because the feet
  coincide there and are welded instead, and the point of the record is that the expectation is
  a measurement rather than an assumption.
- THE SAME-SPAN CENTRAL PAIR. The two existing fixtures that pin it stay green, on the new
  clearance: the plan-curved bar at Type 0, eight trees, an even row, the innermost pair merging
  onto chord (0, 160/81) and NOT onto the chord midpoint, seven feet and FeetMerged 1; and the
  nudged ten-notch arch, the innermost pair merging at x = 4.49 exactly and not at the chord
  midpoint of 4.5. Assert both gaps against the new clearance, 0.111 and 0.032 against
  0.25 * g = 0.25, so the check shows why they still merge. And assert that the narrow bay
  fixture, which has an ODD tree row of five, merges NOTHING, because only an even row has a
  central pair; that is what keeps a centre column and its two leaning neighbours three columns
  rather than one, and it is the fixture that would flip if the merge were extended to any
  mirror pair.
- THE COLLISION CLEARANCE MOVED, AND IT DESTROYS A FIXTURE. Record the collision count and Auto's
  chosen level under the old net-median clearance and under the new span-term one, in the check's
  message, and assert the new counts are the ones the check computes from the span spacings. Then
  say plainly that the existing Auto collision fixture CANNOT SURVIVE: it drives a nine node arch
  eight wide at a median of 24 precisely so that 0.05 of the median is 1.2, and its seven plumb
  Type 0 members a unit apart collide six times. With the median gone that span's g is 1.0, the
  clearance is 0.05, seven members a unit apart never collide, and the fixture's premise dies,
  taking with it the only proof that Auto prefers a collision-free level. The REPLACEMENT is
  specified here rather than left to the implementer: the same arch with two neighbouring
  interior notches crowded to 0.02 * g apart in plan, a mesh the author can really produce, so
  that their two plumb Type 0 members stand inside 0.05 * g and collide, while at Type 1 they
  share a foot, share an end and cannot. Type 0 still carries the shortest load path, being plumb
  throughout, so Auto's preference for the collision-free level is still what is being measured.
  A second replacement covers the cross-span case, two spans whose members come within
  0.05 * min(g_A, g_B) of one another, because at a twentieth of a spacing two members of one
  span can barely collide at all.
- PRESERVATION PINS, each asserted as a failure and not as a comment. Every member of every
  fixture leaves lower end first. Every fork lies on its foot-to-main segment to 1e-9, and the
  lowered-fork case fires on an anchor-end tree at Branching 3 whose outer notch is below the
  fork height. The ring tree's foot is identical before and after this wave on the free-rim
  fixture, it never merges, and its rim notches still cut the spans, and its TAU_weld and its
  collision clearance come from its own rim scale R and never from a net median. Auto's chosen
  level equals the level the check recomputes from Tried. The Type value list items and values
  pin unchanged, all six of them, INCLUDING the item text "2 two feet" on a fixture that places
  three, which is the inaccuracy section 2 leaves standing knowingly and section 18 puts to
  Param; the check names it so that nobody later reads the green as agreement. Every columns.
  code this spec names is present on the emitted Result, the retired phrase about unmirrored
  spans is absent, the columns.overlap sentence is the new one, and Diagnose renders the set.
- NO NANS AND NO ESCAPES. On every fixture above, assert every foot is finite and lies within its
  span's own plan bounding box grown by one notch spacing plus the merge clearance, so that a
  foot beyond its own anchors is caught as a failure rather than read off a screenshot.

### 17.1 Every existing case, and what happens to it

The brief requires the spec to say what it changes, and a list of new fixtures is not that. The
existing ValidateColumnPlacement cases in tests/native_smoke/Program.cs are enumerated here by
their line at the time of writing, with a disposition each. A case not named below stays green
unchanged, and the plan must say so case by case rather than discovering it at the console.

- Line 6566, three ribs of one family, AsymmetricSpans 0. RE-PINNED: the field is retired, and
  the assertion becomes UnpairedTrees 0 and CommonModeResidual 0. The Families 1 assertion, the
  crown-bar across assertion and the profile assertions stay green untouched.
- Lines 6732 to 6815, the crossed eleven-notch arch "placed UNMIRRORED". DELETED WITH ITS RULE.
  Under section 10 the arch keeps nine free notches, the trees go from 9 to 10, no span is
  unmirrored and AsymmetricSpans is gone. The crossing fixture above replaces it, and the
  replacement must assert the OPPOSITE of what this case asserts, which is the clearest possible
  demonstration that the rule changed.
- Lines 6817 to 6858, the band foot as the centroid of its mains, plan-curved bar at Type 2.
  RE-PINNED to a number this spec states: eight trees, two groups of four, each group's two tied
  central notches meaning to chord (-2, 128/81) and (2, 128/81). The old pin, (-2, 40/27), was
  the centroid of four mains and is not what a group centre gives.
- Lines 6860 to 6895, the centre pair merging onto the mean of its two feet, plan-curved Type 0.
  STAYS GREEN, with the clearance restated from 0.05 * medianPlanEdge to 0.25 * g; the gap of
  1/9 sits inside 0.25 either way, the merged foot is still chord (0, 160/81), FeetMerged is
  still 1 and the feet still seven. The check prints both clearances.
- Lines 6897 to 6960, the plan-curved bar crossed, AsymmetricSpans 1 and eight trees. RE-PINNED:
  the curved bar keeps its eight free notches, the trees become nine, UnpairedTrees is 0, and
  the placement's layout and Types 1 to 4 feet equal the uncrossed control's.
- Lines 6962 to 6993, a band rebuilding its foot from the survivors of a peel, pinned at chord
  (0, 832/486). DELETED WITH ITS RULE, since section 11 states that a peel never moves a foot.
  Its replacement asserts the opposite on the same fixture: at Type 1 the one group of eight
  stands at chord (0, 160/81), the outermost trunk on each flank peels, and the foot DOES NOT
  MOVE to (0, 832/486) or anywhere else.
- Lines 7002 to 7045, Type 1 on the control arch. STAYS GREEN in every number, Peeled 4, five
  feet, the shared foot at x = 5; Banded 9 becomes Gathered 9, still counted before the peel.
- Lines 7047 to 7090, Type 2 on the control arch. STAYS GREEN, three feet, the centre tree on
  its own foot at x = 5, the two shared feet at 2.5 and 7.5; Banded 8 becomes Gathered 8, and
  CentralColumns 1 is added.
- Lines 7092 to 7113, the narrow bay where neighbours stay apart. STAYS GREEN in its merge
  count, because its tree row is ODD and only an even row has a central pair; the FeetClose count
  RISES on the new feet-close clearance, 0.25 * g = 0.167 against the old 0.033, and the check
  records both numbers.
- Lines 7115 to 7153, the nudged ten-notch arch, the central pair at x = 4.49. STAYS GREEN, with
  the clearance restated in span terms and AsymmetricSpans 0 becoming UnpairedTrees 0.
- Lines 7341 to 7386, the crossing held once by the lower bar. REWRITTEN: the head count must
  come from the built members and the block's heads and not from Tree.Nodes, since both spans now
  list the shared node; the trees go from five to six; the owner is still bar 0, but now BY THE
  GEOMETRIC KEYS, the arch's endpoint pair beginning at (-4, 0) against the rib's (0, -4), and
  the check must say so rather than saying "the lower-indexed bar"; the Type 1 feet still weld to
  one node and FeetMerged is still 0.
- Lines 7556 to 7591, Auto preferring the collision-free level. REPLACED, for the reason and with
  the geometry stated above; the old fixture cannot be built at 0.05 * g.
- Every case that names AsymmetricSpans anywhere, which is lines 6566, 6567, 6742, 6781, 6782,
  6813, 6814, 6941, 6945, 6946 and 7146, must be re-pinned or deleted with its case, because the
  field is gone.

## 18. What was ruled, and what is still open

This section was a list of questions. Param answered three of them on 2026-09-01 and the
controller answered four more, so it is now a record of decisions with a short list of open items
at the end. Nothing is departed from silently, and no rejected alternative is deleted: a later
reader is entitled to know what was considered and why it lost.

### 18.1 Ruled by Param, on 2026-09-01

CONFIRMED A SECOND TIME, LATER THE SAME DAY, ON CORRECTED ARITHMETIC. When he took the
fewest-strays ruling he was told that two Branching 3 layouts would move. Four move: m = 3, 7, 9
and 13. He was shown the four rows, the mains that shift at m = 7 and m = 13, and the alternative
of pinning those two counts to the shipped layout at the price of writing the ladder as a rule
plus two footnotes with no structural reason behind them. He took all four. The rule therefore
carries no exceptions, and the movement at m = 7 and m = 13 is accepted rather than tolerated.

The quotation this section rests ruling 1 on is now filed in the design input at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-columns-design-input.md,
section 2a, so an auditor no longer has to take it on trust from a relayed ruling.

- THE CENTRAL COLUMN AT AN EVEN TYPE: IT STANDS STRAIGHT. A span with an odd number of tree
  groups at an even Type shows N gathered feet plus one further column standing alone and plumb
  on the mirror plane, and a span with fewer trees than the Type asks for shows one foot per
  tree. The spec's reading, that the ladder governs the GATHERED feet and that the centre tree's
  own column is not one of them, is confirmed.
      THE GROUND IS NOW A QUOTATION AND NO LONGER THE ENGINE'S HABIT. The earlier entry rested
      the case on the fact that the engine already does it and the harness already pins three
      feet at Type 2 on a nine tree span, and it was careful to say that the sentence "the middle
      one should be straight" is a paraphrase of the review conversation and appears in no ruling
      of his. That correction stands and is still true of THAT sentence. What replaces it as the
      ground is a real quotation from the review that opened this round, in which he objected to
      "just moving the standing coloumn for symmetry reasons away from center when it shold
      obviously default to center". That is his own wording, it names the fault exactly, and it
      settles the question in favour of a plumb central column.
      The quotation reached this spec through the ruling relayed on 2026-09-01 and is not in
      docs/superpowers/specs/2026-09-01-columns-design-input.md, which predates it. Anyone
      auditing the provenance should look there and expect not to find it.
      THE REJECTED ALTERNATIVE, kept rather than deleted: the centre tree could have joined the
      flank group whose foot is nearer, ties going to the lower chord parameter, and the middle
      column would then lean to a side. It was rejected because it is precisely the move he
      named. Sections 5, 7 and 8.6 carry the ruling, and section 17 has a check of its own for
      it, which computes the flank foot the alternative would have given and asserts the engine
      does not take it.
      What the ruling does NOT buy, and 8.6 is careful about this: on a span whose notch row is
      lopsided the central foot stands at its own central notch, which is off the plane by
      however far that notch is. No step projects it onto the plane, because projecting would
      move a column nothing asked to move.

- BRANCHING 3: TAKE FEWEST STRAYS, NOT FEWEST REMAINDER TREES. Where several candidate centre
  tree sizes k are admissible, the one leaving the FEWEST STRAY TREES wins. His reason is his own
  currency: he wrote "only 1 or two columns get left stranded", and the retired criterion RAISED
  the stray count from one to two at m = 5 and at m = 11, which is movement in the wrong
  direction on a definition he had already saved.
      THE RETIRED CRITERION, recorded rather than deleted: "take the k with the fewest REMAINDER
      TREES", which was this spec's own invention and appeared in no ruling of his. Under it the
      layouts at Branching 3 would have been [3] at m = 3, [1,3,1] at m = 5, [3,1,3] at m = 7,
      [3,3,3] at m = 9, [1,3,3,3,1] at m = 11 and [3,3,1,3,3] at m = 13. The two rows in bold
      against it are m = 5 and m = 11, where it turned one stray into two.
      THE TIE-BREAK IS THE AUTHOR'S AND NOT HIS. He ruled on the criterion and not on what to do
      when two k leave equally few strays. The rule stated in section 6 is to take the SMALLER k,
      chosen on the instruction to prefer whichever answer moves the fewest columns against the
      shipped engine: the engine always takes the smallest admissible k, so on a tie nothing
      moves. It reverses the earlier draft's "take the larger", which belonged to the retired
      criterion and would now move a column for no reason. Section 6 proves the tie is
      UNREACHABLE for Branching 1 to 3, so the clause is there for totality and not for use, and
      anyone raising Branching past three must revisit it along with the rest of section 6.
      THE TWO-CELL EXPECTATION DID NOT HOLD, and section 6 says so in its own words. The ruling
      was passed down expecting m = 3 and m = 9 to move and m = 5, m = 7 and m = 11 to be
      preserved. m = 5 and m = 11 are preserved. m = 7 is not: the engine's [3,1,3] leaves one
      stray at the centre and [2,3,2] leaves none, so fewest strays takes the latter. m = 13
      moves for the same reason. FOUR cells move at Branching 3, m = 3, m = 7, m = 9 and m = 13,
      and none at Branching 1 or Branching 2.
      That is not an argument against the ruling and the spec does not present it as one. Every
      one of the four LOWERS the stray count, three to zero at m = 3 and m = 9 and one to zero at
      m = 7 and m = 13, which is the direction his currency asks for and which the retired
      criterion could not deliver. The cost is that at m = 7 and m = 13 the remainder tree count
      rises from one to two, a lone central column traded for two trees of two at the anchor
      ends. His ruling says that trade is right, since a tree of two is a tree and a tree of one
      is a stranded column.

- THE LOAD AT A SHARED NODE: FIX IT PROPERLY. The two new arguments are threaded through, the
  untransversed pull per bar and bar position and the whole incident pull per node, and the head
  load at a node held by k distinct bars is the sum of their pulls less (k - 1) times the node's
  whole pull, which recovers the node's own infill exactly once. Section 10 states where they
  come from, what carries them and what the engine signature becomes; section 16 restates the
  same three additions from the diagnostics' side.
      THE REJECTED ALTERNATIVE, kept: leave the owner's own transverse pull alone, accept that a
      crossing's other bar contributes nothing, and add no plumbing at all. That is what the
      engine does today and it is what produced seventeen counted where eighteen were applied. It
      was rejected because the undercount propagates into the aim, the axial force, the load path
      and Auto's choice, and because a diagnostic that reports a total is worth nothing if the
      total is wrong.
      THE NAIVE FIX REMAINS OFF THE TABLE, for the reason section 10 already gives and not
      because anyone ruled against it: BarLoads excludes only its own bar's along edges, so
      summing two bars' transverse pulls counts the node's infill twice, which on a real vault
      is close to doubling the head load at every crossing. The measurement that seventeen came
      back from eighteen was taken on hand-built transverse arrays, where each bar declares its
      own pull independently, and it does not license that sum on production data.
      THE MEASURED CASE THAT MUST NOW COME OUT RIGHT is eighteen units applied and eighteen
      counted, asserted as an equality in section 17, with the seventeen printed beside it.

### 18.2 Ruled by the controller, not by Param

These four were open when the wave was reviewed and Param did not rule on them. They are settled
here on the controller's authority so that the plan is not blocked, and they are marked as the
controller's so that he can overturn any of them without unpicking his own.

- THE CROSS-LINE MERGE MIRROR GATE IS KEPT. A merge candidate is refused unless its mirror by
  group index is also a candidate. That is an addition to his ruling and not a reading of it, and
  it is kept because accepting one of a mirrored pair of merges and not the other is exactly how
  two matching columns stop matching, and symmetry is the whole complaint this wave answers. The
  refusal is reported rather than silent, in Level.MergeRefused and in columns.feet_close. The
  cost is real and stated: two feet satisfying his stated condition can be refused because of the
  state of a different pair elsewhere on the span. The alternative, dropping the gate and letting
  the clearance alone decide with the resulting asymmetry bounded by a quarter of the tighter
  span's spacing, is rejected on the ground above.

- THE COLLISION CLEARANCE AND THE FEET-CLOSE SCALE CHANGE AS THE SPEC PROPOSES. The brief forbids
  a net-median tolerance, the investigation found the median still live in two places, and a
  median over every edge in both mesh directions stands in no fixed ratio to the notch spacing
  along any one bar. Span-local is right. The collision clearance becomes 0.05 * g and the
  feet-close clearance becomes the merge clearance of the pair concerned, which parts it from the
  collision number it used to share by a factor of five. Both changes will move counts, the
  collision change can move Auto's choice, and it destroys one green fixture outright, for which
  section 17 states the replacement geometry rather than leaving it to the implementer. The
  harness records the counts before and after, as section 17 already requires. The argument for
  leaving the collision clearance alone, that member thickness is a property of the machine
  rather than of a span, is noted and rejected: the brief governs, and a bound that becomes
  several whole notch spacings on one mesh and exact coincidence on another is not measuring
  thickness either.

- THE SHARED-NODE OWNERSHIP RULE STANDS AS WRITTEN, which is the greater free notch count, then
  the longer chord, then the spans' own sorted endpoint coordinates, then the lower mean Z, and
  only then the bar and span indices. It stands because it is the only candidate that is
  trace-order free on an EQUALLY RIBBED VAULT, which is the geometry Param actually builds: a
  cross vault, a dome of equal ribs and hoops and a regularly ribbed barrel all tie on both count
  and chord, so any rule ending at the bar index answers differently depending on which curve
  Pattern traced first, which is the very finding section 10 exists to answer. The alternatives
  are recorded. The more central notch reads the node rather than the span and can hand two
  mirrored shared nodes to different owners, which breaks the symmetry it was meant to protect.
  The lower bar index is the present trace-order rule under another name. The honest cost of the
  rule that stands is that on a fan of ribs of unequal length it will look arbitrary in a
  screenshot, and a rib whose notches are all borrowed builds nothing at all.

- FORCES AND THE LEAN AT TYPES 1 TO 4: SECTION 13'S ACCOUNT IS ACCEPTED AND THE ITEM IS CLOSED.
  It was listed as needing his explicit confirmation on the suspicion that it departed from his
  ruling. It does not. His ruling is that the forces inform the lean and no longer decide the
  position, and section 13 honours it exactly: with the foot fixed by the ladder and the fork
  bound to the foot-to-notch segment there is no free variable left for a force to set, so there
  is nothing left for the forces to inform at those levels beyond the measurement. The honest
  statement, which section 13 makes, is that the forces make the AIM, the aim decides the
  POSITION at Type 0, it chooses the peel and the family everywhere, and elsewhere it is what the
  built column is MEASURED against, in the per-foot alignment measure and the branch off-thrust
  measure. That is not a departure from his ruling but its consequence, so it is settled rather
  than open. The two levers that would put force back into the lean are recorded and both are
  worse than what they buy: letting the fork leave the foot-to-notch segment, which reintroduces
  the kinked trunk section 2 preserves against, or letting the force move the foot, which is the
  position he took away from it.

### 18.3 Still open, for Param

- THE TYPE VALUE LIST NOW LIES, KNOWINGLY. The brief preserves the list, so the canvas still
  reads "2 two feet" on a span that will show three, or one. The tooltip carries the truth and
  the diagnostics report both counts. The wording that would fix it is "2 two gathered feet", and
  a change to the item text is his to authorise. Until he does, section 17 pins the item text
  unchanged and names the inaccuracy in the check, so that nobody later reads the green as
  agreement.

- THE EVEN GROUP'S FOOT IS NOT ON A NODE, which is the design's one knowing departure from a
  carried ruling of his. A group with an even notch count stands at the midpoint of its two
  central notches and is not snapped to either. The reason is in 8.5: snapping would move the
  foot half a notch spacing to a side chosen by nothing, and on the centre group it would move
  the one column he has now ruled must stand straight. That last point strengthens the case since
  he ruled, so the departure is more defensible than it was, but it is still a departure and it
  is still his to accept or refuse.

### 18.4 Costs this design accepts, recorded and not open

None of these is a question. They are the prices of rules already settled, written down so that
they are found here rather than on the canvas.

- CROSS-LINE MERGING CANNOT BE EXACT. Where two spans' mirror planes disagree, a merged foot
  cannot lie on both, and each span's own symmetry is disturbed by up to a quarter of the tighter
  span's notch spacing, which is inside the tolerance that declared the feet to be together in
  the first place. On a fan of ribs whose chords are not parallel that will be visible.
- THE SAME-SPAN CENTRAL PAIR IS KEPT AND ITS CLEARANCE HAS CHANGED SCALE, from 0.05 of a net
  median to 0.25 * g, and it is confined to the innermost pair of an EVEN tree row. Confining it
  is what keeps the narrow-bay fixture honest: on an ODD row the pair either side of the centre
  tree would otherwise merge onto the centre tree's own foot, and welding leaning neighbours into
  one column is a defect this file has already fixed once. It is also what Param's ruling of
  18.1 now requires, since that merge would swallow the column he ruled must stand alone.
- ONE WHOLE-SPAN GATE SURVIVES, on the family average of the aim, for the node-order reason in
  section 9. The cliff is gone from the layout, from the feet, from the common mode and from the
  merging, which is what shows on the canvas, but a span with one unpaired tree still keeps its
  own aims. That is not the defect the input measured: the common mode goes from that span too,
  unconditionally, before any pairing runs.
- THE AIM MIRROR IS TAKEN FROM THE PULL, WHICH IS A FORCE. The design input's second numbered
  change binds and this spec follows it, and the tension with "forces inform the lean and no
  longer decide the position" is resolved by scope: no foot reads s_mirror, because the layout,
  the groups, the candidates and the merge mirror are all taken by index, so at Types 1 to 4 no
  force moves a foot. At Type 0 the aim decides the position by definition and there the change
  is the point. Two costs are real. Where a span's along profile has several sign changes,
  s_mirror can jump between them as the solve moves, which costs only which trees share an across
  and a down with which. And where a span's aim is plumb everywhere there is no sign change at
  all and the plane falls back to the notch row's own centre, which does not correct an unequal
  anchor cluster and does not need to, because a plumb aim has no lean to get wrong.
- THE MERGED FOOT'S GUARD WAS A WHOLE SPACING AND IS NOW A QUARTER. Feet declared to have already
  landed together within a quarter of the tighter span's spacing were then allowed to converge up
  to a whole spacing away from them, which is the same measurement contradicting itself. That
  will send more merged feet to the plan mean, counted in ConvergenceFallback, which is the safe
  direction.
- THE FEET FOLLOW THE MESH. A group's foot stands on its own central notch or between its two
  central notches, so remeshing a bar moves its feet, and on a span whose notch row is lopsided
  the feet are lopsided with it. That is deliberate, since a column standing under a notch is
  what he asked for, and columns.snap exists so it is visible rather than surprising.
- TYPE 1 ON A WIDE SPAN WILL STILL LOOK LIKE TYPE 0 AT THE FLANKS, because a trunk from the
  centre to an anchor-end notch leans past sixty degrees and peels. That is the measured control
  behaviour today and this spec does not change it. The honest levers are a higher Type, a lower
  Branching or a taller span, not a placement rule.
- BRANCHING 3 MOVES COLUMNS ON SAVED DEFINITIONS, at four counts, by his own ruling. An author
  reopening a definition at Branching 3 with three, seven, nine or thirteen free notches on a
  span will see the columns rearrange. The diagnostics say what the layout is and the harness
  pins every row against the engine's old one, so the change is legible rather than mysterious.

## 19. Out of scope

The skin buildability work, by his own ruling: minimum piece size, build sequence order and band
splitting for topology transitions, which come after the columns. Any change to
MouldGeometry.AimFrom, to the sixty degree cap, to BarLoads or to BarTransverse; section 16 adds
a NodeLoads beside BarLoads and leaves BarLoads itself exactly as it is, which is why the head
pull of section 10 is expressed as arithmetic over what those two return rather than as a change
to either. The shape of the two collision tests, as opposed to the clearance they use. The ring
tree's own rule. The block contract and its validation. Animate, Frame, Deconstruct, the readers,
Export, Skin, the icons, the panels and the component count; in particular Animate's per-node
live aim, which at a shared node is the last bar traced and does not agree with the engine's
summed head aim, is named in section 13 and left where it is. The tools/tree_forest Python twin,
which keeps its own algorithms. Load balancing between feet, which was named as a fault of the
band rule and is answered here by removing the bands rather than by balancing anything. The
outermost principal line's across component, measured at nine times its down, which the design
input records as real, as not this wave's business, and as visible on his model as the outermost
ribs' columns leaning out of plane.

## 20. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No Co-Authored-By and no AI
attribution. Commit locally after every fix; push only on Param's word. Rebuild and install to
Grasshopper as the final step with Rhino closed, then tell Param to restart Rhino. Every measured
check runs in the smoke harness without launching Rhino and without calling Vector3d.Unitize.
Check for OneDrive name-clash files before every build and every commit. Stage by explicit path
only.
