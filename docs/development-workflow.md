# Development workflow

The repository uses `development` as the integration branch and `main` as the
reviewed release history.

## Branches

| Branch | Purpose |
| --- | --- |
| `main` | Tagged, releasable states only. |
| `development` | Integrated work for the next release. |
| `feature/<topic>` | One bounded component, contract, solver, visualisation, or documentation change. |
| `fix/<topic>` | A compatible defect fix based on `development`. |
| `release/<version>` | Short-lived release hardening; no new features. |
| `hotfix/<topic>` | Urgent compatible fix based on `main`, merged back to both `main` and `development`. |

Create feature and fix branches from `development`. Merge them back through a
reviewed pull request. Do not develop directly on `main`.

## Change sequence

1. Pull `development` and create a bounded branch.
2. Identify affected typed contracts and component manifest entries before
   changing Grasshopper ports.
3. Implement numerical/core logic without Rhino imports.
4. Implement Rhino conversion only in the Grasshopper adapter layer.
5. Add or update unit, contract, and representative network tests.
6. Update docs and `plugin/components.toml` in the same change.
7. Exercise the source components in Rhino when Grasshopper behaviour changes.
8. Run the Python checks and inspect the complete diff.
9. Open a pull request against `development`.

Build products (`.gha`, `.rhp`, `.rui`, `.yak`, generated solutions, `bin/`,
and `obj/`) are not source and must not be committed. The `.rhproj`, source
`.gh` definitions, icons, and shared resources are source and should be
committed.

## Pull-request gates

- The change has one clear purpose.
- Optional COMPAS dependencies fail locally with an actionable message, not at
  package import time.
- Contract objects remain serialisable and free of RhinoCommon types.
- Registration preserves source-to-topology mapping and diagnoses disconnected
  or invalid input.
- Solver results include provenance, units, sign convention, residuals, and
  reactions.
- Graphic-statics changes preserve form/force edge correspondence and report
  closure rather than drawing an unverified polygon.
- Component ports match `plugin/components.toml`.
- Existing source Instance IDs did not change accidentally.
- Breaking component changes retain the old instance as Legacy and document the
  new GUID.
- Tests and a clean Rhino smoke test pass in proportion to the change.

## Release preparation

1. Create `release/<version>` from `development`.
2. Freeze component ports and GUIDs.
3. Set package and manifest versions for the intended release.
4. Review `.rhproj` author, project UUID, target, pre-release flag, and licence.
5. Run the full Python suite and Rhino smoke-test matrix.
6. Build with Script Editor or `rhinocode` into an ignored build directory.
7. Test the generated Yak package on the test server in a clean environment.
8. Record the generated full version, artefact names, and checksums.
9. Merge the release branch to `main`, tag the repository, and merge it back to
   `development`.

Until an explicit licence is selected, stop after internal build/testing and do
not publish the package publicly.

## Hotfixes

Create `hotfix/<topic>` from `main`, retain all public GUIDs and compatible
ports, validate the smallest possible change, merge to `main`, tag a patch
release, and merge the same commit back to `development`.
