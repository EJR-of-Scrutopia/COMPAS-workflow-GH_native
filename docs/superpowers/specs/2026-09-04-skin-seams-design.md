# The seams: the skin closes where its course families meet

Written overnight 2026-09-04. Binding inputs: Param's ruling of record (the closer band: cover
the refused interval by direct tessellation, no correspondence), his four requirements of
2026-09-03 23:40 given verbatim in .superpowers/sdd/2026-09-03-overnight/OVERNIGHT-PLAN.md item
3, the 2026-09-03 level-set diagnosis (adversarially verified), and his mirrored-ordering find
from the six-lobe test. Spec section 13.2 item 3 of the buildability design is CLOSED by this
document: the answer is the closer, not the hole, and the old refusal text gains an erratum
saying so when the closer lands.

## 1. What a seam is, and that it becomes data

Wherever level curves change count between two levels, correspondence fails and ResolveBands
refuses the interval (the bisected CH/64 sliver). Geometrically the refusal straddles the MEETING
LINE of two level-curve families: the arch's crown ring, the six-lobe's bay junctions, a groin.
RULE 1.1: the meeting line is recovered as a polyline, THE SEAM CURVE, by carrying the SEED
IDENTITY through the rim-distance marching (each vertex remembers which seed group reached it
first; an edge whose two ends were reached from different groups crosses the seam; the seam is
the chained dual of those edges). The diagnosis costed this as a two-line addition to the
marching plus the chaining. Seed groups are the connected components of the anchor set, computed
once in ReadNet. The seam curves are carried on the pattern result and drawn by diagnostics.

## 2. The closer band

RULE 2.1. WHERE. Every interval in resolved.Refused, in every pattern: closer cells are their own
species, built from the SURFACE, not from either course family, so one mechanism serves courses,
honeycomb and force-aligned alike. They are emitted at the band's own course index, so staging
and export see ordinary cells.

RULE 2.2. HOW. Take every face whose field values straddle [band.Low, band.High]; clip each to
the two level values (the tracer's own crossing arithmetic, reused); group the clipped polygons
into connected components; each component is one STRIP along the seam. Cut each strip by section
lines PERPENDICULAR TO THE SEAM CURVE at a spacing chosen from Size (rule 2.4), so the stones run
WITH the seam, elongated along it, head joints across it. That is Param's "following the force
path ... the tangent curvature of the mesh", and it is how groin masonry is coursed.

RULE 2.3. BONDING (his requirement c). A closer stone's long edges lie ON the two traced level
curves that bound the refused interval, so its corners land on the same curves the neighbouring
course cells' corners lie on, and the standing corner weld (1e-6 at Dedupe) fuses them. No chord
crosses the seam: where the strip narrows to nothing at a seam endpoint, the stone closes on the
seam curve itself.

RULE 2.4. SIMILAR SIZE, PINNED (his requirement b). The section spacing is Size scaled so that no
stone's span is under Min Piece's fraction of Size or over Size / MinPiece (the same bounds the
courses obey); remainders MERGE into their neighbour exactly as MergeShortPieces does along a
course. THE CHECK: on every fixture with a refused interval, the closer stones' span statistics
sit INSIDE the min-to-max range of the two adjacent ordinary courses, asserted, and proved red by
disabling the merge.

RULE 2.5. NO MORE DROPS AT THE SEAM (his requirement a). With the refused interval covered and
the force-aligned chain already bounded at its band (the 2026-09-03 defect fix), the plan-filter
drops at seams must fall to zero on the fixtures: asserted on the two-hump barrel and on the
crown-arch contract fixture, whose merge at course 19 of 21 is the measured case. The transition
warning becomes: "1 seam was CLOSED with N stones between d=a and d=b", a Remark, not a Warning.

RULE 2.6. THE CAP IS UNTOUCHED. A closed loop shrinking to an apex still caps (the apex is real
on these forms, measured); the closer serves intervals where curve COUNT changes, the cap serves
the top of a surviving closed loop. The two meet at most in sharing rule 1.1's seam data.

## 3. The within-course order (his mirrored-selection find)

RULE 3.1. The Cells tree keeps its shape (path = course; downstream contracts unmoved). WITHIN a
branch, cells are ordered COMPONENT BY COMPONENT (the traced level curve components, in a stable
order: by their seam-curve association, then by plan position of their starts), and within one
component by SIGNED ARC ALONG THE CURVE IN ONE CONSISTENT DIRECTION, the direction propagated
between courses by the existing seam alignment (NormaliseDirections already owns direction
propagation; the ordering reads it instead of fighting it).

RULE 3.2. THE CHECK: on a two-component fixture (the two-hump barrel), item k of consecutive
branches belongs to the SAME component and its plan position advances monotonically along that
component, for every k inside the shorter branch; proved red by restoring the old concatenation.
Closer cells sort at their component's position in the same scheme.

## 4. Honesty bounds

- This closes the SEAM-located losses. The loft-route thickening nulls are a different mechanism,
  owned by scripts/rhino_skin_surface.py 12.5(i), still unrun, still Param's five minutes.
- Like indices align down a meridian only as far as counts allow; where course cell counts
  change, alignment shifts by construction, and no rule here pretends otherwise.
- The honeycomb's own seam behaviour (per-chart refusals) is narrowed by the closer only where
  ResolveBands owns the refusal; the hexagon chart rules are untouched this wave.

## 5. Checks, each proved able to fail

1. Seam recovery: on the crown-arch fixture the seam curve exists, is one component, and lies
   within one mean edge length of the measured merge locus (field distance 9.72 of 10.454).
2. Coverage: the refused interval's plan area is covered by closer stones to the same
   plan-coverage ratio the adjacent courses achieve, within 2 per cent.
3. Size statistics inside neighbours' range (rule 2.4), red by disabling the merge.
4. Corner weld to both families (rule 2.3), red by skewing the clip level.
5. Zero seam drops on both merge fixtures (rule 2.5).
6. Ordering (rule 3.2), red by restoring concatenation.
7. TransitionBands semantics: the count reports seams CLOSED, the intervals still named; the
   harness's transition pins re-measured with reasons, never relaxed.
