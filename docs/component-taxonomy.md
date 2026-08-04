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

The compiled native slice has twelve components. The C# classes under
`plugin/native_v02/Components` are authoritative for their current ports;
`plugin/components.toml` records the preserved script-backed v0.1 surface.
Every stage takes one primary typed object and returns it enriched, and a
nickname names the type carried on that port, not the word "input": `PAT`,
`SUP`, `PRB`, `RLX`, `RES`, and `STY` appear on exactly the ports that
carry those types, on both sides of every wire.

| Category | Component | Inputs | Outputs | Responsibility |
| --- | --- | --- | --- | --- |
| `01 Model` | **Pattern** | Geometry `G`, Mode `M`, Resolution `R`, Weld Tolerance `Tol` | Pattern `PAT` | Register a stable Rhino mesh or already-split planar line pattern as the shared spine's source geometry. Surface, Grid, Triangulation, and Skeleton modes fail explicitly until their generators exist. |
| `01 Model` | **Supports** | Pattern `PAT`, Anchor Points `A`, Snap Tolerance `Tol` (optional) | Anchored Pattern `SUP` | Snap explicit structural anchors to a registered Pattern; intermediate boundary vertices stay free for relaxation. |
| `01 Model` | **Loads** | Anchored Pattern `SUP`, Vector `V`, Node IDs `ID` (optional), Factor `F` | Problem `PRB` | Apply one load vector as a surface load (no Node IDs) or as point loads on explicit nodes, producing the Problem both solvers take. The TNA solve applies the surface load selfweight-style to the built surface's own tributary areas, updating as the shape rises (RhinoVault's loading model); FD approximates it on plan areas. Previews magnitude-scaled load arrows. |
| `02 Form Finding` | **TNA Relax** | Problem `PRB`, Force Density `q`, Boundary Sag `Sag %` | Relaxed `RLX` | Relax the Problem's plan Pattern, match unsupported-boundary sag, and build an inspectable unbalanced topological force dual. |
| `02 Form Finding` | **TNA Solve** | Relaxed `RLX`, Height `H` (optional), Iterations `I` (optional), Run `Run` | Result `RES`, Thrust Mesh `M`, Thrust Lines `L`, Supports `S` | Solve a Relaxed Pattern against the load case its Problem carries. Blank Height finds the natural equilibrium height; a number solves exactly to that crown height. Blank Iterations auto-converges the reciprocal diagrams: the worker keeps the best reciprocal state it finds and polishes past RhinoVault's five-degree gate within a bounded budget, stopping earlier at a tenth of a degree or on a genuine plateau; under five degrees reports as converged. Run false holds the solve. Returns the unified Result plus native geometry, and owns the shaded thrust-mesh preview. |
| `02 Form Finding` | **TNA Solve Algebraic** | Relaxed `RLX`, Height `H` (optional), Iterations `I` (unused), Run `Run` | Result `RES`, Thrust Mesh `M`, Thrust Lines `L`, Supports `S` | Interface-identical sibling of TNA Solve using the algebraic horizontal method: exact force densities from the equilibrium matrix in one sparse least-squares solve, machine-precision reciprocity wherever the pattern admits it, and a warning naming the edges that would need tension when it does not admit a compression-only self-stress. |
| `02 Form Finding` | **FD Solve** | Problem `PRB`, Force Density `q` (list, optional), Run `Run` | Result `RES`, Member Lines `L`, Supports `S` | Run whole-network COMPAS force-density form finding against the Problem's load case; returns the unified Result plus native geometry, and previews the solved network. Run false holds the solve. |
| `03 Visualise` | **Display** | Result `RES`, Style `STY` (optional), Elements `E` (optional), Metric `M`, Weight `W`, Vector Scale `VS`, Gap `G` | Thrust Mesh `TM`, Thrust Lines `TL`, Force Lines `FCL`, Load Lines `LL`, Reaction Lines `RL`, Report | Draw a solved Result's element lines: thrust network, the reciprocal force diagram (auto-fit beside the model), and mapped load/reaction/residual vectors, with one style preset, auto-scaling, and Elements/Metric filters. The shaded thrust mesh is TNA Solve's preview; here it is a data output only, and nothing draws in Grasshopper's default red. |
| `03 Visualise` | **Style** | Preset, Weight Scale `Weight`, Vector Scale `Vector` | Style `STY` | Bundle a display preset, weight scale, and vector scale for Display. |
| `03 Visualise` | **Deconstruct** | Result `RES` | Thrust Mesh `TM`, Member Lines `M`, Form Lines `FL`, `q`, `H`, `F`, Force State `S`, Member IDs `MID`, Node IDs `NID`, Support Points `SP`, Load Points `LP`, Load Vectors `LV`, Reaction Points `RP`, Reaction Vectors `RV`, Residuals `E`, Diagnostics `D`, Report | Extract thrust/form geometry, member forces, and nodal actions from one solved FD or TNA Result in one component. Reciprocal-only streams (Thrust Mesh, Form Lines, `H`) come out empty for FD. |
| `07 Delivery` | **Export** | Result `RES`, Format `F` (contract \| compas), Path `P` (optional), Write `W`, Name `N` (optional) | JSON `J`, Written `W` | Serialise a solved Result as portable Contract JSON or native COMPAS `json_dumps` geometry via the worker. The JSON output is always live; the file is written while the Write trigger is true, and the component keeps showing the last written file and time so a one-shot Button write stays visible after release. Path accepts a file or a folder; Name chooses the file name (keep it to bake over the same file, change it to bake a new one; without an extension `-contract.json`/`-compas.json` is appended so both exports of one geometry sit side by side, an explicit extension is used verbatim), a folder with a blank Name receives `ananke-export-<format>.json`, and missing parent folders are created. |
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

## Tab layout: one tab per COMPAS family

The subcategories are named after COMPAS's own extension families rather than
after invented groupings. That choice does real work: the tab tells you which
package family backs it, so "why is this tab empty" has an answer you can act
on instead of a shrug.

The rule is a four-way alignment:

```text
one tab  <->  one COMPAS family  <->  one capability flag  <->  one pyproject extra
```

`Backend Health` reports the capability flags. An inactive tab is therefore
always explained by a missing package, and installing an extra lights up a tab.
Nothing is hidden behind a silent fallback.

| Tab | COMPAS family | Packages | Capability | Extra | State |
| --- | --- | --- | --- | --- | --- |
| `01 Model` | core | `compas` | always | none | **Built** |
| `02 Form Finding` | Form Finding | `compas_fd`, `compas_tna` (`compas_ags` reserved) | `fd.solve`, `tna.solve` (`ags.solve` reserved) | `equilibrium` | **Built** |
| `03 Visualise` | none | none | always | none | **Built** |
| `04 Masonry` | Masonry | `compas_dem`, `compas_assembly`, `compas_cra` | `masonry` | `masonry` | Packages installed, components pending |
| `05 Engineering` | Engineering | `compas_fea2` plus a solver | `fea` | `fea` | Package installed, **no solver backend** |
| `06 Fabrication` | Digital Fabrication | `compas_fab`, `compas_robots` | `fab` | `fab` | Packages installed, components pending |
| `07 Delivery` | Data Modelling | `compas_model`, `compas_ifc` | `model`, `ifc` | `model`, `ifc` | Export **built**; `compas_model`/`compas_ifc` components pending |
| `90 System` | none | none | always | none | **Built** |

Capability flags and pyproject extras keep the names they already had before
this redesign; only the tab numbers and the components sitting under them
changed.

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

The tab sequence is renumbered and compacted from the constants the surface
used before this redesign (which read 04/06/07/08 with a gap): `03 Graphic
Statics` disappears because its display half folds into `Display` and a
future AGS solver belongs in `02 Form Finding`, which is where COMPAS
classifies `compas_ags` anyway; `05 Visualisation` becomes `03 Visualise`,
now hosting `Display`, `Style`, and `Deconstruct`; the reserved families close
up to `04 Masonry`, `05 Engineering`, and `06 Fabrication`, with `Delivery` at
`07`. Subcategory is display grouping only and component identity is the
GUID, so regrouping never invalidates a saved definition; the versioning
policy's breaking-change rules govern ports and semantics, not tabs.

### Why TNA is not its own tab

TNA is a method inside Form Finding, which is how COMPAS itself classifies it
alongside `compas_fd`, `compas_dr` and `compas_ags`. Giving it a tab would
break the alignment above and would separate it from the shared registration
spine it depends on. `02 Form Finding` holds three components (`TNA Relax`,
`TNA Solve`, `FD Solve`), and if it becomes crowded the answer is a
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

**`04 Masonry`.** `Block Tessellation` turning a `Result` into intrados and
extrados block geometry with interface frames; `Assembly` binding those blocks
into a contact graph; `Stability` running the coupled rigid-block solve for a
chosen build stage; `Formwork Reaction` extracting the load history the
falsework carries across the whole sequence. The last of these is the one that
does not exist anywhere else in the pipeline, because a thrust network
describes only the completed vault.

**`05 Engineering`.** `Structural Model` and `FEA Solve`, consuming the
existing `StructuralAnalysisCase`. The current `StructuralHandoff` already
reports exactly which material, section, restraint and load-combination inputs
are still missing, so this tab has a specified entry contract already.

**`06 Fabrication`.** `Robot` loading a `compas_robots` model, `Place Sequence`
ordering block placement from the assembly, and `Inverse Kinematics` returning
joint configurations per target frame. Analytical IK needs no backend beyond
`compas_fab` itself, so this tab can be useful before any ROS decision is made.

**`07 Delivery`.** `Export` already serialises a solved Result as portable
Contract JSON or native COMPAS JSON; `Compas Model` and `IFC Export` are the
reserved additions, wrapping formulations that `structural.py` already builds
and deliberately does not auto-save.

### Sequence across tabs

Left to right on the ribbon is close to the real workflow, which is the second
reason for the numbering:

```text
01 Model -> 02 Form Finding -> 04 Masonry -> 06 Fabrication
                |                  |              |
                +-> 05 Engineering                |
                +-> 07 Delivery <-----------------+

03 Visualise and 90 System read any stage without advancing it.
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
reads either solver's unified `Result`:

```text
TNA Solve.Result  or  FD Solve.Result
    --> Deconstruct --> Thrust Mesh / Member Lines / Form Lines /
                         q / H / F / Force State / Member IDs / Node IDs /
                         Support Points / Load Points / Load Vectors /
                         Reaction Points / Reaction Vectors / Residuals /
                         Diagnostics / Report
```

There is no separate bridge component or generic intermediate type:
`Deconstruct` accepts the same `Result` envelope both solvers return.
Reciprocal-only streams (Thrust Mesh, Form Lines, `H`) come out empty for an
FD result, and Deconstruct's Report states that explicitly rather than
erroring.

## Naming policy

Use functional names in the public plugin. Historical project names may remain
only in a compatibility namespace and migration notes. In particular, new
components and contracts use `ananke_equilibrium`, not an old implementation
name.
