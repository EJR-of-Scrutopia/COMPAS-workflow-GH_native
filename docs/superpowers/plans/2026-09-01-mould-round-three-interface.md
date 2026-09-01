# Round three: the interface document

The three plan files are internally coherent. This file holds only what crosses
between them, because material that crosses belongs to no single file and that
is how it stops being anyone's job.

Read this whole. Read the plan files by task. The final whole-branch review
reads THIS plus the three files' task headings, never the three files entire; if
that review ever needs all three in full at once, this document has failed and
should be fixed rather than worked around.

**Rule: anything cross-cutting is written here at the moment it is discovered,
not at the end of the branch it was found in. Otherwise it lands in whichever
plan file was open and disappears.**

## The three files

| File | Tasks | Lines | Engine |
|---|---|---|---|
| `2026-09-01-mould-round-three-1-columns.md` | 1 to 11 | 4,580 | `ColumnPlacement.cs`, `MouldComponents.cs`, `ColumnsComponent.cs` |
| `2026-09-01-mould-round-three-2-skin.md` | 12 to 32 | 8,277 | `SkinPatterns.cs`, `SkinComponents.cs`, `DeliveryComponents.cs` |
| `2026-09-01-mould-round-three-3-readers.md` | 33 to 47 | 4,220 | `VisualiseComponents.cs`, `FrameComponents.cs`, `DiagnoseComponents.cs`, `DeliveryComponents.cs` |

Forty-seven tasks. Each file repeats the header and the Global Constraints so it
stands alone.

Specs, which govern wherever a plan file disagrees with one:

- `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-columns-priority-design.md`
- `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-skin-buildability-design.md`
- `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-readers-merge-design.md`

## Ordering

Phases one and two touch disjoint files and neither depends on the other. The
only rule between them is that they are NOT INTERLEAVED: finish one, leave the
harness green, start the next.

Phase three must come after both. It retires two GUIDs, deletes a file, and
changes port names and counts on components the first two phases hand geometry
to. `ParameterIdentity.Mismatch` compares archived port NAMES as well as counts,
so a readers merge landed early would make every intermediate build of the other
two phases warn on Param's saved definitions about ports that are about to move
again.

## Files two phases both touch

These are the only places where one plan file's work can be undone by another's.
An implementer sees one task and cannot know this, so it is named here and must
be carried into the dispatch for every task below.

**`DeliveryComponents.cs` is touched by phase TWO and phase THREE.**
Phase two reorders Export's INPUTS to Param's order (Res, C, Co, Radius, Name,
Path, studio URL, Live, Write). Phase three retires Export's Status TEXT while
keeping the port's slot, type, name and nickname, which is what makes that
migration silent. The two are compatible only because phase three deliberately
does not move the port. **If phase two's reorder changes Status's index, phase
three's silent migration breaks.** Whoever executes phase two's Export task must
leave the OUTPUT side alone entirely.

**`MouldComponents.cs` is touched by phase ONE and phase THREE.**
Phase one adds a per-node load total beside `MouldGeometry.BarLoads` and changes
`Place`'s signature. Phase three folds `FrameGeometry` out of this file and into
`VisualiseComponents.cs`. Phase three therefore MOVES code phase one has just
edited; it must move the post-phase-one version, not a remembered one.

**The harness `tests\native_smoke\Program.cs` is touched by all three.**
Every phase adds checks and every phase must leave it green. Port-name pins are
the collision point: phase three's merge changes pins phases one and two wrote.
Phase three owns updating them and must not simply delete a failing pin.

## Contracts that cross

- **The `native_smoke` harness is green at the end of every task.** This is the
  one shared gate. A task that leaves it red is not done.
- **`ResultDto` and its `Mould` block are not reshaped by this round.** All three
  phases read it; none rewrites it.
- **Diagnostics carried INSIDE a Result are untouched.** They travel to Export
  and the studio. Only the diagnostics TEXT PORTS are retired, and only in phase
  three. Do not conflate the two.
- **Forces are kN.** Every conversion through `MonitorMath.ToNewtons`, in all
  three phases.

## The four installs, and only these

No other task installs anything. Each runs with RHINO CLOSED and each is
followed by telling Param to restart Rhino, because an open session keeps the old
`.gha` and the old worker.

1. **Task 11**, after phase one, run by the CONTROLLER rather than by the
   implementer, after the columns whole-branch review, so the installed build is
   the reviewed one.
2. **Task 32 step 6**, after phase two, because the skin wave writes a walk list
   and Param cannot walk it without an installed plugin.
3. **Task 44 step 1**, mid phase three. Not a delivery: Task 44 is a manual
   measurement in Rhino whose answer sets the message level in Tasks 45 and 46.
4. **Task 47 step 5**, the final hand-over, carrying the merged reader, the two
   retired GUIDs and the fifteen ports.

## What needs Param, and what does not

**Nothing here stops work.** Every task is written to its spec's stated default
and names where the alternative would land. All twelve open questions can be
answered after the branch is built without unpicking anything.

**Two tasks need Param at a keyboard, and both have a default.**

- **Task 28 step 5** asks him to run `scripts/rhino_skin_surface.py` once in
  Rhino. Until he does, Task 29 is written to rule 5.2 as it stands.
- **Task 44** is a manual check in Rhino deciding the message level in Tasks 45
  and 46. An unattended run takes the fallback, WARNING level, which costs a
  yellow balloon on a successful import and a successful push.

The twelve open questions live in full at the end of
`2026-09-01-mould-round-three-3-readers.md`. The three worth knowing before you
start, because they touch more than one phase:

- **Anchor Lines, chord or polyline (Task 35).** Built as the POLYLINE. The chord
  alternative is written out inside Task 35, so taking it later is an edit rather
  than a redesign. Put it to Param at review, not before.
- **Skin's third output (Task 30).** Built with TWO outputs, Cells and Surface,
  which is literally what Param asked for. A RES output would add twelve
  diagnostics entries and change the port pin.
- **The Type value list wording (Task 10).** The pin says `"2 · two feet"` on a
  fixture that places three. The check names the inaccuracy so nobody reads the
  green as agreement.

## Cost shape for the run

Recorded here because it is a decision about the whole branch rather than any one
file. Tier and effort are set per dispatch, not inherited.

- Mechanical transcription tasks, above all much of phase three: cheap model, low
  effort, and BATCHED where several tasks are the same shape.
- The columns engine and the skin course field: strong model, they are the
  reasoning.
- Task reviewers: medium effort. The final whole-branch review: high, and it
  reads this document plus headings.
- Verification lenses cut from three to two. The third has never been the only
  finder.
