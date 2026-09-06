# Round five: the honeycomb's overlapping rows, and a self-weight loop that settles fast

Written 2026-09-06 evening, after round four's reviewer answered the only question that matters
with a NO: "would Param, opening these same eight forms in Rhino, SEE the difference?" His
verdict, quoted because it must not be softened: "opening those forms in Rhino today looks
exactly as it did before this wave, gaps and all." Round four's four tasks were honest work
that changed nothing visible. This document is the correction.

## PART ONE: the honeycomb rows overlap by construction

WHAT ROUND FOUR MEASURED, and what it means. On Param's three Hex studies (his own words: "the
really troublesome hex skin") the engine PROPOSES cells and then drops 28.5, 28.5 and 34.4 per
cent of them to plan overlap. Round four's rescue lowered the number of cells built-then-rejected
(127 to 90, 127 to 90, 252 to 200) but the SURVIVING SET IS BIT-IDENTICAL: ClosedSeams and
CloserCells read 0 on every fixture measured, so not one closer stone has ever been observed to
survive on a honeycomb net. The visible gaps are unchanged.

THE MECHANISM, as far as round four got: "every honeycomb row spans two Course Heights by
construction" and "a row whose centre count differs from its predecessor overlaps an earlier
course". So the defect is not a missing closer. IT IS THE ROW GENERATION ITSELF: the honeycomb
lays rows that mutually overlap in plan whenever the centre count changes between rows, and the
plan filter then deletes whichever cell arrives second. Every downstream rescue is therefore
treating a symptom.

RULE 1.1. ROOT-CAUSE FIRST, no more rescues. Instrument the honeycomb's row construction on his
three Hex studies and answer, with numbers: where does each row's band come from; why does a
changed centre count make a row reach into its predecessor's territory; is the two-Course-Height
span a deliberate design or an accident of the chart mapping. Report the answer BEFORE changing
anything, because three waves have now been spent fixing this from the wrong end.

RULE 1.2. THE FIX IS THAT ROWS DO NOT OVERLAP. Whatever the root cause names, the acceptance is
that the honeycomb proposes a tiling whose cells do not mutually overlap in plan, so the plan
filter deletes single figures at worst and ideally nothing. Measured on his three Hex studies,
before and after, as a drop RATE against proposed cells (round four's own denominators: 316,
316, 581). The kept-cell set must GROW: a fix that lowers the drop count without adding surviving
stones has changed nothing, which is precisely round four's lesson, and the check must therefore
pin the SURVIVING count, not the dropped one.

RULE 1.3. Only once rows are sound does the closer question return: with a non-overlapping
tiling, whatever the honeycomb still refuses is a genuine refusal and the closer may serve it.
Until then the closer wiring stands as shipped and is not to be widened.

## PART TWO: the self-weight loop must settle fast, not merely settle

WHAT IS SHIPPED, and why it cannot stand. The refinement cap was raised from 10 to 100 rounds
(commit 4cc398a) after re-measurement showed seven of his eight nets settle in three to six
rounds, and only the 6-sided vault (1321 vertices) creeps: drift falls monotonically
(0.322, 0.0849, 0.0364, 0.0193, 0.0121, 8.69e-3, 6.91e-3 by round 10) and crosses the 1e-3
tolerance at ROUND 75. Correctness improved: the old fenced answer underweighed self-weight by
about 3.6 times. But that net's solve went from 4.1 s to 28.0 s, and 28 s per solve is not a
tool Param can design with.

RULE 2.1. ACCELERATE THE CONVERGENCE RATHER THAN GRINDING IT. The measured drift sequence is
smooth, monotone and strictly decreasing: that is the easy case for convergence acceleration
(Aitken extrapolation on the iterate sequence, or an under-relaxation factor tuned from the
measured contraction ratio, or Anderson mixing if the simple routes underperform). Target: the
6-sided vault reaches the SAME 1e-3 tolerance in a single-figure round count, and the solve
returns in a few seconds rather than 28.

RULE 2.2. IDENTITY IS THE BAR. The accelerated answer must agree with the ground truth the slow
loop reaches, to a stated tolerance tighter than the loop's own 1e-3, on every one of his eight
nets. Report the comparison per net. An acceleration that changes the answer is a bug, not an
optimisation.

RULE 2.3. HONESTY IF IT STILL CANNOT SETTLE. If a net genuinely cannot reach tolerance, the
component says so by name with its measured drift, and the fenced fallback stays. Silent
grinding to a cap is what this wave exists to remove.

RULE 2.4. THE INTERACTION ROUND FOUR'S REVIEWER FLAGGED: with cancellation no longer killing the
worker (commit 9211896), a long solve that has been superseded now runs to completion rather
than dying. Once part two lands, the long solve is short and the concern shrinks; verify it
rather than assume it, by measuring a rapid drag on the 6-sided vault before and after.

## Acceptance for the wave

Every number measured on HIS eight studies. For part one the pin is the SURVIVING cell count on
the Hex studies and the reproduction pins re-measured with old numbers named. For part two it is
round count, wall clock and answer identity per net. And the wave's own review must again answer,
in writing, whether Param would SEE the difference on his own forms; a no is a failure of the
wave, not a note in its margin.
