# Round three B: the holed nets, and the coverage instrument that lied

Written 2026-09-06 from the holed-net diagnosis (docs/superpowers/specs/
2026-09-06-skin-holed-net-diagnosis.md, measured on a new HoledLobedNet fixture in one-hole
and six-hole, on-seam and off-seam, free-rim and anchored-rim variants against a filled-in
control). This document is the scope of the round three B wave, which runs AFTER the round
three wave (fixes 1 to 7) lands and is reviewed, because both touch the same engine.

WHY IT EXISTS. Param's live six-lobe carries design holes near the crown. Round two closed
the synthetic lobed fixtures to 0.0000 m2 uncovered, and round three addresses four gap
classes measured on solid nets, yet his holed net keeps showing radial openings along the
valleys and a ring of gaps near the crown. The diagnosis answers why: a hole rim is a
DISTINCT DEFECT CLASS, and all seven planned round three fixes are blind to it. Every fixture
proven to date carries exactly one outer boundary and no interior rim, so any mechanism that
silently assumes that has never been tested. Three new mechanisms, G5 to G7.

## RULE 1: G6 first, because it broke the instruments

G6, the hole-adjacent crown cascade (unanchored single hole): CloserBand stitches ONE closer
stone about seventeen times oversized across a seam whose two sides are at mismatched scale.
That single stone EVICTS about 2.76 m2 of legitimate geometry (ten ordinary stones plus the
keystone) through the plan filter, and re-triggers the self-cross and drop behaviour that
round two's depth-0 rescue was believed to have closed.

THE PART THAT MATTERS MOST: while this happens, BOTH coverage instruments read about 100 per
cent, the harness's own sampler and the engine's PlanCoverage per cent alike. An eviction
that replaces ten good stones with one monstrous one keeps the area covered, so an
area-only instrument cannot see it. This is the repo's documented false-green class arriving
in the acceptance criteria themselves, and it is the reason the fixture numbers kept saying
0.0000 m2 while Param kept photographing holes.

THEREFORE, and this is binding on every later skin wave: coverage acceptance is no longer
area alone. A pattern is accepted only if, in addition to covered area, (a) no emitted stone
exceeds the size bounds the ordinary courses obey (the maximumPiece rule already exists;
it must bind the closer too, which is where the 17x stone came from), and (b) the emitted
stone COUNT per band does not collapse against the traced curves' own capacity, so an
eviction is visible as a count deficit even when area reads full. Both asserted, both proved
red by restoring the oversized stitch.

## RULE 2: G5, the anchor-proximity field capture, is the worst outcome measured

An ANCHORED hole ring near the crown becomes the field's nearest anchor, so the rim seeds the
course families as if it were the vault's own rim. The course count collapses (16 down to 8
or 9 on the fixture) and "the crown" relocates to phantom off-centre locations. Up to 6.9 m2
open, measurably WORSE than leaving the same hole unanchored.

This is not a bug in one routine; it is the seeding rule meeting a form it was never told
about. Param's real models DO anchor their rings (his words on the six-lobe: without the
rings as anchor points the form itself fails), so anchored interior rims are ordinary usage,
not an edge case.

THE RULING FOR THE IMPLEMENTER, made here so the wave is not blocked overnight, and flagged
for Param to overturn if he wants the other reading: an interior anchored rim is a STRUCTURAL
support but NOT a coursing origin. The course field's seeds stay the OUTER support set, so
courses run from the outer rim to the crown as they do on a solid net, and an interior hole
becomes an OBSTACLE the level curves part around (its rim gets the free-edge treatment and,
where a course is severed by it, the two arms are ordinary components of that course).
Rationale: coursing follows the dominant flow of the vault, and a masonry oculus is coursed
around, not coursed from, unless the designer says otherwise. The alternative reading, hole
rims seeding their own concentric coursing like a true oculus ring, is a legitimate design
choice and is left as a possible future input, deliberately NOT built now. Say the choice in
the component chin so it is never silent: name how many interior rims were treated as
obstacles.

## RULE 3: G7, the ridge gate false positive

Round three's ridge handling gates the cap on whether the summit is a ridge. On a
hole-perforated POINT crown the gate misfires: it reads ridge, refuses the cap, and the
summit ships open. The gate must classify the summit from the surviving crown structure
rather than from perforated-neighbourhood evidence, and a point crown with holes nearby must
still cap. Checked on the holed fixture at both hole positions, red by restoring the naive
gate.

## RULE 4: what carries over unchanged

G1's pinch-out generalises to hole rims correctly; the diagnosis measured it and it needs no
work. Round three's fixes 1 to 7 stand as written for solid nets, and their fixtures stay.
The holed fixtures (HoledLobedNet, all four variants plus the filled control) become
PERMANENT harness fixtures: from this wave on, every skin acceptance runs on a holed net as
well as a solid one, because his real geometry has holes and ours did not.

## Acceptance

Param's standing sentences, now on holed nets too: no tiny fill-in pieces, no gaps beyond the
adjudicated sub-sliver residues, seam stones indistinguishable from ordinary courses, and
every hole named rather than silently absorbed. Plus the new instrument rule of section 1:
area alone never again certifies a pattern.
