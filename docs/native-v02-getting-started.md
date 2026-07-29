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
`fd.solve` and `tna.solve`.

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

## Build the first TNA reciprocal definition

TNA reuses the same topology, supports, load cases, and problem bundle. Its
additional control and display chain is:

```text
Faced Network.Topology --> Support Set.Topology
Faced Network.Topology --> Load Case.Topology

Network.Topology ---------+
Support Set.Supports -----+--> Equilibrium Problem.Problem --> TNA Solve.Problem
Load Case.Load Case ------+                                  ^
                                                              |
TNA Control.Control ------------------------------------------+

TNA Solve.Result --> TNA Reciprocal.TNA Result
TNA Reciprocal.Diagram --> Graphic Diagram Display.Diagram

TNA Solve.Result --> TNA Geometry.TNA Result
TNA Solve.Result --> TNA Members.TNA Result
TNA Solve.Result --> TNA Actions.TNA Result
```

1. Supply a mesh with valid faces to `Network` and choose `Kind = Faced`
   (`Auto` also detects a mesh). TNA uses the complete registered face
   topology as one pattern; do not deconstruct it into separately solved
   curves or supply an already resolved thrust network.
2. Create supports and one or more named load cases exactly as for FD, then
   assemble them with `Equilibrium Problem`.
3. Add `TNA Control`. Its suggested `Height Mode` value list offers `Crown
   Height` (`zmax`) and `Force Scale` (`q`). `Height Value` is respectively
   the target crown elevation or a non-zero force-density scale. `Horizontal
   Alpha`, horizontal/vertical iteration limits, and `Tolerance` are solver
   controls, not viewport settings.
4. Connect the problem and control to `TNA Solve`. `Load Case` accepts an
   exact case name, a stored stable case ID, or a zero-based index written as
   text; an empty input selects the first case. A text Panel is therefore the
   clearest selector when the problem contains several named cases.
5. `TNA Solve` itself previews the resolved thrust edges. Enable Grasshopper
   preview and use Zoom Extents if needed. To obtain a proper Rhino mesh rather
   than only the direct edge preview, connect the result to
   `90 Query > TNA Geometry` and use its `Thrust Mesh` output. Use
   `TNA Actions` for load and reaction arrows with an explicit display scale.
6. Connect the result to `03 Graphic Statics > TNA Reciprocal`. Newly placed
   components receive value lists for `Layout` (`Side by Side` or `Overlay`)
   and `Metric` (`Natural F / H`, `Force Density q`, `Horizontal Force H`, or
   `Axial Force F`). `Force Scale`, `Vector Scale`, and `Gap Ratio` change only
   the drawing layout; they do not rerun TNA.
7. Connect `TNA Reciprocal.Diagram` to
   `03 Graphic Statics > Graphic Diagram Display`. Choose `Analysis`,
   `Classical GS`, or `Monochrome`, switch the five diagram roles on or off,
   and adjust only the display `Weight Scale`. This component provides the
   reliable styled viewport preview and ordinary Rhino line outputs for the
   form, thrust, reciprocal force, load, and reaction diagrams.

`TNA Reciprocal` constructs and can preview the spatial thrust edges, planar
form pattern, mapped reciprocal force diagram, applied loads, and reactions.
It emits one renderer-neutral `Graphic Diagram` bundle. `Graphic Diagram
Display` is the explicit presentation boundary: it owns colours, line weights,
role visibility, and native line deconstruction without changing the solve.
The force-edge geometry uses the solved physical horizontal scale before
applying the display-only `Force Scale`.

The displayed `q`, `H`, and `F` values describe equilibrium demand. In the
horizontal stage, before vertical calibration fixes the physical force scale,
`q` and `H` are relative equilibrium quantities. The lifted spatial solve
then supplies `F`; the final `TnaResult` stores all three in the selected
scale. None states how much load a member can carry: material, section or
thickness, stability, connections, safety factors, and a verification model
are still needed for capacity or utilisation.

A general TNA mesh produces a reciprocal force mesh or set of cells. It is
not expected to fit inside one triangular force diagram. The familiar dashed
load line, pole rays, and funicular polygon are directional constructions for
an ordered path; their registration and drawing components are the next
graphic-statics stage.

Metric-weighted edges reveal discrete force flow, but they do not yet extract
a unique "principal line". At a branching or high-valence node that requires
an explicit continuation rule, such as maximum transmitted force, minimum
turning angle, or proximity to a guide curve.

Column placement is also a later design loop, not a displacement applied to
this first result. Candidate column heads must be selected, added as new TNA
supports, and solved again; the resulting reactions at those new supports
become the actions passed into the column or branch solver.

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
accept `TnaResult`. This is why connecting `TNA Solve.Result` to it produces a
Grasshopper type error. It is retained for saved FD definitions. If an old
operation cannot yet be migrated, use the explicit compatibility path:

```text
TNA Solve.Result --> TNA Geometry.Equilibrium --> Result Breakdown.Result
```

New TNA definitions should use the focused components and avoid expanding
every solved quantity when only one responsibility is needed.

## Current boundary and roadmap

The native v0.2 slice currently provides whole-network FD form finding, a
one-shot faced TNA solve, a directly previewable final TNA state, focused TNA
queries, and an explicit compact graphic-diagram display. The current
`TNA Solve` internally performs the form/dual, horizontal, and vertical work
and remains the convenience macro.

A future RhinoVault-style authoring surface will expose the sequence as
separate `Register -> Relax -> Form -> Dual -> Horizontal -> Vertical ->
Reciprocal` stages. That staged surface is not implemented by the current
one-shot component. It will allow a user to inspect or alter the relaxed
pattern, support and plan-pin roles, reciprocal dual, horizontal equilibrium,
and height-controlled vertical solve independently. See
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
