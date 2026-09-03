# Export: three documents, built on rest, and a worker that survives a scrub

Written overnight 2026-09-03/04. Binding inputs: Param's rulings (three documents; formwork
carries members, nodes and frames together; Export + Live is the wave after the slider; the CO
port goes); the measured export costs of 2026-09-03 (managed set ~28 ms a solve, the compas kind
an out-of-process round trip, cancellation KILLING the Python worker via
RecoverCancelledRequestAsync, WorkerHost.cs:911-991); and the studio session's channel entries
R-010 and R-011 with this session's REPLY beneath them, in
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS-Workflow-bench\REQUESTS-for-plugin-session.md
The reader side is THEIRS and is already flexible (their commit 89bc1b3: a contract alone
resolves as a study; they add the new suffixes themselves). Nothing here waits on them.

## 1. The set

Three kinds replace five. Files land beside the old ones; old studies keep resolving (their side).

FORM, "<study>-form.json". The contract exactly as ContractJson.Serialize writes it today, mould
block included, PLUS two top-level keys: "study" (the study name) and "thrustMesh" (the SAME
compas json string the compas document carries today at its own "thrustMesh" key, which is the
one thing their FEA reads; nothing in bench/studio parses the rest of the compas document, their
measurement). The compas kind and the contract kind stop being written.

SKIN, "<study>-skin.json". The bench.tessellation/1 sidecar as today, authored cells only, plus
"study". The tessellation kind stops being written, and the COURTESY per-face tessellation is
never built again: their bundle.py discards pattern "faces" unread (their R-010 g confirms
absence and "faces" mean the same thing to them). DefaultTessellationFor and its cache go.

FORMWORK, "<study>-formwork.json", schema "bench.formwork/1". Self-contained: "study", "units",
"lengthUnitToMetres", "forceUnit", "radius" (kept, their R-010 h: the studio draws animated
members as tubes at exactly this radius), the columns block as bench.columns/1 carries it (nodes,
members, and the tree bookkeeping), "vertexCount" and "columnNodeCount" at DOCUMENT level (their
validator reads them before any frame), and "frames": the bench.frames/1 array unchanged (time,
phase, vertices, columnNodes; boundaries 0, 30, 60, 90, 100 always present; strictly ascending).
The columns and frames kinds stop being written. PAIRING (their R-011 f, agreed in the REPLY):
time-100 columnNodes equal the columns block's own nodes IN THIS DOCUMENT; time-100 vertices
equal FORM's equilibrium vertices to 1e-9. The writer keeps both true by construction; the
harness pins both.

ROUTES: all three kinds go down the ONE exports route, PUT
/api/uploads/exports/{study}/{kind}. LiveUploader.RouteFor's columns special case dies.

## 2. The ports

The Courses (CO) input, index 2, IS REMOVED. Courses derive from the Cells tree's branch paths
and from nothing else; a flat Cells list is course 0 throughout, said in a Remark (the hand-
authored escape hatch dies with the port, deliberately). Removing input 2 slides every archived
wire up one, which is exactly the hazard the Live hold exists for: InputPortsMovedOnLoad already
detects the shift and holds Live until it is deliberately cycled. Verify that detection fires for
this removal on a saved definition and pin it; the hold message already tells the author what to
do. All other inputs keep their order.

## 3. Built on rest, never on a drag

The five-kind set is built unconditionally on every solve today (DeliveryComponents.cs:465-475,
1516-1610), which is the measured slow canvas. New contract, agreed with the studio (their Live
ask 1 and 2, accepted in the REPLY):

RULE 3.1. A SOLVE BUILDS NOTHING. SolveInstance records the inputs and pokes the debouncer.

RULE 3.2. THE BUILD RUNS ON REST: on the debounce tick (the uploader's existing half-second,
one-shot, reset by every solve), on Write being true at solve time (a write is a deliberate act
and builds synchronously on that solve), and on nothing else. When the build lands, outputs are
refreshed via the existing marshalled ExpireSolution, so J carries the fresh set one solve later.
J's port text is rewritten to say "built on rest" instead of "always live"; on a canvas that
never rests longer than the debounce, J lags by design and says so.

RULE 3.3. ONLY WHAT CHANGED IS SENT, and only what is needed is built. Each document carries its
own change key: form's key is the CONTRACT bytes (thrustMesh excluded, its uuids churn per
serialisation, the standing SetKey lesson), skin's and formwork's their own bytes. Live sends
only documents whose key moved. The thrustMesh string is produced only when a form document is
actually about to be written or sent with a moved key, never for a J-only refresh (J's form
carries "thrustMesh": null with a one-line note in that case, so J stays cheap and honest).

RULE 3.4. THE WORKER IS NEVER KILLED BY EXPORT. The thrustMesh request runs on a token
independent of Grasshopper's solution cancellation (a component-lifetime token, cancelled only
when the component is removed or the document closes). A superseded build finishes and its result
is discarded; the RecoverCancelledRequestAsync kill path is unreachable from Export. The solver
components' own use of cancellation is out of scope and untouched.

## 4. Folded queue items, all small, all in this wave

1. NameIsOneSegment tightens to refuse ".." ANYWHERE in the study name, matching the studio's
   deployed boundary (channel decision of 2026-09-03; live 400s demonstrated on "a..b").
2. The skin document gains the cheap pairing anchor: "vertexCount" and the contract's
   "topologyHash", declaration only, reader free to ignore (channel agreement, R-008/4).
3. BuildCompasJson's stale comment about the studio refusing non-metre documents is corrected
   where the code survives, deleted where it does not.
4. Every document carries "study" inside itself (their Live ask 3).

## 5. What must be checked, each proved able to fail

1. KINDS AND ORDER: exactly form, skin (cells wired), formwork (columns present); old kinds
   absent; each file named and routed as section 1 says.
2. FORM: byte-compatible with today's contract for every existing key (serialise both, compare
   after stripping the two new keys); "thrustMesh" json_loads-able shape preserved verbatim from
   the worker response.
3. FORMWORK: document-level counts; boundaries present; time-100 columnNodes equal the columns
   block; time-100 vertices equal form's equilibrium to 1e-9; radius stamped.
4. REST: a burst of N solves inside the debounce window triggers exactly ONE build (count via the
   uploader seam the harness already drives); Write builds synchronously that solve.
5. CHANGE KEYS: a formwork-only change re-sends formwork alone; a form change with identical
   formwork bytes sends form alone; an identical set sends nothing.
6. NO KILL: through the WorkerHost test seam, a build superseded mid-request leaves the SAME
   worker process serving the next request (no restart, no fresh handshake).
7. CO: the port is gone, remaining inputs bind, InputPortsMovedOnLoad holds Live on a definition
   archived with the old port count.
8. NAME GUARD: "a..b", "x..", "..y" all refused; plain names pass.
9. The atomic write discipline (temp beside destination, move over) holds for all three kinds,
   measured through ExportComponent.WriteSet as today.

## 6. Out of scope, said so nobody reinvents it

Emitting thrustMesh natively in C# (deleting the worker from export entirely): a later spike,
recorded as an option in the REPLY to R-010/3. The studio's SSE push replacing its poll: theirs.
The single-file form question: settled, three documents, closed by Param twice over.
