# Skin: one tessellation component, three patterns

Date: 2026-08-31. Status: approved design, awaiting Param's spec review.
Companion to docs/superpowers/specs/2026-08-31-readers-design.md and built after it; that
spec's inherited rules (RES first, aligned trees, name-comparing load warning, ForceUnit)
bind here too.

## 1. Purpose

Two components propose tessellations today and neither is the skin authoring tool the
workflow needs. Skin (04 Read) emits one polyline per thrust-mesh face banded into
courses: raw faces, no control, outputs hidden so nothing previews, and since the surface
rework Export builds the identical cells itself when nothing is wired. Armadillo Dual
(05 Deliver) generates the force-aligned dual in the worker: on the review vault it
produced 57 cells and dropped 28 of them for plan overlap, and its size control gives no
uniformity. This spec replaces both with ONE component named Skin: a proposer that
generates the buildable skin layout directly on the thrust surface with real control in
the two surface directions, previews on canvas, and feeds Export and Grasshopper alike.

The Bench Studio build algorithm (COMPAS-UI-integration-tool, bench/studio/generators.py)
is the measured precedent: its bonded-courses generator divides each course at uniform
arc length (equal-angle division measured up to 13.8x piece-size variance before the
2026-08-18 fix), staggers alternate courses by half a piece, and sorts cells by course
then position, which the studio uses as the build sequence. The courses pattern below is
that algorithm restated on the thrust surface itself.

## 2. Identity

Name "Skin", the component GUID of the old Skin (7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063)
KEPT, so a saved definition's Skin placement becomes the new component under the load
warning rather than an orphan. Panel 05 Deliver, beside Export, where its predecessor
Armadillo Dual sat: it proposes the cut, Export writes it. Its outputs are VISIBLE, the
proposer convention Armadillo Dual set, because seeing the pattern the moment it computes
is the point of the component. Message line: "12 cells · 8 courses · hexagonal" and the like. The Armadillo Dual component class is deleted and its GUID
(51f4ade8-f918-4455-9823-563afbf201f4) is not reused; saved placements orphan.

## 3. Ports

Inputs:

- Result RES (0): a solved Result. The two native patterns need a TNA Result with faces;
  an FD Result gives empty outputs and a Remark, the old Skin's rule. The force-aligned
  pattern hands the Result to the worker unchanged and inherits its refusal rules.
- Pattern P (1): integer, default 0, with a value list offered on right-click the way
  Columns' Type is: `0 · courses`, `1 · hexagonal`, `2 · force aligned`.
- Size S (2): target piece length along the course, metres, default 0.6, optional. The
  floor is 1 mm, the Armadillo Dual guard (a NaN or non-positive S is refused with the
  same negated-comparison guard).
- Course Height CH (3): course rise, metres, default 0.35, optional, same 1 mm floor and
  fallback warning the old Skin used. S and CH are the two-direction size control;
  pattern 2 reads S alone, as Armadillo Dual did, and ignores CH.

Outputs:

- Cells C (0): one closed polyline per cell, on the thrust surface, as a TREE branched by
  COURSE (path = course, 0 up from the bottom). Wire into Export's Cells; Export flattens
  and projects itself, unchanged.
- Courses CO (1): the course per cell, an integer tree branched and ordered exactly as
  Cells, the index repeated per item, so the pairing survives Export's flatten.
- Flowlines FL (2): the advected flow lines, force-aligned pattern only; empty for the
  native patterns.
- Diagnostics D (3): readable text. Native patterns: the pattern name, cell and course
  counts, mean/min/max piece length, the stagger, and the count of boundary-clipped
  cells. Force aligned: the worker's diagnostics text verbatim, as today.

Within each course branch, cells are ordered along the course, which hands the studio its
build sequence for free (it sorts by course then position).

## 4. The setout map (shared by courses and hexagonal)

Both native patterns are drawn in a surface coordinate system (u, z) and mapped onto the
thrust surface. The engine works on the Result's own vertex and face arrays, no
RhinoCommon in the maths, so the harness can measure it; PolylineCurves are built only at
the output boundary, the FrameGeometry Read/Build split.

- Level curves: the thrust surface is cut at heights z_min + r*CH. Each cut is traced
  across the mesh faces into one or more polyline components. A component is OPEN (a
  strip ending on the boundary, the barrel case) or CLOSED (a loop, the dome case).
- The seam: every level curve needs a u origin. An open strip's seam is its arc-length
  MIDPOINT, so setout is centre-outward and mirror-symmetric geometry gets
  mirror-symmetric joints by construction. A closed loop's seam is propagated from the
  loop below it (nearest point in plan to the lower seam); the lowest loop's seam is the
  vertex nearest the +X direction from its plan centroid, deterministic and stated.
- The map: (u, z) is the point at signed arc length u from the seam along the level curve
  at height z (curves interpolated between cut heights where a vertex falls between
  them). Where a height has several components, each component is set out independently,
  matched to the component below it by plan overlap.

Because a TNA thrust surface is a height field, any cells set out through this map
project to plan without overlap; the plan-degeneracy losses that halved the Armadillo
Dual pattern cannot occur on the native patterns, and the harness asserts it.

## 5. Pattern 0: courses

Running-bond quads, the Bench Studio algorithm on the surface:

- Bands: course r spans heights [z_min + r*CH, z_min + (r+1)*CH). The top band runs
  to the crown; when its rise is under a quarter of CH it merges into the band below
  rather than shipping a sliver course.
- Joints: on each band's MID-height level curve, the pitch is P = L / n with n = max(1,
  round(L / S)) and L the curve's arc length, so pieces land as close to S as the length
  allows and are uniform within the course. On a CLOSED loop the course is simply n equal
  pieces, the division rotated half a pitch on odd courses. On an OPEN strip the joints
  lie on a grid of pitch P anchored at the seam, phase zero on even courses (a joint at
  the seam) and half a pitch on odd courses (a piece centred on the seam), truncated at
  the strip's ends: interior pieces are exactly P and only the two end pieces absorb the
  phase, so every course is individually symmetric about the seam and adjacent courses
  carry the half-piece stagger.
- Cells: each joint maps to the band's lower and upper level curves by normalised arc
  length measured from the matching seams. A cell's outline is the lower curve's sampled
  run between two adjacent joints, the straight joint edge up, the upper curve's run back
  and the closing joint edge down: closed, on the surface, non-folding.

## 6. Pattern 1: hexagonal

A stretched honeycomb in the setout plane, width S and height 2*CH, so the bond reads
at the same course rhythm as pattern 0:

- The cell: a flat-topped hexagon centred at (uc, zc) with vertices, in order, (uc - S/4,
  zc - CH), (uc + S/4, zc - CH), (uc + S/2, zc), (uc + S/4, zc + CH), (uc - S/4,
  zc + CH), (uc - S/2, zc).
- The lattice: generated by the translations (0.75*S, CH) and (0, 2*CH), which tiles
  the plane with these cells exactly; centres are laid out from the seam outward so the
  crown column of cells sits on the seam and symmetric geometry gets a symmetric
  honeycomb.
- Mapping and clipping: each vertex is evaluated through the setout map at its own
  height. A cell crossing the surface boundary or the crown is CLIPPED to it, taking the
  boundary polyline as its edge; every clipped cell is kept (a coverage hole is worse
  than an odd-shaped rim piece) and counted in Diagnostics. Cell edges between mapped
  vertices are straight chords; the two horizontal edges follow their level curves.
- Course index: the band holding the cell's centroid height, for the CO output and the
  tree path.

## 7. Pattern 2: force aligned

The Armadillo Dual engine, moved in behind the Pattern flag and otherwise untouched this
round: the same worker command (pattern.armadillo_dual), the same RawWire-forwarding
dispatch, the same async task pattern with the cancellation recompute, the same decode,
warnings and diagnostics text, the same S floor. Its known limits (non-uniformity, the
plan-overlap drops) are accepted and stay on the ledger as later work; the component
exists so the force-aligned cut stays available for comparison against the structured
patterns. The two native patterns compute synchronously on the solve thread; only pattern
2 dispatches the worker.

## 8. Export and the old components

Export is untouched: C and CO wire into Cells and Courses as before, Export projects to
plan and writes the bench.tessellation/1 sidecar, and its unwired default (one cell per
thrust-mesh face, course 0) stays. The FacePolylines helper Export calls
(DeliveryComponents.cs line 1055 today) remains an internal static on the Skin class with
its signature unchanged, so Export's call site does not move. The old Skin's
FaceCourses/course-banding logic is superseded by the courses engine; the old
ArmadilloDualComponent file's dispatch and decode logic moves into the new Skin's pattern
2 rather than being rewritten.

## 9. Loading old definitions

- Old Skin placements load as the new component (same GUID) and the name warning fires:
  input 1 was "Course Height" and is now "Pattern", so a wired CH slider must move to
  slot 3; outputs 0 and 1 keep their meanings (cells tree, courses tree) under new names,
  so those wires stand.
- Armadillo Dual placements orphan; the author places a Skin and sets Pattern 2. RES and
  S rewire; C, CO, FL, D land on the same meanings in the same order.

## 10. Icons, panels, taxonomy, counts

The icon map's skin entry keeps its key and SK label and moves to category 05 Deliver
(fill #765300); the armadillo_dual entry is deleted; icons regenerate and --check stays
byte-green. The taxonomy replaces the Skin and Armadillo Dual rows with one Skin row in
05 Deliver. The component count moves from twenty-two (after the readers rework) to
twenty-one.

## 11. Harness

On a hand-built barrel fixture (open strips) and a dome fixture (closed loops):

- Courses: piece lengths within a course equal to within tolerance; adjacent courses
  staggered by half a piece; a mirror-symmetric fixture produces mirror-symmetric joint
  positions; every cell closed; the cells' plan projections pairwise disjoint and simple
  (the height-field guarantee, asserted).
- Hexagonal: interior cells six-sided with the stated vertex offsets; lattice neighbours
  share edges; course indices follow centroid bands; clipped rim cells present, none
  dropped; plan projections disjoint and simple.
- Both: C and CO trees aligned branch for branch and item for item; FD Result gives empty
  outputs and the Remark; S and CH floors enforced.
- Identity: the Skin GUID pin unchanged; the Armadillo Dual GUID absent; the Pattern
  value list pins; the component count pin at twenty-one; the icon map pins.
- Pattern 2 keeps the existing Armadillo Dual checks, re-pointed.

## 12. Out of scope

Improving the force-aligned engine's uniformity or projection losses; the studio's other
planned patterns (guastavino herringbone, diagrid, spiral); voussoir solid generation
(the studio owns thickness and solids); the UI-to-Grasshopper analysis back-channel; the
columns placement redesign.
