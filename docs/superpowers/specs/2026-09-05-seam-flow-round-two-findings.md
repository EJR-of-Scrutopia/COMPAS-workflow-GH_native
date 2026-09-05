# Seam flow round two: Param's findings on the early 8b9a44a build

Written 2026-09-05 afternoon from his three screenshots of the six-lobe form running the
early-feedback install (commit 8b9a44a, the blended field and full-width seam stones, installed
ahead of the wave's completion at his request). His verdict: "well done we are getting close
now. still not perfect." These three findings are binding scope for the round-two fix wave,
dispatched after the running seam-and-speed wave (wf_c45cd653-3b3) lands. Where a finding
overlaps the held free-edge tasks, HIS INSTRUCTION HERE WINS: he asked for these closed.

## Finding 1: gaps still open, and the fill pieces are tiny

His words: "we need these gaps closed and they also need to be of similar size so they arent
tiny little fill in pieces."

Observed on the six-lobe: rectangular voids left open in the tessellation (several per lobe,
plus one full missing stone in the close-up), and clusters of sliver stones (rows of tiny
pieces visible at mid-lobe, the old pinstripe signature at reduced scale). The full-width
absorb rule (round one, rule 3.1) runs at the SEAM refusals; these residues suggest either
(a) refusals away from the recovered seam curves that no closer serves, (b) absorb stopping
short of a full course height in some intervals, or (c) plan-filter drops that rule 2.5 of the
2026-09-04 seams design pinned to zero only on the two merge fixtures and not on a six-lobe
class form. DIAGNOSIS FIRST: reproduce on a six-lobe fixture, name which of the three
mechanisms owns each void class, then fix. The acceptance is his sentence: closed, and closing
stones inside the adjacent courses' size range, same as the seam pin. No tiny fill-in pieces
anywhere, not only at seams.

## Finding 2: some stones flat and low

His words: "Still getting gaps and flat surface only on some, which arent raising to the right
height to match."

Observed: certain stones render as flat plates sitting below their neighbours' top surface,
with steps and daylight beside them.

MEASURED 2026-09-05 (diagnosis in 2026-09-05-seam-flow-round-two-diagnosis.md, superseding the
guesswork that stood here): outline-corner heights are NOT the defect. Every emitted cell's
outline corners sit at 0.0000 m from the surface on every route, so a corner-height check
would pass today and is vacuous; do not build it. The two real mechanisms:
(a) MID-FACE CHORD SAG on the closer-loft route over absorbed multi-CH slabs: interiors sag to
    35 mm off the surface against a 9 mm p90 for ordinary courses. The fan routes are
    acquitted (0.7 to 2.4 mm measured).
(b) THE UN-THICKENED-FACE FALLBACK on the Rhino side (SkinComponents.cs:417-467 and 574-604,
    warned by ThickenFailureLine): cells whose thickening fails ship as a literal flat face at
    the bottom height. Param's GH chin on the six-lobe should be checked for that warning to
    confirm this owns his flattest stones.
The checks that pin the fix: interior SAMPLE points (not corners) of every emitted top face
sit within the ordinary-course sag envelope, asserted across the six-lobe fixture, red by
re-coarsening the closer loft; and every cell ships in the Solid slot (slot==Solid asserted),
red by forcing one thickening failure.

## Finding 3: the central cap becomes one polygon

His words: "the central cap is that many pieces split or can it just be a polygon please, the
polygon sides will of course be determined by the sides we have on the form."

Today the apex cap is a rosette of many wedge pieces. RULING: the cap is emitted as ONE
polygonal stone. Its side count follows the form: the cap polygon's vertices are the corners
the final closed level loop actually carries (a six-lobe form's loop shows its six-fold
structure; a dome's loop is near-circular and the polygon follows its vertex structure).
Implementation shape: where CapQualifies fires, emit a single cell whose boundary is the final
traced loop, simplified to its structural corners, instead of the fan; the keystone-leads
ordering keeps its slot (one keystone, no rosette). The existing cap gates are untouched: this
changes what a cap EMITS, not when a cap fires.

## Live-model confirmations, from Param's own Grasshopper pull, 2026-09-05 late afternoon

He ran the installed 8b9a44a build on his six-lobe and read the chins back. These are the
ground truth the fixtures must reproduce:

- FINDING 2(b) CONFIRMED: "32 faces would not close into a SOLID at Thickness 0.200, the
  first at course 2. Those cells are STILL EXPORTED and are drawn as the un-thickened face."
  The chin's own remedy ("a smaller Thickness") is the component admitting it has no rescue.
  His close-up shows exactly this: a grey face sunk to bottom height amid closed red solids.
  The fix must rescue the cell, not advise on sliders: either close the solid robustly or, at
  minimum, ship the fallback face AT TOP HEIGHT so it reads in the coursing while a named
  warning still says it is not a solid.
- FINDING 1 (plan drops, live count): "3 of the 863 cells this pattern proposed were REFUSED
  or DROPPED: 0 self-crossing, 3 overlapping a cell already kept. The skin has a small hole
  where each one was." The overlap class, not the fold class, owns his visible holes on this
  model; the fixture work already measured the crown fold class separately.
- SEAM WORKING: "1 seam was CLOSED with 80 stones of a closer band cut along the seam,
  between d=4.000 and d=4.500 m." The round-one machinery is live and firing on his model.
- Context: mean piece length 0.495 m, 863 cells, crown cap girth 1.983 m with 0 wedges
  reported on this pull, 10 boundary-clipped cells, 0 merged pieces.

## Sequencing

Round two dispatches when wf_c45cd653-3b3 lands and the tree frees, ahead of everything except
completion of the running wave itself. The Speed phase's profiling stands as scoped. The held
free-edge tasks stay held except where finding 1 subsumes a specific void class, which the
diagnosis will name explicitly.
