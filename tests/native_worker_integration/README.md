# Native worker integration harness

This console harness starts the configured persistent Python worker through the
native `WorkerHost`, solves a three-node/two-member force-density cable, decodes
the result through the plug-in's native result codec, validates equilibrium
and resolved support provenance, then requests a graceful shutdown. It also
uses a deterministic test worker to verify concurrent-cancellation recovery
and rejection of an incompatible worker schema. It does not launch Rhino.

```powershell
dotnet build plugin/native_v02/Ananke.COMPAS.Native.csproj -c Release -t:Rebuild
dotnet run --project tests/native_worker_integration -c Release -- `
  "$env:APPDATA\Grasshopper\Libraries\Ananke_COMPAS\backend.json"
```

The harness references the already built `.gha`; it does not rebuild the
plugin with a different target extension or mutate the plugin output folder.
