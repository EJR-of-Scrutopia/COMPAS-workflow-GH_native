# Studio task set from the mould rework, 2026-08-28

For the sessions that own the Bench Studio at
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-UI-integration-tool
(bench/studio/app.py). The plugin's Export component now writes the full
set for a study in one go and, with Live on, PUTs it on every solve:
`/api/uploads/exports/{name}/contract`, `.../compas`, `.../tessellation`
when cells are wired, and `/api/uploads/columns/{name}-columns.json` when
the Result carries columns. Each task names the route it touches and what
the plugin already sends, so the two sides meet in the middle.

## 1. Columns namespaced per study

`upload_columns` stores into one flat `COLUMNS_DIR` and `/api/studies`
lists that folder whole. The plugin names the file `{name}-columns.json`
after the study, so today the namespace is by convention only. Store the
file under the study's slug (beside its bundle) and list `columns` per
study row in `/api/studies`, keeping the flat listing for files that
predate this.

## 2. A change channel

An open page learns nothing when Export pushes. Either add a `version`
field to `/api/studies` (a counter or the newest upload's mtime) that the
page polls every few seconds, or serve SSE from `/api/events` with one
event per stored upload naming the study and kind. The plugin needs
nothing from this; it is for the page.

## 3. A columns kind from lines plus radius

The plugin's `bench.columns/1` document carries both a prism mesh
(`vertices`, `faces`, which `upload_columns` accepts today) and the source
of that mesh: `members` as `{"from": [x,y,z], "to": [x,y,z], "force": f}`,
`forceUnit`, and `lengthUnitToMetres`. Read `members` and build the
columns in the studio's own material, so the radius is the studio's
choice rather than the plugin's `Column Radius` input; keep accepting the
mesh for older files.

## 4. Retry-After on the 409

`upload_export` answers 409 `{"run": id}` while a run for the study is
queued or running. The plugin retries after 2, 4 and 8 seconds, then
defers. Add a `Retry-After` header (seconds, from the run's expected
remaining time or a fixed 5) so the plugin can honour the studio's own
estimate; the plugin will prefer the header when present.

## 5. Upload validation tolerant of the Mould block

Every contract the plugin exports now carries a `mould` block (ground,
columns, frame) and a `forceUnit` (kN unless the document says
otherwise). Confirm that `geometry.mesh_arrays`, `geometry.support_ids`
and `geometry.member_forces_newtons` ignore the `mould` key on a
contract upload, and that `member_forces_newtons` reads `forceUnit`
rather than assuming newtons: the plugin's own labels were wrong by a
thousand until today, and the studio's may be too.

## Already done, not asked for

The `tessellation` upload kind exists. The plugin flattens Skin's
course-branched cells before upload. `lengthUnitToMetres` is on the
compas export (the other session's edit, folded into the plugin's main
on 2026-08-28).
