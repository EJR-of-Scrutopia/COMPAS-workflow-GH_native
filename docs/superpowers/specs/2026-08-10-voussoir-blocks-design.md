# Voussoir Blocks for CRA

Bench Studio's rigid-block verdict is correct but unaffordable on real
geometry. A block today traces every analysis-mesh face inside its
ring/wedge cell, so it reaches the solver carrying 500 to 1700 faces, and
the joint between two blocks arrives as dozens of small triangles. A real
Trial 2 staged run at rings=2 timed out at 600 seconds on a stage of six
blocks, while cube fixtures of six faces each solve in about a second.
Block count was never the cost driver; mesh complexity and contact-point
count are.

This spec replaces the block model with voussoirs: one planar face per
neighbour, a top and a bottom cap, six to eight faces per block. It
changes nothing about the verdict logic, which is already correct.

## What a voussoir is here

For each cell of the segmentation:

1. Take the cell's boundary edges (edges used by exactly one of the cell's
   faces). This already exists as `blocks.segment_boundary_edges`.
2. Label each boundary edge with the cell on its far side: the edge's other
   user among all mesh faces, mapped through the segmentation assignment.
   An edge with no outside user is a free edge at the vault's rim, labelled
   as free.
3. Chain the boundary edges into an ordered loop, then split the loop into
   runs of consecutive edges sharing the same label. Each run is one joint
   with one neighbour, or one stretch of free edge.
4. The junctions between runs are the voussoir's corners. They are real
   mesh vertices, so neighbouring cells agree on them exactly.
5. Build the solid: for each corner, a top point (corner offset by
   +n * t/2 along the shared full-mesh vertex normal) and a bottom point
   (-n * t/2). Side faces span consecutive corner pairs through the
   thickness, one per run. Caps are polygons through the top corners and
   through the bottom corners.

Every face is triangulated with the shared-edge diagonal rule already in
`blocks.py`, so faces stay planar and two blocks meeting at a joint emit
identical triangles.

## Why neighbours still match

Two cells sharing a run derive that run's side face from the same corner
vertices and the same vertex normals, so their side faces are coincident by
construction, in the same way the current triangulated walls are. The
blocks tile a faceted version of the vault rather than the true curved one,
but they tile it consistently, and consistency is what contact detection
needs. Fidelity to the curve is the thing being traded away, deliberately.

## The approximation, stated

A voussoir replaces the curved boundary between corners with a straight
line, so its volume and centroid differ from the drawn segment. The viewer
keeps drawing the true curved geometry; the analysis runs on the faceted
model. The implementation measures the volume difference on the real Trial
2 export and reports it, and the Data panel states that the verdict
describes a faceted model with planar joints. This is disclosure of the
same kind already applied to the friction provenance.

## Degenerate cases, handled explicitly

- A cell whose boundary forms more than one loop is genuinely more than one
  piece (a ring's occupied wedges are not always contiguous). Each loop
  becomes its own voussoir, which is physically right: they are separate
  precast pieces. Support marking and ring/wedge tags carry to both.
- A loop with fewer than three runs cannot form a polyhedron with distinct
  side faces. Split the longest run at its midpoint vertex until there are
  at least three corners, so the solid is always well formed.
- A run of a single edge is fine and produces one side face.
- A cell with no boundary edges cannot happen (a cell always has a rim or a
  neighbour), but if the mesh produced one, the block is skipped and the
  stage's verdict records the skip rather than solving a wrong model.

## What does not change

- `solve_cra.py` keeps its three-state verdict, its tight fixed tmax, the
  penalty solver, and the tension check on the returned contact forces
  (peak tension over peak contact force against TENSION_TOLERANCE). That
  logic is already correct and is what makes a verdict trustworthy.
- The per-stage over-budget refusal and the CRA subprocess timeout stay as
  guards. Voussoirs should stop the budget from binding in practice, but
  the guard is not removed on an expectation: the acceptance gate measures
  it.
- Staging, the badge, the HUD line, the pulse and the friction provenance
  are untouched.
- The viewer's rendering is untouched.

## Testing

- Unit tests on a toy mesh with two cells: run labelling, loop chaining,
  run splitting, corner extraction, closed orientable manifold (every
  directed edge once, reverse present), face counts in the expected six to
  eight range, and coincident side faces between the two cells.
- A disconnected-cell fixture yielding two voussoirs.
- A degenerate two-run loop proving the split-to-three-corners rule.
- Volume comparison against the current mesh-following block on the real
  Trial 2 export, reported as a percentage, pinned loosely so a large
  regression fails but a small modelling difference does not.
- Real-solver tests in `.venv-cra` keep their existing fixtures and
  verdicts: a supported stack stands, a hanging block does not stand with
  status "tension at joints", isolated and empty cases refuse.
- The acceptance gate is the real test: a full staged run on the Trial 2
  export with real FEA and real CRA, reporting per-stage verdicts, block
  and interface counts, and wall-clock time. The wave is not finished until
  that run produces verdicts rather than timeouts, or produces measured
  evidence that it still cannot, in which case the finding is reported
  rather than papered over.

## Out of scope

- Drawing the voussoir model in the viewer as a layer.
- Any change to the FEA side.
- Mould clustering, concrete versus timber A/B, robot choreography: the
  remaining wave 4 items, each with its own spec.
