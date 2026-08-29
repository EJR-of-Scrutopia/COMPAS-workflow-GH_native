# Animate: columns from frame zero, rotating up about a fixed foot

Date: 2026-08-28. Sub-project 4 of 6 from the mould rework brainstorm of
2026-08-27. Branch feature/animate-rigid-columns off plugin main a8b5936.
Implements section 10, second paragraph, of
docs/superpowers/specs/2026-08-27-res-spine-design.md, which is binding.

## 1. Why

Animate raised the columns by solving each foot's position per frame:
the foot lay out along a rail while the strut was retracted, slid in as
the notch rose, and the ram finished the reach; a shared foot was served
by the force-weighted centre of its trunks' heads; and the fork was
re-aimed per frame along a live thrust line from the main notch. Three
things are wrong with that after sub-project 3. The foot Columns builds
is now fixed by rule (a band's plan centre, a thrust line at Ground 0,
a ring's intersection) and moving it per frame contradicts the block.
The fork now lies on the foot-to-main segment, and `ForkOnLine`'s aim
line no longer lands on it for a shared foot, so the column changed
shape as it rose. And a column that "did not exist" until its notch
cleared the floor is not what the machine does: the tree lies on the
ground from the start and rotates up.

## 2. The frame model (binding)

### 2.1 Phases

Time 0 to 100 runs four phases, from the seven-questions document's
state machine as the spine spec bound it:

| Phase | Time | Sag | Lift | What moves |
| --- | --- | --- | --- | --- |
| reel | 0 to 30 | 0 to Pre-Sag | 0 | the net draws in on the ground, plan and depth |
| raise | 30 to 60 | Pre-Sag | 0 to 1 | the columns rotate up and lift the bars |
| finish | 60 to 90 | Pre-Sag to 1 | 1 | the rest of the sag is reeled against the bars |
| hold | 90 to 100 | 1 | 1 | nothing; the mould holds while load arrives |

`MouldGeometry.Phases(double time01, double preSag01)` returns
`(double Sag, double Lift, string Phase)` with Phase one of `reel`,
`raise`, `finish`, `hold`; it is a pure function and the harness checks
every boundary. `MouldFrameDto.Phase` carries the bare word; the
percentage detail lives in the `animate.phase` diagnostic. The net's
frame formula is unchanged: plan interpolates by sag, depth is
`start + lift x (bare - start) + sag x relief`.

### 2.2 Columns

- Every tree's FOOT is fixed at the position the block carries, from
  frame zero. Nothing slides.
- Every HEAD is at its net vertex's live position, found by
  `HeadNode` (head i stands on `Vertices[HeadNode[i]]`), never by plan
  matching.
- Every FORK is on the segment from its foot to its main notch's live
  position, at the fraction it was built at (measured on the block as
  distance foot to fork over distance foot to main, both in 3D; the main
  branch is `MouldGeometry.MainBranch`, recovered from collinearity).
- Branches run from the fork to their live notches.
- So at Time 0 every trunk lies flat on the ground from its foot to its
  notch's drawn position (the rail), and rotates up about the foot as
  the notch rises, its length being the ram. The tree turns as one body
  because the fork keeps its fraction.
- Every member is drawn at every frame; a member is skipped only when
  its two ends coincide within 1e-9.
- `MouldGeometry.LiveColumnNodes(MouldColumnsDto block, Point3d[] live)
  -> Point3d[]` gives every block node's position for a frame, pure, in
  block node order, so `Frame.ColumnNodes` is that array.

### 2.3 Extension

The port stays and becomes a check. For every trunk (a member leaving a
foot) at this frame: its length `L` against its built length `B`. The
`animate.columns` diagnostic reports count, shortest, longest; a new
`animate.ram_range` warning fires when any `L < B x (1 - Extension)` (the
ram would have to be shorter than retracted) or `L > B` (longer than
built), naming the worst member and the ratio. `animate.column_overrun`
is folded into it.

### 2.4 Alignment

`animate.column_alignment` (info) reports the worst angle between a
trunk's direction and the live thrust direction at its main notch
(`AimFrom` of that frame's transverse pull, computed exactly as now).
Nothing is re-aimed; the trunk points where its foot and its notch put
it, and this number says how far that is from the force path at this
frame.

### 2.5 Perimeter Lines

Output slot 8, appended after Columns: a tree of curves, one CLOSED
polyline per boundary loop at the live frame, branch i the same loop as
Perimeter Nodes branch i. A loop of fewer than three nodes gives an
empty branch (the branch is kept so numbering holds). Closure is by
repeating the first point.

## 3. Ports (binding)

Inputs unchanged: Result, Time, Pre-Sag, Extension. Outputs 0 to 7
unchanged in order and type (Mesh, Cables, Principal Lines, Principal
Nodes, Anchor Nodes, Perimeter Nodes, Result, Columns); 8 Perimeter
Lines `PRL`, tree of curves. GUID unchanged. No contract type changes;
`MouldFrameDto.Phase` values become the four words.

## 4. Diagnostics (binding)

Source "Animate". Kept: `animate.phase` (now the phase word plus its
percentages), `animate.anchor_strips`, `animate.anchors_isolated`,
`animate.nodes_want_push` and every other entry not named here.
Changed: `animate.columns` (count, shortest, longest; no slide text).
New: `animate.ram_range` (warning, per 2.3), `animate.column_alignment`
(info, per 2.4). Removed: `animate.below_ground`,
`animate.column_overrun`.

## 5. Files (binding)

- `plugin/native_v02/Components/MouldComponents.cs`: Animate's column
  block replaced by a call to `LiveColumnNodes`; the phase block by
  `Phases`; Perimeter Lines output; diagnostics per section 4.
  `MouldGeometry` gains `Phases` and `LiveColumnNodes`; `FootOnRail` and
  `ForkOnLine` are deleted (no caller remains).
- `tests/native_smoke/Program.cs`: section 6.
- `docs/component-taxonomy.md`: the Animate row.

Deconstruct, Monitor, Diagnose, Columns and the contracts are untouched.
Monitor already reads `Frame.ColumnNodes` when present.

## 6. Testing (binding)

- `ValidatePhases`: `Phases(0, 0.4)` is reel with sag 0, lift 0;
  `Phases(0.3, 0.4)` is raise with sag 0.4, lift 0; `Phases(0.6, 0.4)`
  is finish with sag 0.4, lift 1; `Phases(0.9, 0.4)` is hold with sag 1,
  lift 1; `Phases(1, 0.4)` is hold with sag 1, lift 1; sag and lift are
  monotone and continuous across the boundaries to 1e-9.
- `ValidateLiveColumnNodes`: a hand-built block with one forked tree
  (foot, fork, main head, one branch head) and a shared-foot pair. With
  `live` equal to the block's own net vertices, every node returns its
  built position within 1e-9. With `live` at ground level in plan
  (time zero), every returned node has Z equal to ground within 1e-9 and
  the fork lies on the foot-to-main segment at the built fraction. With
  `live` halfway, the fork keeps its fraction and trunk, fork and main
  head are collinear within 0.5 degrees.
- `ValidateVisualiseContract`'s Animate output list (if pinned) gains
  Perimeter Lines at index 8. `ValidateOutputGrouping` unchanged.
- The persistent parameter count stays 12.

## 7. What breaks on the canvas

Nothing rewires. The Columns output tree now holds every member from
frame zero, so a definition that filtered empty branches sees full ones
at Time 0. Phase text in any panel reading `Frame.Phase` becomes one
word.

## 8. Out of scope

Strike as a time past 100 (the spine spec defers it). Monitor's
document 07 output set (sub-project 5). Export (sub-project 6). Any
change to the Python worker.

## 9. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino. Check for OneDrive name-clash
files before every build and commit. Another session holds an
uncommitted edit to plugin/native_v02/Components/DeliveryComponents.cs:
never stage it; git add by explicit path only.
