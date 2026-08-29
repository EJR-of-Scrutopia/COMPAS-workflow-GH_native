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
| 1 | Path | P | text, optional | "" | A folder, or a file whose folder is used; created when missing. A Path with no extension is a folder whether or not it exists yet; a Path that is not rooted (a bare name or a relative path) is refused with a Warning and nothing is written, and so is a rooted Path whose folder has no folder of its own (a drive root). |
| 2 | Write | W | boolean, optional | false | While true, every solve writes the set to Path. Optional, so a port with no data reads false rather than refusing to collect. Write true with a blank Path is a Warning saying nothing was written, not an Error: the solve finishes and every output is set. |
| 3 | Name | N | text, optional | "" | The study name: the files are `<Name>-<kind>.json` and the studio's export name is `<Name>`; blank uses `ananke-export`. ONE path segment, checked after the blank-to-default with `ExportPlan.NameIsOneSegment`: a Name carrying `/`, `\`, `:`, `..` or a character no file name may hold is a Warning naming it, nothing is written and nothing is enqueued, and the JSON outputs still stand. Two Exports sharing a Name and a Studio overwrite each other. |
| 4 | Cells | C | curves, list, FLATTENED | none | Closed plan outlines per cutting cell, from Skin's Face Polylines. The registered flatten is re-asserted on every open, so a graft set on the port by hand is wiped when the file is reopened. |
| 5 | Courses | CO | integers, list, FLATTENED | none | Course per cell, from Skin's Face Courses; empty puts every cell in course 0. Flattened on every open, as Cells. |
| 6 | Live | L | boolean, optional | false | Push the set to the studio on every solve. Optional, as Write. Live false cancels the uploader (section 4). HELD after a load whose archived port counts did not match the registered ones: while held, Live true enqueues nothing and Uploaded reads `held: ports changed on load; set Live off then on to resume`. A solve that reads Live false clears the hold, so the next Live true is deliberate. |
| 7 | Studio | S | text | http://127.0.0.1:8600 | The studio's base URL. Blank falls back to the default, with a Warning saying so when Live is on. |
| 8 | Column Radius | R | number | 0.05 | Radius, in document units, of the prism each column member is drawn as in the columns mesh. A value that is not positive and finite falls back to 0.05 with a Warning. The default is metre-shaped and the port says so. |

Format is removed. Outputs, in order: 0 Contract JSON `CJ`, 1 COMPAS
JSON `MJ`, 2 Tessellation JSON `TJ` (empty when no cells), 3 Columns
JSON `KJ` (empty when the Result carries no columns), 4 Written `W`
(the files THIS solve wrote, one line each, latched so a one-shot
Button write survives its release solve), 5 Uploaded `U` (the most
recent upload outcome, one line per kind). GUID unchanged. The
component count stays 19; the persistent parameter count stays 12.

One Export is one study. Slot 0 is item access, so a Result tree with
more than one item makes every iteration after the first overwrite the
files the last one wrote and supersede the set it enqueued: a Warning
on the second iteration says "Export handles one Result per component;
the last one wins.", said once so a wide tree does not repeat itself
down the whole chin.

## 3. What Export produces (binding)

`ExportPlan.Kinds(bool hasCells, bool hasColumns) -> string[]` returns
`contract`, `compas`, then `tessellation` when cells are wired, then
`columns` when the block has at least one member. Pure, measured.

- contract: `ContractJson.Serialize(result)`, as today.
- compas: the worker's `export.compas` with `lengthUnitToMetres`, as
  today. The only kind that needs the worker, and so the only one that
  can fail for a reason outside this component: a worker that will not
  start, a timeout or a worker-side error leaves the COMPAS JSON output
  empty and adds a Warning naming the failure, and the rest of the set
  (the contract, the tessellation, the columns, the disk write and
  Written, none of which touch the worker) stands and is uploaded
  without it.
- tessellation: `bench.tessellation/1`, as today, from the flattened
  Cells and Courses; the same validation (negative courses refused,
  open cells warned).
- columns: `ColumnsMesh.Build(IReadOnlyList<(Point3d From, Point3d To,
  double Force)> members, double radius, int sides = 6) -> (double[][]
  Vertices, int[][] Faces)`: one closed prism per member, `sides`
  vertices at each end on a circle of `radius` perpendicular to the
  member, `sides` side quads, and each end cap as `sides - 2` triangles
  fanned from the cap's first vertex (triangles and quads only, since
  the studio's mesh reader is not known to take n-gons). `sides` is
  floored at 3 and `radius` at 1e-9, both silently: a prism needs three
  sides to be a solid and a surface to be seen, and Export refuses a
  non-positive Column Radius long before this. A member shorter than
  1e-9 is skipped, from the `members` list as well as from the prisms,
  so the nth prism and the nth member stay the same member. Serialised
  as `{"schema": "bench.columns/1", "lengthUnitToMetres": f, "forceUnit":
  u, "radius": r, "vertices": [[x,y,z]...], "faces": [[i,j,k,l]...],
  "members": [{"from": [..], "to": [..], "force": N}...]}`, which the
  studio's columns upload accepts today (`vertices` and `faces` keys) and
  the lines-plus-radius kind of section 6 can read later. `radius` is the
  clamped value the mesh was actually built at, so a studio drawing from
  `members` knows what the mesh beside it used. Forces carry the
  Result's ForceUnit as `"forceUnit"`.

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
  `columns: deferred, 409 after 3 retries (run r-…)`, `compas: refused
  400 …`), the Message shows the last outcome, and any failure is a
  Warning runtime message, never an Error: the files and outputs stand.
  The run id is read out of the 409 body with System.Text.Json and any
  body that is not that JSON falls back to the body itself, trimmed to
  120 characters.
- The uploader carries a phase beside the outcome, and the component
  reads both under ONE lock acquisition (`LiveUploader.Current`, a
  `Snapshot` of phase, text and failure verdict): reading the text and
  the verdict separately let a send land between them and print one
  set's failure with the other set's flag. The phases are NeverSent,
  Pending, Sending and Done. `Uploaded` reads `nothing sent yet` before
  the first send, `sending` while a set is waiting out the debounce or
  on the wire, and the outcome lines when a send has landed; the Warning
  is raised only for a failure that has landed.
- Live false: nothing is sent, `Uploaded` says `Live is off`, and the
  component calls `LiveUploader.Cancel()`, which drops a pending set,
  cancels a send in flight through the uploader's cancellation token,
  and CLEARS the last-sent key so that turning Live back on sends the
  same set again. The cancelled send records `<kind>: cancelled` in its
  own outcome, which is not a failure and raises no Warning, and the
  port never shows it: the only caller of `Cancel` is the Live-false
  branch, and that branch says `Live is off` instead. Clearing the key
  is protected against the send in flight by a cancel GENERATION,
  bumped and compared under the same lock, and not by the token: the
  token has to be cancelled after that lock is released, since
  cancelling a `Task.Delay` can inline the send's own continuation onto
  the caller's thread and under the lock that would deadlock, so a send
  tail taking the lock in that window would read the token as not
  cancelled and put the key back. Cancel does not dispose: it takes a
  fresh source when there was something to cancel, and that source waits
  for the next enqueue. The token is passed to `PutAsync`
  and to `Task.Delay`, and each payload is checked for disposed or
  cancelled before it starts, so a deleted component stops PUTting
  within one kind instead of running its retry schedule out.
- The uploader never touches Grasshopper objects from its thread; it
  posts its outcome into a field the next solve reads, and when an
  outcome arrives it marshals onto the UI thread with
  `Rhino.RhinoApp.InvokeOnUiThread` and asks the document for
  `ScheduleSolution(5, d => ExpireSolution(false))`, which defers to a
  solution already running and does nothing at all once the component
  has left its document. To keep that expire from re-sending forever,
  the uploader hashes the Name, the Studio and the set's payloads and
  skips a set identical to the last one sent; only a changed Result,
  Name or Studio, or Live toggled off and on, sends again. The key is
  latched after EVERY completed send, failed or not, so a refused or
  unreachable set does not re-open the expire loop on every solve; a
  cancelled send does not latch it. The skipped set's outcome text is
  `unchanged since: <the outcome that still stands>; toggle Live or
  change the Result to send again`. The skip is decided when the set is
  ENQUEUED, on the solve thread, not after the debounce: the component
  reads the uploader's state in the same solve that enqueues, so a
  repeat parked as pending would read as `sending` for a send that is
  never going to happen, and the solve an outcome asks for enqueues that
  very repeat. Deciding it at the enqueue is what makes the cycle settle
  in one solve. The key is stamped on the pending set there and carried
  with it, so the debounce never hashes the same bytes twice. A skip
  found while a DIFFERENT set is on the wire writes the unchanged text
  but leaves the phase alone: that other set really is sending, and its
  own outcome moves the phase and asks for the solve that shows it.
- Neither thread the uploader owns may throw where it stands. The whole
  body of the send runs under a catch, with the owner's callback inside
  its own, so the discarded task can neither fault nor lose an outcome;
  a caught exception becomes a `failed:` line for the kind in flight, or
  for the set when it happened between kinds. The debounce timer's
  callback is fenced the same way and returns at once when disposed.
  `LiveUploader.SetKey(string name, string studio, IReadOnlyList<(string
  Kind, string Json)> set)` is the pure hash, measured. The compas
  kind's JSON is the one thing the hash does not read: the worker's
  `compas.data.json_dumps` writes a fresh uuid4 `guid` into every
  serialisation, so a key that read those bytes could never repeat and
  the expire would send again for as long as Live was left on. Its
  presence in the set still counts, so a set that lost the compas kind
  to a worker failure and the same set with it back key differently. A
  changed Result changes the contract kind, which the hash does read.

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
  `(true, true)` is all four in that order. `NameIsOneSegment` is true
  for `study-1` and false for `..`, `.`, `a\b`, `a/b`, `a:b`, `a?b`,
  blank and whitespace, which fails a name check that only refuses a
  blank.
- `ValidateColumnsMesh`: one member of length 2 along Z at radius 0.1
  with 6 sides gives 12 vertices and 6 quads plus 8 triangles, every
  vertex within 1e-9 of radius 0.1 from the axis, end-cap vertices at
  Z 0 and 2; a zero-length member gives nothing; two members give 24
  vertices and face indices all in range. A DIAGONAL member, (0,0,0) to
  (1,1,1), has every cap vertex within 1e-9 of perpendicular to the
  member and within 1e-9 of the radius, which fails an implementation
  that draws the circle in world XY (every other case lies on an axis
  and would pass it). `ColumnsMesh.Json` of a zero-length member lists
  no members and no vertices, and `Json` at radius 0 declares the
  clamped 1e-9 the mesh was built at.
- `ValidateLiveUploader`: `RetryDelay(0..2)` is 2000, 4000, 8000 and
  `RetryDelay(3)` is null; `LiveUploader.RouteFor(kind, name, studio)`
  gives `{studio}/api/uploads/exports/{name}/contract` for the three
  export kinds and `{studio}/api/uploads/columns/{name}-columns.json`
  for columns, with a trailing slash on Studio tolerated and the name
  escaped into both (a Name of `my study#1` reaches
  `.../exports/my%20study%231/contract` and
  `.../columns/my%20study%231-columns.json`);
  `LiveUploader.DeferredDetail` reads `(run r-42)` out of
  `{"run": "r-42"}` and falls back to the body itself for a body that is
  not that JSON and for JSON carrying no run;
  `LiveUploader.Outcome(int status, int attempt)` classifies 200 to 299
  as stored, 409 as retry while `RetryDelay(attempt)` is not null and
  deferred after, anything else as refused. `SetKey` of two equal sets
  is equal; two sets differing ONLY in the compas kind's JSON are equal
  too (the loop guard of section 4); two sets differing in the contract
  kind's JSON differ, as do a set with a compas entry and the same set
  without one, the same set under a different Name, and the same set
  going to a different Studio.
- `ValidateExportWriteFolder`: `TryResolveWriteFolder` reads an
  extensionless Path as the folder itself (whether or not it exists), a
  Path with an extension as its own directory, a trailing separator as a
  folder, and refuses a Path that is not rooted (a bare name or a
  relative path) with a Warning and nothing is written.
- Export's nine inputs and six outputs pinned in `VisualiseContracts`;
  Cells and Courses pinned flattened in `FlattenedInputs` (indices 4
  and 5).
- `ValidateParameterMismatch`: beside Deconstruct's counts,
  `ParameterIdentity.Mismatch(7, 2, 9, 6)` warns and names both pairs,
  and `(9, 6, 9, 6)` says nothing. That is the load a saved Export meets
  and the state the Live hold is built on; the hold itself is not
  measured here, since reading it needs a Grasshopper archive and this
  harness never starts Rhino.
- `ValidateExportCoursesValidation` and
  `ValidateExportTessellationJsonOptions` keep passing (the methods they
  reflect on keep their names and signatures).
- No check performs network I/O; the uploader's send is not measured.

## 9. What breaks on the canvas

Format is gone, so the ports after it move up one slot. Grasshopper
stores a wire on the receiving port as the SOURCE port's instance guid
and hands a component's archived ports back BY INDEX, so nothing comes
back broken: every old wire reattaches to whatever now stands at its
index, and `ParameterIdentity.Restore` then relabels that port with its
registered name, so the canvas looks self-consistent while it carries a
different quantity. Read the table as the author does, wire by wire.

| Old slot | Old port | New port at that index | Cast | What the author gets |
| --- | --- | --- | --- | --- |
| in 1 | Format (text) | Path (text) | same type | SILENT reattach. The old Format value list, or a panel reading "contract", now feeds Path. `contract` is not rooted, so nothing is written and the Path warning names it, but only once Write reads true. |
| in 2 | Path (text) | Write (boolean) | text to boolean | Fails for any real path: a red conversion error on the port. A string that reads true, false, 1, 0, y or n converts. |
| in 3 | Write (boolean) | Name (text) | boolean to text | SILENT reattach. A Button or Toggle now names the study, so the files become `false-contract.json` and the studio's study name is `false`. |
| in 4 | Name (text) | Cells (curve) | text to curve | Fails. Red conversion error. |
| in 5 | Cells (curve) | Courses (integer) | curve to integer | Fails. Red conversion error. |
| in 6 | Courses (integer) | Live (boolean) | integer to boolean | SILENT reattach. Item access takes the FIRST course; 0 reads false, anything else reads TRUE, which is why Live is held (below). |
| out 0 | JSON (text) | Contract JSON (text) | same type | SILENT reattach. Correct content only if the file was saved on Format = contract; one saved on compas or tessellation now feeds its downstream the CONTRACT instead. |
| out 1 | Written (text) | COMPAS JSON (text) | same type | SILENT reattach. A panel, a File Path or a script that consumed the written file path now receives the whole COMPAS document. Written has moved to slot 4 and the wire has to be moved with it. |

The load-time warning fires on every saved Export, because
`ParameterIdentity.ArchivedCounts` reads 7 inputs and 2 outputs from the
archive against the 9 and 6 registered now, and `BeforeSolveInstance`
re-asserts it on every solve so the first expire cannot wipe it:

  this component's ports changed since the file was saved: 7 inputs and
  2 outputs archived, 9 and 6 registered; wires may now sit on the wrong
  port, check every one

It names the counts, not which wire went where, which is what this table
is for. Because the old Courses wire lands on Live and reads true for
any first course index but 0, a warning alone would arrive in the same
instant as an upload the author never asked for: Export therefore HOLDS
Live on the first solve after such a load, enqueues nothing, and says
`held: ports changed on load; set Live off then on to resume` on
Uploaded until Live is seen false and then true again.

Write and Live are the two ports whose slots an old archive hands
persistent chunks of the wrong Goo type, so their registered false
defaults are not expected to survive the read; both are Optional, so a
port left with no value reads false rather than going red.

Three Export components per study collapse to one.

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
