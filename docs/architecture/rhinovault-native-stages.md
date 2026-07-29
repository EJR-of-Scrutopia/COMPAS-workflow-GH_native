# RhinoVault-style native TNA stages

Status: the first compact native authoring sequence is implemented. The
recommended Grasshopper path is:

```text
TNA Pattern
    -> TNA Supports
    -> TNA Relax + Boundaries
    -> TNA Equilibrium
    -> TnaResult
```

The older `Equilibrium Problem + TNA Control -> TNA Solve` path remains as a
one-shot compatibility macro. Both paths use the external COMPAS Python
worker; the Grasshopper components themselves are compiled C#.

## Why these four stages

The four-component surface follows the design decisions in a RhinoVault
workflow without exposing every numerical parameter on the canvas:

1. register the pattern and its stable source topology;
2. identify the actual structural supports;
3. relax the planar pattern, shape its unsupported boundary openings, and
   create the initial form/force topology;
4. solve horizontal and vertical equilibrium by a target crown Z or signed
   force-density scale.

Each component returns one typed state rather than a bank of parallel lists.
The intermediate `Prepared` state retains the relaxed pattern, boundary
records, form graph, topological force graph, mappings, units, and
diagnostics. The final stage returns the existing `TnaResult`, so the focused
query and display components do not need a second data model.

## 1. TNA Pattern

`TNA Pattern` registers the input as one stable source pattern. It outputs:

- `Pattern`: the compact staged pattern bundle;
- `Topology`: the unchanged source topology used to construct an optional
  `Load Case`.

The `Mode` value list contains `Mesh`, `Lines`, `Surface`, `Grid`,
`Triangulation`, and `Skeleton`. Current support is deliberately narrower:

- `Mesh` is implemented and preserves the supplied mesh faces;
- `Lines` is implemented for planar lines or polylines whose intersections
  have already been split. The preparation worker derives closed faces and
  rejects dangling, open, or unsplit patterns;
- `Surface`, `Grid`, `Triangulation`, and `Skeleton` are roadmap entries. They
  produce an explicit component error and never substitute guessed geometry.

`Resolution` is retained for those future generators and does not remesh
current Mesh or Lines input. `Weld Tolerance` merges coincident topology
nodes. Length-unit metadata is inferred from the active Rhino document for
`mm`, `cm`, `m`, `in`, or `ft`; coordinates are not rescaled. If no active
document is available, the component warns and records `m`. An unsupported
Rhino document unit is rejected so unscaled coordinates are never silently
relabeled as metres.

The component previews the registered source edges. A disconnected source is
reported and should be prepared as separate patterns.

## 2. TNA Supports

`TNA Supports` snaps explicit `Anchor Points` to the stable source pattern. At
least two distinct snapped nodes are required. The optional snap tolerance
overrides the Pattern weld tolerance.

These points are structural supports: they can carry reactions in the final
TNA solve. They should be the real anchors or column-head locations, not every
naked mesh-boundary point. The distinction controls the boundary geometry:

- two consecutive supports delimit a support-to-support boundary path;
- intermediate vertices on that path remain free and can move during
  relaxation;
- adjacent supported boundary vertices define a held edge with no free
  intermediate vertex;
- selecting every boundary vertex intentionally holds the complete rim and
  leaves no opening that can receive sag.

This is the principal correction for a vault whose boundary stays as one
straight held line: reduce the support input to the true holding locations.
If a continuously held rim is the design intent, selecting all of its
vertices is valid, but zero opening sag is then expected.

The component previews the source pattern and the snapped support points.
Collinear supports are allowed for an arch or strip and generate a warning
because a general two-dimensional pattern may remain singular.

## 3. TNA Relax + Boundaries

`TNA Relax + Boundaries` flattens the registered pattern into world XY,
applies uniform positive plan-FDM force density, relaxes free vertices, splits
boundary loops at the structural supports, and shapes every eligible opening.
An arbitrary analysis-plane input is not exposed in this milestone. Its
compact inputs are:

- `Pattern`: the supported Pattern from `TNA Supports`;
- `Force Density`: a positive nominal plan-relaxation weight, default `1.0`;
- `Boundary Sag`: target opening rise/span in percent, default `10%`.

The relaxation force density controls the relative planar FDM weights. Its
uniform absolute value does not calibrate final forces in kN.

For each support-to-support path containing an intermediate boundary vertex,
the worker records the initial, target, and actual rise/span ratio. It
iteratively rescales the path edge force densities and repeats FDM relaxation.
The current native component uses ten iterations and an absolute rise/span
tolerance of `0.01`. It warns when the exact target has not been reached
within that tolerance.

The UI semantics are intentionally an exact target for every eligible
opening. They are not the minimum-sag behavior of compas-RV's user-facing
boundary control. The boundary splitting, sag measurement, FDM relaxation,
and force-density update mechanics are adapted from the Block Research
Group's
[compas-RV Pattern implementation](https://github.com/BlockResearchGroup/compas-RV/blob/main/src/compas_rv/datastructures/pattern.py).
See [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) for attribution and
the upstream MIT terms.

After relaxation, the worker creates:

- a conditioned planar form graph;
- its topological dual force graph;
- stable form/source mappings and boundary-opening records.

The force graph at this stage is topological and intentionally unbalanced.
It establishes reciprocal connectivity; it does not yet represent final
horizontal equilibrium or physical force scale. Both graphs live in the one
typed `Prepared` output. The component previews the relaxed form at its model
location and shifts the force graph to the side, with unsupported boundary
paths and anchors distinguished. They are not duplicated as parallel line
outputs; downstream solver code receives their stable correspondence through
the typed state.

If no eligible opening is found, the component warns instead of fabricating
sag. Common causes are adjacent supports around the complete rim or support
placement that does not provide two anchors on a boundary loop.

## 4. TNA Equilibrium

`TNA Equilibrium` reconstructs the prepared state in the worker, performs the
horizontal reciprocal solve, and lifts the form in the vertical solve. Its
inputs are:

- `Prepared`: the typed state from `TNA Relax + Boundaries`;
- `Load Case`: optional load data bound to `TNA Pattern.Topology`;
- `Mode`: `Crown Height` or `Force Scale (signed q)`;
- `Value`: target crown Z or signed force-density scale.

`Crown Height` is the default mode and `Value` defaults to `5.0`. It is a
target crown Z elevation and must lie above the highest support elevation.
`Force Scale` is a signed `q` scale with force/length dimensions. Under the
fixed `positive_tension` convention, compression uses negative `q`; this
value is not a direct member force in kN.

When `Load Case` is empty, the component creates an explicit nodal load of
`(0, 0, -1)` at every source-topology node, records `kN` metadata, and reports
that default in Grasshopper. A connected load case must use the `Topology`
output from the same `TNA Pattern`. Force and length units are metadata: the
solver does not convert numeric values, so custom inputs must already use one
consistent unit system. The input is one `Load Case` item per solve; compare
independent named cases through separate Grasshopper solver branches.
Current TNA load vectors must lie along analysis Z. Nonzero analysis-X/Y
components are rejected explicitly; FD remains the general spatial-load path.

The horizontal alpha, horizontal and vertical iteration limits, and numerical
tolerance are currently internal defaults rather than extra canvas inputs.
The output is one strict `TnaResult` containing spatial thrust geometry,
balanced planar form and reciprocal force graphs, member `q`, `H`, and `F`,
loads, reactions, stable source correspondence, and diagnostics.

The component previews form, thrust, reciprocal force, loads, and reactions
side by side. `q`, `H`, and `F` are equilibrium demands, not member capacity,
utilisation, stiffness, or verified prestress.

## Preview and downstream display

Each stage owns a viewport preview of the state it creates:

| Component | Native preview |
| --- | --- |
| `TNA Pattern` | registered source edges |
| `TNA Supports` | source edges and snapped anchors |
| `TNA Relax + Boundaries` | relaxed form, highlighted openings and supports, topological force graph to the side |
| `TNA Equilibrium` | solved form/thrust/force state plus loads and reactions |

Grasshopper's native Preview command controls these custom previews. Turning
Preview off on the component hides its viewport drawing; turning it on shows
it again.

The final typed result can be consumed without a large result-breakdown
component:

```text
TNA Equilibrium.TNA Result
    +--> TNA Geometry
    |      Thrust Mesh, Thrust Edges, Form Edges, Equilibrium bridge
    +--> TNA Members
    |      IDs, Thrust Lines, q, H, F, State, Source Edge IDs
    +--> TNA Actions
    |      Supports, Loads, Reactions
    +--> TNA Reciprocal
             -> Graphic Diagram Display
```

`TNA Reciprocal` packages the solved form, thrust, reciprocal force, loads,
and reactions into one renderer-neutral `GraphicDiagram`. `Graphic Diagram
Display` applies a visual preset and exposes ordinary Rhino line outputs. Its
custom preview also obeys the component's native Preview setting; its line
output previews are kept hidden internally to avoid drawing duplicate default
green lines.

The familiar directional dashed load line, pole rays, and funicular polygon
are not part of this milestone. A general TNA reciprocal is a force mesh or
collection of cells and is not required to fit inside one triangle.

## Compatibility path

The older chain remains available for saved definitions:

```text
Faced Network + Support Set + Load Case
    -> Equilibrium Problem + TNA Control
    -> TNA Solve
```

`TNA Solve` is a one-shot faced-topology macro. It does not expose the staged
boundary-opening relaxation state. New definitions that need RhinoVault-style
pattern relaxation and sag control should use the four staged components.

`Result Breakdown` remains a legacy full deconstructor for the generic
`EquilibriumResult`, principally FD. It does not accept `TnaResult` directly.
If an existing downstream operation cannot yet be migrated, use:

```text
TNA Equilibrium.TNA Result
    -> TNA Geometry.Equilibrium
    -> Result Breakdown.Result
```

## Later design-by-statics extensions

Directional 2D graphic statics, generic AGS, spatial/3D graphic statics,
force-flow ranking, inverse load-case fitting, column and branch placement,
Steiner relaxation, prestress design, `compas_model`, FEA, and IFC delivery
remain separate milestones. They should consume the typed `Prepared` or
`TnaResult` states rather than expanding the solver outputs or reconstructing
correspondence from nearby lines.

## Primary references

- [RhinoVault workflow](https://blockresearchgroup.gitbook.io/rhinovault/manual)
- [RhinoVault boundary conditions](https://blockresearchgroup.gitbook.io/rhinovault/manual/2.-define-boundary-conditions/boundary-conditions-2)
- [compas-RV Pattern source](https://github.com/BlockResearchGroup/compas-RV/blob/main/src/compas_rv/datastructures/pattern.py)
- [COMPAS TNA](https://blockresearchgroup.github.io/compas_tna/latest/)
- [COMPAS TNA equilibrium API](https://blockresearchgroup.github.io/compas_tna/latest/api/compas_tna.equilibrium.html)
