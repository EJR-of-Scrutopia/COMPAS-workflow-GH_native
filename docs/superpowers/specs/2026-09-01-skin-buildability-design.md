# Skin buildability and pattern rework

Date: 2026-09-01. Status: design, AMENDED to Param's rulings of 2026-09-01. Section 13 now separates
what is settled from the four items still genuinely open for him.

Governed by his rulings in
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-skin-round-design-input.md,
which wins wherever this spec disagrees with it. Built on the shipped design in
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-08-31-skin-design.md,
whose three errata about the correspondence rules are carried forward intact in section 11.

Every claim below about how the code behaves today was checked against the code and is cited by
file and line. Where a claim could not be checked, the text says so in the sentence that makes it.
Where a ruling is mine rather than Param's, the rule says so.

Param ruled on two points on 2026-09-01 and this text is amended to them rather than annotated with
them. THE SEAM-OUTWARD BUILD ORDER STANDS, on the corrected understanding of what it serves, which
is section 7. THE CROWN CAP SPLITS when it is oversized, into a ring of wedges about a smaller centre
disc, which is section 2.6. Four further rulings in this round are MINE, the controller's, and each
says so where it stands: the masonry reading of the continuous joint family (rules 3.3.4 and 3.3.4a),
the half-pitch stagger (rule 5.4.3), the minimum piece size as a port that fixes the maximum with it
(rules 6.0 and 9.5), and Path's slot in Export (section 10.1).

## 0. Files, paths and citation convention

The files this spec touches or cites, in full:

1. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\SkinPatterns.cs
2. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\SkinComponents.cs
3. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\DeliveryComponents.cs
4. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\ColumnsComponent.cs
5. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\NativeComponentBase.cs
6. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\ResultDiagnostics.cs
7. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\VisualiseComponents.cs
8. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Contracts\TnaContracts.cs
9. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Contracts\ContractDtos.cs
10. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Contracts\ResultContracts.cs
11. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\tests\native_smoke\Program.cs
12. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\src\ananke_equilibrium\patterns\armadillo_dual.py
13. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-UI-integration-tool\bench\studio\tessellation.py
14. C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-UI-integration-tool\bench\studio\staging.py

Every later citation gives the base name and the line, against that list. Nothing outside the list
is cited.

## 0a. Where Param's words and the code disagree

Six places, named here rather than resolved quietly.

1. The design input says the tracer "is already field-agnostic, it cuts level sets of a
   piecewise-linear scalar on triangles". It is not. It reads the world Z coordinate by hard-coded
   component index in three places: the crossing predicate at SkinPatterns.cs:508-511, the crossing
   point at SkinPatterns.cs:497-499, and the surface's range at SkinPatterns.cs:1898-1901. Beyond
   those three, Z arithmetic is spread through both engines: the courses ladder at
   SkinPatterns.cs:1745-1759, the honeycomb's row heights at SkinPatterns.cs:2224-2232, the vertex
   clamp at SkinPatterns.cs:2304-2311 and the course label at SkinPatterns.cs:2405-2412. The value
   is then stored on every curve in a property named Height (SkinPatterns.cs:54) and printed to the
   author as "z=" (SkinPatterns.cs:2030-2035). Swapping the scalar is mechanical, but it is a change
   in a dozen places plus a rename, not a substitution at one call site. Section 1 states the whole
   of it.
2. His sentence asks for courses cut "in planes tangential to the curvature". A level curve of a
   distance field is not a plane section and is generally not planar at all. What he gets is a bed
   that runs everywhere across the direction of steepest ascent away from the rim, which is what he
   means and what a mason lays; it is worth him knowing that such a bed cannot be cut with one
   straight saw pass and that the Surface output of section 5 will hand him a doubly curved face.
3. The design input says all three patterns become "the same construction on different fields". That
   is true of the two families that are level sets and false of the flow family. The force bands are
   integral curves of a LINE field, built from the mesh's own edge directions weighted by member
   force and smoothed three times (armadillo_dual.py:455-478, :398-412, :583-619) and advected face
   by face (armadillo_dual.py:1213-1308). A line field on a doubly curved surface has no integrating
   factor in general, so there is no scalar whose level sets are those curves and the hardened tracer
   cannot produce them. Section 3 says what the pattern actually becomes.
4. The design input treats the honeycomb's pentagons and heptagons as something the rework will
   reveal "where the row counts change". There are no row counts today. The column set
   uc = 0.75 * S * i is the same absolute set on every row from base to crown
   (SkinPatterns.cs:2267-2269) and nothing anywhere recomputes a count per row, unlike the courses
   engine which does take one per curve (SkinPatterns.cs:1801-1803). Giving every row its own count
   is new work, and the odd cells arrive for the first time with it. Section 4 states where they are
   allowed.
5. The plugin's own Cells port tells the author that the within-course order is "the studio's build
   sequence within a run" (SkinComponents.cs:149). It is false.
   tessellation.py:473 sorts every tessellation, authored or generated, by course and then by the
   polar angle of each cell's centroid about the cut's own centroid, and reassigns each cell's index
   from that sort at tessellation.py:474-477. The order is not idle for being discarded there: it is
   EMISSION order, and emission order is what decides which cell survives an overlap
   (SkinPatterns.cs:1584-1590). So the order serves the Grasshopper author and the overlap filter and
   not the studio, and that is the basis on which Param kept it on 2026-09-01. Section 7 corrects the
   sentence and section 13.1 records the ruling.
6. "It should be not too hard of a problem to fix" is true of the cheap form he rejected and false of
   the proper one he chose. The proper form replaces the scalar the whole engine is built on. It is a
   foundation change. It is the right one, and it reuses rather than replaces the hardened tracer,
   but the plan must be costed as a foundation change and not as a patch.

## 1. Course cutting: the field becomes distance from the rim

### 1.1 What is wrong today

Course boundaries are a fixed arithmetic ladder in world Z built before anything is traced:
band boundary r sits at zMin + r * CH, its mid at the average of its two boundaries, and the two
extreme cuts are pulled inside the surface by an epsilon (SkinPatterns.cs:1738-1759). For a surface
at slope theta from horizontal, a rise of CH is a distance along the surface of CH / sin(theta), so
the bed spacing is CH at a vertical springing, 1.41 CH at forty-five degrees, 5.8 CH at ten degrees,
and it diverges at a horizontal crown. That is the stretching in his screenshot and it is
unavoidable while the field is Z.

### 1.2 The field

RULE 1.2.1. The scalar the tracer cuts becomes the GEODESIC DISTANCE FROM THE RIM, one value per net
vertex, in metres, and CH becomes the true bed-to-bed spacing of the masonry measured along the
surface rather than a rise.

RULE 1.2.2. SkinNet gains THREE members beside Vertices and Faces, each declared with a default so
that every existing two-argument construction in the harness goes on compiling and goes on measuring
what it measures today (the record is `SkinNet(IReadOnlyList<double[]> Vertices,
IReadOnlyList<int[]> Faces)` at SkinPatterns.cs:31-33):

  (a) a rim, `IReadOnlyList<int> Rim`, holding net-space vertex indices and defaulting to empty;
  (b) the net's own FORCE EDGES, `IReadOnlyList<SkinNetEdge> Edges`, defaulting to empty, where
      `internal sealed record SkinNetEdge(int A, int B, double Force)` carries two NET vertex
      indices with A less than B and the member force in kN;
  (c) a computed `IReadOnlyList<double> Levels`, one value per vertex in vertex order, built once in
      the constructor exactly as the triangulated Faces are built there today
      (SkinPatterns.cs:35-39).

The field is computed once per net, so both engines read the same one and the smoke harness can
measure it by handing a net in, which is the reason the triangulation lives on the record rather than
in ReadNet (SkinPatterns.cs:25-29). Member (b) is on the record for that reason and for one more, and
it is not a convenience: section 3 makes the force-aligned pattern NATIVE and builds its line field
from the mesh's own edge directions weighted by MEMBER FORCE (rule 3.5.2), and today neither the net
nor its reader holds a single force. `ReadNet` reads vertex positions and face corner indices and
nothing else, never touching `equilibrium.Edges` or `equilibrium.MemberForces`
(SkinPatterns.cs:131-195). Without member (b) there is no path by which a native C# line field could
see a force at all, and section 3 does not exist.

RULE 1.2.3. With an EMPTY rim, Levels is the vertices' own Z. This is deliberate and it is what
keeps six adversarial rounds' worth of pins alive: every fixture in the smoke harness builds its net
through the two-argument constructor and therefore goes on measuring exactly what it measures today,
while new rim-bearing variants of the same fixtures measure the new field. It is also the honest
fallback of rule 1.7.

RULE 1.2.4. Every read of `vertex[2]` in the tracer becomes a read of `net.Levels[index]`: the
crossing predicate at SkinPatterns.cs:508-511, the crossing point at SkinPatterns.cs:497-499 (note
that the crossing POSITION stays a three-dimensional Lerp between the two vertices; only the
parameter t changes source), and the range at SkinPatterns.cs:1894-1904, which is renamed
`LevelRange`.

RULE 1.2.5. `SkinLevelCurve.Height` is renamed `Level` (SkinPatterns.cs:54) and every consumer with
it: `CurveAt` (SkinPatterns.cs:2158-2170), the honeycomb course index
(SkinPatterns.cs:2405-2412) and the diagnostics wording, which stops printing "z=" and prints
"d=" for a rim distance and "z=" only under the fallback of rule 1.7
(SkinPatterns.cs:2030-2035). Without this rename the author is shown a rim distance labelled as a
height and warned about a "height" that is not one, which is a worse defect than the one being
fixed.

### 1.3 Which rim, and why

RULING (mine; Param said "the rim" and the code offers two candidates that differ on precisely the
shells he cares about). The rim is the ANCHOR SET, not the mesh boundary.

RULE 1.3.1. The rim of a TNA Result is `result.Mappings.Supports`, each entry's `FormVertexId`
(TnaContracts.cs:225-236), mapped into net space through ReadNet's own `formToNet` dictionary
(SkinPatterns.cs:163, 175-178), which stops being a local variable and is used to build the net's
Rim before `return new SkinNet(...)` at SkinPatterns.cs:194.

RULE 1.3.2. It is NOT `ResultTables.SupportNodes` (VisualiseComponents.cs:196-206). That method
returns EQUILIBRIUM vertex ids, while SkinNet is indexed in FORM vertex order, the insertion order
of the loop at SkinPatterns.cs:164-178. On a net whose two index spaces happen to have the same
count, feeding SupportNodes' output into a net lookup indexes the wrong vertices silently.
`TnaSupportMappingDto` carries both ids, so the correct source needs no geometric guessing.

RULE 1.3.3. It is NOT the mesh boundary, meaning the edges belonging to exactly one triangle. That
set is derivable from the face list, but it includes an oculus, a free edge and every hole, none of
which is a support and none of which a course should be measured from. On an oculus dome the two
answers differ over the whole surface.

RULE 1.3.4. A form vertex named as a support but absent from `formToNet`, or out of range, is
dropped and counted; the count reaches the diagnostics as `skin.rim` and, when it is non-zero, a
Remark.

RULE 1.3.5. THE FORCE EDGES OF RULE 1.2.2(b) ARRIVE IN THE WRONG INDEX SPACE AND MUST BE MAPPED, and
this trap must be raised against the edges exactly as rule 1.3.2 raises it against the supports.
`EquilibriumResultDto.Edges` and `EquilibriumResultDto.MemberForces` are indexed on EQUILIBRIUM
vertices (ContractDtos.cs:669-673), while SkinNet is indexed in FORM vertex order, the insertion
order of the loop at SkinPatterns.cs:164-178. So `ReadNet` builds the INVERSE of its own
`formToEquilibrium` dictionary (SkinPatterns.cs:139-160), composes it with `formToNet`
(SkinPatterns.cs:163, 176) to get equilibrium index to net index, and maps both ends of every edge
through it before storing the edge. On a net whose two index spaces happen to have the same count,
storing the raw pairs weights the wrong edges silently, and every direction section 3 computes is
then noise wearing the right units.

RULE 1.3.6. An edge either of whose ends does not map, or whose position is out of range of
`MemberForces`, is DROPPED and counted, exactly as rule 1.3.4 drops an unmappable support. The count
reaches `skin.field`'s Context and, when it is non-zero, a Remark. A net carrying NO force edges at
all is not an error: rule 3.2.8's own fallback covers it, pattern 2 on such a net gives the (1, 0)
direction on every face, and the diagnostics must say so rather than leaving the author to wonder why
his flow lines came out straight.

The precedent is in the repository already and it is the same choice: the force-aligned worker reads
its own rim from the case's named supports (armadillo_dual.py:222-227) and orders them into bands
through the mesh's own triangle edges (armadillo_dual.py:651-700), never from the topology.

### 1.4 How the field is computed

RULING (mine; the design input says "computed once per vertex over the mesh" and does not name a
method). The method is FAST MARCHING on the triangulated net, the Kimmel and Sethian triangle
update, which is Dijkstra's structure with an edge relaxation replaced by a triangle update.

RULE 1.4.1. Every vertex in the Rim is seeded at 0 and every other vertex at positive infinity. A
min-heap over tentative values pops the smallest, FREEZES it, and then RELAXES every vertex adjacent
to the frozen one across a triangle edge. A candidate C is offered a value by each triangle ABC
incident on C, and takes the smallest offer any of them makes:
  (a) where BOTH A and B are frozen, the triangle update of rule 1.4.2;
  (b) where only ONE of them, say A, is frozen, the plain edge relaxation dA + |CA|;
  (c) where neither is frozen, that triangle offers nothing on this pop.
C's tentative value becomes the smaller of its present value and the smallest offer, and the heap is
updated. That is the standard fast-marching structure and every clause of it is load-bearing.

Clause (b) in particular is not tidying. Rule 1.3.1 makes the rim the ANCHOR SET, `Mappings.Supports`
(TnaContracts.cs:226-236, the collection at TnaContracts.cs:271-272), and a vault carried on four or
eight POINT supports has a rim of pairwise non-adjacent vertices. Under a rule written only as (a),
no triangle anywhere has two frozen corners at the first pop, nothing is ever relaxed, every non-rim
vertex keeps positive infinity, and rule 1.7.3 then reports the whole shell as unreachable and raises
its Warning on a shell that is perfectly reachable. The one-frozen edge relaxation is what STARTS the
front; the two-frozen triangle update is what makes it accurate once the front is a front. This is
the case rule 1.7.2 already contemplates when it names a groin vault's four rims, and check 12.1(i)
measures it.

RULE 1.4.2. The triangle update solves the planar wavefront on the triangle itself, which is planar
by the net's own invariant (SkinPatterns.cs:35-39). Where the characteristic direction falls outside
the triangle, which an obtuse angle at the updated corner can give, the update falls back to
`min(dA + |CA|, dB + |CB|)`, the plain edge relaxation. No unfolding across neighbours: the fallback
is bounded, stated and cheap, and the cost of getting it slightly wrong is a course boundary a few
millimetres off on a badly shaped triangle, against a CH of order 0.35 m on mesh edges of order
0.2 m.

RULE 1.4.3. Heap ties break on the lower vertex index, so the field is a property of the mesh's own
numbering rather than of any traversal order, the same discipline the triangulation tie-break keeps
(SkinPatterns.cs:246-252).

RULE 1.4.4. The field the engine DEFINES is the piecewise-linear interpolant of these vertex values
over the triangles. Say that plainly, because it is what preserves the exactness argument. The chord
the tracer draws between two edge crossings is the exact level set of that interpolant on a planar
triangle, for the same reason it is the exact level set of Z: a function that is affine on a plane
has straight level sets. What is approximate is the relation between the interpolant and the true
geodesic distance, and that approximation is the field's own definition rather than an error
downstream of it. Every guarantee in section 11 is a guarantee about the interpolant and survives
unchanged.

RULE 1.4.5. Cost is O(V log V) with a small constant, run once per solve, against a plan filter
already measured at seconds to minutes on the canvas thread (SkinPatterns.cs:1606-1616). The field
is not the expensive part of this component and must not be cached across solves, because a Result
whose vertices moved is a different field.

### 1.5 What follows mechanically

RULE 1.5.1. `BandCount` (SkinPatterns.cs:1855-1869) takes the field range instead of the Z range.
Its sliver-merge branch is unchanged and is now load-bearing for the crown cap; see rule 2.4.

RULE 1.5.2. The epsilon at SkinPatterns.cs:1739 becomes a fraction of the FIELD range. Both ranges
are in metres, so no unit changes and no tolerance moves.

RULE 1.5.3. The course count changes on every shell, because it is now
`BandCount(0, dMax, CH)` over a geodesic extent rather than a vertical one. Every pinned cell and
course count in the smoke harness moves for rim-bearing fixtures. That is expected and it is the
reason rule 1.2.3 keeps the old fixtures on the Z fallback: the correspondence, tracing and filter
regressions stay measurable against their existing numbers while the new field is measured beside
them.

RULE 1.5.4. The guard `!(zMax - zMin > 1.0e-9)` at SkinPatterns.cs:1735-1736 and
SkinPatterns.cs:2208-2209 becomes a guard on the field range. A surface flat in Z now has courses,
because it has a rim distance; a surface with no rim and no Z range still has none.

### 1.6 Where the nesting argument stands

The argument at SkinPatterns.cs:212-219 is often read as an argument about Z. It is not. It is an
argument about the SURFACE: on a plan-injective surface two components of one level set cannot cross
in plan, because a crossing point would lie on both and they would be one component. That holds for
the level sets of any scalar carried on the same surface. So nesting depth stays well defined, the
depth rule stays sound rather than sampling-dependent, and the correspondence machinery of
SkinPatterns.cs:692-713, :996-1021 and :1097-1124 carries across without re-argument.

What DOES change is how often the machinery fires. Level sets of Z on a vault are a nested family
that changes topology rarely. Level sets of a rim distance MEET at a cut locus, typically over a
crown or between two springings, and merging fronts are a topology event at every such place.
Refusing a whole band there, which is the shipped rule (SkinPatterns.cs:1785-1791), would put a hole
of one full course wherever the field's fronts meet, which on an ordinary barrel is the whole ridge.
Section 8 is therefore not an optional improvement in this round; it is a precondition for section 1.

### 1.7 A mesh whose rim is not closed

Four cases, each with a stated rule.

RULE 1.7.1. The rim is one open band rather than a loop, which is an ordinary barrel's springing
line. Nothing special happens. Fast marching is multi-source and does not care whether its seed set
closes.

RULE 1.7.2. The rim is several disconnected bands, which is a barrel's two springings or a groin
vault's four. Nothing special happens either; the fronts advance from all of them and meet at a cut
locus, which section 8 splits.

RULE 1.7.3. Some of the surface is unreachable from the rim across the triangulation, which a net in
two disconnected pieces gives. Unreachable vertices take a field value of positive infinity, are
excluded from the field range, and their faces produce no cells. The count of unreachable vertices
is a `skin.field_unreachable` diagnostic entry and, when non-zero, a Warning naming it, because a
silently uncovered region is exactly the failure the plan filter's warning scaling exists to prevent
(SkinComponents.cs:335-363).

RULE 1.7.4. There is NO rim at all, meaning the Result names no supports or none of them maps into
the net. The field falls back to world Z, the shipped behaviour, and the component raises a Warning
saying so in those words and writes `skin.field` with the message "world Z: this Result names no
supports, so courses are cut horizontally". RULING (mine): a fallback with a loud label beats an
empty output, and it beats a silent change of what CH means. Param may prefer a refusal; it is one
line either way.

### 1.8 How a joint maps onto a band's boundary curves, which is his FIRST cause

His carried ruling names two causes and is specific that they are separate: "The setout distortion
has TWO causes and both must be addressed: the arc-length RATIO mapping, and SEPARATELY the seam
quantised to a trace vertex, the latter measured on concentric similar polygons where the ratio is
exactly right and the cells shear regardless." The second cause is the quantised seam and rule 4.2.6
answers it. The FIRST cause is named here, because an earlier draft of this spec closed both out with
one sentence at the end of section 4.1 and that sentence was wrong: it read defect 1, the honeycomb's
absolute column set, as his cause 1. Defect 1 is the ABSENCE of any ratio, `uc = 0.75 * size * i`
against one global bound (SkinPatterns.cs:2263-2269). His cause 1 is a ratio, and the only
arc-length ratio mapping in the engine is the courses engine's. His own parenthesis settles it: the
control case he cites is the one where a proportional mapping is exactly right.

RULE 1.8.1. WHERE IT LIVES. `BandCell` computes `lowerRatio = lowerCurve.Length / mid.Length` and
`upperRatio` likewise, and lands a joint at signed arc u on the mid curve at `u * lowerRatio` on the
lower boundary and `u * upperRatio` on the upper (SkinPatterns.cs:1963-1969). It is exact where the
three curves are similar about a common centre and wrong everywhere else, because it assumes a
boundary curve differs from the mid only by a scale factor. On a vault whose plan is not a circle,
the flanks and the crown of one course scale by different amounts, the joint slides along the bed,
and that is the shear. Nothing in section 4 touches it, because it belongs to pattern 0, and rule
3.3.6 carries it into pattern 2 with the rest of the `BandCell` construction.

RULE 1.8.2. THE OBVIOUS REPLACEMENT IS REFUSED, and the reason is worth recording so it is not
proposed again. Mapping a joint to the point of the boundary curve NEAREST IN PLAN carries no ratio
and no seam, and it is the discrete form of "a head joint runs across the beds". It also collapses. A
course between two nested squares of half-width 2 and 1: every joint on the outer top edge beyond
|x| = 1 has its nearest point on the inner square AT THE CORNER, so all of them land on one point and
their cells are degenerate. A converging course is the ordinary case at a crown, so the replacement
fails exactly where the mapping matters most.

RULE 1.8.3. THE PRINCIPLED REPLACEMENT, and it only becomes available with section 1's field: a
joint's image on a boundary curve is found by marching from the joint along the GRADIENT of Levels,
which is constant on each triangle, until the boundary curve is met. The head joint is then a curve
that runs across the beds by construction rather than a chord chosen by proportion, and patterns 0
and 2 become one construction whose head joints follow two different fields, the level gradient and
the force line field, which is what the design input means by "the same construction on different
fields". The march is short, of order CH divided by the mesh edge length, so of order two faces, and
it reuses section 3's own face-exit walk (rule 3.2.10) on a different vector.

RULE 1.8.4. RULING (mine, the controller's, and it is a DEFERRAL against his "both must be
addressed", so section 13.2 puts it to him in his own words). Cause 1 is NOT fixed in this round.
The proportional mapping of rule 1.8.1 stays. Three reasons, stated so he can weigh them: rule 1.8.3 is a second advection engine
stacked on top of the one section 3 introduces in the same wave, and section 3 has to be proved
first; a gradient-marched head joint carries intermediate points, so a courses cell's outline gains
corners and rule 5.2.3(a)'s two-section loft no longer has the cell's own outline as its boundary,
which pushes most cells onto route 5.2.3(e)'s fan and changes what the Surface output is; and rule
3.5.3's cost warning, that the plan filter gets dearer exactly as the cells get more corners, then
applies to pattern 0 as well as to pattern 2.

RULE 1.8.5. WHAT IS DONE INSTEAD THIS ROUND. The residual is MEASURED rather than left unknown. On
each fixture the harness computes, for every joint, the plan distance between the proportional image
of rule 1.8.1 and the gradient-marched image of rule 1.8.3, and reports the maximum as a pinned
measurement. That number is the size of his cause 1 on real geometry, it costs no engine change to
take, and it is what tells him whether the deferral is cheap or expensive. Check 12.1(j).

## 2. The crown cap

### 2.1 There is no cap today

The top course closes on the level curve at zMax minus epsilon (SkinPatterns.cs:1739, :1748-1751),
which on a dome is a micron-scale loop around the apex. The engine's own comment names the artefact
and records its cost: about 0.65 mm of effective tolerance on the 1.5 micron edges of a crown epsilon
loop, and 72 tolerance disagreements in 422 configurations, every one on the honeycomb and every one
at the crown (SkinPatterns.cs:1289-1294). The surface above that cut is covered by nothing. A cap is
therefore new work in both engines and not a substitution.

### 2.2 When a cap is emitted

Let n be `BandCount` over the field range and L_top = (n - 1) * CH the topmost course boundary.

The CROWN REGION of a traced component c at L_top is defined on FACES, and it is defined tightly,
because three separate tests turn on it and a loose definition gives each of them a different answer.
It is: the connected set of net faces ALL THREE of whose vertices carry a Levels value strictly
greater than L_top, seeded from every such face that shares a vertex with a face c crosses, and
walked from face to face across a shared edge only where BOTH ends of that edge exceed L_top. Call
that set R, and call the faces c actually crosses, whose vertices straddle L_top, the STRADDLING
BAND. The straddling band is NOT in R: it is the band the cap's own outline runs through and it
belongs to the cap rather than to the region the tests interrogate. Saying which of the two holds a
face is what decides whether a dome gets a keystone and a barrel does not.

RULE 2.2.1. A cap is emitted for component c when all three hold:
  (a) c is CLOSED;
  (b) neither R nor the straddling band of c carries a MESH BOUNDARY EDGE, meaning an edge belonging
      to exactly one triangle, so there is no free edge and no oculus anywhere in the crown above c.
      Both sets are tested, not R alone: an oculus small enough to lie wholly within the straddling
      band would otherwise pass;
  (c) no OTHER component of L_top seeds a face of R, so R is not the saddle region joining two
      crowns.
Together these say the crown above c is a topological disc, which is what a keystone is.

RULE 2.2.2. Where any of the three fails, NO cap is emitted for that component and band n - 1 is
tiled as an ordinary band by the pattern's own rule, with the level curve at dMax minus epsilon as
its upper boundary. That is today's behaviour, kept deliberately as the fallback, and the diagnostics
say which of the three tests refused it.

RULE 2.2.3. Exactly one cap per qualifying component, never more. A cap is a keystone and a keystone
is one stone, unless it is too big to be one stone, in which case it is one ROSETTE: rule 2.6 splits
it into a ring of wedges about a smaller centre disc, and one rosette is still exactly one cap.

### 2.3 What shape it is

RULE 2.3.1. The cap's outline IS the level curve c, whole, from its seam round to its seam,
Dedupe'd by SkinPatterns.cs:1694-1711 like every other outline. It carries every trace vertex of that
curve, so it typically has tens of corners; it follows the surface exactly rather than chording
across it, the same property Run gives every other cell edge (SkinPatterns.cs:1215-1221).

RULE 2.3.2. Its course is n - 1, its Clipped flag is false, and it carries a new `Cap` flag on
SkinCell so the diagnostics and the Surface output can treat it as the one cell of its kind. U0 and
U1 are -c.Length / 2 and +c.Length / 2, so its span is its whole girth.

RULE 2.3.2a. A CAP IS EXCLUDED FROM THE PIECE-LENGTH STATISTICS, and so is every WEDGE of a cap that
rule 2.6 has split, and this matters more than it sounds. Piece lengths are taken as
`cell.U1 - cell.U0` over the surviving cells (SkinPatterns.cs:1839), and that list feeds the message
chin of rule 9.3.1 and the uniformity bar of check 12.3(d). On a dome the cap's girth is metres
against ordinary pieces of order S, so a cap left in the list dominates the maximum and the
max-over-min ratio single-handedly, and the one number this round exists to restore stops measuring
the thing it was restored for. A wedge is excluded for the same reason at a smaller scale: rule 2.6.2
sizes it just under the maximum piece size, which is 3 S at the default MP, so a ring of wedges left
in the list would carry the ratio past check 12.3(d)'s bar of 2.5 on any dome by itself. Every cap
piece's span is reported in `skin.crown_caps`' Context instead, which rule 9.3.3 provides for, and it
is reported per piece rather than pooled.

RULE 2.3.3. Its plan projection is a level curve of a plan-injective surface, hence simple, so it
passes `PlanSelfCrosses`; and it lies above every other cell's band, so it overlaps none. It is not
exempted from `KeepValidPlans` (SkinPatterns.cs:1618-1673) and must not be. If it ever fails, that is
a defect and the filter is where it should show.

RULE 2.3.4. A CAP'S SIZE IS BOUNDED, and Param ruled on 2026-09-01 how. Above the maximum piece size
of rule 6.0(b) the cap becomes a ring of wedges about a smaller centre disc, which is section 2.6.
What stands from the earlier draft is the author's own remedy and the reason it cannot be the whole
answer: a shallow dome at a large CH gives a large keystone and a smaller CH moves L_top up, but a
rule that leaves the whole answer to the author leaves a stone nobody can lift sitting on the model
until he happens to notice it. The cap's girth is reported either way, and section 2.6 now acts on
it.

### 2.4 The band the cap sits in

RULE 2.4.1. The cap replaces the TILING of band n - 1, not band n. Bands 0 to n - 2 are tiled
normally; band n - 1 is the cap, or, where rule 2.6 splits an oversized one, the cap's ring of wedges
and its centre disc together. The tree therefore still has exactly `CourseCount` branches whether the
cap is split or not, the convention at SkinComponents.cs:365-379 is untouched, and the studio still
gets one stage per distinct course (staging.py:162-207).

RULE 2.4.2. `BandCount`'s sliver merge (SkinPatterns.cs:1863-1868) MUST be kept and must run before
the cap decision, and what it guarantees must be stated accurately, because a cap-girth bound or a
sliver assertion built on the wrong interval would be built on a number the engine does not produce.

Before the merge, bands is `ceil(rise / CH)`, so the top band's extent lies in (0, CH]. The merge
fires only where that extent is under CH / 4 AND bands is greater than one, and it then DECREMENTS
bands, which makes the top band's extent the old one PLUS CH, that is in (CH, 1.25 CH). So after
`BandCount` the top band's extent is above CH / 4 wherever more than one band exists, and at most
1.25 CH once a merged sliver has been absorbed. It is never bounded above by CH. And where
`BandCount` returns 1 the merge is skipped by its own `bands > 1` guard, so a shallow shell of rise
0.01 m at CH 0.35 ships a single band of 0.01 m, far below CH / 4, which is correct because there is
nothing to merge it into.

The conclusion the cap rests on survives all of that and does not depend on the upper bound: band
n - 1 genuinely sits at the crown, because no top band thinner than a quarter of CH is ever shipped
beside another one. Remove the merge and the cap lands one band low on every surface whose extent is
not a near multiple of CH.

### 2.5 A barrel ridge, where there is no apex

A barrel's crown is a RIDGE LINE and not a point, and its two sides are separate traced components
matched to one another by nothing: MatchBelow pairs a component with the component below it in the
same chart and never joins the two sides across the ridge (SkinPatterns.cs:996-1021).

RULE 2.5.1. Under a rim-distance field the ridge of a barrel seeded from both springings is the cut
locus, the set of points equidistant along the surface from the two rims. It is where fronts MEET,
so it is a topology event and section 8 splits the band there rather than refusing it.

RULE 2.5.2. No cap is emitted at a ridge. Test 2.2.1(c) refuses it, because the crown region above
the topmost boundary of one side is reachable from the topmost boundary of the other. What the two
sides get instead is an ordinary top band on each, meeting along the ridge, which is what a barrel
is actually built as. Say that in the diagnostics in those words rather than reporting a missing cap
as a failure.

RULE 2.5.3. A dome with one springing rim gets a cap; a barrel with two gets a ridge; a groin vault
gets a ridge along each groin and no cap. These are three readings of one rule and no case is
special-cased.

### 2.6 The cap that is too big

Param ruled on 2026-09-01: above the maximum piece size the cap becomes a ring of wedge pieces around
a smaller centre disc, with the wedge count chosen so that each wedge falls under the maximum; and
ONE threshold governs both ends of the size question, too small merging into a neighbour and too
large splitting into a ring. So the maximum is not a new number and gets no port of its own. It is
the Min Piece port read from the other end, `Mx = S / MP` by rule 6.0(b), which is 3 S at the default
MP of 1/3 and 2 S at the cap of rule 6.4.

RULE 2.6.1. WHEN THE SPLIT FIRES. Let G be the cap's girth, the length of its outline c, which is
also its span `U1 - U0` by rule 2.3.2. The cap is SPLIT where G is strictly above Mx by more than
1e-9 and is emitted WHOLE otherwise. That test is the exact mirror of rule 6.1's "at or under
MP * S": the two ends of the one threshold can never both fire on one piece, and no span anywhere is
left undecided at the boundary. Where MP is zero the minimum is zero and Mx is unbounded, so merging
and splitting go off together, which is the only coherent reading of a single threshold turned off.

RULE 2.6.2. THE WEDGE COUNT. `W = max(2, ceil(G / Mx))`, the FEWEST wedges that put every one of
them under the maximum, and each wedge's outer arc is exactly `G / W`. Fewest, and not the pattern's
own pitch: a keystone region is one stone where it can be one and as few stones as it can be where it
cannot, and tiling the ring at the ordinary pitch would put a course of ordinary stones where a
rosette belongs and would answer a question nobody asked.

The lower end needs no rule of its own, and the arithmetic is worth writing down because it is what
lets rule 6.5 go on saying that no cap piece is ever merged. With `W = ceil(G / Mx)` and G above Mx,
the outer arc `G / W` is above `Mx / 2`; and `Mx / 2 = S / (2 MP)` is at or above `MP * S` for every
MP at or under 0.707, which rule 6.4's cap of 0.5 guarantees with room to spare. A wedge therefore
can never fall under the minimum piece size, and the two ends of the one threshold cannot fight each
other.

RULE 2.6.3. THE INNER BOUNDARY IS A TRACED LEVEL CURVE, like every other boundary in this engine. The
centre disc is the region above a level Li and the ring is the band between L_top and Li. Li is found
by BISECTION on [L_top, dTop], dTop being the top cut at dMax minus the epsilon of rule 1.5.2,
keeping a bracket [lo, hi] whose upper end always satisfies the test:
  (a) hi starts at dTop. Where the curve inside c at dTop has girth ABOVE Mx, no level qualifies at
      all and rule 2.6.6's base case fires immediately;
  (b) otherwise lo starts at L_top and each step traces the midpoint m of [lo, hi]: hi becomes m
      where the component of level m lying inside c has girth at or under Mx, and lo becomes m where
      it does not. Where MORE THAN ONE component of level m lies inside c, the crown holds two
      summits above m, and rule 2.6.6's base case fires;
  (c) SIX steps, the depth of rule 8.2.3 and for the same reason, and Li is then hi.
The bracket invariant and not the shape of the surface is what guarantees the disc is under the
maximum. Girth need NOT fall monotonically as the level rises, because a wiggly curve inside a smooth
one can be longer than it, so the bisection here is a search for a large ALLOWED disc and not for a
crossing, and taking hi at the end is correct whatever the girth does in between.

RULE 2.6.4. WHAT THE TWO PIECES ARE, and the whole of it reuses machinery this spec already has.
  (a) THE RING is the band [L_top, Li] tiled by the pattern's own band construction with the piece
      count FORCED to W and the spans equal: `U0 = -G / 2 + w * G / W` and `U1 = U0 + G / W` for
      w = 0 to W - 1, taken about c's own seam so that rule 7.1's seam-outward order applies to them
      with no special case. A wedge is therefore an ordinary `BandCell` between the outer curve, the
      ring's own mid curve and the inner curve, and it inherits every guarantee and every defect that
      construction carries, including the proportional arc mapping of rule 1.8.1 which rule 1.8.4
      defers out of this round. Say so here rather than leave it to be found, exactly as rule 3.3.6
      says it for the force-aligned pattern.
  (b) THE CENTRE DISC is a cap by rules 2.2.3, 2.3.1 and 2.3.2 unchanged, with the inner curve as its
      outline and its own girth as its span.
  (c) BOTH NEW LEVELS ENTER THE ONE ASCENDING LIST of rule 8.2.9 and the whole list is traced again.
      The ring needs its own MID at (L_top + Li) / 2 as well as Li itself, so a split cap costs two
      levels beyond the ones its bisection has already spent, every one of them counts against the
      total cap of rule 8.2.3b, and inserting them re-propagates the seams above them exactly as rule
      8.2.9 says a band split does.
  (d) THE RING IS A BAND AND IS TESTED LIKE ONE, by the correspondence test of rule 8.2.1. Where it
      FAILS the split is abandoned and rule 2.6.6's base case fires. The ring is NOT bisected
      further: section 8's bisection exists to find a level at which the topology is simple, and here
      the level is already being chosen, by rule 2.6.3.

RULE 2.6.5. THE TREE CONSEQUENCE, which has to be stated because a cap that was one item becomes
several. All W + 1 pieces sit in branch n - 1, the course the cap already had. The tree keeps exactly
`CourseCount` branches, rule 2.4.1 is untouched, and rule 8.2.4's prohibition holds for a split cap
as it holds for a split band: it may not invent a course, because the studio builds one stage per
distinct course (staging.py:162-207) and a rosette is laid in one stage. Within the branch the pieces
sort by rule 7.1 like everything else, and one consequence follows from that which the author should
not have to discover: the disc's mid-span is 0, so it is emitted FIRST and therefore WINS any overlap
against its own wedges under the first-emitted-wins filter of rule 7.3. That is the right way round,
since the keystone is the piece least worth dropping. Where W is ODD the middle wedge straddles the
seam and its mid-span is 0 as well, and rule 7.1's own tie-break, the negative side first, cannot
separate two spans both centred on the seam; so the tie is broken here explicitly and in the disc's
favour, for the same reason. Every piece carries the `Cap` flag of rule
2.3.2 and all W + 1 of them are excluded from the piece-length statistics by rule 2.3.2a.

RULE 2.6.6. THE BASE CASE. Param asked what happens when even the centre disc is oversized, and
whether it recurses or refuses. IT DOES NEITHER, and both halves of that have a reason.

It does not RECURSE, because rule 2.6.3's bracket puts the centre disc under the maximum in ONE step
wherever a qualifying level exists at all, so there is nothing left for a second round to improve. It
does not REFUSE, because a refusal at the crown is a hole at the crown, and this engine already has
one bounded hole in it that section 13.2 has to put to him. So where rule 2.6.3(a) finds no
qualifying level, where rule 2.6.3(b) finds two summits, or where rule 2.6.4(d)'s correspondence
fails, the cap is emitted WHOLE and OVERSIZED, its girth and the maximum are named in a runtime
Warning and in `skin.crown_caps`' Context, and the author's remedy is the one rule 2.3.4 gives him: a
smaller CH, or a larger MP if he wants bigger stones. A stone he can see and measure beats a hole he
cannot fill, and the Warning is what makes the difference between the two visible on the canvas.

The case is not exotic and this spec should not pretend it is. A dome whose plan is not a circle has
a cut locus that is a SEGMENT rather than a point; the level curves inside its crown shrink onto that
segment rather than onto an apex; and the girth at the top cut is therefore bounded below by roughly
twice the segment's length, however fine CH is made. Check 12.2(g) builds exactly that fixture rather
than hoping the case never arrives.

## 3. The force-aligned rework

### 3.1 What is wrong today, from the code

The force-aligned pattern computes a structure and then throws it away. `streamlines` advects a line
field face by face (armadillo_dual.py:1410, :1213-1308) and `seeds` lays points along the accepted
lines (armadillo_dual.py:1605-1620), but `dual_cells` never sees the lines: the whole pipeline at
armadillo_dual.py:3232-3237 passes `points` to `dual_cells` and `lines` to nothing. The cell walls
are geodesic Voronoi bisectors from a multi-source Dijkstra over a refined mesh
(armadillo_dual.py:2725-2727). No cell edge runs along a streamline. That is the mechanism behind
his "cutting through it randomly", and it is not an intersection of two cuts; it intersects nothing.

Three further defects compound it. Adjacent lines are anywhere from 0.5 S to nearly 2 S apart by
construction, because a candidate is accepted at 1.0 S clearance but a growing line stops at 0.5 S
(armadillo_dual.py:94-95, :1478, :1299-1300). Seeds are thinned wherever two lines run close, which
is precisely where force concentrates, leaving oversized cells (armadillo_dual.py:1630-1641). And
the half-step stagger is applied on alternate STREAMLINE INDICES, which is acceptance order and
therefore FIFO queue order for every gap-filling line, not a spatial order at all
(armadillo_dual.py:1613, :1441-1444, :1509-1532).

### 3.2 What the pattern becomes

RULE 3.2.1. The BED joints of pattern 2 are the SAME curves pattern 0 uses: level sets of the
rim-distance field of section 1, at spacing CH. They are continuous, they run across the thrust, and
the thrust closes them rather than sliding along them.

RULE 3.2.2. The HEAD joints of pattern 2 are STREAMLINES of the line field, computed natively in C#,
and every head joint of every cell lies on one. That is what makes the pattern force-aligned in the
sense he can see: the sinusoidal curves running up his form become the joints instead of being
ignored by them.

RULE 3.2.3. A cell is therefore the quadrilateral bounded below and above by two consecutive bed
curves and left and right by two consecutive head joints, with the two bed edges following their
level curves through every intervening trace vertex and the two head edges following their
streamlines. It is the same construction as pattern 0 with the joint POSITIONS taken from the flow
instead of from a uniform division, and it inherits the whole hardened apparatus: exact level curves
on triangles, nesting depth, correspondence by bijection, and the enforced plan validity.

RULE 3.2.4. The worker round trip goes. Pattern 2 becomes native and synchronous like the other two,
so the dispatch at SkinComponents.cs:202-212 and :404-507 and the decode at SkinComponents.cs:739-838
are deleted. `pattern.armadillo_dual` stays in the Python package for the acceptance tests and stops
being reachable from the canvas.

### 3.2a The line field's own arithmetic, written out

Section 3 is the largest new engine in this wave, and specifying it by outcome alone would leave the
implementer told what to achieve, forbidden by rule 3.5.1 from checking his work against the only
existing implementation, and given no arithmetic of his own. The arithmetic is therefore stated here.
Taking the formulae FROM the Python is a different thing from validating OUTPUT against it: the
formulae are copied and cited, the outputs are not comparable, because the two sides triangulate
differently and rule 3.5.1 gives the measured reason.

RULE 3.2.5. FACE BASIS. Each triangle carries its own orthonormal plane basis (e1, e2): e1 is the
first edge normalised, the normal is the normalised cross product of the first two edges falling back
to (0, 0, 1) where it degenerates, and e2 is the cross product of normal and e1
(armadillo_dual.py:368-396). Every direction below lives in its own face's (e1, e2) and never in a
shared world frame.

RULE 3.2.6. DOUBLED ANGLE. A unit plane direction (dx, dy) is carried as
`double(dx, dy) = (dx * dx - dy * dy, 2 * dx * dy)`, which is (cos 2 theta, sin 2 theta), and
recovered as `undouble(v) = (cos(atan2(v_y, v_x) / 2), sin(atan2(v_y, v_x) / 2))`, returning (1, 0)
where the magnitude of v is at or below 1e-12 (armadillo_dual.py:398-413). A line and its negation
are the same line, and doubling is what makes an average of lines mean anything at all.

RULE 3.2.7. THE RAW PER-FACE DIRECTION AND ITS COHERENCE. For each of the triangle's own three edges:
look the edge up among the net's force edges of rule 1.2.2(b) by its unordered net vertex pair; skip
it where there is no entry or the absolute force is at or below 1e-12; take the edge's
three-dimensional direction, normalise it, project it into (e1, e2), normalise the projection, and
skip it where either norm is at or below 1e-12; then accumulate `|force| * double(projected)` and add
`|force|` to a weight total. The face's raw direction is `undouble` of that accumulated pair, and its
RAW COHERENCE is the magnitude of the accumulated pair divided by the weight total, a number in
[0, 1] (armadillo_dual.py:425-485).

RULE 3.2.8. THE FALLBACK. A face NONE of whose edges carries a weight takes the direction (1, 0),
which is its own e1, and reports coherence 1.0, so that a fixed default is never discounted as though
it were a contested vote (armadillo_dual.py:433-436, :481-485). Rule 3.5.2 says what the author must
be told about it, and rule 1.3.6 covers the case of a net with no force edges anywhere.

RULE 3.2.9. SMOOTHING. EXACTLY THREE neighbour-averaging passes, a constant and not an input
(armadillo_dual.py:71, :616-617). One pass, for each face f: start the accumulator at `double` of f's
own current direction; then for every face sharing a triangle edge with f, take that neighbour's
current direction in three dimensions, project it into f's plane by removing its component along f's
normal, normalise, express it in f's (e1, e2), normalise again, skip on either norm at or below
1e-12, and add `weight * double(that)`, where `weight = min(1, coherence of the neighbour / 0.2)`.
The new state is `undouble` of the accumulator (armadillo_dual.py:550-580). The coherence used is the
RAW coherence of rule 3.2.7, fixed from the unsmoothed field and never recomputed between passes.
Weighting every neighbour by its raw coherence instead, without the clamp, was tried and measured:
it discounts the ninety-two per cent of ordinary faces along with the eight per cent meant, changes
every face's final direction and regresses the vault's own bars (armadillo_dual.py:525-547). Do not.

RULE 3.2.10. ADVECTION IS A FACE-EXIT WALK AND NOT A FIXED STEP, so there is no step length to
choose and none is specified. From a point inside a face, take that face's own field direction,
project it into the face's plane, normalise, cast the ray from the point along it, and find where it
EXITS the triangle. That exit point is the next polyline point and the face across the exited edge is
the next face (armadillo_dual.py:1213-1309). A streamline therefore carries exactly one point per
face crossed, which is the same discipline `Run` keeps for a level curve, and it is why rule 3.5.3's
warning about corner counts applies to this pattern. The sign ambiguity a line field carries is
resolved by CONTINUATION: the next face's direction is negated where its dot product with the
direction just used is negative, and the very first face takes an orientation hint, which here is the
ascending direction of the Levels field, since rule 3.3.2 advects upward
(armadillo_dual.py:1246-1252, :1290-1296). Each seed advects BOTH ways, with the hint and against it.

RULE 3.2.11. TERMINATION OF A BRANCH. It stops when it exits a mesh boundary edge, when the field
under it projects to nothing (in-plane norm at or below 1e-12), when it has taken 20000 steps
(armadillo_dual.py:101), or when it comes within the termination radius of an ALREADY-ACCEPTED line.
In THIS engine, unlike the Python's, spacing is not what accepts a line: rule 3.3.3's insertion and
termination tests on each bed decide the spacing. The only spacing rule kept here is that a line
stops where it comes within `0.5 * (S / 2)` of an accepted line, measured point to SEGMENT against
the accepted lines resampled at `0.5 * (S / 2)` (armadillo_dual.py:94-100). A line that stops before
reaching the top of its band is a termination in the sense of rule 3.3.3 at the bed above it, and its
parity retires by rule 3.3.4.

RULE 3.2.12. WHAT THE ARITHMETIC DOES NOT SETTLE. About eight per cent of Param's own vault's faces
sit below coherence 0.2, where the direction is numerically arbitrary
(armadillo_dual.py:440-452, :525-547). Nothing here suppresses those faces: a streamline crosses one
and continues by rule 3.2.10's sign continuation, which is the only defensible thing to do with a
direction carrying no information, and rule 3.2.9's smoothing has already discounted their vote in
their neighbours' directions. What follows from that is a fact about the pattern and not about the
code, and rule 3.5.2 requires it on the port.

### 3.3 How a pattern is fitted into a band

RULE 3.3.1. Seeding, on BED 0 and never on the rim. There is no curve at field value 0 to place a
seed on, and no L0 to divide. The tracer's crossing rule is half-open, an edge crosses when one end
is strictly below the level and the other at or above it (SkinPatterns.cs:506-512), so at level 0
every rim vertex is at-or-above, no edge crosses anywhere and `Trace` returns nothing. That is
exactly why the courses ladder's bottom cut is dMin plus an epsilon (SkinPatterns.cs:1739, :1749).
Seeds are therefore placed on BED 0, the traced curve at the epsilon of rule 1.5.2, at uniform pitch
P0 = L0 / max(1, round(L0 / (S / 2))), that is at HALF the target piece length. Half, not full, for
the reason in rule 3.3.4.

RULE 3.3.1a. EVERYTHING IN THIS SECTION IS PER TRACED COMPONENT. A bed is a LIST of components and
not one curve: an ordinary barrel's bed is two open strips and an oculus dome's is two nested loops.
So L_k, P_k, the seam-outward walk, the insertion and termination tests of rule 3.3.3 and the parity
of rule 3.3.4 are all taken per COMPONENT of bed k, each with its own length and its own seam.
Components are matched between beds by the engine's existing `MatchBelow`
(SkinPatterns.cs:996-1021), which is the same predicate the courses engine uses and the same one rule
11.4's bijection is built from. A component with NO match below carries no head joints across that
band; it is tiled by pattern 0's own rule for that band and the fact is counted in the diagnostics
rather than passed over.

RULE 3.3.2. Advection. Each seed's streamline is advected upward through the line field and recorded
where it crosses each bed curve. Those crossings are the candidate head joints of that bed.

RULE 3.3.3. Insertion and termination, which is the rule the design input asks for and the
difference between a force-aligned pattern and a mess. On bed k let Pk = Lk / max(1, round(Lk / (S / 2)))
be that bed's own target half-pitch. Walk the bed's crossings seam-outward. Where two consecutive
crossings are more than 1.5 Pk apart, INSERT a new streamline at the midpoint of that gap on bed k
and advect it upward from there. Where two consecutive crossings are less than 0.5 Pk apart,
TERMINATE the later of the two at bed k and merge its two pieces. Both events are counted, both are
reported, and both are what a mason does when he adds or drops a course.

RULE 3.3.4. Bond. RULING (mine, the controller's and not Param's, and it SETTLES the tension in the
design input's own open question rather than leaving it open; section 13.1 records it and rule 3.3.4a
records the reading it rejects). Because the half-pitch family is generated at S / 2, a course can
take every OTHER line. PARITY IS ANCHORED ON THE STREAMLINE AND NEVER ON A BED'S CROSSING INDEX. Every
line seeded by rule 3.3.1 carries a parity fixed at seeding, alternating along bed 0 seam-outward; a
line INSERTED by rule 3.3.3 takes the parity opposite to both of its neighbours at the bed it is
inserted on, which is always well defined because the two crossings bracketing a gap of more than
1.5 P_k carry opposite parities; a line TERMINATED by rule 3.3.3 retires its parity with it. Course r
then takes as its head joints the crossings of the lines whose parity is r mod 2, among the lines
PRESENT in band r. Every head joint then lies exactly on a streamline, so the pattern is genuinely
force-aligned, and no head joint runs through two consecutive courses, so the bond is a running bond
and no joint becomes a crack line up the form. Pieces are of length 2 P_k, which is within rounding
of S.

Anchoring the parity on the bed's crossing INDEX instead does not work, and the reason has to be
stated because it is the difference between a bond and a mess. Rule 3.3.3 inserts and terminates
lines AT beds, so bed r + 1 does not carry the same number of crossings as bed r. A line that is even
by index on bed r is odd by index on bed r + 1 from the insertion point onward, so a head joint would
stop running along one streamline between its own two beds, which is the single property rule 3.2.2
and check 12.3(b) exist for; and the parity flip would run from the event to the END OF THE BED
rather than staying at the event. Anchoring on the line confines the disturbance to the place it
happened, and the parity needs no re-synchronisation anywhere, because it was never a function of a
count.

RULE 3.3.4a. WHICH FAMILY CARRIES THE CONTINUOUS JOINT, and the alternative is REJECTED and recorded
rather than dropped. RULING (mine, the controller's and not Param's). The design input's own sentence
reads as pieces sitting BETWEEN adjacent flow lines, in strips running rim to crown, which would make
the flow lines the continuous joints and every piece a segment of one strip. That reading is refused.
A joint continuous from rim to crown is a crack line up the form: nothing crosses it, so nothing
closes it, and the shell loses the one property that makes a masonry surface work. The MASONRY
reading stands instead, and it is what section 3 is built on: the BEDS are the continuous family and
they are the section 1 level curves, running across the thrust so the thrust closes them; the HEAD
joints are the native streamlines, generated at S / 2 by rule 3.3.1 with alternate parity per course
by rule 3.3.4. Every joint therefore still lies on a streamline, so the pattern still reads as the
sinusoidal curves running up his form, while the bond stays a running bond. The two readings look
completely different and both are buildable, which is why the rejected one is written down here with
its reason rather than left out.

RULE 3.3.5. A cell gains or loses a side ONLY where a line begins or ends within the cell's own band,
which is what anchoring the parity on the line rather than on an index buys. An insertion inside a
cell's span gives that cell five sides; a termination gives three. No cell elsewhere along the bed
changes its side count. Those cells are named, counted in the diagnostics as `skin.odd_cells`, and
allowed. They are the pattern's honest response to a flow that converges, and refusing them would put
a hole where a mason puts a closer.

RULE 3.3.6. Everything downstream is pattern 0's. The cell is built by the same `BandCell`-shaped
construction, filtered by the same `KeepValidPlans`, sorted by the same rule as section 7, merged by
the same rule as section 6, and capped by the same rule as section 2. It therefore INHERITS the
proportional arc mapping of rule 1.8.1 along with the rest, which is his first cause of the setout
distortion and is deferred by rule 1.8.4. Say that here rather than leaving it to be found: pattern 2
does not escape a defect merely by being new.

### 3.4 Why the result is buildable, and what makes a good voussoir here

Five properties, stated so they can be measured rather than admired.

1. Its bed joints run across the thrust, so the thrust closes them. The engine's own present comment
   claims the Voronoi achieves this (it does not, by 3.1), so the intent is already the masonry one
   and this construction is the first to deliver it.
2. Its head joints are staggered between courses by rule 3.3.4, so no joint runs through two
   courses.
3. Its plan projection is simple, and disjoint from every other cell's, by the enforced guarantee of
   section 11.5.
4. Its along-course span lies between the minimum piece size of section 6 and 1.5 times the target,
   by rules 3.3.3 and 6. A pattern whose min and max piece lengths read 0.377 m against 3.889 m, as
   his earlier screenshot did, fails this and must be visible as failing it, which is why section 9
   keeps min and max on the component's own message line.
5. Its two bed edges follow the surface and its two head edges follow the flow, so all four are
   curves of the geometry rather than chords across it, and the Surface output of section 5 is a
   genuine face of the vault.

### 3.5 The honest cost, which must be in the plan

RULE 3.5.1. A C# port of the line field will NOT reproduce today's flow lines and cannot be
validated against them. The Python side fan-triangulates every polygon from its first vertex
(armadillo_dual.py:285-301); the C# tracer splits on the shortest valid plan diagonal, and its own
comment records the measured reason a fan is unacceptable for level-curve work
(SkinPatterns.cs:197-258). Different triangles give different face bases, a different edge set, a
different smoothed field and different streamlines. The port needs its own bars, listed in section
12.

RULE 3.5.2. The flow lines are the mesh's own EDGE directions weighted by member force and averaged
in doubled-angle space (armadillo_dual.py:455-478, and the arithmetic is written out at rule 3.2.7),
not principal stress directions. The forces they are weighted by reach the engine only through rule
1.2.2(b), in the net index space rule 1.3.5 maps them into; there is no other source, and a spec that
made this pattern native without that member would be asking for a field built from nothing. The
module records median coherence 0.558 and about eight per cent of Param's vault's faces below 0.2,
where the direction is numerically arbitrary (armadillo_dual.py:440-452, :525-547). A face NONE of
whose edges carries a weight falls back to (1, 0), its own e1, by rule 3.2.8, which is the shipped
Python's own default (armadillo_dual.py:433-436) and the native field keeps it unchanged. Any promise
that the pattern "follows the forces" inherits all of that: the dependence on the form diagram's own
layout, so that a remesh of the form diagram moves the joints, and the fact that where a face's edges
carry no force the direction is a default rather than a measurement. Say so on the port.

RULE 3.5.3. Cells bounded by two curve families carry MORE corners than today's, because both of a
cell's flow-wise edges then follow a traced curve rather than being a chord. The plan filter is
quadratic in the cell count and expensive per cell (SkinPatterns.cs:1518-1535, :1606-1616), so it
gets dearer exactly as the pattern improves. Budget for it and measure it, section 12.9.

RULE 3.5.4. The studio's import rule is stricter than the plugin's filter and the gap becomes
likelier under this pattern. `KeepValidPlans` tests corner count, self-crossing and overlap only
(SkinPatterns.cs:1631, :1660-1661), and `Dedupe` removes only CONSECUTIVE duplicates within 1e-9
(SkinPatterns.cs:1699-1707). The studio additionally rejects any ring with two points within 1e-6 of
each other and any vertex lying strictly on a non-adjacent edge (tessellation.py:636, :648-654), and
it rejects the WHOLE sidecar on the first offender. A pattern with more corners and more
near-coincident ones at insertions and terminations will find that gap.

RULE: `Dedupe`'s duplicate test is raised to the studio's own test, in the studio's own form, and a
vertex-on-edge test is added to the degenerate branch of `KeepValidPlans`. Both halves have to be
stated precisely or the change misses what it is for.

  (a) The raised test is a PLAN test in the STUDIO'S PER-AXIS FORM, not a three-dimensional distance.
      `Dedupe` today measures `Distance`, which is the full three-dimensional length
      (SkinPatterns.cs:1700 calling SkinPatterns.cs:1677-1683), while the studio's ring test compares
      plan coordinates alone, axis by axis, rejecting a ring when
      `abs(pi[0] - pj[0]) <= TOL and abs(pi[1] - pj[1]) <= TOL` at TOL 1e-6 (tessellation.py:31,
      :632-636). Raising a three-dimensional test to 1e-6 does NOT close the gap: two outline points
      1e-7 apart in plan and 1e-3 apart in z pass a three-dimensional 1e-6 test comfortably and still
      fail the studio, which is the exact case a cell spanning a steep band produces.
  (b) It runs over the WHOLE RING and not only over consecutive points, again as the studio's does,
      which is a double loop over all pairs (tessellation.py:632-636).
  (c) It runs BEFORE `KeepValidPlans`, so the filter judges the deduped ring rather than a ring the
      author will never receive.
  (d) The vertex-on-edge test added to `KeepValidPlans`' degenerate branch (SkinPatterns.cs:1631) is
      the studio's: a vertex lying strictly on a non-adjacent edge of its own ring
      (tessellation.py:648-654).

That is a change to shipped behaviour, and section 11 permits it as one of two named exceptions;
rule 11.11 states both and states what each of them actually guarantees.

### 3.6 The course label

RULE 3.6.1. A cell's course is its BED index, the rim-distance band it sits in, for all three
patterns. The force-aligned pattern's present course is its seed's along-flow band index counted in
S-steps from the springing, which is FLOW order and not height order: the module's own docstring
records that 7 of 39 streamlines on the BRG armadillo primal rise then fall by more than 0.5 m
(armadillo_dual.py:3202-3208). Bench Studio builds one stage per distinct course walked rim to crown
and cumulative, and runs a formwork weight and an FEA solve per stage (staging.py:162-207), so this
is a structural choice and not a labelling one. One meaning of "course" across the three patterns.

## 4. The hexagon defect

### 4.1 What is wrong, from the code

Five defects, each cited.

1. The lattice's column set is ABSOLUTE and identical on every row: `uc = 0.75 * size * i` for a
   single global bound iMax (SkinPatterns.cs:2263-2269). Rows differ in length by a large factor on
   any dome, so the same arc offset is a different fraction of each row, the cells shear, and
   eventually they overlap. There is no per-row count anywhere, unlike the courses engine
   (SkinPatterns.cs:1801-1803).
2. Membership is decided against the half-length of the curve at the candidate's CENTRE row alone
   (SkinPatterns.cs:2325-2332, :2382-2388) while the six vertices are clamped against rows
   centreRow - 1, centreRow and centreRow + 1 (SkinPatterns.cs:2304-2311). A candidate admitted on
   its centre row can have both top vertices clamp to the same end of a much shorter row, collapsing
   the top edge to a point and turning the hexagon into a pentagon. Reproduced in a faithful port of
   the MAPPING only, level curves supplied analytically, on a hemispherical dome of R = 3 at S 0.6,
   CH 0.35 and 96 samples a ring: of 161 admitted candidates, 26 had both top vertices clamped to
   one u. That figure is from a port and not from the shipped binary; the mechanism, however, is
   plain in the two line ranges above.
3. A closed loop's u domain is CUT at plus and minus half rather than wrapped
   (SkinPatterns.cs:2378-2381), and the wrap that makes the two ends one physical point is inside
   `PointAtArc` (SkinPatterns.cs:1185-1190). Since a loop's length is never a multiple of 0.75 S, the
   leftmost and rightmost columns meet in a ragged leftover at the meridian opposite the seam, and
   the leftover differs row by row.
4. At the crown the top row's whole curve is shorter than the span a hexagon asks for, so `Run`'s
   closed branch collects every trace vertex of the ring (SkinPatterns.cs:1243-1259, :2396-2399) and
   the cell comes back as a short lower arc plus the entire crown circle. On the same port that cell
   had 104 corners and self-crossed in plan.
5. The seam every u is measured from is QUANTISED to a trace vertex, both when it is propagated from
   the loop below and when it is taken on the +X bearing (SkinPatterns.cs:894-901, both branches
   indexing `Cumulative`). It therefore jumps from row to row by up to half the mesh's own vertex
   spacing, which on a 96-a-ring dome is up to 0.098 m against a hexagon half-width of 0.15 m.

Defect 5 is the SECOND of the two causes the design input names as the setout distortion, the seam
quantised to a trace vertex, and rule 4.2.6 answers it. Defect 1 is NOT his first cause. His first
cause is "the arc-length RATIO mapping", and defect 1 is the absence of any ratio: an absolute column
set identical on every row, with a single global bound (SkinPatterns.cs:2263-2269). The actual ratio
mapping is the courses engine's, `lowerRatio` and `upperRatio` in `BandCell`
(SkinPatterns.cs:1963-1969), it belongs to pattern 0 rather than to the honeycomb, and section 1.8
states it, states what would replace it and rules that it is DEFERRED out of this round, with section
13.2 putting the deferral to him. Nothing in section 4 addresses it and section 4 should not be read
as though it did.

The measured cost of defect 1 is separately large: the plan filter withholds 26 to 49 per cent of
honeycomb cells on the two-oculus fixture and 38 to 62 per cent on the serpentine. Those two figures
carry a warning of their own, which rule 12.4(g) enforces: they were quoted against prose
reconstructions of fixtures nothing in this repository can rebuild, so they are not a before that any
after can be measured against until rule 12.0's fixtures exist. On a plain hemispherical dome the
same port measured only 5 of 161 dropped, so the defect hides on the easy fixture, which is why
section 12 builds the hard ones.

### 4.2 The rule that fixes it

The whole of it is one move: the lattice stops being laid in ABSOLUTE arc length and is laid in each
row's OWN NORMALISED arc length, with each row taking its own count from its own length. That is
what the courses engine already does and it removes defects 1, 3 and 4 together, and with the cap of
section 2 it removes what is left of 4.

RULE 4.2.1. Rows. Row k is the traced level curve at field value k * CH, k running 0 to K, with the
two extremes pulled inside by the epsilon of rule 1.5.2. There are no rows beyond the surface and no
clamping of rows onto the extremes; the construction at SkinPatterns.cs:2224-2232 goes.

RULE 4.2.2. Counts, stated in CENTRES and not in columns. Row k takes its own CENTRE count
`n_k = max(1, round(L_k / (1.5 * S)))` from its own arc length, and its COLUMN count is
`m_k = 2 * n_k`, so the column pitch is `L_k / m_k` against a target of the shipped 0.75 S.

The count is taken in centres because rule 4.2.4 puts a centre on every other column, and on a CLOSED
row that alternation only closes onto itself when the column count is EVEN. Round a column count
straight off the length and it is odd about half the time: the repository's own barrel would give
round(6.0 / 0.45) = 13. With m_k odd, columns m_k - 1 and 0 are adjacent round the wrap and BOTH
carry a centre, so two hexagons sit side by side at the meridian and their cells overlap there, which
`KeepValidPlans` then drops (SkinPatterns.cs:1618-1673). That is the very defect this section exists
to remove, arriving by a different road. Forcing the column count even removes the case instead of
detecting it. The same arithmetic is used on an open strip, where the parity does not matter, so that
both branches share one formula.

Note what this rule does NOT claim, because an earlier draft claimed it and the claim is false. The
shipped column set is ABSOLUTE, `uc = 0.75 * size * i` (SkinPatterns.cs:2269), so its pitch is
exactly 0.75 S whatever the row's length is; the per-row pitch is `L_k / m_k`, which equals 0.75 S
only where L_k is an exact multiple of it. WHERE A ROW'S LENGTH IS AN EXACT MULTIPLE OF 1.5 S the
per-row rule reduces to the absolute one, and nowhere else. It does not reduce on the repository's
barrel: every level cut there is a straight strip of length 6 (Program.cs:8396-8422) and the
honeycomb check runs it at S 0.6 (Program.cs:11536-11537), so n = round(6.0 / 0.9) = 7, m = 14 and
the pitch is 6 / 14 = 0.4286 m against 0.45 m. Every column, every vertex and every outline moves,
on the one fixture an earlier draft named as unchanged. Rule 12.4(a) is written against what is
genuinely invariant.

RULE 4.2.3. Columns. Column j of row k sits at NORMALISED arc `t = j / m_k`, j = 0 to m_k - 1 on a
closed row, so the last column closes onto the first exactly, there is no leftover at the meridian,
and the u domain is WRAPPED rather than cut. Defect 3 is gone.

THERE IS NO PHASE TERM IN THIS RULE. An earlier draft gave column j of row k the position
`(j + 0.5 * (k mod 2)) / m_k`, a half-column phase on odd rows, while rule 4.2.4 ALSO alternated the
centres by parity. That applies the honeycomb's row-to-row offset TWICE: adjacent rows' centres would
then sit 1.5 / m_k apart rather than the 1 / m_k a honeycomb needs, which is half the in-row centre
spacing of 2 / m_k. The phase and the parity are two spellings of ONE rule and only one of them may
be applied. The parity of rule 4.2.4 carries the whole offset, which is also what the shipped lattice
does: its centres within a row sit 1.5 S apart and the row above is displaced 0.75 S, exactly one
column pitch, by `centreRow = 1 + i + 2 * j` alone (SkinPatterns.cs:2274), against a column set that
carries no phase at all (SkinPatterns.cs:2269).

On an OPEN strip, t is normalised arc from the strip's start, columns run j = 0 to m_k so both ends
carry a column, and the cells at the two ends are truncated at the strip's ends and marked CLIPPED by
the standing rule of section 4.4. The column set `j / m_k` is symmetric about t = 0.5, which is the
strip's arc-length midpoint seam, so the strip stays mirror-symmetric, the property the courses
engine already guarantees (SkinPatterns.cs:1929-1942).

RULE 4.2.4. Centres. A hexagon has its centre at (row k, column j) with j + k EVEN and
1 <= k <= K - 1. Adjacent rows' centres are then offset by exactly one column pitch, 1 / m_k in
normalised arc, which is half the in-row centre spacing of 2 / m_k, and that is the honeycomb's own
offset. It is the shipped lattice's alternating parity (`centreRow = 1 + i + 2 * j` at
SkinPatterns.cs:2274 puts column i's centres on rows of parity (1 + i) mod 2) restated per row, and
by rule 4.2.3 it is the ONLY place the offset is applied.

RULE 4.2.5. Vertices, stated as fractions of the ROW'S OWN column pitch so that where the pitch is
the target 0.75 S they reproduce the shipped hexagon exactly. All six are in normalised arc and EACH
IS EVALUATED ON ITS OWN ROW'S PARAMETERISATION, never on the centre row's:
  (a) the two SIDE vertices, on row k, at t(k, j) minus 2 / (3 m_k) and plus 2 / (3 m_k);
  (b) the two BOTTOM vertices, on row k - 1, at t(k, j) minus 1 / (3 m_(k-1)) and plus
      1 / (3 m_(k-1));
  (c) the two TOP vertices, on row k + 1, at t(k, j) minus 1 / (3 m_(k+1)) and plus 1 / (3 m_(k+1)).
Two thirds and one third of a column pitch are, at a pitch of 0.75 S, exactly S / 2 and S / 4, which
is the shipped flat-topped hexagon (SkinPatterns.cs:2290-2298) and the corner set the harness pins
for the barrel's column-1 interior cell, x at 3.3, 3.6, 3.75, 3.6, 3.3 and 3.15 about uc = 0.45
(Program.cs:11556-11563).

THE BRACKETING COLUMNS DECIDE HOW MANY VERTICES A ROW CONTRIBUTES AND NEVER WHERE THEY SIT. An
earlier draft took the bottom and top vertices from "the two columns of row k plus or minus one that
BRACKET t(k, j)", and that cannot draw a flat-topped hexagon at all. The shipped offsets are a third
and two thirds of a column pitch, and no lattice column sits at a third of a pitch; bracketing puts
them at plus and minus one whole pitch against sides at two thirds, which is an hourglass with
re-entrant sides rather than a convex hexagon. With the phase of the earlier draft also in force the
brackets coincide with the sides, all six vertices land on two u values and the cell is a rectangle,
whose neighbours in the row above and below then overlap it by half a pitch and are dropped by the
filter. Bracketing survives ONLY in rule 4.3 and only as a COUNTING rule: how many of row k - 1's or
k + 1's columns fall within the cell's own span is what decides whether that row contributes one
vertex, two or three, and whichever it contributes still sit at that row's own thirds.

Every one of these lies inside its own row by construction on a closed row, so no vertex is ever
clamped there and the top edge can no longer collapse. Defect 2 is gone, and with it the whole
`overlaps` interval test at SkinPatterns.cs:2382-2388: membership reduces to "rows k - 1, k and k + 1
all exist in this chart", which is a question about the chart and not about arithmetic. On an OPEN
strip a vertex whose normalised position falls outside [0, 1] is truncated at the strip's end and its
cell is CLIPPED and KEPT, so the clipped count does not vanish; it moves, and rule 12.4(a)
re-measures it rather than asserting the shipped number.

RULE 4.2.6. The seam becomes exact. It stops being quantised to a trace vertex. A closed row's seam
is the point on that row nearest IN PLAN to the row below's seam, found by exact projection onto the
row's segments and stored as a continuous arc length, not by choosing the nearest sample vertex
(SkinPatterns.cs:894-901). An open strip's seam stays its arc-length midpoint
(SkinPatterns.cs:888), which is exact already. Defect 5 is gone, and this is the same fix section 5.4
needs for Param's consistent-corner requirement, which is why they are one job.

### 4.3 Pentagons and heptagons, plainly

Yes. A surface with Gaussian curvature cannot be tiled by hexagons alone. Accommodating positive
curvature requires pentagons and negative curvature requires heptagons, which is why a sphere needs
exactly twelve pentagons and why a football is built as it is.

Under rule 4.2 the row counts change where the rows change length, and the odd cells follow from that
and from nothing else. Where n(k - 1) equals n(k), row k - 1 has exactly one column falling within
the cell's own span, the cell takes the two bottom vertices of rule 4.2.5(b) either side of it, and
the tiling is a plain honeycomb. Where n(k - 1) differs from n(k) by ONE CENTRE, that is by two
columns, the cell's span on row k - 1 may hold NO column of that row, in which case the cell takes
one bottom vertex instead of two and has five sides; or TWO, in which case it takes three bottom
vertices and has seven. The same reading applies to row k + 1 and the top vertices. That is what rule
4.2.5's closing paragraph means by bracketing surviving as a counting rule: it decides how many, the
thirds of rule 4.2.5 decide where. This is not a defect and must not be filtered.

RULE 4.3.1. Five- and seven-sided cells are ALLOWED only at a row where the count changes, meaning
where m(k - 1), m(k) and m(k + 1) are not all equal. Anywhere else they are a defect and must fail
the harness.

RULE 4.3.2. They are PLACED, not left to fall where the arithmetic puts them. The engine distributes
a count difference to the columns whose normalised position is nearest t = 0.5 on a closed row, that
is, at the meridian opposite the seam; and to the two ends on an open strip. Reason: that is where the
setout is already least symmetric and where the shipped scar lives, so the odd cell sits in the place
the author already reads as the back of the pattern rather than beside the seam he sets out from.

RULE 4.3.3. They are COUNTED. The diagnostics carry `skin.odd_cells` with the two counts and the
rows at which the count changed: "Odd cells: 4 five-sided, 2 seven-sided (row counts change at rows
5, 7, 9)".

RULE 4.3.4. The count-change rows themselves are chosen, not accepted. Where two adjacent rows would
differ by more than one CENTRE, that is by more than two columns, the difference is spread over the
intervening rows one centre at a time by adjusting `n_k` upward or downward by one from its rounded
value, so no single row carries more than one CENTRE change and no cell has more than seven sides.
The adjustment is made in CENTRES and never in columns, because rule 4.2.2 requires a closed row's
column count to stay even and an even count can only change by two; a rule stated in columns would
either break the parity or be unable to move at all. A row whose rounded count would differ from its
neighbour by more than one centre is a row where CH is too coarse for the surface's convergence, and
the diagnostics say so.

### 4.4 What the honeycomb keeps

The chart construction (SkinPatterns.cs:2122-2156), the `CurveAt` lookup, the course index taken from
the cell's own centre row (SkinPatterns.cs:2405-2412, which is a deliberate resolution of the spec's
"centroid height" and stays), and the ruling that a cell crossing the surface boundary is CLIPPED and
KEPT rather than dropped (SkinPatterns.cs:2188-2191). Note for the spec's own language: one branch of
Cells can hold two lattice rows, because the course label is a clamped derivation from centreRow, so
no sentence anywhere may say "one branch is one row" for pattern 1.

## 5. The Surface output

### 5.1 The honest justification

Param's stated reason is that Grasshopper struggles to turn polylines with arcs into surfaces. Skin
never produces an arc: every cell leaves through `ClosedOutlineCurve`, which builds a `PolylineCurve`
from plain double[3] triples and appends the first point again (SkinComponents.cs:517-536). Arcs
enter only through Export's Cells port, where an arbitrary author curve is chorded at 5 mm
(DeliveryComponents.cs:1184-1195). The real reason a Surface output earns its place is that Skin's
cells are NON-PLANAR many-sided rings, and turning one of those into a face by hand is the awkward
job. Say that on the port rather than the arc reason, which would be a promise about a case Skin does
not produce.

### 5.2 The API, and what is unverified

There is no `Brep`, `NurbsSurface`, `CreateEdgeSurface`, `CreatePatch` or `CreatePlanarBreps`
anywhere in this repository: a repository-wide search over plugin\ and tests\native_smoke\ returns
nothing. A Surface output would be the plugin's first Brep. The project targets net8.0-windows
against Rhino 8's RhinoCommon, so the full Rhino 8 Brep API is available. Every statement in this
section about RhinoCommon's own behaviour is therefore an assertion about the API and is NOT checked
against any call site in this repository; it must be proved by the first task of the wave and the
rules below adjusted if it is wrong.

RULE 5.2.1. The surface is derived from the two RUNS the cell was built from, never re-derived from
the finished closed polyline. Both runs still exist separately inside `BandCell` before they are
concatenated (SkinPatterns.cs:1965-1972), and a ruled surface between them is the cell's own
surface. Recovering four chains from the concatenated ring afterwards means re-detecting the joint
corners, which `Dedupe` has already made ambiguous.

RULE 5.2.2. `Brep.CreateFromCornerPoints` and `Brep.CreateEdgeSurface` with four curves are both
refused as routes. `Run` inserts every trace vertex strictly between the two joints
(SkinPatterns.cs:1215-1262), so a courses cell has an unbounded and varying point count, and four
corners would chord across the surface, which is exactly what `Run` exists to prevent.
`Brep.CreatePlanarBreps` is refused because the two runs sit on two different level curves and the
ring is non-planar by construction.

RULE 5.2.3. Per pattern:
  (a) a COURSES cell is a loft of two sections, the lower run and the upper run, both in the same
      direction, with `LoftType.Straight` and no closing;
  (b) a HEXAGON is a loft of three sections, the bottom run, the two-point section from the left
      side vertex to the right side vertex, and the top run, again straight and unclosed;
  (c) a FORCE-ALIGNED cell is a courses cell by rule 3.2.3 and takes route (a);
  (d) a CAP is the one cell that cannot be a single face. It is emitted as a single Brep of
      triangular faces fanned from the cell's own PLAN INTERIOR POINT, lifted onto the surface
      exactly as route (e) below lifts it, to each segment of the loop, joined. Say plainly on the
      port that the cap is a Brep of many faces
      while every other cell is one, rather than pretending otherwise. `Brep.CreatePatch` is not
      used: it is a fitting solver, its output is not the surface the cell describes, and a
      deterministic fan is worth more here than a smooth guess. A WEDGE of a cap that rule 2.6 has
      split is NOT a cap for this purpose: by rule 2.6.4(a) it is an ordinary band cell between two
      level curves, so it takes route (a) and is a single face. Only the centre disc takes this
      route;

      ERRATUM, 2026-09-03, from the whole-branch review's finding 6. This rule read "fanned from the
      net vertex of greatest field value inside its loop", which is a DIFFERENT apex from route
      (e)'s and one the engine has never built. The engine is right and the spec was wrong, and the
      rule above is amended to the engine rather than the engine to the rule, for three measured
      reasons. A cap's loop need not contain a net vertex at all: the crown disc rule 2.6.3 leaves
      behind is a small ring found by bisection, sitting between vertices on any net whose crown is
      coarser than the disc, so the apex the old wording names can simply fail to exist and the cell
      would have no surface. Even where one exists it is a MESH vertex and not a point on the loop's
      own patch, so a fan raised to it can leave the cap's own surface. And the two routes share one
      code path in `CellSurface`, which has no `Cap` branch anywhere and never had: a rule that
      wanted two apexes wanted a branch nobody wrote. What the rule was reaching for, an apex at the
      high point of the cap, is what the lifted plan interior point gives on any cap whose loop is a
      level curve, since the surface inside a crown loop rises to a single summit. The apex is now
      asserted, at the height of the cap's own outline, the way route (e)'s already was.
  (e) ANY OTHER CORNER COUNT takes the same deterministic fan, and this route is not optional
      tidying. Rule 3.3.5 requires three- and five-sided force-aligned cells and rule 4.3 requires
      five- and seven-sided honeycomb cells. Route (b) is written for a cell with exactly two side
      vertices and route (a) for a cell with exactly two bed edges, so neither serves any of them,
      and without route (e) check 12.4(d), which asserts five- and seven-cornered cells exist, and
      check 12.5(b), which asserts `skin.surface_failed` is zero on every fixture, could not both
      pass. A cell whose corner count its pattern's own route does not fit is emitted as a single
      Brep of triangular faces fanned from the cell's own PLAN INTERIOR POINT, which the filter has
      already computed once per outline and hands on (SkinPatterns.cs:1647 calling
      SkinPatterns.cs:1445), lifted onto the surface by locating the net face containing it in plan
      and evaluating that face's plane there, to each segment of the outline, joined. Say plainly on
      the port, as route (d) already does for the cap, that such a cell is a Brep of several faces.

RULE 5.2.4. Construction happens on the SOLVE thread and only there, beside `ClosedOutlineCurve`,
the split the component already keeps (SkinComponents.cs:467-469). Nothing in SkinPatterns.cs may
reference RhinoCommon; that is the rule the harness's whole ability to measure the engine rests on
(SkinPatterns.cs:110-117).

### 5.3 The failure path

RULE 5.3.1. The Surface tree is aligned with the Cells tree BRANCH FOR BRANCH and ITEM FOR ITEM.
Where a cell will not close into a Brep, a NULL is placed in that slot. The item is never dropped:
dropping it would silently misalign every downstream index against the Cells tree, which is the one
promise this output exists to keep.

RULE 5.3.2. Failures are counted, reported as `skin.surface_failed` with the count as its Value, and
raised as one runtime Warning naming the count and the first offending course. A failure is a defect
in this engine, not a fact about the geometry, so the harness asserts zero on every fixture, the same
discipline `RequireNothingDropped` keeps for the plan filter (Program.cs:9728-9759).

      ERRATUM, 2026-09-03, plan 2026-09-03-skin-defects-and-free-edge task 1. There are now TWO
      failures and TWO Warnings, because there were always two failures and only one Warning. Since
      the thickness input landed, the component built the face and then REPLACED it with the
      thickened solid, so a cell whose face closed and whose thickening did not came back as a null
      and was reported under this rule's wording, which sends the reader to `CellSurface` when the
      fault is in `ThickenCellSurface`. Param measured 148 nulls of 262 cells on a force-aligned run
      at Thickness 0.29 and 12 of 282 on a courses run. The rules are now these. A face the engine
      built is NEVER discarded: where the thickening fails the slot carries the un-thickened face,
      the cell is still exported, and only a failed FACE leaves a null, which is what rule 5.3.1
      already says a null means. The two counts are separate and so are their sentences: one names
      cells whose FACE would not close and the null slots they leave, the other names faces that
      would not close into a SOLID at the Thickness in force and states plainly that those cells are
      still exported and drawn as the un-thickened face.

      ADDED in fix round 1, 2026-09-03, correcting the erratum above rather than the rule. The SOLID
      sentence's remedy is worded against the Along Normal mode ACTUALLY IN FORCE, so
      `ThickenFailureLine` takes the flag. Its first draft advised "a smaller Thickness, or Along
      Normal off" whatever the mode, and Along Normal defaults to FALSE (SkinComponents.cs:179-190),
      so on a default canvas, which is the canvas Param ran, it named a toggle already off. Off is
      also the likelier cause on a steep force-aligned arch: off means the offset is vertical at
      (0, 0, Th) (`ThicknessOffset`), and a side wall is built per outline edge from the quad
      (a, b, b + offset, a + offset) (SkinComponents.cs:950-953), so an outline edge that itself
      runs vertical puts all four corners on one vertical line and `Brep.CreateFromCornerPoints` has
      no quad to make. With Along Normal off the message therefore names ON as the thing to try;
      with it on it offers a smaller Thickness and says the toggle is already on. Neither wording
      may advise turning Along Normal off, and the harness pins that.

      One further correction of record, same round. The Brep half of the thickener has THREE exits
      past the under-three-corner guard, not one: the per-wall `Brep.CreateFromCornerPoints` at
      SkinComponents.cs:950-953, which returns before any join is called; the `JoinBreps` result
      test at :957-959; and the `IsSolid` test at :963. The harness can measure only that the guard
      itself did not fire, and must not be read as attributing the nulls to the join.

      The slot decision is `SkinComponent.ClassifyCellSurface`, a static of three booleans, and the
      two sentences are `SkinComponent.FaceFailureLine` and `SkinComponent.ThickenFailureLine`. They
      are statics because RhinoCommon's native core does not initialise outside Rhino: measured
      2026-09-03 on this machine, `Brep.CreateFromCornerPoints` throws "System.DllNotFoundException:
      Unable to load DLL 'rhcommon_c'". So no count of cells that would not close can be taken in
      the native_smoke harness at all, and this rule's "the harness asserts zero on every fixture"
      has never been enforceable for the Brep half. What the harness holds instead is the slot rule
      itself, the two sentences, and a force-aligned fixture at a nonzero Thickness which it did not
      have before, which is why this defect was never caught here. The Brep counts stay with
      `scripts/rhino_skin_surface.py`, which Param runs inside Rhino.

RULE 5.3.3. An empty course survives as an EMPTY BRANCH in both trees, because `OutputTree` creates
every path before filling it and the component pre-creates one branch per course
(SkinComponents.cs:365-371). Branch {2} must mean course 2 in both outputs or the alignment promise
is void.

### 5.4 The tree and the seam convention Param asked for

RULE 5.4.1. Branch path is the course, 0 up from the bottom, exactly as Cells. Within a branch, the
same order as Cells, which section 7 sets.

RULE 5.4.2. Every cell's outline begins at its LOW-U corner on its LOWER bed curve. This is already
true of both engines and is being made a stated rule rather than an accident: a courses cell's first
point is `Run(lowerCurve, u0 * lowerRatio, ...)`'s first element, which is `PointAt(curve, uStart)`
(SkinPatterns.cs:1966-1967, :1227); a hexagon's first point is setout vertex 0, the bottom-left
corner at (uc - S/4, centreRow - 1) (SkinPatterns.cs:2290-2294, :2392-2394). The cap's first point is
its own seam, and a WEDGE of a split cap takes the ordinary rule rather than the cap's, since by rule
2.6.4(a) it is a band cell: its first point is its low-U corner on the OUTER curve, which is the
lower of its two boundaries. The `lowerRatio` in that citation is the proportional arc mapping of
rule 1.8.1, which
is his first cause of the setout distortion and is DEFERRED by rule 1.8.4; it is cited here for the
corner convention alone and this sentence does not ratify it.

RULE 5.4.3. His analogy is exact and so is its limit. Setting a circle's seam to face a corner works
because the seam is the same on every circle. Here the seam is a property of each level curve, and
two things move it between courses today: it is quantised to a trace vertex (defect 5 of section
4.1), and odd courses are additionally phase-shifted half a pitch by the running bond
(SkinPatterns.cs:1804). Rule 4.2.6 removes the first, which is drift and is a defect. THE SECOND
STAYS. RULING (mine, the controller's and not Param's): the half-pitch stagger is KEPT, because it is
BOND and not drift. A running bond exists precisely so that cell 0 of course r + 1 does not begin
above cell 0 of course r, and the bond is not sacrificed to the convenience of a tree mapping.

The consequence for the Surface output's tree must be stated plainly here and again on the port,
because it is the one thing an author building a mapping will assume the other way. The Surface tree
is aligned with the Cells tree branch for branch and item for item by rule 5.3.1, so item k of branch
r IS the surface of cell k of course r; what it is NOT is the surface sitting directly above item k
of branch r - 1. Rows do not stack. Item 0 of each course begins half a piece round from item 0 of
the course below it, deliberately, and on a closed course the count itself may differ between courses
as the girth changes. An author who wants the piece above a given piece must find it geometrically,
by its span overlapping in signed arc, and not by taking the same index in the next branch. So the
promise the port can honestly make is "every cell begins at the same corner of itself, and courses
are deliberately offset half a piece". The alternative is recorded rather than adopted: a
suppressible stagger is a one-line option, it would make the mapping index against index, and it
would cost the bond, which is why it is not taken here. Section 13.1 records the ruling and section
13.2 does not carry it as a question.

## 6. Piece size: one threshold, both ends

Param ruled: merge into the neighbour, default a third of the target size, adjustable. He ruled
separately, on 2026-09-01, that a crown cap above the MAXIMUM piece size splits into a ring of
wedges, and that one threshold governs both ends of the size question. So the threshold is named
here once and used twice, by this section at the bottom end and by section 2.6 at the top.

RULE 6.0. THE THRESHOLD, NAMED ONCE. `MP` is the Min Piece port of rule 9.5: a pure fraction of Size,
default 1/3, floored at 0 and capped at 0.5 by rule 6.4. From that one number:
  (a) the MINIMUM PIECE SIZE is `MP * S`, in the model's own length unit, which is metres because S
      is, and this section merges anything at or under it;
  (b) the MAXIMUM PIECE SIZE is `Mx = S / MP`, in the same unit, which is 3 S at the default and 2 S
      at the cap, and rule 2.6 splits a crown cap strictly above it.
Reciprocal, and not a second port. The two ends are one question asked twice, and a second number
would let an author set a minimum above his own maximum and leave the engine with nothing sensible to
do. At MP = 0 the minimum is 0 and Mx is unbounded, so both ends go off together, which is the only
coherent reading of a single threshold turned off.

The default's arithmetic is worth seeing. At MP = 1/3 a piece may run from S / 3 to 3 S, and 3 S is
exactly the upper bound rules 3.3.3 and 3.3.4 already impose on an ordinary force-aligned piece,
which check 12.3(d) reads. The maximum therefore introduces no new bound on ordinary pieces at the
default. What it does is put the crown cap, which is the one cell that escapes every other size rule
in this engine, under the same bound as everything else.

RULE 6.1. Threshold. A cell whose along-course span is AT OR UNDER `MP * S`, compared with a 1e-9
tolerance, is merged, MP being the port of rule 9.5 and `MP * S` the minimum piece size of rule
6.0(a). Against S rather than against the course's own pitch, because that is what he said. What a
merged cell IS is rule 6.7, and naming a merge without naming its outline would leave the engine
undefined.

The comparison is "at or under" and not "under", deliberately. The barrel's odd-course end pieces are
exactly half a pitch, 0.3 m at S 0.6 and CH 0.5, which the harness pins in those words
(Program.cs:9762-9771), and MP is capped at 0.5 by rule 6.4, so the largest threshold the engine can
ever see on that fixture is `0.5 * 0.6 = 0.3`. Under a strict inequality the fixture's own end piece
sits exactly ON the threshold and the boundary case is undecided at the one value the harness can
reach. Deciding it is worth more than the purity of a strict test, and the 1e-9 tolerance is what
stops the decision turning on the last bit of a double.

Note for him: within a course every interior piece is exactly the pitch by construction
(SkinPatterns.cs:1801-1806), so the rule bites on an open strip's end pieces and on the force-aligned
pattern's insertions and terminations. It does NOT bite on the honeycomb, which rule 6.7(b) excludes
outright with its reason. It is mostly a rim rule.

RULE 6.2. Which neighbour wins. The neighbour ALONG THE COURSE with the SHORTER span, so merging
keeps the maximum piece length down rather than growing one long piece. A tie goes to the neighbour
with the lower U0, which is deterministic and is the seam-ward one. A piece with only one neighbour,
which a strip end has, merges into that one.

RULE 6.3. What stops a cascade. Merging runs in ONE pass over a course's spans, seam outward, and a
span that has already absorbed a merge is not itself tested again. Each span can therefore grow at
most once per side and the pass terminates in a single sweep. There is no iteration to convergence
and no recursion.

RULE 6.4. Bounds. MP is floored at 0, where merging is disabled and, by rule 6.0(b), the maximum is
unbounded with it, so the crown cap never splits either; and capped at 0.5, above which merging two
pieces makes a piece longer than the target and the rule would oscillate. A value outside the range,
a negative one included, is clamped to the nearer bound with a Warning naming the clamped value, the
discipline the CH floor already keeps (SkinComponents.cs:603-611). The cap at 0.5 does a second job
beside its own: it is what makes rule 2.6.2's proof hold, that a wedge of a split cap can never come
out under the minimum piece size.

RULE 6.5. What it never does. It never merges across a course boundary, never across two traced
components, and never leaves a course empty: a course whose ONLY piece is under the threshold keeps
that piece as it is. No cap piece is ever merged, the wedges of a split cap included: a cap is one
stone or one rosette by rules 2.2.3 and 2.6, and rule 2.6.2 proves that no wedge can fall under the
minimum in the first place, so the case never arises rather than being suppressed.

RULE 6.6. The merge runs BEFORE `KeepValidPlans`, so the filter sees and judges the cells the author
is actually handed. Merged pieces are counted as `skin.merged_pieces`.

RULE 6.7. WHAT A MERGED CELL IS.
  (a) COURSES and FORCE ALIGNED. The merged cell is REBUILT and not glued: the `BandCell`
      construction is run again over the UNION span, with the same lower curve, mid curve and upper
      curve the two members were built from (SkinPatterns.cs:1954-1973), taking U0 from the lower-U
      member and U1 from the higher-U member, `Clipped` as the OR of the two members' flags, and
      `Course` unchanged, since rule 6.5 forbids merging across a course boundary. Rebuilding rather
      than gluing is not fastidiousness: gluing two outlines leaves the absorbed joint's two points
      in the ring as a pair of collinear corners, which is exactly the degeneracy rule 6.8 exists to
      guard `PlanInteriorPoint` against.
  (b) THE HONEYCOMB IS EXCLUDED FROM SECTION 6 OUTRIGHT, and the reason is that "the neighbour ALONG
      THE COURSE" has no referent in a lattice. A row's centres sit TWO columns apart
      (SkinPatterns.cs:2274, rule 4.2.4), the cells lying between them belong to the rows above and
      below, and two hexagons of one row meet at a single side vertex rather than along an edge.
      Merging two cells that touch at a point is not a merge, it is a bow tie, and `KeepValidPlans`
      would drop the result. The honeycomb's short cells are the five- and seven-sided cells of rule
      4.3 and the truncated end cells of rule 4.2.3, and both are wanted as they are.

RULE 6.8. THE ZERO-AREA CANDIDATE CENTROID, which is his carried ruling in his own words: "a
candidate interior point can be the centroid of three collinear trace corners lying exactly ON the
joint, where the containment test is a coin flip. Named fix: refuse a candidate centroid whose
triangle has no area." The defect is live and unguarded. `PlanInteriorPoint` walks the triangles from
`SplitPolygonInOrder`, takes each one's plain centroid and tests `PlanContains`, with no area test
anywhere (SkinPatterns.cs:1465-1477).

RULE: before `PlanContains` is called on a candidate centroid, the candidate triangle's PLAN AREA is
computed by the centred signed shoelace of rule 11.2 and the triangle is SKIPPED where the absolute
area is at or below 1e-12 square metres. Skipping a triangle is free, because `SplitPolygonInOrder`
yields them one at a time and the method already walks on to the next one; what is not free is
accepting a point whose containment answer is arbitrary, because `PlansOverlapWithInteriors` then
decides an overlap on it and a good cell is dropped where two courses touch.

This round makes the coin flip MORE likely, not less, which is why it cannot be carried again: rule
3.5.3 makes cells carry more corners, rule 8.2.5 puts short pieces hard against a cut locus, and rule
6.7(a) merges spans whose joint lay on a shared boundary. Check 12.6(f) measures it. This is the
second of the two exceptions rule 11.11 permits.

## 7. Build order

Param ruled: from the seam outward.

RULE 7.1. Within a course branch, cells are ordered by the absolute value of their own seam-relative
mid-span, ascending: |(U0 + U1) / 2|. A tie, which the two cells either side of the seam give, goes
to the negative side first. That is seam outward, alternating left and right, and on a closed loop it
walks both ways round from the seam and meets at the meridian opposite it. Where a course holds
several traced components, components are ordered as they are today, by their index, before this rule
applies within each.

That reading is only true where U is SIGNED about the seam, and on a CLOSED course today it is not.
`CourseSpans`' closed branch emits spans at `(phase + k * pitch, phase + (k + 1) * pitch)` for k = 0
to pieces - 1 (SkinPatterns.cs:1920-1927), so every U0 and U1 is non-negative and the set runs one
way round the loop from the seam back to the seam. An absolute value of a non-negative number does
nothing: the order would be identical to today's `ThenBy(U0)` at SkinPatterns.cs:1829, the tie would
never occur, no two cells would ever lie on opposite sides of the seam, and check 12.7(a) would fail
on every dome fixture. The rule already behaves as written on the open-strip branch
(SkinPatterns.cs:1929-1942) and on the honeycomb, whose U0 and U1 are the clamped plus and minus half
values at SkinPatterns.cs:2415.

RULE 7.1.1. So a CLOSED curve's spans are RE-CENTRED into the signed range (-L / 2, +L / 2] AT
SOURCE, in `CourseSpans` itself, by subtracting L from any span whose mid exceeds L / 2. The
re-centring is on the SPANS and not merely on the sort key, and the choice is stated because the two
give different U0 values in the sidecar. Re-centring the spans gives U one meaning across the whole
engine, closed and open alike, namely signed arc about the seam; wrapping only the sort key would
leave two meanings in one engine and would make rule 6.2's "a tie goes to the neighbour with the
lower U0, which is the seam-ward one" false on every dome. The re-centring happens BEFORE the merge
of section 6 and before this order is taken.

RULE 7.1.2. The cost of 7.1.1 is stated rather than discovered. It is a change to shipped behaviour:
every pinned U0 and U1 on a closed fixture moves, and the sidecar's recorded spans move with them. A
span that STRADDLES the seam after re-centring, which the piece containing arc 0 does whenever the
phase is non-zero, keeps U0 negative and U1 positive; its mid is nearest zero, so rule 7.1 puts it
first without a special case.

RULE 7.2. Today's order is by course, then component or chart, then U0 ascending
(SkinPatterns.cs:1825-1833 and :2423-2431), which walks a course from one end to the other. This is
therefore a change to shipped behaviour and not a restatement.

RULE 7.3. The consequence that must not be discovered late. `KeepValidPlans` runs in EMISSION ORDER
over the sorted list, by its own stated rule (SkinPatterns.cs:1584-1590), and which of an overlapping
pair survives is decided by that order. Changing the sort changes which cells survive. The filter
runs in the NEW order, because "the first cell wins" must mean "the first cell the author is handed",
and seam-outward then biases survival towards the cells nearest the seam, which are the setout cells
and the right ones to keep. Every pinned drop count in the harness must be re-measured against the
new order, and a moved number is not by itself a regression.

RULE 7.4. WHAT THE ORDER ACTUALLY SERVES, and it must be in the port description in these terms.
This order does not reach the studio. `build_tessellation` sorts every tessellation, authored or
generated, by course and then by the polar angle of each cell's centroid about the cut's own centroid
(tessellation.py:473) and reassigns each cell's index from that sort (tessellation.py:474-477). The
sidecar's own `c<course>p<n>` key, which Export writes as a plain per-course running counter
(DeliveryComponents.cs:1566-1578), is kept as an opaque string and never parsed. So the file's order
is discarded the moment it is read.

Param made this ruling believing it fed the studio's build sequence. He was shown that it does not,
and on 2026-09-01 he KEPT IT ANYWAY, on the two grounds that are true. It serves the GRASSHOPPER
AUTHOR, who sequences his own work on the canvas. And it serves the OVERLAP FILTER, which is not
cosmetic at all: `KeepValidPlans` runs in emission order and the FIRST cell emitted wins an overlap
(SkinPatterns.cs:1584-1590), so emitting seam-outward makes the SEAM STABLE, the cells nearest the
setout seam being the ones that survive, and pushes the losses out to the edges of each course,
symmetrically on both sides because the order alternates. The order therefore serves the author and
the filter and NOT the studio, and section 13.1 records the ruling on that basis. What does not
survive is the sentence on the port claiming the order is the studio's build sequence, which is rule
7.5.

RULE 7.5. The port description is CORRECTED, and correcting it is the operative half of Param's
ruling: the order stands, the claim made about it on the port does not. The present text at
SkinComponents.cs:145-153 contains the false clause "each run ordered along the course, the studio's
build sequence within a run". It is false for the reason rule 7.4 gives and it must go. The
replacement, exactly:

  "One closed polyline per cell, on the thrust surface, as a TREE branched by COURSE (path = course,
  0 up from the bottom), which is now the ONLY carrier of the course: Export reads the branch path.
  Within a branch cells run FROM THE SEAM OUTWARD, alternating either side of it. That order is for
  sequencing work on this canvas, and for one thing more: where two cells overlap in plan the FIRST
  one emitted is the one kept, so the cells nearest the seam survive and the losses fall out at the
  edges of the course. It is NOT the studio's build sequence. The studio re-sorts every tessellation
  by course and then by each cell's angle about the cut's own centre and reassigns its own index, so
  the order in the file is discarded on import. Courses are a RUNNING BOND, so cell 0 of one course
  does not sit above cell 0 of the course below it and the two courses may not even hold the same
  number of cells; do not map item k of one branch against item k of the next. Wire into Export's
  Cells. Do NOT graft, flatten or regraft the wire: the branch path is the course, and a flatten
  sends every cell to course 0 and every build stage with it."

The stagger clause in that text is rule 5.4.3's ruling stated where an author will meet it, and the
Surface port's own description carries the same clause, since the Surface tree is aligned item for
item with this one by rule 5.3.1 and inherits the offset with it.

## 8. Band splitting at topology transitions

### 8.1 The shipped rule and why it must change now

Today a band whose three levels do not correspond one for one is refused WHOLE, leaving a hole, and
the comment records it as an interim ruling with splitting deferred (SkinPatterns.cs:1785-1791). The
honeycomb refuses every lattice row spanning such an interval (SkinPatterns.cs:2279-2287). Under the
Z field those events are rare. Under a rim-distance field they are the cut locus, which a barrel has
along its whole ridge and a groin vault along every groin, so the shipped refusal would put a hole of
one full course along every ridge on the model. Section 8 is therefore a precondition for section 1,
not an improvement beside it.

### 8.2 The rule

RULE 8.2.1. The correspondence test itself does not change. It is the one in section 11.3 and 11.4:
kind, then nesting depth, then symmetric rotation-invariant plan distance, and a mutual bijection in
both directions (SkinPatterns.cs:996-1021, :1097-1124). Nothing about the refusal criterion moves;
only what is done when it fires.

RULE 8.2.2. BISECTION, written out as arithmetic, because "trace at (a + b) / 2" names a level that
has ALREADY been traced. A band carries three levels, its lower at heights[2r], its MID at
heights[2r + 1] and its upper at heights[2r + 2] (SkinPatterns.cs:1769-1771), and its mid IS
(a + b) / 2. What a sub-band needs is its OWN mid, at a quarter point. So when
`Corresponds(mids, lowers)` or `Corresponds(mids, uppers)` fails for band r spanning field interval
[a, b] with mid m = (a + b) / 2:
  (a) the lower sub-band is [a, m], with lower a, MID (a + m) / 2 and upper m;
  (b) the upper sub-band is [m, b], with lower m, MID (m + b) / 2 and upper b;
  (c) each is tested by the correspondence test of rule 8.2.1, each half that passes is tiled, and
      each half that FAILS recurses independently on the same rule.
One level of bisection therefore costs TWO new mid traces, not one.

RULE 8.2.3. DEPTH. Six levels, so the residual interval is CH / 64, which on the shipped CH of 0.35 m
is about 5.5 mm. RULING (mine; the design input asks for "the full band-splitting answer" and does
not name a depth). Six because the residual is then below the coarsest tolerance anything downstream
uses and well above the 1e-9 arithmetic floor.

RULE 8.2.3a. THE COST, stated correctly, because an earlier draft gave it as "six extra traces on a
band" and it is not. A full recursion to depth d costs up to 2^d - 1 new mid traces on ONE band,
which is up to 63 at depth six, delivered in at most d + 1 passes of `TraceAll` over the whole
ascending list by rule 8.2.9. Every new level pays that pass's whole bottom-up cost, including the
quadratic nesting-depth vote (SkinPatterns.cs:692-713, :719-730) and the quadratic mean-nearest-plan
distance of every correspondence test (SkinPatterns.cs:1036-1064), which rule 11.7 already names as
this engine's cost hazard. In practice a band's failure is local and one half passes at each level,
so the ordinary cost is of order 2 d, twelve traces; the bound is what must be budgeted.

RULE 8.2.3b. A CAP ON THE TOTAL. No solve may introduce more than 128 extra levels across all bands
together. At the cap, splitting stops, every interval still failing is refused by rule 8.2.6, and the
diagnostics say that the cap was reached and how many intervals it left. A pathological net must not
be able to lock Grasshopper's canvas thread, which is the discipline rule 11.7 keeps for the plan
filter and the same reason it is kept.

RULE 8.2.4. Every sub-band that corresponds is tiled as an ordinary band, by the pattern's own rule,
at the SAME course index as the band it came from. Splitting must not invent courses: the studio
builds one stage per distinct course present (staging.py:162-207), and a split that added courses
would silently multiply his analysis stages. The tree keeps exactly `CourseCount` branches.

RULE 8.2.5. Pieces within a sub-band take that sub-band's own mid curve and its own pitch, so a thin
sub-band beside a cut locus gives short pieces, which section 6 then merges. That is the correct
behaviour: a course that runs into a ridge closes with a short stone.

RULE 8.2.6. The residual interval that still fails at depth six is REFUSED, exactly as today, its
interval is named in the diagnostics, and the Warning is raised.

RULING (mine, and it is a DEPARTURE FROM HIS WORDING and not merely a detail of it). His carried
ruling reads "Topology transitions: the full band-splitting answer, REPLACING the present refusal",
and this rule does not replace the refusal, it keeps it as the base case. That is the larger of the
two departures in section 8, larger than the depth of rule 8.2.3, and it is the one that leaves a
hole on the model: a residual interval of up to CH / 64, which at the shipped CH of 0.35 m is 5.5 mm
of uncovered surface along the transition, and at CH 0.5 is 7.8 mm. The argument for keeping it is
that the critical set is measure zero on the surface, so the refused area shrinks geometrically and
the hole goes to nothing; the alternative he was promised, an explicit critical-point solve, would be
exact and would need a saddle classifier the engine does not have and this wave cannot afford beside
everything else in it. Section 13.2 puts the choice to him rather than settling it here.

RULE 8.2.7. The honeycomb gets the same treatment at the CELL level, not the row level. A candidate
hexagon is refused when the three rows it maps through do not correspond as a chain WITHIN ITS OWN
CHART. Today the test is global over the whole net and refuses every row spanning the interval
(SkinPatterns.cs:2279-2287 with `SpansTransition` at :2004-2015), so a transition on one side of a
two-sided vault holes the other side too. Restricting it to the cell's own chart makes the hole
local. A hexagon is not bisected: its height is fixed at 2 CH by construction and halving it would
make a different pattern.

RULE 8.2.8. The diagnostics wording changes with the field. "between z=1.234 and z=1.584" becomes
"between d=1.234 m and d=1.584 m" under a rim distance and keeps "z=" only under the fallback of rule
1.7.4 (`TransitionLine`, SkinPatterns.cs:2023-2043). The harness's two string pins on that wording
move with it in the same commit (Program.cs:10136-10145, :10345-10349), and rule 9.3.6 says why they
survive at all.

RULE 8.2.9. EVERY LEVEL THIS WAVE INTRODUCES ENTERS ONE ASCENDING HEIGHT LIST, AND `TraceAll` RUNS
ONCE OVER THE WHOLE LIST. Its contract is that heights arrive ASCENDING and its own comment gives the
reason: nesting depth, direction normalisation and seam assignment are one bottom-up pass, a closed
loop's seam is propagated from the loop below it and an open strip's direction from the strip below
it (SkinPatterns.cs:457, :466-468, :878-906). A sub-band mid traced on its own has no level beneath
it, so its seam falls to the +X rule at SkinPatterns.cs:900 instead of the propagated one and its
cells' u origin does not agree with the rest of its own course.

So the band-split mids of rule 8.2.2, the cap boundary of section 2 and the bed curves of section 3
are ALL inserted into the single ascending list, and the whole list is traced again. Splitting is
therefore a staged solve: trace, test, insert the new mids of every failing band, trace the whole
list once more, test again, and so on to the depth of rule 8.2.3 or the cap of rule 8.2.3b. The
consequence must be stated rather than found later: inserting a level RE-PROPAGATES the seams and
directions of every level above it, so a split moves the seam pins of the split fixtures, and a moved
seam pin there is not by itself a regression.

## 9. Port changes

### 9.1 Skin's ports after this wave

Inputs, in order: 0 Result RES, 1 Pattern P, 2 Size S, 3 Course Height CH, 4 Min Piece MP. MP is a
fraction of S and no length of its own, and it sets BOTH ends of the size question by rule 6.0: the
merge threshold below and the crown cap's split threshold above. Rule 9.5 states its type, default,
units and bounds in full.

Outputs, and the list is CONDITIONAL on his answer to section 13.2 item 1, because rule 9.4.1 is my
ruling and not his:
  if he takes the RES output: 0 Result RES, 1 Cells C, 2 Surface SRF;
  if he declines it: 0 Cells C, 1 Surface SRF, which is literally what his own sentence asked for,
  with the numbers living on the message chin of rule 9.3.1 and in the Remark of rule 9.3.5.
Everything else in this spec holds either way. Only rule 9.4, the port pin at 12.10(a) and the RES
checks at 12.10(d) turn on the answer, and each of them says so where it stands.

### 9.2 Removals

RULE 9.2.1. FLOWLINES goes. It is output index 2 today (SkinComponents.cs:162-167) and it exists so
the author can see the field before committing to a cut. Once section 3 makes the head joints the
flow lines, the pattern IS the field and a separate output says it twice. The dependency the design
input names is respected: this is the same wave that reshapes the pattern, and Flowlines may not be
removed before it.

RULE 9.2.2. DIAGNOSTICS goes. It is output index 3 today (SkinComponents.cs:168-180).

RULE 9.2.3. COURSES goes from Skin. Its content is already in Cells as the branch path, and section
10 makes Export read that path. It is output index 1 today (SkinComponents.cs:155-161).

RULE 9.2.4. Nothing in the plugin reads Flowlines or Diagnostics as DATA; a repository-wide search
for "Flowlines" returns only SkinComponents.cs, and the only other "FL" is an unrelated Form Lines
output at VisualiseComponents.cs:358-362. But the port NAMES are read twice over, by the ports-moved
load warning at NativeComponentBase.cs:571-600 and by the harness's pin at Program.cs:100-102, so
every saved definition will raise the warning on open and the pin must be updated in the same commit.

### 9.3 What replaces the removed Diagnostics text

Three places, and between them they carry more than D did, not less.

RULE 9.3.1. The MESSAGE CHIN carries the pattern, the counts and the number that diagnoses
uniformity: "312 cells · 9 courses · courses · piece 0.55 to 0.61 m". Min and max piece length are on
the face of the component because they are what showed him the force-aligned pattern was not uniform,
0.377 m against 3.889 m, and losing them would remove the measurement this round exists to restore.
The present chin is at SkinComponents.cs:385-388.

RULE 9.3.2. RUNTIME MESSAGES keep everything that is a hole: the scaled plan-drop Warning
(SkinComponents.cs:335-363), the transition Warning (SkinComponents.cs:297-307), the field fallback
of rule 1.7.4, the unreachable-vertex Warning of rule 1.7.3, and the surface failure of rule 5.3.2.
They gain one more, which is not a hole but a stone nobody can lift and belongs at the same volume:
the oversized-cap Warning of rule 2.6.6, naming the cap's girth against the maximum.

      ERRATUM, 2026-09-03, plan 2026-09-03-skin-defects-and-free-edge task 1. The transition Warning
      NAMES the heights. Its last sentence read "Diagnostics names the heights" and nothing named
      them: the intervals live on `SkinPatternResult.TransitionIntervals` and inside the engine's own
      `Diagnostics` string, and no component has read either since rule 9.2.2 removed the D port, so
      the sentence sent the reader somewhere he could not go. The Warning now carries the intervals
      themselves, formatted by `SkinPatterns.TransitionWhere`, which is the same arithmetic and the
      same wording the diagnostics line uses, so the two readings of one refusal cannot drift apart.
      Rule 8.2.8's distinction survives it: metres of rim distance where the field is one, "z=" only
      under the fallback of rule 1.7.4.

RULE 9.3.3. RESULT DIAGNOSTICS ENTRIES carry every number, written with
`ResultDiagnostics.Replace(result, "Skin", entries)` (ResultDiagnostics.cs:72-82) so they travel
forward and Diagnose reads them back beside every other component's. Numbers go in Value, Tolerance
and Unit and never only inside the sentence, the rule at ResultDiagnostics.cs:16-17. Severity is one
of ok, info, warning, error (ContractDtos.cs:635-637). The entries, with their codes:

  skin.field (info): which field, how many rim vertices seeded it, and, in Context, how many named
    supports and how many force edges were dropped as unmappable by rules 1.3.4 and 1.3.6.
  skin.pattern (info), skin.cells (info, Value), skin.courses (info, Value).
  skin.piece_length_mean / skin.piece_length_min / skin.piece_length_max (info, Value, Unit "m").
  skin.clipped (info, Value): boundary-clipped cells.
  skin.plan_degenerate_dropped and skin.plan_overlap_dropped (Value; warning above zero, ok at zero).
  skin.transition_bands (Value; warning above zero, ok at zero; Context carries the intervals).
  skin.crown_caps (info, Value; Context carries each cap's girth, its wedge count where rule 2.6
    split it and zero where it did not, the maximum piece size the split was measured against, and
    the count of caps rule 2.6.6 emitted whole and oversized, which is the count the Warning of rule
    9.3.2 is raised on).
  skin.odd_cells (info, Value; Context carries the five- and seven-sided counts and the rows).
  skin.merged_pieces (info, Value; Context carries the count of courses whose only piece was kept
    short by rule 6.5 and the count of merged pairs still under the threshold by rule 6.3, which is
    what check 12.6(b) reads).
  skin.degenerate_centroids (info, Value): candidate triangles skipped by rule 6.8's zero-area guard.
  skin.surface_failed (Value; warning above zero, ok at zero).
  skin.rim (info, Value): rim vertices used, and how many named supports were dropped.
  skin.field_unreachable (Value; warning above zero, ok at zero).

RULE 9.3.4. The trade must be stated to him and not discovered. A balloon and a Diagnose report can
be read; neither can be wired into a panel to compare two patterns numerically or to log a sweep of
sizes. The Result diagnostics recover most of that, because Diagnose emits them and they carry real
numbers rather than a formatted string, which is strictly better than the text output for anything
programmatic. What is genuinely lost is a text output he can drop a panel on directly.

RULE 9.3.5. THE BALLOON CARRIES THE REST, AS ONE REMARK, and this rule is required by his own
sentence rather than added to it. The design input attaches exactly one condition to the removal he
asked for: "Some of that is already on the Message line and in the warnings; the REST MUST MOVE to
the balloon as a Remark rather than disappear", and his own words ratify the vehicle, "leave the info
bubble that pops up as enough". Rules 9.3.1 to 9.3.3 name three replacements and none of them is a
Remark: 9.3.1 is the chin, 9.3.2 keeps only what is a hole, and 9.3.3 is the Result entries, which
are the reserved option of rule 9.4 and may not survive his answer. So the residual D content that is
not a hole and does not fit the chin, namely mean piece length, the boundary-clipped count, each
cap's girth and its wedge count where rule 2.6 split it, the odd-cell counts and their rows, and the
merged-piece count, reaches him nowhere at all unless it is stated here. An OVERSIZED cap is not in
that list, because rule 9.3.2 makes it a Warning: it is the one cap number loud enough to need one.

RULE: the component raises ONE runtime Remark per solve carrying that residual content, in the D
output's own reading order, so that the balloon alone remains sufficient exactly as he said,
INDEPENDENT of whether the RES output of rule 9.4 survives his answer. A Remark is the right level:
it is not a hole, so it must not be a Warning, and the scaled plan-drop Warning of rule 9.3.2 must
stay the loudest thing on the component.

RULE 9.3.6. THE ENGINE'S RETURN RECORD IS RESTATED IN FULL, because rule 9.3.3 asks for twelve
entries carrying real Values and section 12 measures all of them ON THE ENGINE, through reflection
without a canvas, while `SkinPatternResult` today carries Cells, CourseCount, a formatted Diagnostics
string, TransitionBands, PlanDegenerateDropped and PlanOverlapDropped and nothing else
(SkinPatterns.cs:102-108). It becomes:

    internal sealed record SkinPatternResult(
        IReadOnlyList<SkinCell> Cells,
        int CourseCount,
        string Diagnostics,
        int TransitionBands,
        IReadOnlyList<(double Low, double High)> TransitionIntervals,
        int PlanDegenerateDropped,
        int PlanOverlapDropped,
        string FieldKind,
        int RimVerticesUsed,
        int RimVerticesDropped,
        int ForceEdgesDropped,
        int UnreachableVertices,
        int ClippedCells,
        IReadOnlyList<double> CapGirths,
        IReadOnlyList<int> CapWedgeCounts,
        int CapsOversized,
        int FiveSidedCells,
        int SevenSidedCells,
        IReadOnlyList<int> CountChangeRows,
        int MergedPieces,
        int DegenerateCentroidsSkipped);

      ERRATUM, 2026-09-03, plan 2026-09-03-skin-defects-and-free-edge task 1. The record gains
      `int ThreeSidedCells = 0`, appended LAST, after `WeldCollapsedDropped`, with a default, so no
      existing construction site moves. It exists because the force-aligned pattern's closer of rule
      3.3.5 has THREE corners and was being carried in `SevenSidedCells`, where the component
      printed it as "seven-sided" while the engine's own diagnostics line called the same number
      "three-sided". The two readings of one pattern disagreed by name. `SevenSidedCells` now means
      only rule 4.3's honeycomb rim cell, and the force-aligned pattern reports zero in it. The
      Remark of rule 9.3.5 carries all three counts, each under its own name.

      The listing above is in any case no longer the whole record: `ClosedRows`, `ExtraLevels`,
      `TracePasses`, `MergedShortKept`, `MergedStillShort`, `FlowLines`, `BedCurves` and
      `WeldCollapsedDropped` were each added by a later task without amending this rule. The record
      in `SkinPatterns.cs` is the authority; this listing is the shape rule 9.3.3 was written
      against.

The three cap members are read together and each is per CAP, not per cell: `CapGirths` carries the
girth of each emitted cap, meaning the CENTRE DISC's girth where rule 2.6 split it and the whole
cap's girth where it did not; `CapWedgeCounts` carries that cap's W, zero where it was not split; and
`CapsOversized` counts the caps rule 2.6.6 emitted whole above the maximum, which is what check
12.2(g) reads and what the Warning of rule 9.3.2 is raised on.

The three piece lengths are DERIVED from the surviving cells and need no member, excluding Cap cells
by rule 2.3.2a, which since that rule was amended means excluding the wedges of a split cap as well
as its disc. `skin.surface_failed` is deliberately NOT on this record: the Brep build happens on
the solve thread beside `ClosedOutlineCurve` and never in SkinPatterns.cs, which is rule 5.2.4, so
that count belongs to the component and check 12.5(b) reads it there.

The Diagnostics STRING IS KEPT, on the engine's record and not on any port. The design input's own
implementation note says the harness's assertions on D's text "move to the engine's own returned
PatternDiagnostics, which is where they should have been, since the engine is measurable without
Rhino and the component's text is not". So the two string pins at Program.cs:10136-10145 and
:10345-10349 survive, read off the engine rather than off a component, and their wording changes only
where rule 8.2.8 changes it, from "z=" to "d=", in the same commit. What rule 9.2.2 removes is the D
PORT and not the text.

### 9.4 The new RES output, which is NOT yet his

RULE 9.4.1. RULING (mine; the design input put this to him and he has not answered). His own sentence
asked for a REMOVAL only, "Remove Diagnositcs too, leave the info bubble that pops up as enough". He
never asked for a new output. What the design input did was reserve the question in terms: "A BETTER
OPTION IS AVAILABLE and is put to him, because it fits the plugin's own architecture rather than
working around it ... That removes two ports and adds one, leaves Skin with Cells and Surface as its
only geometry outputs". An earlier draft of this spec turned that reserved option into settled rules
with no marker on them and pinned it into the port list and the verification, which left him no
branch on which to say no. Section 13.2 item 1 puts it back to him, rule 9.1 states both port lists,
and checks 12.10(a) and 12.10(d) are conditional on the answer.

The case FOR it, so he can weigh it: Result RES would be output 0, the house convention that puts it
first, worked at ColumnsComponent.cs:189-205 and pinned for Fit in the harness, and Skin is today the
only component in the chain that takes a Result and emits none (SkinComponents.cs:101-109 registers
the input; SkinComponents.cs:139-181 registers four outputs and none is a ResultParam). The case
AGAINST it is his own sentence: he asked for fewer ports, and the balloon of rule 9.3.5 already
carries everything on its own.

RULE 9.4.2. IF HE TAKES IT, it is a PASSTHROUGH with skin.* diagnostics written into it. It does NOT
carry a skin block on ResultDto, and this spec deliberately does not ask for one. Carrying the skin
would be a contract change on the scale of MouldDto: a nullable property, a Validate call and an
envelope schema constant (ResultContracts.cs:65-71, :106, :29-34), and nothing would consume it,
since Export reads cells from its own ports. Deferred and named.

RULE 9.4.3. IF HE TAKES IT, it MUST be built with Skin's own `CloneResult`
(SkinComponents.cs:640-641), which reattaches RawWire after the deep clone. A plain deep clone drops
it silently, and RawWire is what a downstream worker dispatch depends on (SkinComponents.cs:703-717).

RULE 9.4.4. IF HE DECLINES IT, rule 9.3.3's twelve entries are not written anywhere, the numbers live
on the chin of rule 9.3.1 and in the Remark of rule 9.3.5, and section 12 measures every one of them
off the engine record of rule 9.3.6 instead, which it does in either case. Nothing else in this spec
changes, which is the test of whether the option was properly reserved.

### 9.5 Min Piece MP as an input

RULING (mine, the controller's and not Param's, drawn from his word "adjustable"). MP is a PORT and
not a fixed constant, and it is stated here once in full because rule 6.0 uses it twice.

  TYPE. A number input, `Param_Number`, `GH_ParamAccess.item`, at input slot 4, optional, so a
  definition that never touches it goes on behaving as the design input's "a third of the target
  size".
  DEFAULT. 1/3, which gives a minimum piece of S / 3 and a maximum of 3 S.
  UNITS. NONE. MP is a pure FRACTION of Size and carries no length of its own, which is exactly what
  lets one number set a minimum of `MP * S` and a maximum of `S / MP` in whatever unit S is already
  in. The two derived lengths are in metres because S is in metres, and neither is a second input.
  ZERO. Both ends off, by rule 6.0: no merging and no crown-cap split. It is a legal value and not an
  error, and it is the value an author uses to see the engine's raw output.
  NEGATIVE, OR ABOVE 0.5. Out of range and clamped to the nearer bound by rule 6.4, with a Warning
  naming the clamped value. A negative therefore means "off" rather than meaning a failed solve,
  because refusing the whole output over a number he can see and fix on the canvas would cost him
  more than the mistake did.

It is a fifth port on a component that is already paying the ports-moved warning for its outputs, so
it costs nothing extra this wave and it costs a second warning if it is added later.

## 10. Export's input reorder

### 10.1 The order

Param's sentence gives: Result, Cells, Courses if it survives, Radius, Name, Studio URL, Live, Write.
He OMITTED PATH.

RULING, AND IT IS MINE, THE CONTROLLER'S, AND NOT HIS. Path sits IMMEDIATELY AFTER Name, because the
name and the folder together decide the file and neither means anything without the other. The order
becomes:

  0 Result RES, 1 Cells C, 2 Courses CO, 3 Column Radius R, 4 Name N, 5 Path P, 6 Studio S,
  7 Live L, 8 Write W.

Putting Path after Name rather than before it has a second merit worth stating: it leaves every port
Param DID name in exactly the relative order he named it in, so the ruling inserts the omitted port
and disturbs nothing he decided. An earlier draft of this spec put Path immediately before Name,
which reads just as well as prose and moves Name one slot from where his own sentence had it; the
ruling above supersedes it.

He did not name that slot and this stays marked as my ruling until he says otherwise; section 13.1
records it. Path is not optional in effect: Write with a blank Path writes nothing and says so as a
Warning rather than an Error, deliberately, so the solve survives (DeliveryComponents.cs:794-803); a
path that is not rooted is refused, and a drive root is refused (DeliveryComponents.cs:704-742).
Dropping it or burying it changes what the component can do.

### 10.2 Courses survives on Export and dies on Skin

RULING (mine, within his "if both of those are still needed"). Export KEEPS its Courses port; Skin
loses its Courses output.

RULE 10.2.1. Export's Cells port drops `GH_DataMapping.Flatten` (DeliveryComponents.cs:278), becomes
`GH_ParamAccess.tree`, and is read with `GetDataTree`. Each branch's path index is the course of every
cell in that branch. That reproduces exactly what Courses supplies today for Skin-sourced cells, since
Skin already branches Cells by course (SkinComponents.cs:365-379).

RULE 10.2.2. Export's Courses port keeps its Flatten (DeliveryComponents.cs:290) and its list access.
It exists for the one case branch-path derivation cannot serve: an author wiring a FLAT list of
hand-authored cells with an explicit per-item course list. Removing it would forbid that case
outright.

RULE 10.2.3. The two are mutually exclusive and the conflict is REFUSED, not resolved. When Cells
arrives as more than one branch AND Courses is non-empty, the component raises an Error naming both
and writes nothing, because guessing which the author meant is how a study silently loses its stages.
When Cells arrives as ONE branch, Courses supplies the course as it does today; when Cells arrives as
one branch and Courses is empty, every cell is course 0, which is what one branch means.

RULE 10.2.4. The hazard must be on the port. Any Flatten, graft or regraft between Skin and Export
destroys the courses, and a Flatten specifically sends every cell to course 0, which is one studio
stage instead of many (staging.py:162-207). The port text of rule 7.5 says so and Export's own Cells
description must say it too.

RULE 10.2.5. The negative-course refusal stays exactly as it is (DeliveryComponents.cs:830-840),
and it now applies to derived courses too: a branch path cannot be negative, so this becomes
unreachable from a Skin wire and stays reachable from a hand-wired Courses list, which is where it
was earned.

### 10.3 The consequence of the reorder

`SideMoved` fires on a different NAME at any index, not only on a changed count
(NativeComponentBase.cs:458-462). So every saved definition will reattach its wires BY POSITION onto
different ports, raise the ports-moved Warning (NativeComponentBase.cs:343-349), and have Live HELD
until it is toggled off and on again (DeliveryComponents.cs:528-532, with the rationale at
DeliveryComponents.cs:118-135). That is the designed behaviour and it is stated here so it is not
discovered on the next file open. The plan should say plainly that every existing definition needs
its Export wires checked once after this wave.

## 11. What must not move

These are the behaviours six adversarial rounds bought, from the shipped design's three errata and
from the code. Nothing in this rework may break them, and the harness must go on asserting each.

RULE 11.1. EXACT LEVEL-SET TRACING ON TRIANGULATED FACES. The net triangulates at construction, as
its own invariant (SkinPatterns.cs:35-39), on the shortest VALID PLAN diagonal with ties to the lower
vertex index and a stated fallback for a polygon with no valid diagonal (SkinPatterns.cs:240-254,
:259-285). The crossing count on a triangle is 0 or 2, so the pairing is forced and the saddle
ambiguity is gone (SkinPatterns.cs:531-540). This survives the field change: the chord is the exact
level set of the piecewise-linear field on a planar triangle for the same reason it was the exact
level set of Z, which is rule 1.4.4.

RULE 11.2. THE CENTRED SIGNED PLAN AREA. The shoelace sum is taken on coordinates measured from the
points' plan mean (SkinPatterns.cs:827-842). The measured reason is a sited model: on the dome
fixture translated 1000 m in plan the crown loop's centred area is -1.131e-11 m2 while the raw sum
returns exactly 0.0, which reads as "not negative" and turns the top band's cells into bow ties. A
sited model is the ordinary studio case.

RULE 11.3. CORRESPONDENCE BY KIND, THEN NESTING DEPTH, THEN ROTATION-INVARIANT DISTANCE. All three
stages, in that order (SkinPatterns.cs:996-1021). Kind because a strip and a loop are never the same
piece of surface. Depth because no distance can separate two loops that coincide in plan at a ridge,
and depth is topological and survives rotation, translation and remeshing
(SkinPatterns.cs:636-713). Distance last, and it must stay a symmetric mean nearest-plan-distance
(SkinPatterns.cs:1036-1064) rather than any bounding-box measure: a box is a property of the world
axes and the sweep found the two-hump barrel refused at exactly five angles in 180 degrees, with 84
cells and up to 214 overlapping pairs at the rest.

RULE 11.4. THE MUTUAL BIJECTION. A band is refused on the MATCHING and not on the count
(SkinPatterns.cs:1097-1124): built in both directions, no curve claimed by two, none unclaimed, and
the two maps inverses. A count test is too weak and both reproductions are recorded there. Section 8
changes what happens after the test fires and changes nothing about the test.

RULE 11.5. THE ENFORCED PLAN-VALIDITY GUARANTEE. `KeepValidPlans` (SkinPatterns.cs:1618-1673) runs
on the sorted list in emission order, drops a self-crossing cell, then drops a cell overlapping one
already kept, counts each kind separately, reports both as their own lines, and the component raises
a scaled Warning (SkinComponents.cs:335-363). The guarantee is enforced and not argued, because one
bad cell makes the studio reject the whole tessellation. Every clean fixture must go on asserting
both counts are ZERO (Program.cs:9728-9759), and the harness must go on calling the ENGINE's own
predicates rather than keeping arithmetic of its own (Program.cs:9675-9719).

RULE 11.6. `PlanFoldTolerance` AS A PERPENDICULAR DISTANCE. Side values are divided by their own
segment's length so the tolerance is one nanometre of perpendicular separation everywhere on the
model (SkinPatterns.cs:1297-1338). The measured reason is the crown: a raw cross-product floor was
about 0.65 mm on micron-scale edges, and the two arithmetics disagreed 72 times in 422
configurations.

RULE 11.7. `PlanInteriorPoint` FOUND ONCE PER OUTLINE AND HANDED IN. The pair walk is quadratic and
one answer can cost milliseconds; found inside the pair test it took the courses engine over three
minutes on the canvas thread at 96 a ring (SkinPatterns.cs:1518-1541, :1606-1616). Section 3.5.3
makes this dearer, not cheaper, so it must not regress. Rule 6.8's zero-area guard goes INSIDE that
one call and not beside it: it is a constant-time test per candidate triangle, taken before the
containment walk it would otherwise pay for, so it makes the method cheaper on a degenerate outline
and unchanged on every other, and this rule and rule 6.8 are not in tension.

RULE 11.8. THE `BandCount` SLIVER MERGE (SkinPatterns.cs:1855-1869), which rule 2.4.2 now depends
on.

RULE 11.9. `FacePolylines`'s internal static signature (SkinComponents.cs:965-971). It is a
compile-time contract with Export's call site at DeliveryComponents.cs:1054-1055 and does not move.

RULE 11.10. `CloneResult`'s RawWire reattachment (SkinComponents.cs:640-641), and the Skin GUID
7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063 (SkinComponents.cs:95-96) with the Armadillo Dual GUID staying
dead.

RULE 11.11. THE PERMITTED EXCEPTIONS, AND THERE ARE TWO. Everything else in section 11 stands
untouched; these two are changes to shipped behaviour and each is permitted for a stated reason.

  (a) RULE 3.5.4's raised duplicate test and the vertex-on-edge test added to `KeepValidPlans`'
      degenerate branch, so the plugin's filter becomes at least as strict as the studio's reader
      (tessellation.py:632-636, :648-654). The safety argument must be stated for each HALF
      separately, because it does not hold for both. Adding the vertex-on-edge test makes
      `KeepValidPlans` drop MORE cells and never fewer, so it cannot hide a defect, and every fixture
      asserting zero drops must still assert zero after it. Raising the duplicate test does NOT have
      that property: it removes POINTS from outlines rather than dropping cells, and removing a point
      can turn a self-crossing plan ring into a clean one, so it can make the filter drop FEWER.
      What it guarantees instead is the thing it exists for, that no surviving outline holds two
      points the studio would reject, and check 12.6(g) asserts exactly that rather than assuming it.
  (b) RULE 6.8's zero-area guard on a candidate centroid in `PlanInteriorPoint`
      (SkinPatterns.cs:1465-1477), which is his own carried ruling with his own named fix, and which
      this round makes more necessary rather than less. It changes an ARBITRARY answer into a defined
      one and can only stop a cell being dropped for a reason that was never real, so it too cannot
      hide a defect. Check 12.6(f) measures it.

His third carried ruling, the arc-length ratio mapping, is NOT an exception here, because it is not
being changed: rule 1.8.4 defers it out of this round and section 13.2 item 2 puts the deferral to
him.
Saying so plainly is the point of this rule. A reader who counts the exceptions and finds the ratio
missing should find the deferral rather than an omission.

## 12. Verification

Everything below is a check in
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\tests\native_smoke\Program.cs,
measuring the ENGINE through reflection without a canvas, which is the convention the existing Skin
checks already follow (Program.cs:9789 onward). Where a check needs the component rather than the
engine, it is read and not run, the `ValidateExportDefaultTessellation` convention.

RULE 12.0. FIXTURES FIRST. The two-oculus and serpentine fixtures are BUILT ONCE, in the repository,
beside the existing ones (SkinBarrelNet at Program.cs:8404, SkinDomeNet at :8490, SkinRingVaultNet at
:8603, SkinSpiralVaultNet at :8907, SkinAnnularVaultNet at :8966, SkinTwoPeakNet at :9049,
SkinTwoHumpBarrelNet at :9102, SkinSplitAndDeathNet at :9137, SkinLShapedNet at :9189). They have
been prose reconstructions differing between rounds, and the honeycomb's measured losses of 26 to 49
and 38 to 62 per cent are quoted against fixtures nothing in this repository can rebuild. Add
`SkinTwoOculusNet`, `SkinSerpentineNet` and `SkinEllipticalDomeNet`, and add a rim and a force-edge
list to every fixture as further constructor arguments so each has both a bare Z-fallback form and a
rim-bearing, force-bearing one.

The three new fixtures are DESCRIBED HERE, at the level of detail SkinDomeNet's own comment gives
(Program.cs:8482-8489: two octagonal rings and an apex, radius 2 - h at height h, a level curve of
perimeter 16 (2 - h) sin(pi / 8) with a vertex on the +X axis). Without that, two implementers build
two different nets, get two different numbers, and the rule fails at the thing it exists for.

  `SkinTwoOculusNet`. A plan grid over the rectangle x in [0, 10], y in [0, 6] at a 0.25 m pitch, so
  i runs 0 to 40 and j runs 0 to 24, with vertices at (0.25 i, 0.25 j, z) and
  z = 2 sin(pi x / 10) sin(pi y / 6), which is zero on all four edges and 2 m at the centre. Quad
  faces between adjacent grid vertices, EXCEPT that a face is omitted where its plan centre lies
  within 1.0 m of (3, 3) or within 1.0 m of (7, 3), which cuts two oculi with stepped free edges. The
  rim is every boundary vertex of the rectangle, that is every vertex with i = 0, i = 40, j = 0 or
  j = 24, and NOT the oculus edges, which is what makes this the fixture that measures rule 1.3.3 and
  rule 2.2.1(b) at once.

  `SkinSerpentineNet`. A sheared strip vault, plan-injective by construction. For i = 0 to 60 and
  j = 0 to 12, with x = 0.25 i and t = (j - 6) / 6, the vertex is
  (x, 0.6 sin(2 pi x / 10) + 1.5 t, (1.4 + 0.6 sin(2 pi x / 7.5)) cos(pi t / 2)). Quad faces between
  adjacent (i, j). Plan x is strictly increasing in i and plan y strictly increasing in j at every i,
  so the net is plan-injective without an argument, which the whole engine requires and a true offset
  serpentine would break at its own bends. Both long edges, j = 0 and j = 12, sit at z 0 and are the
  rim. The crest meanders between 0.8 m and 2.0 m along the strip, so a constant-Z level curve above
  0.8 m breaks into SEVERAL components of differing length, which is what makes this fixture hard for
  the honeycomb's per-row count of rule 4.2.2 and for section 8's transitions at the same time.

  `SkinEllipticalDomeNet`, which exists for rule 2.6.6's base case and for nothing else. It is
  SkinDomeNet's own construction with the plan circle replaced by an ellipse: rings at parameter h
  from 0 to 1 in 24 steps and 96 vertices a ring, the vertex at ring h and angle theta sitting at
  (3 (1 - h) cos theta, 1.5 (1 - h) sin theta, 2 h), with quad faces between adjacent rings and the
  last ring collapsed to the apex (0, 0, 2). The base ring at h = 0 is the rim. Because the plan is
  not a circle, the rim-distance field's cut locus inside the crown is a SEGMENT along the major axis
  rather than a point; the level curves near the top shrink onto that segment instead of onto an
  apex; and the girth at the top cut therefore stays of the order of twice the segment's length
  however fine CH is made. That is the one shape on which rule 2.6.3 can find no qualifying level, so
  it is the only fixture that reaches rule 2.6.6.

12.1 THE FIELD (section 1).
  (a) On a fixture whose rim is its whole base ring, every rim vertex reads 0 and no vertex reads
      negative.
  (b) On a flat rectangular plate meshed regularly, with one long edge as the rim, the field at every
      vertex equals its perpendicular distance from that edge to within 2 per cent, which pins the
      triangle update rather than the edge fallback. On the same plate the shipped Z field is
      constant, so the plate also pins rule 1.5.4: courses under the rim field and none under Z.
  (c) On a hemispherical dome of R with its base ring as rim, the field at the apex equals
      pi * R / 2 to within 2 per cent.
  (d) BED SPACING, which is the whole point. On the same dome, the along-surface distance between
      consecutive course boundaries is CH to within 5 per cent at every sampled meridian and at
      every course, against the shipped engine on the same net where the ratio between the flattest
      and steepest course spacing exceeds 5. Measure both and assert the improvement, not just the
      new number.
  (e) EMPTY RIM keeps the FIELD identical, and that is what this check asserts, no more. Every
      fixture built through the two-argument constructor produces a Levels array byte-identical to
      its own vertex Z values, hence traced level curves, nesting depths, seams and correspondence
      results byte-identical to the shipped build. It does NOT assert identical CELLS, and a check
      written that way would be false: section 4 relays the honeycomb, section 6 merges short pieces
      at the default MP of 1/3, and rule 7.1.1 re-centres every closed course's spans, all of which
      change cells on every field including this one. Take the field identity as the assertion and
      re-measure the cells. Within that limit this is still the single most valuable check in the
      wave, because it is what proves the field change did not disturb the tracer, the correspondence
      or the filter.
  (f) NO RIM ON THE RESULT falls back to Z with the stated Warning text and the `skin.field` entry
      naming it.
  (g) DISCONNECTED NET: a two-piece net with a rim on one piece only reports the other piece's
      vertices as unreachable, emits no cells there, and raises the Warning.
  (h) RIM INDEX SPACE: a Result whose form and equilibrium vertex counts are EQUAL but whose
      orderings differ must still seed the right vertices. Build one deliberately and assert the rim
      is the form-mapped set, not the equilibrium set. This is the trap at
      VisualiseComponents.cs:196-206 against SkinPatterns.cs:164-178 and it fails silently if got
      wrong. ON THE SAME RESULT, assert the same of the FORCE EDGES of rule 1.3.5: the edge whose
      weight lands on a given net vertex pair is the edge the equilibrium named for the FORM vertices
      that pair came from. That trap fails silently in exactly the same way and poisons the whole of
      section 3 rather than the rim alone.
  (i) A RIM OF ISOLATED VERTICES, which is what rule 1.4.1(b) exists for. Build a fixture whose rim
      is a set of PAIRWISE NON-ADJACENT support vertices, four of them on a square-plan shell, so
      that no triangle anywhere has two frozen corners at the first pop. Assert the field is FINITE
      at every vertex and that `skin.field_unreachable` is zero. Under an update rule written only as
      the two-frozen triangle case this check fails at every vertex, which is the point of taking it.
  (j) THE DEFERRED FIRST CAUSE, measured rather than left unknown, by rule 1.8.5. For every joint on
      every fixture, compute the plan distance between the proportional image of rule 1.8.1 and the
      gradient-marched image of rule 1.8.3, and pin the maximum per fixture as a MEASUREMENT. It is
      the size of his cause 1 on real geometry and it is what tells him whether rule 1.8.4's deferral
      is cheap. Taking the measurement needs no engine change, because the march is computed in the
      harness and never in the pattern.

12.2 THE CROWN CAP (section 2).
  (a) DOME: exactly one cell carries the Cap flag, its course is CourseCount - 1, its outline is the
      whole topmost boundary curve, and its plan projection is simple.
  (b) DOME: no cell whose outline has fewer than four corners exists above the cap's course, and the
      total surface area covered by cells, summed as plan area, differs from the net's own plan area
      by less than one per cent. That is the coverage assertion the epsilon loop fails today.
  (c) BARREL with two springing rims: ZERO caps, the top band tiled on both sides, and the
      diagnostics naming the ridge in the stated words.
  (d) TWO-OCULUS fixture: zero caps at the oculi, because rule 2.2.1(b) refuses a region touching a
      free edge, and the diagnostics naming which test refused.
  (e) SLIVER: a dome whose field extent is a near multiple of CH plus a twentieth still puts the cap
      at course CourseCount - 1, which pins rule 2.4.2 against the "cap one band low" failure.
  (f) THE SPLIT (section 2.6). On the dome at a CH large enough that the cap's girth G exceeds
      `Mx = S / MP`, assert the whole of rule 2.6 at once: the cap is emitted as W + 1 cells with
      `W = max(2, ceil(G / Mx))`; every wedge's span is at or under Mx and strictly above `MP * S`,
      which is rule 2.6.2's proof measured rather than trusted; the centre disc's girth is at or
      under Mx; all W + 1 cells carry the Cap flag, sit in branch CourseCount - 1 and appear in no
      other branch; the branch COUNT is unchanged from the same fixture at a CH that gives no split,
      which pins rule 2.6.5 against inventing a course; the disc is the FIRST item in its branch,
      which pins the overlap consequence of rule 2.6.5; and the piece-length statistics of rule 9.3.1
      contain none of the W + 1 spans, which pins the amended rule 2.3.2a. Take the same fixture at
      MP = 0 and assert no split at all, which pins rule 2.6.1's reading of a threshold turned off.
  (g) THE BASE CASE, on `SkinEllipticalDomeNet` and at the default MP. Assert that no qualifying
      inner level is found, that the cap is emitted WHOLE with one cell and not refused, that
      `CapsOversized` is 1, that the Warning of rule 9.3.2 is raised naming the girth and the
      maximum, and that the cap's girth is pinned as a MEASUREMENT rather than as a bar, since it is
      a property of the fixture's own proportions. The check that matters most here is the negative
      one: no hole. Assert the plan area covered by cells still differs from the net's own plan area
      by less than one per cent, as (b) does for the ordinary dome.
  (h) THE COST of the split is counted with band splitting's, at check 12.9(c), because rule
      2.6.4(c) puts its levels into the same ascending list and under the same cap of 128.

12.3 THE FORCE-ALIGNED PATTERN (section 3).
  (a) The native line field on a BARREL, where the thrust runs one way everywhere, gives streamlines
      that agree with the barrel's own generators to within 5 degrees at every sampled face. That is
      the port's own bar and it does not reference the Python output, which rule 3.5.1 says it
      cannot. THE FIXTURE MUST CARRY FORCES. `SkinBarrelNet` today is a bare vertex-and-face tuple
      (Program.cs:8404-8422) built through the two-argument constructor, so it holds no rim and no
      member force, and this bar cannot be run on it at all. Rule 12.0 therefore requires a
      force-bearing form of the barrel: every edge running along the barrel, that is between
      (i, j) and (i + 1, j), carries a compression of 1 kN and every edge across it, between (i, j)
      and (i, j + 1), carries 0.1 kN, which is a one-way thrust stated as data rather than assumed.
      Under rule 3.2.7 the field then lies along the generators everywhere, and if it does not, the
      arithmetic of rules 3.2.5 to 3.2.9 was built wrong. On the SAME barrel with its force list
      removed, the field falls to the (1, 0) default of rule 3.2.8 on every face, the diagnostics say
      so by rule 1.3.6, and the component does not throw. The author must be able to tell a straight
      flow line from a defaulted one, and running the fixture both ways is what makes that
      distinction exist.
  (b) On every fixture, every head joint of every cell lies on a streamline to within a stated
      tolerance, and every bed edge lies on a level curve. That is the property the pattern exists
      for and it is the one that would silently not hold.
  (c) BOND: for every pair of vertically adjacent cells, the head joints of the upper do not
      coincide with the head joints of the lower, to within a tenth of a piece. That pins rule
      3.3.4.
  (d) UNIFORMITY: max piece length over min piece length is AT OR UNDER 2.5 on every fixture,
      measured over the non-Cap cells by rule 2.3.2a, against the 0.377 to 3.889 ratio of over 10
      his screenshot recorded. The bar is 2.5 and not 3 because the construction's own bound IS 3 and
      a check set at its own bound cannot fail meaningfully: rules 3.3.3 and 3.3.4 hold a gap between
      0.5 P_k and 1.5 P_k and a piece is two gaps, so a piece lies between P_k and 3 P_k. Setting the
      bar at 2.5 leaves the check room to detect a pattern drifting towards its own limit. Where a
      fixture measures between 2.5 and 3, the bar is re-pinned as a measurement with the reason
      written beside it rather than the engine being bent to reach it, and the Cap exclusion is
      asserted separately, because a cap left in the list would carry the ratio past 3 on any dome by
      itself.
  (e) INSERTION AND TERMINATION: a fanning fixture whose rows lengthen produces at least one
      insertion and a converging one at least one termination, each producing exactly one five- or
      three-sided cell, each counted in `skin.odd_cells`.
  (f) The pattern computes SYNCHRONOUSLY: the harness asserts no worker command named
      `pattern.armadillo_dual` is reachable from the component.

12.4 THE HEXAGON (section 4).
  (a) BARREL, whose rows are all one length. The bar is NOT byte identity and cannot be. The barrel's
      strip is 6.0 m exactly (Program.cs:8404-8422) and the honeycomb check runs at S 0.6
      (Program.cs:11536-11537), so rule 4.2.2 gives n = 7 centres, m = 14 columns and a pitch of
      6 / 14 = 0.4286 m against the shipped absolute 0.45 m: every column moves. Rule 4.2.5
      separately removes the vertex clamp the pinned clipped count of 36 was measuring
      (Program.cs:11548-11554), so that number moves too. What is asserted instead is what the rule
      actually claims: every row takes the SAME centre count and the SAME pitch; the pitch is within
      one rounding step of 0.75 S; adjacent rows' centres are offset by exactly half the in-row
      centre spacing; the interior cell's six corners sit at its own row's 2 / (3 m) and 1 / (3 m);
      and the plan filter drops ZERO cells. The 76 cells and 36 clipped are RE-MEASURED and re-pinned
      as new numbers, with the new numbers written into the check's own message, which is the
      discipline 12.4(g) asks for elsewhere. A byte-identity bar is available only on a fixture whose
      strip length is an exact multiple of 1.5 S at the S the check uses; if one is wanted, build it
      and say so in the rule rather than bending rule 4.2.2 to make the barrel fit.
  (b) DOME: no cell has a collapsed edge, meaning no two outline points within 1e-6 of each other IN
      PLAN after Dedupe, per axis in the studio's own form by rule 3.5.4(a), against the 26-of-161
      port measurement of section 4.1 defect 2.
  (c) DOME: no cell has more than twelve corners plus the trace vertices its two horizontal edges
      carry, and specifically no cell contains a whole row, which pins the crown lollipop out of
      existence.
  (d) DOME AND TWO-OCULUS: the count of cells with 5 corners plus 7 corners is non-zero, every one
      of them sits at a row where the CENTRE count changes, and none sits anywhere else. That asserts
      rule 4.3.1 in both directions. Corners here means setout corners, not the trace vertices the
      two horizontal edges carry, and the check must count them as such or it counts the mesh.
  (e) PLACEMENT: every odd cell's normalised position is within one column of t = 0.5 on a closed
      row, or at an end on an open strip, which pins rule 4.3.2.
  (f) THE SCAR IS GONE: on a closed row, the arc gap between the last column and the first, measured
      round the wrap, equals every other column gap to within 1e-9. That is the direct measurement
      of defect 3.
  (g) LOSSES: on the two-oculus and serpentine fixtures the withheld fraction is MEASURED and pinned
      as a measurement, and no per-cent bar is carried over. The 26 to 49 and 38 to 62 per cent of
      section 4.1 were quoted against prose reconstructions, so there is no honest BEFORE for any
      after to be compared with until rule 12.0's fixtures exist. The order of work is therefore:
      build the two fixtures; measure the SHIPPED honeycomb on them and record that as the before;
      measure the reworked one; pin both figures with the improvement stated between them. A bar may
      be set once the before exists and not before, which is the discipline the harness already uses
      for the two-peak net (Program.cs:10191-10202).

12.5 THE SURFACE OUTPUT (section 5).
  (a) The Brep route is proved FIRST, before anything else in section 5 is built: a standalone check
      that builds one loft from two known polylines and asserts a valid single-face Brep comes back.
      Every rule in 5.2 depends on RhinoCommon behaviour this repository has never exercised.
  (b) Every cell in every fixture yields a Brep; `skin.surface_failed` is zero everywhere. That
      includes every three-, five- and seven-cornered cell, which take route 5.2.3(e); without that
      route this check and 12.4(d) cannot both pass, and the pair of them is the reason route (e)
      exists.
  (c) Each Brep's area is within 2 per cent of the plan area of its cell divided by the cosine of
      the cell's mean surface slope, which is a cheap independent check that the face is the cell's
      own surface and not something else.
  (d) TREE ALIGNMENT: branch count, branch paths and per-branch item counts are identical between
      Cells and Surface on every fixture, including a fixture with an empty course, which pins rule
      5.3.3, and including the split-cap fixture of check 12.2(f), whose top branch holds W + 1 items
      in both trees. On that fixture assert further that each WEDGE came back as a single-face Brep,
      which is route 5.2.3(a), and that only the centre disc is a multi-face fan, which is route
      5.2.3(d). A wedge silently taking the cap's fan route would pass every other check here.
  (e) A deliberately degenerate cell, injected, produces a NULL in the Surface slot rather than a
      missing item, and the counts still align.
  (f) SEAM DRIFT: on the dome at 96 a ring, the plan distance between consecutive courses' seams is
      under 1e-6 m, against the up to 0.098 m the quantised seam gives. That is the direct
      measurement of section 4.1 defect 5 and of rule 4.2.6.

12.6 PIECE SIZE, BOTH ENDS (section 6).
  (a) On the barrel, whose open strips have end pieces of exactly half a pitch on odd courses, that
      is 0.3 m at S 0.6 and CH 0.5, which the harness pins in those words (Program.cs:9762-9771): MP
      at 0.5 merges those end pieces and MP at 0.3 does not. The values are 0.5 and 0.3 and NOT the
      0.6 an earlier draft named, for two reasons that both have to hold at once. Rule 6.4 caps MP at
      0.5 and clamps anything above it with a Warning, so 0.6 never reaches the engine and arrives as
      0.5; and at MP 0.5 the threshold is exactly 0.3, which a strict "under" would leave undecided
      on the one fixture the check names, so rule 6.1's comparison is "at or under" within 1e-9 and
      the boundary is decided rather than left to the last bit of a double. At MP 0.3 the threshold
      is 0.18 and the 0.3 end piece is plainly above it, so the two bars separate.
  (b) After merging, no cell's span is under MP * S anywhere on any fixture, EXCEPT a course's only
      piece, which rule 6.5 protects, and except a merged pair whose union is still under the
      threshold, which rule 6.3's single pass allows deliberately. Both exceptions are counted and
      the counts are reported in `skin.merged_pieces`' Context. Stated without the exceptions this
      check is false against two rules that were written on purpose.
  (c) TERMINATION: the merged pattern is identical whether the pass is run once or twice, which
      pins rule 6.3 against a cascade.
  (d) A course holding exactly ONE piece in total keeps it however short, which pins rule 6.5 in rule
      6.5's own words. Not "a course with exactly one short piece", which would wrongly protect a
      single short piece sitting among many long ones and is the opposite of what the rule says.
  (e) MP at 0 changes nothing, at either end: no piece is merged and no crown cap is split, which
      pins rule 6.0's reading of a single threshold turned off. MP at 0.9 clamps to 0.5 with the
      Warning, and MP at -1 clamps to 0 with the Warning and behaves exactly as MP at 0, which pins
      rule 9.5's answer for a negative value.
  (f) THE ZERO-AREA CENTROID of rule 6.8: on a fixture where two courses share a joint, so that three
      trace corners lie collinear exactly ON it, no cell is dropped as degenerate. Take the same
      fixture with the guard removed and assert the drop count is non-zero, so the check measures the
      guard and not merely the fixture's good luck.
  (g) THE STUDIO'S OWN TEST, which is what rule 3.5.4 exists for: no surviving outline anywhere holds
      TWO points within 1e-6 of each other IN PLAN, compared per axis over the whole ring in the
      studio's own form (tessellation.py:632-636), and no outline vertex lies strictly on a
      non-adjacent edge of its own ring (tessellation.py:648-654). A three-dimensional distance check
      here would pass while the studio rejected the file, which is the gap the rule was written to
      close.
  (h) ONE PORT, BOTH ENDS, which is the measurement rule 6.0 exists for. On the split-cap fixture of
      check 12.2(f), vary MP alone and assert the wedge count moves as `ceil(G / (S / MP))` does: a
      smaller MP gives a larger maximum and fewer wedges, and MP at the cap of 0.5 gives the most.
      That is the direct measurement that the maximum is the same number read from the other end and
      not a second constant hidden in the cap code, which is the failure this check exists to catch.

12.7 BUILD ORDER (section 7).
  (a) Within every branch, |mid-span| is non-decreasing, and the first two cells lie on OPPOSITE
      SIDES of the seam. That second bar is only reachable because of rule 7.1.1: on a closed course
      `CourseSpans` emits every span non-negative (SkinPatterns.cs:1920-1927), so without the
      re-centring no cell ever has a negative mid and the bar fails on every dome fixture. Assert it
      on a closed course and on an open strip, since the two reach it by different routes. On a
      closed course additionally assert that every U0 and U1 lies in (-L / 2, +L / 2], which is the
      direct measurement of rule 7.1.1, and re-pin the moved U values as new measurements, since they
      are what changes in the sidecar.
  (b) The order pins are taken in ARRIVAL order and never re-sorted, the discipline the existing
      course checks already keep (Program.cs:9774-9776).
  (c) THE FALSE PORT SENTENCE IS GONE, which is the operative half of Param's ruling of 2026-09-01
      and therefore a check and not a nicety: a string check that "the studio's build sequence within
      a run" appears nowhere in SkinComponents.cs, read and not run by the
      `ValidateExportDefaultTessellation` convention. On the same read, assert the replacement text
      of rule 7.5 carries its two load-bearing clauses, the one saying the studio re-sorts on import
      and the one saying the courses are a running bond so item k of one branch is not above item k
      of the next, since a text that dropped either would leave the author with a different false
      belief in place of the old one.

12.8 BAND SPLITTING (section 8).
  (a) TWO-HUMP BARREL and SPLIT-AND-DEATH, the two nets a count test cannot see
      (Program.cs:10379, :10400): today each refuses exactly one band whole. After splitting, each
      must emit cells at every course including the one previously refused, `TransitionBands` counts
      only the residual, and the refused interval named in the diagnostics is at most CH / 64 wide.
  (b) The plan projections stay pairwise disjoint and simple through the split, by
      `RequireDisjointSimplePlans`, which is the whole reason the refusal existed.
  (c) COURSE COUNT IS UNCHANGED by splitting on every fixture, which pins rule 8.2.4 against
      inventing studio stages.
  (d) A BARREL under the rim field, whose ridge is a cut locus, emits cells along the whole ridge
      with no hole; the shipped rule would leave one course's worth of hole there, so measure both.
  (e) The honeycomb's refusal is LOCAL: on a two-sided fixture with a transition on one side only,
      the other side's cells are unaffected, which pins rule 8.2.7 against the global
      `SpansTransition`.

12.9 COST.
  (a) The plan filter's cost check on the annular vault at 96 a ring (Program.cs:826-841) stays and
      its bound is re-measured, not relaxed, since rule 3.5.3 makes cells carry more corners.
  (b) The field computation is measured separately and asserted under a tenth of the filter's time
      on the same net, so nobody mistakes the field for the expensive part.
  (c) BAND SPLITTING'S OWN COST, which rule 8.2.3a states as up to 2^depth - 1 new levels per refused
      band. On the two-hump barrel and split-and-death nets, count the levels the split actually
      introduces and the number of `TraceAll` passes it costs, and assert both against rule 8.2.3b's
      cap of 128 levels. Count the CROWN CAP's levels in the same total on the split-cap fixture of
      check 12.2(f), since rule 2.6.4(c) puts them into the same ascending list and under the same
      cap: up to six from the bisection of rule 2.6.3 plus the ring's mid and its inner curve. A pathological net that reaches the cap must return with the diagnostics
      saying so and must not run long, which is the behaviour under test rather than the timing.

12.10 PORTS AND IDENTITY.
  (a) The pin at Program.cs:100-102 becomes inputs
      {Result, Pattern, Size, Course Height, Min Piece} and outputs {Result, Cells, Surface} IF he
      takes the RES output of rule 9.4, or {Cells, Surface} if he declines it. The input half is
      settled and may be written now, since rule 9.5's port is ruled; only the output half waits on
      section 13.2 item 1, and writing that half either way now would pin a decision that is his to
      make.
  (b) Export's pin becomes inputs
      {Result, Cells, Courses, Column Radius, Name, Path, Studio, Live, Write}, with Path
      immediately AFTER Name by the ruling of section 10.1.
  (c) The Skin GUID pin, the dead Armadillo Dual GUID, the Pattern value list, the component count
      and the icon map all stay as they are (Program.cs:310, :860-873).
  (d) IF HE TAKES THE RES OUTPUT: a check that Skin's RES output is a ResultParam at index 0, and
      that its Result carries at least one diagnostic whose source is "Skin". IF HE DECLINES IT:
      a check that Skin registers no ResultParam output and that the Remark of rule 9.3.5 carries the
      residual content, since that Remark then becomes the only place the numbers live. One of these
      two is written, never both.
  (e) EXPORT'S BRANCH READING: a tree of three branches with two cells each produces courses
      0, 0, 1, 1, 2, 2 in the sidecar; a flat list with a Courses list produces that list; both
      together produce the Error of rule 10.2.3 and no file.

## 13. What is settled, and what still needs Param

### 13.1 Settled, and by whom

Six of the nine questions the last draft carried are answered. Each entry says who answered it, what
the answer is, where it now lives in the spec, and what alternative was rejected, because a rejected
alternative and its reason are worth more later than the ruling itself.

1. THE BUILD ORDER STANDS. PARAM'S RULING, 2026-09-01. He made the original ruling believing the
   seam-outward order fed the studio's build sequence. He was shown that tessellation.py:473 re-sorts
   every tessellation by course and by each cell's angle on import, so the order never reaches the
   studio, and that it does still decide which cell survives an overlap. He kept it on that basis.
   What the order serves is therefore the GRASSHOPPER AUTHOR and the OVERLAP FILTER, and the filter's
   rule is first-emitted-wins, which with seam-outward emission makes the seam stable and pushes the
   losses out to the edges of each course, symmetrically. Rule 7.4 states it and rule 7.5 corrects
   the port sentence that claimed otherwise, which is the operative half of the ruling; check 12.7(c)
   pins the correction. REJECTED: reverting to today's order along the course, which would move the
   survivors away from the seam for no gain.
2. THE CROWN CAP SPLITS WHEN OVERSIZED. PARAM'S RULING, 2026-09-01. Above the maximum piece size the
   cap becomes a ring of wedges about a smaller centre disc, the wedge count chosen so each wedge
   falls under the maximum, and ONE threshold governs both ends of the size question. Section 2.6
   states the whole of it: rule 2.6.2 gives the count as `W = max(2, ceil(G / Mx))` and proves no
   wedge can fall under the minimum; rule 2.6.3 finds the inner boundary by bracketed bisection;
   rule 2.6.5 states the tree consequence, that the cap's one item becomes W + 1 items in the SAME
   branch and the branch count does not move; and rule 2.6.6 answers the residual case, that the
   construction neither recurses, since one bracketed step already bounds the disc, nor refuses,
   since a refusal at the crown is a hole at the crown. REJECTED: leaving the cap unbounded and the
   remedy to the author, which is rule 2.3.4's earlier text, kept there as the author's remedy but no
   longer as the whole answer. STILL OPEN under it: the base case, at 13.2 item 4.
3. WHICH FAMILY CARRIES THE CONTINUOUS JOINT. MINE, the controller's, at rule 3.3.4a. The masonry
   reading stands: the BEDS are the continuous family and they are the section 1 level curves, and
   the head joints are the native streamlines generated at S / 2 with alternate parity per course, so
   every joint lies on a streamline, the pattern still reads as his sinusoidal curves, and the bond
   stays a running bond. REJECTED: literal uninterrupted strips running rim to crown, which is the
   other reading of his own sentence, because a joint continuous from rim to crown is a crack line up
   the form. Nothing crosses it, so nothing closes it. The two look completely different and both are
   buildable, which is why the rejected one is recorded rather than dropped.
4. THE HALF-PITCH STAGGER IS KEPT. MINE, the controller's, at rule 5.4.3. The running bond
   deliberately offsets cell 0 of odd courses, and the bond is not sacrificed to the convenience of a
   tree mapping. What the spec owes him instead is the consequence stated plainly, and rule 5.4.3 and
   the port text of rule 7.5 now carry it: the Surface tree is aligned with Cells item for item, but
   item k of one branch does NOT sit above item k of the branch below, and on a closed course the two
   branches may not even hold the same number of items. An author who wants the piece above a given
   piece finds it by overlapping signed arc, not by index. REJECTED, and recorded: a suppressible
   stagger, which is a one-line option and would make the mapping index against index at the cost of
   the bond.
5. MIN PIECE IS A PORT, AND IT SETS THE MAXIMUM TOO. MINE, the controller's, from his word
   "adjustable", at rules 6.0 and 9.5. It is a number input at slot 4, a pure fraction of Size with
   no unit of its own, default 1/3, floored at 0 and capped at 0.5; zero turns BOTH ends off and a
   negative clamps to zero with a Warning rather than failing the solve. The minimum piece is
   `MP * S` and the maximum is `S / MP`, which is the same number read from the other end, so the
   threshold is named once and used twice exactly as his crown-cap ruling requires. REJECTED: a
   second port for the maximum, which would let an author set a minimum above his own maximum; and a
   fixed constant with no port, which would not honour "adjustable".
6. PATH'S SLOT IN EXPORT. MINE, the controller's, at section 10.1, and it stays marked as mine. Path
   sits IMMEDIATELY AFTER Name, because the name and the folder together decide the file, and because
   putting it there leaves every port he did name in the relative order he named it in. The order is
   {Result, Cells, Courses, Column Radius, Name, Path, Studio, Live, Write} and check 12.10(b) pins
   it. REJECTED: Path immediately BEFORE Name, which an earlier draft carried and which moves Name
   one slot from where his own sentence had it; and dropping Path, which he did not intend, since
   Export cannot write a file without it.

### 13.2 Still open, and each one is genuinely his

1. THREE OUTPUTS OR TWO. The design input put an option to him and he has not answered it, so rule
   9.4.1 marks it as mine and rule 9.1 carries both port lists. The choice: THREE outputs, Result
   RES first with the skin.* diagnostic entries of rule 9.3.3 written into it, so the numbers live
   where every other component's numbers live and Diagnose reads them with the rest; or TWO outputs,
   Cells and Surface, with the numbers living only on the message chin of rule 9.3.1 and in the
   Remark of rule 9.3.5, which is literally what his own sentence asked for, "Remove Diagnositcs too,
   leave the info bubble that pops up as enough". The Remark of rule 9.3.5 exists either way, so
   declining the output loses him nothing he can read and loses him the ability to wire the numbers
   into a panel, which rule 9.3.4 states. Only rule 9.4, the port pin at 12.10(a) and the RES checks
   at 12.10(d) turn on the answer.
2. HIS FIRST CAUSE OF THE SETOUT DISTORTION IS BEING DEFERRED, and he should see that plainly rather
   than infer it. His ruling reads "The setout distortion has TWO causes and both must be addressed:
   the arc-length RATIO mapping, and SEPARATELY the seam quantised to a trace vertex". This round
   answers the SECOND, by rule 4.2.6, and defers the FIRST, by rule 1.8.4. The reason is in rule
   1.8.4: replacing `BandCell`'s proportional mapping properly means marching each joint along the
   field gradient, which is a second advection engine stacked on the one section 3 already
   introduces in this wave, and it adds corners to every courses cell, which pushes them onto the
   Surface output's fan route and makes the plan filter dearer. The obvious cheap replacement,
   mapping to the nearest point in plan, is refused with its counter-example at rule 1.8.2. Rule
   1.8.5 measures the size of the residual on every fixture so the deferral is quantified rather than
   asserted. If he wants both causes closed in this round, section 3 or section 5 has to come out of
   it to pay for it, and he should say which.
3. A BOUNDED RESIDUAL HOLE AT A TOPOLOGY TRANSITION, OR AN EXACT SOLVE. His carried ruling asks for
   "the full band-splitting answer, REPLACING the present refusal", and rule 8.2.6 does not replace
   the refusal; it keeps it as the base case at depth six. That leaves a hole of up to CH / 64 along
   a transition, which is 5.5 mm at the shipped CH of 0.35 m and 7.8 mm at CH 0.5. The alternative is
   an explicit critical-point solve, which is exact and needs a saddle classifier the engine does not
   have and this wave cannot carry beside everything else in it. A bounded 5.5 mm hole or a later
   wave for the exact answer: his call, and rule 8.2.6 marks the departure as mine until he makes it.

   ERRATUM, 2026-09-04. THIS ITEM IS CLOSED, and by neither of the two answers it offered him. It is
   closed by the CLOSER BAND of the seam spec of 2026-09-04: the refused interval is covered by
   stones of its own species, built from the surface's own level sets at the two refused levels
   rather than from a correspondence between the two course families, cut along the seam the seed
   identity of that spec's rule 1.1 recovers, and emitted as ordinary cells at the band's own course.
   There is no residual hole left to bound and no critical-point solve was needed. Measured on
   Param's own crown arch, the refused interval's own plan area comes back covered to 99.95 per cent
   at S 0.10 and CH 0.30 and to 99.91 per cent at S 0.17 and CH 0.375, and on the two-hump barrel to
   92.87 per cent. The wording goes with the hole: what read "Transition bands skipped" now reads
   "1 seam was CLOSED with N stones between d=a and d=b", and it is a Remark and not a Warning.
   What is left of this item is a smaller and better-stated question, carried in the seam spec's own
   honesty bounds rather than here: where the slab PINCHES, as the two-hump barrel's does at each of
   its three ridge dips, the two families bound it with ENDS rather than with sides and no ribbon
   between two curves reaches into the lune. That is the 7.13 per cent.
4. THE CAP THAT CANNOT BE SPLIT, which is the honest residue of his own crown-cap ruling and not a
   reopening of it. The split of section 2.6 needs an inner level whose curve is under the maximum,
   and on a dome whose plan is not a circle there may be none: the cut locus is a segment rather than
   a point, so the level curves near the top shrink onto that segment and the girth at the top cut
   stays of the order of twice its length however fine CH is made. Rule 2.6.6 EMITS such a cap whole
   and oversized with a Warning naming its girth against the maximum, on the ground that a stone he
   can see and measure beats a hole he cannot fill. The alternative is to REFUSE it, which leaves the
   crown uncovered and is what section 8's own base case does at a transition, so refusing here would
   at least be consistent with that. His call; check 12.2(g) measures the case either way on
   `SkinEllipticalDomeNet`.
