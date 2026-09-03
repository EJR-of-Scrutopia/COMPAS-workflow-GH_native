# Skin thickness input: Param's ruling, 2026-09-02, mid-phase-two

His words, verbatim:

> "i would like to add one thing to this implementation plan, which is to have the skin component
> take a thickness input and therefore thicken the skin we add always in the z direction but
> depending whether the slider is - or + in integer. it should stay the same level of connectivness
> so an offset surface as opposed to a extrude in the normal direction otherwise we get gaps. but
> perhaps that can be a toggle option"

## The reading

1. SKIN GAINS A THICKNESS INPUT (Th), a signed number. Zero, the default, means today's behaviour
   exactly: nothing thickens, no output changes shape.
2. THE DEFAULT MODE IS A VERTICAL OFFSET. Every vertex of a cell's face is translated by (0, 0, Th),
   sign deciding up or down, and the solid is closed between the original face and the offset one.
   Because every cell moves by the SAME vector, shared edges stay coincident and the thickened skin
   remains watertight cell to cell: "the same level of connectivness". This is his stated reason for
   offsetting in Z rather than extruding along each cell's own normal, which makes neighbouring
   cells diverge and "we get gaps".
3. A TOGGLE selects the normal-extrusion mode for those who want it, gaps accepted. A boolean input,
   default false (vertical offset).
4. WHAT THICKENS: the SURFACE output. When Th is nonzero each emitted face becomes a CLOSED SOLID
   (bottom face, top face, side walls), same tree, same item alignment, nulls preserved where a face
   failed. Cells (the outlines) are untouched. This is the controller's reading of "thicken the skin
   we add"; if he wants the solids on their own output instead, that is a one-port change.

## The physical trade, stated so the toggle's purpose is on the record

A vertical offset of thickness t gives a NORMAL thickness of t times the cosine of the surface's
slope. Near the crown, where the shell is flat, the two agree; at a steep springing the effective
structural thickness thins accordingly. That is inherent to keeping the skin connected, and the
normal-extrude toggle exists exactly for readings where true normal thickness matters more than
watertightness.

## Sequencing

Queued as the CLOSING TASK of phase two, dispatched after Task 32, before the whole-branch review,
inside the same install. It builds on Task 29's Surface output (CellSurface) and touches
SkinComponents.cs (the new inputs) and SkinPatterns.cs or the component (the thickening); it must
not disturb the port order Task 30 establishes except by appending, and the load-protection
warning's archived-port comparison means the ADDED inputs must be a pure append so saved
definitions reattach silently.

Harness: the thickened solid is closed (a watertight Brep) for a planar and a non-planar cell; two
adjacent cells' shared wall is coincident to tolerance in Z mode; Th = 0 leaves every output
byte-identical; the sign flips the offset direction; the toggle produces the normal-mode solid.
Every new check proved able to fail, per CLAUDE.md.
