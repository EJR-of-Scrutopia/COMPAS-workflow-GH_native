# Grasshopper component taxonomy

The plugin boundary is deliberately smaller than the Python API. Grasshopper
components exchange typed bundles, while ordinary Grasshopper operations can
still be inserted between stages to edit geometry, select branches, or drive
parameters.

## Contract families

| Family | Contract | Purpose |
| --- | --- | --- |
| Registration | `TopologyBundle` | One registered object: nodes, edges, optional faces, source mapping, groups, tolerances, and topology diagnostics. |
| Staged TNA | `TnaPattern`, `TnaPrepared` | Stable source pattern with explicit anchors, then the relaxed pattern, boundary-opening records, form graph, topological force graph, mappings, and preparation diagnostics. |
| Actions | `LoadCase` | Named nodal loads, load metadata, and the mapping back to registered nodes. |
| Solver settings | `FDConfig`, `HeightControl`, `TNAConfig` | Explicit, serialisable controls for force-density or thrust-network solving. |
| Results | `SolvedCase`, `TnaResult` | Immutable solved geometry, edge forces, reactions, residuals, provenance, units, and solver diagnostics. `TnaResult` additionally preserves the reciprocal form/force pair and stable correspondence. |
| Display | `DiagramStyle`, `DiagramBundle`, `GraphicDiagram` | Display policy and Rhino-ready preview payloads kept separate from solver data. `GraphicDiagram` is the compact native TNA reciprocal bundle. |
| Design extensions | `BranchDesign` | Later response-field, branch-layout, and Steiner-junction decisions. |
| Delivery extensions | `StructuralDefinition`, `FEAResult`, `IFCPackage` | Later structural modelling, analysis, and IFC hand-off contracts. |

The precise Python definitions are the source of truth. The table above
describes their responsibilities, not an invitation to duplicate them inside
Rhino-specific code.

## Native v0.2 component surface

The compiled native slice has twenty components. The C# classes under
`plugin/native_v02/Components` are authoritative for their current ports;
`plugin/components.toml` records the preserved script-backed v0.1 surface.

| Category | Component | Inputs | Outputs | Responsibility |
| --- | --- | --- | --- | --- |
| `01 Model` | **Network** | geometry, kind, weld tolerance, length unit | `Topology` | Weld lines, polylines, or mesh edges into one registered topology, preserve faces and source IDs, and diagnose the whole object. |
| `01 Model` | **Support Set** | topology, points or node IDs, mode, snap tolerance | `Supports` | Bind form-finding supports to the registered topology without defining FEA restraint degrees of freedom. |
| `01 Model` | **Load Case** | topology, points or node IDs, vectors, distribution, name, factor, force unit, snap tolerance | `Load Case` | Assign one named load case to the topology without embedding solver assumptions. |
| `01 Model` | **Equilibrium Problem** | topology, support set, load-case list, name | `Problem` | Validate and bundle the shared solver input. |
| `02 Form Finding` | **FD Settings** | scalar or member-aligned force densities | `Settings` | Keep force-density values separate from loads and drawing controls. |
| `02 Form Finding` | **FD Solve** | problem, settings, load-case index | `Result` | Run whole-network COMPAS force-density form finding. |
| `02 Form Finding` | **TNA Pattern** | geometry, mode, resolution, weld tolerance | `Pattern`, source `Topology` | Register a mesh or already-split planar line pattern. Surface, grid, triangulation, and skeleton modes fail explicitly until their generators exist. |
| `02 Form Finding` | **TNA Supports** | pattern, explicit anchor points, optional snap tolerance | supported `Pattern` | Bind only the true structural anchors; intermediate boundary vertices remain free for relaxation. |
| `02 Form Finding` | **TNA Relax + Boundaries** | supported pattern, nominal plan force density, target boundary sag | `Prepared` | Run planar FDM relaxation, target support-to-support opening sag, and retain the conditioned form plus unbalanced topological force graph. |
| `02 Form Finding` | **TNA Equilibrium** | prepared state, optional load case, crown-height/signed-q mode and value | `TnaResult` | Run horizontal and vertical TNA with compact controls and preserve the complete solved reciprocal state. |
| `02 Form Finding` | **TNA Control** | height mode/value, horizontal alpha, horizontal/vertical iterations, tolerance | `Control` | Bundle crown-height or force-scale control and numerical TNA settings. |
| `02 Form Finding` | **TNA Solve** | problem, control, load-case selector | `Result` (`TnaResult`) | Retained one-shot faced-pattern compatibility solve. |
| `03 Graphic Statics` | **TNA Reciprocal** | TNA result, layout, metric, force scale, vector scale, gap ratio | `Diagram` (`GraphicDiagram`) | Construct and preview the linked thrust/form/force diagram without rerunning the solver. |
| `03 Graphic Statics` | **Graphic Diagram Display** | graphic diagram, style, role visibility, weight scale | form/thrust/force/load/reaction lines, report | Provide the explicit styled viewport boundary and expose ordinary Rhino lines for downstream drawing operations. |
| `05 Visualisation` | **Equilibrium Preview** | equilibrium result, force weight, vector scale | member colours/lines and load, reaction, residual lines | Preview the current FD equilibrium result in the Rhino viewport. |
| `90 Query` | **TNA Geometry** | TNA result | thrust mesh, thrust edges, form edges, equilibrium bridge | Reconstruct the resolved Rhino thrust mesh and provide a compatibility bridge to generic equilibrium consumers. |
| `90 Query` | **TNA Members** | TNA result | member IDs, thrust lines, `q`, `H`, `F`, state, source-edge tree | Extract only the aligned member demand/provenance table needed for force-flow and later branch-design operations. |
| `90 Query` | **TNA Actions** | TNA result, vector scale | supports, load points/vectors, reaction points/vectors | Extract paired nodal actions and provide a focused arrow preview. |
| `90 Query` | **Result Breakdown** | generic equilibrium result | aligned member geometry/forces/densities, vectors, source IDs, supports, diagnostics, report | Preserve the legacy full FD-oriented deconstruction surface. It does not directly accept a `TnaResult`. |
| `90 Query` | **Backend Health** | none | ready, Python, packages, capabilities, report | Verify the persistent Python worker, package environment, and protocol. |

### Port rules

- Components accept a primary typed bundle rather than parallel lists whose
  indices can silently drift.
- A solver returns one `SolvedCase`; downstream visualisation or export reads
  that same result rather than rerunning the solver.
- Rich TNA state is queried by responsibility. Geometry, member demand, and
  nodal actions are separate components instead of one oversized bank of
  unrelated parallel outputs.
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
| `02 Form Finding` | Form Finding | `compas_fd`, `compas_tna` | `fd.solve`, `tna.solve` | `equilibrium` | **Built** |
| `03 Graphic Statics` | Form Finding | `compas_ags` | `ags.solve` | `equilibrium` | **Built** |
| `04 Masonry` | Masonry | `compas_dem`, `compas_assembly`, `compas_cra` | `masonry` | `masonry` | Reserved |
| `05 Visualisation` | none | none | always | none | **Built** |
| `06 Engineering` | Engineering | `compas_fea2` plus a solver | `fea` | `fea` | Reserved |
| `07 Fabrication` | Digital Fabrication | `compas_fab`, `compas_robots` | `fab` | `fab` | Reserved |
| `08 Delivery` | Data Modelling | `compas_model`, `compas_ifc` | `model`, `ifc` | `model`, `ifc` | Packages installed, components pending |
| `90 Query` | none | none | always | none | **Built** |

`04 Masonry` fills the gap deliberately left between `03` and `05`, so no
existing subcategory string changes. Subcategory is display grouping only and
component identity is the GUID, so regrouping never invalidates a saved
definition; the versioning policy's breaking-change rules govern ports and
semantics, not tabs.

### Why TNA is not its own tab

TNA is a method inside Form Finding, which is how COMPAS itself classifies it
alongside `compas_fd`, `compas_dr` and `compas_ags`. Giving it a tab would
break the alignment above and would separate it from the shared registration
spine it depends on. `02 Form Finding` is the fullest tab at eight components,
and if it becomes crowded the answer is a naming prefix (`TNA ...`, `FD ...`,
which the components already use) rather than a new tab that implies a new
backend.

### The Patterns family already has a home

COMPAS lists Patterns (`compas_skeleton`, `compas_singular`) as its own family,
but in this plugin it is not a tab. It is the missing backend for modes that
already exist and already fail honestly: `TNA Pattern` offers `Surface`,
`Grid`, `Triangulation` and `Skeleton`, and rejects all four with an actionable
error because no generator exists. `compas_skeleton` 2.0.1 is COMPAS 2
compatible and is the natural implementation of the `Skeleton` mode.
`compas_singular` is conda-only and would back quad-mesh singularity
patterning. Adopting them fills in existing modes rather than adding a tab.

### What each reserved tab would hold

Sketched to the same rule the built tabs follow: a stage returns one typed
bundle, and downstream components read that bundle rather than recomputing.

**`04 Masonry`.** `Block Tessellation` turning a `TnaResult` into intrados and
extrados block geometry with interface frames; `Assembly` binding those blocks
into a contact graph; `Stability` running the coupled rigid-block solve for a
chosen build stage; `Formwork Reaction` extracting the load history the
falsework carries across the whole sequence. The last of these is the one that
does not exist anywhere else in the pipeline, because a thrust network
describes only the completed vault.

**`06 Engineering`.** `Structural Model` and `FEA Solve`, consuming the
existing `StructuralAnalysisCase`. The current `StructuralHandoff` already
reports exactly which material, section, restraint and load-combination inputs
are still missing, so this tab has a specified entry contract already.

**`07 Fabrication`.** `Robot` loading a `compas_robots` model, `Place Sequence`
ordering block placement from the assembly, and `Inverse Kinematics` returning
joint configurations per target frame. Analytical IK needs no backend beyond
`compas_fab` itself, so this tab can be useful before any ROS decision is made.

**`08 Delivery`.** `Compas Model` and `IFC Export`, wrapping formulations that
`structural.py` already builds and deliberately does not auto-save.

### Sequence across tabs

Left to right on the ribbon is close to the real workflow, which is the second
reason for the numbering:

```text
01 Model -> 02 Form Finding -> 04 Masonry -> 07 Fabrication
                |                  |              |
                +-> 03 Graphic Statics            |
                +-> 06 Engineering                |
                +-> 08 Delivery <-----------------+

05 Visualisation and 90 Query read any stage without advancing it.
```

## Roadmap components

These are separate stages, not extra modes hidden inside the initial solvers.
The compact RhinoVault-style authoring surface is now implemented as
`TNA Pattern -> TNA Supports -> TNA Relax + Boundaries -> TNA Equilibrium`;
`TNA Solve` remains the one-shot compatibility macro. See
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

`Network` registers all supplied geometry in one pass:

1. Extract nodes and candidate edges from lines, polylines, or mesh topology.
2. Weld coincident endpoints using the supplied tolerance.
3. Retain a mapping from every source item to registered node and edge IDs.
4. Identify connected components, boundaries, supports, faces where available,
   non-manifold conditions, duplicates, and zero-length members.
5. Return one `TopologyBundle`, even when diagnostics reveal several connected
   components.

This is what lets TNA or FD act on the object as a network instead of solving
each input line independently. TNA additionally needs an admissible pattern
with the topology, faces, boundary conditions, loads, and height/force controls
required by its solver; an arbitrary collection of curves is not automatically
a funicular form.

`Network` exposes `mm`, `cm`, `m`, `in`, and `ft` as canonical coordinate
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
stages therefore own any new reciprocal construction; display components only
draw structured solver or construction results.

For staged TNA, `TNA Relax + Boundaries` already serialises the initial
topological force graph beside its form graph in `TnaPrepared`; that graph is
not yet horizontally balanced. `TNA Equilibrium` returns the solved
reciprocal force diagram as part of `TnaResult`. A native `TNA Reciprocal`
component packages and previews that final state without rerunning AGS.
`Graphic Diagram Display` is the explicit presentation/deconstruction
boundary: it applies a visual preset and exposes the five diagram roles as
ordinary Rhino lines. A classical dashed load-line/pole construction is
extracted separately from an ordered directional path.

Before vertical calibration fixes the physical scale, horizontal-equilibrium
`q` and `H` are relative quantities; the final spatial `F` follows the lifted
thrust geometry. In a final `TnaResult`, `q`, `H`, and `F` are equilibrium
demands in the selected scale, not material capacity or utilisation. See
[`architecture/tna-graphic-statics-columns.md`](architecture/tna-graphic-statics-columns.md).

## Focused result queries

Use the smallest component that matches the downstream operation:

```text
TNA Equilibrium.TNA Result
    +--> TNA Geometry --> Thrust Mesh / Thrust Edges / Form Edges
    +--> TNA Members  --> IDs / Lines / q / H / F / State / Source IDs
    +--> TNA Actions  --> Supports / Loads / Reactions
    +--> TNA Reciprocal --> Graphic Diagram Display
```

`Result Breakdown` is intentionally retained for legacy definitions built
around the generic `EquilibriumResult`, particularly FD workflows. A
`TnaResult` is a richer and different Grasshopper type, so connecting it
directly is a type error. Where an old downstream definition cannot yet be
migrated, `TNA Geometry.Equilibrium` exposes the embedded generic result as a
compatibility bridge:

```text
TNA Equilibrium.TNA Result
    --> TNA Geometry.Equilibrium
    --> Result Breakdown.Result
```

New TNA definitions should not use that bridge as their normal data model;
they should preserve `TnaResult` and query only the geometry, member, action,
or diagram information actually needed.

## Naming policy

Use functional names in the public plugin. Historical project names may remain
only in a compatibility namespace and migration notes. In particular, new
components and contracts use `ananke_equilibrium`, not an old implementation
name.
