# Monitor as the numbers, Deconstruct as the geometry, Skin as the cells

Date: 2026-08-28. Sub-project 5 of 6 from the mould rework brainstorm of
2026-08-27. Branch feature/monitor-deconstruct-skin off plugin main
0383624. Implements section 10, third paragraph, of
docs/superpowers/specs/2026-08-27-res-spine-design.md, which is binding
except where section 8 below states how document 07's items map onto
what a Result carries, approved by Param on 2026-08-28.

## 1. Why

Three components each carried a little of everything. Deconstruct gave
geometry and the solver's numbers and the tessellation cells; Monitor
gave flat lists that lined up with nothing downstream; the machine's own
readings from document 07 (spool lengths, leg forces split along the
tensioner, tip reactions, deviation to target, reachability) existed
nowhere. The spine rule, geometry via Deconstruct and numbers via
Monitor, is applied to the letter here, and Skin takes the cells.

## 2. Monitor (binding)

### 2.1 Inputs

| Slot | Name | Nick | Type | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| 0 | Result | RES | ResultParam item | required | From Columns (built) or Animate (this frame). |
| 1 | EI | EI | number | 0 | Bar bending stiffness, N.m2; zero reports shape only. Unchanged. |
| 2 | EA | EA | number, optional | none | Axial stiffness of a principal bar, N; wired, it gives unstrained spool lengths. |
| 3 | Tolerance | Tol | number | 5 | Deviation tolerance in millimetres for the reachability flag. |
| 4 | Cable Capacity | CC | number, optional | none | Allowable tension per cable, N; wired, Cable Utilisation is filled. |
| 5 | Column Capacity | CO | number, optional | none | Allowable compression per column member, N; wired, Column Utilisation is filled. |

### 2.2 Outputs, every one a tree

The alignment partner is named for each; item i of branch b of the
Monitor output is item i of branch b of the partner.

| Slot | Name | Nick | Per | Aligned with | Meaning |
| --- | --- | --- | --- | --- | --- |
| 0 | Member Force | F | member | Deconstruct Member Lines (one branch per bar, infill last) | Signed axial force, N, in the Result's sign convention. |
| 1 | Force Density | q | member | Member Lines | Force over live length. |
| 2 | Horizontal Force | H | member | Member Lines | Horizontal component of the member force, from the Result's H when it carries one, else force times the member's plan length over its length. |
| 3 | Slack | SL | member | Member Lines | Infill only: true where a cable's force opposes the Result's positive-tension convention or is zero. Bar-branch members are always false (a bar is never slack), so the tree stays aligned. The convention string is trimmed before comparison, as the validator trims it. |
| 4 | Spool Length | SP | bar | Member Lines' bar branches (branch b is bar b, one item) | Strained length at the frame: the sum of the bar's member lengths. |
| 5 | Unstrained Length | UL | bar | Spool Length | `sum(L / (1 + N / EA))` when EA is wired; empty otherwise. A member whose `1 + N / EA` is not positive contributes its strained length. |
| 6 | Anchor Along | AA | anchor | Deconstruct Reaction Points (one branch per strip) | Reaction component along the tensioner axis, the unit mean direction of the anchor's incident members into the net (falling back to the pattern's edges through the grouping adjacency when the net carries none at that anchor, counted in the diagnostic); the pull the tensioner takes. |
| 7 | Anchor Across | AX | anchor | Reaction Points | The perpendicular remainder's magnitude; what the anchorage carries and the tensioner cannot. |
| 8 | Tip Reaction | TR | head | Deconstruct Heads (one branch per column tree) | The axial force of the member under the head as a vector along it, pointing up into the head. |
| 9 | Column Force | CF | column member | Deconstruct Columns | Axial demand, N. Column numbers are read at the frame the Result carries, where Deconstruct draws the built state; the index alignment holds, the geometry may differ. |
| 10 | Thrust | TH | column member | Columns | Horizontal component, N. |
| 11 | Lean | LN | column member | Columns | Degrees from vertical. |
| 12 | Deviation | DV | node | vertex order (flat, one branch; no partner tree) | Signed vertical distance from the frame to the solved state, mm; zero without a frame. |
| 13 | Deviation Stats | DS | three items | none | RMS, max absolute, 95th percentile absolute, mm. |
| 14 | Reachable | RC | one item | none | True when every node's absolute deviation is within Tolerance. |
| 15 | Unreachable | UN | node ids | none | The nodes outside Tolerance, ascending. |
| 16 | Bar Sag | BS | notch | Animate Principal Nodes (one branch per bar, notches in order) | Bending away from straight at each notch, mm, with EI; unchanged mechanism. |
| 17 | Residuals | E | node | vertex order | The Result's equilibrium residual vector per node, zero where the Result carries none (the FD codec omits supports and exact zeros), assigned by node id (moved from Deconstruct). |
| 18 | Cable Utilisation | CU | member | Member Lines | absolute force / Cable Capacity when wired; empty otherwise. The capacity is in newtons whatever the Result's ForceUnit: a kN Result's forces are converted; any other unit gives empty trees and a warning. |
| 19 | Column Utilisation | CLU | column member | Columns | absolute force / Column Capacity when wired; empty otherwise. Same unit rule as Cable Utilisation. |
| 20 | Result | RES | item | none | Passthrough with Monitor's diagnostics. |

Bars and cables are told apart as now: a member joining two notches is a
bar member. `Force Density`, `Horizontal Force`, `Residuals` read the
Result's own arrays where the Result carries them (a TNA Result carries
q and H per member); an FD Result gets q as force over length and H as
above.

### 2.3 Diagnostics

Source "Monitor". Kept: `monitor.counts`, `monitor.cable_tension`,
`monitor.slack_cables`, `monitor.bar_force`, `monitor.column_force`,
`monitor.thrust_into_ground`, `monitor.no_columns`,
`monitor.anchor_horizontal`, `monitor.intermediate_frame`,
`monitor.bar_sag`, `monitor.bar_sag_shape_only`,
`monitor.bar_sag_absent`, `monitor.demand_only`. New:
`monitor.spool` (info: longest and shortest spool, unstrained when EA is
wired), `monitor.anchor_split` (info: worst across component, the
anchorage's share), `monitor.deviation` (info: RMS, max, p95; or "no
frame, deviation zero"), `monitor.reachability` (ok when every node is
within Tolerance, warning naming the count otherwise),
`monitor.utilisation` (info: worst INFILL cable and worst column
utilisation when capacities are wired; "demand not verdict" otherwise;
warning above 1 or on an unknown force unit), `monitor.column_frame_absent`
(info: a frame without column nodes, numbers at the built state),
`monitor.bar_unheld` (warning: runs held at fewer than two notches, whose
zero sag is not a straight bar). `monitor.thrust_into_ground` says, on a
part-built frame, that the finished force acts along this frame's lean.
`monitor.demand_only` stays and says utilisation is the one verdict
here, and only against a capacity the author supplied.

### 2.4 Pure helpers (binding names)

In `MonitorComponents.cs`, static, arithmetic only:
- `MonitorMath.AnchorSplit(Vector3d reaction, Vector3d axis) -> (double Along, double Across)`.
- `MonitorMath.TensionerAxis(int anchor, Point3d[] v, List<int>[] neighbours) -> Vector3d` (unit mean direction of incident members; ZAxis when none).
- `MonitorMath.DeviationStats(IReadOnlyList<double> mm) -> (double Rms, double Max, double P95)` (p95 by nearest-rank on absolute values; zeros on an empty list).
- `MonitorMath.UnstrainedLength(double strained, double force, double EA) -> double` (`strained / (1 + force / EA)`, `strained` when EA is not positive or the denominator is not positive).
- `ResultTables.Residuals(ResultDto) -> Vector3d[]`, one per vertex, zero where the Result carries none.
- `ParameterIdentity.Mismatch(int archivedInputs, int archivedOutputs, int registeredInputs, int registeredOutputs) -> string?`, the warning every reshaped component raises on load (section 9).

## 3. Deconstruct (binding)

Geometry only. Input: Result (Course Height removed). Outputs, in order:
0 Thrust Mesh, 1 Member Lines, 2 Form Lines, 3 Member IDs, 4 Node IDs,
5 Support Points, 6 Load Points, 7 Load Vectors, 8 Reaction Points,
9 Reaction Vectors, 10 Columns, 11 Heads, 12 Feet. Removed: q, H, F,
Force State, Residuals (to Monitor), Face Polylines, Face Courses (to
Skin). Every output after Form Lines renumbers; the harness pins the new
list; Param accepted the one-time rewire.

## 4. Skin (binding)

New component, tab `03 Visualise`, display name Skin, nickname Skin,
icon `skin`, GUID `7c2e9a54-3b6d-4f18-9e27-a1c5d8b4e063`. Inputs:
Result `RES`, Course Height `CH` (default 0.35, minimum 1 mm as now).
Outputs: Face Polylines `FP` and Face Courses `FC`, exactly Deconstruct's
today (one branch per course, closed polylines per face, the course
index per face), feeding Export's Cells and Courses. The code moves
from VisualiseComponents.cs to SkinComponents.cs unchanged in mechanism.
Empty for FD (no faces), with a remark.

## 5. Karamba

Nothing built. The taxonomy's Monitor row says the Karamba round trip
is fed by Member Force and Column Force with the matching Deconstruct
lines.

## 6. Files (binding)

- `plugin/native_v02/Components/MonitorComponents.cs`: rewritten ports
  and solve; `MonitorMath` added.
- `plugin/native_v02/Components/VisualiseComponents.cs`: Deconstruct
  trimmed; `FaceCourses` and the face polyline builder moved out.
- `plugin/native_v02/Components/SkinComponents.cs` (new).
- `plugin/icons/skin.png` (new, 24x24, the family style) and
  `plugin/icons/make_skin_icon.py`; `plugin/icons/icon-map.json` if the
  map lists icons.
- `plugin/native_v02/Components/NativeComponentBase.cs`: the archived
  parameter-count warning on load (section 9).
- `tests/native_smoke/Program.cs`: section 7.
- `docs/component-taxonomy.md`: Monitor, Deconstruct rows; Skin row
  added; the result-queries block and tab narrative brought up to date.
- `plugin/icons/LEGEND.md`: the skin row. `icon-map.json` is the
  manifest `generate_icons.py` regenerates from, not a registry: listing
  `skin` there would hand the file to two generators, and its alphabet
  has no K. The mould family's icons (stress_analysis, column_finder,
  mould_animate, diagnose, skin) stay outside it by design.

Export, Animate, Columns, Diagnose and the contracts are untouched.

## 7. Testing (binding)

- `ValidateMonitorMath`: AnchorSplit of reaction (3, 4, 0) on axis
  (1, 0, 0) gives along 3, across 4; TensionerAxis of an anchor with
  members to (1, 0, 0) and (0, 1, 0) is (1, 1, 0) normalised;
  DeviationStats of {1, -2, 3, -4, 5} gives RMS sqrt(11), max 5, p95 5,
  and of {} gives zeros; UnstrainedLength(2, 100, 1000) is 2 / 1.1 and
  UnstrainedLength(2, 100, 0) is 2.
- `VisualiseContracts` gains Monitor (six inputs, twenty-one outputs by
  name), Skin (two inputs, two outputs) and the trimmed Deconstruct list.
- Component count becomes 19; parameter count stays 12.
- `ValidateMonitorMath` also drives AnchorSplit with a non-unit axis and
  a negative dot, DeviationStats with a negative maximum and an empty
  field (all three zeros), and UnstrainedLength through its guards.
- `ValidateResultTablesOrder` drives the FD and the TNA path (edge-state
  Id order disagreeing with EquilibriumEdgeId order; a zero reaction
  dropped) and `ResultTables.Residuals` by node.
- `ValidateParameterMismatch` drives `ParameterIdentity.Mismatch`.
- `ValidateExportCoursesValidation` and
  `ValidateExportTessellationJsonOptions` unchanged.

## 8. Mappings of document 07 section 2.3 (approved)

1. The sign-change flag becomes Slack: a Result carries no solve
   history, so the only sign fact available is whether a member's force
   opposes the convention.
2. Unstrained spool length needs EA; it is an optional input, empty
   output without it.
3. The "legs" are the anchors; the tensioner axis is the anchor's cable
   direction into the net.
4. Tip reactions come from the block's member forces, not from a
   solver's node_reactions.
5. Deviation is frame to solved state, vertical, signed; a photoscan
   target is a later input.
6. Reachability is deviation within Tolerance at this frame; the
   constrained-solver meaning belongs to the M1 bridge and the port text
   says so.

## 9. What breaks on the canvas

Deconstruct lost one input and seven outputs, so every output after
Form Lines renumbers; Monitor's thirteen flat outputs became twenty-one
trees with Result at slot 20. Grasshopper reattaches saved wires BY
INDEX, so a wire on an old slot lands on whatever is there now: on
Deconstruct old slot 9 (Support Points) lands on Reaction Vectors, old
11 (Load Vectors) on Heads and old 12 (Reaction Points) on Feet, all
point or vector trees, so nothing errors and the drawing is wrong; on
Monitor the old Result at 11 lands on Lean and the old number ports
carry different quantities. That is worse than a broken wire, so both
base classes now compare the archived input and output counts with the
registered ones on load and raise a Warning naming them on the
component ("wires may now sit on the wrong port, check every one"). A
saved-file compatibility test is not built: the harness has no
Grasshopper archive reader; the Mismatch function is measured instead.
Export's Cells and Courses reconnect to Skin, flattened (Export flattens
them itself in sub-project 6).

## 10. Out of scope

Export auto-format and live mode (sub-project 6). Any photoscan input.
The M1 bridge. Any change to the worker or contracts.

## 11. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino. Check for OneDrive name-clash
files before every build and commit. Another session holds an
uncommitted edit to plugin/native_v02/Components/DeliveryComponents.cs:
never stage it; git add by explicit path only.
