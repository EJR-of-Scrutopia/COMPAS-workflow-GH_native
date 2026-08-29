# Export decides its formats, and Live pushes them to the studio

Date: 2026-08-28. Sub-project 6 of 6 from the mould rework brainstorm of
2026-08-27. Branch feature/export-live off plugin main b914356; its first
commit 0767636 folds in another session's pending edit (the compas
export's `lengthUnitToMetres`). Implements section 10, fourth paragraph,
of docs/superpowers/specs/2026-08-27-res-spine-design.md, which is
binding, corrected by what the studio's app.py actually does today
(section 7).

## 1. Why

Export asked the author which of three formats to write, so a definition
needed three Export components to keep a study whole, and the studio
learned nothing until a file was copied by hand. The Result already
knows what it carries: every Result can be a contract and a COMPAS
document, a Result with cells wired can be a tessellation sidecar, and a
Result whose Mould block carries columns can be a columns mesh. Export
now writes what the Result can be, and Live sends it.

## 2. Ports (binding)

Inputs, in order:

| Slot | Name | Nick | Type | Default | Meaning |
| --- | --- | --- | --- | --- | --- |
| 0 | Result | RES | ResultParam item | required | Solved FD or TNA Result. |
| 1 | Path | P | text, optional | "" | A folder, or a file whose folder is used; created when missing. |
| 2 | Write | W | boolean | false | While true, every solve writes the set to Path. |
| 3 | Name | N | text, optional | "" | The study name: the files are `<Name>-<kind>.json` and the studio's export name is `<Name>`; blank uses `ananke-export`. |
| 4 | Cells | C | curves, list, FLATTENED | none | Closed plan outlines per cutting cell, from Skin's Face Polylines. |
| 5 | Courses | CO | integers, list, FLATTENED | none | Course per cell, from Skin's Face Courses; empty puts every cell in course 0. |
| 6 | Live | L | boolean | false | Push the set to the studio on every solve. |
| 7 | Studio | S | text | http://127.0.0.1:8600 | The studio's base URL. |
| 8 | Column Radius | R | number | 0.05 | Radius, in document units, of the prism each column member is drawn as in the columns mesh. |

Format is removed. Outputs, in order: 0 Contract JSON `CJ`, 1 COMPAS
JSON `MJ`, 2 Tessellation JSON `TJ` (empty when no cells), 3 Columns
JSON `KJ` (empty when the Result carries no columns), 4 Written `W`
(the most recent files written, one line each), 5 Uploaded `U` (the
most recent upload outcome, one line per kind). GUID unchanged. The
component count stays 19; the persistent parameter count stays 12.

## 3. What Export produces (binding)

`ExportPlan.Kinds(bool hasCells, bool hasColumns) -> string[]` returns
`contract`, `compas`, then `tessellation` when cells are wired, then
`columns` when the block has at least one member. Pure, measured.

- contract: `ContractJson.Serialize(result)`, as today.
- compas: the worker's `export.compas` with `lengthUnitToMetres`, as
  today.
- tessellation: `bench.tessellation/1`, as today, from the flattened
  Cells and Courses; the same validation (negative courses refused,
  open cells warned).
- columns: `ColumnsMesh.Build(IReadOnlyList<(Point3d From, Point3d To,
  double Force)> members, double radius, int sides = 6) -> (double[][]
  Vertices, int[][] Faces)`: one closed prism per member, `sides`
  vertices at each end on a circle of `radius` perpendicular to the
  member, `sides` side quads, and each end cap as `sides - 2` triangles
  fanned from the cap's first vertex (triangles and quads only, since
  the studio's mesh reader is not known to take n-gons); a member
  shorter than 1e-9 is skipped. Serialised as `{"schema": "bench.columns/1",
  "lengthUnitToMetres": f, "vertices": [[x,y,z]...], "faces": [[i,j,k,l]...],
  "members": [{"from": [..], "to": [..], "force": N}...]}`, which the
  studio's columns upload accepts today (`vertices` and `faces` keys) and
  the lines-plus-radius kind of section 6 can read later. Forces carry
  the Result's ForceUnit as `"forceUnit"`.

Write: with Write true and a Path, every kind in the plan is written to
`<folder>/<Name>-<kind>.json`; `Written` lists them. The existing
one-shot Button behaviour (latch the last write) stays.

## 4. Live (binding)

- When Live is true, each solve's post phase enqueues the plan's
  payloads with the Name and Studio URL on a per-component uploader.
- Debounce: the uploader waits `DebounceMilliseconds = 500` after the
  last enqueue before sending, replacing any pending set, so a slider
  scrub sends only the final state.
- Sending runs on a thread-pool task with one shared static
  `HttpClient` (timeout 30 s). Order: contract, compas, tessellation,
  columns. Routes: `PUT {Studio}/api/uploads/exports/{Name}/{kind}` for
  the first three, `PUT {Studio}/api/uploads/columns/{Name}-columns.json`
  for the columns mesh. Body: the JSON, `application/json`.
- 409: the studio answers 409 `{"run": id}` while a run for that study is
  queued or running. `LiveUploader.RetryDelay(int attempt) -> int?`
  returns 2000, 4000, 8000 ms for attempts 0, 1, 2 and null after, pure
  and measured; the send waits and retries; after the third failure the
  kind is reported as deferred.
- Outcome: `Uploaded` carries one line per kind (`contract: stored`,
  `columns: 409 after 3 retries (run r-…)`, `compas: refused 400 …`),
  the Message shows the last outcome, and any failure is a Warning
  runtime message, never an Error: the files and outputs stand.
- Live false: nothing is sent, the uploader is idle, and Uploaded says
  so.
- The uploader never touches Grasshopper objects from its thread; it
  posts its outcome into a field the next solve reads, and calls
  `ExpireSolution` on the UI thread through `Rhino.RhinoApp.InvokeOnUiThread`
  when an outcome arrives, so the component shows it. To keep that
  expire from re-sending forever, the uploader hashes each set's
  payloads and skips a set identical to the last one sent (the outcome
  text is kept); only a changed Result, Name or Studio sends again.
  `LiveUploader.SetKey(IReadOnlyList<(string Kind, string Json)>)`
  is the pure hash, measured.

## 5. Files (binding)

- `plugin/native_v02/Components/DeliveryComponents.cs`: Export rewritten
  as above (the tessellation code, the compas worker call, the path
  resolution and the unit factor stay); `ExportPlan` and `ColumnsMesh`
  as internal static classes in a new
  `plugin/native_v02/Components/ExportPayloads.cs`; `LiveUploader` in a
  new `plugin/native_v02/Components/LiveUploader.cs`.
- `tests/native_smoke/Program.cs`: section 8.
- `docs/component-taxonomy.md`: the Export row.
- `docs/studio-tasks-2026-08-28.md`: section 6, for the studio sessions.

## 6. The studio task set

Written for the sessions that own
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-UI-integration-tool,
as docs/studio-tasks-2026-08-28.md in this repo, each task with the
route it touches and what the plugin already sends:

1. Columns namespaced per study: `/api/uploads/columns/{filename}`
   stores into one flat `COLUMNS_DIR`; store under the study slug and
   list them per study in `/api/studies`.
2. A change channel: `/api/studies` gains a `version` (or the app
   gains SSE) so an open page reloads after a Live push.
3. A columns kind from lines plus radius: read the `members` list and
   `lengthUnitToMetres` from `bench.columns/1` instead of the prism mesh.
4. `Retry-After` on the 409 from `upload_export`, in seconds, so the
   plugin's retry can honour the studio's estimate.
5. Upload validation tolerant of the Mould block: confirm
   `geometry.mesh_arrays`, `support_ids` and `member_forces_newtons`
   ignore a `mould` key on a contract upload, and that
   `member_forces_newtons` reads the contract's `forceUnit` (kN by
   default) rather than assuming newtons.

Already done and not asked for: the tessellation upload kind (present);
the Export-side flatten (section 2).

## 7. Corrections to the spine spec's studio assumptions

The spine spec assumed no tessellation upload kind and no 409 semantics
beyond "retry". The studio has the kind, and 409 means a run in flight
for that study with the run id in the body; everything else in section
10 paragraph 4 stands.

## 8. Testing (binding)

- `ValidateExportPlan`: `Kinds(false, false)` is `contract, compas`;
  `(true, false)` adds `tessellation`; `(false, true)` adds `columns`;
  `(true, true)` is all four in that order.
- `ValidateColumnsMesh`: one member of length 2 along Z at radius 0.1
  with 6 sides gives 12 vertices and 6 quads plus 8 triangles, every
  vertex within 1e-9 of radius 0.1 from the axis, end-cap vertices at
  Z 0 and 2; a zero-length member gives nothing; two members give 24
  vertices and face indices all in range.
- `ValidateLiveUploader`: `RetryDelay(0..2)` is 2000, 4000, 8000 and
  `RetryDelay(3)` is null; `LiveUploader.RouteFor(kind, name, studio)`
  gives `{studio}/api/uploads/exports/{name}/contract` for the three
  export kinds and `{studio}/api/uploads/columns/{name}-columns.json`
  for columns, with a trailing slash on Studio tolerated;
  `LiveUploader.Outcome(int status, int attempt)` classifies 200 to 299
  as stored, 409 as retry while `RetryDelay(attempt)` is not null and
  deferred after, anything else as refused. `SetKey` of two equal sets is equal and of two sets
  differing in one byte differs.
- Export's nine inputs and six outputs pinned in `VisualiseContracts`;
  Cells and Courses pinned flattened in `FlattenedInputs` (indices 4
  and 5).
- `ValidateExportCoursesValidation` and
  `ValidateExportTessellationJsonOptions` keep passing (the methods they
  reflect on keep their names and signatures).
- No check performs network I/O; the uploader's send is not measured.

## 9. What breaks on the canvas

Export's Format input is gone, so Path, Write, Name, Cells and Courses
move up one slot and the load-time port warning fires on every saved
Export; wires must be checked once. Old JSON output wires land on
Contract JSON, the same content for a contract-format export. Three
Export components per study collapse to one.

## 10. Out of scope

The studio's own changes (section 6 is a task set, not work here). Any
change to the worker. Uploading frames or the Result's diagnostics.

## 11. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Every measured check runs in the
smoke harness without launching Rhino and without network access. Check
for OneDrive name-clash files before every build and commit.
