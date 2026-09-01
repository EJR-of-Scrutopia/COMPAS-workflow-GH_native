# Columns redesign: Param's rulings, verbatim, with the reading taken from them

This is the design input for the columns priority spec. Param's own words are quoted exactly;
everything outside a quote is the reading taken from them and is subordinate to the quote. Where
the two disagree, the quote governs.

## 1. The current behaviour is confirmed wrong

> "The column logic you described and said its how they perform in the screenshot is confirmed to
> produce that result and its actually not what we want."

The account given to him of the existing engine (bands cut from the chord, each tree projecting into
a band, a band's foot the plan centroid of its main notches, symmetrisation disengaging whole when a
span fails its pairing test) is accurate as a description of the code and is not the behaviour
wanted. The redesign is therefore a replacement of the placement rule, not a repair of it.

## 2. The stray columns, and the priority ladder he wants

Grouping notches into trees of Branching consecutive notches leaves a remainder. Those leftover
single columns are what he calls stranded or stray. His rule:

> "So yes the idea that only 1 or two columns get left stranded, but they also need to be placed
> symmetrically and we need to build a priority placement into it. If one column it should defer
> directly to the center node where then the rest of the columns will all be symmetrical, then two
> stray columns will be the 2 end nodes and nothing in the center, three stray columns the two end
> nodes plus the center. This should be clear enough not to describe the symmetry I am getting at."

So, stated as a ladder over the number of strays:

- one stray: the CENTRE node, and nothing else, so every other column pairs off symmetrically
- two strays: the two END nodes, and NOTHING at the centre
- three strays: the two end nodes AND the centre

He explicitly declines to enumerate further, expecting the principle to generalise. The principle to
take is that the strays occupy the most symmetric positions the span offers, the centre being taken
when and only when the count is odd, and the remaining strays taken in mirrored pairs working from
the ends inward. The spec must state the general rule it derives and must show that rule reproducing
all three of his cases exactly.

This REPLACES the present rule, which puts the remainder at the anchor ends in every case regardless
of how many there are, and which is a large part of why the placement looks arbitrary to him.

## 3. Why a column that branches from one point is never quite central

> "the columns if branching from one point, seriously struggle to ever be centered correctly. this i
> think is because for some reason taking the center of the object doesnt give the center of the
> principle lines, and even taking the center of them also doesnt always (I actually dont know why
> maybe a bug), so best is to take the closest points to center from the principle lines and then get
> them to all point inwards where they touch, maybe this will give the exact placement for that all
> branching from center point."

His instruction is to stop deriving the central foot from a centre or a centroid at all. Take the
points on the principal lines CLOSEST TO THE CENTRE, and let those converge inward to where they
meet; that meeting is the foot. The engine today uses the plan centroid of the main notches a band
carries, which is precisely the construction he is rejecting.

The spec must state the convergence rule exactly: which points are candidates, what "point inwards"
means as arithmetic, and what the foot is when the inward directions do not meet at a single point,
which they will not in general.

## 4. Duplicate points where two principal lines touch, and his hypothesis

> "Also on this the two principle lines can be touching eachother and so we need to make sure we
> arent placing duplicate points over each other then one of them gets cancelled out becuase cant
> have two connections on one node which then throws off the symmetry algorithm. this might be what
> is getting it to go wrong often."

This names a real mechanism in the present code and should be treated as a leading hypothesis for
the symmetry failures. Where two principal lines cross or touch they share a net node. The engine
keeps a set of held notches; the first bar to reach a shared notch claims it and every later span
skips it. A span that loses an interior notch that way has a free-notch list which is no longer
symmetric about its own chord midpoint, so it FAILS the pairing test in Symmetrise, and the whole
span then falls back to unmirrored per-tree placement. That is the symmetry cliff, and a crossing is
one of the two ways the code's own comments say it is reached.

The spec must say what happens at a shared node: whether both lines may hold it, how a column is
placed there without two members meeting at one connection, and how a span whose notch was claimed
elsewhere still receives symmetric treatment. Solving the general symmetry rule without solving this
would leave his most likely trigger in place.

## 4a. The one-sided lean, MEASURED, and what it changes in the design

A second screenshot showed the columns on one side of the crown leaning as expected and those on the
other leaning the wrong way, with the feet all displaced in the same world direction rather than
mirroring. That was diagnosed against a fresh build of the engine, driven directly. The result is
conclusive and it confirms section 4's hypothesis as the trigger.

WHAT WAS RULED OUT, so the redesign does not waste effort there. The aim's sign and frame are exactly
right: over 20,000 random pull vectors, mirroring the input and mirroring the output agreed to the last
bit, and hand-built mirrored resultants gave feet mirrored to zero. The lean cap is continuous and
monotone, so it compresses the symptom rather than causing it; on the broken net it reduced a
37 degree discrepancy to 30.5. The across component kept per span is real but displaces feet
perpendicular to the chord, in world Y, so it cannot produce a lean along the chord at all.

WHAT IT IS. A crossing steals an interior notch, the span's surviving notches no longer pair off, the
whole span is condemned, and line 618 to 623 hands it back its RAW resultants entire, including the
common along-chord component the mirror rule exists to remove. Every foot on that rib then walks the
same way down the chord.

| net | asymmetric spans | mean foot shift | worst mirror error |
| --- | --- | --- | --- |
| no crossing | 0 | 0.000 | 0.000 |
| crossing near a springing | 5 | +0.663 | 2.171 |
| crossing at the CENTRE notch | 0 | 0.000 | 0.000 |

The third row is the tell: a crossing at the centre leaves the notch list symmetric and costs nothing.
Only an off-centre crossing does the damage, which is what his ribs do where they touch away from the
crown.

THE CLIFF IS ABOUT A CENTIMETRE WIDE. Nudging one notch along the chord: at 0.20 the span is mirrored
and every foot is exact; at 0.21 five spans are condemned, the mean foot moves 0.944 and the worst
error is 2.209. One centimetre of node movement on a ten metre span takes every column on every rib
from perfectly mirrored to displaced most of a metre in the same direction.

TWO MORE ROUTES TO THE SAME COMPLAINT, both found in the same investigation.

A bar anchored at ONE end only trips the cliff with no crossing at all. And an unequal anchor cluster
does something quieter and arguably worse: the span still PASSES the test, but its chord now runs from
the innermost anchor, so the mirror plane sits off the crown, the pairing is off by one, and the column
that should stand plumb stands half a notch away from the crest.

Worst of all, and on a net where every diagnostic reads clean: with the crest displaced a tenth of the
span off centre, every span passes, so the mirror rule IMPOSES a symmetry the structure does not have.
The notch at the true crest, which wants to stand plumb, is made to lean 7.4 degrees, and the notch at
the chord midpoint, which wants 7.9 degrees, is made plumb. The band of columns between the true crest
and the chord midpoint leans the wrong way. Raising one springing above the other does the same.

A DIAGNOSTIC TRAP worth fixing in the same wave. AsymmetryRemoved FELL from 75.40 degrees to 1.81 the
moment the rule stopped running, because an unmirrored span's aim is never moved. The number reads most
reassuringly exactly when the machinery has been bypassed. The honest signal today is AsymmetricSpans,
which the component prints as ", unmirrored N"; the number that SHOULD be reported is the largest
along-chord common mode still standing after placement, which reads zero when the rule worked.

WHAT THIS CHANGES IN THE AGREED DESIGN. Section 5's per-tree pairing was proposed to soften the cliff.
The measurement says go further and remove the cliff entirely, because any threshold on a continuous
measurement has one, and this one is a centimetre wide with a metre of column movement on the far side:

1. REMOVE THE COMMON MODE EXPLICITLY, not by pairing. What must go is the span's MEAN along-chord pull,
   a rigid-body tilt no column should follow. Subtracting that mean is defined for any notch list
   whatever, needs no pairing, no tolerance and no test, and is continuous in the node positions, so it
   cannot cliff. Pairing then only refines what is left, and an unpartnered notch costs nothing.
2. DERIVE THE MIRROR PLANE FROM THE STRUCTURE, not from the anchors. The span's first and last node are
   an artefact of where the anchor cluster stops; the physical mirror is where the along-chord pull
   changes sign. That fixes the unequal anchor cluster and the off-centre crest in one move, and it
   degrades gracefully on a genuinely asymmetric vault instead of forcing a symmetry onto it.
3. A STOLEN NOTCH KEEPS ITS OWN LINE'S FRAME, or a crossing is not allowed to take another line's
   interior notch at all. That alone accounted for 1.33 units of error on a perfectly symmetric net
   with no skew whatever.
4. THE DIAGNOSTIC REPORTS THE RESIDUAL, so it cannot read clean when the rule was skipped.

INCIDENTAL, AND WORTH ITS OWN LOOK LATER: the outermost principal line, which carries infill on one
side only, had an across component NINE TIMES its down component, so its columns are aimed almost
entirely sideways. That is not the reported symptom and is not this wave's business, but it will be
visible on his model as the outermost ribs' columns leaning out of plane.

## 5. What carries over from the earlier agreed design

These were agreed with him before the above and are not displaced by it:

- Feet are decided first, from the span, and trees are then assigned to them, inverting the present
  order in which each tree projects into a band.
- A foot SNAPS to the plan position of the nearest principal node to its target, so a column stands
  plumb under a notch and feet on matching ribs line up because the nodes do.
- Mirror pairing is PER TREE, by chord parameter reflection, so a tree at parameter s pairs with
  whichever tree sits nearest 1 - s within a stated tolerance and an unpartnered tree simply stands
  alone. This removes the present all-or-nothing behaviour in which one asymmetry disables a whole
  span's symmetry treatment.
- A mirrored pair always takes mirrored feet.
- Feet on ADJACENT principal lines merge into one column only where they already fall within a
  clearance of each other, never always and never not at all.
- Forces inform the LEAN and no longer decide the POSITION.

Note for the spec author: an earlier draft of this design proposed foot targets at chord parameters
1/(N+1) through N/(N+1). Section 2's ladder is his own and supersedes it wherever the two disagree;
in particular two strays go to the ENDS and not to 1/3 and 2/3. Reconcile the Type level's own foot
targets with section 2's principle and state the single rule that governs both.

## 6. Out of scope, by his ruling

The skin buildability work (minimum piece size, build sequence order, band splitting for topology
transitions) and the new Skin surface output come AFTER the columns:

> "Youre right that we defferred the skin buildability. we will work on this after the columns and I
> will review the tesselation and rest of the work while that happens"
