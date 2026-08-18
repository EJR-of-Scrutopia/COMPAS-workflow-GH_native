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
- S (number, item, default 0.4): target voussoir size in metres,
  both the along-flow seed spacing and the across-flow streamline
  spacing.

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
