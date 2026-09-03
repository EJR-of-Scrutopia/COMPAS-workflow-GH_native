# The thickness slider: offset to extrude, both on the surface normal

Written 2026-09-04 from Param's correction and his slider design, in his words: "Offset button
doesnt mean the direction changes from surface normal to world Z, it will always be on the normal
direction, it means that it offsets the surface or it extrudes it in the normal direction ...
I want to take this a step further and do a slider 0-1.00 where I can slide between if the outer
surface goes from offset (essentially meaning a smooth edge to edge surface) to extruded (which is
the gaps we mention because we just straight extrude the surface by the thickness from the normal
as well). That means we can remove the button and put in this slider."

This supersedes rule 5 of docs/superpowers/specs/2026-09-03-skin-offset-surface.md and its
erratum's port description. Rules 1 to 3 of that spec (the normal field, the normal at a point,
the continuity argument) stand and are load-bearing here. Rule 4 (signed, one-sided thickness)
stands unchanged.

## 1. The two ends of the slider, stated in Rhino terms

OFFSET, the 0 end, is OffsetSrf: the outer skin is the true offset of the thrust surface. Every
outline corner travels along the field normal AT THAT CORNER, shared corners coincide, joints are
shared faces, the assembly is one watertight thickened shell, and on a dome the outer face is
genuinely larger than the inner because that is what an offset is.

EXTRUDE, the 1 end, is a per-cell ExtrudeSrf along the CELL'S OWN normal: the block is a rigid
translation of its cell, outer face congruent to the inner face, same area, and gaps open at the
joints in proportion to curvature times thickness because neighbouring cells' normals disagree.

BOTH ends live on the surface normal. WORLD Z IS GONE: the (0, 0, Th) branch of the superseded
rule 5 is DELETED, its harness check 4 (the extrude-branch regression pin) dies with it under an
erratum note in the old spec, and nothing in the engine may offset by a direction the surface does
not own. In between, the slider morphs the JOINT BEVEL: at 0 the side faces are radial and shared,
at 1 they are parallel to the cell normal and open.

## 2. The port

The input at INDEX 6 (the old Offset toggle) becomes:

    name        "Extrude"
    nickname    "EX"
    type        Number, item access
    domain      0.0 to 1.0, values outside clamped with a Remark naming the clamp
    default     0.0  (the offset surface, the finished shell)

The index does not move, so no archived wire slides. An archived BOOLEAN wired here casts the
Grasshopper way: False reads 0.0 (offset) and True reads 1.0 (extrude), so Param's existing canvas
toggle at False lands on the correct new default without his touching it. The port description
says both ends in one sentence each and names the gap behaviour at 1.

## 3. The geometry

RULE 3.1. THE CORNER. For every outline point p with field normal n(p) and cell normal N:

    direction(p, t) = unit( (1 - t) * n(p) + t * N )
    top(p, t)       = p + Th * direction(p, t)

The blended direction is RENORMALISED so the thickness is exactly |Th| at every t. Where the blend
degenerates (n(p) and N opposed, length under 1e-12), fall back to n(p).

RULE 3.2. THE CELL NORMAL. N is the renormalised MEAN of the cell's own corners' field normals.
It derives from the same oriented field as the corners, so t = 1 cannot disagree with t = 0 about
which side is out. Degenerate (under 1e-12): the Newell normal of the outline, oriented to agree
with the field's global up; failing that (0, 0, 1).

RULE 3.3. THE WELD SURVIVES ONLY AT 0, AND THAT IS THE POINT. At t = 0 the direction is n(p), a
function of the point alone, and shared corners coincide (the standing rule 3 argument). At any
t > 0 the cell normal enters and neighbours may split: that is the design, not a defect, and the
weld check asserts coincidence at t = 0 ONLY. A second check asserts the split GROWS with t on a
curved fixture (monotone in t at a shared corner of two cells whose normals differ), so the
slider measurably does what it says.

RULE 3.4. CONGRUENCE AT 1. At t = 1 every corner of one cell moves by the same vector Th * N, so
the top ring is congruent to the bottom ring. Assert it: pairwise corner distances of the top ring
equal the bottom ring's to 1e-9 at t = 1, and do NOT equal them on a curved cell at t = 0.

## 4. The field is oriented, so +Th always means OUT

The vertex-normal field currently follows the mesh winding, and Param's first offset test on a
net wound the other way drove the blocks through the surface. RULE: after the field is built, if
the AREA-WEIGHTED SUM of all raw face crosses has negative Z, flip every vertex normal once,
globally. One flip preserves rule 3's continuity exactly. +Th is outward and up on every net,
whatever the winding; -Th is inward. A check builds the same fixture with both windings and
asserts identical offsets.

## 5. The top face is built by its bottom's own route

Under the old extrude the top face was a transformed copy of the bottom and matched it by
construction. Under the offset the top was built as a FAN even when the bottom is a loft, which is
the triangulated crust in Param's screenshot and the leading suspect for the thickening failures.
RULE: the top face takes the SAME route its own bottom face took. A loft-route cell lofts its top
from the per-corner-moved section rails; a fan-route cell fans over the moved outline from the
moved apex. Walls run between corresponding rings as now. The routes are already keyed off
Sections; no new case is invented.

## 6. The vertical face answers with its own mean, not with Z

NormalAt's nearest-face branch still returns (0, 0, 1) when the nearest face has no usable PLAN
area, which is exactly the vertical face the offset most needs to serve. RULE, matching LevelAt's
own degenerate convention (it answers with the mean of its triangle's three values): a nearest
face below the 1e-15 plan-area guard answers the renormalised MEAN of its three vertex normals,
and (0, 0, 1) survives only for a net with no usable face at all. This was parked as paragraph 8
of the old spec's erratum for a ruling; the ruling is taken here and recorded in the ledger.

## 7. Housekeeping folded into this wave, from the fix round's re-review (all seven)

1. The 2026-09-04 datelines written by commits that landed late on 2026-09-03: leave the text, add
   one line to the old spec's erratum noting the dates are the working date, not the commit date.
2. docs/superpowers/plans/2026-09-03-skin-defects-and-free-edge.md still promises "exactly one
   DEFER" (lines 56 and 108); amend to name the sanctioned second deferral and its owner.
3. ThickenFailureLine's docstring and remedy still describe the dead world-Z branch ("copied onto
   itself", "costs nothing"). Rewrite both for the slider: the honest remedy is a smaller
   Thickness; Extrude near 1 opens joints by design; and no wording may imply the slider rescues
   the loft-route failures, which remain unattributed until the Rhino script runs.
4. A non-finite Th is a silent no-op through Thickening; TryReadInputs floors it, but the
   component should WARN when it does, one sentence, so a NaN expression upstream is not invisible.
5. The eighteen-line nearest-face loop is now duplicated between LevelAt and NormalAt, and only
   NormalAt carries the empty-net guard. Extract ONE shared helper carrying the guard; both call
   it. Prove by the bit-identical-normals technique that the extraction changes no answer.
6. The off-mesh verticality assertion is guarded on cornersOffMesh > 0 and nothing asserts the
   population; assert it the way its sibling does, so a fixture change cannot hollow the check.
7. The wedge fixture's endAgreement guard compares two hand-written constants and can never fire;
   either compute one side from the engine or delete the guard and say the fixture carries the
   intention.

## 8. Checks, each proved able to fail

1. Weld at t = 0 (exists; unchanged).
2. Split grows with t at a shared corner on the curved fixture (rule 3.3).
3. Congruence at t = 1, and non-congruence at t = 0 on a curved cell (rule 3.4).
4. |top - p| = |Th| at t = 0, 0.5 and 1 (the renormalisation).
5. Both windings, identical offsets (rule 4).
6. The Boolean cast: a GH_Boolean False supplied to the port reads 0.0 and True reads 1.0.
7. The vertical-face mean answer (rule 6), on the walled-vault fixture that today reads (0, 0, 1).
8. Top-by-bottom-route: a loft cell's top face at t = 0 carries the loft structure, not a fan
   (assert on the section/rail counts the builder reports, since Brep face counts need Rhino).
scripts/rhino_skin_surface.py: the offset cases gain the slider at 0, 0.5 and 1, keep the exact
per-corner |Th| assertions, and 12.5(i)'s side-by-side count now runs per slider stop. Still never
run; still the owner of the loft-route question and the second DEFER.
