# Ananke Equilibrium

Ananke Equilibrium is a bundle-first COMPAS workflow for form finding,
graphic statics, structural handoff, and Rhino 8 Grasshopper.

The current v0.2 development milestone is a native Grasshopper plugin:

- the components visible on the canvas are compiled C#/.NET 8
  `GH_Component` and `GH_TaskCapableComponent` classes;
- one persistent, hidden CPython worker performs the COMPAS calculations
  outside Rhino's process;
- C# and Python exchange versioned, JSON-safe topology, support, load,
  settings, result, and diagnostic contracts;
- RhinoCommon, Grasshopper, live Python, and live COMPAS objects never cross
  the process boundary.

This architecture keeps COMPAS as the numerical source of truth without
turning every Grasshopper component into a visible Python script. The earlier
script-backed prototype is preserved at Git tag
`prototype-script-backed-v0.1.0`.

## Current scope

The native v0.2 vertical slice contains eleven components:

```text
01 Model
  Pattern      Geometry, Mode, Tol            -> PAT  registered pattern
  Supports     PAT, Points, Tol               -> SUP  anchored pattern
  Loads        SUP, Vector, NodeIDs, Factor   -> PRB  problem (surface load
                                                 by default, point loads
                                                 with NodeIDs)

02 Form Finding
  TNA Relax    PRB, ForceDensity, Sag%        -> RLX  relaxed state
  TNA Solve    RLX, Height (optional),
               Iterations (optional), Run     -> RES  result + native
                                                 Mesh/Lines/Supports
  FD Solve     PRB, ForceDensity, Run         -> RES  result (same type) +
                                                 native Lines/Supports

03 Visualise
  Display      RES, STY, Elements, Metric,
               Weight, VectorScale, Gap       -> viewport + ThrustMesh,
                                                 Thrust/Force/Load/Reaction
                                                 lines, Report
  Style        Preset, Weight Scale,
               Vector Scale                   -> STY  display preset
  Deconstruct  RES                            -> every data stream

07 Delivery
  Export       RES,
               Format (contract | compas),
               Path (optional), Write         -> JSON text, written file path

90 System
  Backend Health                              -> ready, packages,
                                                 capabilities, report
```

A blank TNA Solve `Height` finds the natural equilibrium height of the
current force densities and reports it; a number solves so the crown lands
exactly there. A blank `Iterations` auto-converges the horizontal solve
until the reciprocity angle falls below one degree.

Every stage takes one primary typed object and returns it enriched, so the
wire is the workflow. See [Component taxonomy](docs/component-taxonomy.md)
for the full port list with nicknames and per-component responsibilities.

The implemented solver paths share the same registered Problem:

```text
Geometry -> Pattern -> Supports -> Loads = Problem
Problem -> TNA Relax -> TNA Solve -> Result
Problem -> FD Solve ------------------> Result (same type)
Result -> Display / Deconstruct / Export
Style feeds Display.
```

FD and TNA now share one spine end to end. The recommended path is
`Pattern -> Supports -> Loads -> TNA Relax -> TNA Solve`, with `FD Solve`
branching directly off the same `Problem`. `Pattern` currently implements
mesh input and already-split planar line input; the line worker derives
closed faces and rejects dangling or unsplit patterns. `Surface`, `Grid`,
`Triangulation`, and `Skeleton` appear in the mode list as explicit roadmap
modes and fail with an actionable error instead of generating substitute
geometry.

`Supports` takes the true structural anchors or column heads only.
Intermediate boundary vertices remain free. Supplying every naked boundary
vertex intentionally holds the complete rim, so no boundary opening can sag.
`TNA Relax` targets an exact rise/span ratio for every eligible
support-to-support opening, then stores the relaxed pattern, form graph, and
unbalanced topological force graph in one typed `Relaxed` state. `TNA Solve`
runs the horizontal and vertical solve and returns the shared `Result`
envelope, preserving reciprocal planar form/force correspondence. `Display`
draws the resolved thrust mesh and form/thrust/force/load/reaction lines from
either solver's `Result` in one place, and `Deconstruct` extracts the same
information as data: member IDs, thrust lines, `q`/`H`/`F`, force state,
support/load/reaction points and vectors, residuals, and diagnostics.

The current TNA solver accepts nodal loads along analysis Z only. It rejects
nonzero analysis-X/Y components instead of silently discarding them; use the
FD workflow for general spatial load vectors.

The displayed force density `q`, horizontal force `H`, and spatial axial force
`F` are equilibrium demands, never member capacities. Before a vertical
height/force calibration fixes the physical TNA scale, horizontally balanced
`q` and `H` are relative equilibrium quantities; `F` belongs to the lifted
spatial result. Material, section, stability, connection, and safety checks
remain separate verification work.

`Deconstruct` reads the same unified `Result` from either solver: an FD
result simply leaves the reciprocal-only streams (Thrust Mesh, Form Lines, H)
empty, and its Report states that explicitly rather than erroring.

Directional dashed load-line/pole and funicular constructions, generic AGS,
spatial/3D graphic statics, column and branch placement, Steiner relaxation,
`compas_model`, FEA, and IFC formulation remain roadmap items. A general TNA
reciprocal is a force mesh or set of cells and is not forced into the single
triangle that applies to some ordered cable or arch constructions. Installed
packages may be reported by `Backend Health`, but package detection does not
mean those Grasshopper workflows have been implemented or structurally
verified.

FD, TNA, and graphic statics will remain distinct methods sharing neutral
inputs, diagnostics, and one shared Display/Deconstruct/Export surface. They
will not be hidden behind one ambiguous solver.

The implemented RhinoVault-style authoring path groups its inspectable
operations into the spine itself: `Pattern -> Supports -> Loads -> TNA Relax
-> TNA Solve`. `TNA Relax` carries both form and topological-force graphs;
`TNA Solve` combines horizontal and vertical solving behind two optional
inputs: `Height` (blank finds the natural equilibrium height) and
`Iterations` (blank auto-converges the reciprocal diagrams). The
implemented surface and later design-by-statics roadmap are detailed in
[RhinoVault-style native TNA stages](docs/architecture/rhinovault-native-stages.md).

## Build and install

Requirements:

- Windows with Rhino 8 and Grasshopper;
- the .NET 8 SDK;
- Rhino 8's CPython interpreter;
- a Rhino Python site environment named `catenary-compas-2026` containing the
  required COMPAS packages, including `compas_fd` and `compas_tna`.

From the repository root on the `development` branch, close Rhino and run:

```powershell
& .\plugin\native_v02\Build-And-Install.ps1
```

The script builds the native `.gha`, installs it to
`%APPDATA%\Grasshopper\Libraries\Ananke_COMPAS`, copies the Python worker
sources, resolves the exact Rhino Python environment, and writes
`backend.json`. It does not launch Rhino.

Restart Rhino and Grasshopper yourself after installation. Place
`Ananke COMPAS > 90 System > Backend Health` first; `Ready = True` confirms
that the native plugin can communicate with the persistent COMPAS worker.

See [Native v0.2: install and first FD/TNA workflows](docs/native-v02-getting-started.md)
for custom environment paths, exact canvas wiring, first-result checks, and
troubleshooting.

## Python development setup

The Python contracts, adapters, and worker can also be tested independently of
Rhino. Python 3.9 is the minimum language level because Rhino 8's CPython
environment remains a primary target.

```powershell
git clone https://github.com/EJR-of-Scrutopia/COMPAS-workflow-GH_native.git
cd COMPAS-workflow-GH_native
git switch development
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[equilibrium,model,fea,ifc,dev]"
python -m pytest
```

The COMPAS extras are pinned to the environment used to establish the
workflow. Change those pins deliberately and test the complete implemented
solver matrix before publishing.

## Repository layout

```text
docs/                            architecture and workflow documentation
plugin/native_v02/               compiled C# Grasshopper plugin source
plugin/native/                   preserved script-backed v0.1 source
plugin/legacy_component_scripts/ pasteable Rhino 8 Python 3 components and the
                                 prototype WORKFLOW.md they belong to
plugin/icons/                    component icon sources
src/ananke_equilibrium/          public contracts, adapters, codec, and worker
src/tree_forest_compas/          compatibility solver namespace
tests/                           headless contract, worker, and solver tests
tests/legacy/                    solver-core tests for the compatibility namespace
pyproject.toml                   Python distribution and dependency groups
```

Generated `.gha`, `.rhp`, `.rui`, `.yak`, `bin/`, and `obj/` files are build
products and are ignored. The installer copies its build to the user's
Grasshopper Libraries folder; that installed copy is not repository source.

Further project documentation:

- [System analysis: architecture, design intent, graphic statics, and the
  COMPAS ecosystem](docs/system-analysis.md) (start here for orientation)
- [The COMPAS suite, and how it enters this plugin](docs/compas-suite-adoption.md)
  (verified package inventory, the masonry-on-formwork pipeline, adoption order)
- [Native worker architecture](docs/architecture/native-worker-v02.md)
- [RhinoVault-style native TNA stages](docs/architecture/rhinovault-native-stages.md)
- [TNA, graphic statics, and column placement](docs/architecture/tna-graphic-statics-columns.md)
- [Component taxonomy](docs/component-taxonomy.md)
- [GUID and version policy](docs/versioning-and-guids.md)
- [Development and release branches](docs/development-workflow.md)

## Design rules

- Core contracts contain no Rhino or Grasshopper objects.
- Registered topologies carry deterministic vertex and source-segment IDs for
  the exact flattened input order. Solved members carry the source IDs forward
  only after their returned edge order has been checked against the registered
  topology.
- Length and force units are explicit metadata in v0.2. Numeric conversion is
  not performed, so every input to a solve must already use one consistent
  unit system. `Pattern` offers the canonical coordinate units `mm`, `cm`,
  `m`, `in`, and `ft`; FD force density `q` must use force-unit/length-unit.
- FD consumes the registered edge network. A faced mesh may therefore feed
  FD directly; its faces are retained in the result but do not enter the
  force-density equations. TNA accepts a mesh or an already-split planar line
  pattern whose closed faces can be derived during `TNA Relax`.
- Support and load points are snapped to the nearest registered topology node
  in C# and cross the worker boundary as zero-based node IDs.
- Native v0.2 accepts explicit anchors only on `Supports` (no `Terminals` or
  `Boundary` auto-detection) and one load vector applied to every node or an
  explicit subset on `Loads`, under the fixed COMPAS `positive_tension` sign
  convention. Unsupported options produce errors instead of silently
  approximating another operation. `Supports` is explicit-only so boundary
  nodes cannot be silently converted into a continuously held rim.
- Form-finding support selections are not silently treated as FEA restraint
  degrees of freedom.
- `CarriedVerticalLoad` is design metadata, not solved axial force.
- A graphic-statics triangle is detected from equilibrium; it is never fitted
  around unrelated force polygons.
- IFC export will not turn an unverified equilibrium result into a verified
  structural model.

The boundary-opening relaxation is adapted from the Block Research Group's
[compas-RV Pattern workflow](https://github.com/BlockResearchGroup/compas-RV/blob/main/src/compas_rv/datastructures/pattern.py).
This plugin exposes sag as an exact per-opening target rather than a
minimum-sag setting. Attribution and the upstream MIT terms are recorded in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

**License: TBD.** No licence has been selected, and this repository does not
grant redistribution rights. Select and add an explicit licence before any
public package release.
