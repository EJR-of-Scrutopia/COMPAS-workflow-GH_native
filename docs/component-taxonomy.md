# Grasshopper component taxonomy

The plugin boundary is deliberately smaller than the Python API. Grasshopper
components exchange typed bundles, while ordinary Grasshopper operations can
still be inserted between stages to edit geometry, select branches, or drive
parameters.

## Contract families

| Family | Contract | Purpose |
| --- | --- | --- |
| Registration | `TnaPatternDto` | One registered Pattern: topology (nodes, edges, optional faces, source mapping), pattern mode, resolution, weld tolerance, and provenance. |
| Anchoring | `AnchoredPatternDto` | The Pattern with explicit anchor node IDs and snap tolerance resolved by Supports. |
| Problem | `ProblemDto` | The Anchored Pattern bundled with one load case; the shared input both solvers take. |
| Relaxation | `RelaxedDto` (wraps `TnaPreparedDto`) | Relaxed pattern, boundary-opening records, form graph, and unbalanced topological force graph, paired with the Problem it will be solved against. |
| Solver settings | `TnaControlDto` | Explicit, serialisable height/iteration solve settings built internally by TNA Solve from its Height and Iterations inputs, and carried on the Result for provenance. |
| Results | `ResultDto` | One unified solved-result envelope for both FD and TNA: geometry, edge forces, reactions, residuals, provenance, units, and diagnostics, with an optional reciprocal block (form/force graphs, mappings, edge states) present only for TNA. `TnaResultDto` and `EquilibriumResultDto` merged into this one contract as part of the redesign. |
| Display | `StyleDto` | Display-only preset, weight scale, and vector scale kept separate from solved data. |
| Design extensions | `BranchDesign` | Later response-field, branch-layout, and Steiner-junction decisions. |
| Delivery extensions | `StructuralDefinition`, `FEAResult`, `IFCPackage` | Later structural modelling, analysis, and IFC hand-off contracts. |

The precise C# definitions under `plugin/native_v02/Contracts` are the
source of truth for what crosses onto the canvas; the table above describes
their responsibilities, not an invitation to duplicate them inside
Rhino-specific code. The Python worker's own dataclasses in
`src/ananke_equilibrium/contracts.py` (`TopologyBundle`, `SupportSet`,
`LoadCase`, `FDConfig`, `HeightControl`, `TNAConfig`, `SolvedCase`,
`DiagramStyle`, `DiagramBundle`, and others) sit behind the worker protocol
and were not touched by this redesign; the C# contracts above wrap and adapt
them for the canvas.

## Native v0.2 component surface

The compiled native slice has twenty components, under six tabs named after
the stages of the chain a Result travels: model, solve, mould, read, deliver,
and one for the backend itself. The C# classes under
`plugin/native_v02/Components` are authoritative for their current ports;
`plugin/components.toml` records the preserved script-backed v0.1 surface.
Every stage takes one primary typed object and returns it enriched, and a
nickname names the type carried on that port, not the word "input": `PAT`,
`SUP`, `PRB`, `RLX`, `RES`, and `STY` appear on exactly the ports that
carry those types, on both sides of every wire.

| Category | Component | Inputs | Outputs | Responsibility |
| --- | --- | --- | --- | --- |
| `01 Model` | **Pattern** | Geometry `G`, Mode `M`, Resolution `R`, Weld Tolerance `Tol`, Principal Lines `P` (optional, flattened) | Pattern `PAT` | Register a stable Rhino mesh or already-split planar line pattern as the shared spine's source geometry. Surface, Grid, Triangulation, and Skeleton modes fail explicitly until their generators exist. `Principal Lines` are the notched bars of the reconfigurable mould, drawn as curves over the pattern and matched here, in plan, to runs of pattern vertices carried downstream as indices; this is the only way a principal line enters the chain. Curves that place no bar are an error and no Pattern is emitted; a dropped curve is a warning; two curves on one run are merged with a remark. Pattern is the only component that previews the bars, in red at the net's own weight; the message line counts them. |
| `01 Model` | **Supports** | Pattern `PAT`, Anchor Points `A`, Snap Tolerance `Tol` (optional) | Anchored Pattern `SUP` | Snap explicit structural anchors to a registered Pattern; intermediate boundary vertices stay free for relaxation. Carries the Pattern's principal runs through unchanged and derives none. |
| `01 Model` | **Loads** | Anchored Pattern `SUP`, Vector `V`, Node IDs `ID` (optional), Factor `F` | Problem `PRB` | Apply one load vector as a surface load (no Node IDs) or as point loads on explicit nodes, producing the Problem both solvers take. The TNA solve applies the surface load selfweight-style to the built surface's own tributary areas, updating as the shape rises (RhinoVault's loading model); FD approximates it on plan areas. Previews magnitude-scaled load arrows. |
| `02 Solve` | **TNA Relax** | Problem `PRB`, Force Density `q`, Boundary Sag `Sag %`, Floating Anchors `FA` (optional, flattened) | Relaxed `RLX` | Relax the Problem's plan Pattern, match unsupported-boundary sag, and build an inspectable unbalanced topological force dual. |
| `02 Solve` | **TNA Solve** | Relaxed `RLX`, Height `H` (optional), Iterations `I` (optional), Run `Run` | Result `RES`, Thrust Mesh `M`, Thrust Lines `L`, Supports `S` | Solve a Relaxed Pattern against the load case its Problem carries. Blank Height finds the natural equilibrium height; a number solves exactly to that crown height. Blank Iterations auto-converges the reciprocal diagrams: the worker keeps the best reciprocal state it finds and polishes past RhinoVault's five-degree gate within a bounded budget, stopping earlier at a tenth of a degree or on a genuine plateau; under five degrees reports as converged. Run false holds the solve. Returns the unified Result plus native geometry, and owns the shaded thrust-mesh preview. |
| `02 Solve` | **TNA Solve Algebraic** | Relaxed `RLX`, Height `H` (optional), Run `Run` | Result `RES`, Thrust Mesh `M`, Thrust Lines `L`, Supports `S` | Sibling of TNA Solve using the algebraic horizontal method: a short classic warm-up projected onto the self-stress space, giving the classic solver's character with machine-precision reciprocity. No Iterations input; the direct solve has no iteration knob. Reports how many edges need tension when the pattern admits no compression-only self-stress (the iterative solver expresses the same fact as residual unbalanced thrust). |
| `02 Solve` | **FD Solve** | Problem `PRB`, Force Density `q` (list, optional), Run `Run` | Result `RES`, Member Lines `L`, Supports `S` | Run whole-network COMPAS force-density form finding against the Problem's load case; returns the unified Result plus native geometry, and previews the solved network. Run false holds the solve. |
| `03 Mould` | **Animate** | Result `RES`, Time `T`, Pre-Sag `PS`, Extension `E` | Result `RES` | Replay the reconfigurable mould building itself from one timeline slider. Everything is read from the solved Result: relaxing the free nodes with the bars and anchors pinned gives the `bare` surface (Schek's Theorem 1 minimum-way surface, so flat or saddled and never domed) which carries the height, the remainder to the Result is the relief the steppers reel which carries the sag, the ground is the level the anchors sit at, and the surface is rebuilt from the Result's own faces. A frame is `start + lift x (bare - start) + sag x relief`, with the plan drawing in by sag. `Time` 0-100 runs four phases: reel (0-30) draws the net in on the ground to `Pre-Sag`, raise (30-60) rotates the columns up about their feet and lifts the bars, finish (60-90) reels the rest and tensions both axes, hold (90-100) keeps the shape while load arrives. Columns are read from the incoming Result, so **Columns** must sit upstream for them to rise; this component runs no equilibrium check and places no columns. Columns exist from frame zero: every tree stands on the foot **Columns** built for it, and its TRUNK lies flat along its rail at time zero and turns about the foot as one body as its notch rises, keeping its fork at its built fraction (heads by `HeadNode`), its length being the ram; the ARMS follow their own notches, so an arm's length changes with the net and `animate.arm_stretch` reports the worst. `Extension` is the ram's range and a trunk outside it is reported, not moved. `Perimeter Lines` gives one closed curve per boundary loop, branched as Perimeter Nodes; a group whose walk does not return to its first node comes back as an OPEN polyline instead, and where the Result carries neither faces of its own nor a pattern topology with faces the perimeter is only a degree estimate, so the port is left empty and `animate.perimeter_estimated` says why. `Result` carries the frame in the Mould block (time, phase word, live net, live column nodes); wire it to **Frame** for the geometry at that frame, to **Monitor** for the numbers and to **Diagnose** for the words. |
| `03 Mould` | **Columns** | Result `RES`, Branching `B`, Type `T` | Result `RES` | Hold every notch of every principal line with a column head. The Result is the form finder: the principal lines travel in it, resolved by Pattern, the load each notch hands its bar comes from the Result's own member forces, and the ground is the level the anchors sit at. `Branching` (1, 2, 3) groups neighbouring notches into trees of that size, mirrored about the middle of each span with the remainder at the anchors, and the centre notch of an odd count standing alone; a bar is cut into spans at its anchors (a held ring gives two half-spans and no column at the ring) and at a ring tree, which serves bars ending on a free central rim from one foot at the plan intersection of their end tangents. Before a single foot is placed the trees' resultants are MIRRORED about each span's midpoint (a tree and its mirror get equal and opposite along-chord pulls, the centre tree none) and their ALONG and VERTICAL profiles averaged across every span that holds the same NUMBER of notches and whose chord is within a tenth of the family lead's length, because a solved net's forces are never mirrored to the last digit and that is what used to put one principal line's columns out of step with another's. Length is in that key because the aim is shared, and a short steep span handed a long flat one's aim can put its foot beyond its own anchors. The ACROSS-chord pull is never shared: it stays each span's own, mirrored within that span, because it is the one part of the reading that depends on which end of the bar was traced first, and a rib lying in the structure's own mirror plane would otherwise be handed a lean whose side its trace direction picked. Along and down do not depend on it, so bars congruent by translation (a barrel traced in mixed directions) and bars congruent by rotation (opposite ribs of a dome) both come out carrying the same columns by construction. So a family takes the along-chord and vertical disagreement out from between neighbouring principal lines and leaves the across-chord disagreement standing: two neighbours handed different across-chord pulls still lean slightly differently across their chords, because that is their own net talking and not an artefact of which way the curves were drawn. A span whose free notches are NOT symmetric about its chord midpoint, each notch's partner standing within a quarter of that span's own notch spacing of where the mirror would put it, which is what a crossing taking an interior notch or a free bar end leaves behind, is placed unmirrored: its own aims, its bands read off each tree's own projection, and no merge; **Diagnose** says how many. `Type` is how the trees meet the ground: 0 stands each on its own foot on the line of its force; 1 to 4 gather each span's trees onto that many mirrored feet in bands about the span's midpoint, the band being decided per mirror pair so that a pair always lands in mirrored bands (a centre tree takes the central band at an odd Type, and at an even Type stands on its own foot in the mirror plane), and each band's foot standing at the plan CENTROID of the mains on it, which is what mirrors when the chord runs along neither axis; -1 is Auto. A trunk that would lean past 60 degrees to its shared foot is PEELED, standing on its own foot instead, and a band that loses trees that way rebuilds its foot from the survivors; where EVERY trunk peels the component says nothing gathered and the columns stand as Type 0's geometry. A peel is reported as information, not as a fault. The level is never refused for it: a level is judged, not refused, and Auto builds all five and places the shortest load path among those whose members do not collide, ties to the higher. Feet merge in one case only, a mirrored pair inside the clearance, which stands on the MEAN of the pair's two feet, in the span's mirror plane rather than on the chord midpoint a plan-curved bar's notches sit well off; any other two feet closer than the clearance stay two and are reported. The fork of every tree lies on the segment from its foot to its main notch at 65% of the notch height, so trunk and main branch are one straight line. The built trees leave ONLY inside the Result's Mould block. **Deconstruct** hands the geometry back as trees, **Monitor** the numbers, **Diagnose** the words. |
| `04 Read` | **Display** | Result `RES`, Style `STY` (optional), Elements `E` (optional), Metric `M`, Weight `W`, Vector Scale `VS`, Gap `G` | none (viewport only) | Draw a solved Result's element lines: thrust network, the reciprocal force diagram (auto-fit beside the model), and mapped load/reaction/residual vectors, with one style preset, auto-scaling, and Elements/Metric filters. The shaded thrust mesh is TNA Solve's preview and the geometry is **Deconstruct**'s; this component draws and emits nothing, so nothing here can drift from the lines Deconstruct hands back. The two readings that are its own are Remarks (an FD Result has no reciprocal diagram, and Metric `H` on one falls back to `F` magnitude), and the chin carries the weight and vector scales the drawing was made at, saying `auto` where the component chose the vector scale itself. |
| `04 Read` | **Style** | Preset, Weight Scale `Weight`, Vector Scale `Vector` | Style `STY` | Bundle a display preset, weight scale, and vector scale for Display. |
| `04 Read` | **Deconstruct** | Result `RES` | Thrust Mesh `TM`, Member Lines `M`, Form Lines `FL`, Member IDs `MID`, Node IDs `NID`, Support Points `SP`, Load Points `LP`, Load Vectors `LV`, Reaction Points `RP`, Reaction Vectors `RV`, Columns `CO`, Heads `HD`, Feet `FT`, Force Lines `FCL` | The GEOMETRY of one solved FD or TNA Result, and nothing else: member lines as a tree with one branch per principal line and the infill last, supports and reactions as one branch per connected strip walked end to end, the built column trees from the Mould block one branch per tree. Every number that used to sit here (q, H, F, force state, residuals) is on **Monitor**, branched and ordered identically, so Deconstruct's line at branch b item i and Monitor's number at branch b item i are the same member. The cells moved to **Skin**. `Force Lines` is the reciprocal force diagram at its own coordinates, branched with Member Lines and Form Lines, appended at slot 13 so no existing wire moved. Reciprocal-only streams (Thrust Mesh, Form Lines, Force Lines) come out empty for FD. |
| `04 Read` | **Frame** | Result `RES` | Mesh `M`, Cables `C`, Principal Lines `PL`, Principal Nodes `PN`, Anchor Nodes `AN`, Perimeter Nodes `PRN`, Perimeter Lines `PRL`, Columns `CO`, Phase `PH` | The GEOMETRY of the state a Result stands at: the net's surface, every cable as a tree branched by principal line with the infill last, the notched bars and their notches, the anchors by connected strip, the boundary by loop, and the live column trees. A Result from a solver or from **Columns** carries no frame, so this is the finished vault; a Result from **Animate** carries one, so this is that frame of the build, and `Phase` says which (`reel`, `raise`, `finish`, `hold`, or `final` when there is no frame). One set of helpers builds this and Animate's viewport, so what is drawn and what is emitted cannot drift. Mesh is empty for FD, which carries no faces; Columns is empty unless the Result carries columns. The geometry outputs start with their previews HIDDEN, as every other reader's do: **Animate** draws the machine and Frame carries the data, and each port can still be switched on from its own context menu. The chin reads the phase, or `No Result` with nothing wired. |
| `04 Read` | **Monitor** | Result `RES`, EI `EI`, EA `EA` (optional), Tolerance `Tol`, Cable Capacity `CC` (optional), Column Capacity `CO` (optional) | Result `RES`, Member Force `F`, Force Density `q`, Horizontal Force `H`, Slack `SL`, Spool Length `SP`, Unstrained Length `UL`, Anchor Along `AA`, Anchor Across `AX`, Tip Reaction `TR`, Column Force `CF`, Thrust `TH`, Lean `LN`, Deviation `DV`, Deviation Stats `DS`, Reachable `RC`, Unreachable `UN`, Bar Sag `BS`, Residuals `E`, Cable Utilisation `CU`, Column Utilisation `CLU` | Every NUMBER a Result and its frame carry, as trees aligned item for item with **Deconstruct**'s geometry (member trees with Member Lines, anchor trees with Reaction Points, column trees with Columns and Heads) and with **Frame**'s Principal Nodes (Bar Sag). The machine's own readings from document 07: the spool length, one branch per bar (strained; unstrained when EA is wired), each anchor's reaction split along its tensioner axis and across it (the across part is the anchorage's), the tip reaction under every head, the signed deviation of this frame from the solved shape with RMS, max and 95th percentile, and whether every node is within Tolerance with the set that is not. Slack marks a member whose force opposes the Result's sign convention. Utilisation is the absolute force over capacity, filled only against a capacity the author wires; otherwise every figure is a demand, not a verdict. The Karamba round trip is a manual one fed by Member Force and Column Force with the matching Deconstruct lines. `Result` passes through with Monitor's diagnostics. |
| `04 Read` | **Skin** | Result `RES`, Course Height `CH` | Face Polylines `FP`, Face Courses `FC` | The cells the surface is built from: one closed polyline per face of the thrust mesh, as a tree branched by course (faces banded by centroid height from the lowest, `Course Height` per band, bottom row 0), with the course per face branched identically. The ready-made Cells and Courses inputs for **Export**, which flattens them. Empty for FD, which carries no faces. |
| `04 Read` | **Diagnose** | Result `RES` | Text `T`, Source `S`, Code `C`, Severity `SV`, Message `M`, Value `V` | Read every diagnostic the chain wrote into a Result and say in words what is wrong and which lever to pull: errors first, grouped by the component that raised them, the solver's own report last. Adds the cross-checks no single component can make (Columns with no principal runs, a frame with no columns, every anchor isolated, more than half the net wanting to be pushed). Replaces the Report ports the mould components used to carry. |
| `05 Deliver` | **Export** | Result `RES`, Path `P` (optional), Write `W`, Name `N` (optional), Cells `C` (optional, flattened), Courses `CO` (optional, flattened), Live `L`, Studio `S`, Column Radius `R` | JSON `J` (list), Status `ST` | Write everything a solved Result can be, in one component: the portable Contract JSON and the native COMPAS document always, the `bench.tessellation/1` sidecar always for a TNA Result, from **Skin**'s cells when they are wired and from the Result's own faces (one cell per face, course 0) when they are not, declaring `pattern` `authored` in the first case and `faces` in the second, and nothing at all for an FD Result, which carries no faces, and a `bench.columns/1` mesh (a prism per member at `Column Radius`, with the members beside it) when the Result's Mould block carries columns. `Write` puts the set under `Path` as `<Name>-<kind>.json`; `Status` lists what was written. `Live` pushes the same set to the studio at `Studio` on every solve, debounced half a second so a scrub sends only the final state, retrying a 409 (a run in flight for that study) after 2, 4 and 8 seconds and then deferring; an identical set is not sent twice; `Status` says what happened per kind, and a failure is a warning, never an error. `Path` must be rooted; a bare name or a relative path is refused with a warning and nothing is written. `Name` must be one path segment. Only the COMPAS document needs the worker, so a worker failure drops the compas kind from `JSON` with a warning and the rest of the set stands. Reopening a definition saved before this rework: every output wire moves, because the six ports are now two. The old Contract JSON wire lands on `JSON`, which carries the whole set as a list of texts, each naming its own kind; the old COMPAS JSON wire lands on `Status`, which is not JSON at all; the rest are dropped. Live is NOT held by that load: the hold reads the INPUT side, and the nine inputs did not move. It is held after a load whose inputs DID move, by count or by name, which is a definition saved before the export-live work; while held, Live true enqueues nothing until Live is set off and then on again, and `Status` says so. The studio-side tasks this feeds are in `docs/studio-tasks-2026-08-28.md`. |
| `05 Deliver` | **Import Pieces** | Path `P` | Meshes `M`, Keys `K`, Supports `S`, Base Mesh `B`, Diagnostics `D` | Read a studio pieces document back into Rhino: the cut voussoir meshes branched by course, their keys and support flags branched identically, and the base mesh the cutting ran against. |
| `05 Deliver` | **Armadillo Dual** | Result `RES`, Size `S` | Cells `C`, Courses `CO`, Flowlines `FL`, Diagnostics `D` | Force-aligned voussoir cells from a solved Result: the flow lines advected through the thrust field, the dual cells built on them at the target size, and the course band per cell. Feeds **Export**'s Cells and Courses directly. |
| `90 System` | **Backend Health** | none | Ready `R`, Python `Py`, Packages `Pkg`, Capabilities `Cap`, Report `Out` | Verify the persistent Python worker, package environment, and protocol. |

### Port rules

- Components accept a primary typed bundle rather than parallel lists whose
  indices can silently drift.
- A solver returns one `Result`; Display, Deconstruct, and Export all read
  that same envelope rather than rerunning the solver.
- Rich TNA and FD state is queried by one grouped component, `Deconstruct`,
  rather than several narrow ones whose outputs a definition must remember
  to wire in the right combination.
- Status is concise and human-readable. Structured warnings and numerical
  diagnostics remain on the bundle.
- Rhino geometry conversion happens in the Grasshopper adapter layer.
  Contracts and solvers must not import RhinoCommon.
- Grasshopper data trees are flattened or mapped explicitly at the adapter
  boundary; no data-tree object enters the numerical core.
- Units and sign conventions are explicit in contracts and reports.

### Suggested value lists

A component with a fixed vocabulary offers a populated dropdown on drop, so the
valid values are visible on the canvas without reading documentation.
`ComponentValueListSpec` declares them and `SuggestedValueListPlacement` places
them, once, for every native base class.

The placement has one non-obvious requirement. `Attributes.Pivot` is not a
stored point; it is read off the centre of `Bounds`, and `Bounds` on a freshly
dropped component holds whatever the last layout pass computed rather than
where the object visibly sits. Reading it in `AddedToDocument` without forcing
a layout lands every list near the canvas origin. The fix is to call
`ExpireLayout` then `PerformLayout` on the owning component synchronously
before reading the input's pivot, then again on the new list so it sizes to the
items it now holds. Deferring with `ScheduleSolution` does not help, because
waiting for a layout is not the same as causing one.

This pattern is proven in the QS Intelligence Grasshopper plugin, whose
`ValueLists.cs` documents the two earlier attempts that failed and why. Keep
the two implementations consistent if either changes.

## Tab layout: one tab per stage of the chain

The tabs used to be named after COMPAS's own extension families. That
answered "which package family backs this" and nothing else, and it put eight
of the nineteen components under one tab while three tabs stood empty. They
are named after the WORK now, in the order the work happens, so the ribbon
reads left to right the way a canvas is built: model a pattern, solve it,
build the mould that makes it, read what came out, deliver it.

The package alignment has not gone; it has stopped being the name. Two of the
six panels are backed by a COMPAS family and report a capability flag through
`Backend Health`, and the three reserved families keep their tabs at the end,
renumbered out of the way.

| Tab | Holds | Packages | Capability | Extra | State |
| --- | --- | --- | --- | --- | --- |
| `01 Model` | Pattern, Supports, Loads | `compas` | always | none | **Built** |
| `02 Solve` | TNA Relax, TNA Solve, TNA Solve Algebraic, FD Solve | `compas_fd`, `compas_tna` (`compas_ags` reserved) | `fd.solve`, `tna.solve` (`ags.solve` reserved) | `equilibrium` | **Built** |
| `03 Mould` | Columns, Animate | none | always | none | **Built** |
| `04 Read` | Deconstruct, Monitor, Skin, Diagnose, Frame, Style, Display | none | always | none | **Built** |
| `05 Deliver` | Export, Import Pieces, Armadillo Dual | `compas_model`, `compas_ifc` | `model`, `ifc` | `model`, `ifc` | Export, Import Pieces and Armadillo Dual **built**; `compas_model`/`compas_ifc` components pending |
| `06 Masonry` | reserved | `compas_dem`, `compas_assembly`, `compas_cra` | `masonry` | `masonry` | Packages installed, components pending |
| `07 Engineering` | reserved | `compas_fea2` plus a solver | `fea` | `fea` | Package installed, **no solver backend** |
| `08 Fabrication` | reserved | `compas_fab`, `compas_robots` | `fab` | `fab` | Packages installed, components pending |
| `90 System` | Backend Health | none | always | none | **Built** |

Capability flags and pyproject extras keep the names they had before this
rework; only the tabs, their numbers and the components under them changed.
Subcategory is display grouping only and component identity is the GUID, so
regrouping never invalidates a saved definition: nothing on a canvas moves
when a component changes tab.

### The Engineering flag is deliberately stricter than the others

`compas_fea2` can express a model without being able to analyse one, because
analysis lives in a separate backend plugin for Abaqus, ANSYS, SOFiSTiK or
OpenSees. **None of those plugins are published to PyPI**, so the gap is the
normal case rather than an edge case: installing the `fea` extra gets you a
modelling API and no solver.

The capability reporting therefore splits the claim:

```text
fea.model      compas_fea2 is importable, a model can be expressed
fea.backends   the solver plugins actually installed, by name
fea            a backend is present, so an analysis can genuinely run
```

`fea` stays false until a backend is installed from source. That keeps the
promise the design rules make everywhere else: package detection is not a claim
that the workflow exists.

The tab sequence is renumbered and renamed from the COMPAS-family scheme this
rework replaces: `02 Form Finding` becomes `02 Solve`; `03 Visualise`, which
hosted `Display`, `Style`, `Deconstruct`, `Animate`, `Columns`, `Monitor`,
`Skin` and `Diagnose` in one tab, splits into `03 Mould` (`Columns`,
`Animate`) and `04 Read` (`Deconstruct`, `Monitor`, `Skin`, `Diagnose`, the
new `Frame`, `Style`, `Display`); the reserved families close up to
`06 Masonry`, `07 Engineering` and `08 Fabrication`, and `Deliver` moves
ahead of them to `05`, because it is the one reserved family already
carrying built components. Subcategory is display grouping only and
component identity is the GUID, so regrouping never invalidates a saved
definition; the versioning policy's breaking-change rules govern ports and
semantics, not tabs.

### Why TNA is not its own tab

TNA is a method inside Form Finding, which is how COMPAS itself classifies it
alongside `compas_fd`, `compas_dr` and `compas_ags`. Giving it a tab would
break the alignment above and would separate it from the shared registration
spine it depends on. `02 Solve` holds four components (`TNA Relax`,
`TNA Solve`, `TNA Solve Algebraic`, `FD Solve`), and if it becomes crowded the answer is a
naming prefix (`TNA ...`, `FD ...`, which the components already use) rather
than a new tab that implies a new backend.

### The Patterns family already has a home

COMPAS lists Patterns (`compas_skeleton`, `compas_singular`) as its own family,
but in this plugin it is not a tab. It is the missing backend for modes that
already exist and already fail honestly: `Pattern` offers `Surface`,
`Grid`, `Triangulation` and `Skeleton`, and rejects all four with an actionable
error because no generator exists. `compas_skeleton` 2.0.1 is COMPAS 2
compatible and is the natural implementation of the `Skeleton` mode.
`compas_singular` is conda-only and would back quad-mesh singularity
patterning. Adopting them fills in existing modes rather than adding a tab.

### What each reserved tab would hold

Sketched to the same rule the built tabs follow: a stage returns one typed
bundle, and downstream components read that bundle rather than recomputing.

**`06 Masonry`.** `Block Tessellation` turning a `Result` into intrados and
extrados block geometry with interface frames; `Assembly` binding those blocks
into a contact graph; `Stability` running the coupled rigid-block solve for a
chosen build stage; `Formwork Reaction` extracting the load history the
falsework carries across the whole sequence. The last of these is the one that
does not exist anywhere else in the pipeline, because a thrust network
describes only the completed vault.

**`07 Engineering`.** `Structural Model` and `FEA Solve`, consuming the
existing `StructuralAnalysisCase`. The current `StructuralHandoff` already
reports exactly which material, section, restraint and load-combination inputs
are still missing, so this tab has a specified entry contract already.

**`08 Fabrication`.** `Robot` loading a `compas_robots` model, `Place Sequence`
ordering block placement from the assembly, and `Inverse Kinematics` returning
joint configurations per target frame. Analytical IK needs no backend beyond
`compas_fab` itself, so this tab can be useful before any ROS decision is made.

**`05 Deliver`.** `Export` already writes a solved Result's whole set,
one list of self-describing JSON texts, the contract and the COMPAS document
always, a tessellation for every Result and a columns mesh where the Mould
block carries one, to file and live to the studio; `Compas Model` and
`IFC Export` are the reserved additions, wrapping formulations that
`structural.py` already builds and deliberately does not auto-save.

### Sequence across tabs

Left to right on the ribbon is close to the real workflow, which is the second
reason for the numbering:

```text
01 Model -> 02 Solve -> 03 Mould -> 06 Masonry -> 08 Fabrication
                |            |          |               |
                |            |          +-> 07 Engineering
                +------------+----------+-> 05 Deliver

04 Read and 90 System read any stage without advancing it.
```

## Roadmap components

These are separate stages, not extra modes hidden inside the initial solvers.
The compact RhinoVault-style authoring surface is now implemented as the
shared spine itself: `Pattern -> Supports -> Loads -> TNA Relax ->
TNA Solve`, with `FD Solve` branching off the same `Problem`. See
[`architecture/rhinovault-native-stages.md`](architecture/rhinovault-native-stages.md)
for the exact implemented boundary and later design-by-statics work.

| Stage | Planned component | Main result |
| --- | --- | --- |
| Environmental/design input | **Response Field** | Weighted attractor, clearance, canopy, obstacle, or performance fields. |
| Topology generation | **Branch Layout** | Candidate trunk/branch graph derived from a field and target points. |
| Junction optimisation | **Steiner** | Branching topology and junction positions satisfying the chosen 120-degree policy where the Euclidean Steiner assumptions apply. |
| Reciprocal equilibrium | **AGS Solve** | Force and form diagrams with explicit reciprocal correspondence using `compas_ags`. |
| Force-flow query | **TNA Force Flow** | Ranked and traceable discrete edge paths using `q`, `H`, `F`, or load-path metrics. |
| Direction registration | **GS Direction Register** | Ordered section paths and effective transferred loads for a declared direction. |
| Directional drawing | **GS Funicular 2D** | Dashed load line, recovered pole, pole rays, funicular polygon, labels, and closure errors for an ordered path. |
| Spatial drawing | **Graphic Statics 3D** | Explicit spatial form/force cells and reciprocal correspondence where the selected method supports them. |
| Column design | **TNA Column Heads / Column Actions** | Candidate heads, augmented supports, re-solved reactions, and branch-tip actions. |
| Structural assembly | **Structural Model** | `compas_model` elements, materials, sections, connections, supports, and load cases. |
| Verification | **COMPAS FEA** | Analysis-ready model plus displacements, internal forces, utilisation inputs, and solver provenance. |
| Information delivery | **IFC** | Mapped products, relationships, properties, analysis provenance, and an IFC file/package. |

The field, branching, and Steiner stages may be used before either FD or TNA,
with ordinary Grasshopper geometry operations inserted between them. This
keeps generative design decisions distinct from equilibrium solving.

## Whole-object registration

`Pattern` registers all supplied geometry in one pass:

1. Extract nodes and candidate edges from lines, polylines, or mesh topology.
2. Weld coincident endpoints using the supplied tolerance.
3. Retain a mapping from every source item to registered node and edge IDs.
4. Identify connected components, boundaries, supports, faces where available,
   non-manifold conditions, duplicates, and zero-length members.
5. Return one registered `Pattern`, even when diagnostics reveal several
   connected components.

This is what lets TNA or FD act on the object as a network instead of solving
each input line independently. `Supports` and `Loads` then carry that
registered Pattern into the shared `Problem` both solvers take; an arbitrary
collection of curves is not automatically a funicular form.

`Pattern` exposes `mm`, `cm`, `m`, `in`, and `ft` as canonical coordinate
units. These are explicit dimensional metadata, not an implicit scale
operation: coordinates remain in the supplied unit, load vectors remain in
the selected force unit, and FD force density has units of force/length. A
faced mesh can be passed directly to FD because FD consumes its registered
edge network; the same topology retains its faces for TNA.

## Graphic-statics representation

A display bundle must preserve equilibrium correspondence rather than merely
draw member magnitudes:

- every form edge has a stable ID and a linked reciprocal force edge;
- external loads and reactions are explicit, ordered edges in the force
  diagram;
- force polygons or reciprocal cells close within a reported tolerance;
- direction, compression/tension convention, scale, and diagram origin are
  metadata;
- closure error is visible and numerically accessible.

A single cable or arch under parallel loads often produces the familiar
triangular outer force polygon with a fan of rays. A branching frame generally
has several joint polygons or reciprocal cells and should not be forced into
one decorative triangle. `AGS Solve` and the directional graphic-statics
stages therefore own any new reciprocal construction; `Display` only draws
structured solver or construction results, gaining a renderer for each new
diagram kind rather than a new display component.

For TNA, `TNA Relax` already serialises the initial topological force graph
beside its form graph in the `Relaxed` state; that graph is not yet
horizontally balanced. `TNA Solve` returns the solved reciprocal force
diagram as part of the unified `Result`. `Display` packages and previews that
final state directly from the `Result`, without a separate
reciprocal-construction step: it applies a visual preset (via `Style`) and
exposes the diagram roles (form, thrust, force, loads, reactions) as ordinary
Rhino lines, while `Deconstruct` is the explicit data-extraction boundary for
the same `Result`. A classical dashed load-line/pole construction is
extracted separately from an ordered directional path.

Before vertical calibration fixes the physical scale, horizontal-equilibrium
`q` and `H` are relative quantities; the final spatial `F` follows the lifted
thrust geometry. In a final `Result`, `q`, `H`, and `F` are equilibrium
demands in the selected scale, not material capacity or utilisation. See
[`architecture/tna-graphic-statics-columns.md`](architecture/tna-graphic-statics-columns.md).

## Focused result queries

`Deconstruct` replaced the four old query components (`TNA Geometry`,
`TNA Members`, `TNA Actions`, `Result Breakdown`) with one component that
reads either solver's unified `Result`. It carries the GEOMETRY and nothing
else:

```text
TNA Solve.Result  or  FD Solve.Result
    --> Deconstruct --> Thrust Mesh / Member Lines / Form Lines /
                         Member IDs / Node IDs / Support Points /
                         Load Points / Load Vectors / Reaction Points /
                         Reaction Vectors / Columns / Heads / Feet
```

Every number that used to leave this component (`q`, `H`, `F`, force state,
residuals) is on **Monitor**, branched and ordered identically, so a line at
branch b item i there and a number at branch b item i here are the same
member; the cells of the surface are on **Skin**; and the words, including
everything a Result cannot answer, are on **Diagnose**.

There is no separate bridge component or generic intermediate type:
`Deconstruct` accepts the same `Result` envelope both solvers return.
Reciprocal-only streams (Thrust Mesh, Form Lines) come out empty for an FD
result, and the diagnostics **Diagnose** prints state that explicitly rather
than erroring.

## Naming policy

Use functional names in the public plugin. Historical project names may remain
only in a compatibility namespace and migration notes. In particular, new
components and contracts use `ananke_equilibrium`, not an old implementation
name.
