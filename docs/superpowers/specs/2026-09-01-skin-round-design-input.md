# Skin buildability round: Param's rulings, verbatim, with the reading taken from them

Design input for the skin round, which he has placed AFTER the columns. His words are quoted
exactly; anything outside a quote is the reading taken from them and is subordinate to the quote.

## 1. The courses are cut at constant world Z, and they should not be

> "I am also noticing a problem with the cutting of the skin and this should be not too hard of a
> problme to fix. the obvious reason to be is that it is cutting the banding directly from Z, is is
> wrong, it should be cutting in planes tangential to the curvature of the mesh. so it is the Z axis
> from each banding location across the mesh not just a z cut"

He is correct about the mechanism, and it is explicit in the engine: `Courses` bands the surface at
heights `zMin + r * CH` and `BuildCharts` cuts at the same constant-Z levels, so a course boundary is
a horizontal slice through the vault.

The consequence is geometric and unavoidable. For a surface at slope angle theta from horizontal, a
rise of CH corresponds to a distance along the surface of CH / sin(theta). At the springing, where
the surface is near vertical, that is CH. At 45 degrees it is 1.41 CH. At 10 degrees it is 5.8 CH,
and at 5 degrees it is 11.5 CH. At the crown of an arch, where the surface is horizontal, it diverges.
With the shipped CH of 0.35 m, a course crossing a 10 degree crown region is about 2 m of masonry
and one crossing a 5 degree region about 4 m, which is what his screenshot shows: courses tight at
the flanks and enormously stretched over the crown.

WHAT HE IS ASKING FOR, stated structurally: course boundaries spaced equally along the SURFACE
rather than in height, with each bed running across the local direction of steepest ascent rather
than lying horizontal. That is what a mason does, and CH then means the physical bed-to-bed distance
of the masonry rather than a rise, which is the more useful meaning of the parameter.

THE FORK IS RULED. He has chosen the PROPER form, the geodesic distance from the rim, and a CROWN
CAP PIECE where the courses converge:

> Course cut: "Distance from the rim (Recommended)"; Crown: "A crown cap piece (Recommended)"

So the round replaces the scalar the tracer cuts, CH becomes the true bed-to-bed spacing of the
masonry, and the last course closes with a single cap piece, the keystone or oculus a real vault has,
rather than running the lattice into a converging point. That cap ruling also settles, in the same
stroke, the crown behaviour that has been costing cells in the hexagonal pattern: the honeycomb stops
being asked to tile a domain that shrinks to nothing.

The two forms are recorded below as they were put to him, because the rejected one names what the
chosen one must be measured against.

- The CHEAP form, NOT CHOSEN. Keep the constant-Z cut but choose the cut heights so the AVERAGE along-surface
  spacing between consecutive courses is CH, solving one scalar per course instead of stepping the
  height uniformly. This keeps every part of the tracer, the nesting, the correspondence and the plan
  guarantee that six adversarial rounds hardened, and it removes the stretching at the crown. It
  cannot make the bed spacing uniform ALONG a course, because on a vault a single horizontal plane is
  steeper at the flanks than at the crown, so it corrects the average and not the variation.
- The PROPER form. Replace the scalar the tracer cuts: instead of level sets of z, trace level sets of
  the geodesic DISTANCE FROM THE BASE RIM, computed once per vertex over the mesh. The tracer is
  already field-agnostic, it cuts level sets of a piecewise-linear scalar on triangles, so the
  exactness argument, the nesting depth rule and the correspondence machinery all carry across
  unchanged. This gives genuinely uniform bed spacing everywhere and beds that run across the flow by
  construction. The new work is the distance field itself and the behaviour where advancing fronts
  MEET (the cut locus, typically at a crown or between two springings), which is a real topology event
  the existing transition machinery would refuse unless it is given a rule of its own.

His remark that it "should be not too hard" is true of the cheap form and not of the proper one. The
proper form is the right answer for a mason's skin and it is a foundation change, though a much
smaller one than it sounds because it reuses the hardened tracer rather than replacing it.

## 1a. The force-aligned pattern is reworked onto the same setout, not patched

> "also with the force aligned cut for tesselation i think we need to rework but again not too hard to
> solve. You can already see we are calculating those force bandings with the sine shapped curves
> going up the form, these should be where we fit the tesselation pattern, not cutting through it
> randomly. We need to be strategic, so we should find a way to create amazing voussoirs in that. I
> think the tesselation pattern as it is, is quite ugly and we should avoid that messiess"

He is describing the engine's own two halves working against each other. The force-aligned pattern
computes a line field from the thrust, advects STREAMLINES along it (the sinusoidal curves he can see
running up the form, which the component already emits on its Flowlines output), and then throws that
structure away: the cells come from a geodesic VORONOI of a seed set, whose boundaries are the
bisectors between seeds and therefore bear no relation to the streamlines they cross. The flow is
computed and then ignored, which is exactly why the result reads as random and, in his word, ugly.

THE REWORK, and it is a simplification rather than an addition. All three patterns become the same
construction on different fields, which the tracer already supports because it cuts level sets of any
piecewise-linear scalar carried on the triangles:

- courses: level sets of geodesic distance from the rim, divided along their length
- hexagonal: the same chart, a honeycomb lattice laid on it
- force aligned: one family taken from the thrust flow, the other from its perpendicular, cells being
  the quads between two consecutive curves of each family

So the Voronoi and the whole worker round trip go away, pattern 2 becomes native like the other two,
and it inherits every guarantee six adversarial rounds bought: exact level curves through triangulated
faces, nesting depth, correspondence by bijection, and the enforced plan validity. The streamline
family is not uniformly spaced by nature, since flow converges where force concentrates, so the rule
must INSERT a streamline where a strip grows past the size bound and TERMINATE one where it narrows
below it, which is what a mason does when adding or dropping a course, and is also how the pattern
stays uniform while remaining force-aligned.

ONE QUESTION IS HIS TO RULE and is put to him separately: which family carries the CONTINUOUS joint.
Masonry logic says the continuous bed joints should run ACROSS the thrust, so the thrust closes them
rather than sliding along them, which would make the flow lines the staggered head joints. His
sentence reads the other way, with the pieces sitting BETWEEN adjacent flow lines in strips running up
the form. Both are buildable and they look completely different. The engine's own present comment
claims the Voronoi makes "every joint run across the thrust instead of along it", so the existing
intent is the masonry one, but it is achieved by a construction he has rejected.

## 2. Skin outputs a surface as well as a polyline

> "one thing worth adding to the skin component is that it outputs a surface too, it actually can be
> really difficult for grasshopper to turn polylines with arcs into surfaces, so i would like that
> added with the same tree structure. I presume the tree structure for that is that it takes each row
> as a branch and starts with the very corner of one side each time so that they map very easily, if
> not i can reorganise the branching later if it becomes too difficult. I would typically sort list
> around a circle and set the circle seam facing the corner of a side."

A surface per cell, branched exactly as Cells is, one branch per course. Each cell's outline is to
begin at a consistent corner so the surfaces map predictably, which is the same instinct as setting a
circle's seam to face a corner before sorting around it. He is content to reorganise the branching
later if the natural one proves awkward.

Note the dependency: the outline's starting point today inherits the seam, which is pinned to a mesh
vertex and shifts with the mesh, and the sixth adversarial round measured that when the seam drifts
more than about two thirds of a piece between courses the cells shear. So his consistent-corner
requirement and the seam rule the round already owes are one problem, and are cheaper solved together.

## 3. Carried into this round from earlier rulings

- Minimum piece size: MERGE INTO THE NEIGHBOUR, default a third of the target size, adjustable.
- Build sequence within a course: FROM THE SEAM OUTWARD.
- Topology transitions: the full band-splitting answer, replacing the present refusal.
- The setout distortion has TWO causes and both must be addressed: the arc-length RATIO mapping, and
  SEPARATELY the seam quantised to a trace vertex, the latter measured on concentric similar polygons
  where the ratio is exactly right and the cells shear regardless.
- The spurious drop where two courses touch: a candidate interior point can be the centroid of three
  collinear trace corners lying exactly ON the joint, where the containment test is a coin flip. Named
  fix: refuse a candidate centroid whose triangle has no area.
- Build the two-oculus and serpentine fixtures ONCE, in the repository, and measure there; they have
  been prose reconstructions differing between rounds.

## 4. Sequence

> "we will work on this after the columns and I will review the tesselation and rest of the work while
> that happens"
