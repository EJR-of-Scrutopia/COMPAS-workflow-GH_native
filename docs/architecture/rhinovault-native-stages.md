# RhinoVault-style native TNA stages

Status: architecture roadmap. The one-shot `TNA Solve`, its final
`TnaResult`, focused query components, and graphic-diagram display are
implemented. The separate Register, Relax, Form, Dual, Horizontal, and
Vertical authoring components described below are not yet implemented.

## Why expose the stages

The current native solver deliberately proves the complete numerical path in
one component:

```text
Faced Equilibrium Problem + TNA Control
    -> TNA Solve
    -> final TnaResult
```

This is useful as a dependable macro, but design by graphic statics requires
access to the states between registration and the final thrust network.
Pattern relaxation, support and plan constraints, reciprocal geometry, force
scale, and target height are different design decisions. They should be
editable in ordinary Grasshopper workflows without unpacking or rebuilding
internal COMPAS objects by hand.

The long-term primary workflow therefore follows the RhinoVault/TNA sequence:

```text
Register -> Relax -> Form -> Dual -> Horizontal -> Vertical -> Reciprocal
```

Each stage consumes one typed state and returns one typed state. Focused query
and display components may inspect a state, but they never become a second
solver or infer correspondence from geometry proximity.

## What works now

`TNA Solve` currently performs the essential form/force and vertical
equilibrium operations internally for a registered faced problem. The final
result retains:

- resolved spatial thrust geometry;
- planar form and reciprocal force graphs;
- stable form/force/thrust member correspondence;
- member force density `q`, horizontal force `H`, and spatial axial force
  `F`;
- supports, loads, reactions, source mappings, and diagnostics.

It starts from the faced topology supplied by `Network`. It does not yet
provide the separate RhinoVault pattern-relaxation/boundary-sag operation,
arbitrary analysis plane, independent form/force pins, or editable
intermediate dual and horizontal states. Those capabilities belong to the
planned stages below; the current component should not be described as a full
RhinoVault replacement.

The current result and display wiring is:

```text
TNA Solve.Result
    +--> viewport
    |      resolved thrust edges
    |
    +--> TNA Geometry
    |      Thrust Mesh, Thrust Edges, Form Edges, Equilibrium bridge
    |
    +--> TNA Members
    |      IDs, Thrust Lines, q, H, F, State, Source Edge IDs
    |
    +--> TNA Actions
    |      Supports, Loads, Reactions
    |
    +--> TNA Reciprocal
             |
             +--> Graphic Diagram Display
                  styled form/thrust/force/actions plus native lines
```

`TNA Reciprocal` constructs one renderer-neutral `GraphicDiagram`.
`Graphic Diagram Display` owns visual styling and exposes its roles as
ordinary Rhino lines. This keeps numerical correspondence separate from
presentation and makes the diagram deconstructable without a large generic
result component.

`Result Breakdown` remains a legacy full deconstructor for the generic
`EquilibriumResult`, principally FD. It does not directly accept
`TnaResult`. If an existing definition cannot yet be migrated, use:

```text
TNA Solve.Result
    -> TNA Geometry.Equilibrium
    -> Result Breakdown.Result
```

That bridge is for compatibility, not the recommended TNA workflow.

## Planned staged surface

### 1. TNA Register

Purpose: turn the supplied mesh or pattern geometry into one deterministic,
validated TNA topology.

Planned responsibilities:

- register vertices, edges, faces, boundary loops, and connected components;
- preserve source geometry and segmentation IDs;
- establish the analysis plane rather than assuming world XY;
- validate manifold/faced topology and identify unsupported conditions;
- distinguish dimensional metadata from coordinate scaling.

The output is a registered pattern, not a solved or already-funicular mesh.

### 2. TNA Relax

Purpose: edit the planar pattern before reciprocal construction.

Planned controls:

- uniform or member-aligned relaxation force density;
- fixed pattern points and edges;
- opening-boundary relaxation and boundary-sag controls;
- iteration and tolerance settings;
- optional guide geometry while retaining source IDs.

This is planar force-density relaxation of the pattern. It is not the vertical
TNA solve and does not claim that the relaxed geometry is a final thrust
network.

### 3. TNA Form

Purpose: create the constrained form diagram and attach the physical/problem
roles needed by TNA.

Planned responsibilities:

- structural supports that can carry reactions;
- independent plan-position pins that constrain form geometry;
- nodal loads and elevations;
- compression/tension edge roles;
- form-edge length and direction bounds;
- boundary and opening updates;
- validation that distinguishes structural support from a geometric pin.

The output is an inspectable form state. Grasshopper operations may select or
modify roles before the reciprocal dual is created.

### 4. TNA Dual

Purpose: create the topological reciprocal force diagram from the form
diagram.

Planned responsibilities:

- build and validate the form/force edge correspondence;
- expose initial force vertices, edges, and cells;
- distinguish independent force vertices/edges from form constraints;
- report topology, orientation, and mapping problems before balancing.

This stage establishes reciprocal topology. It does not yet guarantee
horizontal equilibrium.

### 5. TNA Horizontal

Purpose: solve plan equilibrium and reciprocity between form and force
diagrams.

Planned controls and outputs:

- horizontal balancing method and alpha;
- iteration limits and separate numerical tolerances;
- form/force pins and geometric bounds;
- balanced planar form and reciprocal force states;
- per-edge reciprocity errors and closure diagnostics;
- inspectable pre- and post-balance geometry.

At this stage, force density `q` and horizontal force `H` express the balanced
relative force distribution. Until a vertical height or force calibration
fixes the physical scale, they must not be presented as final physical demand.

### 6. TNA Vertical

Purpose: lift the horizontally balanced form into the spatial funicular thrust
network.

Planned modes:

- target crown or maximum height;
- prescribed force-density/horizontal-force scale;
- density and later thickness/self-weight controls where the selected COMPAS
  TNA version supports them reliably;
- vertical iteration, absolute tolerance, and relative tolerance.

The output is the final `TnaResult`. It records the chosen calibration and
spatial axial-force demand `F` together with final `q` and `H`. These are
equilibrium demands, not material capacity, utilisation, or verified
prestress.

### 7. TNA Reciprocal

Purpose: package the linked form, force, thrust, load, and reaction state for
graphic-statics inspection and design.

The implemented `TNA Reciprocal` already performs the final-result version of
this role. The staged version should also accept the horizontal state so the
reciprocal diagram can be inspected before the vertical solve. It must retain
stable mappings and diagnostics; it must not rebuild reciprocity from nearby
lines.

Presentation remains separate:

```text
TNA Reciprocal.Diagram
    -> Graphic Diagram Display
    -> editable Rhino/Grasshopper diagram geometry
```

Directional load-line, pole-ray, and funicular-polygon construction is a
later specialised graphic-statics workflow. A general TNA reciprocal is a
force mesh or collection of cells and is not required to fit one enclosing
triangle.

## State and component rules

- `TNA Solve` stays as the convenience macro and should be implemented by the
  same stage services, not a divergent numerical path.
- Every stage preserves source IDs, units, sign convention, load-case
  identity, and solver provenance.
- Components exchange typed states instead of parallel list bundles.
- A displayed or deconstructed diagram never becomes the numerical source of
  truth unless a future design component explicitly creates a new constrained
  state and requests another solve.
- Plan pins, structural supports, and reciprocal-force pins are separate
  concepts and separate inputs.
- A changed pattern, support, load, height, force scale, or column head
  invalidates downstream stages and requires recomputation.
- `q`, `H`, and `F` are force demand/state variables. Capacity requires
  material, section, stability, connection, load-combination, and verification
  models.

## Later design-by-statics extensions

The staged result provides a stable base for later components without
hard-wiring the user's evolving branch system:

```text
TnaResult
    -> TNA Members
    -> force-flow/path query
    -> principal-path and high-demand-node candidates
    -> user-authored branch/column topology
    -> augmented supports and another TNA solve
    -> structural model and FEA verification
```

Spatial graphic statics, directional 2D constructions, prestress design,
inverse load-case fitting, branch placement, `compas_model`, COMPAS FEA, and
IFC delivery remain separate milestones. Their contracts should consume the
same immutable staged states rather than expanding `TNA Solve` or `Result
Breakdown` into another all-purpose component.

## Primary references

- [RhinoVault workflow](https://blockresearchgroup.gitbook.io/rhinovault/manual)
- [RhinoVault pattern tutorial and relaxation](https://blockresearchgroup.gitbook.io/rhinovault/introduction/tutorial)
- [RhinoVault horizontal equilibrium](https://blockresearchgroup.gitbook.io/rhinovault/manual/horizontal-equilibrium)
- [RhinoVault vertical equilibrium](https://blockresearchgroup.gitbook.io/rhinovault/manual/fitting)
- [COMPAS TNA](https://blockresearchgroup.github.io/compas_tna/latest/)
- [COMPAS TNA equilibrium API](https://blockresearchgroup.github.io/compas_tna/latest/api/compas_tna.equilibrium.html)
