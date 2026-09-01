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

THE FORK, which needs his ruling before the round is specced:

- The CHEAP form. Keep the constant-Z cut but choose the cut heights so the AVERAGE along-surface
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
