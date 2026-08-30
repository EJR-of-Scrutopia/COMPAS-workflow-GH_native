# The surface: RES first, one JSON, a Frame component, six panels, one icon family

Date: 2026-08-30. Sub-project 8, the second of two from Param's review
of the installed rework on 2026-08-30 (sub-project 7, the columns, is
merged at main 6a4341c). Branch feature/surface off main 6a4341c. Every
decision in sections 2 to 6 was taken by Param on 2026-08-30; this spec
fixes the exact ports, names and rules. Where it touches the RES spine
spec (docs/superpowers/specs/2026-08-27-res-spine-design.md), the
columns spec and the export spec, section 11 records the amendments.

## 1. Why

Five things about the surface, seen on the canvas after the six-part
rework: Export carried four JSON outputs where one would do; Display
carried six outputs that Deconstruct and Diagnose now provide; the
Result port sat in the middle of Animate's outputs and at the end of
Monitor's; Animate's eight geometry outputs belong to a reader, not to
the component that makes the frame; and the nineteen components were
filed under five tabs, eight of them under one, with icons whose fills
belonged to tab names that no longer exist and five of which were drawn
by a different hand. This sub-project settles all five at once, so the
canvas is rewired once.

## 2. Ports: RES first (binding)

Rule: on every component that takes a Result, the Result is INPUT 0;
on every component that emits a Result, the Result is OUTPUT 0. A
component that reads a Result and emits geometry or numbers does not
re-emit it (Deconstruct, Skin, Diagnose, Frame, Armadillo Dual, Export,
Display). The solvers already emit RES at 0; Columns already has it at
0 both sides. What moves:

| Component | Before | After |
| --- | --- | --- |
| Animate | outputs Mesh, Cables, Principal Lines, Principal Nodes, Anchor Nodes, Perimeter Nodes, Result, Columns, Perimeter Lines | ONE output: 0 Result `RES`. The geometry moves to Frame (section 3). Inputs unchanged (Result, Time, Pre-Sag, Extension). |
| Monitor | outputs 0..19 the twenty trees, 20 Result | 0 Result `RES`, then the twenty trees in their present order (Member Force at 1 ... Column Utilisation at 20). Inputs unchanged. |
| Export | six outputs | two: section 4. Inputs unchanged (nine, Cells and Courses flattened). |
| Display | six outputs | none: section 5. Inputs unchanged (seven). |

Every other component's ports are unchanged. GUIDs unchanged. The
component count becomes 20 (Frame); the persistent parameter count
stays 12.

## 3. Frame, the reader of the frame (binding)

A new component **Frame** (nick `FR`, GUID
`5d8e2f61-7a4c-4b93-a0e6-c3f19b7d2a58`, panel 04 Read, icon key
`frame`, letters FR). Input 0 Result `RES` (item, required). Outputs,
in order, with Animate's old names and nicks where they existed:

| Slot | Name | Nick | Type | Meaning |
| --- | --- | --- | --- | --- |
| 0 | Mesh | M | Mesh item | The net's mesh at the frame's positions (FD: none). |
| 1 | Cables | C | Line tree | Every net edge at the frame, one branch per principal run, the infill in the last branch, as Animate had. |
| 2 | Principal Lines | PL | Curve tree | One polyline per principal run at the frame. |
| 3 | Principal Nodes | PN | Point tree | The notches per run. |
| 4 | Anchor Nodes | AN | Point tree | Anchors grouped into strips. |
| 5 | Perimeter Nodes | PRN | Point tree | The boundary nodes per loop. |
| 6 | Perimeter Lines | PRL | Curve tree | The boundary polylines, closed when the walk closes. |
| 7 | Columns | CO | Line tree | The live column members, one branch per tree (nick CO, not Animate's clashing C). |
| 8 | Phase | PH | Text item | The frame's phase name (`reel`, `raise`, `finish`, `hold`, or `final` when no frame). |

Rule: Frame reads `Result.Mould.Frame` when present (positions from
`Frame.Vertices`, columns from `Frame.ColumnNodes` over
`Mould.Columns`), and the SOLVED state otherwise (`Equilibrium.Vertices`,
`Mould.Columns.Nodes`), so Frame on a Solve or Columns RES is the
finished vault and Frame on an Animate RES is that frame. Columns is
empty when the Result carries no columns block. The geometry is built
by ONE set of helpers shared with Animate's preview, moved out of
Animate's SolveInstance into `MouldGeometry` (or a `FrameGeometry`
static class beside it): `FrameGeometry.Build(ResultDto result) ->
FrameGeometry.Set` carrying Mesh, Cables (per run), PrincipalLines,
PrincipalNodes, AnchorGroups, PerimeterLoops, PerimeterEstimated,
ColumnBranches, Phase, so Animate's viewport and Frame's outputs cannot
drift. Animate keeps its viewport preview (shaded mesh, cables, blue
columns, green supports) and its diagnostics; its `animate.*` codes are
unchanged. Frame has no custom preview, and its eight geometry outputs
start HIDDEN, as every other reader of a Result starts them (Deconstruct,
Monitor, Skin, Columns): Animate draws the frame, Frame carries the data.
Amended 2026-08-30 in the final fix round; the earlier wording said
"visible by default", which drew the mesh, the cables and the columns a
second time in Grasshopper's default red over Animate's own preview.
Each output can still be switched on from its own context menu, and
Phase is text and previews nothing either way.

## 4. Export: one JSON and one Status (binding)

Outputs: 0 JSON `J` (text LIST), 1 Status `ST` (text item, lines).

- `J` carries one JSON text per kind in `ExportPlan.Kinds` order:
  contract, compas, tessellation, columns; a kind that is absent (no
  cells, no columns) or failed (the compas worker) is simply not in the
  list, and every text carries its own identity key (the contract's
  `kind` and `schemaVersion`, the compas document's `compasVersion`
  and the `dtype` inside each diagram it carries, `schema` on
  `bench.tessellation/1` and on `bench.columns/1`) so a reader knows
  what each item is without its index. Amended 2026-08-30 in the Task
  5 fix round: the earlier wording promised a `schema` key on all
  four, which the contract and the compas document do not carry and
  which no wire format was going to be changed to give them.
- `ST` is the former Written and Uploaded, as lines: `written: <path>`
  per file of the LATEST write (the one-shot Button latch of the export
  spec; `written: nothing` before any), then `live: <kind>:
  <outcome>` per kind (or `live: off`, or the hold and cancelled texts
  of the export spec), then any Warning's text.
- Default tessellation: when Cells is unwired (empty) and the Result
  carries a mesh, Export builds the tessellation itself: one cell per
  face of the thrust mesh in face order, course 0 for every cell, via
  `SkinComponent.FacePolylines` made `internal static` (the same code
  Skin uses). Wiring Cells (from Skin or a custom pattern) overrides,
  as today. The tessellation kind is therefore present for every TNA
  Result. The sidecar's `pattern` key says which of the two it is:
  `authored` for cells somebody wired, `faces` for the ones Export made
  from the Result's own mesh, so the studio can tell a chosen cutting
  pattern from the courtesy one. Courses without Cells is ignored, with
  a Remark accompanying a FACE-BUILT default only: on a Result with no
  faces at all, which is every FD Result, no tessellation is built and
  the Remark would describe nothing. Both amended 2026-08-30 in the
  final fix round: the key was `authored` on both paths, and the Remark
  sentence read as unconditional.
- Everything else of the export spec of 2026-08-28 stands: the nine
  inputs, the write rules, Live, the uploader. The HOLD does not stand
  as written there: it now reads the INPUT side alone (section 11).
  Amended 2026-08-30 in the final fix round, because Export's outputs
  went from six to two on this branch with its nine inputs untouched,
  and a hold on any port move would have held Live on every definition
  in existence for a change that cannot have moved an input wire.

## 5. Display without outputs (binding)

Display keeps its seven inputs and its whole viewport job (the element
lines with the Style preset, the Elements and Metric filters, the
auto-scaled vectors, the residual arrows) and registers NO outputs. The
data those outputs carried is Deconstruct's (Member Lines, Form Lines,
FORCE LINES, Load and Reaction Points and Vectors) and Diagnose's
(Report). `RequiredPreviewComponents` and
`NativeVisibilityGuardComponents` keep Display; it stays a
`NativePreviewComponentBase`.

Amended 2026-08-30 in the final fix round. Deconstruct gains `Force
Lines` `FCL` (Line tree, branched as Form Lines, from the ForceGraph,
empty for FD), APPENDED at slot 13 so no existing port moves. It carries
the force diagram at its OWN coordinates, where Display's old `FCL`
carried a copy laid out beside the form diagram by Display's Gap input,
which Deconstruct has not got: same shape, different place, and a data
boundary is the wrong owner of a drawing decision. Without it
the reciprocal force diagram had no data port anywhere in the plugin,
which the sentence above assumed it had. And two readings are Display's
OWN, not Deconstruct's or Diagnose's, so they are raised on the
component as Remarks rather than emitted: "FD result: no reciprocal
diagram" and "Metric H unavailable for FD result; used F magnitude",
the second of which is a fact about Display's own Metric input and
reaches no other component. The chin carries the scales the drawing was
made at (`TNA . analysis . thrust x1 . vectors x0.0153 auto`), saying
`auto` where the vector scale was the component's own choice.

## 6. Panels and icons (binding)

Six subcategories, in the order of the RES chain, replacing the five
in use (`ComponentCategories` constants renamed and renumbered; the
reserved Masonry, Engineering and Fabrication constants become 06, 07,
08 and stay unused):

| Panel | Components (letters) | Fill |
| --- | --- | --- |
| 01 Model | Pattern PA, Supports SU, Loads LO | `#126E82` teal |
| 02 Solve | TNA Relax RX, TNA Solve TS, TNA Solve Algebraic TA, FD Solve FD | `#A9462E` orange |
| 03 Mould | Columns CO, Animate AN | `#2855AF` blue (the column colour 40,85,175) |
| 04 Read | Deconstruct DE, Monitor MO, Skin SK, Diagnose DG, Frame FR, Style ST, Display DI | `#2F7D6D` green |
| 05 Deliver | Export EX, Import Pieces IP, Armadillo Dual AD | `#765300` ochre |
| 90 System | Backend Health BH | `#4E5968` slate |

One icon family: `plugin/icons/generate_icons.py` and `icon-map.json`
own every icon of the twenty components. `icon-map.json` gains the six
panel categories above (the old category names stay only for the
legacy `components` list, labelled as the script-backed v0.1 set that
`plugin/components.toml` still pins) and a
`native_components` entry for every component key with its two-letter
label, panel and filename; the five hand-drawn icons (column_finder,
mould_animate, stress_analysis, diagnose, skin) are regenerated by the
generator in the same badge shape as the rest; `make_skin_icon.py` and
`make_diagnose_icon.py` are deleted; TNA Solve Algebraic gets its own
key `tna_solve_algebraic` and icon (TA) instead of sharing TNA Solve's;
a new `frame` icon (FR). The generator's alphabet gains any letter the
twenty labels need. The legacy `components` list and its
`components.toml` check stay as they are (they serve the old
plugin/native project). `LEGEND.md` is regenerated to list the six
panels and the twenty components.

## 7. Load-time protection: names, not only counts (binding)

Monitor's output count does not change when RES moves to slot 0, so
every saved Monitor wire would land one slot down on a same-typed tree
with no warning. `ParameterIdentity.Mismatch` therefore compares, for
each side, the archived parameter NAMES by index against the registered
names, as well as the counts: a difference in count OR in any name at
any index raises the Warning ("this component's ports changed since the
file was saved: … check every wire"), read from the archive's
`ParameterData` chunk (`InputCount`/`OutputCount` and each parameter
chunk's `Name`), re-asserted from `BeforeSolveInstance` as today. Pure
and measured (`ParameterIdentity.Mismatch(archivedIn, archivedOut,
registeredIn, registeredOut)` takes the name lists; the old count-only
overload is deleted).

## 8. Files (binding)

- `plugin/native_v02/Components/MouldComponents.cs`: Animate's outputs
  reduced to RES; the geometry assembly moved to `FrameGeometry`.
- `plugin/native_v02/Components/FrameComponents.cs` (new): Frame.
- `plugin/native_v02/Components/MonitorComponents.cs`: RES to output 0.
- `plugin/native_v02/Components/DeliveryComponents.cs`: two outputs, the
  default tessellation.
- `plugin/native_v02/Components/SkinComponents.cs`: `FacePolylines`
  internal.
- `plugin/native_v02/Components/VisualiseComponents.cs`: Display's
  outputs removed.
- `plugin/native_v02/Components/NativeComponentBase.cs`:
  `ComponentCategories` renamed and renumbered; `ParameterIdentity.Mismatch`
  by name; every component's subcategory constant updated where it
  names one.
- `plugin/icons/`: `icon-map.json`, `generate_icons.py` (alphabet, the
  six categories), the twenty PNGs regenerated, `frame.png` and
  `tna_solve_algebraic.png` new, the two one-off scripts deleted,
  `LEGEND.md` regenerated.
- `tests/native_smoke/Program.cs`: section 9.
- `docs/component-taxonomy.md`: every row, the tab layout section, the
  count (twenty); `README.md`: the component map and count; the
  columns, export and spine specs are amended by reference (section
  11), not edited.

## 9. Testing (binding)

- `VisualiseContracts`: Animate (inputs Result, Time, Pre-Sag,
  Extension; output Result), Monitor (output 0 Result then the twenty
  names in order), Export (outputs JSON, Status), Display (seven inputs,
  NO outputs), Deconstruct (the twelve outputs it had, then `Force
  Lines` appended at 13), Frame (input Result; the nine outputs of
  section 3), all pinned by name in order.
- `SpineComponentContracts`: every Tab string updated to the six panels
  for the components it pins; Frame pinned with nick `FR`, tab `04
  Read`, output nicks `M, C, PL, PN, AN, PRN, PRL, CO, PH`.
- The component count pin becomes 20.
- `ValidateIconMap` (new): reads `plugin/icons/icon-map.json`; every
  component's icon key (from the constructor argument, read by
  reflection or from the embedded resource name) has exactly one
  `native_components` entry whose category is the component's
  registered subcategory; every embedded icon's fill, sampled at pixel
  (12, 20) of the badge, equals its category's fill; every label is the
  two letters the spec table gives. The fill sample cannot tell one
  badge from another inside a panel, since every badge in a panel shares
  it, so `python plugin/icons/generate_icons.py --check` carries the
  other half: it re-renders every icon the map lists IN MEMORY and
  refuses any file whose BYTES differ, which is what stops a stale PNG
  with the wrong letters surviving. One comparison per FILE, against the
  entry that owns it: a key in both lists is one file the native entry
  owns, so the legacy entry is skipped and the closing line counts what
  was compared and what was skipped rather than claiming both. `--check`
  runs in the same gates the harness does and at install time, beside
  the build.
- `ValidateParameterMismatch` extended: same counts with one output
  name moved (Monitor's case) reports a mismatch; equal names report
  none; a longer archived list reports one; the old count-only
  behaviour is gone.
- `ValidateFrameGeometry` (new, pure): it measures `FrameGeometry.Read`,
  which is the whole of the frame's reading bar the mesh and the curves.
  A Result with a frame whose vertices are the solved vertices raised by
  1 gives cable ends at the raised positions; a Result without a frame
  gives the solved positions and Phase `final`; a Result with a frame
  and no columns block gives an empty Columns tree; and a Result with no
  faces anywhere gives a boundary marked ESTIMATED. `Build` is not
  driven here and cannot be: it is the Rhino-bound half (`Mesh`,
  `Polyline.ToNurbsCurve`), and section 13 forbids launching Rhino. That
  Frame's ports and Animate's preview cannot drift is structural rather
  than measured: both take one `FrameGeometry.Build` on the same
  Result. Amended 2026-08-30 in the final fix round, which found the
  earlier sentence claiming both meshes were asserted.
- `ValidateExportDefaultTessellation` (new): with no cells wired and a
  Result carrying faces, the plan includes `tessellation` and the JSON
  holds one cell per face at course 0; with cells wired the wired cells
  win; Courses without Cells is ignored.
- `RequiredPreviewComponents` gains `MouldAnimateComponent`, which pins
  "Animate keeps its viewport preview": Animate is now the one component
  whose only output is custom Goo and whose whole visible behaviour is
  the drawing, which is exactly the case that set exists for.
- `ValidateDeconstructForceLines` (new, pure): one force line per member
  row, in row order, between the force-graph vertices of the force edge
  that row's state NAMES, driven by a fixture whose state ids, list
  order and force-edge ids all disagree; and nothing at all for an FD
  Result.
- `ValidateArchivedNamesFromDefinition` (new): `ArchivedNames` driven
  over a REAL archive, `plugin/definitions/ananke_equilibrium_v01.gh`,
  read headless through `GH_IO`'s `GH_Archive` down to the same
  `Container` chunk a component's `Read` is handed, asserting the five
  input names and two output names the file's first object holds. This
  is the case that catches a wrong chunk or item name, which returns
  nulls and silences the whole load-time warning without failing
  anywhere else.
- Every existing check keeps passing; the Animate-specific checks that
  read its geometry outputs move to Frame or to `FrameGeometry`.

## 10. What breaks on the canvas

Every saved Animate, Monitor, Export, Display and Deconstruct raises the
port Warning on load. Display and Deconstruct trip the count rule alone;
Animate, Export and Monitor trip the NAME rule as well, so all three of
those warnings NAME the port that moved, which is the useful half of the
message. Monitor trips ONLY the name rule, which is what section 7 was
written for.

The mechanism, stated once because every paragraph below depends on it:
Grasshopper matches archived parameter chunks to live parameters BY
INDEX, and a wire is stored on the receiving port as the source
parameter's instance guid. An archived wire therefore reattaches to
whatever port now stands at ITS OWN INDEX, and an archived slot beyond
the new range simply has nowhere to land and is dropped. Nothing is
matched by name.

**Animate.** NO output wire keeps its meaning. Nine outputs become one,
so the old MESH wire, at index 0, is the one that reattaches, and it now
carries a Result: any mesh or geometry consumer downstream turns red on
a data conversion, and a Panel there reads `TNA Result . #<hash>`. Every
other output wire is dropped for want of an index, INCLUDING the old
Result wire at slot 6, which is the wire that fed Monitor, Diagnose or
Export and the one an author is least likely to look for. Rewire RES,
and take the geometry from a Frame fed by that same RES. The four input
wires and their slider values are untouched.

**Monitor.** All twenty-one wires reattach, and every one of them now
delivers the metric ABOVE the one it used to, because the Result was
inserted at the front. Move each wire DOWN one port, to the next higher
slot: a wire that read slot 16, Bar Sag, moves to slot 17. The old
Member Force wire, on slot 0, now delivers the Result itself and turns
red on a number consumer; the old Result wire, on slot 20, now delivers
Column Utilisation numbers into a RES input and turns red too. Between
them, slots 1 to 19 change quantity with no colour and no complaint,
which is why the warning is the only thing that says so.

**Export.** Slot 0's wire lands on JSON, which is now a text LIST
carrying the contract AND the COMPAS document AND the tessellation AND
the columns, so a File-write on that wire writes four documents into one
file. Slot 1's wire lands on Status, which is lines of prose and not
JSON at all; rewire it. Slots 2 to 5 are dropped. Live is not held by
this load: the hold reads the INPUT side, and Export's nine inputs did
not move (section 4).

**Display.** Every output wire is dropped; feed Deconstruct for the
lines, points and vectors, including the reciprocal force diagram on its
new Force Lines port, and Diagnose for the report. One thing to expect
of that port: it hands back the force diagram at its own coordinates,
not the copy Display drew beside the form diagram, so an author who had
the old laid-out `FCL` wired gets the same shape somewhere else.

**Deconstruct.** Its outputs went from thirteen to fourteen, so it warns
too, by count. Nothing moved and nothing is dropped: `Force Lines` was
APPENDED at slot 13, the names at slots 0 to 12 are what they were, and
every archived wire lands on the port it left. The warning is
precautionary there, and it is the price of adding the port at all.

The panel move does not touch saved files: the subcategory is display
grouping and no GUID changed. The new icons appear after the restart.

## 11. Amendments to earlier specs

- RES spine spec section 9 (Animate's ports): outputs are RES only;
  Frame is the reader. Section 10 paragraph 3 (Deconstruct gains column
  trees) stands.
- Monitor/Deconstruct/Skin spec section 2: Monitor's Result output is
  slot 0.
- Export spec section 2: outputs JSON and Status; section 3: the
  default tessellation; section 3's Live row (and the paragraph in
  section 4 that repeats it): the hold reads the INPUT side, by count
  or by name, not the archived port counts of both sides; section 4:
  Uploaded's texts are Status lines.
- Columns spec: unchanged (RES already first).

## 12. Out of scope

The solvers' extra outputs (Thrust Mesh, Lines, Supports on TNA Solve
and FD Solve), Backend Health, Import Pieces, Armadillo Dual. Any change
to what Animate computes or draws. Any engine change.

## 13. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino. Check for OneDrive name-clash
files before every build and commit. git add by explicit path only.
