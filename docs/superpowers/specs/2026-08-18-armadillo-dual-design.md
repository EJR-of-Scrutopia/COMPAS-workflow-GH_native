# Wave 6c: the Armadillo force-aligned dual

Date: 2026-08-18, agreed with Param. Decisions taken in the brainstorm:
TRUE DUAL voussoirs (the BRG-literal reading, not force-aligned
courses); alignment driven by the contract's MEMBER FORCES with a
FALLBACK to the compas form/force diagrams; APPROACH 1 (plugin-side
generator, sidecar delivery through the authored-cut path proven
end to end on 2026-08-18). Fixture: Param's "Aramdillo style" export;
reference data: the real BRG Armadillo primal already local at
bench/upstream/compas_dem/data/armadillo.json (1038 triangles; the
built vault had 399 voussoirs over a 16 m span).

## What it is

The cutting pattern of the Armadillo Vault (BRG/ETH 2016): an
anisotropic mesh aligned with the force flow, whose DUAL becomes the
blocks, so every joint runs ACROSS the thrust -- the property that
resists sliding in an unmortared vault. 6c generates that pattern in
Grasshopper from a solved Result and hands it to Bench Studio as an
authored tessellation.

## Component contract (plugin/native_v02)

A new component, name "Armadillo Dual", nickname "Dual", category
Delivery (it sits beside Export on the canvas and feeds it).

Inputs:
- RES (ResultParam, item): the solved FD or TNA Result.
- S (number, item, default 0.6): target voussoir size in metres,
  both the along-flow seed spacing and the across-flow streamline
  spacing. (The default read 0.4 as agreed; see "Retrospective
  corrections" (d) for the measurement that changed it.)

Outputs:
- C (curves, list): one CLOSED 3D polyline per voussoir cell, on the
  thrust surface. Wire into Export's Cells (Export projects to plan
  and writes the sidecar; this component never writes files).
- CO (integers, list): the course band per cell, aligned one to one
  with C, never sorted. Wire into Export's Courses.
- FL (curves, list): the advected flow lines, for eyeballing the
  force field on canvas before committing to a cut.
- D (text, item): diagnostics -- alignment source used (forces or
  diagrams), cell count, mean/min/max cell size, degenerate cells
  dropped, streamline count.

The component is a thin async dispatcher in the FdSolve/Export
pattern: pre-solve validates and posts the worker task, post-solve
converts the worker's plain-number response into Rhino curves. No
Rhino geometry crosses into the background task.

## Worker command (src/ananke_equilibrium/worker.py)

"pattern.armadillo_dual" joins ALLOWED_COMMANDS. Payload:
{"result": <RawWire verbatim when present, else the serialised
ResultDto -- same convention as export.compas>, "size": <metres>}.
Response: {"cells": [{"outline": [[x, y, z], ...], "course": int},
...], "flowlines": [[[x, y, z], ...], ...], "diagnostics": {...}}.
All plain JSON numbers; the C# side owns curve construction.

## Algorithm (src/ananke_equilibrium/patterns/armadillo_dual.py)

Pure functions, numpy ONLY: the live Rhino site-env
(catenary-compas-2026) has numpy 2.0.2 and compas 2.15.1 but NO
scipy, so nothing may import scipy. The repo venv used for tests has
more; the module must not.

1. MESH AND FORCES: assemble the thrust mesh (vertices, faces,
   edges) and per-edge member forces from the result payload, the
   same way export.compas already assembles its thrustMesh. Faces
   are triangles or quads; work on the triangulated form.
2. LINE FIELD: per face, the thrust direction is the force-weighted
   sum of its edges' direction vectors. This is a LINE field, not a
   vector field (a direction and its negation are the same thing),
   so smoothing and averaging happen in doubled-angle space (2-theta
   representation) in the face plane. Smooth with exactly 3
   neighbour-averaging passes (a constant, not a knob).
3. FALLBACK: when member forces are absent or all zero, the field
   comes from the form diagram's edge directions weighted by force
   density (the compas formDiagram/forceDiagram pair in the result
   payload). When neither forces nor diagrams exist, the command
   REFUSES with a message naming both absences. No curvature
   guessing, ever.
4. STREAMLINES: advect polylines across faces along the line field,
   starting from a seed band at the springing -- the vertices named
   by the result's own support mappings (resolvedSupportNodeIds /
   Mappings.Supports), never inferred -- neighbouring lines spaced S
   apart; a line terminates
   at the boundary or where spacing collapses below 0.6 S, and a new
   line seeds where a gap exceeds 1.4 S.
5. SEEDS: a point every S along each streamline, staggered half a
   step on alternating streamlines (running bond in field space).
6. DUAL CELLS: discrete geodesic Voronoi of the seeds on the
   triangle mesh -- multi-source Dijkstra over the mesh's
   edge-weighted vertex graph, every vertex assigned to its nearest
   seed; each cell's outline is the closed chain along the
   assignment boundary (through edge midpoints where the two ends of
   an edge belong to different seeds), emitted as a closed 3D
   polyline on the surface. One smoothing pass on the chain. This is
   what makes multi-loop rims and the funnel's steepness non-issues
   for GENERATION: everything happens on the mesh graph, no plan
   domain, no boundary ring.
7. COURSES: a cell's course is its seed's along-flow band index (how
   many S-steps along its streamline from the springing), so
   neighbouring cells stagger the way the built vault's do.
8. HYGIENE: cells with fewer than 3 distinct corners or degenerate
   area are dropped and counted in diagnostics, never silently.

## Delivery and the honest limit

C and CO wire into Export's Tessellation format; the sidecar imports
into the studio through the authored-cut path shipped 2026-08-18.
That contract is PLAN-outline based, so voussoirs on near-vertical
stretches (the Armadillo funnel's throat) may project degenerately
and be dropped-and-disclosed by the studio's existing machinery. That
is a KNOWN, NAMED limit of bench.tessellation/1, recorded here and in
the component's D output when plan-degenerate cells are detectable; a
surface-parameterised bench.tessellation/2 lifts it and is OUT OF
SCOPE for 6c.

## Out of scope

- A server-side generator in the studio (the dropdown's 6c entry
  gains a one-line pointer to this component instead).
- bench.tessellation/2 (3D outlines).
- Anisotropy ratio controls, custom seed bands, per-region size
  fields: S is the one knob until real use demands more.

## Testing

- Worker tests (repo venv, pytest, following the existing worker
  test layout): a synthetic dome fixture (analytic meridian field:
  streamlines follow meridians within tolerance, voussoir count
  scales with 1/S^2, courses band monotonically with height); the
  real BRG armadillo.json primal (field builds from its data, cell
  count lands in the low hundreds at S = 0.75 on the 16 m span, zero
  crashes, dropped-count small and disclosed); the refusal path (no
  forces, no diagrams); the fallback path (forces stripped, diagrams
  present).
- C# component: build clean; codec/unit tests only where the
  existing component test pattern reaches.
- Acceptance: the BRG armadillo run scripted in tests, and Param's
  own fixture driven live through GH -> Export -> studio import,
  dual voussoirs standing in the viewport.
- No em dashes (U+2014; ASCII "--" fine); no AI attribution; commit
  per task; NEVER push; final step rebuilds and installs the .gha
  with Rhino closed and tells Param to restart Rhino.

## Retrospective corrections

Added by the wave's final fix review, 2026-08-19, after the plan above
had shipped and been measured against the real BRG armadillo primal.

(a) THE D OUTPUT'S PLAN-DEGENERACY DISCLOSURE ("Delivery and the
honest limit", above) says the named limit is "recorded here and in
the component's D output when plan-degenerate cells are detectable".
It was recorded here only. Nothing in `generate()`'s diagnostics
counted such cells and nothing in `FormatDiagnostics` printed one,
while at S = 0.75 on the reference primal 15 emitted cells did
self-cross in plan and 3 pairs overlapped once flattened -- and the
studio rejects the WHOLE sidecar, by cell key, on the first of either.
Now delivered: `diagnostics["plan_degenerate"]` counts emitted cells
whose plan projection is not a simple polygon by the studio's own
rule (a numpy port of `bench/studio/tessellation.py`'s `_is_simple`,
checked cell by cell against that function itself in
tests/patterns/test_armadillo_dual_studio_acceptance.py), and D
carries a line naming the count and what to do about it. Cross-cell
plan OVERLAP is still not counted: it is a property of a cell SET,
not of a cell, and the acceptance script that does resolve it stays
the place that measures it.

(b) COURSE IS FLOW ORDER, NOT HEIGHT ORDER. Step 7 above defines a
cell's course as "its seed's along-flow band index (how many S-steps
along its streamline from the springing)", and that is exactly what
ships. What the spec never says, and what a reader coming from Bench
Studio's rim-to-crown reading of "course" will assume, is that the
two coincide. On a real vault they do not: measured on the BRG primal,
7 of 39 streamlines rise and then descend by more than 0.5 m, so
their later bands sit LOWER than earlier ones. Course is flow order.
`generate()`'s docstring now says so in as many words.

(c) THE DUAL'S INTERNAL REFINEMENT IS ADAPTIVE. Step 6 above describes
the geodesic Voronoi without saying anything about mesh resolution,
and what shipped refined the mesh exactly once. On the reference
primal that left a 0.512 m refined median edge against a 0.75 m seed
spacing: a median seed owned 3 refined vertices, its boundary came out
as several disconnected splinters, and `dual_cells` kept the longest
splinter and silently discarded the rest -- 5.9% of the surface
emitted, from an assignment that was exact and covered all of it. The
refinement now repeats until the refined median edge is at most 0.3 * S,
capped at 4 passes (each quadruples the triangle count) with the cap
disclosed in diagnostics when it bites; and every chain of a seed is
accounted for, as interior holes (`diagnostics["holes_ignored"]`) when
they lie inside the largest chain, or as a REJECTION of the whole seed
into the dropped count when the territory is genuinely disconnected.

(d) THE S DEFAULT IS 0.6, NOT 0.4. The 0.4 agreed in the brainstorm
was never measured on the reference vault. It is now, and it fails the
mean-cell-size bar: at 0.4 the primal gives 687 seeds and 682 cells
(0.7% dropped, 89.0% surface coverage) with a mean cell size of
0.671 m against a 0.600 m ceiling, because this vault's streamlines
fan out from the springing without mid-mesh backfill, so halving S
does not halve the cell. Measured on a 0.05 m grid: 0.50 fails
(0.752 against 0.750), 0.55 clears by 1.1%, 0.60 clears by 5.2%
(0.853 against 0.900). 0.6 ships, named once in
`armadillo_dual.DEFAULT_SIZE` and mirrored by the component's own
`DefaultSize`.

(e) THE DOMINANT CAUSE OF THE 5.9% WAS AN INDEXING DEFECT, NOT THE
REFINEMENT. Correction (c) above records under-refinement and the
longest-chain discard; both were real, but neither was the dominant
mechanism. `_cell_segments`' two-owned-vertices branch read the
non-owned CORNER INDEX (a local 0/1/2) as a mesh VERTEX ID, so the
boundary broke apart at every such triangle -- 12179 of the 12670
mixed triangles on the reference run at S = 0.75, 96% of the whole
assignment boundary. Measured by the merge re-review with the old
branch body restored against the otherwise-fixed module: 0 cells of
300 seeds, 299 territories reading as disconnected. Adaptive
refinement alone could not have recovered a single voussoir. The fix
is one line (`j = triangle[non_k_indices[0]]`), recorded beside the
code with this history; the module was swept and no other site mixes
the two index spaces.
