# Seam flow: the stones where directions meet become indistinguishable

Written 2026-09-05. THE ACCEPTANCE CRITERION IS PARAM'S SENTENCE, verbatim and binding: "the
seam stones should feel exactly like the flow of the other contours, they should not be a
pinstripe. they should be indistinguishable." And the mechanism is his earlier sentence, also
binding as intent: "joining or tweening two force lines where they both give way equally to keep
the contouring distance the same and then have the shape still flow nicely from one into the
other." He has raised this since the first screenshot; this spec is the direct answer.

## 1. The two defects this fixes

1. THE CHEVRONS AND THE CROWDING. The course field is min(distance from family A, distance from
   family B); the min carries a CREASE along the meeting line, every contour crossing it kinks,
   and contours crowd against it. The crease is the visual signature he has objected to all week.
2. THE PINSTRIPE. The closer band tiles only the refused interval, which after bisection is
   about CH/64 wide, so its stones are Size long and millimetres wide: a pinstripe. His
   similar-size requirement was pinned along the curve and missed the width direction. A genuine
   spec miss, owned.

## 2. The blended field (his tween)

RULE 2.1. The rim-distance marching carries THE BEST TWO family arrivals per vertex: (d1, g1,
d2, g2), nearest and second-nearest seed families. The family identity g1 already exists (built
for the seam curves); the second arrival is the addition.

RULE 2.2. The course field becomes a SOFT MINIMUM of d1 and d2 inside a blend zone and is
EXACTLY d1 outside it: where d2 - d1 >= R the field equals d1 to the last bit, so everything
away from seams is untouched and the harness's field pins survive unmoved. R, the blend radius,
defaults to one Course Height; whether it surfaces as an input is the implementer's proposal to
the review, with OFF-by-zero mandatory (R = 0 reproduces today's field bit for bit, pinned).

RULE 2.3. The blend form is the implementer's choice under four binding properties, each
asserted: symmetric in d1 and d2 (both families give way equally); C1 smooth across the old
crease (no kink: the contour tangent is continuous where it crosses the seam curve); gradient
magnitude never above 1 and never below a stated floor inside the zone (contouring distance
stays honest, his words); reduces exactly to min outside the zone.

RULE 2.4. Consequences to verify, not assume: the traced level curves near a meeting flow
smoothly from one family into the other (chevron kink angle measured across the seam, pinned
under a stated threshold on the crown-arch and two-hump fixtures); the transition machinery sees
a smooth saddle instead of a crease, and whatever interval it still refuses is handled by rule 3.

## 3. Full-width seam stones

RULE 3.1. Where a band is refused at the (now smooth) meeting, the closer ABSORBS ADJACENT BANDS
up to at least one full Course Height of field interval before cutting stones, so seam stones
carry ordinary course width. The sliver is never tiled on its own again.

RULE 3.2. THE INDISTINGUISHABILITY PIN, his acceptance: on every merge fixture, the closer
stones' span statistics sit inside the adjacent courses' range ALONG the seam AND their widths
sit inside the adjacent courses' width range ACROSS it, both asserted, both proved red by
re-shrinking the interval. A reviewer who can pick the seam stones out of a screenshot by size
or rhythm fails the task even if the numbers pass; say so in the review brief.

## 4. Riding in the same wave

The Skin slider rename: "Extrude" (EX) becomes "Gaps" (index unchanged, wires safe), his words:
"extrude is a bit confusing to what it actually does". Port text says what the slider does:
0 seals the joints into the offset shell, 1 opens them in proportion to curvature times
thickness. Every pinned port-name string moves with it, re-measured.

## 5. Explicitly out of scope

The computation-time wave (its own task, measured profiling first). The honeycomb closer
deferral stands. The mechanism collector stands held per Param's queue ruling.
