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

The native v0.2 vertical slice contains nine components:

| Grasshopper subcategory | Component | Purpose |
| --- | --- | --- |
| `01 Model` | `Network` | Flatten and weld lines, polylines, or meshes into one topology. |
| `01 Model` | `Support Set` | Bind form-finding supports to that topology. |
| `01 Model` | `Load Case` | Bind a named nodal load case to that topology. |
| `01 Model` | `Equilibrium Problem` | Validate and bundle topology, supports, and loads. |
| `02 Form Finding` | `FD Settings` | Bundle scalar or member-aligned force densities. |
| `02 Form Finding` | `FD Solve` | Run whole-network COMPAS force-density form finding. |
| `05 Visualisation` | `Equilibrium Preview` | Draw signed member forces, loads, reactions, and residuals. |
| `90 Query` | `Result Breakdown` | Extract aligned geometry, forces, source IDs, vectors, and diagnostics. |
| `90 Query` | `Backend Health` | Check the Python worker, packages, and protocol. |

The implemented solver path is:

```text
Geometry --> Network --------+--> Support Set --+
             |               |                  |
             +---------------+--> Load Case ----+--> Equilibrium Problem
                                                        |
Force densities --> FD Settings ------------------------+--> FD Solve
                                                                  |
                                           +----------------------+
                                           |
                                           +--> Equilibrium Preview
                                           +--> Result Breakdown
```

FD currently works end to end. Native TNA solving, reciprocal 2D and 3D
graphic statics, branch placement and Steiner relaxation, `compas_model`,
FEA, and IFC formulation are roadmap items. Installed packages may be reported
by `Backend Health`, but package detection does not mean those Grasshopper
workflows have been implemented or structurally verified.

FD, TNA, and graphic statics will remain distinct methods sharing neutral
inputs, diagnostics, and visualisation contracts. They will not be hidden
behind one ambiguous solver.

## Build and install

Requirements:

- Windows with Rhino 8 and Grasshopper;
- the .NET 8 SDK;
- Rhino 8's CPython interpreter;
- a Rhino Python site environment named `catenary-compas-2026` containing the
  required COMPAS packages, including `compas_fd`.

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

See [Native v0.2: install and first FD workflow](docs/native-v02-getting-started.md)
for custom environment paths, the exact canvas wiring, first-result checks,
and troubleshooting.

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
  unit system.
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
