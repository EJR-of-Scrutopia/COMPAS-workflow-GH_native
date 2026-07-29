# TNA, graphic statics, and column-placement architecture

Status: current native TNA/graphic-display contract plus later design
architecture. Current and planned components are identified explicitly below.
The staged RhinoVault-style authoring roadmap is defined separately in
[`rhinovault-native-stages.md`](rhinovault-native-stages.md).

## One solved state, three linked diagrams

A native TNA solve returns one immutable `TnaResult`. It contains three
different but linked representations:

1. The **form diagram** is the planar force-flow pattern.
2. The **force diagram** is its reciprocal dual for horizontal equilibrium.
3. The **thrust network** is the spatial funicular result after vertical
   equilibrium.

Every active member retains this stable correspondence:

```text
source edge -> form edge <-> force edge -> thrust edge
```

The correspondence is solver data, not a relationship that a display
component may reconstruct from proximity or line direction. The Python worker
therefore serialises the COMPAS form/force pair when TNA is solved. A native
`TNA Reciprocal` component can display it immediately without rerunning AGS
and without deconstructing a large generic result.

For member \(i\):

```text
q_i = F_i / L_thrust,i
    = H_i / L_form,i
    = s L_force,i / L_form,i
```

Here `q` is force density, `H` is horizontal force demand, `F` is full spatial
axial-force demand, and `s` converts reciprocal force-edge length to physical
horizontal force. Display force scale is separate from this physical scale.

TNA and graphic statics provide equilibrium **demand**, not material
capacity. Capacity and utilisation additionally require material, section or
shell thickness, stability/buckling, connections, safety factors, and a
verification model.

## Component surface

The implemented compact native workflow is:

```text
Problem + TNA Control -> TNA Solve -> TnaResult
                                           +-> direct thrust-edge preview
                                           +-> TNA Geometry
                                           +-> TNA Members
                                           +-> TNA Actions
                                           +-> TNA Reciprocal
                                                   |
                                                   +-> Graphic Diagram Display
```

`Force Flow`, `GS Direction Register`, `GS Funicular 2D`, and spatial
graphic-statics components described later in this document are planned, not
part of the implemented v0.2 component surface.

### TNA Control

The control bundle owns the physical solve choices:

- vertical mode: target crown height or horizontal-force scale;
- target value;
- horizontal balancing alpha;
- horizontal and vertical iteration limits;
- solve tolerance.

It does not own diagram origin, viewport line weight, colour, label policy, or
display scale.

### TNA Reciprocal

This is the implemented constructor for the default graphic-statics view of a
TNA result. It packages:

- planar form edges;
- reciprocal force edges and force cells;
- spatial thrust edges;
- form-edge/force-edge correspondence;
- `q`, `H`, `F`, force state, and reciprocity error;
- loads, support reactions, and equilibrium diagnostics.

The component returns one typed, renderer-neutral diagram bundle and also
supports a direct compact preview. `Graphic Diagram Display` is the explicit
presentation boundary: it applies the visual preset and exposes ordinary
Rhino form, thrust, force, load, and reaction lines.

Raw solved data is split by responsibility instead of sent through one large
deconstructor:

- `TNA Geometry`: resolved thrust mesh, thrust/form edges, generic equilibrium
  compatibility bridge;
- `TNA Members`: aligned member IDs, lines, `q`, `H`, `F`, state, and source
  groups;
- `TNA Actions`: supports, applied loads, and reactions.

The legacy `Result Breakdown` accepts only the generic `EquilibriumResult`.
It is not the TNA data model. `TNA Geometry.Equilibrium` may bridge an old
definition, but new TNA workflows should retain `TnaResult`.

At horizontal equilibrium, before the vertical solve calibrates the physical
scale, `q` and `H` are relative equilibrium quantities. The lifted thrust
network then supplies the spatial axial demand `F`. The final result preserves
all three in its selected scale; none is capacity.

### Force Flow (planned)

This component weights and colours the TNA network by one deterministic value:

- `Axial Force F`;
- `Horizontal Force H`;
- `Force Density q`;
- `Load Path |F| L`.

These are discrete network force paths, not continuum principal-stress
trajectories. At a high-valence node there is no unique continuation into a
"principal line"; a traced path must record its continuation rule.

### Directional two-dimensional graphic statics (planned)

The familiar dashed load line, pole rays, and funicular polygon are a special
directional construction. A general TNA mesh has a reciprocal force mesh and
must not be forced into one enclosing triangle.

Directional extraction therefore requires a section frame with an origin,
along axis, and load axis, plus either an explicit ordered edge path or a
seed-and-trace rule.

`GS Direction Register` converts that choice into stable ordered paths. For a
quad pattern it may register the two topological edge families independently.
For an irregular pattern it uses an explicit continuation rule such as minimum
turning angle, maximum transmitted force, or proximity to a guide curve.
The selected rule and every source edge ID remain on the result; the component
does not imply that a high-valence network has a unique principal path.

For a selected path, transverse members are included as effective nodal loads:

```text
p_eff,i = Project(p_i + sum(forces from members not on the path))
```

Omitting those transfers destroys the path's local equilibrium. The result
stores projected residual, force-polygon closure, out-of-plane force ratio,
collapsed or crossing projected edges, and whether a common pole exists.

Moving an arbitrary pole creates a new equilibrium design and belongs in a
later `GS Design 2D` component. `GS Funicular 2D` initially recovers the pole
of the solved state.

The dashed line shown in a classical force diagram is the ordered load line in
force space. It is not automatically the centreline or inflection line of the
surface. A geometric centre/inflection/asymptotic line can be used as the guide
for path registration, but it remains a separate geometric datum.

## Direction fields are not interchangeable

Later surface components keep these quantities separate:

- principal curvature directions: geometry only;
- asymptotic directions: geometry only, where normal curvature is zero;
- principal membrane-force directions: shell FEA result;
- discrete TNA force-flow directions: an approximation on the network edges.

An anticlastic or hypar direction view may display more than one of these, but
the legend and contract always identify which field is being shown.

## Column-head placement

Columns are not long reaction-vector previews. Column placement is an explicit
design and optimisation layer between TNA solves.

```text
initial TnaResult
    -> TNA Candidate Field
    -> Select Column Heads
    -> Augment TNA Supports
    -> TNA Solve again
    -> Column Actions
    -> Group Tips
    -> Branch Topology
    -> Branch Equilibrium
```

An already equilibrated free node has approximately zero residual. Its
residual cannot be used as a "column need" score, and the current result has no
reaction at a support that does not yet exist.

Candidate-field modes are explicit:

- user or architectural guide regions;
- deviation from a reference surface/form;
- tributary force or load-path concentration;
- force-density shape proxy, clearly labelled as non-stiffness;
- counterfactual trial TNA solves;
- later FEA displacement/compliance after material and section assignment.

Adding, removing, moving, or changing the elevation of a column head changes
the support conditions and requires a new TNA solve. Reactions at the newly
added supports from that solve are the exact actions passed to the branch or
column design. If a flexible column changes the head position, a later coupled
outer iteration must alternate canopy and column solves to convergence.

## Branch junctions and 120-degree geometry

The branch solver exposes two different modes rather than blending them:

- `Geometric 120`: equal-weight Euclidean Steiner length optimisation;
- `Force Weighted`: joint equilibrium using the solved branch force
  magnitudes.

For three forces \(w_1, w_2, w_3\), equilibrium requires:

```text
w_1 u_1 + w_2 u_2 + w_3 u_3 = 0
```

and the angle opposite force \(w_k\) follows:

```text
cos(theta_ij) = (w_k^2 - w_i^2 - w_j^2) / (2 w_i w_j)
```

All three angles are 120 degrees only when the magnitudes are equal. If the
strict triangle inequality fails, the weighted junction degenerates and the
component reports it instead of drawing a false Steiner point. Accumulated
vertical load is not automatically an axial branch-force magnitude.

## Verification and delivery

After the support/branch configuration is selected:

```text
TnaResult + column/branch topology
    -> COMPAS Model
    -> FEA / TNO verification
    -> capacity and utilisation
    -> COMPAS IFC
```

TNA remains the form-finding and equilibrium-design source. FEA adds stiffness,
displacement, bending, buckling, and section checks; IFC records the selected
physical members and analysis provenance.

## Primary references

- [COMPAS TNA overview](https://blockresearchgroup.github.io/compas_tna/latest/)
- [COMPAS TNA horizontal equilibrium and force-density relation](https://blockresearchgroup.github.io/compas_tna/latest/api/generated/compas_tna.equilibrium.horizontal_nodal.html)
- [RhinoVAULT equilibrium workflow](https://blockresearchgroup.gitbook.io/rhinovault/manual)
- [COMPAS AGS](https://blockresearchgroup.github.io/compas_ags/latest/)
- [Algebraic Graphic Statics](https://blockresearchgroup.github.io/compas_ags/latest/publications/ags.html)
- [Thrust Network Analysis, Block and Ochsendorf](https://www.block.arch.ethz.ch/brg/files/block_ochs_IASS_2007.pdf)
- [Load-path optimisation of funicular networks](https://block.arch.ethz.ch/brg/files/liew_pagonakis_van_mele_block_2017_-_load-path_optimisation_of_funicular_networks_1498721556.pdf)
