# The skin thickens by OFFSET, not by extrusion

Written 2026-09-03 after Param read the honeycomb blocks on his own arch and saw what they were.
This document supersedes the thickness rules of docs/superpowers/specs/2026-09-02-skin-thickness-input.md
on the two points it names, and leaves the rest of that spec standing.

## 1. What was built, and why it was wrong

The Thickness input shipped with a second port, "Along Normal" (N). With it OFF the whole cell was
translated by (0, 0, Th); with it ON the whole cell was translated along a single Newell normal of
that one cell's own outline (SkinComponents.ThicknessOffset). BOTH ARE EXTRUSIONS. The toggle
named the direction of an extrusion, when what was asked for was the choice between an OFFSET
SURFACE and an extrusion. In Param's words of 2026-09-03: "I meant with normal toggle that we
switch between offset surface and extrude and that is the distinction."

The consequences are three, and all three are visible on his arch.

1. A cell translated one way does not meet its neighbour, which was translated another way. The
   skin loses the connectivity the original ruling asked it to keep, and the blocks CLASH where
   the surface turns: "the geometry is clashing when certain directions meet".

2. On a steep part of the vault a vertical translation is nearly tangential, so the block is a
   sheared sliver carrying almost no thickness perpendicular to the surface, which is the only
   direction in which a voussoir's thickness means anything.

3. It REFUSES CELLS. A side wall is built from the quad (a, b, b + offset, a + offset) per outline
   edge. Where the edge a to b runs vertical and the offset is also vertical, all four corners lie
   on one line, Brep.CreateFromCornerPoints has no quad to make, and the cell is refused. His
   springing is steep and its head joints run near-vertical, so an unknown share of the 148
   non-closing cells on his force-aligned run are this and not a thickener defect at all.

## 2. The recipe, which the studio already carries

bench/studio/blocks.py and bench/studio/voussoirs.py have solved this. Two parts:

    normals = blocks.vertex_normals(vertices, faces)   # area-weighted unit normal PER VERTEX
    ...
    p, n = vertices[corner], normals[corner]           # each corner moves along ITS OWN normal
    block_vertices.append([p[0] + n[0]*half*sign, ...])

The normal is a property of the POINT and not of the cell. Two blocks that share a corner move
that corner identically, so they cannot gap and cannot clash. That is the whole of it.

Area weighting is had for free by summing UNNORMALISED cross products, since a raw cross product
is twice the triangle's area (blocks.py:36-46). A degenerate fan falls back to (0, 0, 1).

## 3. What this engine must add, and the one thing the studio did not have to solve

The studio offsets MESH VERTICES. This engine offsets OUTLINE POINTS, and an outline point is
almost never a net vertex: it lies on a traced level curve, which crosses faces. So the normal
must be evaluated at an arbitrary point on the net.

RULE 1. THE NORMAL FIELD. Compute area-weighted unit vertex normals over the net once per solve,
by the blocks.py arithmetic above. Cache it on the net beside the level field; it is the same
shape of data and has the same lifetime.

RULE 2. THE NORMAL AT A POINT. Find the face under the point (the engine already has FaceUnder and
LiftPlanPoint for the cap's apex) and return the BARYCENTRIC interpolation of that face's vertex
normals, renormalised. Fall back to (0, 0, 1) where no face is found or the interpolated vector is
shorter than 1e-12.

RULE 3. WHY THAT IS ENOUGH FOR THE WELD, and it is worth stating because it is the whole point.
Interpolated vertex normals are CONTINUOUS ACROSS A FACE EDGE: along a shared edge both faces
interpolate the same two vertex normals with the same weights. So the normal is a continuous
function of the point alone, independent of which face the lookup happened to pick, and two cells
that share a corner offset it to the same place whether or not they agree about its face. No
weld pass, no tolerance, no shared-corner table.

RULE 4. SIGN AND SIDE. Param's ruling of 2026-09-03: SIGNED, ONE SIDE ONLY. A positive Thickness
builds outward along the normal and a negative one builds inward, so the solved surface is the
intrados or the extrados of the skin and never its middle. The studio centres its blocks instead
(half each side); that is NOT taken here, and the reason it was offered is recorded so the choice
is not relitigated: a thrust surface running through the middle of the stone is the structurally
truer reading, and he wants the solved surface to be a face he can build to.

RULE 5. THE PORT. The existing input keeps its INDEX, so no archived wire moves, and is renamed:

    name        "Offset"
    nickname    "OF"
    default     TRUE
    True        offset surface: every outline point moves along the surface normal AT THAT POINT,
                so cells that share a corner stay welded and the skin keeps its connectivity.
    False       extrude: the whole cell is translated by (0, 0, Th), which leaves gaps where cells
                meet and copies a vertical outline edge onto itself, but is a simpler solid.

The old True branch, a whole-cell translation along the cell's own Newell normal, is DELETED. It
gaps like an extrusion and ignores the point normals like an extrusion, so it is strictly worse
than both survivors and nothing should be built with it.

The default flips from False to True. Param's canvas carries a toggle wired to this port reading
False, so he flips it once by hand; a component he drops fresh gets the offset surface.

## 4. What must be checked, and each check proved able to fail

1. THE WELD. Two adjacent cells sharing a corner offset that corner to the SAME point, to 1e-12.
   This is the check the whole change exists for; without it nothing here is verified. Build it on
   a curved fixture where the two cells' own Newell normals genuinely differ, or it proves nothing.
2. THE VERTICAL EDGE. A cell with a vertical outline edge on a steep part of the net thickens into
   a valid solid under Offset ON, where under Offset OFF it is refused. Count both.
3. THE SIGN. A negative Thickness mirrors a positive one about the solved surface, point for point.
4. NO REGRESSION IN THE EXTRUDE BRANCH. Offset OFF reproduces today's (0, 0, Th) translation
   exactly, so the change is additive for anyone who wants the old solid.
5. Th = 0 still returns the IDENTICAL Brep reference CellSurface built, untouched. That fast path
   is what the "byte-identical at Th = 0" ruling rests on and it must not become a copy.
6. THE NORMAL FIELD ITSELF. Area weighting is real: a vertex shared by one large and one small
   face leans toward the large one. Pin it against a hand-computed value on a two-triangle fixture.

The closedness of a Brep needs RhinoCommon's native core, which this harness deliberately does not
launch. scripts/rhino_skin_surface.py carries that half and MUST gain an Offset-ON case: it has
never thickened a loft-route cell at all, which is why this defect class reached Param's screen.

## 5. ERRATUM, 2026-09-04

Written after the change was built and reviewed, and after the harness measured what the document
had only argued. Two points of the text above are wrong and are corrected here rather than edited
away, so that the reasoning that produced them stays legible.

1. SECTION 1 POINT 3 CLAIMS A REACH IT DOES NOT HAVE. The mechanism it describes is real geometry:
where an outline edge runs vertical and the offset is vertical too, the four corners of that side
wall lie on one line, Brep.CreateFromCornerPoints has no quad to make, and the cell is refused.
That much is asserted on hand-written corners in tests/native_smoke and goes red when the predicate
is broken. What the section then guesses, that an unknown share of the 148 non-closing cells on
Param's force-aligned run are this and not a thickener defect, IS REFUTED BY MEASUREMENT.

2. THE NUMBERS. At Th 0.29, his own thickness, the count of cells carrying an annihilated wall is
ZERO under the extrude branch and ZERO under the offset branch on every fixture available: the
force-aligned barrel, 97 cells; Param's own net in courses at S 0.17 and CH 0.375, 1032 cells; his
own net force-aligned, 71 cells; and a vault built for this question alone, standing on exactly
vertical walls, 188 cells. Not one cell anywhere is refused by the vertical-edge mechanism, so the
offset branch cannot reduce a count that was never above zero.

3. WHY, AND IT GENERALISES. Annihilation is an EXACT collinearity. A merely steep edge leaves a
sliver quad with real area, which Rhino builds without complaint at the 1e-9 the call is made with:
on the walled vault the head joints come within 1e-5 rad of vertical without reaching it, leaving a
wall area of about 6e-7. And an exactly vertical outline edge cannot arise on a height-field net at
all except on a plan-degenerate wall, because two distinct surface points would have to share one
plan position. The tightest walls the harness can find are not vertical edges but SHORT ones: the
least wall area on the force-aligned run, 2.1e-7, is 0.5 times an outline edge of 1.5 microns times
Th, and the engine's own weld tolerance at emission is 1e-6, so those corners survive it by a hair.

4. WHERE THE 148 GO. They remain attributed to the loft-route thickening, which only Rhino can
settle. A lofted bottom face whose boundary is not the outline's straight chords cannot join the
wall quads built on those chords at the 1e-6 the join is asked for, and that would refuse every
cell of that route rather than a scattering, which fits 148 of 262 far better than any vertical
edge does. scripts/rhino_skin_surface.py 12.5(i) is where the count is taken.

5. THE CHECK SAYS SO. Section 4 check 2's own claim, a cell refused under Offset OFF and built
under Offset ON, is written and run in tests/native_smoke as a DEFERRED assertion with its owner
named, rather than dressed as a pass. The slot that carries it now claims the mechanism and the
one-way guard, which is what it enforces, and nothing more.

6. RULE 2 IS AMENDED. Off the mesh in plan the answer is no longer (0, 0, 1). It is the NEAREST
face's own, found by plan centroid and evaluated at the point, which is the branch the sibling
function LevelAt has carried all along. The old text fired on 172 of the 8870 cell corners of
Param's own crown arch: a traced level curve runs along the net's own boundary edges, and the
plan-containment test claims a boundary point for a face only about half the time, so those corners
took a VERTICAL thickness direction at the steep rim, which is exactly the defect this document
exists to remove. (0, 0, 1) survives only where there is no usable face to read at all, meaning a
net with no faces, a face whose plan area is below the 1e-15 LevelAt refuses to divide by on the
same triangle, or an interpolated vector shorter than 1e-12.

7. RULE 3 SURVIVES THE AMENDMENT UNTOUCHED. The nearest-face answer is still a function of the
POINT alone, so two cells that share such a corner hand the method the same three doubles and get
the same three back, and the corner moves to one place. Measured after the amendment, those 172
corners agree with world Z down to -0.999467, which is inside the range the 8698 corners that do
find a face already span on the same vault, down to -0.999984: they are answers of the same field
and not artefacts of being off it.

8. ONE LIMIT STANDS AND IS NOT FIXED HERE. On a surface standing EXACTLY vertical the offset branch
still degrades to the extrusion. Such a face has no plan area, so the nearest face is the vertical
one itself, and a face with no plan area carries no barycentric coordinates. LevelAt answers that
case with the mean of the triangle's three values, and the same reading is open here, the mean of
its three vertex normals, which would give a horizontal direction where the surface is vertical.
It is NOT taken in this pass, because it is a change of answer rather than of tolerance and it is
Param's to rule on.
