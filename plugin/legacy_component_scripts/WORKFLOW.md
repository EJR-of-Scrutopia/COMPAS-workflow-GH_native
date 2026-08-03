# COMPAS form-finding, graphic statics, analysis and IFC workflow

This folder is the COMPAS-facing layer for the existing `tree_forest` design
tools. The layers stay separate on purpose: a clustering or Steiner operation is
not silently treated as structural equilibrium, and an equilibrium result is not
silently treated as a verified building model.

```text
Rhino / Grasshopper geometry
          |
          v
1  Register one topology -------------------------------------------+
   mesh -> vertices + faces                                         |
   lines/polylines -> flattened segments -> welded graph -> faces   |
          |                                                         |
          +-------------------------+-------------------------------+
                                    |
                 +------------------+------------------+
                 |                                     |
                 v                                     v
2A  Faced compression pattern             2B  Tree / cable graph
    COMPAS TNA                                COMPAS FD
    form + force + thrust network             nodal equilibrium
                 |                                     |
                 +------------------+------------------+
                                    |
                                    v
3  Visualise and interrogate
   forces, force densities, loads, reactions, residuals, mappings
                                    |
                 +------------------+------------------+
                 |                                     |
                 v                                     v
4A  COMPAS AGS                            4B  Structural validation
    planar reciprocal studies                 COMPAS FEA2 / benchmark model
                 |                                     |
                 +------------------+------------------+
                                    |
                                    v
5  COMPAS Model -> COMPAS IFC
   physical members + materials + sections + relationships + provenance
```

## What can be a single TNA object?

A TNA input is the complete, connected **faced pattern**, not a collection of
independent member solves.

- A Rhino mesh already supplies vertices, edges and faces.
- A list of Lines or Polylines is flattened into straight segments, coincident
  endpoints are welded, and closed planar cycles are reconstructed as faces.
- Every real crossing must be split before registration.
- The pattern must be planar in its analysis plane and must contain closed faces.
- A tree has no cycles or faces. It is therefore not a TNA pattern; use COMPAS FD
  for that graph, and use AGS on intentional planar projections or joint slices.

The returned session preserves source-to-COMPAS node and edge mappings. A source
edge mapped to `None` was removed by TNA boundary conditioning and is not a
solved member. Pass the session itself to downstream components. Do not bake and
re-read lines between the solve and visualisation stages.

TNA computes a thrust network from a chosen pattern, supports, loads and force
constraints. The input pattern is not already “funicular”; it is the horizontal
topology and starting geometry from which equilibrium is sought. A converged
solution with acceptably small residuals is the funicular result for those
assumptions.

TNA does not infer the best structural segmentation from an arbitrary surface.
The pattern encodes the possible force paths, so topology remains a design
decision. Start with edges that express the intended spans, ribs, openings and
support paths; split every real joint; then use signed force, reciprocal-edge
length, force-density and residual plots to decide where the pattern needs
redirection or refinement. Subdividing a line only for visual smoothness adds
nodes and variables—it does not automatically improve the force flow.

In the installed `compas_tna` 0.7.0 build, self-weight through the `density`
parameter does not preserve a reliable signed effective-load field. This adapter
therefore requires `Density=0` and expects self-weight to be converted to
explicit negative nodal `Pz` values. `Pz` is the Z component of
`AnalysisPlane`, not necessarily World Z; reported reactions use the same local
XYZ components and are rotated back to world coordinates for preview.

## Tree-column geometry and the 120-degree stage

`tree_forest` now calls its tributary quantity `CarriedVerticalLoad`. The old
`FBR` name was misleading because this value is neither solved axial force nor
force density.

Rename the existing Grasshopper output parameters as well as replacing the
script:

```text
FBR  -> CarriedVerticalLoad
CFBR -> CentralCarriedVerticalLoad
```

The Python data object retains a read-only `branch_load` compatibility alias for
old saved definitions, but all live components use the new name.

Use `gh_steiner_relax.py` before load equilibrium when a fixed degree-three tree
topology should approach true Steiner geometry:

1. Connect the complete branch network to `Branches`.
2. Connect fixed tips and feet to `FixedPoints`, or leave it empty to fix all
   degree-one terminals.
3. Use `Plan=True` for plan optimisation, or `False` for full 3D.
4. Check `MaxAngleDeviation` and the per-junction `JunctionAngles`.

This stage minimises total length with equal branch tension. A non-degenerate
free degree-three optimum has 120-degree angles. Applying unequal strengths
(including `CarriedVerticalLoad`) produces a weighted Fermat problem and, in
general, does **not** produce three 120-degree angles. After topology/geometry
design, solve loads with FD/TNA and use the actual solved axial force for
visualisation and sizing.

## Grasshopper components

Create Rhino 8 Python 3 components and paste the corresponding scripts.

Keep the interpreter/environment header at the very top of every pasted
`gh_*.py` script. Rhino Code resolves named virtual environments per Python
component; running the one-off package installer does not automatically select
that environment for every other Grasshopper component. All COMPAS adapters in
this folder therefore select the same pinned `catenary-compas-2026` environment.

### `SteinerRelax`

Script: `../tree_forest/gh_steiner_relax.py`

Inputs:

`Branches, FixedPoints, Plan, WeldTol, SnapTol, MaxIter, Tol, Run`

Outputs:

`RelaxedLines, RelaxedPoints, JunctionIDs, JunctionAngles,
MaxAngleDeviation, LengthHistory, Report`

### `AGSGraphicStatics`

Script: `gh_ags.py`

Inputs:

`Geometry, DiagramPlane, ReferenceEdge, ReferenceForce, ForceOrigin,
ForceScale, Run`

Outputs:

`Session, FormLines, ForceLines, SourceForces, ForceMagnitudes,
ReciprocityErrors, SourceToFormEdge, Report`

The expanded interface also accepts:

```text
IndependentEdges, IndependentForces, LoadEdges, ReactionEdges
```

and emits:

```text
ForceInternalLines, ForceExternalLines, ForceLoadLines, ForceReactionLines,
ForceVertices, ForceFaces, ForceRoles, SourceRoles, SourceToForceEdge,
Nullity, Mechanisms
```

Leave `IndependentEdges` empty to retain the single `ReferenceEdge` workflow.
For a form with nullity greater than one, provide exactly `Nullity` source-edge
indices and signed force values. A nonzero `Mechanisms` result is rejected
because the form topology is unstable.

The input must include the complete planar system, including the appropriate
external load and reaction edges. `ReferenceEdge` refers to the flattened source
segment order. `LoadEdges` and `ReactionEdges` use that same flattened order and
only classify external leaf edges for visualisation and downstream mapping. The
force polygon may sit to one side by design; `ForceOrigin` and `ForceScale`
control display placement only.

### `FDWholeNetwork` and `FDVisualize`

Scripts: `gh_fd_solve.py` and `gh_fd_visualize.py`.

`FDWholeNetwork` flattens Lines/Polylines, welds their endpoints, and solves the
registered graph once. Supply support points, load points/vectors and force
densities. Its `Session` output is the object passed downstream.
Crossing curves are only connected when the intended joint exists as matching
segment endpoints; split physical intersections upstream.

With `Supports` empty, every degree-one endpoint is fixed, which is convenient
for a two-ended catenary. For a tree column, wire the actual feet explicitly so
loaded tips are not accidentally fixed.

Use `LoadNodeIDs` instead of `LoadPoints` when a slider should move point load
`Q` between registered stations. Duplicate node IDs are intentional and their
vectors are accumulated, so a distributed base load plus a larger moving load
can target the same node. Supply either points or IDs in one solve, not both.

`FDVisualize` consumes the session and emits equilibrium members, signed member
forces, force densities, loads, reactions, residuals and local joint force
polygons. A loaded degree-two catenary node has two member-force vectors and one
load vector, so its closed local force polygon is necessarily a triangle. The
polygons are laid out to one side for readability; `DiagramOrigin`,
`LayoutVector`, `DiagramSpacing` and `ForceScale` are display controls.

```text
FDWholeNetwork
  in:  Geometry, Supports, LoadPoints, LoadNodeIDs, LoadVectors, ForceDensity,
       WeldTol, SnapTol, Run
  out: Problem, Session, RegisteredPoints, EquilibriumLines, MemberForces,
       ForceDensities, SupportPoints, AppliedLoadNodeIDs, ResidualMagnitudes,
       SourceEdges, Report

FDVisualize
  in:  Session, JointIDs, DiagramOrigin, LayoutVector, DiagramSpacing,
       ForceScale, VectorScale, Run
  out: FormLines, MemberForces, ForceDensities, ForceNormalised, ForceColours,
       LoadPoints, LoadVectors, ReactionPoints, ReactionVectors,
       ForceMemberLines, ForceLoadLines, ForceReactionLines,
       ClosureErrors, Report
```

### `FDGlobalGraphicStatics`

Script: `gh_fd_global_graphic_statics.py`.

This is the missing operation between an FD equilibrium solve and the classical
drawings in the reference examples. It does not reset at every joint. Instead,
it cyclically orders each nodal force cell and glues the two equal/opposite
copies of every shared member side.

```text
FDGlobalGraphicStatics
  in:  Session, DiagramPlane, StartNode, QNodeID, ForceOrigin, ForceScale,
       Tolerance, Clockwise, Run
  out: GraphicSession, FormLines, ForceMemberLines, ForceLoadLines,
       ForceLoadStartPoints, ForceLoadVectors, ForceReactionLines,
       ForceReactionStartPoints, ForceReactionVectors, ForceCells,
       BoundaryLines, BoundaryKinds,
       OuterEnvelope, Pole, LoadLinePoints, LoadLineSegments, QSegment,
       ChainNodeIDs, ChainEdgeIDs, MemberIDs, LoadNodeIDs, ReactionNodeIDs,
       ClosureErrors, StitchError, PlanarityErrors, ForceDimension,
       FitsOuterEnvelope, DiagramPlaneOut, Report
```

For a connected serial cable or arch, the result is one common force pole, one
cumulative load line, and one member ray per source edge. Under parallel loads,
the exact external-force boundary simplifies to the familiar triangle: left
reaction, total load, right reaction. `OuterEnvelope` is detected from this
boundary; no triangle is fitted around unrelated local polygons.

`QNodeID` only identifies the segment to highlight. To move or scale point load
`Q`, select a different registered load point or change its load vector upstream
of `FDWholeNetwork`, then let FD solve again. Uppercase `Q` is an applied point
load. Lowercase COMPAS `q` is force density; changing `q` changes the funicular
form and pole distance. `ForceScale` changes drawing size only.

For a connected planar acyclic tree, the component instead emits one stitched
network of shared force cells. It does not force that network into a triangle.
The component rejects cyclic networks with a routing message to
`AGSGraphicStatics`, and rejects spatial networks that do not lie in the chosen
plane. Disconnected trees are separate equilibrium systems and therefore need
separate reciprocal diagrams.

A bare binary tree with one root reaction and parallel vertical loads at its
degree-one tips has a degenerate pin-jointed axial solution: the terminal
members must align with their loads and the reciprocal collapses toward a line.
The eQUILIBRIUM tree reference avoids this by including a crown/top chord. To
reproduce that drawing, explicitly supply:

```text
branches + crown/canopy chord + load stubs + reaction stub
    -> AGSGraphicStatics
```

Do not invent the canopy silently. If the physical branches are intended to
carry bending rather than axial force only, route them to the frame/beam FEA
model; a pin-jointed reciprocal is then not the complete structural model.

### TNA whole-pattern registration, solve and visualisation

Scripts: `gh_tna_register.py`, `gh_tna_solve.py` and
`gh_tna_visualize.py`.

`TNARegister` accepts either one or more meshes, or a list of lines/polylines,
and registers the flattened input as one `TNAProblem`. `TNASolve` adds supports,
loads and vertical-control parameters without rebuilding the topology and emits
one `TNASession` with stable source mappings. `TNAVisualize` consumes that same
session and emits:

For a mesh workflow, connect the Rhino mesh itself to `TNARegister.Geometry`.
Do not pass it through `Mesh Edges`: the mesh faces are the information that
allows TNA to construct the dual reciprocal. The input supplies the topology
and horizontal form pattern; `TNASolve` recomputes the free-node elevations.
The resulting `ThrustLines` are outputs, not inputs.

- planar form edges;
- the three-dimensional thrust network;
- a translated force diagram;
- aligned member forces and force densities;
- compression/tension colours;
- load and support-reaction vectors;
- source-to-form mappings and a diagnostic report.

If linework has no closed faces, the register component rejects it with a routing
message to COMPAS FD instead of pretending that each line is a TNA object.

Grasshopper parameter names:

```text
TNARegister
  in:  Geometry, AnalysisPlane, WeldTol, Precision, Run
  out: Problem, PatternLines, RegisteredPoints, FacePolylines,
       SourceVertexKeys, SourceEdges, SourceToForm, SourceEdgeToForm, Report

TNASolve
  in:  Problem, SupportPoints, LoadPoints, Pz, VerticalMode, ZMax, QScale,
       Density, HorizontalAlpha, HorizontalIter, VerticalIter,
       SolveTolerance, SnapTol, Run
  out: Session, ThrustLines, MemberForces, ForceDensities, SupportPointsOut,
       Reactions, SourceToForm, SourceEdgeToForm, Diagnostics, Report

TNAVisualize
  in:  Session, ForceOrigin, ForceScale, VectorScale, Run
  out: FormLines, ThrustLines, ForceLines, MemberForces, HorizontalForces,
       ForceDensities, ForceNormalised, ForceColours, LoadPoints, LoadVectors,
       ReactionPoints, ReactionVectors, ResidualPoints, ResidualVectors,
       FormEdges, ForceEdges, FormToForceMappings, SourceEdgeMappings,
       SourceToForceMappings, Report
```

Set `Geometry`, support and load point inputs to **List Access**. Right-click and
**Flatten the Geometry input** on TNA, FD, AGS and Steiner components; otherwise
Grasshopper can execute the component once per data-tree branch instead of once
for the whole object. `Pz` and `ForceDensity` are also List Access so a single
value can be broadcast while still allowing aligned per-node/per-edge data.
`SnapTol` is the maximum distance from a supplied support/load/fixed point to a
registered node; unmatched points raise an error instead of silently targeting
the nearest node.

### `StructuralHandoff`

Script: `gh_structural_handoff.py`.

This component consumes either a solved TNA or FD session. It creates both a
neutral `StructuralAnalysisCase` and its reduced `StructuralBundle`, can create
an explicitly sized in-memory `compas_model` preview, and always creates a
reviewable IFC formulation. An IFC model is only created when `BuildIFC=True`,
and no file is written automatically. Its FEA readiness output recognises the
case's labeled nodal loads, then lists the material, section, restraint and
load-combination data still needed for a real analysis.

```text
StructuralHandoff
  in:  Session, LengthUnit, ForceUnit, LoadCase, MemberRoles, Width, Depth,
       BuildModel, BuildIFC, IFCBodies, Run
  out: SourceSession, AnalysisCase, SourceMappings, Bundle, ModelHandoff,
       CompasModel, IFCFormulation, IFCModelHandoff, IFCModel, MemberLines,
       AxialForces, ForceStates, SupportPoints, FEAAvailable, FEAMissing,
       Report
```

### Bundle versus provenance case

`StructuralBundle` is the small active-topology contract: solved world
coordinates, active member connectivity, signed axial forces, supports and
units. It is convenient for geometry previews and IFC member formulation, but
it deliberately does not reconstruct how the result was produced. In
particular, TNA boundary conditioning can remove registered source vertices and
members before the active bundle is assembled.

`StructuralAnalysisCase` is the object to retain between analysis, structural
breakdown and export stages. It wraps the bundle and additionally preserves:

- every source vertex and source member mapping, including TNA members marked
  `removed` with no active bundle-member index, plus the exact source support
  IDs selected before welding;
- source IDs and force density aligned one-to-one with active bundle members;
- member roles, defaulting safely to `unspecified` unless supplied explicitly;
- requested source loads plus active loads, support reactions and free-node
  residuals as world-coordinate point/vector records;
- the load-case label, solver kind, immutable diagnostics and solver metadata.

The case remains neutral provenance. It is not a stiffness model, a material or
section assignment, a load combination, or proof of structural capacity.

## Graphic statics views and routing

There are four related but non-interchangeable views:

1. **FD local cells:** independent nodal closure diagnostics from
   `FDVisualize`.
2. **FD stitched reciprocal:** one global diagram for a connected planar
   acyclic FD graph from `FDGlobalGraphicStatics`; a serial chain specialises
   to the pole/load-line fan.
3. **AGS reciprocal:** the mesh dual of a complete planar form graph, including
   cyclic canopy/truss topology and explicit external-force leaf edges.
4. **TNA reciprocal:** the global horizontal force diagram dual to a faced
   compression pattern.

A spatial tree does not have one directly drawable two-dimensional reciprocal
without choosing a real plane, slice, or projection whose equilibrium remains
in that plane. Never discard out-of-plane force components merely to make a
clean diagram. Use 3D FD vectors/local cells for diagnosis, planar AGS studies
for intentional slices, and structural FEA for the complete spatial system.

## Structural model, FEA and IFC boundary

TNA and FD are equilibrium/form-finding methods; they do not check section
capacity, buckling, material nonlinearity, connection stiffness or code
compliance.

The downstream handoff therefore carries:

- stable node/member identifiers and source mappings;
- solved geometry, signed axial force and force density;
- loads, supports, reactions and residual diagnostics;
- member role (`net`, `vault`, `column`, `branch`, and so on);
- units, load-case name and analysis provenance.

`compas_model` owns the physical element/material/section representation.
`compas_fea2` (in a compatible dedicated environment) owns verification and
result fields. `compas_ifc` exports selected physical objects and relationships;
it does not make an unverified form-finding result structurally verified.

Keep the Rhino COMPAS environment stable while building the geometry and TNA/AGS
stages. The current Rhino environment does not contain `compas_fea2`, so the FEA
adapter reports that boundary clearly rather than falling back to invented
results.

The official FEA2 guidance recommends a dedicated Conda environment and at least
one supported solver backend. Do not install it into the working Rhino
environment until the solver/backend choice is fixed:

```powershell
conda create -n tree-forest-fea compas
conda activate tree-forest-fea
pip install compas_fea2
python -m compas_fea2.test
```

Before implementing that adapter, define the material, section family, whether
each member is a cable/truss/beam, connection releases, support restraint DOFs,
load cases/combinations, second-order/buckling requirements and the unit system.
The `StructuralHandoff` component reports these missing inputs.

To write a reviewed in-memory IFC model explicitly from Python:

```python
IFCModelHandoff.model.save(r"C:\path\reviewed_tree_forest.ifc")
```

Saving is intentionally not triggered by the Grasshopper component.

## Acceptance checks

Do not promote a candidate to the model/IFC stage until:

- all intended source vertices and edges have a recorded mapping or an explicit
  reason for removal during boundary conditioning;
- supports and loads are visible at the intended nodes;
- TNA/FD equilibrium residuals are below the project tolerance;
- force signs and units are stated;
- the force/form reciprocity error is acceptably small;
- degree-three 120-degree claims come from the Steiner angle output, not from
  tributary load values;
- an independent structural model has checked members that can buckle or bend.
