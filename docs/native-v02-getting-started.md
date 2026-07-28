# Native v0.2: install and first FD workflow

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
   workflow. `compas` and `compas_fd` are required for the current FD solve.

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
environment check. In v0.2, `fd.solve` is the only numerical command exposed
by the native workflow.

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
   Give the complete geometry list to `Network`, set `Kind` to `Line`, use a
   weld tolerance appropriate to the Rhino model, and state the length unit.
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
component error rather than falling back to a different mode. `Faced`
registration is available for future TNA work, but `FD Solve` accepts only a
`Line` topology.

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

Use `Result Breakdown` when downstream Grasshopper operations require explicit
lines and aligned values. Check its diagnostics and residual vectors before
treating a form as equilibrated. The result is an equilibrium/form-finding
result, not a stiffness analysis, design-code check, or verified IFC
structural model.

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

## Current boundary and roadmap

The native v0.2 slice currently provides whole-network FD form finding and
result visualisation. The following remain separate future milestones:

- TNA registration, solving, and thrust-network visualisation;
- reciprocal 2D graphic statics and spatial/3D graphic statics;
- branch placement, Steiner 120-degree operations, and network design tools;
- `compas_model` structural decomposition;
- material, section, stiffness, restraint, combination, and result workflows
  for FEA;
- reviewed analytical/physical IFC formulation and export.

Those packages may already exist in the selected Python environment. They are
not complete Grasshopper features until their native contracts, commands,
components, validation, and representative tests are implemented.
