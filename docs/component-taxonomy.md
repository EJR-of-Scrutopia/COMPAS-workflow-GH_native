# Grasshopper component taxonomy

The plugin boundary is deliberately smaller than the Python API. Grasshopper
components exchange typed bundles, while ordinary Grasshopper operations can
still be inserted between stages to edit geometry, select branches, or drive
parameters.

## Contract families

| Family | Contract | Purpose |
| --- | --- | --- |
| Registration | `TopologyBundle` | One registered object: nodes, edges, optional faces, source mapping, groups, tolerances, and topology diagnostics. |
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

The compiled native slice has sixteen components. The C# classes under
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
| `02 Form Finding` | **TNA Control** | height mode/value, horizontal alpha, horizontal/vertical iterations, tolerance | `Control` | Bundle crown-height or force-scale control and numerical TNA settings. |
| `02 Form Finding` | **TNA Solve** | problem, control, load-case selector | `Result` (`TnaResult`) | Solve a faced thrust network and preserve the spatial thrust, planar form, reciprocal force, source mapping, loads, reactions, and diagnostics as one state. |
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

## Roadmap components

These are separate stages, not extra modes hidden inside the initial solvers.
The current `TNA Solve` remains the implemented one-shot macro. A future
RhinoVault-style surface will expose `TNA Register`, `TNA Relax`, `TNA Form`,
`TNA Dual`, `TNA Horizontal`, `TNA Vertical`, and `TNA Reciprocal` as
inspectable stages. See
[`architecture/rhinovault-native-stages.md`](architecture/rhinovault-native-stages.md)
for the current-versus-roadmap boundary and proposed contracts.

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

For TNA, the reciprocal force diagram is already produced during horizontal
equilibrium. The worker must serialise it as part of `TnaResult`; a native
`TNA Reciprocal` component packages and previews that state without rerunning
AGS. `Graphic Diagram Display` is the explicit presentation/deconstruction
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
TNA Solve.Result
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
TNA Solve.Result --> TNA Geometry.Equilibrium --> Result Breakdown.Result
```

New TNA definitions should not use that bridge as their normal data model;
they should preserve `TnaResult` and query only the geometry, member, action,
or diagram information actually needed.

## Naming policy

Use functional names in the public plugin. Historical project names may remain
only in a compatibility namespace and migration notes. In particular, new
components and contracts use `ananke_equilibrium`, not an old implementation
name.
