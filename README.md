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

The native v0.2 vertical slice contains sixteen components:

| Grasshopper subcategory | Component | Purpose |
| --- | --- | --- |
| `01 Model` | `Network` | Flatten and weld lines, polylines, or meshes into one topology. |
| `01 Model` | `Support Set` | Bind form-finding supports to that topology. |
| `01 Model` | `Load Case` | Bind a named nodal load case to that topology. |
| `01 Model` | `Equilibrium Problem` | Validate and bundle topology, supports, and loads. |
| `02 Form Finding` | `FD Settings` | Bundle scalar or member-aligned force densities. |
| `02 Form Finding` | `FD Solve` | Run whole-network COMPAS force-density form finding. |
| `02 Form Finding` | `TNA Control` | Bundle crown-height/force-scale and iteration controls. |
| `02 Form Finding` | `TNA Solve` | Solve a faced thrust network and retain its reciprocal form/force state. |
| `03 Graphic Statics` | `TNA Reciprocal` | Construct one linked, renderer-neutral thrust/form/force graphic diagram from a TNA result. |
| `03 Graphic Statics` | `Graphic Diagram Display` | Draw that diagram with a preset style and expose ordinary Rhino form, thrust, force, load, and reaction lines. |
| `05 Visualisation` | `Equilibrium Preview` | Draw signed member forces, loads, reactions, and residuals. |
| `90 Query` | `TNA Geometry` | Extract the resolved thrust mesh, thrust/form edges, and generic equilibrium bridge. |
| `90 Query` | `TNA Members` | Extract one aligned table of member IDs, thrust lines, `q`, `H`, `F`, force state, and source-edge groups. |
| `90 Query` | `TNA Actions` | Extract support locations, loads, and reactions while previewing the action vectors. |
| `90 Query` | `Result Breakdown` | Legacy full deconstruction of a generic `EquilibriumResult`, primarily for FD definitions. |
| `90 Query` | `Backend Health` | Check the Python worker, packages, and protocol. |

The implemented solver paths share the same registered problem:

```text
Geometry --> Network --------+--> Support Set --+
             |               |                  |
             +---------------+--> Load Case ----+--> Equilibrium Problem

Equilibrium Problem + FD Settings --> FD Solve
                                          +--> Equilibrium Preview
                                          +--> Result Breakdown

Equilibrium Problem + TNA Control --> TNA Solve.Result
                                          |  direct thrust-edge preview
                                          +--> TNA Geometry --> thrust mesh
                                          +--> TNA Members
                                          +--> TNA Actions
                                          +--> TNA Reciprocal
                                                   |
                                                   +--> Graphic Diagram Display
                                                        form/thrust/force/actions
```

FD and the first native TNA slice now work end to end. TNA requires a
registered `Faced` topology. Its result preserves the reciprocal planar
form/force correspondence. The `TNA Solve` result previews its resolved thrust
edges directly; `TNA Geometry` additionally reconstructs the proper Rhino
thrust mesh, and `TNA Actions` provides explicitly scaled load/reaction
arrows. `TNA Reciprocal` turns the linked state into one compact
`GraphicDiagram`, and `Graphic Diagram Display` provides the explicit styled
viewport and ordinary Rhino line outputs without rerunning AGS.

The displayed force density `q`, horizontal force `H`, and spatial axial force
`F` are equilibrium demands, never member capacities. Before a vertical
height/force calibration fixes the physical TNA scale, horizontally balanced
`q` and `H` are relative equilibrium quantities; `F` belongs to the lifted
spatial result. Material, section, stability, connection, and safety checks
remain separate verification work.

`Result Breakdown` is retained for saved FD definitions and accepts the
generic `EquilibriumResult` type, not `TnaResult`. Normal TNA definitions use
the three focused TNA query components. If a legacy operation genuinely needs
the generic state, connect `TNA Geometry.Equilibrium` to `Result Breakdown`.

Directional dashed load-line/pole and funicular constructions, generic AGS,
spatial/3D graphic statics, column and branch placement, Steiner relaxation,
`compas_model`, FEA, and IFC formulation remain roadmap items. A general TNA
reciprocal is a force mesh or set of cells and is not forced into the single
triangle that applies to some ordered cable or arch constructions. Installed
packages may be reported by `Backend Health`, but package detection does not
mean those Grasshopper workflows have been implemented or structurally
verified.

FD, TNA, and graphic statics will remain distinct methods sharing neutral
inputs, diagnostics, and visualisation contracts. They will not be hidden
behind one ambiguous solver.

The current `TNA Solve` remains a useful one-shot macro. The planned
RhinoVault-style design workflow exposes its internal operations as inspectable
`Register -> Relax -> Form -> Dual -> Horizontal -> Vertical -> Reciprocal`
stages so ordinary Grasshopper operations can intervene between them. The
implemented surface and that roadmap are distinguished in
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
`Ananke COMPAS > 90 Query > Backend Health` first; `Ready = True` confirms
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
plugin/icons/                    component icon sources
src/ananke_equilibrium/          public contracts, adapters, codec, and worker
src/tree_forest_compas/          compatibility solver namespace
tests/                           headless contract, worker, and solver tests
pyproject.toml                   Python distribution and dependency groups
```

Generated `.gha`, `.rhp`, `.rui`, `.yak`, `bin/`, and `obj/` files are build
products and are ignored. The installer copies its build to the user's
Grasshopper Libraries folder; that installed copy is not repository source.

Further project documentation:

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
  unit system. `Network` offers the canonical coordinate units `mm`, `cm`,
  `m`, `in`, and `ft`; FD force density `q` must use force-unit/length-unit.
- FD consumes the registered edge network. A faced mesh may therefore feed
  FD directly; its faces are retained in the result but do not enter the
  force-density equations. TNA still requires a faced topology.
- Support and load points are snapped to the nearest registered topology node
  in C# and cross the worker boundary as zero-based node IDs.
- Native v0.2 accepts only implemented modes: `Explicit`, `Terminals`, or
  `Boundary` supports; `Point`, `Uniform Nodes`, or `Custom` loads; and the
  fixed COMPAS `positive_tension` sign convention. Unsupported options produce
  errors instead of silently approximating another operation.
- Form-finding support selections are not silently treated as FEA restraint
  degrees of freedom.
- `CarriedVerticalLoad` is design metadata, not solved axial force.
- A graphic-statics triangle is detected from equilibrium; it is never fitted
  around unrelated force polygons.
- IFC export will not turn an unverified equilibrium result into a verified
  structural model.

## License

**License: TBD.** No licence has been selected, and this repository does not
grant redistribution rights. Select and add an explicit licence before any
public package release.
