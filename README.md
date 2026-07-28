# Ananke Equilibrium

Ananke Equilibrium is a bundle-first COMPAS workflow for form finding,
graphic statics, structural handoff, and Rhino 8 Grasshopper components.

The repository is currently a **pre-alpha plugin scaffold**. The public package
namespace is `ananke_equilibrium`; `tree_forest_compas` remains available as a
compatibility namespace while its tested solvers are adapted to the new
contracts.

## Intended workflow

```text
Rhino geometry
    |
    v
TopologyBundle -> LoadCase
    |                |
    +-----+----------+
          |
          +-- FD  ------> SolvedCase --+
          +-- TNA ------> SolvedCase --+--> Validate
          +-- AGS ------> GraphicCase -+
                                      |
                                      +--> Preview / graphic statics
                                      +--> COMPAS Model
                                      +--> COMPAS FEA
                                      +--> reviewed IFC package
```

FD, TNA, and AGS remain separate analysis methods. They share neutral inputs,
diagnostics, and presentation contracts; the plugin does not hide them behind
one ambiguous solver.

## Initial v0.1 component slice

The first Script Editor project targets:

- `Network`: register raw geometry as a typed `TopologyBundle`;
- `Support Set`: collect solver-neutral form-finding supports;
- `Load Case`: construct named nodal loads;
- `FD Settings`: bundle member force densities;
- `TNA Control`: bundle crown-height/force-scale and iteration controls;
- `FD Solve`: solve graph/cable/tree equilibrium;
- `TNA Solve`: solve a faced compression pattern;
- `Validate`: apply explicit acceptance tolerances;
- `Diagram Style`: collect display settings without changing analysis;
- `Preview Payload`: create typed form/force preview data.

The full roadmap also includes branch placement, Steiner relaxation, global
graphic statics, structural definition, COMPAS FEA, and IFC coordination.
See [the component taxonomy](docs/component-taxonomy.md) and the
[machine-readable component manifest](plugin/components.toml).

## Local Python setup

Python 3.9 is the minimum supported language level because Rhino 8's CPython
environment is a primary target.

```powershell
git clone https://github.com/EJR-of-Scrutopia/COMPAS-workflow-GH_native.git
cd COMPAS-workflow-GH_native
git switch development
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[equilibrium,model,fea,ifc,dev]"
python -m pytest
```

The COMPAS extras are pinned to the Rhino environment used to establish the
workflow. Change those pins deliberately and test the complete solver matrix
before publishing.

## Rhino 8 plugin development

The Grasshopper plugin is built from a Rhino Script Editor project rather than
from a hand-authored `.gha` project:

1. create the `.rhproj` in Rhino 8 Script Editor;
2. add the Python package as a project language library;
3. add source `.gh` definitions containing the publishing Script components;
4. build in Script Editor or with `rhinocode project build`;
5. inspect the generated `.gha` and `.yak` before publishing.

Do not hand-invent the project UUID or component GUIDs. Rhino assigns the
project UUID, and each published Grasshopper component inherits the Instance ID
of its source Script component. Record both in the manifest once assigned.

Detailed instructions:

- [Rhino Script Editor build and publish workflow](docs/rhino-script-editor-workflow.md)
- [GUID and version policy](docs/versioning-and-guids.md)
- [development and release branches](docs/development-workflow.md)

## Repository layout

```text
docs/                         architecture and release documentation
plugin/                       Script Editor project sources and manifest
src/ananke_equilibrium/       public bundle-first API
src/tree_forest_compas/       compatibility solver namespace
tests/                        headless contracts and solver tests
pyproject.toml                Python distribution metadata and dependency groups
```

Generated `.gha`, `.rhp`, `.rui`, `.yak`, build, and Visual Studio output are
not source files and are ignored.

## Design rules

- Core contracts contain no Rhino or Grasshopper objects.
- Stable source IDs, units, analysis planes, and topology provenance travel
  with every bundle.
- Form-finding support selections are not silently treated as FEA restraint
  degrees of freedom.
- `CarriedVerticalLoad` is design metadata, not solved axial force.
- A graphic-statics triangle is detected from equilibrium; it is never fitted
  around unrelated force polygons.
- IFC export does not turn an unverified equilibrium result into a verified
  structural model.

## License and authorship

**License: TBD.** No licence has been selected, and this scaffold does not grant
redistribution rights. Select and add an explicit licence before any public
package release.

Rhino Script Editor also requires an Author record before it can build a
project. The project maintainer must enter accurate author/contact information
when creating the `.rhproj`; this repository does not invent it.
