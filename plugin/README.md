# Grasshopper plugin

`plugin/native/Ananke.COMPAS.csproj` builds the Rhino 8 Grasshopper assembly.
The assembly publishes ten native Grasshopper component classes while retaining
the tested Python implementation for FD, TNA, diagnostics, and diagram payloads.

## Layout

- `native/` contains the `.gha` host source and repeatable local installer.
- `component_scripts/` contains the embedded Rhino Python 3 component code.
- `icons/` contains the 24 × 24 category-coloured component icons.
- `components.toml` is the component contract and stable GUID registry.
- `definitions/ananke_equilibrium_v01.gh` records the matching source component
  definition for inspection and the optional Script Editor publication route.

The `.gha` embeds all ten scripts and icons. The installer places the Python
packages beside it so each component can import the same tested core.

## Build and install

From the repository root:

```powershell
& plugin\native\Build-And-Install.ps1
```

The default destination is:

```text
%APPDATA%\Grasshopper\Libraries\Ananke_COMPAS
```

The installed payload contains:

```text
Ananke_COMPAS/
├── Ananke.COMPAS.gha
├── icons/
└── python/
    ├── ananke_equilibrium/
    └── tree_forest_compas/
```

Rhino 8 supplies the referenced RhinoCommon, Grasshopper, and RhinoCode
assemblies; those system DLLs must not be copied into this folder.

## Compatibility

The current workstation build targets .NET Framework 4.8, which matches the
installed Rhino 8.33 Grasshopper assemblies. The embedded scripts select the
existing Rhino Python environment `catenary-compas-2026`, where the required
COMPAS packages are installed.

Compiled `.gha` files remain local build artifacts and are ignored by Git.
Commit the C# source, Python source, icons, component GUIDs, and tests instead.
