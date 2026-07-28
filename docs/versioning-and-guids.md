# Version and GUID policy

Grasshopper serialises component identity into every saved definition. A stable
GUID policy is therefore part of the public data contract, not housekeeping.

## Project identity

- Create the project in Rhino 8 Script Editor.
- Script Editor assigns the project UUID and makes it read-only.
- Commit the resulting `.rhproj`.
- Never invent, edit, or replace the UUID to make a build pass.
- A renamed product keeps its UUID when it is still the same plugin lineage.

The project UUID identifies the plugin assembly. It is distinct from every
component GUID.

## Component identity

For Script components, Rhino Script Editor uses the source Script instance's
**Instance ID** as the published Grasshopper component GUID.

- Create each source instance once.
- Record the assigned GUID under the matching key in
  `plugin/components.toml`.
- Never generate GUIDs in Python, copy a GUID between components, or reuse a
  retired GUID for different behaviour.
- Planned components may have an empty manifest GUID. A release may not.
- Treat unexpected GUID changes in a pull request as release blockers.

### Compatible changes

Edit the existing source instance in place when behaviour remains compatible,
for example:

- correcting a numerical or display bug;
- improving diagnostics;
- speeding up a solver without changing its contract;
- adding internal metadata that old downstream components can ignore.

Changing an input's order, access mode, type, required status, default
semantics, or an output's meaning can break a saved definition even if the
component name is unchanged.

### Breaking changes

When a port or semantic break is unavoidable:

1. Keep the old source Script instance.
2. Duplicate it in the source `.gh`; the duplicate receives a new Instance ID.
3. Make the breaking change only on the duplicate.
4. Give the new public component an explicit successor name/version where
   useful.
5. Mark the old component **Legacy** in Script Editor. It stays compiled but is
   hidden from ordinary search, allowing existing definitions to load.
6. Record both GUIDs and the successor relationship in the manifest.
7. Add a migration note and a saved-file compatibility test.

Do not delete the legacy source merely because it is hidden. Removing it from
the assembly breaks files that reference its GUID.

## Version lines

The Python package starts at `0.1.0.dev0`. The Rhino project starts on the
matching `0.1` line; Script Editor completes its artefact version with generated
patch/build values.

Use these repository semantics:

- **development suffix / pre-release**: unfinished integration builds;
- **patch**: compatible bug fixes and diagnostics;
- **minor**: additive contracts or components with old GUIDs retained;
- **major**: an intentionally new system contract or migration boundary.

Script Editor's generated patch/build values do not replace release planning.
Record both the repository release and full generated Rhino/Yak version in the
release notes.

## Release identity checks

Before a release:

1. `pyproject.toml`, `ananke_equilibrium.__version__`, the plugin manifest, and
   the intended Rhino project version line agree.
2. The project UUID is present and unchanged from the previous release.
3. Every released component GUID is present and unique.
4. Every manifest port matches the source component.
5. Every previous GUID is still present or has an explicitly approved
   retirement and migration.
6. Previous saved Grasshopper definitions load and solve.
7. The exact built package filename and checksum are recorded.

No public release is permitted while the repository licence remains `TBD`.
