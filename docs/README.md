# Documentation

Two surfaces share this repository: the Grasshopper plugin (the Workflow)
and the VS Code side (the Bench). The root README tells the end-to-end
story; these documents go deeper.

## The Bench

- [The Bench](BENCH.md) is the guide to the VS Code side: the three
  environments and why they exist, the `ananke` terminal tool, the demos,
  the structural verification strand, and where results land.
- The [demo runbook](../bench/demo/README.md) documents every clickable demo.

## The Workflow

- [Component taxonomy](component-taxonomy.md) defines the stable Grasshopper
  boundary and the staged component roadmap.
- [Native v0.2 getting started](native-v02-getting-started.md) covers
  installation and the current FD, TNA, query, and graphic-display wiring.
- [RhinoVault-style native TNA stages](architecture/rhinovault-native-stages.md)
  documents the implemented `TNA Pattern -> TNA Supports ->
  TNA Relax + Boundaries -> TNA Equilibrium` authoring workflow and its
  retained one-shot compatibility path.
- [TNA, graphic statics, and column placement](architecture/tna-graphic-statics-columns.md)
  defines the current linked diagram contract and later force-flow, directional
  drawing, and column/branch design layers.
- [Rhino Script Editor workflow](rhino-script-editor-workflow.md) covers
  project creation, local builds, smoke testing, and publication preparation.
- [Version and GUID policy](versioning-and-guids.md) protects saved
  Grasshopper definitions from accidental identity or port changes.
- [Development workflow](development-workflow.md) defines branches, review
  gates, and release preparation.

The machine-readable component contract is
[`plugin/components.toml`](../plugin/components.toml).
