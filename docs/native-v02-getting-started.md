# Native v0.2: install and first FD/TNA workflows

This guide covers the current compiled C# Grasshopper plugin and its external
COMPAS Python worker. It does not describe the preserved script-backed v0.1
prototype.

## What is installed

The default installer creates:

```text
%APPDATA%\Grasshopper\Libraries\Ananke_COMPAS\
    Ananke.COMPAS.gha
    backend.json
    icons\
    python\
        ananke_equilibrium\
        tree_forest_compas\
```

`Ananke.COMPAS.gha` contains the native Grasshopper components. The Python
folder contains the worker and COMPAS adapters, not Grasshopper Script
components. `backend.json` records the exact interpreter and site-environment
paths used by the plugin.

The worker starts hidden when a component first requests health information or
a solve. It remains available for later requests and uses framed JSON over
standard input and output. The plugin does not open Rhino during build or
installation.

## Prerequisites

Install or confirm:

1. Rhino 8 with Grasshopper.
2. The .NET 8 SDK (`dotnet --version`).
3. Rhino 8's CPython interpreter, normally:

   ```text
   C:\Users\<you>\.rhinocode\py39-rh8\python.exe
   ```

4. A Rhino Python site environment whose folder starts with
   `catenary-compas-2026-` and contains the COMPAS packages used by the
   workflow. `compas` and `compas_fd` are required for FD; `compas_tna` is
   additionally required for the native TNA solve.

The default installer selects the most recently modified matching
site-environment folder. It writes the resolved path to `backend.json`; the
runtime does not rely on `PATH` or a wildcard.

## Build and install

Close Rhino before replacing a loaded plugin. In PowerShell:

```powershell
git switch development
git pull
& .\plugin\native_v02\Build-And-Install.ps1
```

The default destination is:

```text
C:\Users\<you>\AppData\Roaming\Grasshopper\Libraries\Ananke_COMPAS
```

If automatic environment discovery cannot find the intended environment, pass
exact paths:

```powershell
& .\plugin\native_v02\Build-And-Install.ps1 `
  -PythonExecutable "C:\Users\<you>\.rhinocode\py39-rh8\python.exe" `
  -SiteEnvironmentPath "C:\Users\<you>\.rhinocode\py39-rh8\site-envs\catenary-compas-2026-<id>"
```

For a build without installation:

```powershell
dotnet build .\plugin\native_v02\Ananke.COMPAS.Native.csproj -c Release
```

The installer prints the assembly identity, selected Python paths, and SHA-256
hash when it succeeds.

## Confirm the backend

After installation:

1. Start or restart Rhino 8 yourself.
2. Open Grasshopper.
3. Find the `Ananke COMPAS` tab.
4. Place `90 Query > Backend Health`.
5. Confirm `Ready` is `True`.

The other outputs identify the Python runtime, detected package versions,
advertised capabilities, and protocol report. Package presence is only an
environment check. The implemented numerical commands in this slice are
`fd.solve`, `tna.prepare`, and `tna.solve`.

If `Ready` is false, read the component's runtime error and `Report`, then
inspect:

```text
%APPDATA%\Grasshopper\Libraries\Ananke_COMPAS\backend.json
```

Confirm that `executable` is a file and every entry in `pythonPaths` is an
existing folder. Re-run the installer with explicit paths instead of changing
the JSON to guessed locations.

## Build the first whole-network FD definition

The current component chain is:

```text
Network.Topology --> Support Set.Topology
Network.Topology --> Load Case.Topology

Network.Topology ---------+
Support Set.Supports -----+--> Equilibrium Problem.Problem
Load Case.Load Case ------+

Equilibrium Problem.Problem --> FD Solve.Problem
FD Settings.Settings --------> FD Solve.Settings

FD Solve.Result --> Equilibrium Preview.Result
FD Solve.Result --> Result Breakdown.Result
```

Use these steps for a small catenary or cable test:

1. Create a connected line or polyline with at least one free internal vertex.
   Give the complete geometry list to `Network`, use a weld tolerance
   appropriate to the Rhino model, and state the length unit. A newly placed
   component receives dropdowns for `Kind` and `Length Unit`; the supported
   units are `mm`, `cm`, `m`, `in`, and `ft`, with `m` selected by default.
   The unit is metadata and does not rescale the supplied coordinates.
   Reopened or copied components are not mutated; right-click `Network` and
   choose `Create suggested value lists` if a missing dropdown is wanted.
   Use `Kind = Line` for lines and polylines. A mesh may remain `Auto`/`Faced`:
   FD consumes its registered edge network while retaining its faces for TNA.
   `Network` intentionally flattens every Geometry tree branch and registers
   all supplied segments as one topology. A polyline becomes one member per
   segment. Coincident members are merged and retain all contributing source
   segment IDs joined by `|`.
2. Connect the topology to `Support Set`. For the first test, use `Explicit`
   mode and supply the two endpoint locations through `Points`. The points must
   fall within `Snap Tolerance`; if it is omitted, the Network weld tolerance
   is used. The component converts them to stable node IDs before Python runs.
   `Terminals` and `Boundary` are automatic alternatives and require `Points`
   and `Node IDs` to be disconnected. Geometric corner detection is not
   implemented yet.
3. Connect the same topology to `Load Case`. Supply internal topology vertices
   through `Points` and one downward vector to broadcast, or one vector per
   target. Keep `Distribution` as `Point` for this explicit first test and set
   `Snap Tolerance` if the Network tolerance is too strict. `Point`, `Uniform
   Nodes`, and explicit `Custom` are the implemented distributions;
   tributary-area and self-weight generation are not. The force unit is
   metadata; all numeric inputs must already use one consistent unit system.
   `Factor` is applied in the native component before the effective vectors
   enter the solver and is retained as provenance.
   `Point` and `Custom` require targets. For `Uniform Nodes`, leave `Points`
   and `Node IDs` disconnected and supply exactly one base vector.
4. Connect the topology, support set, and load case to
   `Equilibrium Problem`. Its `Load Cases` input is a list, so additional named
   cases can be added later.
5. Give `FD Settings` one force-density value to broadcast to every member, or
   exactly one value per topology edge. Every value must be finite and
   have magnitude greater than `1e-12`, using force-unit per length-unit
   numerics. Native v0.2 fixes the COMPAS sign convention to
   `positive_tension`; it is not a selectable component input.
6. Connect the problem and settings to `FD Solve`. Leave `Load Case Index` at
   `0` for the first load case.
7. Connect the result to `Equilibrium Preview` for viewport lines and to
   `Result Breakdown` for aligned member forces, force densities, loads,
   reactions, residuals, stable member source IDs, resolved support node IDs
   and points, diagnostics, and the backend report.

The input linework is the network's connectivity and starting geometry. Do not
solve every line separately or feed an already deconstructed collection of
independent funicular curves. FD solves the free node coordinates of the
connected network from its topology, fixed supports, applied loads, and force
densities.

All Geometry, support-target, load-target, load-vector, and force-density list
inputs are flattened intentionally. Node IDs are zero-based after welding and
removal of unused points. Vertex IDs (`v0`, `v1`, ...) and member source IDs
are deterministic for the exact flattened geometry and input order, but they
can change if that order, segmentation, or weld tolerance changes. Prefer
point snapping while a definition is still being edited; use explicit node IDs
only when the registered topology is controlled.

The documented option names are strict. `Corners`, `Tributary Area`, and
`Self Weight` are not generated by this milestone and produce an actionable
component error rather than falling back to a different mode. `FD Solve`
consumes the registered edge network of either a `Line` or `Faced` topology;
`TNA Solve` requires `Faced` registration with valid faces.

## Build the first staged TNA definition

Use the compact RhinoVault-style chain for a new TNA definition:

```text
Geometry
  -> TNA Pattern.Pattern
  -> TNA Supports.Pattern
  -> TNA Relax + Boundaries.Prepared
  -> TNA Equilibrium.TNA Result

TNA Pattern.Topology -> Load Case.Topology
Load Case.Load Case --> TNA Equilibrium.Load Case  (optional)

TNA Equilibrium.TNA Result --> TNA Geometry
TNA Equilibrium.TNA Result --> TNA Members
TNA Equilibrium.TNA Result --> TNA Actions
TNA Equilibrium.TNA Result --> TNA Reciprocal
TNA Reciprocal.Diagram -----> Graphic Diagram Display
```

### 1. Register the pattern

Place `02 Form Finding > TNA Pattern`. Connect the complete mesh or line
pattern as one Geometry list.

The `Mode` value list contains `Mesh`, `Lines`, `Surface`, `Grid`,
`Triangulation`, and `Skeleton`, but only the first two are implemented:

- use `Mesh` for a mesh with valid faces;
- use `Lines` for a planar graph whose intersections are already split and
  whose edges bound closed faces. The worker derives those faces during
  preparation and rejects dangling, open, or unsplit geometry;
- the other four modes report that their topology generator is not
  implemented. They never fall back to a guessed mesh.

Newly placed `TNA Pattern` components create this dropdown automatically. If
an older or copied component has no dropdown, right-click it and choose
`Create suggested value lists`.

`Resolution` is reserved for the future generator modes and does not remesh
Mesh or Lines input. Set `Weld Tolerance` to the smallest useful modelling
tolerance. The component infers `mm`, `cm`, `m`, `in`, or `ft` from the active
Rhino document and records it as metadata; coordinates are not converted.

`Pattern` is the staged bundle. `Topology` is the unchanged source topology
to use when creating a custom `Load Case`.

### 2. Select the true anchors

Connect `TNA Pattern.Pattern` to `TNA Supports.Pattern`, then supply the real
anchor or column-head locations as `Anchor Points`. The component snaps those
points to pattern nodes. An optional `Snap Tolerance` overrides the Pattern
weld tolerance.

Do not connect every naked boundary vertex unless the complete rim really is
continuously held. Only selected anchors are fixed. The intermediate vertices
between two anchors remain free and form an unsupported boundary opening.
Adjacent supported boundary vertices form a held edge and cannot sag. If all
boundary vertices are selected, the straight held boundary is the expected
condition, not a thrust-forming error.

At least two distinct anchors are required. Collinear anchors are permitted
for an arch or strip, with a warning because a two-dimensional mesh may still
be singular.

### 3. Relax the pattern and boundary openings

Connect the supported Pattern to `TNA Relax + Boundaries`.

- `Force Density` defaults to `1.0` and must be positive. It is a nominal
  plan-FDM weight; its uniform absolute value is not a physical kN force.
- `Boundary Sag` defaults to `10%` and means exact target rise/span for every
  eligible support-to-support opening.

The worker flattens the source into world XY, performs plan FDM relaxation,
identifies support-to-support paths with intermediate free vertices, and
iteratively adjusts their edge force densities. An arbitrary analysis-plane
input is not exposed in this milestone. The current component uses ten sag
iterations and an absolute rise/span tolerance of `0.01`; it warns if a target
is not met. This exact-target interpretation differs from compas-RV's
minimum-sag user control, while adapting its boundary splitting, sag
measurement, relaxation, and update mechanics. See the
[compas-RV Pattern source](https://github.com/BlockResearchGroup/compas-RV/blob/main/src/compas_rv/datastructures/pattern.py)
and [third-party notice](../THIRD_PARTY_NOTICES.md).

The single `Prepared` output contains the relaxed pattern, boundary records,
conditioned form graph, and topological dual force graph. The force graph is
deliberately unbalanced at this point; it represents reciprocal connectivity,
not final physical force. The component previews the relaxed form and
unsupported openings in the model, with the topological force graph placed to
the side.

### 4. Solve horizontal and vertical equilibrium

Connect `Prepared` to `TNA Equilibrium`.

- `Mode = Crown Height` is the default. `Value` is the target crown Z and
  defaults to `5.0`; it must be above the highest support elevation.
- `Mode = Force Scale (signed q)` interprets `Value` as a signed
  force-density scale with force/length dimensions. With the fixed
  `positive_tension` convention, compression uses negative `q`. It is not a
  direct member force in kN.

Newly placed `TNA Equilibrium` components create the mode dropdown
automatically; the same right-click command restores it without changing the
component's inputs.

`Load Case` is optional. If it is empty, the component creates and reports a
`(0,0,-1)` load at every source-topology node with `kN` metadata. For a custom
case, connect `TNA Pattern.Topology` to `Load Case.Topology`, then connect the
resulting case to `TNA Equilibrium`. Units are metadata and numeric conversion
is not performed, so all custom values must already use one consistent unit
system. Each solve consumes one `Load Case` item; use separate Grasshopper
branches when comparing independent named cases.

This TNA path currently accepts load vectors along analysis Z only. A custom
case with a nonzero analysis-X or analysis-Y component produces an explicit
error; use FD for a general spatial load vector.

The horizontal alpha, horizontal/vertical iteration counts, and solve
tolerance are intentionally internal defaults in this compact component. Its
output is the existing strict `TnaResult`.

### 5. Read and display the result

`TNA Equilibrium` previews the solved form, spatial thrust network, reciprocal
force diagram, loads, and reactions, with the force diagram placed to the
side. Every staged component's custom drawing obeys Grasshopper's native
Preview command: Preview off hides that component's viewport output, and
Preview on restores it.

For ordinary Rhino geometry and focused data:

- `TNA Geometry` returns the proper Rhino thrust mesh, thrust edges, form
  edges, and generic equilibrium bridge;
- `TNA Members` returns aligned member IDs, lines, `q`, `H`, `F`, force
  states, and source-edge groups;
- `TNA Actions` returns and previews supports, loads, and reactions;
- `TNA Reciprocal -> Graphic Diagram Display` packages and styles the linked
  form, thrust, reciprocal force, load, and reaction geometry.

`Graphic Diagram Display` owns its styled custom preview. Its ordinary line
outputs remain available downstream but their automatic green output preview
is suppressed to avoid drawing a duplicate. Turning Preview off on the
display component hides the styled drawing.

The displayed `q`, `H`, and `F` values are equilibrium demands, never member
capacities. A general TNA mesh produces a reciprocal force mesh or collection
of cells and is not expected to fit inside one triangular force diagram. The
directional dashed load line, pole rays, funicular polygon, principal-path
queries, and column-placement loop remain later components.

### Compatibility: the one-shot TNA macro

Existing definitions can continue to use:

```text
Faced Network + Support Set + Load Case
  -> Equilibrium Problem + TNA Control
  -> TNA Solve
```

That path requires a faced `Network` topology and keeps its load-case selector
by exact name, stable case ID, or zero-based index written as text. It does not
expose the staged pattern relaxation or boundary-sag state. New definitions
that need RhinoVault-style boundary control should use the four staged
components above.

## Reading the result

`Equilibrium Preview` uses preset colours:

- red: tension;
- blue: compression;
- orange: applied loads;
- green: reactions;
- magenta: residuals.

`Force Weight` changes member line-weight response without changing the
analysis. `Vector Scale` changes only the displayed load, reaction, and
residual lengths.

For a generic FD result, use `Result Breakdown` when a legacy downstream
Grasshopper operation requires its complete output surface. Check its
diagnostics and residual vectors before treating a form as equilibrated. The
result is an equilibrium/form-finding result, not a stiffness analysis,
design-code check, or verified IFC structural model.

`Member Source IDs` aligns one-to-one with `Member Lines`. Before attaching
those IDs, the native result decoder verifies that the worker returned the
same edge count and edge order as the registered topology. An edge created
from a polyline segment has an ID such as `g0:s1`; a welded duplicate can have
a joined value such as `g0:s1|g2:s0`. These are provenance keys for
segmentation, not permanent Rhino object IDs.

`Support Node IDs` contains every fixed form-finding node selected for the
solve, including an automatically selected terminal or boundary support whose
reaction happens to be zero. `Support Points` contains the corresponding
solved vertex positions in the same order.

For TNA, keep the richer typed result intact and choose a focused consumer:

- `TNA Geometry` returns the resolved thrust mesh, thrust edges, form edges,
  and an embedded generic equilibrium bridge.
- `TNA Members` returns one aligned member table: IDs, resolved lines, `q`,
  `H`, `F`, force state, and source-edge groups.
- `TNA Actions` returns supports plus paired load and reaction points/vectors,
  and previews those vectors.
- `TNA Reciprocal -> Graphic Diagram Display` constructs and displays the
  linked graphic-statics representation.

`Result Breakdown` accepts a generic `EquilibriumResult`; it does not directly
accept `TnaResult`. This is why connecting `TNA Equilibrium.TNA Result` or
`TNA Solve.Result` to it produces a Grasshopper type error. It is retained for
saved FD definitions. If an old operation cannot yet be migrated, use the
explicit compatibility path:

```text
TNA Equilibrium.TNA Result
    -> TNA Geometry.Equilibrium
    -> Result Breakdown.Result
```

New TNA definitions should use the focused components and avoid expanding
every solved quantity when only one responsibility is needed.

## Current boundary and roadmap

The native v0.2 slice currently provides whole-network FD form finding, the
four-component staged TNA authoring path, the retained one-shot faced TNA
macro, focused TNA queries, and an explicit compact graphic-diagram display.
The staged path exposes pattern registration, explicit support selection,
plan/boundary relaxation, the initial form/topological-force state, and the
height- or force-scale-controlled equilibrium result. See
[`architecture/rhinovault-native-stages.md`](architecture/rhinovault-native-stages.md).

The following also remain separate future milestones:

- force-flow ranking and traceable path queries from TNA;
- directional path registration, effective transverse-load transfer, and the
  dashed load-line/pole/funicular 2D construction;
- generic AGS and spatial/3D graphic statics;
- column-head candidate selection, support augmentation and TNA re-solving,
  followed by branch placement and geometric or force-weighted Steiner tools;
- `compas_model` structural decomposition;
- material, section, stiffness, restraint, combination, and result workflows
  for FEA;
- reviewed analytical/physical IFC formulation and export.

Those packages may already exist in the selected Python environment. They are
not complete Grasshopper features until their native contracts, commands,
components, validation, and representative tests are implemented.
