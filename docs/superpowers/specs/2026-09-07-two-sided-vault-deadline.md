# The two sided vault must produce a skin he can build, for the deadline

Written 2026-09-07 from his screenshots of the installed build (9ae02bd) and his words:
"theres alot fo issues still. some of these pieces that get broken up need to be larger pieces
and not cut so small. The banding is still happening but now its jsut showing a face and not
nothing. The honeycomb really sisnt working at all. then the 2 sided vault doesnt work well
with the skins. i really need that working for this deadline."

THE PRIORITY RULING, made from that sentence and binding until he says otherwise: ONE FORM
MATTERS NOW, the 2 SIDED VAULT on the COURSES pattern. It is what he needs for the deadline.
The honeycomb is PARKED: it is deeply broken (his own verdict, and his screenshots show whole
regions missing even after round five's genuine improvement), and it is not what the deadline
needs. The other vault counts follow the 2-sided fix for free where they share mechanisms, but
they are not the target and must simply not regress.

THE GOAL IS NOT A DEFECT LIST. It is: OPEN THE 2 SIDED VAULT AND THE SKIN LOOKS BUILDABLE.
Courses run continuously over the form, the crown reads as coursed stone, every stone is a
solid of sensible size, and there are no holes, no slivers, and no flat plates.

## The three defects he named, in his terms

1. PIECES CUT TOO SMALL. "some of these pieces that get broken up need to be larger pieces and
   not cut so small." Wherever the engine subdivides (transitions, closers, wedges, fans), the
   pieces must stay in the size family the ordinary courses keep. A stone noticeably smaller
   than its neighbours is a defect even when it tiles correctly.
2. THE BANDING NOW SHOWS A FACE. "The banding is still happening but now its jsut showing a
   face and not nothing." This is the top-height fallback shipped in round three: a cell whose
   solid would not close now ships as a flat face at top height instead of a hole. It removed
   the hole and introduced a plate, and a plate reads as a defect just as loudly. THE FALLBACK
   IS NOT THE ANSWER: the cell must CLOSE. Fix the closing, and let the fallback go back to
   being the rare, named exception it was meant to be.
3. THE BANDING ITSELF. Whatever is producing the continuous pale strips across the courses is
   still there after two rounds aimed at it. Root-cause it on HIS 2-sided net specifically,
   the way the honeycomb was root-caused, rather than reasoning from the synthetic fixtures.

## HIS RULING ON THE CROWN, 2026-09-07: ridge stones, no cap

Put to him with the render in front of him, because the cap gate was measured to fire CORRECTLY
by its own literal rule (it refuses an open strip; this crown genuinely traces a small closed
loop, since the crest has its own local high point: heights fall about four times faster across
the ridge than along it, and the diamond's own corners read 4.985 against 4.564). The rule's
premise, that a closed loop means a dome apex, simply does not anticipate a ridge whose crest
closes a small loop. That made it a design decision, and his answer is:

THE CROWN OF A RIDGE VAULT TAKES RIDGE STONES AND NO CAP. Courses from both flanks meet along
the crest and interlock there, the way a barrel or groin vault is built. No cap stone, no
radiating sunburst of wedges. This also retires the two defects that sit downstream of the cap
on this form: the oversized diamond (girth 2.855 m against a maximum piece of 1.5 m) and the
eight undersized wedges (0.27 m against an ordinary 0.53 m span).

IMPLEMENTATION NOTE, so the gate is not simply disabled: the distinction to encode is RIDGE
versus APEX, not open versus closed. A crest whose height falls much faster across than along
is a ridge however small the loop it closes; round three's ridge machinery (cross-ridge stones,
docs/superpowers/specs/2026-09-05-skin-round-three-findings.md finding 2, built in commit
3cb1371) is what should serve it. A genuine dome apex keeps the one-polygon cap of round two.
The measurement above is the discriminator and it must be checked on the OTHER studies too: the
3, 4, 5 and 6 sided vaults have real apexes and must keep capping.

## How the work is done

RULE A. HIS NET, START TO FINISH. All measurement on "2 sided vault-form.json" from
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Kinetic AI\PHD robotics\COMPAS Exports at his
canvas settings (Size 0.5, Course Height 0.5, Min Piece 0.20, Gaps 0.95, Thickness as exported).

RULE B. A PICTURE, NOT ONLY NUMBERS. The engine's tessellation is rendered to an SVG plan (and
an elevation) before and after every change, so the result can be LOOKED AT rather than
inferred from counts. Cell outlines drawn, holes left white, cells that failed to close filled
a distinct colour, cells under the size floor filled another. This closes the feedback loop
that has cost a week: every previous wave passed its numbers and failed his eyes.

RULE C. THE ACCEPTANCE, all on his 2-sided vault, all measured and all visible in the SVG:
   1. Uncovered plan area above the sliver floor: ZERO.
   2. Cells not shipping as closed solids: ZERO (the fallback fires never).
   3. Cells below the size floor: ZERO.
   4. Stone size distribution: the spread of stone areas outside the crown sits inside the
      band the ordinary courses themselves keep, so no stone reads as a fragment.
   5. The crown: coursed, not a fan of triangles. Whatever the ridge or cap machinery does
      there, the result must read as masonry.
   6. Every other study's surviving-cell count does not fall.

RULE D. ITERATE. This is not a one-shot task. Diagnose, change, re-render, look, repeat until
rule C holds or until a mechanism is proved to need a decision only Param can make, in which
case stop and name it precisely rather than guessing.
