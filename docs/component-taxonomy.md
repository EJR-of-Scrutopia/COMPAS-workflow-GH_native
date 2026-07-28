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
| Results | `SolvedCase` | Immutable solved geometry, edge forces, reactions, residuals, provenance, units, and solver diagnostics. |
| Display | `DiagramStyle`, `DiagramBundle` | Display policy and Rhino-ready preview payloads kept separate from solver data. |
| Design extensions | `BranchDesign` | Later response-field, branch-layout, and Steiner-junction decisions. |
| Delivery extensions | `StructuralDefinition`, `FEAResult`, `IFCPackage` | Later structural modelling, analysis, and IFC hand-off contracts. |

The precise Python definitions are the source of truth. The table above
describes their responsibilities, not an invitation to duplicate them inside
Rhino-specific code.

## v0.1 component surface

The first working slice has ten components. Their machine-readable contract
is in `plugin/components.toml`.

| Component | Inputs | Outputs | Responsibility |
| --- | --- | --- | --- |
| **Network** | geometry, kind, plane, tolerance, unit | `TopologyBundle`, status | Weld endpoints, register line/polyline or faced-mesh connectivity, preserve source IDs, and diagnose the whole object. |
| **Support Set** | topology, points or node IDs, selection mode | `SupportSet`, status | Bind form-finding supports to the registered topology without defining FEA restraint degrees of freedom. |
| **Load Case** | topology, points or node IDs, vectors, distribution, case name | `LoadCase`, status | Assign named loads to the registered topology without embedding solver assumptions. |
| **FD Settings** | scalar or member-aligned force densities | `FDConfig`, status | Keep force-density values together and separate from loads or drawing controls. |
| **TNA Control** | height mode/value, horizontal alpha, iterations, tolerance | `HeightControl`, `TNAConfig`, status | Keep crown-height/force-scale control and advanced solver options together. |
| **FD Solve** | topology, supports, load case, `FDConfig` | `SolvedCase`, status | Force-density form finding for compatible networks. |
| **TNA Solve** | faced topology, supports, load case, `HeightControl`, `TNAConfig` | `SolvedCase`, status | Thrust-network form finding for a compatible whole-object pattern. |
| **Validate** | solved case, tolerances | diagnostics, status | Check topology, residual equilibrium, reactions, closure, and numerical warnings. |
| **Diagram Style** | preset, scales, label controls | `DiagramStyle`, status | Set scales, colours, labels, and line weights without changing analysis. |
| **Preview Payload** | solved case, style, kind, dimension | `DiagramBundle`, status | Produce renderer-neutral form/member primitives for the first Rhino preview implementation. |

### Port rules

- Components accept a primary typed bundle rather than parallel lists whose
  indices can silently drift.
- A solver returns one `SolvedCase`; downstream visualisation or export reads
  that same result rather than rerunning the solver.
- Status is concise and human-readable. Structured warnings and numerical
  diagnostics remain on the bundle.
- Rhino geometry conversion happens in the Grasshopper adapter layer.
  Contracts and solvers must not import RhinoCommon.
- Grasshopper data trees are flattened or mapped explicitly at the adapter
  boundary; no data-tree object enters the numerical core.
- Units and sign conventions are explicit in contracts and reports.

## Roadmap components

These are separate stages, not extra modes hidden inside the initial solvers.

| Stage | Planned component | Main result |
| --- | --- | --- |
| Environmental/design input | **Response Field** | Weighted attractor, clearance, canopy, obstacle, or performance fields. |
| Topology generation | **Branch Layout** | Candidate trunk/branch graph derived from a field and target points. |
| Junction optimisation | **Steiner** | Branching topology and junction positions satisfying the chosen 120-degree policy where the Euclidean Steiner assumptions apply. |
| Reciprocal equilibrium | **AGS Solve** | Force and form diagrams with explicit reciprocal correspondence using `compas_ags`. |
| Drawing | **Graphic Statics** | Ordered load lines, force polygons/cells, reciprocal member lines, labels, scales, and closure errors. |
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
one decorative triangle. `AGS Solve` and `Graphic Statics` therefore own the
reciprocal topology; `Preview Payload` only draws the structured result.

## Naming policy

Use functional names in the public plugin. Historical project names may remain
only in a compatibility namespace and migration notes. In particular, new
components and contracts use `ananke_equilibrium`, not an old implementation
name.
