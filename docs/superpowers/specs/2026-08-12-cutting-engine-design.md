# Studio Wave 6a: The Cutting Engine and the Generator Interface

## What is wrong now

The studio does not cut the vault into pieces. It bins whole analysis-mesh
faces: each face centroid is tested for the ring and wedge it lands in, and
a cell is whatever set of faces answered the same way. A cell boundary
therefore staircases along mesh edges, and it can only ever be as straight
as the mesh happens to be.

Measured on the Trial 2 export at eight rings:

```text
cell        faces   boundary edges   corner runs
(0, 3)         70               66             4
(0, 4)         35               30             3
(1, 0)         66               86             3
```

A four-sided voussoir has four boundary edges. These have thirty to
eighty-six. That is the jaggedness in the browser. No amount of texture or
material work hides it, because the shape itself is wrong. Wave 5 gave
those cells flat joints and curved caps, which made them read as castings,
but a casting with eighty-six sides is still a casting with eighty-six
sides.

## The idea

Decide the cut first, then cut the surface to it.

A pattern produces outlines: closed polygons in the plan of the vault. The
engine welds their corners, resolves T junctions, checks that they cover
the surface exactly once, and then builds each piece by triangulating its
own outline and lifting the result onto the thrust surface. The piece
boundary is the outline, exactly, because the outline is what it was built
from. Neighbouring pieces share boundary points, so their joints match by
construction rather than by later agreement.

The point of the wave is not the two patterns it ships. It is the seam
those patterns sit behind. Param's own tessellations will come from
Grasshopper, where the control and the design intent belong; the studio's
built-in patterns exist so that materiality, engineering, rendering and
animation are all working before those arrive. So the interface is the
deliverable, and an imported tessellation is a first-class generator in
this wave, not a later bolt-on.

## The domain

Parametric patterns need somewhere to be drawn. That place is a normalised
polar domain built from the vault's own plan boundary, not from a circle.

`domain.py` takes the analysis mesh, finds its boundary loop, projects it
to plan, and takes the axis as the mean of the face centroids (the same
axis the current binning uses, so the existing views stay recognisable).
It then samples the boundary radius as a function of angle, `rho_b(theta)`,
and exposes the mapping

```text
plan(f, theta) = axis + f * rho_b(theta) * (cos theta, sin theta)
```

So `f = 1` is the real rim at every angle, and a course boundary at
`f = 0.4` follows the real plan shape rather than cutting across it. This
is what makes generated pieces fit a vault that is not a disc, without a
polygon clipper.

It has one precondition: the plan boundary must be star shaped about the
axis, meaning every ray from the axis crosses it exactly once. `domain.py`
checks this by sampling and reports failure with the offending angle and
the number of crossings found. A vault with an oculus, or a strongly
re-entrant plan, will fail that check. That is not a bug to be papered
over: parametric polar patterns genuinely cannot cover such a plan, and
the honest answer is the message plus the imported route. Trial 2 must be
verified as star shaped as part of this wave, and the result recorded.

## The tessellation contract

This is the shape a piece takes when it crosses from Grasshopper, and it
is the part worth getting right now, because three waves will be built on
it.

A tessellation arrives either embedded in the contract JSON under a
`tessellation` key, or as a sidecar file beside the export named
`<export>-tessellation.json`. The contract wins if both exist. Neither
present means the studio generates one.

```json
{
  "tessellation": {
    "schema": "bench.tessellation/1",
    "units": "m",
    "domain": "plan",
    "pattern": "guastavino-herringbone",
    "cells": [
      {
        "key": "t0007",
        "course": 3,
        "outline": [[1.82, 0.44], [2.61, 0.44], [2.55, 1.19], [1.78, 1.16]],
        "holes": []
      }
    ],
    "provenance": {
      "source": "Grasshopper",
      "author": "...",
      "authored": "2026-08-14",
      "note": "free text, quoted verbatim in the Data panel"
    }
  }
}
```

The rules, all of them enforced and all of them reported by cell key when
broken:

- `outline` is a simple closed polygon, counter clockwise, with no
  repeated final point. Two points are the same point within 1e-6 m.
- Points may be `[x, y]` or `[x, y, z]`. The surface owns z: a supplied z
  is not used for geometry, but the engine reports the largest difference
  between a supplied z and the surface height under it, so an author who
  drew on the wrong surface finds out rather than being silently corrected.
- `course` is the placement group, 0 at the rim and increasing toward the
  crown. It drives the staging sequence, and it replaces the ring index
  everywhere the studio used one. It may be omitted, in which case the
  engine assigns it from the cell centroid's `f`, and says so.
- `key` is unique across the tessellation and stable across reloads. It is
  the casting's identity: its tint, its texture offset and its place in the
  drop order all hang off it.
- `holes` is optional, a list of outlines lying strictly inside the
  outline. A cell with a hole is one piece with a hole in it, which is a
  real case and not two pieces. Hole winding is normalised by the engine,
  so an author does not have to remember which way round it goes.
- Cells may not overlap, and together they must cover the surface. T
  junctions are allowed and expected, because bonded masonry is made of
  them; the engine resolves them.

`units` must be `"m"` and `domain` must be `"plan"` in this schema
version. Anything else is rejected by name rather than guessed at, so the
next schema version can add an on-surface domain without ambiguity.

## Generators shipped in this wave

Behind the interface, three implementations:

**Bonded courses.** Courses from the rim to the crown at the target piece
size, each course divided into pieces at the same target size measured
along its own mid-course circumference, and each course offset by half a
piece from the one below, so the head joints stagger rather than line up
into a continuous radial crack. This is the brick logic, and it is what
the current ring and wedge binning was always trying to be.

**Monolithic bands.** One continuous cell per course, no head joints at
all. This is sprayed concrete: it is applied in passes, it has no
castings, and it should not pretend to. Bands keep the staging sequence
and the growth animation meaningful, which a single whole-vault cell would
destroy.

**Imported.** The contract route above.

Nothing else. Herringbone, hexagons, diagrid and spiral are wave 6b; the
force-aligned Armadillo tessellation is wave 6c. Shipping two patterns and
one importer is enough to prove the seam, and the seam is the wave.

## How a cell becomes a piece

One pipeline, in `tessellation.py` and `cutting.py`, with `pieces.py`
keeping the joint work it already does well:

1. **Weld.** Every outline point from every cell enters one global vertex
   table, matched within 1e-6 m. Two cells that name the same corner get
   the same index, which is what makes their joints coincide.
2. **Resolve T junctions.** An edge that passes through another cell's
   welded vertex, within 1e-6 m of the segment, splits there. After this
   pass every sub-edge is bounded by welded vertices and is shared whole
   or not at all. This is what lets a stretcher above two half pieces be
   conforming without forcing every course to line up.
3. **Densify.** Every sub-edge is subdivided to the cap edge target,
   globally, before anything is lifted, so both owners of a sub-edge see
   the identical chain of points. Densifying afterwards, per piece, is how
   two neighbours end up with boundaries that nearly match. Densification
   adds points along a sub-edge; it does not create new sub-edges. A joint
   is still one flat cut with a chain of points across it, which is
   exactly the shape wave 5's `run_plane` already takes.
4. **Validate.** Every interior sub-edge has exactly two owners; every
   analysis-mesh face centroid falls inside exactly one cell. Orphans and
   doubles are counted and named, not summed into a pass or fail.
5. **Lift.** Each welded point is located in the render mesh in plan, and
   its height, its surface normal and its field weights come from that
   face. The field weights are the point's barycentric weights on that
   face's vertices.
6. **Cap.** Each cell's outline, with its densified boundary points, is
   triangulated by ear clipping and then refined by longest-edge bisection
   until the cap follows the surface. Boundary edges are never split by
   refinement, because they were already densified in step 3 and splitting
   them now would break the neighbour. Interior points are lifted the same
   way as boundary ones.
7. **Joint facets.** Every sub-edge is one planar joint. Its plane runs
   through the sub-edge's two corners along the average surface normal of
   its chain, which is `run_plane` unchanged from wave 5; interior chain
   points are projected onto it, and the vertex normals with them, so the
   wall over the sub-edge is genuinely flat rather than nearly flat.

Wave 5's corner problem survives this change unaltered and so does its
solution. A corner belongs to two joints, one stored normal cannot lie in
both planes, so exactly one incident sub-edge owns each corner's normal,
chosen by a global rule that both neighbours compute identically. What
changes is the scale: a piece has a handful of sub-edges instead of a
chain of eighty-six mesh edges, so the residual is being disclosed on a
far smaller set. The measured residual must be re-taken on the new
geometry and the disclosure updated with it, since wave 5's figure
describes a drawing this wave replaces.

The cap refinement target: refine until the maximum chord deviation is at
or below 5 mm, or until no interior edge exceeds 0.1 m, whichever comes
first. Chord deviation is measured by lifting each cap triangle's plan
centroid onto the surface and taking its distance to the plane of that
triangle's three lifted corners. Both the achieved deviation and which
limit stopped the refinement are reported, per study, in the Data panel.

## Fields follow the cut

Today each piece vertex carries `sources`, the index of the render-mesh
vertex it came from, and every field lookup and the displacement
exaggeration read straight through it. Cut pieces do not sit on mesh
vertices, so that index no longer exists.

`sources` becomes a list of index and weight pairs per vertex, two to four
of them, summing to one. Every consumer becomes a weighted sum of what it
already read. The old behaviour is the special case where a vertex
coincides with a mesh vertex and the single weight is one, which is worth
testing explicitly because it is the case that proves the generalisation
did not shift the fields.

This is the load-bearing change in the viewer, and it is the reason the
stress and deflection heatmaps keep their meaning after the cut. It is
interpolation of the solved field, not resampling or smoothing of it.

## Size in metres, not rings

The rings slider goes. Its replacement is a target piece size in metres,
from 0.3 to 3.0, default 0.9, in 0.05 steps, with the resulting piece
count shown live beside it. Size is what handling, transport and robot
reach are actually constrained by; ring counts were a proxy for it.

The consequences are mechanical and must all be carried:

- The API takes `size` in metres instead of `rings`, validated to that
  range, and rejects out-of-range values by name as it does today.
- Bundle and staging cache filenames key on size in millimetres instead of
  ring count, so old and new caches cannot collide.
- The HUD and Data panel report the target size, the achieved piece count,
  and the course count that came out of it.
- Two exports at the same size setting will give different piece counts.
  That is correct, and the readout is what tells the truth about it.

## What deliberately does not move

The analysis side keeps consuming exactly what it consumes today. As a by
product of validation the engine already knows which cell owns each
analysis-mesh face centroid, so it emits that map in the same shape the
old binning emitted `assignment`, and `staging.py` and `voussoirs.py` keep
working unchanged against it, with `course` where they used the ring index.

This is a deliberate limit. It means the CRA blocks are still built from
whole mesh faces and are therefore still faceted, while the drawn pieces
are cut cleanly. Unifying the two is real work and it belongs with the CRA
rescue, not here. The wave must not claim otherwise anywhere in the UI.

Also unchanged: the FEA path and every verdict it produces, which run on
the analysis mesh and never saw pieces; the CRA machinery, its block
budget and its honest nulls; the timeline, the purity of `applyTimeline`
and `applySceneAtTime`, and record mode; every existing layer, the legend
and the transport controls.

One consequence worth stating plainly rather than discovering later: at a
0.9 m target size a bonded-course tessellation of Trial 2 has far more
than fourteen cells, so CRA will skip those stages with the message it
already has. This wave does not rescue CRA and does not pretend to.

## Materials

Three presets join the four that exist, with sourced values in the same
style, and the Data panel quotes them as it quotes the others:

- **Brick**, 1900 kg/m3. EN 1991-1-1 Annex A Table A.1 gives clay masonry
  in the range 18 to 22 kN/m3; 1900 kg/m3 sits inside it. Friction 0.6,
  the same mortar-joint value the concrete presets carry from
  EN 1992-1-1 clause 6.2.5.
- **Tile**, 1800 kg/m3, fired clay tile for Guastavino work, a literature
  value with no Eurocode entry of its own, recorded as such in the same
  way timber's friction already is. Friction 0.6.
- **Stone**, 2500 kg/m3, limestone, the Armadillo Vault's own material.
  Friction 0.6, the middle of the 0.5 to 0.7 span that the dry-stone
  rigid-block literature uses, and deliberately not quoted more precisely
  than that.

Appearance must separate them at a glance, the way wave 5 separated the
four concretes: brick warm red-brown and matt, tile thinner and lighter
with a fired sheen, stone pale and mineral. The closest-pair luminance
check that wave 5 introduced covers seven presets after this wave, not
four, and it must be keyed by preset name rather than by position in the
registry, since this wave inserts entries.

## Pattern is not material

Pattern and material are separate controls. Each material carries a
default pattern, and the default is overridable, so "stone in bonded
courses" and "brick in bands" are both askable. In this wave the defaults
are bonded courses for brick, tile, stone, timber and both cast concretes,
and monolithic bands for sprayed concrete.

Tile defaults to bonded courses and not to Guastavino herringbone, and
stone defaults to bonded courses and not to the Armadillo dual, because
neither pattern exists yet. Where a material's intended pattern has not
shipped, the pattern control says so in as many words. A studio that
quietly draws courses while the label says Guastavino is the same class of
dishonesty as a verdict quoting a withdrawn number.

## What is retired

`binning.js` and the segmentation mirror banner go. The client stopped
binning when the rings slider was fixed to follow the loaded bundle; it
computes a local binning now solely to compare it with the shipped one.
With the tessellation built server side and shipped whole, the mirror has
nothing left to mirror, and retiring it removes a duplicated
implementation rather than adding one. Its tests go with the code they
pin, not weakened.

`segmentation.py` stays only if something still calls it after the
tessellation lands. If nothing does, it goes too, and the wave says which
happened.

## Testing

- Joint facets per piece, on the real Trial 2 export, bounded and
  asserted. A bonded-course quad has four sides, of which the bed joints
  may split at T junctions, so the bound is small and single figured. The
  count is of facets, meaning sub-edges after T junction resolution, not
  of boundary points after densification; both numbers are recorded, and
  this is the direct replacement for the measurement at the top of this
  document.
- Welding, T junction resolution and conformity: every interior sub-edge
  has exactly two owners, on a fixture built to contain a T junction
  deliberately.
- Coverage: every analysis-mesh face centroid lands in exactly one cell,
  with orphan and double counts asserted at zero.
- Cap accuracy: maximum chord deviation at or below the 5 mm target, or
  the edge floor reached, with both numbers reported.
- Joint planarity to 1e-9 for the owning facet, neighbour agreement exact
  on shared points, and the corner residual re-measured and pinned on the
  new geometry.
- Field weights: they sum to one, every index is a real render-mesh
  vertex, and a piece vertex coincident with a mesh vertex reduces to a
  single weight of one.
- Domain: the star-shape check passes on Trial 2 and fails, with its angle
  reported, on a fixture built to break it.
- Imported tessellations: a valid one is accepted and drawn; overlapping
  cells, an unclosed or self-intersecting outline, a duplicate key and an
  unknown `units` are each rejected naming the offending cell; a supplied
  z that misses the surface is reported rather than silently used.
- Sizing: the piece count moves monotonically with the size slider, and
  the reported count equals the number of pieces actually drawn.
- The existing guards all keep passing: the server import guard (this is
  all stdlib, on the bundle path), the offline check on the page and its
  scripts, and the `applyTimeline` purity pin.

## Measurements to report

This wave exists because of a measurement, so it closes with them, in
`BENCH.md` and in the Data panel where the user can see them:

- Boundary sub-edges per piece, before and after, on Trial 2.
- Piece count and course count at the default size.
- Maximum cap chord deviation, and which limit stopped refinement.
- The corner normal residual on the new geometry.
- Whether Trial 2's plan boundary is star shaped.

## Risks and honest limits

- The star-shape precondition is real and will exclude some plans. The
  message and the imported route are the answer, not a fallback that
  produces something wrong.
- Ear clipping and longest-edge bisection are both well trodden, but a
  degenerate outline (a zero-area sliver from a pattern at an awkward
  size) will find their edges. Slivers must be detected and reported by
  cell key rather than triangulated into garbage.
- The analysis side stays faceted, as stated above.
- Fields become interpolated rather than looked up. That is more honest,
  not less, but it is a change in what a heatmap value at a point means,
  and the Data panel should say that pieces sample the solved field by
  interpolation.

## Out of scope

- Herringbone, hexagonal panels, diagrid and spiral patterns, wave 6b.
- The force-aligned Armadillo tessellation and loading the real Armadillo
  data for comparison, wave 6c.
- Rebuilding CRA blocks on the cut pieces, and CRA convergence above
  fourteen blocks.
- Making the crown taper structural.
- The HDRI environment, the camera spiral, placeable props and robots.
