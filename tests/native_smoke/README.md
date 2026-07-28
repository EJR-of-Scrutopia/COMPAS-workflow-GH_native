# Native Grasshopper constructor smoke test

This console harness loads the built GHA and Rhino 8/Grasshopper managed
dependencies into .NET without starting Rhino. It:

- discovers every concrete public `GH_Component`;
- rejects any component whose base-type chain refers to `RhinoCodePluginGH`;
- constructs every component and persistent contract parameter;
- checks unique document GUIDs, embedded 24×24 icons, and intentional
  bundle-input flattening; and
- reports component and parameter pass/fail counts.

From the repository root:

```powershell
dotnet run --project tests/native_smoke -- `
  plugin/native_v02/bin/Release/net8.0-windows/Ananke.COMPAS.gha
```

Rhino 8 is found in `C:\Program Files\Rhino 8` by default. A nonstandard
installation can be supplied with `--rhino-root <directory>` or the
`RHINO8_ROOT` environment variable.

An empty plugin, a forbidden script-backed component, a missing icon, a GUID
collision, an incorrect collection mapping, an assembly-loading problem, or
any constructor exception produces a nonzero exit code.
