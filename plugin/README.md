# Rhino plugin source

This directory is the publication boundary for the Rhino 8 Grasshopper
components. The computational implementation remains in `src/`; the Rhino
Script Editor project references that implementation and publishes compiled
plugin artefacts.

## Files that belong here

- `components.toml` is the repository's component contract and GUID registry.
- `component_scripts/` contains the Python source for the ten v0.1 Script
  components. Copy these into matching Rhino 8 Python components before adding
  the source definition to the Script Editor project.
- `AnankeEquilibrium.rhproj` will be created by Rhino Script Editor and
  committed after its project metadata has been reviewed.
- `definitions/ananke_equilibrium_v01.gh` will contain the source Script
  components added to the project.
- Optional icons and other shared resources should live in subdirectories of
  `plugin/` and be added to the Script Editor project as shared resources.

Do not hand-author an `.rhproj`, a project UUID, or component GUIDs. Rhino
Script Editor assigns these identities. Generated `.gha`, `.rhp`, `.rui`, and
`.yak` files belong in a build directory and are ignored by Git.

## First project setup

1. In Rhino 8, run `ScriptEditor`.
2. Select **File > Create Project** and choose the Grasshopper project type.
3. Use `Ananke Equilibrium` for the project name and category, then save the
   project as `plugin/AnankeEquilibrium.rhproj`.
4. Enter the actual author identity. Keep the licence field as `TBD` until a
   licence has been explicitly selected; do not publish publicly before then.
5. Add `src/ananke_equilibrium` as a Python library. Add
   `src/tree_forest_compas` only where a compatibility component still imports
   that namespace.
6. Create the ten source Python components listed in `components.toml`, copy in
   their matching scripts from `component_scripts/`, and save them together as
   `definitions/ananke_equilibrium_v01.gh`.
7. Add `definitions/ananke_equilibrium_v01.gh` to the project.
8. Copy the assigned project UUID and each source Script component's
   **Instance ID** into `components.toml`.

`components.toml` is not a Yak `manifest.yml`. Script Editor produces the Yak
package metadata as part of its own build/publish process.

## Release gate

Before building a distributable plugin:

- every released component has a unique, non-empty GUID in
  `components.toml`;
- the source component names, ports, access modes, type hints, and optionality
  match the manifest;
- saved Grasshopper files made with the preceding release still open;
- the Python and Rhino project versions describe the same release line;
- author and licence metadata have been deliberately approved.

See `docs/rhino-script-editor-workflow.md` and
`docs/versioning-and-guids.md` for the complete policy.
