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
with steps and daylight beside them. Candidate mechanisms, to be measured not assumed: the
sectionless-cell fan route drawing at level height instead of lofting to the thickened
surface; the closer stones built from clipped faces but not carried through the same
thickening route as ordinary cells (top face must be built by the bottom's own route, the
standing rule from the offset work); or the loft-route nulls' fallback. The check that pins
the fix: every emitted cell's top-face corner heights sit within tolerance of the thickened
field surface at those plan points, asserted across the whole six-lobe fixture, proved red by
re-flattening one route.

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

## Sequencing

Round two dispatches when wf_c45cd653-3b3 lands and the tree frees, ahead of everything except
completion of the running wave itself. The Speed phase's profiling stands as scoped. The held
free-edge tasks stay held except where finding 1 subsumes a specific void class, which the
diagnosis will name explicitly.
