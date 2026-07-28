# Rhino 8 Script Editor workflow

Rhino Script Editor is the authoritative tool for creating the project and
component identities. The repository deliberately does not contain a fabricated
`.rhproj` file or placeholder UUID.

## Prerequisites

- Rhino 8 with Grasshopper and Python 3 scripting.
- Rhino 8.11 or later for the documented `rhinocode` command-line workflow.
- A checkout of this repository on the `development` branch.
- The COMPAS packages required by the component being exercised.
- A reviewed author identity. The project licence is currently `TBD`, so public
  distribution is not yet authorised.

For editable Python development outside the embedded plugin, run:

```powershell
python -m pip install -e ".[equilibrium,model,fea,ifc,dev]"
```

The optional groups are intentionally separate. A user working only on
registration and display should not have to import FEA or IFC packages.

## Create the project once

1. Run `ScriptEditor` in Rhino.
2. Choose **File > Create Project** and save the result as
   `plugin/AnankeEquilibrium.rhproj`.
3. Set the project name and Grasshopper category to **Ananke Equilibrium**.
4. Keep the Script Editor-assigned project UUID unchanged.
5. Enter the actual author; Script Editor requires an author to build.
6. Start on the `0.1` release line and mark development packages as
   pre-release.
7. Do not select or claim a licence until the repository owner makes that
   decision. Do not push the package to the public Yak server while it remains
   `TBD`.
8. Save and commit the `.rhproj` after reviewing its paths and metadata.

Script Editor completes the project version with generated patch/build values.
Record the exact generated artefact version in release notes.

## Add code and source components

1. Add `src/ananke_equilibrium` under the project's **Libraries** collection
   as a Python 3 library.
2. Add `src/tree_forest_compas` as a second Python 3 library. The v0.1 FD and
   TNA adapters currently use its tested solver backends; it remains required
   until those backends have moved into `ananke_equilibrium`.
3. Create `plugin/definitions/ananke_equilibrium_v01.gh`.
4. Place one source Script component for each v0.1 entry in
   `plugin/components.toml`.
5. Give every input the required/optional setting, item/list/tree access, and
   type hint specified by the component contract.
6. Give every output the intended preview setting.
7. Add the `.gh` definition through the project's **Components** collection.
8. Configure component name, nickname, description, subcategory, exposure,
   and icon in the project editor.

For a definition without contextual ports, Script Editor publishes each source
Script instance as its own Grasshopper component. Required/access/type-hint
settings and output preview settings are inherited from that source instance.

The source Script component's **Instance ID** becomes the published component
GUID. After adding the definition, copy each ID to `plugin/components.toml` and
review the diff. See `versioning-and-guids.md` before duplicating or replacing
any source instance.

## Local development loop

1. Work in a feature branch based on `development`.
2. Edit Python implementation and tests in the repository.
3. Open the `.rhproj` and source `.gh` definition in Rhino.
4. Exercise each adapter with minimal, invalid, and representative tree/arch
   networks.
5. Confirm the `SolvedCase` is reused by validation and preview rather than
   recomputed.
6. Confirm form-edge IDs and reciprocal force-edge IDs survive from solve to
   drawing.
7. Save the `.gh` and `.rhproj` sources; do not commit compiled artefacts.

## Build

From Script Editor, open the project and select **File > Publish Project**.
Choose the minimum Rhino 8 build target and a build path outside the source
folders, then select **Build Package**.

Rhino 8.11 and newer also ship `rhinocode`. On Windows, add
`%PROGRAMFILES%\Rhino 8\System` to `PATH`, open a new terminal, and verify:

```powershell
rhinocode -V
rhinocode project build plugin\AnankeEquilibrium.rhproj --buildtarget 8.* --buildpath build
```

The project build itself does not require a running Rhino instance. If flags
differ in the installed Rhino service release, use:

```powershell
rhinocode project --help
```

The selected build directory can contain a Grasshopper `.gha`, a Yak package,
and—if the project defines Rhino commands or UI—a `.rhp` and `.rui`. Script
Editor also generates a .NET solution for further customisation. Generated
outputs are intentionally ignored by Git.

## Smoke-test checklist

- Load the built plugin in a clean Rhino/Grasshopper profile.
- Confirm there is one **Ananke Equilibrium** tab with the expected panels.
- Confirm every manifest component appears once with the expected ports.
- Open a saved definition from the previous release and check that no
  components are missing or replaced.
- Run line, polyline, and mesh-derived registration examples.
- Run at least one FD case and one faced TNA case.
- Check validation residuals, reactions, reciprocal correspondence, and
  force-polygon closure.
- Toggle diagram styles and origins; numerical results must not change.
- Exercise missing-package and invalid-topology paths; they should report
  actionable status rather than fail during component import.

## Package publication

Do not publish while author ownership, licence, GUIDs, or compatibility tests
are unresolved. Once approved:

1. Build a pre-release package.
2. Push it to the Yak test server and install it in a clean environment.
3. Repeat the smoke tests.
4. Only then push the reviewed version to the production package server.

Published Yak versions cannot be overwritten or deleted. A bad version can be
yanked (unlisted), so every retry needs a new version.

## Official references

- [Creating Rhino/Grasshopper Script Plugins](https://developer.rhino3d.com/guides/scripting/projects-create/)
- [Publishing Rhino/Grasshopper Script Plugins](https://developer.rhino3d.com/guides/scripting/projects-publish/)
- [RhinoCode Command Line Interface](https://developer.rhino3d.com/en/guides/scripting/advanced-cli/)
- [Pushing a Package to the Server](https://developer.rhino3d.com/en/guides/yak/pushing-a-package-to-the-server/)
