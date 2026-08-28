# The RES spine: one contract through the whole mould chain

Date: 2026-08-27. Sub-project 1 of 6 from the mould rework brainstorm of
the same date. Branch feature/res-spine off plugin main b02b9ef.

The recurring failure across the mould components has one shape: a
component holds the right information and throws it away at its output,
and the next component rebuilds a worse version from geometry. Flat anchor
lists lost the strips. Prose reports lost the numbers. State carried
columns on a side wire that Animate could not see. This spec makes every
fact a component establishes travel forward inside the Result contract
(RES), so no downstream component re-derives anything. Re-derivation was
the source of the asymmetry, the doubled bars and the singleton strips
alike.

The six sub-projects, in build order, are: (1) this spine; (2) principal
lines input-only with one preview owner; (3) the columns rework; (4) the
Animate rework; (5) Monitor, the Deconstruct split and Skin; (6) Export
with live mode, with the studio task set dispatched in parallel. Sections
9 and 10 hand binding requirements to 2 to 6 so the decisions taken while
grounding this spec are not lost.

## 1. The chain

```text
Pattern > Supports > Loads > Relax > Solve
                                       |
                                      RES
                                       |
                                    Columns        writes  Mould.Columns
                                       |
                                      RES
                                       |
                                    Animate        writes  Mould.Frame
                                       |
                                      RES
            +--------------+-----------+-----------+-------------+
            |              |           |           |             |
        Deconstruct     Monitor     Diagnose     Skin         Export
        (geometry)      (numbers)   (english)    (cells)      (files)
```

Two rules make the rest possible.

A component OUTPUTS WHAT IT CREATED and nothing it merely carried. Columns
creates the built trees, so they leave it only inside RES and are read
back by Deconstruct. Animate creates the frame, so its live geometry
leaves it as geometry outputs as well as inside RES, because Param drives
a built Grasshopper structure from those outputs and they exist nowhere
else. Every component previews only what it created; the four-times-over
red principal lines are sub-project 2's job but the rule is stated here.

A component APPENDS DIAGNOSTICS INTO RES instead of printing a report.
Every Out and Report port on the mould components goes. Diagnose reads
the diagnostics back. Without this rule Diagnose has nothing to read.

## 2. The contract (binding)

ResultDto gains ONE nullable block, Mould. Everything the machine adds
lives inside it, so one wire carries the whole mould design to whoever
wants it. Attached client-side with a record `with { Mould = ... }`
expression, exactly as Problem is today; null is omitted on write
(WhenWritingNull), so a Result without a Mould block serialises as it
always has and old files load unchanged. New files are unreadable by old
plugin builds (UnmappedMemberHandling.Disallow); accepted, and already
true of every contract change in this repo.

```text
ResultDto
  ...existing fields unchanged...
  ResultSchema        "0.3"   stamped at every site where a solver component
                              already attaches Problem (SolverComponents.cs
                              993 and 1414 today; the plan enumerates them);
                              never validated, envelope-only, and the global
                              ContractSchema.Current stays "0.2" untouched
  Mould?              MouldDto
```

MouldDto, MouldColumnsDto and MouldFrameDto are PLAIN SEALED RECORDS in
the TnaPrepareConfigDto style: no Kind, no SchemaVersion, no Goo, no
Param, validated by the parent through an internal
`Validate(int vertexCount, string label, List<string> errors)`. They
never travel on their own wire.

```text
MouldDto
  Ground          double                     the level the anchors sit at
  Columns?        MouldColumnsDto            written by Columns
  Frame?          MouldFrameDto              written by Animate

MouldColumnsDto
  Nodes           Point3Dto[]                every tree node: heads, forks, feet
  Members         EdgeDto[]                  (lower, upper) as indices into Nodes;
                                             lower end first, always
  MemberForce     double[]                   N, aligned with Members, compression positive
  Trees           int[][]                    member indices per tree; one branch per tree
                                             downstream, in this order
  Heads           int[]                      node indices that sit on notches
  Forks           int[]                      node indices that are junctions
  Feet            int[]                      node indices on the ground
  HeadNode        int[]                      aligned with Heads: the equilibrium vertex
                                             each head stands on, so Monitor aligns
                                             column data to the net by INDEX, never
                                             by matching coordinates
  Branching       int                        the branching level asked for
  GroundAsked     int                        the ground type asked for
  GroundPlaced    int                        the ground type actually placed; equal to
                                             GroundAsked in this sub-project, and
                                             different only on the recorded fallback
                                             sub-project 3 introduces
  ForkFraction    double                     the Fork setting, 0 to 1
  ForksRaised     int                        how many forks the lean limit lifted

MouldFrameDto
  Time            double                     0 to 100
  Phase           string                     the phase name Animate already reports
  Lift            double                     0 to 1
  Sag             double                     0 to 1
  Vertices        Point3Dto[]                the live net; same count and index space as
                                             Equilibrium.Vertices
  ColumnNodes?    Point3Dto[]                live positions of Mould.Columns.Nodes, same
                                             count; absent when Columns is absent
```

Validation, run from ResultDto.ValidatePayload when Mould is present:
Ground finite; Columns, when present: every index in range, the Z order
of a member's two ends deliberately NOT validated (sub-project 4 lays
every tree flat on the ground at frame zero, and a flat member has no
lower end), MemberForce count equals Members count, HeadNode count equals Heads count
and every HeadNode in range of Equilibrium.Vertices, every member index in
Trees in range and used at most once, Branching at least 1, GroundAsked
and GroundPlaced at least 0, ForkFraction in 0 to 1, ForksRaised at least
0; Frame, when present: Time in 0 to 100, Lift and Sag in 0 to 1,
Vertices count equals Equilibrium.Vertices count, ColumnNodes count
equals Columns.Nodes count when both present, ColumnNodes absent when
Columns absent.

The frame is ONE frame, never a history. Every Goo boundary deep-clones
through JSON, and Animate re-emits on every slider tick; one frame of a
441-node net is tens of kilobytes, which is fine, and a hundred frames
would not be.

ResultGoo.Snapshot reattaches only RawWire after the deep clone. The
Mould block is plain JSON with no [JsonIgnore] member, so it survives
every clone with no change to Snapshot. No new [JsonIgnore] member may be
added to it without extending Snapshot; this is stated so nobody
discovers it the way the anchors were discovered.

MouldStateDto, MouldStateGoo, MouldStateParam, ContractKinds.MouldState
and MouldGeometry.BuildState are DELETED. Their fields are reborn above
with a cleaner split; nothing is embedded.

## 3. Components and ports (binding)

| Component | Inputs | Outputs |
| --- | --- | --- |
| Columns (was Column Finder; display name changes, GUID does not) | Result; Columns Per Line, Type, Fork, Branches unchanged in this sub-project | Result, and the viewport preview |
| Animate | Result, Time, Pre-Sag, Extension | Mesh, Cables, Principal Lines, Principal Nodes, Anchor Nodes, Perimeter Nodes, Columns (live, one branch per tree), Result |
| Deconstruct | Result, Course Height | as today, plus Columns, Heads, Feet as trees with one branch per tree in Mould.Columns.Trees order; Diagnostics and Report ports removed |
| Monitor (was Stress Analysis; display name changes, GUID does not) | Result, EI | Stress Analysis's outputs today, plus Lean (degrees from vertical per column, aligned with its Columns output) so nothing Column Finder's Angle port gave is lost; Report port removed |
| Diagnose (new) | Result | Text (item); Source, Code, Severity, Message, Value as trees branched by source |
| Export | unchanged | unchanged; contract mode now carries the Mould block for free |

Columns loses Columns, Heads, Feet, Force, Angle, State and Report. It
reads its principal runs from RES exactly as now and writes Mould with
Columns filled and Frame absent. If the incoming RES already carries a
Mould block (a second Columns downstream of a first), it REPLACES
Mould.Columns and drops Mould.Frame, because a frame computed against
other columns is stale.

Animate loses its Columns input, State and Report. It reads
Mould.Columns from RES when present, animates them exactly as it does
from the wired lines today (BuildColumnTree is replaced by reading the
tree the block already carries, which is simpler and cannot mis-weld),
and writes Mould.Frame without touching Mould.Columns. When RES carries no
Mould block Animate creates one with Frame filled and Columns absent, and
records Ground.

Deconstruct reads Mould.Columns when present. Its Columns output holds
Members as lines from lower to upper, one branch per tree; Heads and Feet
hold the points, one branch per tree in the same order. Empty trees when
the block is absent, never an error.

Monitor is Stress Analysis re-plumbed to RES so nothing it reports today
goes dark between this sub-project and sub-project 5. It reads
`Frame?.Vertices ?? Equilibrium.Vertices` for the net and
`Frame?.ColumnNodes ?? Columns.Nodes` for the columns, and its BarBending
takes its runs from MouldGeometry.PrincipalRuns, which reads the ANALYSIS
topology's runs, the index space of Equilibrium.Vertices, exactly as
Columns and Animate already do. Its EI input and Bar Nodes and Bar Sag
outputs stay, and it gains Lean per column.

The Columns and Animate previews are unchanged. Diagnose has no preview.

## 4. Diagnostics (binding)

Columns, Animate and Monitor append DiagnosticDto entries to
`result.Diagnostics` and return `result with { Diagnostics = ... }`. The
worker's own entries are never removed or reordered; native entries go
after them. Every native entry carries
`Provenance["source"] = "Columns" | "Animate" | "Monitor"` and a Code
namespaced by that source in lower case. Every entry must pass
DiagnosticDto.Validate (non-empty code and message, severity in
ok/info/warning/error), because the worker codecs throw on an invalid one
and Diagnose must be able to trust the list.

Numbers go in Value, Tolerance and Unit, never only inside the sentence.
A line of the old report that carried a number becomes an entry whose
Message still reads as a sentence and whose Value carries the number, so
the prose is not lost and the number becomes graphable.

Facts are severity `info`. Anything the old report prefixed WARNING is
`warning`. `error` is reserved for a state that makes the component's
own output meaningless (no principal runs on Columns; no vertices).

Initial code set, mapped from the reports that exist today. This is the
minimum; a code is added whenever a report line is added, never the other
way round.

Columns: columns.bars (count, notches), columns.bar_shape (one per bar:
notches, anchored at both ends or ANCHORED AT ONE END ONLY, warning in
the second case), columns.overlap (warning: two lines share N notches),
columns.arms (per bar count), columns.symmetry (info mirrored, or warning
lopsided with the cost), columns.centre_added, columns.foot_drift (Value
in model units), columns.plumb_fallback (count), columns.lean (Value max,
Tolerance 60, Unit degrees), columns.trunk_lean_exceeded (warning, Value
the worst, Tolerance 60), columns.forks_raised (Value count, Context
highest fraction), columns.force_max (Value N), columns.ground_fallback
(warning; Context asked and placed; written by sub-project 3, reserved
here).

Animate: animate.phase, animate.counts (nodes, cables, bars, notches,
anchors, perimeter), animate.start (info: pattern, flat, or final with
the reason), animate.travel (Value the deepest reel in mm), animate.plan_draw
(Value mm), animate.anchor_strips (info: N strips of a/b), animate.anchors_isolated
(warning), animate.nodes_want_push (warning, Value count above the bare
surface, Context total), animate.unreachable (warning, Context the node
ids), animate.columns (Value member count, Context shortest, longest,
slid), animate.column_overrun (Value the overshoot), animate.below_ground
(Value count).

Monitor: monitor.slack_cables (warning, Value count), monitor.tension_max,
monitor.compression_max, monitor.thrust_into_ground (Value N, Context
per foot), monitor.anchor_horizontal (Value N), monitor.bar_sag (Value mm
worst, Context EI; or info monitor.bar_sag_shape_only when EI is zero).

## 5. Diagnose (binding)

Input Result. Outputs: Text, one string for the panel; and five trees,
Source, Code, Severity, Message, Value, branched by source in the order
worker, Columns, Animate, Monitor, Diagnose, item-aligned across the five
so any one can be filtered by another.

Text renders severity first (error, warning, then info), grouped by
source, one sentence per entry, the number appended in its unit where
Value is present, and the worker's Report string printed last under its
own heading. A Result with no native diagnostics prints the worker report
and a line saying which mould components have not run, read off which
blocks are absent.

Cross-checks, written as diagnostics with source Diagnose and severity
warning, computed from RES alone:

- diagnose.no_principal_runs: Mould.Columns present and
  Problem.Topology.PrincipalRuns empty. Columns ran on nothing.
- diagnose.frame_without_columns: Mould.Frame present and Mould.Columns
  absent. Animate ran with no Columns upstream; the animation has no
  columns to raise.
- diagnose.anchors_all_isolated: the anchor grouping over the plan
  unioned with the solved net returns one strip per anchor. The Result
  has lost its source Pattern.
- diagnose.stale_frame: Mould.Frame present and Mould.Columns present
  and Frame.ColumnNodes count differs from Columns.Nodes count. A
  Columns ran downstream of an Animate, or the block was hand-edited.
- diagnose.push_needed: animate.nodes_want_push exceeds half the nodes.
  Restates the machine question in words: a reel only pulls.
- diagnose.forks_raised: columns.forks_raised above zero. Says which
  lever to pull if the shape is unwanted.

The set grows one check per failure that teaches something, and each
check names the lever to pull in its message.

## 6. What breaks on the canvas

Wires into removed ports drop on load. Reconnections, one pass:

- Column Finder: Columns, Heads, Feet went to your built structure;
  reconnect from Deconstruct's new Columns, Heads, Feet trees (same
  branching, one branch per tree). Force and Angle went to panels or
  graphs; reconnect from Monitor's Column Force and Monitor's new Lean.
  State went to Stress Analysis; delete the wire, Stress Analysis now
  takes RES. Report went to a panel; reconnect the panel to Diagnose's
  Text.
- Animate: the Columns input came from Column Finder; delete the wire
  and wire Column Finder's RES into Animate's RES instead. State and
  Report as above.
- Stress Analysis: State input becomes Result; wire the RES from
  Animate (for the live frame) or from Columns (for the built state).
- Deconstruct: Diagnostics and Report went to panels; reconnect to
  Diagnose.

Component GUIDs do not change, so every other wire survives. Display
names change: Column Finder becomes Columns, Stress Analysis becomes
Monitor.

## 7. Testing (binding)

All in tests/native_smoke, Rhino-free, in the existing style of one
measured check per mechanism with a message that says what the failure
means:

- MouldColumnsDto and MouldFrameDto validation: good counts pass; a
  MemberForce one short, a HeadNode out of range, a Frame with the wrong
  vertex count, ColumnNodes present without Columns, all refused by name.
- The golden chain: a synthetic ResultDto (the harness already builds
  one) with a Mould block attached by `with`, serialised through
  ContractJson, deserialised, and asserted intact field by field; the
  same Result without a Mould block serialises with no "mould" key at
  all; a hand-written 0.2 JSON with no Mould loads and validates.
- Diagnostics append: a Result with two worker entries gains three
  native ones and keeps the worker's two first and unchanged; every
  native entry passes DiagnosticDto.Validate.
- Diagnose rules: each cross-check driven on a synthetic Result built to
  trigger it and asserted by code; a Result that triggers none produces
  no Diagnose-sourced entry.
- Deconstruct's tree shaping of Mould.Columns: two trees of two members
  give two branches of two lines, lower to upper, and the empty block
  gives empty trees rather than an error.

The existing ten checks stay and must keep passing.

## 8. Acceptance bars

- Param's current definition, after the one-pass rewire of section 6,
  produces the same viewport as before this sub-project: same columns
  from Columns' preview, same animation from Animate, same Stress
  Analysis numbers from Monitor. This is a refactor of where facts live,
  not of what they are.
- Wiring Diagnose to any RES in the chain prints, in words, every line
  the three retired Report ports printed, with the numbers now present
  as Values.
- A Result saved in a .gh file with the Mould block reloads and
  validates.
- Build 0 warnings 0 errors; every smoke check passes against the
  installed .gha; installed hash equals built hash.

## 9. Binding requirements handed to sub-project 3 (columns)

Recorded here because the grounding and Param's screenshots settled them
and they must not be re-decided.

- Two sliders and nothing else: Branching (1, 2, 3; every notch on every
  principal line receives a column head, grouped into trees of that
  size with the remainder as smaller trees) and Ground (0 standalone, 1
  to 4 shared feet, plus Auto). Columns Per Line is removed; the beam
  solver stops choosing arms and survives in Monitor as bar sag between
  adjacent held notches.
- The fork lies ON THE SEGMENT FROM ITS FOOT TO ITS MAIN NOTCH. Order of
  operations: group notches, place the foot, place the fork on the
  foot-to-main-notch line at the fork fraction, then draw branches.
  Standalone columns are the same rule with the foot on the notch's own
  thrust line. The kinked forks in Param's middle screenshot are the
  failure this forbids; acceptance is trunk and main branch collinear
  within 0.5 degrees on every tree.
- Auto-rejection: a candidate arrangement is refused when any trunk
  exceeds MouldGeometry.MaxLeanDegrees with no fork left to raise, when
  members collide with each other or with the net at the built state,
  or when thrust alignment is worse than a stated bound; the next lower
  Ground type is tried and GroundAsked and GroundPlaced record the
  fallback. Param's top screenshot (one foot, trunks past seventy
  degrees) is the acceptance case: Type 1 refused and recorded.
- Centering is per SPAN, not per bar: a bar is a sequence of supported
  spans between anchors and any interior support (a ring held to the
  ground, a column head on a crossing bar); mirroring and any centre
  column are about the span's own midpoint. A form with a central hole
  and free rim gets a ring tree: one shared foot at the plan
  intersection of the drawn lines, branches to the notch nearest the
  hole on each bar. A form with a ring held to the ground gets no centre
  column and two half-spans per bar. Param's bottom screenshot (one
  foot off centre under a symmetric arch) is the acceptance case: foot
  on the plan centre of the span within one hundredth of the span.
- The scorer's objective for Auto is minimum load path, the sum over
  members of force times length; the weighted Fermat point is not asked
  to place a fork on its own.

## 10. Binding requirements handed to sub-projects 2, 4, 5 and 6

Sub-project 2, principal lines: remove DeriveFromAnchors and the Ribs
input; Flatten the Principal Lines input on Pattern to match Geometry;
Pattern is the only component that previews principal runs; "curves
supplied, none matched" is an error, not a silent fallback; Pattern's
message line shows the run count; Deduplicate stays as a safety net.

Sub-project 4, Animate: columns exist from frame zero, each tree lying
flat on the ground along its rail and rotating up about its foot as a
rigid body while the ram extends, so the column points along the
interpolated force path from horizontal to its final aim; Perimeter
Lines output, one closed curve per boundary loop, branched as Perimeter
Nodes; the phase model from the seven-questions document, section 4.3
(reel in, raise, finish, hold; strike by uniform increments as a time
past 100 later).

Sub-project 5, Monitor and the split: Monitor's output set is document
07 section 2.3 verbatim (signed force per member with a sign-change
flag, spool length per principal line, leg and anchor reactions split
along and across the tensioner axis, tip reactions per column head, a
signed deviation field to target with RMS, max and 95th percentile, a
reachability flag with the unreachable node set), plus per-column force,
thrust and lean, the slack set, and bar sag with EI, every output a tree
aligned item for item with the matching Deconstruct tree; utilisation
only when section inputs are wired, "demand not verdict" otherwise;
Deconstruct becomes geometry only; Course Height, Face Polylines and
Face Courses move to Skin; Karamba stays a manual round trip fed by
Monitor's outputs.

Sub-project 6, Export and live: Export takes RES and decides for itself,
always writing the contract and compas pair, the tessellation sidecar
when Skin cells are wired, and a columns mesh when Mould.Columns is
present; Live is a boolean that PUTs to the studio on every solve with a
debounce and a retry on 409. Studio task set to dispatch: a tessellation
upload kind with its own invalidation; columns namespaced per study; a
change channel (SSE or a version field on /api/studies) so a push
reloads the open page; a columns payload from lines plus radius; a
retry-after on the 409; upload validation tolerant of the Mould block.

## 11. Out of scope for this sub-project

The column sliders and every column behaviour (section 9). Principal
line derivation removal (section 10). Animate's frame-zero columns and
perimeter curves. Monitor's document 07 output set. Skin. Export's auto
format and live mode. Any Karamba bridge. Any change to the Python
worker or its wire.

## 12. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every fix; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino; anything that P/Invokes
rhcommon_c cannot be tested there and must be kept out of the mechanism
under test. Check for OneDrive name-clash files before every build and
commit.
